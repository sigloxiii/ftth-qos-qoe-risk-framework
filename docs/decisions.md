# Decision Log

**Version:** 1.1.0 · **Last updated:** 2026-10-15
**Purpose:** Record each methodological decision with its alternatives, evidence and impact, so any result can be traced to a justified choice. A decision is changed only by adding a new entry that supersedes it; the metrics specification (`docs/metrics_spec.md`) and `config.yaml` are updated in the same commit.

**Status values:** Accepted · Superseded

| ID | Decision | Date | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- |
| D-01 | Analysis period 2022-09-12 to 2022-10-31 | 2026-10-10 | Accepted | `step_2.py` |
| D-02 | `N_MIN` = 50 peak records per unit | 2026-10-10 | Accepted | `step_1.py`, `step_3.py` |
| D-03 | `dtime` treated as local time; UTC reading as sensitivity | 2026-10-11 | Accepted | `step_6.py`, `step_7.py`, `step_8.py` |
| D-04 | One server per unit (`primary_only`); all servers as sensitivity | 2026-10-11 | Accepted | `step_5.py`, `step_6.py` |
| D-05 | Duplicates: keep one if identical, drop all if conflicting | 2026-10-10 | Accepted | `step_4.py` |
| D-06 | One server rule for all metrics: the latency primary server is used for latency, loss and jitter | 2026-10-11 | Accepted | `step_9.py` (diagnostic 4) |
| D-07 | Jitter is evaluated only with at least 50 peak jitter records | 2026-10-15 | Accepted | `step_9.py` (diagnostics 5, 6) |
| D-08 | Sensitivity grid: latency × jitter × loss × `N_MIN` | 2026-10-15 | Accepted | `step_9.py` (diagnostics 2, 7) |
| D-09 | Jitter stays in the risk rule; base thresholds are not adjusted to the results | 2026-10-15 | Accepted | `step_9.py` (diagnostics 2, 3) |
| D-10 | Episodic latency events: rule unchanged, two descriptive columns | 2026-10-15 | Accepted | `step_10.py`, `step_11.py` |

---

## D-01 Analysis period

**Decision:** use the full observed period, 2022-09-12 to 2022-10-31 (both ends inclusive).

**Alternatives considered**
- September only (the original plan): about 32 peak records per unit, so the P95 rests on about 1.6 observations.
- Full period: about 120 peak records per unit, so the P95 rests on about 6 observations.

**Reason:** the P95 is a tail statistic and needs enough observations to be stable. The files contain 50 days, not one month, so the original "September" scope did not match the data.

**Impact:** the README and the specification must say "2022-09-12 to 2022-10-31", not "September".

## D-02 Minimum peak records per unit

**Decision:** `N_MIN` = 50 peak-window records. Units below it are reported in `units_insufficient_data.csv` and are not scored.

**Reason:** the top 5% of 50 records contains at least 2.5 observations, which is the smallest sample where a P95 is still defensible.

**Impact**
- 8 units are excluded before the server rule.
- 19 units are excluded after the `primary_only` rule under the UTC reading, so 239 of 258 units are analyzed there.
- Base case (local time + primary server, `step_9.py`): **237 analyzed / 21 insufficient**. `N_MIN` is counted after the server rule, on peak records of the latency file.

## D-03 Time convention of `dtime`

**Decision:** `dtime` is treated as the unit's **local time**. The peak window is `hour(dtime)` in [19, 23), with no offset added. The documented reading (UTC plus `timezone_offset_dst`) is reported as a sensitivity with every result.

**Alternatives considered**

| Reading | Rule | Flagged units (`primary_only`, no `N_MIN`) |
| :--- | :--- | ---: |
| Local (base case) | `hour(dtime)` | 10 |
| UTC (FCC documentation) | `hour(dtime + timezone_offset_dst)` | 6 |
| All hours (no window) | none | 8 |

These counts come from `step_6.py`, which does not apply `N_MIN`. With `N_MIN` applied (`step_9.py`): local 5, UTC 4.

**Evidence**
- Eastern and Pacific mean hourly RTT profiles were compared, shifting the Pacific one by k hours. UTC implies k = +3; local implies k = 0.
- Cable: correlation 0.762 at k=0 and −0.107 at k=+3 (best k = −1, 0.892).
- DSL: correlation 0.594 at k=0 and −0.018 at k=+3 (best k = −2, 0.799).
- Fiber was not tested: only 18 Pacific units.

**Reason:** the data do not behave as UTC in either technology. The residual 1 to 2 h lead of the Pacific profile is not a time zone offset; it most likely reflects usage behavior or composition.

**Limitations:** the evidence is indirect and contradicts the FCC general note. The DSL best shift (−2 h) is outside the −1..+1 range set beforehand, but the decision is local versus UTC, and k=+3 is clearly rejected.

**Impact:** 6 units change flag between readings (943226, 1006958, 3798765, 4190285, 24840041, 25314149): 5 flagged only under local, 1 only under UTC. With `N_MIN` applied (`step_9.py`), 12 units change risk status or qualification between the two readings. The unit-profile offsets stay verified but are not used in the base case.

