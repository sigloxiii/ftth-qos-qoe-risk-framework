# pipeline.py
# Objective: single implementation of the FTTH QoE methodology v3 (docs/metrics_spec.md v1.2.0).
#            Reads the RAW FCC files, applies the rules in config.yaml and writes the processed
#            files that Power BI consumes.
# Inputs:    config.yaml (+ config.local.yaml override), data/fiber_units.csv,
#            raw curr_udplatency.csv and curr_udpjitter.csv (path: inputs.raw_dir)
# Outputs:   data/processed/ftth_qoe_unit_metrics.csv       (analyzed units, 20 columns, spec section 9)
#            data/processed/units_insufficient_data.csv     (units below N_MIN, not scored)
#            data/processed/data_quality_log.csv            (records discarded per rule, duplicates, counts)
#            data/processed/variants_matrix.csv             (2x2: local/UTC x primary/all servers)
#            data/processed/sensitivity_grid.csv            (D-08 grid)
# Usage:     python src/pipeline.py [--config config.yaml] [--refresh-cache] [--no-variants]

import argparse
import copy
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]  # repo root (this file lives in src/)


# ------------------------------------------------------------------ configuration
def deep_merge(base, over):
    """Recursive merge: values in `over` replace those in `base`."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path):
    cfg = yaml.safe_load(open(path, encoding="utf-8"))
    local = Path(path).with_name("config.local.yaml")
    if local.exists():  # machine-specific paths (gitignored)
        cfg = deep_merge(cfg, yaml.safe_load(open(local, encoding="utf-8")) or {})
    if not cfg["inputs"].get("raw_dir"):
        sys.exit("inputs.raw_dir is not set: define it in config.local.yaml")
    return cfg


def rpath(p):
    """Relative paths in the config are relative to the repo root."""
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


# ------------------------------------------------------------------ population
def load_units(cfg):
    pop = cfg["population"]
    u = pd.read_csv(rpath(pop["fiber_units_file"]), encoding="utf-8-sig")
    u = u.rename(columns={"Unit ID": "unit_id", "ISP": "isp", "State": "state", "Census": "census",
                          "Download": "download_mbps", "Upload": "upload_mbps",
                          "Whitebox Model": "whitebox_model"})
    exp = pop["expected_counts"]
    # Stop on any deviation: a silent change in the population invalidates every result
    assert u["unit_id"].is_unique, "duplicate unit_id in fiber_units.csv"
    assert len(u) == exp["total_ftth_filtered"], f"expected {exp['total_ftth_filtered']} units, got {len(u)}"
    assert set(u["whitebox_model"]) <= set(pop["allowed_whitebox_models"]), "model outside allowed_whitebox_models"
    assert set(u["timezone_offset_dst"]) <= set(pop["allowed_timezone_offset_dst"]), "unexpected timezone_offset_dst"
    assert u["isp"].value_counts().to_dict() == exp["isps"], "ISP counts differ from expected_counts"
    return u


# ------------------------------------------------------------------ raw reading and cleaning
def read_raw(cfg, name, ids, refresh):
    """Filters a raw file to the FTTH units (chunked) and caches it as CSV in interim_dir."""
    interim = rpath(cfg["output"]["interim_dir"])
    interim.mkdir(parents=True, exist_ok=True)
    cache = interim / f"pipeline_{name}_ftth.csv"
    if cache.exists() and not refresh:
        print(f"  {name}: cache {cache.name}")
        return pd.read_csv(cache, dtype={"dtime": str})
    src = Path(cfg["inputs"]["raw_dir"]) / cfg["inputs"]["files"][name]
    print(f"  {name}: reading {src} (this takes a while)")
    parts = []
    for chunk in pd.read_csv(src, usecols=cfg["columns"][name], dtype={"dtime": str, "ddate": str},
                             chunksize=2_000_000):
        parts.append(chunk[chunk["unit_id"].isin(ids)])
    df = pd.concat(parts, ignore_index=True)
    df.to_csv(cache, index=False)
    return df


def clean(df, name, cfg, log):
    """Period filter, invalid records and duplicates (spec section 5, steps 1-2). Never caps or fills."""
    start = pd.Timestamp(cfg["analysis_period"]["start"])
    end = pd.Timestamp(cfg["analysis_period"]["end"]) + pd.Timedelta(days=1)  # end date inclusive
    log.append((name, "ftth_rows_read", len(df)))

    df = df.copy()
    df["dtime"] = pd.to_datetime(df["dtime"], format=cfg["time"]["dtime_format"], errors="coerce")
    bad_time = df["dtime"].isna()  # rows with unparseable dtime cannot be placed in the period
    log.append((name, "invalid_dtime_not_parseable", int(bad_time.sum())))
    df = df[~bad_time]

    df = df[(df["dtime"] >= start) & (df["dtime"] < end)]
    log.append((name, "rows_in_analysis_period", len(df)))

    if name == "udplatency":
        n = df["successes"] + df["failures"]
        rules = {
            "invalid_successes_plus_failures_le_0": ~(n > 0),
            "invalid_loss_pct_outside_0_100": (n > 0) & ~((df["failures"] / n * 100).between(0, 100)),
            "invalid_rtt_avg_null_or_negative": ~(df["rtt_avg"] >= 0),
        }
    else:
        rules = {"invalid_jitter_null_or_negative": ~((df["jitter_up"] >= 0) & (df["jitter_down"] >= 0))}
    bad = pd.Series(False, index=df.index)
    for rule, m in rules.items():
        log.append((name, rule, int(m.sum())))
        bad |= m
    df = df[~bad]

    # D-05: key (unit_id, dtime, target); identical copies keep one, conflicting groups are dropped
    key = cfg["data_quality"]["duplicates"]["key"]
    full = df.drop_duplicates()
    log.append((name, "duplicate_exact_extra_rows_removed", len(df) - len(full)))
    conflict = full.duplicated(key, keep=False)
    log.append((name, "duplicate_conflicting_groups", int(full[conflict].groupby(key).ngroups)))
    log.append((name, "duplicate_conflicting_rows_dropped", int(conflict.sum())))
    df = full[~conflict]
    log.append((name, "rows_after_cleaning", len(df)))
    return df.reset_index(drop=True)


def prepare(lat, jit, units, cfg):
    """Adds per-row values in ms, the offset used by the UTC sensitivity and drops unused columns."""
    m = cfg["metrics"]
    off = units.set_index("unit_id")[cfg["time"]["sensitivity_utc_reading"]["timezone_col"]]
    lat = lat[["unit_id", "dtime", "target", "rtt_avg", "successes", "failures"]].copy()
    lat["lat_ms"] = lat["rtt_avg"] / m["latency"]["to_ms_divisor"]
    lat["off_h"] = lat["unit_id"].map(off)
    jit = jit[["unit_id", "dtime", "target", "jitter_up", "jitter_down"]].copy()
    jit["jit_ms"] = (jit["jitter_up"] + jit["jitter_down"]) / 2 / m["jitter"]["to_ms_divisor"]
    jit["off_h"] = jit["unit_id"].map(off)
    return lat, jit


# ------------------------------------------------------------------ metrics
def set_time(df, reading):
    """local: dtime as stored (D-03). utc: dtime + timezone_offset_dst hours (sensitivity)."""
    out = df.copy()
    out["t"] = out["dtime"] if reading == "local" else out["dtime"] + pd.to_timedelta(out["off_h"], unit="h")
    return out


def p95_without_worst_day(g, thr, q):
    """D-10: P95 after removing the date with most records above thr (ties: earliest date)."""
    above = g["lat_ms"] > thr
    if not above.any():
        return g["lat_ms"].quantile(q)
    per_day = g.loc[above].groupby("day").size()
    worst = per_day[per_day == per_day.max()].index.min()
    rest = g.loc[g["day"] != worst, "lat_ms"]
    return rest.quantile(q) if len(rest) else np.nan


def unit_table(lat, jit, cfg, reading, mode):
    """Per-unit metrics for every unit with at least one peak latency record (spec section 5, steps 3-7)."""
    t, s = cfg["time"], cfg["server_rule"]
    q = cfg["metrics"]["percentile"]
    thr = cfg["thresholds"]["base"]["latency_p95_ms"]
    n_jit_min = cfg["metrics"]["jitter"]["min_peak_records"]

    L, J = set_time(lat, reading), set_time(jit, reading)
    L = L[(L["t"].dt.hour >= t["peak_start_hour"]) & (L["t"].dt.hour < t["peak_end_hour_exclusive"])]
    J = J[(J["t"].dt.hour >= t["peak_start_hour"]) & (J["t"].dt.hour < t["peak_end_hour_exclusive"])]

    if mode == "primary_only":
        # D-04/D-06: primary = target with most peak LATENCY records; ties -> alphabetical; used for all metrics
        c = L.groupby(["unit_id", "target"]).size().reset_index(name="n")
        c = c.sort_values(["unit_id", "n", "target"], ascending=[True, False, True])
        primary = c.drop_duplicates("unit_id")[["unit_id", "target"]]
        L = L.merge(primary, on=["unit_id", "target"])
        J = J.merge(primary, on=["unit_id", "target"])
        prim = primary.set_index("unit_id")["target"]
    else:
        prim = pd.Series("ALL", index=L["unit_id"].unique())

    L = L.assign(day=L["t"].dt.normalize())
    g = L.groupby("unit_id")
    out = pd.DataFrame({
        "primary_target": prim,
        "n_peak_records": g.size(),
        "p95_latency_ms": g["lat_ms"].quantile(q),
        "loss_pct": g["failures"].sum() / (g["successes"].sum() + g["failures"].sum()) * 100,  # ratio of sums
        "n_days_above_threshold": L[L["lat_ms"] > thr].groupby("unit_id")["day"].nunique(),
    })
    out["n_days_above_threshold"] = out["n_days_above_threshold"].fillna(0).astype(int)  # a count, not a metric
    out["p95_latency_without_worst_day_ms"] = pd.Series(
        {u: p95_without_worst_day(x, thr, q) for u, x in g}, dtype=float)

    gj = J.groupby("unit_id")
    out["n_peak_jitter_records"] = gj.size().reindex(out.index).fillna(0).astype(int)  # a count, 0 is real
    p95j = gj["jit_ms"].quantile(q).reindex(out.index)
    out["p95_jitter_ms"] = p95j.where(out["n_peak_jitter_records"] >= n_jit_min)  # D-07: null, never 0
    return out


def add_flags(df, thr):
    """Strictly greater than the thresholds; a null jitter never raises a flag."""
    b, sv = thr["base"], thr["severe"]
    df = df.copy()
    df["flag_latency"] = (df["p95_latency_ms"] > b["latency_p95_ms"]).astype(int)
    df["flag_jitter"] = (df["p95_jitter_ms"] > b["jitter_p95_ms"]).astype(int)
    df["flag_loss"] = (df["loss_pct"] > b["loss_pct"]).astype(int)
    df["risk_flag"] = (df[["flag_latency", "flag_jitter", "flag_loss"]].sum(axis=1) > 0).astype(int)
    df["risk_severe"] = ((df["p95_latency_ms"] > sv["latency_p95_ms"]) | (df["p95_jitter_ms"] > sv["jitter_p95_ms"])
                         | (df["loss_pct"] > sv["loss_pct"])).astype(int)
    return df


def split_by_nmin(table, units, n_min):
    """Units with n_peak_records >= N_MIN are analyzed; the rest (including 0 records) are insufficient."""
    full = units[["unit_id"]].merge(table.reset_index().rename(columns={"index": "unit_id"}), on="unit_id", how="left")
    for c in ("n_peak_records", "n_peak_jitter_records"):
        full[c] = full[c].fillna(0).astype(int)
    ok = full["n_peak_records"] >= n_min
    return full[ok].copy(), full[~ok].copy()


def variants_matrix(lat, jit, units, cfg):
    rows = []
    for reading, mode in itertools.product(("local", "utc"), ("primary_only", "all_servers")):
        tb = unit_table(lat, jit, cfg, reading, mode)
        ok, bad = split_by_nmin(tb, units, cfg["data_quality"]["n_min_peak_records"])
        ok = add_flags(ok, cfg["thresholds"])
        rows.append({"time_reading": reading, "server_rule": mode, "analyzed": len(ok), "insufficient": len(bad),
                     "at_risk": int(ok["risk_flag"].sum()), "flag_latency": int(ok["flag_latency"].sum()),
                     "flag_jitter": int(ok["flag_jitter"].sum()), "flag_loss": int(ok["flag_loss"].sum()),
                     "severe": int(ok["risk_severe"].sum())})
    return pd.DataFrame(rows)


def sensitivity_grid(table, units, cfg):
    """D-08: units at risk for every combination, base case (local, primary_only)."""
    g = cfg["thresholds"]["sensitivity"]
    rows = []
    for n_min in g["n_min_peak_records"]:
        ok, _ = split_by_nmin(table, units, n_min)
        for lt, jt, ls in itertools.product(g["latency_p95_ms"], g["jitter_p95_ms"], g["loss_pct"]):
            r = int(((ok["p95_latency_ms"] > lt) | (ok["p95_jitter_ms"] > jt) | (ok["loss_pct"] > ls)).sum())
            rows.append({"n_min": n_min, "latency_p95_ms": lt, "jitter_p95_ms": jt, "loss_pct": ls,
                         "analyzed": len(ok), "at_risk": r, "pct_at_risk": round(100 * r / len(ok), 2) if len(ok) else np.nan})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--refresh-cache", action="store_true", help="re-read the raw files")
    ap.add_argument("--no-variants", action="store_true", help="skip the 2x2 matrix and the D-08 grid")
    a = ap.parse_args()

    cfg = load_config(a.config)
    assert cfg["time"]["dtime_interpretation"] == "local", "base case is the local reading (D-03)"
    assert cfg["server_rule"]["mode"] == "primary_only", "base case is primary_only (D-04)"
    out_dir = rpath(cfg["output"]["processed_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/5 Population")
    units = load_units(cfg)
    ids = set(units["unit_id"])

    print("2/5 Raw files")
    log = []
    lat = clean(read_raw(cfg, "udplatency", ids, a.refresh_cache), "udplatency", cfg, log)
    jit = clean(read_raw(cfg, "udpjitter", ids, a.refresh_cache), "udpjitter", cfg, log)
    lat, jit = prepare(lat, jit, units, cfg)

    print("3/5 Base case (local time, primary server)")
    n_min = cfg["data_quality"]["n_min_peak_records"]
    table = unit_table(lat, jit, cfg, "local", "primary_only")
    ok, bad = split_by_nmin(table, units, n_min)
    ok = add_flags(ok, cfg["thresholds"])
    meta = units[["unit_id", "isp", "state", "census", "download_mbps", "upload_mbps", "whitebox_model"]]
    ok = meta.merge(ok, on="unit_id")[cfg["output"]["unit_metrics_columns"]].sort_values("unit_id")
    bad = meta.merge(bad[["unit_id", "primary_target", "n_peak_records", "n_peak_jitter_records"]], on="unit_id")
    bad["reason"] = f"n_peak_records < {n_min}"

    assert len(ok) + len(bad) == len(units), "analyzed + insufficient must equal the population"
    assert ((ok["p95_jitter_ms"].isna()) == (ok["n_peak_jitter_records"] < cfg["metrics"]["jitter"]["min_peak_records"])).all()
    assert (ok["p95_latency_without_worst_day_ms"] <= ok["p95_latency_ms"] + 1e-9).all()

    ok.to_csv(out_dir / cfg["output"]["unit_metrics_file"], index=False, encoding="utf-8")
    bad.sort_values("unit_id").to_csv(out_dir / cfg["output"]["insufficient_data_file"], index=False, encoding="utf-8")

    log += [("pipeline", "units_population", len(units)), ("pipeline", "units_analyzed", len(ok)),
            ("pipeline", "units_insufficient", len(bad)), ("pipeline", "units_at_risk", int(ok["risk_flag"].sum())),
            ("pipeline", "analyzed_units_with_null_jitter", int(ok["p95_jitter_ms"].isna().sum()))]
    log_path = rpath(cfg["data_quality"]["log_file"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(log, columns=["scope", "rule", "count"]).to_csv(log_path, index=False, encoding="utf-8")

    if not a.no_variants:
        print("4/5 Variants (2x2) and D-08 grid")
        v = variants_matrix(lat, jit, units, cfg)
        v.to_csv(out_dir / cfg["output"].get("variants_file", "variants_matrix.csv"), index=False)
        sensitivity_grid(table, units, cfg).to_csv(
            out_dir / cfg["output"].get("sensitivity_file", "sensitivity_grid.csv"), index=False)
        print(v.to_string(index=False))

    print("5/5 Summary")
    print(f"  analyzed {len(ok)} / {len(units)} | insufficient {len(bad)} | at risk {int(ok['risk_flag'].sum())} "
          f"(latency {int(ok['flag_latency'].sum())}, jitter {int(ok['flag_jitter'].sum())}, "
          f"loss {int(ok['flag_loss'].sum())}, severe {int(ok['risk_severe'].sum())}) | "
          f"null jitter {int(ok['p95_jitter_ms'].isna().sum())}")
    print(ok[ok["risk_flag"] == 1][["unit_id", "p95_latency_ms", "p95_jitter_ms", "loss_pct",
                                    "n_days_above_threshold", "p95_latency_without_worst_day_ms"]].round(2).to_string(index=False))
    print(f"  files in {out_dir}")


if __name__ == "__main__":
    main()



'''
PS C:\Users\S1gl0Xiii\Documents\GitHub\ftth-qoe-risk-optimization> & C:\Users\S1gl0Xiii\AppData\Local\Programs\Python\Python314\python.exe "d:/Capstone FTTH/src/pipeline.py"
1/5 Population
2/5 Raw files
  udplatency: reading D:\Capstone FTTH\data\raw\validated-data-sept2022\curr_udplatency.csv (this takes a while)
  udpjitter: reading D:\Capstone FTTH\data\raw\validated-data-sept2022\curr_udpjitter.csv (this takes a while)
3/5 Base case (local time, primary server)
4/5 Variants (2x2) and D-08 grid
time_reading  server_rule  analyzed  insufficient  at_risk  flag_latency  flag_jitter  flag_loss  severe
       local primary_only       237            21        5             5            0          1       1
       local  all_servers       248            10       21            21            0          1       1
         utc primary_only       239            19        4             4            0          0       0
         utc  all_servers       250             8       17            17            0          0       1
5/5 Summary
  analyzed 237 / 258 | insufficient 21 | at risk 5 (latency 5, jitter 0, loss 1, severe 1) | null jitter 93
 unit_id  p95_latency_ms  p95_jitter_ms  loss_pct  n_days_above_threshold  p95_latency_without_worst_day_ms
  943226           23.13            NaN      0.00                       9                             22.86
 4190285           50.00           4.48      0.05                       1                             14.77
24733221           23.96            NaN      0.01                       7                             22.73
24840041           35.80           3.89      1.66                      16                             35.61
25314177           30.48            NaN      0.00                       9                             23.09
  files in D:\Capstone FTTH\data\processed
  
'''