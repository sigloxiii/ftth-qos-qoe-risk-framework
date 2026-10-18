# test_unit_metrics.py
# Objective: automated checks of docs/metrics_spec.md section 9 on the pipeline outputs.
# Inputs:    config.yaml (+ config.local.yaml), data/fiber_units.csv, exclusion files, data/processed/*.csv
# Run:       python -m pytest tests -v   (after python src/pipeline.py)

from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _deep_merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@pytest.fixture(scope="session")
def cfg():
    c = yaml.safe_load(open(ROOT / "config.yaml", encoding="utf-8"))
    local = ROOT / "config.local.yaml"
    if local.exists():
        c = _deep_merge(c, yaml.safe_load(open(local, encoding="utf-8")) or {})
    return c


def _rel(p):
    return ROOT / p


@pytest.fixture(scope="session")
def processed(cfg):
    return _rel(cfg["output"]["processed_dir"])


@pytest.fixture(scope="session")
def metrics(cfg, processed):
    return pd.read_csv(processed / cfg["output"]["unit_metrics_file"])


@pytest.fixture(scope="session")
def insufficient(cfg, processed):
    return pd.read_csv(processed / cfg["output"]["insufficient_data_file"])


@pytest.fixture(scope="session")
def fiber(cfg):
    return pd.read_csv(_rel(cfg["population"]["fiber_units_file"]), encoding="utf-8-sig").rename(columns={"Unit ID": "unit_id"})


# ---------------------------------------------------------------- schema and population
def test_columns_match_config(cfg, metrics):
    assert list(metrics.columns) == cfg["output"]["unit_metrics_columns"]


def test_unit_id_unique_and_subset_of_fiber(metrics, fiber):
    assert metrics["unit_id"].is_unique
    assert set(metrics["unit_id"]) <= set(fiber["unit_id"])


def test_population_matches_expected_counts(cfg, fiber):
    exp = cfg["population"]["expected_counts"]
    assert len(fiber) == exp["total_ftth_filtered"]
    assert fiber["ISP"].value_counts().to_dict() == exp["isps"]


def test_analyzed_plus_insufficient_equals_population(metrics, insufficient, fiber):
    assert len(metrics) + len(insufficient) == len(fiber)
    assert set(metrics["unit_id"]).isdisjoint(set(insufficient["unit_id"]))
    assert set(metrics["unit_id"]) | set(insufficient["unit_id"]) == set(fiber["unit_id"])


def test_excluded_units_consistency(cfg, fiber):
    ftth_ex = pd.read_csv(_rel(cfg["population"]["excluded_units_file"]), encoding="utf-8-sig")["Unit ID"]
    all_ex = pd.read_csv(_rel(cfg["population"]["all_excluded_units_file"]), encoding="utf-8-sig")["Unit ID"]
    assert len(ftth_ex) == cfg["population"]["expected_counts"]["total_excluded"]
    assert set(ftth_ex) <= set(all_ex)
    assert set(ftth_ex).isdisjoint(set(fiber["unit_id"]))


def test_only_allowed_whitebox_models(cfg, metrics):
    assert set(metrics["whitebox_model"]) <= set(cfg["population"]["allowed_whitebox_models"])


# ---------------------------------------------------------------- minimum data and nulls
def test_min_peak_records(cfg, metrics, insufficient):
    n_min = cfg["data_quality"]["n_min_peak_records"]
    assert (metrics["n_peak_records"] >= n_min).all()
    assert (insufficient["n_peak_records"] < n_min).all()


def test_no_nulls_in_latency_and_loss(metrics):
    assert metrics["p95_latency_ms"].notna().all()
    assert metrics["loss_pct"].notna().all()


def test_jitter_null_iff_below_minimum(cfg, metrics):
    n_jit = cfg["metrics"]["jitter"]["min_peak_records"]
    assert (metrics["p95_jitter_ms"].isna() == (metrics["n_peak_jitter_records"] < n_jit)).all()


def test_jitter_never_filled_with_zero(metrics):
    # a zero P95 jitter would be an invented value for a unit without data
    assert not (metrics["p95_jitter_ms"] == 0).any()


