# Reconciliation: Python pipeline vs Power Query audit

**Version:** 1.0.0 · **Last updated:** 2026-10-21
**Purpose:** Record the unit-by-unit comparison between the Python pipeline output (`data/processed/`) and an independent recomputation in Power Query, as required by `docs/metrics_spec.md`, section 8. Reconciliation is judged per `Unit ID`; totals are shown only as controls.

## 1. Result

| Scope | Units | Mismatches | Maximum absolute difference |
| :--- | :-: | :-: | :--- |
| Analyzed units, 13 metrics | 237 | 0 | 0.000050 (P95 and loss); 0 (counts, flags) |
| Insufficient units, 3 metrics | 21 | 0 | exact match |
| Units present on one side only | 0 | | |

All 258 units of the population (237 + 21) match. No unit was outside the tolerance, so no unit needed a case-by-case analysis.

## 2. Method

- **Tool:** Power BI Desktop 2.157.1354.0, file `powerbi/ftth_qoe.pbix`. Step-by-step procedure, code and screenshots: `docs/powerbi_implementation.md` (sessions 4A to 7).
- **Audit side:** Power Query queries (`aud_*`) that recompute the metrics from `data/interim/udplatency_ftth.csv` and `data/interim/udpjitter_ftth.csv` (output of `src/steps/step_1.py`), with the same rules: period D-01, valid records, duplicates D-05, peak window D-03, primary server D-04/D-06, minimum records D-02/D-07, P95 with linear interpolation, loss as a ratio of sums, flags with strictly-greater thresholds, severity and the D-10 columns. Thresholds and minimums are Power Query parameters that mirror `config.yaml`.
- **Pipeline side:** `data/processed/ftth_qoe_unit_metrics.csv` (237 analyzed units) and `data/processed/units_insufficient_data.csv` (21 units), as loaded in the report model (`unit_metrics`, `units_insufficient`).
- **Comparison:** full outer join by `unit_id` (queries `rec_units` and `rec_insufficient`), so a unit present on one side only appears in the result. Presence flags, one `ok_<metric>` and one `diff_<metric>` column per metric, and `n_mismatch` per unit.
- **Tolerances** (spec section 8): +/- 0.001 ms for `p95_latency_ms`, `p95_jitter_ms` and `p95_latency_without_worst_day_ms`; +/- 0.001 percentage points for `loss_pct`; exact match for `n_peak_records`, `n_peak_jitter_records`, `n_days_above_threshold` and `risk_flag`. The audit also requires exact match for `primary_target`, `flag_latency`, `flag_jitter`, `flag_loss` and `risk_severe` (stricter than the specification). Null jitter matches only null jitter.

## 3. Cleaning stage (row counts)

Both interim files were cleaned in Power Query and counted at each stage; the counts equal `data/processed/data_quality_log.csv`.

| Stage | Latency | Jitter |
| :--- | :-: | :-: |
| Rows read | 172,800 | 152,730 |
| In analysis period | 172,800 | 152,730 |
| Valid records | 172,800 | 152,730 |
| After removing exact duplicates | 172,791 | 152,726 |
| Conflicting duplicate groups | 0 | 1 |
| After cleaning | 172,791 | 152,724 |

The only conflicting group is in jitter: unit 943232, server `sp1-vm-atlanta-us.samknows.com`, 2022-10-19 21:12:17, 2 rows, dropped completely (D-05).

## 4. Per-unit results

### 4.1 Analyzed units (237)

| Metric | Tolerance | Units compared | Mismatches | Maximum absolute difference |
| :--- | :-: | :-: | :-: | :-: |
| `primary_target` | exact | 237 | 0 | not applicable (text) |
| `n_peak_records` | exact | 237 | 0 | 0 |
| `n_peak_jitter_records` | exact | 237 | 0 | 0 |
| `p95_latency_ms` | 0.001 | 237 | 0 | 0.000050 |
| `p95_jitter_ms` | 0.001 | 237 | 0 | 0.000050 |
| `loss_pct` | 0.001 | 237 | 0 | 0.000050 |
| `n_days_above_threshold` | exact | 237 | 0 | 0 |
| `p95_latency_without_worst_day_ms` | 0.001 | 237 | 0 | 0.000050 |
| `flag_latency`, `flag_jitter`, `flag_loss` | exact | 237 | 0 | 0 |
| `risk_flag`, `risk_severe` | exact | 237 | 0 | 0 |

