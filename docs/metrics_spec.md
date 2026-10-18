# Metrics Specification — FTTH QoE Risk

**Spec version:** 1.2.0 · **Last updated:** 2026-10-15
**Status:** Baseline. Any change is made first in this document, then in `config.yaml` and `src/`, and recorded in the Changelog (section 12).
**Central rule:** one implementation of each transformation (Python). Power BI does **not** recalculate metrics; it only visualizes them.

**Related documents:** `config.yaml` (values), `docs/decisions.md` (decisions D-01 to D-10 with alternatives and evidence), `docs/data_dictionary.md` (columns and time handling), `docs/data_inspection.md` (Step 0 results), `docs/procedure_summary_v3.md` (procedure overview).

---

## 1. Scope and Population

- **Population source:** `unit-profile-sept2022.xlsx` (FCC MBA, 13th Report, September 2022 data).
- **Filter 1:** `Technology = Fiber` → 285 units.
- **Filter 2 (hardware):** `Whitebox Model IN (skwb8, skwb8p, ac1750v2)` → **258 units**. The 27 excluded units (`wnr3500l-high` 17, `wdr3600` 6, `wr1043nd` 2, `wr741nd` 1, `wr741ndv4` 1) are kept in `data/excluded_legacy_ftth_units.csv` for audit. `data/excluded_legacy_units.csv` lists every Whitebox outside the analysis (non-fiber, or fiber not used) and includes those 27.
- **Rationale:** the Whitebox is the measurement instrument. Models with insufficient CPU or port speed (FastEthernet, no hardware NAT) create artificial latency and loss (instrument bias).
- **ISPs in scope:** Cincinnati Bell 120, Verizon 76, Frontier 62.
- **Grain:** 1 row = 1 `Unit ID`.
- **Analysis period (D-01):** 2022-09-12 to 2022-10-31, both ends inclusive, applied to `dtime` as stored. The files contain 50 days, not only September. The full period gives about 120 peak records per unit (the P95 rests on about 6 observations); September alone gives about 32 (about 1.6 observations), which is too few for a tail statistic.

## 2. Data Verification (Step 0, completed)

Step 0 verified the three raw files (`curr_udplatency.csv`, `curr_udpjitter.csv`, `curr_udpcloss.csv`) against the FCC MBA Technical Appendix. Results are in `docs/data_inspection.md` and `docs/data_dictionary.md` (section 6). Items that shape this specification:

1. **Headers** differ from the FCC dictionary: `ddate` is present in all three files; `location_id` is absent from `curr_udplatency`; the jitter file uses lowercase `latency`.
2. **`curr_udpcloss`** records outage/disconnection events (`duration` in µs; `packets` = number of packets lost in the event, a count per event). `packets` is never used as a percentage and is never divided by a constant.
3. **Offsets:** `timezone_offset_dst` is in hours (values -4, -5, -7) and is consistent with each unit's state. All 258 units observe daylight saving time (DST).
4. **Coverage:** every one of the 258 units has rows in `curr_udplatency` and `curr_udpjitter`; 242 have rows in `curr_udpcloss` (event-based, so no rows means no events).
5. **Invalid records:** 0 found for each rule in section 5.2 (confirmed again in `step_9.py`, both files).
6. **Duplicates:** found and handled by the policy in section 5.2.
7. **Servers:** a unit uses 1 to 4 test servers (68, 131, 45 and 14 units use 1, 2, 3 and 4). See section 4.
8. **Packets per row (check 6, closed):** `successes + failures` ranges from 50 to 2,401 per row (P1 = 65, median 2,065, 172,791 rows). The count varies widely by row, which is why loss is a ratio of sums (section 5).
9. **Jitter unit:** microseconds, supported indirectly: per-unit median jitter 0.70 ms against median `rtt_std` 0.96 ms (median ratio 0.83, Spearman 0.816, `step_10.py`). No documentation states the unit; see section 11.

## 3. Time and Peak Window (D-03)