# ---------------------------------------------------------------- ranges
def test_loss_range(metrics):
    assert metrics["loss_pct"].between(0, 100).all()


def test_latency_positive(metrics):
    assert (metrics["p95_latency_ms"] > 0).all()


# ---------------------------------------------------------------- flags
def _consistent(values, flags, threshold, tol=1e-4):
    """Strictly greater than the threshold. Values are rounded to 4 decimals in the file, so values within
    `tol` of the threshold are not judged; everything else must match the flag."""
    v = values.fillna(-1)  # null jitter never raises a flag
    return ((v <= threshold + tol) | (flags == 1)).all() and ((v >= threshold - tol) | (flags == 0)).all()


def test_flags_follow_thresholds(cfg, metrics):
    b = cfg["thresholds"]["base"]
    assert _consistent(metrics["p95_latency_ms"], metrics["flag_latency"], b["latency_p95_ms"])
    assert _consistent(metrics["p95_jitter_ms"], metrics["flag_jitter"], b["jitter_p95_ms"])
    assert _consistent(metrics["loss_pct"], metrics["flag_loss"], b["loss_pct"])


def test_severe_follows_thresholds(cfg, metrics):
    s = cfg["thresholds"]["severe"]
    any_sev = pd.DataFrame({
        "lat": metrics["p95_latency_ms"] > s["latency_p95_ms"] + 1e-4,
        "jit": metrics["p95_jitter_ms"].fillna(-1) > s["jitter_p95_ms"] + 1e-4,
        "loss": metrics["loss_pct"] > s["loss_pct"] + 1e-4}).any(axis=1)
    assert (metrics.loc[any_sev, "risk_severe"] == 1).all()
    below = pd.DataFrame({
        "lat": metrics["p95_latency_ms"] < s["latency_p95_ms"] - 1e-4,
        "jit": metrics["p95_jitter_ms"].fillna(-1) < s["jitter_p95_ms"] - 1e-4,
        "loss": metrics["loss_pct"] < s["loss_pct"] - 1e-4}).all(axis=1)
    assert (metrics.loc[below, "risk_severe"] == 0).all()


def test_risk_flag_is_or_of_flags(metrics):
    expected = (metrics["flag_latency"] | metrics["flag_jitter"] | metrics["flag_loss"])
    assert (metrics["risk_flag"] == expected).all()


def test_severe_implies_risk(metrics):
    assert (metrics.loc[metrics["risk_severe"] == 1, "risk_flag"] == 1).all()


# ---------------------------------------------------------------- D-10 descriptive columns
def test_descriptive_columns(metrics):
    assert (metrics["n_days_above_threshold"] >= 0).all()
    assert (metrics["p95_latency_without_worst_day_ms"] <= metrics["p95_latency_ms"] + 1e-9).all()
    # no day above the threshold -> nothing is removed -> both P95 are equal
    none = metrics["n_days_above_threshold"] == 0
    assert (metrics.loc[none, "p95_latency_without_worst_day_ms"] == metrics.loc[none, "p95_latency_ms"]).all()


def test_latency_flag_requires_days_above_threshold(metrics):
    # a P95 above the threshold needs at least one record above it
    assert (metrics.loc[metrics["flag_latency"] == 1, "n_days_above_threshold"] >= 1).all()


# ---------------------------------------------------------------- server rule and data quality log
def test_primary_target_present(metrics):
    assert metrics["primary_target"].notna().all()


def test_quality_log_consistent(cfg, metrics, insufficient):
    log = pd.read_csv(_rel(cfg["data_quality"]["log_file"]))
    get = lambda scope, rule: int(log[(log["scope"] == scope) & (log["rule"] == rule)]["count"].iloc[0])
    assert get("pipeline", "units_analyzed") == len(metrics)
    assert get("pipeline", "units_insufficient") == len(insufficient)
    assert get("pipeline", "units_at_risk") == int(metrics["risk_flag"].sum())
    assert get("pipeline", "analyzed_units_with_null_jitter") == int(metrics["p95_jitter_ms"].isna().sum())
    # invalid-record counts must be zero for the verified FCC files; any change needs a decision
    invalid = log[log["rule"].str.startswith("invalid_")]
    assert (invalid["count"] == 0).all()