**Reading.** The pipeline file stores four decimals and the audit computes without rounding, so a maximum difference of 0.000050 (half a unit of the fourth decimal) is the footprint of that rounding. It also shows that the comparison ran: a maximum of exactly 0 in every numeric metric would have been suspicious. All differences are 20 times smaller than the tolerance. Null jitter coincides in the same units (93 analyzed units).

### 4.2 Insufficient units (21)

`primary_target`, `n_peak_records` and `n_peak_jitter_records` match in the 21 units (exact), with none present on one side only.

### 4.3 Control values

| Control | Pipeline | Audit |
| :--- | :-: | :-: |
| Units: analyzed / insufficient / population | 237 / 21 / 258 | 237 / 21 / 258 |
| Units at risk / severe | 5 / 1 | 5 / 1 |
| Latency / jitter / loss flags | 5 / 0 / 1 | 5 / 0 / 1 |
| Persistent / episodic latency flags (D-10) | 4 / 1 | 4 / 1 |
| Analyzed units with null jitter | 93 | 93 |
| Unit 4190285 (episodic case) | P95 50.0035, 1 day, 14.77 without worst day, severe | same |

Screenshots: `docs/img/powerbi/15_reconciliation_totals.png`, `16_reconciliation_summary.png`, `17_reconciliation_insufficient.png`.

![Reconciliation totals](img/powerbi/15_reconciliation_totals.png)

![Reconciliation summary by metric](img/powerbi/16_reconciliation_summary.png)

![Reconciliation of the insufficient units](img/powerbi/17_reconciliation_insufficient.png)

## 5. Findings during the reconciliation

None changed a result; they concern how the comparison is built.

- **`unit_id` type.** It is text in the pipeline tables loaded in the model and integer in the audit. A join without conversion matched no unit (474 rows: 237 on each side only). The comparison converts it to integer; the model tables are unchanged.
- **Rounding.** The pipeline CSV is rounded to four decimals; the audit is not. Differences up to 0.00005 are expected and inside the tolerance.
- **Query evaluation.** Referencing the audit chain many times re-read the interim CSV (3.98 GB read in one load). The comparison queries buffer the audit side with `Table.Buffer`.

## 6. Scope and limits

- **Independence.** The audit was written from the same specification and decisions as the pipeline, so it verifies the implementation of the rules (same output from two independent code paths), not the validity of the decisions D-01 to D-10. Both use linear interpolation for the percentile; agreement does not test that choice.
- **Source.** The audit reads `data/interim/` (output of `step_1.py`, gitignored), not the raw 6.8 GB files. The 258-unit filter in step 1 is therefore not audited here; it is covered by `tests/test_unit_metrics.py`.
- **Not reconciled:** `sensitivity_grid` and `variants_matrix` (precomputed by the pipeline and shown in the report as they are), the UTC-reading and all-servers variants, and the descriptive attributes copied from `fiber_units` (ISP, state, census, speed tiers, Whitebox model).
- **Reproduction.** The interim files must exist locally (`python src/steps/step_1.py`). Open `powerbi/ftth_qoe.pbix`, set the `RepoPath` parameter and refresh. The comparison queries are in `docs/powerbi_implementation.md`, section 10.

## 7. Conclusion

The Power Query audit reproduces the Python pipeline output for the 258 units of the population within the tolerances of `docs/metrics_spec.md`, section 8: 237 analyzed units on 13 metrics and 21 insufficient units on 3 metrics, with 0 mismatches and no unit present on one side only. The reconciliation required by the specification is complete for the scope described in section 6.