- `dtime` is a naive timestamp (`YYYY-MM-DD HH:MM:SS`). The FCC documentation states that it is UTC, but the project data show that it behaves as each unit's **local time**: the hourly RTT profile of Pacific units does not trail the Eastern one by the 3 hours that UTC would imply (correlation at a +3 h shift is about 0 or negative in Cable and DSL; best alignment -1 to -2 h, much closer to 0 than to +3). See `docs/decisions.md`, D-03.
- **Base case:** `dtime` is read as local time. `local_hour = hour(dtime)`. No offset is added.
- **Peak window:** local hour **≥ 19 and < 23** (19:00:00–22:59:59), 4 hours.

```python
# dtime already is the unit's local time; no offset is applied
df["local_hour"] = df["dtime"].dt.hour
peak = df[(df["local_hour"] >= 19) & (df["local_hour"] < 23)]  # peak window [19, 23)
```

- **Sensitivity (reported with every result):** UTC reading, as documented by the FCC. `local_hour = hour(dtime + timezone_offset_dst)`. `timezone_offset_dst` applies to every record because US DST ended on 2022-11-06, after the last record. `timezone_offset` is never used.
- **Limitations:** the evidence for the local reading is indirect and contradicts the FCC general note. Fiber was not tested (only 18 Pacific units). `dtime` marks the end of each test, so records near 19:00 and 23:00 may partly belong to the adjacent hour.

## 4. Server Rule (D-04, D-06)

A unit tests against 1 to 4 servers at different distances. The access line is the same for all of them, so RTT differences between servers reflect distance and route, not the line. Pooling servers makes a unit look worse because of server distance (21 units at risk with all servers vs 5 with the primary server in the base case; 17 vs 4 under the UTC reading; `N_MIN` applied, `step_9.py`).

- **Base case, `primary_only` (D-04):** each unit is measured against its **primary server**, the `target` with the most peak-window records for that unit. Ties are broken by alphabetical order of `target`.
- **One rule for all metrics (D-06):** the primary server is determined **once per unit, from the peak records of the latency file**, and is used for latency, loss and jitter. The jitter file does not get its own primary server. If a unit has no peak jitter records on that server, its jitter is null (section 5).
- **Sensitivity (reported with every result):** all servers pooled.

```python
# primary target per unit: most peak-window latency records, ties by alphabetical order
counts = peak_lat.groupby(["unit_id", "target"]).size().reset_index(name="n")
counts = counts.sort_values(["unit_id", "n", "target"], ascending=[True, False, True])
primary = counts.drop_duplicates("unit_id")[["unit_id", "target"]]
peak_lat_primary = peak_lat.merge(primary, on=["unit_id", "target"])
peak_jit_primary = peak_jit.merge(primary, on=["unit_id", "target"])  # D-06: same server for jitter
```

## 5. Metrics per Unit

All metrics use **only records inside the peak window** and, in the base case, only the primary server. Order of operations:

1. Keep the 258 units and the analysis period (sections 1 and 3).
2. Remove invalid records (log them) and handle duplicates (section 5.2).
3. Keep records in the peak window.
4. Apply the server rule (section 4).
5. Count `n_peak_records` (latency) and `n_peak_jitter_records` (jitter); units with `n_peak_records < N_MIN` are reported separately and not scored.
6. Compute the three metrics. `p95_jitter_ms` is computed only if `n_peak_jitter_records >= N_MIN_JITTER` (D-07); otherwise it stays null.
7. Compute the descriptive columns of D-10.

