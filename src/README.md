# src/ - Code for the FTTH QoE Capstone

Code that implements the methodology defined in [`docs/metrics_spec.md`](../docs/metrics_spec.md) (v1.2.0). Values live in [`config.yaml`](../config.yaml). If code and spec disagree, the spec wins.

## Layout

```
src/
├── README.md        # this file
├── pipeline.py      # single implementation of the metrics
└── steps/           # numbered exploration scripts, step_0.py ... step_11.py, step_11_1.py
tests/
└── test_unit_metrics.py   # automated checks on data/processed (outside src/)
```

| Folder / file | Role | Status |
| :--- | :--- | :--- |
| `pipeline.py` | One implementation of each transformation: raw FCC files -> unit-level metrics. Implements D-01 to D-10, reads `config.yaml` and the `config.local.yaml` override | Done |
| `steps/` | Step-by-step inspection and decision scripts. Each one produced the evidence behind a decision (D-01 to D-10) or a Step 0 check | Versioned |
| `../tests/test_unit_metrics.py` | 21 checks of spec section 9 on the pipeline output and the exclusion files | Done, all passing |

## `pipeline.py`

Runs the order of operations of spec section 5:

1. Population: reads `data/fiber_units.csv` and stops if the counts (258 units, ISPs, Whitebox models, time zone offsets) differ from `population.expected_counts`.
2. Raw files: filters `curr_udplatency.csv` and `curr_udpjitter.csv` to the 258 units, in chunks, and caches the result in `data/interim/pipeline_*_ftth.csv`.
3. Cleaning: analysis period (D-01), invalid records (excluded and counted, never capped or filled) and duplicates (D-05).
4. Peak window on local time (D-03) and one primary server per unit, taken from the latency file and used for latency, loss and jitter (D-04, D-06).
5. `N_MIN = 50` peak latency records after the server rule (D-02); units below it go to `units_insufficient_data.csv`.
6. Metrics: P95 latency, P95 jitter (null below 50 peak jitter records, D-07), loss as ratio of sums, and the D-10 columns. Flags use strictly greater thresholds.
7. Variants and sensitivity: the 2×2 matrix (local / UTC × primary / all servers) and the D-08 grid.

```
python src/pipeline.py [--config config.yaml] [--refresh-cache] [--no-variants]
```

- Needs `inputs.raw_dir` in `config.local.yaml` (gitignored). Paths in `config.yaml` are relative to the repository root.
- The first run reads the raw files (several minutes). Later runs use the cache; `--refresh-cache` reads the raw files again.
- Writes to `data/processed/`: `ftth_qoe_unit_metrics.csv`, `units_insufficient_data.csv`, `data_quality_log.csv`, `variants_matrix.csv` and `sensitivity_grid.csv`.
- Metric columns are written with 4 decimals; flags are computed before rounding.
- Ties: the primary server breaks ties alphabetically; the worst day of D-10 breaks ties by the earliest date.

### Tests

```
python -m pytest tests -v
```

Run from the repository root after the pipeline. The last test compares the output with the base case of `step_9.py` (237 analyzed / 21 insufficient / 5 at risk); if it fails, a change in data, configuration or code altered the base case, and the spec and `docs/decisions.md` must be updated first.

## `steps/` - Script map

Each script states its objective in the header comment. The recorded console output of a script is in the `OUTPUT` docstring at the end of the file.