# ---------------------------------------------------------------- reference results (base case)
REFERENCE = {"analyzed": 237, "insufficient": 21, "at_risk": 5, "latency": 5, "jitter": 0, "loss": 1, "severe": 1,
             "null_jitter": 93, "units": {943226, 4190285, 24733221, 24840041, 25314177}}


def test_reference_base_case(metrics, insufficient):
    """Regression guard against step_9.py. Fails when data, config or code changes the base case:
    update the spec and decisions.md first, then this reference."""
    if len(metrics) != REFERENCE["analyzed"]:
        pytest.skip("reference applies to the full 258-unit dataset only")
    assert len(insufficient) == REFERENCE["insufficient"]
    assert int(metrics["risk_flag"].sum()) == REFERENCE["at_risk"]
    assert int(metrics["flag_latency"].sum()) == REFERENCE["latency"]
    assert int(metrics["flag_jitter"].sum()) == REFERENCE["jitter"]
    assert int(metrics["flag_loss"].sum()) == REFERENCE["loss"]
    assert int(metrics["risk_severe"].sum()) == REFERENCE["severe"]
    assert int(metrics["p95_jitter_ms"].isna().sum()) == REFERENCE["null_jitter"]
    assert set(metrics.loc[metrics["risk_flag"] == 1, "unit_id"]) == REFERENCE["units"]


'''
============================================================= test session starts ==============================================================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.7.0 -- C:\Users\S1gl0Xiii\AppData\Local\Programs\Python\Python314\python.exe
cachedir: .pytest_cache
rootdir: D:\Capstone FTTH
collected 21 items                                                                                                                              

tests/test_unit_metrics.py::test_columns_match_config PASSED                                                                              [  4%]
tests/test_unit_metrics.py::test_unit_id_unique_and_subset_of_fiber PASSED                                                                [  9%]
tests/test_unit_metrics.py::test_population_matches_expected_counts PASSED                                                                [ 14%]
tests/test_unit_metrics.py::test_analyzed_plus_insufficient_equals_population PASSED                                                      [ 19%]
tests/test_unit_metrics.py::test_excluded_units_consistency PASSED                                                                        [ 23%]
tests/test_unit_metrics.py::test_only_allowed_whitebox_models PASSED                                                                      [ 28%]
tests/test_unit_metrics.py::test_min_peak_records PASSED                                                                                  [ 33%]
tests/test_unit_metrics.py::test_no_nulls_in_latency_and_loss PASSED                                                                      [ 38%]
tests/test_unit_metrics.py::test_jitter_null_iff_below_minimum PASSED                                                                     [ 42%]
tests/test_unit_metrics.py::test_jitter_never_filled_with_zero PASSED                                                                     [ 47%]
tests/test_unit_metrics.py::test_loss_range PASSED                                                                                        [ 52%]
tests/test_unit_metrics.py::test_latency_positive PASSED                                                                                  [ 57%]
tests/test_unit_metrics.py::test_flags_follow_thresholds PASSED                                                                           [ 61%]
tests/test_unit_metrics.py::test_severe_follows_thresholds PASSED                                                                         [ 66%]
tests/test_unit_metrics.py::test_risk_flag_is_or_of_flags PASSED                                                                          [ 71%]
tests/test_unit_metrics.py::test_severe_implies_risk PASSED                                                                               [ 76%]
tests/test_unit_metrics.py::test_descriptive_columns PASSED                                                                               [ 80%]
tests/test_unit_metrics.py::test_latency_flag_requires_days_above_threshold PASSED                                                        [ 85%]
tests/test_unit_metrics.py::test_primary_target_present PASSED                                                                            [ 90%]
tests/test_unit_metrics.py::test_quality_log_consistent PASSED                                                                            [ 95%]
tests/test_unit_metrics.py::test_reference_base_case PASSED                                                                               [100%]

============================================================== 21 passed in 0.76s ==============================================================
'''