| Metric | Source | Per-row value | Per-unit aggregation |
| :--- | :--- | :--- | :--- |
| `p95_latency_ms` | `curr_udplatency.rtt_avg` (µs) | `rtt_avg / 1000` | 95th percentile, linear interpolation |
| `p95_jitter_ms` | `curr_udpjitter` (`jitter_up`, `jitter_down`, µs) | `(jitter_up + jitter_down) / 2 / 1000` | 95th percentile, linear interpolation; null if `n_peak_jitter_records < N_MIN_JITTER` |
| `loss_pct` | See 5.1 | `failures / (successes + failures) * 100` | **Ratio of sums:** `sum(failures) / sum(successes + failures) * 100` |
| `n_peak_records` | `curr_udplatency` | Count of valid peak records (after the server rule) | Count |
| `n_peak_jitter_records` | `curr_udpjitter` | Count of valid peak jitter records on the primary server | Count |
| `n_days_above_threshold` (D-10) | `curr_udplatency.rtt_avg` | `rtt_avg / 1000 > latency_p95_ms` (base threshold) | Number of distinct dates with at least one such record |
| `p95_latency_without_worst_day_ms` (D-10) | `curr_udplatency.rtt_avg` | `rtt_avg / 1000` | P95 after removing all peak records of the date with the most records above the threshold (ties: earliest date); equals `p95_latency_ms` if no record is above the threshold |

- **Percentile:** linear interpolation (pandas `quantile(0.95)` default; equivalent to `PERCENTILE.INC` in Excel and Power BI, and to the default `List.Percentile` in Power Query).
- **Ratio of sums:** weights each test by its number of packets. Averaging per-row percentages biases the result when the packet count varies.
- **Jitter minimum (D-07):** `N_MIN_JITTER = 50` (set in `config.yaml`), peak jitter records on the primary server. A unit below it keeps its latency and loss metrics and stays in the denominator; its jitter is null, never 0, and the count of such units is reported with every result.
- **Jitter unit:** µs, supported indirectly (section 2, item 9) and not documented by the FCC. Jitter is dominated by the upstream value (raw medians: `jitter_up` 1,220, `jitter_down` 86), so the average of both mostly reflects upload (section 11).
- **Ties in the worst day (D-10):** when several dates share the maximum number of records above the threshold, the earliest date is removed, so the result is reproducible. The value can depend on that choice: unit 24733221 has 3 tied dates (2022-09-18, 09-20, 10-11; P95 without worst day 22.73 removing the earliest) and unit 24840041 has 6 tied dates (35.61 removing 2022-09-12). Neither conclusion changes (both stay above 20 ms, persistent).
- **Descriptive columns (D-10):** `n_days_above_threshold` and `p95_latency_without_worst_day_ms` are computed for every analyzed unit, on the same records as `p95_latency_ms`. They are not part of `risk_flag`.

### 5.1 Loss source

- **Single source (confirmed in the FCC MBA Technical Appendix 2023):** `failures` and `successes` from `curr_udplatency`. The appendix defines UDP packet loss as the fraction of UDP packets lost in the UDP latency test, maps it to `curr_udplatency.csv`, and gives `failures / (successes + failures)`. A packet is counted as lost if there is no response within 3 seconds.
- **`curr_udpcloss` is not a loss percentage source.** It records outage events (count per event). It is never divided or averaged as a percentage.
- **Optional future use:** `curr_udpcloss` could feed a separate **availability** metric (number and total duration of outages in the peak window). It stays outside the base `risk_flag` and would be added in a later version of this specification.
- One loss source per specification version. No mixing.

### 5.2 Data quality

- **Invalid records** (excluded and counted, never corrected with caps): `successes + failures <= 0`; `loss_pct` outside [0, 100]; `rtt_avg` null or negative; `jitter_up` or `jitter_down` null or negative; `dtime` not parseable. Step 0 and `step_9.py` found 0 records for each rule.
- **Forbidden:** capping values (`min(x, 100)`) and filling nulls with 0 (`fillna(0)`). An invented zero makes a unit without data look perfect. Counts (for example, 0 jitter records) are real counts and may be 0; metrics are never filled.
- **Duplicates (D-05):** key (`unit_id`, `dtime`, `target`). If the duplicate rows are identical, keep one; if they conflict, drop all of them. Every case is counted in the log. Found: `curr_udplatency` 16 rows in 7 groups, all exact (9 extra rows removed); `curr_udpjitter` 10 rows, 8 exact (4 extra rows removed) and 2 conflicting (unit 943232, both dropped).
- **Minimum data (D-02):** a unit enters the risk analysis if `n_peak_records >= N_MIN`, with `N_MIN = 50` (set in `config.yaml`), counted **after** the server rule. The top 5% of 50 records contains at least 2.5 observations, the smallest sample where a P95 is still defensible. Base case: 21 units fall below it, so **237 of 258 units** are analyzed (UTC reading: 19 below, 239 analyzed; 8 units fall below `N_MIN` before the server rule).
- **Units without enough data:** listed in `data/processed/units_insufficient_data.csv` and left out of the risk denominator. Every report states `units_analyzed / 258`.
- **Quality log:** the pipeline writes `data/processed/data_quality_log.csv` with the number of records discarded per rule, the duplicate counts and the number of analyzed units with null jitter.