| Script | What it does | Feeds |
| :--- | :--- | :--- |
| `step_0.py` | Coverage of the three raw files for the 258 FTTH units (rows, units, date range, rows per month), distinct targets, mean `rtt_avg` by hour under UTC, standard offset and DST offset | Dictionary checks 1, 4, 7, 8 |
| `step_1.py` | Filters the raw files to the 258 units and caches them in `data/interim/`; tests per hour (UTC vs offset); servers per unit; median RTT by state; peak-window records per unit (full period vs September only) | D-01, D-02 |
| `step_2.py` | Server mixing (RTT spread between servers of a unit, share of the primary server); count of invalid and duplicate records; global loss | D-04 (motivation), spec section 5.2 |
| `step_3.py` | Time-convention sensitivity with all servers pooled: A) `dtime + timezone_offset_dst`, B) `dtime` as local, C) all hours | D-03 |
| `step_4.py` | Duplicates by (`unit_id`, `dtime`, `target`): exact copies vs conflicting values | D-05 |
| `step_5.py` | All servers vs primary server, under the `dtime + timezone_offset_dst` reading; effect on `risk_flag` | D-04 |
| `step_6.py` | Same three variants as `step_3.py`, with the primary-server rule | D-03 |
| `step_7.py` | Eastern vs Pacific hourly RTT profile, all technologies pooled, shifts 0..+6 h | D-03 |
| `step_8.py` | Same test by technology, shifts -6..+6 h | D-03 |
| `step_9.py` | Base case and sensitivity matrix with one consistent set of rules: period filter, invalid counts, `N_MIN`, 2×2 matrix and eight diagnostics (packets per row, per-unit distributions, units flagged only by jitter, jitter with its own primary server, peak jitter records, jitter minimum, `N_MIN` sensitivity, most repeated `rtt_avg` values in severe units) | D-06, D-07, D-08, D-09 |
| `step_10.py` | A) jitter unit: per-unit median jitter against `rtt_std`; B) unit 4190285: position of its P95, top records and RTT by hour | D-07, D-10 |
| `step_11.py` | Records above 20 ms per flagged unit (days, worst-day share, P95 without the worst day) and the other units on the server of 4190285 on the event day | D-10 |
| `step_11_1.py` | Check of the ties in the worst day for units 24733221 and 24840041 | D-10 |

Decisions and their evidence: [`docs/decisions.md`](../docs/decisions.md). Overview of the procedure: [`docs/procedure_summary_v3.md`](../docs/procedure_summary_v3.md).

### Reading the steps correctly

- **Steps 1 to 6 were written before D-03.** In them, "spec", `h_spec`, `h_local` and `h_dst` mean `dtime + timezone_offset_dst` (the UTC reading, now a sensitivity). The base case of D-03 is the variant `h_alt` / "dtime as local". Their flagged counts (10 / 6 / 17 / 22) are not comparable with the current ones.
- Steps 1 to 8 apply the three-metric rule (latency 20 ms, jitter 5 ms, loss 1%) but do **not** apply `N_MIN`, so the flagged counts they print include units that the pipeline does not score. From `step_9.py` on, `N_MIN` is applied.
- In steps 1 to 8 the primary server is computed separately for the latency file and for the jitter file. From `step_9.py` on (D-06), the primary server of the latency file is used for the three metrics.
- `step_5.py` breaks ties between servers by input order; `step_6.py` breaks them alphabetically, as the spec states.
- `step_9.py` runs the base case without a jitter minimum (`jit_min=0`); the result is the same as with 50 records, and `pipeline.py` applies D-07 explicitly.
- `step_11.py` breaks ties in the worst day without a stated rule, so for units 24733221 and 24840041 it prints 23.98 and 35.81 ms. `pipeline.py` removes the earliest tied date (D-10) and gives 22.73 and 35.61 ms; `step_11_1.py` shows the tied days. No flag changes.
- Thresholds (`T_LAT`, `T_JIT`, `T_LOSS`) are hardcoded in the steps. The pipeline reads them from `config.yaml`.

### Running the steps

- Scripts use pandas only and read absolute Windows paths: `BASE` / `RAW` / `INTERIM` point to `D:\Capstone FTTH\...`. Edit them to run on another machine.
- `step_1.py` creates `data/interim/udplatency_ftth.csv`, `udpjitter_ftth.csv` and `udpcloss_ftth.csv` (gitignored); steps 2 to 6 and 9 to 11 read them. Steps 0, 7 and 8 read the raw files directly. `step_10.py` also caches `rtt_std` and `rtt_max` in `data/interim/udplatency_extra_ftth.csv`.
- `step_11_1.py` reads the cache of the pipeline (`data/interim/pipeline_udplatency_ftth.csv`), so run `pipeline.py` first.
- `step_7.py` and `step_8.py` read `data/unit-profile-sept2022.csv`; the repository versions the `.xlsx` of the same profile.
- Raw FCC files (6.8 GB) are not in the repository.

## Rules for the pipeline

- No capping and no `fillna(0)`: invalid records are excluded and counted.
- `dtime` is read as local time; no offset is added (D-03). The UTC reading is a sensitivity.
- Loss comes from `curr_udplatency` as `sum(failures) / sum(successes + failures) * 100`; `curr_udpcloss` is never used as a loss percentage.
- One server per unit for all three metrics (D-06). Jitter is null, never 0, below the minimum of peak jitter records (D-07).