**Files updated:** `config.yaml` (`time` block), `data_dictionary.md` v1.2.0 (section 4, checks 3 and 4), `metrics_spec.md` section 3 (pending).

## D-04 Server rule

**Decision:** compute metrics on one server per unit, the **primary server**: the target with the most peak-window records (ties broken alphabetically). Using all servers is reported as a sensitivity.

**Alternatives considered**
- All servers pooled: 17 units flagged.
- Primary server only: 6 units flagged (under the UTC reading; 10 under the local reading).
- These counts come from `step_5.py` and `step_6.py`, without `N_MIN`. With `N_MIN` applied (`step_9.py`): local + all servers 21, local + primary server 5.

**Reason:** a unit uses 1 to 4 servers at different distances (68, 131, 45 and 14 units use 1, 2, 3 and 4). The access line is the same for all of them, so RTT differences between servers reflect distance and route, not the line. Pooling them flags units because of server distance. Servers are assigned by proximity, so the primary server is the nearest, most representative one.

**Impact:** 11 units flagged only with all servers pooled. Records kept: 77.7%. Units below `N_MIN` after the rule: 19 under the UTC reading, 21 under the local reading (see D-02).

## D-05 Duplicate records

**Decision:** duplicates are defined by the key (`unit_id`, `dtime`, `target`). If the duplicate rows are identical, keep one; if they conflict, drop all of them. Every case is counted in `data_quality_log.csv`.

**Evidence:** `curr_udplatency` has 16 rows in 7 groups, all exact (9 extra rows). `curr_udpjitter` has 10 rows: 8 exact and 2 conflicting (unit 943232). Applied in `step_9.py`: latency 9 exact copies removed; jitter 4 exact copies removed and 2 conflicting rows dropped; 0 invalid records in either file.

**Reason:** an exact duplicate carries no extra information. A conflicting pair has no objective way to decide which row is right, so neither is used (no silent choice).

**Impact:** negligible (about 0.005% of rows).

## D-06 One server rule for all metrics

**Decision:** each unit has one server for all three metrics: the primary server of the **latency** file (most peak latency records, ties alphabetical). Latency, loss and jitter are computed on that server.

**Alternatives considered:** jitter on its own primary server (the target with most peak jitter records). The primary server differs from the latency one in 68 of the 237 analyzed units, and the base case changes by one unit (3798765 enters the risk set: 6 at risk instead of 5).

**Reason:** one unit, one measured path. Taking each metric from a different server would make the flags depend on different routes for the same unit.

**Impact:** the open item on the jitter primary server in `metrics_spec.md` section 13 is closed.

## D-07 Minimum peak records for jitter

**Decision:** jitter is evaluated only if the unit has at least 50 peak jitter records on its primary server. Otherwise `p95_jitter_ms` stays null and is reported; it is never replaced by 0. The unit stays qualified for latency and loss.

**Evidence** (`step_9.py`, diagnostics 5 and 6)
- Peak jitter records per analyzed unit: minimum 10, median 56, maximum 120. 93 of 237 analyzed units (39%) have fewer than 50.
- Applying the minimum leaves the base case unchanged: 237 / 21 / 5, with 0 units flagged by jitter in both versions.

**Impact:** `step_9.py` runs the base case without a jitter minimum (`jit_min=0`); the pipeline must apply this rule explicitly. The number of units with null jitter is reported with every result. The open item on `N_MIN` for jitter in `metrics_spec.md` section 13 is closed.

## D-08 Sensitivity grid

**Decision:** the sensitivity analysis varies, around the base case, latency {20, 30, 50} ms, jitter {3, 4, 5} ms, loss {0.05, 0.1, 0.5, 1.0} % and `N_MIN` {30, 50, 100}. This supersedes the loss grid {0.5, 1, 2, 5} % in `config.yaml` and `metrics_spec.md` section 7.

**Evidence** (`step_9.py`, diagnostics 2 and 7)
- Per-unit loss (237 analyzed): median 0.007%, P99 0.43%, maximum 1.66%. Units above 0.05 / 0.1 / 0.5 / 1 / 2 / 5%: 18 / 10 / 2 / 1 / 0 / 0. The old grid (0.5 to 5%) left most cells empty.
- Per-unit P95 jitter: median 1.00 ms, maximum 4.48 ms. Units above 3 / 4 / 5 ms: 10 / 3 / 0.
- `N_MIN` (analyzed / insufficient / at risk): 30 → 253 / 5 / 7; 50 → 237 / 21 / 5; 100 → 89 / 169 / 1.

**Impact:** the base thresholds do not change (see D-09). The grid is reported with every result.

## D-09 Jitter in the risk rule and thresholds

**Decision:** `p95_jitter_ms > 5` stays in the risk rule even though no unit exceeds it (maximum 4.48 ms). The base thresholds (20 ms, 5 ms, 1%) are not adjusted to the results.

**Reason:** a threshold defined before seeing the data does not become wrong because it does not trigger; tuning it to produce flags would reverse the logic. Jitter is reported with its distribution and the grid in D-08 shows what lower thresholds would do.

**Impact:** the jitter flag is 0 in every variant of the matrix. The report states this explicitly.