## 6. Risk Definition

- **Status of the thresholds:** they are **operating thresholds defined by the project**, not values from a standard. Earlier citations to ITU-T G.114/Y.1541 and to specific sections of the FCC report are **not verified** (G.114 covers one-way delay and Y.1541 defines network classes with other values) and are not cited until confirmed in the source.
- **Base thresholds** (parameters in `config.yaml`):

| Parameter | Base value |
| :--- | :--- |
| `latency_p95_ms` | 20 |
| `jitter_p95_ms` | 5 |
| `loss_pct` | 1.0 |

- **Rule:** `risk_flag = 1` if `p95_latency_ms > 20` **or** `p95_jitter_ms > 5` **or** `loss_pct > 1.0` (strictly greater). A null jitter does not exceed any threshold. The individual flags (`flag_latency`, `flag_jitter`, `flag_loss`) are also stored to show which metric triggers the risk.
- **Jitter stays in the rule (D-09):** no unit exceeds 5 ms in the base case (maximum 4.48 ms), and the jitter flag is 0 in every variant of section 7. The rule is not changed to match the results; the report states it.
- **Severity tier:** `risk_severe = 1` if `loss_pct > 10` or `p95_latency_ms > 50` or `p95_jitter_ms > 15`.
- **Episodic vs persistent (D-10):** a latency flag is described as *episodic* when `p95_latency_without_worst_day_ms <= latency_p95_ms`, and *persistent* otherwise. The wording is descriptive: it does not change `risk_flag` or any count. Base case: 5 at risk, 4 persistent and 1 episodic (unit 4190285, whose severe tier rests on an interpolated P95 of 50.00 ms).
- Thresholds are not chosen to reproduce a previous result. Changing one requires a change in this specification and a Changelog entry.

## 7. Sensitivity Analysis (mandatory with every result)

All figures come from `step_9.py`, with `N_MIN = 50` applied and the same rules in every variant. Counts from `step_3.py` to `step_6.py` (10 / 6 / 17 / 22 flagged) did not apply `N_MIN` and are not comparable with this table.

| Variant | What changes | Analyzed | Insufficient | At risk |
| :--- | :--- | ---: | ---: | ---: |
| Base case | Local time + primary server | 237 | 21 | 5 |
| All servers | Local time, all servers pooled | 248 | 10 | 21 |
| UTC reading | `dtime + timezone_offset_dst`, primary server | 239 | 19 | 4 |
| UTC reading, all servers | UTC reading, all servers pooled | 250 | 8 | 17 |

- By metric (base case): latency 5, jitter 0, loss 1 (unit 24840041), severe 1 (unit 4190285). The jitter flag is 0 in all four variants.
- Between the local and UTC readings (both with the primary server), 12 units change status: 5 change `risk_flag` (943226, 4190285 and 24840041 only under the local reading; 1006958 and 3892905 only under the UTC reading) and 7 change only their qualification against `N_MIN` (925928, 942200, 1000161, 3799009, 3814781, 24559133, 55105449).
- **Additional variants** (base case with one change):

| Variant | At risk |
| :--- | ---: |
| Jitter on its own primary server (D-06 alternative; unit 3798765 enters) | 6 |
| Jitter evaluated only with at least `N_MIN_JITTER` records (D-07; base rule) | 5 |
| Persistence criterion (minimum days above the threshold; D-10 alternative) | 4 |

