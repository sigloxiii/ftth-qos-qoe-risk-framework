# FTTH QoE Capstone - Procedure Summary v3.2

**Methodology:** v3.0 | **Spec:** v1.2.0 | **Config:** mirrors spec v1.2.0 | **Document:** v3.3 | **Last updated:** 2026-10-18 | **Author:** Eng. Rafael Cansigno P.

Companion documents: `docs/decisions.md` (decision log, D-01 to D-10), `docs/data_dictionary.md` (columns and time handling), `docs/data_inspection.md` (Step 0 results), `docs/metrics_spec.md` (rules), `config.yaml` (values).

## 1. Original problem and v1/v2 audit findings

### Project goal
Identify FTTH units at risk of poor QoE during local evening peak hours (19:00-22:59) using FCC MBA telemetry Sep-Oct 2022, and separate real degradation from measurement artifacts.

### v1/v2 failures

**v1 - Convenience bias:**
- Only the first 1000 rows per monthly file were read.

**v2 - Instrument bias:**
- Legacy Whiteboxes `wnr3500l-high, wdr3600, wr1043nd, wr741nd, wr741ndv4` cannot forward at gigabit line rate. They create the degradation they report.
- FTTH population: 285 raw -> 258 after filter. The 27 excluded units are in `excluded_legacy_ftth_units.csv`.