## D-10 Episodic latency events

**Decision:** the risk rule does not change. A unit flagged by latency stays flagged even if the excess comes from a single episode. The final dataset adds two descriptive columns for every analyzed unit, and the report separates persistent from episodic flags.

**New columns** (`data/processed/ftth_qoe_unit_metrics.csv`, computed on peak-window records of the primary server, after D-05 duplicate handling)

| Column | Definition |
| :--- | :--- |
| `n_days_above_threshold` | Number of distinct dates with at least one peak record where `rtt_avg / 1000 > latency_p95_ms` (base threshold, 20 ms) |
| `p95_latency_without_worst_day_ms` | P95 of `rtt_avg / 1000` after removing every peak record of the date with the most records above the threshold (ties: earliest date). If no record is above the threshold, equals `p95_latency_ms` |

**Report wording:** a latency flag is called *episodic* when `p95_latency_without_worst_day_ms <= latency_p95_ms`, and *persistent* otherwise. The label is descriptive only: it is not part of `risk_flag` and does not change any count. Base case: **5 at risk, 4 persistent and 1 episodic.**

**Evidence** (`step_10.py`, `step_11.py`; base case local time + primary server)

| Unit | Peak records | Records > 20 ms | Days > 20 ms | P95 (ms) | P95 without worst day (ms) | Type |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| 943226 | 53 | 11 | 9 | 23.13 | 22.86 | Persistent |
| 4190285 | 66 | 6 | 1 | 50.00 | 14.77 | Episodic |
| 24733221 | 59 | 10 | 7 | 23.96 | 23.98 | Persistent |
| 24840041 | 131 | 44 | 16 | 35.80 | 35.81 | Persistent |
| 25314177 | 62 | 28 | 9 | 30.48 | 23.09 | Persistent |

- Unit 4190285: all 6 records above 30 ms fall on 2022-10-23. Its RTT rose from about 14 ms to 53-57 ms between 18:00 and 21:00 (`dtime` hour), started near 16:00 (about 32 ms) and returned to 12.5 ms at 23:00. The other 69 units that use the same server (`sp1-vm-ashburn-us`) stayed at 8.4-9.7 ms that day, so the event is not a server event. The cause (line, local network or unit-specific route) cannot be determined from these data.
- Its P95 of 50.00 ms is an interpolation between 39.26 and 53.59 ms (sorted positions 62 and 63 of 66). No record equals 50.0 ms, so it is not a measurement ceiling. Its `risk_severe` flag (`p95_latency_ms > 50`) rests on that interpolation and is reported as episodic.

**Alternatives considered**
- *Persistence criterion in the risk rule (minimum days above threshold):* any minimum from 2 to 7 days removes only unit 4190285 (the others have 7, 9, 9 and 16 days). It would define the criterion after seeing which unit it excludes, which D-09 rules out. It may be reported as a sensitivity (4 at risk, 0 severe), never as the base rule.
- *Exclude unit 4190285:* hides a real episode of at least 7 hours that is not a server artifact, and adds a population exclusion with no basis in the data.

**Impact**
- Counts do not change: 237 analyzed / 21 insufficient / 5 at risk (2.1%), 1 severe.
- `metrics_spec.md` section 9 (schema) gains the two columns and `tests/` checks `p95_latency_without_worst_day_ms <= p95_latency_ms` and `n_days_above_threshold >= 0`.
- Limitation to state in the report: units 943226 and 24733221 stay close to the threshold (22.9 and 24.0 ms without their worst day) with only 53 and 59 peak records, so their flag is sensitive to `N_MIN` (both leave the result at `N_MIN` = 100).

---

## Reference results (`step_9.py`, `N_MIN` applied)

| Variant | Analyzed | Insufficient | At risk |
| :--- | ---: | ---: | ---: |
| Local time + primary server (base case) | 237 | 21 | 5 |
| Local time + all servers | 248 | 10 | 21 |
| UTC reading + primary server | 239 | 19 | 4 |
| UTC reading + all servers | 250 | 8 | 17 |

Base case flags: latency 5, jitter 0, loss 1 (unit 24840041), severe 1 (unit 4190285).

## Open items

- Jitter unit (µs): supported indirectly. Per-unit median jitter 0.70 ms against median `rtt_std` 0.96 ms (median ratio 0.83, Spearman 0.816, `step_10.py`), but no documentation states it. Keep it under Limitations. The documented test length (10 s) differs from the observed `duration` (about 15 s) and remains open.
- Jitter is dominated by the upstream value (raw medians: `jitter_up` 1,220, `jitter_down` 86), so `(jitter_up + jitter_down) / 2` mostly reflects upload. State it under Limitations.
- Time convention for Fiber was not tested (only 18 Pacific units); the local reading rests on Cable and DSL.
- Pending updates for D-06 to D-10 in `metrics_spec.md` (sections 5, 7, 9, 13 and Changelog), `config.yaml` (loss grid, jitter minimum, new columns) and `data_inspection.md`.
- Check 6 is closed: `successes + failures` ranges from 50 to 2,401 per row (P1 = 65, median 2,065), which supports the ratio of sums.