- **Grid (D-08):** units at risk (and % of analyzed units) for latency {20, 30, 50} ms × jitter {3, 4, 5} ms × loss {0.05, 0.1, 0.5, 1.0} % × `N_MIN` {30, 50, 100}, around the base case. The base thresholds do not change (D-09). Reference `N_MIN` results (analyzed / insufficient / at risk): 30 → 253 / 5 / 7; 50 → 237 / 21 / 5; 100 → 89 / 169 / 1.
- Per-unit distributions used to choose the grid (base case, 237 analyzed): loss median 0.007%, P99 0.43%, maximum 1.66% (units above 0.05 / 0.1 / 0.5 / 1 / 2 / 5%: 18 / 10 / 2 / 1 / 0 / 0); P95 jitter median 1.00 ms, maximum 4.48 ms (units above 3 / 4 / 5 ms: 10 / 3 / 0).
- The result is sensitive to `N_MIN` (1 to 7 units at risk). The report gives the base figure together with this range.

## 8. Reconciliation Python ↔ Power BI

Power BI consumes `data/processed/ftth_qoe_unit_metrics.csv` generated by Python. If a metric is reimplemented in Power Query for audit:

1. Export both tables and join by `Unit ID`.
2. Tolerances: `p95_latency_ms`, `p95_jitter_ms` and `p95_latency_without_worst_day_ms` ±0.001 ms; `loss_pct` ±0.001 percentage points; `risk_flag`, `n_peak_records`, `n_peak_jitter_records` and `n_days_above_threshold` exact match; same number of units; null jitter in the same units.
3. Units that differ are analyzed one by one (window, time convention, server rule, nulls); reconciliation is never done by totals only.
4. The result is saved in `docs/reconciliation.md`.

Power Query equivalent of the base peak window: `Time.Hour([dtime]) >= 19 and Time.Hour([dtime]) < 23`, with no offset.

## 9. Final Dataset Schema

`data/processed/ftth_qoe_unit_metrics.csv` (UTF-8, no version in the name; versions live in git tags):

`unit_id, isp, state, census, download_mbps, upload_mbps, whitebox_model, primary_target, n_peak_records, n_peak_jitter_records, p95_latency_ms, p95_jitter_ms, loss_pct, n_days_above_threshold, p95_latency_without_worst_day_ms, flag_latency, flag_jitter, flag_loss, risk_flag, risk_severe`

Automated tests (`tests/`):

- `unit_id` is unique and a subset of `fiber_units.csv`.
- `n_peak_records >= N_MIN` for every unit in the file.
- 0 nulls in `p95_latency_ms` and `loss_pct`; `p95_jitter_ms` is null if and only if `n_peak_jitter_records < N_MIN_JITTER`.
- `0 <= loss_pct <= 100`; `p95_latency_ms > 0`.
- `risk_flag == (flag_latency | flag_jitter | flag_loss)`.
- `n_days_above_threshold >= 0`; `p95_latency_without_worst_day_ms <= p95_latency_ms`.
- `analyzed + insufficient == 258`.
- The 27 units in `excluded_legacy_ftth_units.csv` are contained in `excluded_legacy_units.csv`, and none of them is in `fiber_units.csv`.

## 10. Business Impact

- Dollar savings and avoided truck rolls are omitted: there is no source for the unit cost, and the baseline (v1) was invalidated by bias.
- If an estimate is included, it goes as a **scenario** with explicit, parameterized assumptions (cost per truck roll, rate of unnecessary visits), labeled as illustrative.

## 11. Limitations