**v2.1.3 -> v2.2 - Loss misinterpreted (Finding #1):**
- `curr_udpcloss.packets` was treated as loss %, then patched as `packets/10`.
- FCC dictionary: that file records **outage/disconnection events**, NOT continuous loss %.
- Real loss comes from `curr_udplatency`: `failures / (successes + failures)`.

**v2 - Inconsistent implementations:**
- Python used `timezone_offset` while Power BI used `timezone_offset_dst` -> peak window shifted 1 h.
- Peak window 19-22:59 vs 19-23:59, different loss sources. Totals matched but unit-level reconciliation failed.
- Thresholds changed without justification: 20 ms -> 50 ms latency.

**v2.2 - Data quality:**
- `fillna(0)` made a unit with no data look perfect (0 ms).
- `clip 100%` turned corrupt counters into "total loss".
- v3: invalid records are excluded and counted in a log; units with insufficient data are reported separately.

## 2. Procedure: Step 0 to Step 11

### Script map

Each script is a numbered step (`step_N.py`) with its objective in the header and its recorded output at the end. Every figure in this document traces back to one of them. The scripts print to the console only; `pipeline.py` will be the single implementation.

| Script | Objective | Feeds |
| :--- | :--- | :--- |
| `step_0.py` | Real structure, coverage, targets, hourly RTT, offsets | Dictionary checks 1, 4, 7, 8 |
| `step_1.py` | Extract the 258 FTTH units to interim CSVs; hourly tests; servers per unit; peak records per unit (full period vs September) | D-01, D-02 |
| `step_2.py` | Server mixing (RTT spread, share of the primary server); invalid and duplicate counts; global loss | D-04 (motivation), spec 5.2 |
| `step_3.py` | Impact of the time convention on the risk flag (all servers) | D-03 |
| `step_4.py` | Duplicates by key | D-05 |
| `step_5.py` | Server mixing: all servers vs primary server | D-04 |
| `step_6.py` | Time convention repeated under `primary_only` | D-03 |
| `step_7.py` | Eastern vs Pacific RTT profile, all technologies pooled, shifts 0..+6 h | D-03 |
| `step_8.py` | Same test by technology, shifts -6..+6 h | D-03 |
| `step_9.py` | Base case v3 with one consistent rule set (`N_MIN` applied); 2 x 2 sensitivity matrix; 8 diagnostics | D-06, D-07, D-08, D-09 |
| `step_10.py` | Jitter unit (jitter vs `rtt_std`); P95 latency of unit 4190285 | D-10, spec section 2 |
| `step_11.py` | Chronic vs episodic latency flags; is the 4190285 event shared by its server? | D-10 |

Steps 1 to 6 were written before D-03: in them "spec", `h_spec`, `h_local` and `h_dst` mean the UTC reading (`dtime + timezone_offset_dst`), they do not apply `N_MIN` and their flagged counts (10 / 6 / 17 / 22) are not comparable with each other or with `step_9.py`. Details in `src/README.md`.

### Step 0 - Real structure verification
`data/CSV_previews.md` - first 10 rows of the real files. Full results in `docs/data_inspection.md`.

**Real columns vs FCC dictionary:**
- `udplatency`: the dictionary lists `location_id` but the real file does NOT have it. The real file has `ddate`, which the dictionary does not list for latency/jitter.
- `udpjitter`: uses lowercase `latency` vs `Latency` in the dictionary.
- Verified in `config.yaml`:
```yaml
udplatency: [unit_id, dtime, ddate, target, rtt_avg, rtt_min, rtt_max, rtt_std, successes, failures]
udpjitter: [unit_id, dtime, ddate, target, packet_size, stream_rate, duration, packets_up_sent, packets_down_sent, packets_up_recv, packets_down_recv, jitter_up, jitter_down, latency, successes, failures]
udpcloss: [unit_id, dtime, ddate, duration, target, address, packets]
```

**Verified facts:**
- `dtime` is a string "%Y-%m-%d %H:%M:%S" with no TZ marker, NOT unix epoch.
- `timezone_offset_dst` is in HOURS (-4, -5, -7); all 258 units observe DST.
- FTTH period is 2022-09-12 to 2022-10-31 (50 days), not September only.
- Median RTT per unit is 2.5-17.2 ms; global loss is about 0.022%.
- `rtt_avg` is in microseconds.
- `successes + failures` ranges from 50 to 2,401 per row (P1 = 65, median 2,065; `step_9.py`, dictionary check 6 closed). The packet count varies widely by row, which supports the ratio of sums.
- The jitter unit is microseconds, supported indirectly (median jitter / `rtt_std` = 0.83, Spearman 0.816; `step_10.py`). No documentation states it.
- Invalid records: 0 in every rule, in both files (`step_2.py`, `step_9.py`).

### Step 1 - Analysis period (D-01)
September alone gives ~32 peak records per unit (P95 rests on ~1.6 observations). The full period gives ~120 (about 6 observations).
```yaml
analysis_period: 2022-09-12 to 2022-10-31   # both inclusive
```

### Step 2 - Minimum records per unit (D-02)
`n_min_peak_records: 50`. The top 5% of 50 records holds at least 2.5 observations. `N_MIN` is counted after the server rule, on peak records of the latency file.
- Base case (local time + primary server): 21 units are below 50, so **237 of 258** units are analyzed.
- UTC reading: 19 units below, 239 analyzed. Before the server rule 8 units are below 50 (`step_1.py`).

### Step 4 - Duplicates (D-05)
Key: `[unit_id, dtime, target]`
- Latency: 16 rows in 7 groups, all exact duplicates (9 extra rows removed).
- Jitter: 10 rows; 8 exact (4 extra rows removed) and 2 conflicting (unit 943232, both dropped).

**Policy v3.0:** `keep_one_if_identical_else_drop_all`. Every case is counted in `data_quality_log.csv`.

### Step 5 - Server rule (D-04)
A unit uses 1 to 4 servers at different distances (68, 131, 45 and 14 units use 1, 2, 3 and 4). The access line is the same, so RTT differences reflect distance and route, not the line.
- Measured under the UTC reading without `N_MIN` (`step_5.py`): all servers flag 17 units; primary server only flags 6. 11 units are flagged only with all servers pooled.
- With `N_MIN` applied (`step_9.py`): all servers 21 vs primary server 5 under the local reading; 17 vs 4 under the UTC reading.

### Step 7/8 - Local vs UTC time (D-03)

**Question:** is `dtime` UTC as the FCC says, or already local time?

**Procedure:** correlation of the mean hourly RTT profile of Eastern units (UTC-4) vs Pacific units (UTC-7), shifting the Pacific profile by k hours.
- If `dtime` were UTC, Pacific should trail Eastern by 3 h -> expected k=+3.
- If `dtime` is local, expected k=0.

**Observed (by technology):**

| Technology | Pacific units | k=0 (local) | k=+3 (UTC) | Best k | Peak Eastern / Pacific (dtime hour) |
| :--- | ---: | ---: | ---: | ---: | :--- |
| Cable | 138 | 0.762 | -0.107 | -1 (0.892) | 21 / 20 |
| DSL | 175 | 0.594 | -0.018 | -2 (0.799) | 21 / 19 |

- Correlation at +3 h is about 0 or negative in both technologies -> UTC rejected.
- Best alignment is -1 to -2 h, much closer to 0 than to +3.
- The residual 1-2 h lead of Pacific is not a time zone offset; most likely usage behavior or composition. Not proven, so it is not over-interpreted.
- The DSL best k (-2/-3) is outside the -1..+1 criterion set beforehand, but the local-vs-UTC distinction is clear.
- Fiber was not tested: only 18 Pacific units.

**Conclusion:** indirect evidence. It does not prove the FCC documentation wrong, only that the latency data do not behave as it says. In `step_0.py` the pooled hourly mean RTT of all units varies by at most 0.4 ms under any reading, so that check alone is not conclusive.

### Step 9 - Base case and sensitivity matrix (D-06 to D-09)
`step_9.py` applies one consistent rule set in every variant: period D-01, peak window [19, 23), duplicates D-05, invalid records excluded and counted, one server per unit (primary server of the latency file for latency, loss and jitter), `N_MIN = 50` after the server rule, base thresholds 20 ms / 5 ms / 1% (strictly greater), no capping and no `fillna(0)`. Results are in section 5.

Diagnostics that fed decisions D-06 to D-09:
- Per-unit loss: median 0.007%, maximum 1.66%; units above 0.05 / 0.1 / 0.5 / 1%: 18 / 10 / 2 / 1. Per-unit P95 jitter: median 1.00 ms, maximum 4.48 ms; units above 3 / 4 / 5 ms: 10 / 3 / 0.
- No unit is flagged by jitter alone.
- Jitter on its own primary server: the primary differs from the latency one in 68 of the 237 analyzed units; the result changes by one unit (3798765 enters: 6 at risk).
- Peak jitter records per analyzed unit: median 56, minimum 10; 93 of 237 units have fewer than 50. Evaluating jitter only with at least 50 records leaves the result unchanged.
- `N_MIN` 30 / 50 / 100: 253 / 237 / 89 analyzed and 7 / 5 / 1 at risk.

### Step 10 - Jitter unit and the P95 of unit 4190285
- Jitter: per-unit median 0.70 ms against median `rtt_std` 0.96 ms (ratio 0.83, Spearman 0.816, 258 units), consistent with microseconds. Raw medians `jitter_up` 1,220 and `jitter_down` 86: the average mostly reflects upstream.
- Unit 4190285: its P95 of 50.00 ms is an interpolation between 39.26 and 53.59 ms (sorted positions 62 and 63 of 66 records), not a measurement ceiling. All 6 records above 30 ms fall on 2022-10-23.

### Step 11 - Chronic vs episodic flags (D-10)
- For the 5 units at risk, removing the day with the most records above 20 ms leaves four above the threshold (22.73 to 35.61 ms) and takes 4190285 down to 14.77 ms.
- On 2022-10-23 the other 69 units that use the same server (`sp1-vm-ashburn-us`) kept an RTT of 8.4-9.7 ms, while unit 4190285 rose to 53-57 ms between 18:00 and 21:00 and had started near 16:00. The event is specific to that unit, not to the server; its cause cannot be determined from these data.

## 3. Decisions

All decisions are recorded with alternatives and impact in `docs/decisions.md`.

| ID | Decision | Date |
| :--- | :--- | :--- |
| D-01 | Analysis period 2022-09-12 to 2022-10-31 | 2026-10-10 |
| D-02 | `N_MIN` = 50 peak records | 2026-10-10 |
| D-03 | `dtime` treated as local time; UTC reading as sensitivity | 2026-10-11 |
| D-04 | `primary_only` server rule; all servers as sensitivity | 2026-10-11 |
| D-05 | Duplicates: keep one if identical, drop all if conflicting | 2026-10-10 |
| D-06 | One server rule for all metrics: the latency primary server is used for latency, loss and jitter | 2026-10-11 |
| D-07 | Jitter evaluated only with at least 50 peak jitter records; otherwise null | 2026-10-15 |
| D-08 | Sensitivity grid: latency x jitter x loss x `N_MIN` | 2026-10-15 |
| D-09 | Jitter stays in the risk rule; base thresholds not adjusted to the results | 2026-10-15 |
| D-10 | Episodic latency events: rule unchanged, two descriptive columns | 2026-10-15 |

### D-03: dtime as local time (confirmed 2026-10-11)

```yaml
time:
  dtime_is_utc: false
  dtime_interpretation: local
  peak_start_hour: 19
  peak_end_hour_exclusive: 23   # 19:00:00 to 22:59:59 local
```

**Implementation (`src/pipeline.py`):**
```python
# v2 assumed dtime was UTC and added an offset, without testing the assumption
# v3.0, D-03: dtime already is local time, no offset
local_hour = df["dtime"].dt.hour
```

The unit-profile offsets stay verified but are NOT used in the base case. The UTC reading is reported as a sensitivity:
```yaml
sensitivity_utc_reading:
  rule: "local_hour = hour(dtime + timezone_offset_dst)"
```

**Base result (`primary_only`):**
- Without `N_MIN` (`step_6.py`): 10 units flagged (6 under the UTC reading). 6 units change flag: 5 enter, 1 leaves (943226, 1006958, 3798765, 4190285, 24840041, 25314149).
- With `N_MIN` applied (`step_9.py`): 5 at risk (4 under the UTC reading). 12 units change status: 5 change `risk_flag` (943226, 4190285 and 24840041 only under the local reading; 1006958 and 3892905 only under the UTC reading) and 7 change only their qualification against `N_MIN`.

### D-04 and D-06: primary_only as base case, one server for all metrics

```yaml
server_rule:
  mode: primary_only
  primary_definition: "target with the most peak-window records for the unit"
  primary_source_file: udplatency      # D-06
  apply_to: [latency, loss, jitter]    # D-06
  tie_break: "alphabetical order of target"
  report_sensitivity_all_servers: true
```

### D-07 to D-10 in brief

- **D-07:** `metrics.jitter.min_peak_records: 50`. Below it `p95_jitter_ms` is null, reported, never 0; latency and loss still scored. 93 of 237 analyzed units are below.
- **D-08:** the sensitivity grid replaces the old loss grid {0.5, 1, 2, 5}, which would have left most cells empty (maximum per-unit loss 1.66%).
- **D-09:** jitter stays in the rule although no unit exceeds it (maximum 4.48 ms); thresholds are defined before the results and are not tuned to them.
- **D-10:** the rule does not change. Two descriptive columns are added (`n_days_above_threshold`, `p95_latency_without_worst_day_ms`) and the report says "5 at risk: 4 persistent and 1 episodic". A persistence criterion is reported only as a sensitivity (4 at risk).

### Thresholds - restored to spec

The `config.yaml` values are aligned with the specification:

```yaml
thresholds:
  base:
    latency_p95_ms: 20
    jitter_p95_ms: 5
    loss_pct: 1.0
  severe:
    latency_p95_ms: 50
    jitter_p95_ms: 15
    loss_pct: 10
  risk_rule: "risk_flag = 1 if p95_latency_ms > ... OR ... (strictly greater)"
  sensitivity:                       # D-08
    latency_p95_ms: [20, 30, 50]
    jitter_p95_ms: [3, 4, 5]
    loss_pct: [0.05, 0.1, 0.5, 1.0]
    n_min_peak_records: [30, 50, 100]
```

Any other value must be justified first in the spec and changed in `config.yaml` in the same commit.

### Outputs and parameters

- Outputs Parquet `unit_qoe_v3.*` did not match the decision to use CSV -> now `ftth_qoe_unit_metrics.csv`, `units_insufficient_data.csv`, `data_quality_log.csv`.
- `transform: "p95_us_to_ms"` was text that code had to interpret -> explicit parameters `percentile: 0.95, to_ms_divisor: 1000, method: linear`.
- The unit-level dataset has 20 columns (spec section 9), including `n_peak_jitter_records` and the two D-10 columns.

### Population files

- `fiber_units.csv`: 258 FTTH units in scope (Technology = Fiber and Whitebox model `skwb8`, `skwb8p` or `ac1750v2`).
- `excluded_legacy_ftth_units.csv`: 27 FTTH units excluded because the hardware is not credible -> `excluded_units_file` in config, used by the pipeline.
- `excluded_legacy_units.csv`: all out-of-scope units (non-fiber and unused fiber). Includes the 27. Audit only -> `all_excluded_units_file`.

Tests verify:
- the 27 are contained in `all_excluded`;
- no overlap between `fiber_units` and the excluded files.

## 4. What "it is an outage event, not a loss %" means

`curr_udpcloss.csv` does **not** measure continuous loss %. A row exists only when an outage/disconnection event occurred (FCC definition).

**Real columns:**
```
udpcloss: [unit_id, dtime, ddate, duration, target, address, packets]
```

**Observed in previews:**
- `duration` is about 4,500,000 µs = 4.5 s
- `packets` = 2-3

Illustrative reading: "at 19:00:00, unit 123 had a 4.5 s outage with 2 packets lost against target X". The row has no denominator, so it cannot give a percentage.

**Real loss (v3.0) comes from `curr_udplatency.csv`:**
```
udplatency: [..., successes, failures]
successes=2300, failures=5 in one hour
```

Formula (`config.yaml`):
```yaml
formula: "sum(failures) / sum(successes + failures) * 100"
method: "ratio_of_sums"   # weights by packets, not mean of %
```

**v3.0 code (applied per unit, only on peak-window records of the primary server):**
```python
loss = df.groupby("unit_id").apply(
  lambda g: g["failures"].sum() / (g["successes"].sum() + g["failures"].sum()) * 100
)
```

**v2 error:**
- v2.1.3: `loss = packets` -> if packets=2, it reported 2% (false).
- v2.2: `loss = packets/10` -> if packets=2, it reported 0.2% (still false).

v3 keeps `udpcloss` only as an audit reference, outside `risk_flag`. Real global loss is about 0.022% (from `udplatency`). Per unit in the peak window (base case) the median is 0.007% and only one unit exceeds 1% (24840041, 1.66%).

## 5. Base case results (`step_9.py`, `step_11.py`)

The figures are reproduced by `step_9.py` over the same units; `pipeline.py` must match them unit by unit before they are published.

**Sensitivity matrix** (`N_MIN` applied; analyzed / insufficient / at risk):

| | Primary server | All servers |
| :--- | :--- | :--- |
| Local time (base) | **237 / 21 / 5** | 248 / 10 / 21 |
| UTC reading | 239 / 19 / 4 | 250 / 8 / 17 |

- By metric (base case): latency 5, jitter 0, loss 1 (unit 24840041), severe 1 (unit 4190285). The jitter flag is 0 in all four variants.
- Additional variants of the base case: jitter on its own primary server 6; jitter evaluated only with at least 50 records 5; persistence criterion 4.
- `N_MIN` 30 / 50 / 100: 7 / 5 / 1 at risk (253 / 237 / 89 analyzed). The report gives the base figure with this range.

**Units at risk** (base case):

| Unit | Peak records | Days > 20 ms | P95 (ms) | P95 without worst day (ms) | Type |
| :--- | ---: | ---: | ---: | ---: | :--- |
| 943226 | 53 | 9 | 23.13 | 22.86 | Persistent |
| 4190285 | 66 | 1 | 50.00 | 14.77 | Episodic |
| 24733221 | 59 | 7 | 23.96 | 22.73 | Persistent |
| 24840041 | 131 | 16 | 35.80 | 35.61 | Persistent |
| 25314177 | 62 | 9 | 30.48 | 23.09 | Persistent |

- 943226 and 24733221 stay close to the threshold with 53 and 59 peak records; both leave the result at `N_MIN` = 100.
- About 120 peak records per unit (median) in the full period.

**Also reported with every run:**
- Grid of D-08 (latency x jitter x loss x `N_MIN`): units at risk and % of analyzed units in each combination.

**Outputs:**
- `data/processed/ftth_qoe_unit_metrics.csv` - per-unit metrics (spec section 9)
- `data/processed/units_insufficient_data.csv` - fewer than 50 peak records
- `data/processed/data_quality_log.csv` - data quality counters, duplicates and units with null jitter

**Reproducibility:**
```bash
# config.yaml has raw_dir: null (commitable)
# config.local.yaml is gitignored:
inputs:
  raw_dir: "D:/Capstone FTTH/data/raw/validated-data-sept2022"

python src/pipeline.py
```
Dependencies: pandas and PyYAML (plus openpyxl to read the unit profile).

## 6. Status and next steps

| Item | Status |
| :--- | :--- |
| `docs/decisions.md` v1.1.0 (D-01 to D-10) | Done |
| `docs/metrics_spec.md` v1.2.0 | Done |
| `config.yaml` (spec 1.2.0) | Done |
| `docs/data_inspection.md` | Done |
| `docs/procedure_summary_v3.md` v3.3 | Done |
| `step_9.py`, `step_10.py`, `step_11.py` | Done |
| Loss sensitivity grid review | Done (D-08) |
| Check 6 (`successes + failures` distribution) | Done |
| `docs/data_dictionary.md` v1.3.0 | Done |
| README update | Done |
| `src/pipeline.py` | Done |
| `tests/` (21 checks) | Done, all passing |
| Pipeline run and `data/processed/` outputs | Done: reproduces section 5 unit by unit |
| Python <-> Power BI reconciliation | Done: 258 units, 0 mismatches (`docs/reconciliation.md`) |
| Power BI report | In progress: pages 1-3 of 6 (`docs/powerbi_implementation.md`) |
| Results and findings section | Pending |

**Remaining workflow**
1. Finish the Power BI report (pages 4-6) and session 9 (performance, documentation, publishing).
2. Results and findings section, and the final README update.

Done on 2026-10-17: `src/pipeline.py` applies D-07 explicitly (the base case in `step_9.py` runs without a jitter minimum; the result is the same), the pipeline reproduces the base case and the matrix of section 5, and `tests/` passes. One difference with `step_11.py`: with ties in the worst day, the pipeline removes the earliest date (D-10), so `p95_latency_without_worst_day_ms` is 22.73 for unit 24733221 and 35.61 for unit 24840041 (`step_11.py` printed 23.98 and 35.81); no flag or conclusion changes (`step_11_1.py`).