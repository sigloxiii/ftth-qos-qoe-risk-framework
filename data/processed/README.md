# data/processed - Pipeline outputs

Final outputs of the pipeline (`python src/pipeline.py`). **The Power BI report consumes only this folder**; it never reads the raw files. Names carry no version (versions live in git tags). Settings come from `config.yaml` (`output:` section); the method is specified in [`docs/metrics_spec.md`](../../docs/metrics_spec.md) and the decisions D-01 to D-10 in [`docs/decisions.md`](../../docs/decisions.md).

All files are UTF-8 CSV. Metric columns use 4 decimals; flags are computed before rounding.

## Base case

| Parameter | Value | Decision |
| :--- | :--- | :--- |
| Analysis period | 2022-09-12 to 2022-10-31 | D-01 |
| Minimum peak records per unit (`N_MIN`) | 50 | D-02 |
| Time reading | `dtime` as local time | D-03 |
| Server rule | One primary server per unit (the latency primary server, used for latency, loss and jitter) | D-04, D-06 |
| Peak window | 19:00-22:59 local time | D-03 |
| Risk thresholds | P95 latency > 20 ms, P95 jitter > 5 ms, loss > 1 % (strictly greater) | D-09 |
| Severe thresholds | P95 latency > 50 ms, P95 jitter > 15 ms, loss > 10 % | `config.yaml`, metrics_spec |
| Minimum jitter records | 50 peak jitter records, otherwise jitter stays empty (never 0) | D-07 |

## Files

| File | Rows | Content |
| :--- | :-: | :--- |
| `ftth_qoe_unit_metrics.csv` | 237 | One row per **analyzed** unit: metrics, flags and context. Main table of the report. |
| `units_insufficient_data.csv` | 21 | Units set aside because they have fewer than `N_MIN` peak records, with the reason. |
| `variants_matrix.csv` | 4 | Result for each time reading (local / UTC) and server rule (primary only / all servers). |
| `sensitivity_grid.csv` | 108 | Units at risk for each combination of `N_MIN`, latency, jitter and loss thresholds. |
| `data_quality_log.csv` | 23 | Records read, removed and kept at each cleaning rule, plus the unit totals. |

The 237 analyzed and 21 insufficient units add up to the **258-unit population** (FTTH units of the September 2022 FCC MBA release; see `data/fiber_units.csv`).

### `ftth_qoe_unit_metrics.csv`

| Column | Meaning |
| :--- | :--- |
| `unit_id` | Unit identifier (unique). |
| `isp`, `state`, `census` | Provider, US state and census region of the unit. |
| `download_mbps`, `upload_mbps` | Subscribed speed tier. |
| `whitebox_model` | Whitebox (measurement device) model. |
| `primary_target` | Test server used for the unit (D-06). |
| `n_peak_records` | Latency/loss records in the peak window (at least 50). |
| `n_peak_jitter_records` | Jitter records in the peak window. |
| `p95_latency_ms` | 95th percentile of latency (`rtt_avg`) over peak records, ms. |
| `p95_jitter_ms` | 95th percentile of jitter over peak records, ms. **Empty** when the unit has fewer than 50 peak jitter records (93 units). |
| `loss_pct` | Packet loss over peak records, ratio of sums (failures / total), in %. |
| `n_days_above_threshold` | Days with at least one peak record above the latency threshold (D-10). |
| `p95_latency_without_worst_day_ms` | P95 latency after removing the day with the most records above the threshold (D-10). Used to separate episodic from persistent flags. |
| `flag_latency`, `flag_jitter`, `flag_loss` | 1 if the metric exceeds its threshold, otherwise 0. |
| `risk_flag` | 1 if any of the three flags is 1. |
| `risk_severe` | 1 if any metric exceeds its severe threshold. |

A **persistent** latency flag is one where `p95_latency_without_worst_day_ms` is still above 20 ms; it is **episodic** if it falls to 20 ms or less (D-10). The classification is descriptive and does not change `risk_flag`.

### `units_insufficient_data.csv`

Same descriptive columns as above (`unit_id` to `primary_target`), `n_peak_records`, `n_peak_jitter_records` and `reason` (always `n_peak_records < 50`). These units have no metrics or flags; they are counted in the population but not in the percentages at risk.

### `variants_matrix.csv`

One row per combination of `time_reading` (`local` / `utc`) and `server_rule` (`primary_only` / `all_servers`), with `analyzed`, `insufficient`, `at_risk`, `flag_latency`, `flag_jitter`, `flag_loss` and `severe`. Row `local / primary_only` is the base case.

### `sensitivity_grid.csv`

One row per combination of `n_min` (30, 50, 100), `latency_p95_ms` (20, 30, 50), `jitter_p95_ms` (3, 4, 5) and `loss_pct` (0.05, 0.1, 0.5, 1.0): number of `analyzed` units, `at_risk` and `pct_at_risk`. The base case is `n_min` 50 / latency 20 / jitter 5 / loss 1.

### `data_quality_log.csv`

Columns `scope`, `rule`, `count`. Scopes `udplatency` and `udpjitter` record the rows read, the invalid or duplicated rows removed and the rows kept; scope `pipeline` records the unit totals (population, analyzed, insufficient, at risk, analyzed units with null jitter).

## Key findings (base case)

- **Population:** 258 units; 237 analyzed (Cincinnati Bell 108, Verizon 68, Frontier 61) and 21 set aside for insufficient peak records (Cincinnati Bell 12, Verizon 8, Frontier 1).
- **At risk: 5 of 237 (2.1 %)** - Cincinnati Bell 2 (1.9 %), Verizon 2 (2.9 %), Frontier 1 (1.6 %).
- **By metric:** latency flags 5, jitter flags 0, loss flags 1. Unit 24840041 (Frontier, CA) exceeds both latency (35.8 ms) and loss (1.66 %).
- **Persistent vs episodic:** 4 persistent and 1 episodic. The episodic unit, 4190285 (Verizon, MD), is also the only severe one (`risk_severe` = 1): its P95 is 50.0035 ms, an interpolated value just above the 50 ms threshold, and it falls to 14.77 ms once its worst day is removed.
- **Jitter:** no analyzed unit with a measurable value exceeds 5 ms (maximum 4.48 ms). 93 of 237 analyzed units (39 %) have no jitter value (Cincinnati Bell 69 of 108, Frontier 7 of 61, Verizon 17 of 68), so the jitter result covers 144 units.
- **Loss:** only one unit above 1 %; the next highest is 0.83 % (unit 1002196, Verizon).
- **Sensitivity:** the result depends mostly on the server rule: 5 units at risk with the primary server and 21 with all servers (local time); 4 and 17 under the UTC reading. `N_MIN` 30, 50 and 100 give 7, 5 and 1. Across the full threshold grid the count ranges from 1 to 30.

## Reconciliation and limits

- An independent Power Query rebuild of the metrics reproduces the 258 units with **0 mismatches** ([`docs/reconciliation.md`](../../docs/reconciliation.md)).
- One period (2022) and a non-random sample of volunteer units: the results describe these units and do not generalize to all FTTH subscribers.
- 220 of 258 units (85 %) are in the US Eastern time zone. The local-time reading of `dtime` rests on indirect evidence (D-03); the UTC reading is reported as a sensitivity.
- The risk thresholds are project-defined, not regulatory limits.

## Reproduce

```
python src/pipeline.py
```

Requires the RAW files described in the main README; the first run filters them to the FTTH units and caches the intermediates in `data/interim/` (gitignored). Use `--refresh-cache` to rebuild the cache.