- Two months of data (2022-09-12 to 2022-10-31) from a non-random sample of volunteer units; results do not represent all FTTH subscribers.
- 220 of the 258 units (85%) are in the US Eastern time zone.
- Hardware is filtered by the nominal capability of each model, not by a per-unit throughput test.
- The local-time reading of `dtime` rests on indirect evidence and contradicts the FCC general note; the UTC reading is reported as a sensitivity. Fiber was not tested (only 18 Pacific units).
- Thresholds are project-defined and their sensitivity is part of the reported results.
- The jitter unit (µs) is supported by indirect evidence only. The observed test `duration` (about 15 s) differs from the documented 10 s. Jitter is dominated by the upstream value, so the average of upstream and downstream mostly reflects upload.
- Jitter is evaluated for 144 of the 237 analyzed units (61%); the other 93 have fewer than 50 peak jitter records and a null jitter (D-07).
- The count of units at risk is sensitive to `N_MIN` (7 / 5 / 1 for `N_MIN` 30 / 50 / 100). Units 943226 and 24733221 stay close to the latency threshold (22.9 and 24.0 ms without their worst day) with only 53 and 59 peak records.
- One of the 5 units at risk (4190285) is an episode of a single day (2022-10-23) that is not a server event; its cause cannot be determined from these data (D-10).

## 12. Changelog

- **1.2.0** (2026-10-15): decisions D-06 to D-10 and the results of `step_9.py`, `step_10.py` and `step_11.py` incorporated.
  - One server rule for all metrics: the latency primary server is used for latency, loss and jitter (D-06, section 4).
  - Jitter evaluated only with at least 50 peak jitter records on the primary server; otherwise null (D-07, section 5). `n_peak_jitter_records` added to the dataset to make the rule auditable.
  - Sensitivity grid replaced: latency × jitter × loss × `N_MIN` (D-08, section 7). The loss grid {0.5, 1, 2, 5} % is removed.
  - Base thresholds unchanged; jitter stays in the rule (D-09, section 6).
  - Descriptive columns `n_days_above_threshold` and `p95_latency_without_worst_day_ms` and the episodic/persistent wording added; risk rule unchanged (D-10, sections 5, 6, 9).
  - Sensitivity matrix recomputed with `N_MIN` applied (237 / 21 / 5; 248 / 10 / 21; 239 / 19 / 4; 250 / 8 / 17) and the 12 units that change status listed (section 7).
  - Check 6 closed (50 to 2,401 packets per row); jitter unit supported indirectly; limitations and tests updated.
  - Reconciliation tolerances extended to the new columns.
- **1.1.0** (2026-10-11): translated to English; text recovered from v1.0.1 (commit `5cecc72`) after `metrics_spec.md` was overwritten by the data dictionary in commit `c8fcc37`.
  - Analysis period set to 2022-09-12 to 2022-10-31 (D-01).
  - `N_MIN = 50` (D-02).
  - `dtime` treated as local time, no offset; UTC reading as sensitivity (D-03).
  - Server rule `primary_only`; all servers as sensitivity (D-04).
  - Duplicate policy (D-05).
  - Order of operations and the sensitivity matrix added; `primary_target` added to the dataset; exclusion files and tests updated.
  - Step 0 section rewritten as completed.
  - Dictionary and config values aligned.
- **1.0.1**: definition of `curr_udpcloss` confirmed with the FCC MBA Technical Appendix 2023 (outage events; `packets` = count of lost packets); single loss source = `curr_udplatency`.
- **1.0.0**: baseline: window [19, 23) with `timezone_offset_dst`; loss as ratio of sums from `curr_udplatency`; no capping or `fillna(0)`; parameterized thresholds with sensitivity analysis.

## 13. Open Items

- **`config.yaml`:** add `N_MIN_JITTER = 50`, replace the loss grid with the D-08 grids, and add the two D-10 columns. Update it in the same commit as this version.
- **`step_9.py`:** the base case runs without a jitter minimum (`jit_min=0`). The result is the same (diagnostic 6), but `pipeline.py` must apply D-07 explicitly.
- **`docs/data_dictionary.md` and `docs/data_inspection.md`:** record check 6 and the jitter unit evidence; the latter still lists every check as pending.
- **Jitter test length:** observed `duration` (about 15 s) against the documented 10 s.
- **Fiber time convention:** the local reading was not tested on Fiber (18 Pacific units).