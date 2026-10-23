# src/ - Code for the FTTH QoE Capstone

Code that implements the methodology defined in [`docs/metrics_spec.md`](../docs/metrics_spec.md) (v1.2.0). Values live in [`config.yaml`](../config.yaml); the pipeline never hardcodes a value that appears there. If code and spec disagree, the spec wins.

## Layout

```
src/
├── README.md        # this file
├── steps/           # numbered exploration scripts: step_0.py ... step_11.py and step_11_1.py
└── pipeline.py      # single implementation of the metrics (raw files -> data/processed/)
```

| Folder / file | Role | Status |
| :--- | :--- | :--- |
| `steps/` | Step-by-step inspection and decision scripts. Each one produced the evidence behind a decision (D-01 to D-10) or a Step 0 check. They print to the console. | Versioned, not part of the pipeline |
| `pipeline.py` | One implementation of each transformation: raw FCC files -> unit-level metrics. Implements D-01 to D-10 and reads `config.yaml`. | Done, covered by `tests/` |

## `pipeline.py`

- Reads `config.yaml` and the `config.local.yaml` override (gitignored; sets `inputs.raw_dir`, see `config.local.yaml.example`).
- Filters the raw files to the 258 FTTH units, cleans them (invalid records excluded and counted, duplicates per D-05) and caches the FTTH rows in `data/interim/pipeline_*_ftth.csv`.
- Computes the metrics per unit in the peak window (P95 latency, P95 jitter, loss as ratio of sums), applies `N_MIN`, the risk flags, `risk_severe` and the D-10 columns.
- Writes the five files of `data/processed/` (described in [`data/processed/README.md`](../data/processed/README.md)).
- Power BI consumes only `data/processed/`; it does not recalculate metrics.

```
python src/pipeline.py [--config config.yaml] [--refresh-cache] [--no-variants]
```

| Option | Effect |
| :--- | :--- |
| `--config` | Alternative configuration file (default `config.yaml`). |
| `--refresh-cache` | Re-reads the raw files and rebuilds the cache in `data/interim/`. |
| `--no-variants` | Skips the 2x2 variants matrix and the D-08 sensitivity grid. |

The first run reads the raw files (several minutes); later runs reuse the cache. Validate the output with `python -m pytest tests -v` (21 checks, run from the repository root after the pipeline).

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
| `step_9.py` | Base case of methodology v3 with one consistent set of rules, the 2x2 variants (time reading x server rule) and eight diagnostics (packets per row, loss and jitter distributions, jitter-only flags, jitter primary server, peak jitter records, jitter minimum, `N_MIN` sensitivity, repeated `rtt_avg` values) | D-04, D-06, D-07, D-08, D-09 |
| `step_10.py` | Jitter unit check (jitter vs `rtt_std` per unit) and the 50.00 ms P95 of unit 4190285 (values around the P95 position, days with high latency) | Jitter unit evidence, D-10 |
| `step_11.py` | Chronic vs isolated latency flags: concentration of records above the threshold by day, P95 without the worst day, and whether the event of unit 4190285 is shared by its server | D-10 |
| `step_11_1.py` | Explains the difference in `p95_latency_without_worst_day_ms` between `step_11.py` and `pipeline.py` for units 24733221 and 24840041 (tie-break on the date with the most records above the threshold) | D-10 |

Decisions and their evidence: [`docs/decisions.md`](../docs/decisions.md). Overview of the procedure: [`docs/procedure_summary_v3.md`](../docs/procedure_summary_v3.md).

### Reading the steps correctly

- **Steps 1 to 6 were written before D-03.** In them, "spec", `h_spec`, `h_local` and `h_dst` mean `dtime + timezone_offset_dst` (the UTC reading, now a sensitivity). The base case of D-03 is the variant `h_alt` / "dtime como local" (`hour(dtime)`).
- Steps 1 to 8 apply the three-metric rule (latency 20 ms, jitter 5 ms, loss 1 %) but do **not** apply `N_MIN`, so the flagged counts they print include units that the pipeline does not score. From `step_9.py` on, `N_MIN` is applied.
- Steps 1 to 6 compute the primary server separately for the latency file and for the jitter file. D-06 later fixed one server per unit (the latency primary server) for all metrics.
- `step_5.py` breaks ties between servers by input order; `step_6.py` and later break them alphabetically, as the spec states.
- Thresholds (`T_LAT`, `T_JIT`, `T_LOSS`) are hardcoded in the steps. The pipeline reads them from `config.yaml`.
- `pipeline.py` is the source of the results. The steps are the record of how each decision was reached.

### Running the steps

- Scripts use pandas only and read absolute Windows paths: `BASE` / `RAW` / `INTERIM` point to `D:\Capstone FTTH\...`. Edit them to run on another machine.
- `step_1.py` creates `data/interim/udplatency_ftth.csv`, `udpjitter_ftth.csv` and `udpcloss_ftth.csv` (gitignored); steps 2 to 6 and 9 to 11 read them. Steps 0, 7 and 8 read the raw files directly. `step_11_1.py` reads the cache that `pipeline.py` creates.
- `step_7.py` and `step_8.py` read `data/unit-profile-sept2022.csv`; the repository versions the `.xlsx` of the same profile. Export the sheet to CSV (UTF-8) before running them.
- Raw FCC files (6.8 GB) are not in the repository.

## Rules for the pipeline

- No capping and no `fillna(0)`: invalid records are excluded and counted.
- `dtime` is read as local time; no offset is added (D-03). The UTC reading is a sensitivity.
- One server per unit, the latency primary server, for latency, loss and jitter (D-04, D-06).
- Jitter is computed only with at least 50 peak jitter records, otherwise it stays empty, never 0 (D-07).
- Loss comes from `curr_udplatency` as `sum(failures) / sum(successes + failures) * 100`; `curr_udpcloss` is never used as a loss percentage.
- The risk rule is strictly greater than the threshold and does not change for episodic events (D-09, D-10).