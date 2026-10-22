# Power BI Implementation Log

Living document. It records what was built in Power BI, the reason behind each step, and how each step was verified. Updated after every working session.

- **Tool:** Power BI Desktop 2.157.1354.0 (64-bit)
- **Project file:** `powerbi/ftth_qoe.pbix`
- **Last updated:** 2026-10-21
- **Status:** Sessions 1-3 complete (load, model, base measures). Sessions 4A-6 complete (the full audit table is built: cleaning, peak window, primary server, P95 latency/jitter, loss, flags, severity and D-10 columns). Session 7 complete (per-unit reconciliation of the 237 analyzed units and the 21 insufficient units: 0 mismatches; result in `docs/reconciliation.md`). Sessions 8-9 pending.
- **Images:** `docs/img/powerbi/` (`01_unit_metrics_load.png`, `02_unit_metrics_null_jitter.png`, `03_model_view_flat.png`, `04_hierarchy_matrix.png`, `05_measures_check.png`, `06_audit_data_quality_check.png`, `07_audit_core_totals.png`, `08_audit_core_control_units.png`, `09_audit_jitter_dq_check.png`, `10_audit_jitter_conflicts.png`, `11_audit_units_totals.png`, `12_audit_units_jitter_controls.png`, `13_audit_unit_metrics_totals.png`, `14_audit_unit_metrics_d10_controls.png`, `15_reconciliation_totals.png`, `16_reconciliation_summary.png`, `17_reconciliation_insufficient.png`; numbered in order of appearance, matching Figures 1-17)

## 1. Role of Power BI in this project

The metrics are computed once, in `src/pipeline.py` (single implementation, covered by `tests/test_unit_metrics.py`). The report **consumes** `data/processed/` and does not recompute metrics. A separate set of Power Query audit queries will independently recompute them from the interim files and be reconciled per `Unit ID` (see `docs/metrics_spec.md`, section 8, and the future `docs/reconciliation.md`).

## 2. Design decisions

| Decision | Chosen | Alternatives | Rationale |
| :--- | :--- | :--- | :--- |
| Audit source | `data/interim/udplatency_ftth.csv`, `udpjitter_ftth.csv` (output of `step_1.py`) | `pipeline.py` cache; raw files (6.8 GB) | Produced by different code than `pipeline.py`, so agreement is independent evidence; small enough for Power Query. Does not audit the 258-unit filter (covered by the tests). |
| Project format | `.pbix` in `powerbi/` | `.pbip` | Simpler. Can be migrated later for better git diffs. |
| Data model | Flat table, no relationships | Star schema (`dim_unit` + facts) | Lower complexity. Star-schema practice is deferred to a separate scenario. Implications are documented in section 5. |

Expected audit discrepancies (all handled by explicit rules): `dtime` typed as `datetime` without offset (D-03); `List.Percentile` with `PercentileMode.ExcelInc`; 4-decimal rounding of the output files (tolerance 0.001); earliest-date tie-break for D-10; replication of D-05 duplicate handling (unit 943232 in jitter); alphabetical tie-break for the primary server (D-06). Target: zero classification differences and numeric differences <= 0.001.

## 3. Session 1 - Project setup and data load (Prepare the data)

| # | Step | Why |
| :-: | :--- | :--- |
| 1 | Parameter `RepoPath` = `D:\Capstone FTTH\` (Text, Required), created inside Power Query Editor | Single place for the base path (equivalent of `config.local.yaml`); no hard-coded paths in queries; reproducible on another machine. |
| 2 | Load each CSV with `Csv.Document(File.Contents(RepoPath & ...), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])` | UTF-8 (65001) avoids corrupted text. |
| 3 | `Table.PromoteHeaders(..., [PromoteAllScalars=true])` | Prevents a numeric first row from being mistaken for headers. |
| 4 | Column profiling set to *entire data set* | The default inspects only the first 1,000 rows and can hide errors. |
| 5 | Data types assigned per column | Auto-detection uses a sample. Decimal type for thresholds and percentiles to keep precision. |
| 6 | Null `p95_jitter_ms` left as null | D-07: null means "not measurable" (< 50 jitter records). Replacing it with 0 would claim perfect jitter. |
| 7 | Six queries with the same pattern | Each one is checkable against a known row count. |

Queries loaded: `unit_metrics`, `units_insufficient`, `variants_matrix`, `sensitivity_grid`, `data_quality_log`, `fiber_units`.

**Verification against the pipeline reference**

| Query | Expected | Observed |
| :--- | :-: | :-: |
| `unit_metrics` | 237 rows, 20 columns | OK |
| `unit_metrics.p95_jitter_ms` empty | 93 | 93 (39 %) |
| `unit_metrics.risk_flag = 1` | 5 | 5 |
| `units_insufficient` | 21 | OK |
| `variants_matrix` | 4 (237/21/5, 248/10/21, 239/19/4, 250/8/17) | OK |
| `sensitivity_grid` | 108 | OK |
| `data_quality_log` | 23 | OK |
| `fiber_units` | 258 | OK |

![unit_metrics loaded in Power Query: 237 rows, 20 columns, profiling on the entire data set](img/powerbi/01_unit_metrics_load.png)

*Figure 1. `unit_metrics` after load: 237 rows, 20 columns, no errors, column profiling based on the entire data set.*

![Data view of unit_metrics: p95_jitter_ms left empty where jitter is not measurable](img/powerbi/02_unit_metrics_null_jitter.png)

*Figure 2. Null `p95_jitter_ms` is preserved as blank (D-07). No default aggregation (Σ) on the metric columns.*

## 4. Session 2 - Model (Model the data)

| # | Step | Why |
| :-: | :--- | :--- |
| 1 | *Autodetect new relationships* disabled (Current File > Data Load) | `unit_metrics` and `units_insufficient` are disjoint sets of the same population; an automatic `unit_id` relationship would be wrong. |
| 2 | Close & Apply (Import mode) | Copies data into the in-memory engine used by DAX. |
| 3 | Model view checked: 0 relationships | Confirms the flat design. |
| 4 | *Don't summarize* on identifiers, flags, counts and all `p95_*`, `loss_pct`, `n_days_above_threshold` columns | Default SUM of a per-unit P95 is meaningless. Aggregations will be explicit measures. |
| 5 | `loss_pct` formatted as decimal, not as percentage | It is already in percentage points (0.04 = 0.04 %). The % format would multiply by 100. |
| 6 | Hierarchy `ISP -> State` in `unit_metrics` (right-click `isp` > Create hierarchy, then `state` > Add to hierarchy) | Drill-down without a dimension table. General level first (ISP), specific second (State). The first attempt produced a one-level hierarchy (only `state`), so drill up/down was disabled; the Matrix test (step 8) exposed it and the hierarchy was rebuilt with both levels. |
| 7 | Table descriptions added in Model view | Keeps the modelling notes inside the file. |
| 8 | Hierarchy test with a Matrix visual (`ISP -> State` in rows, count of `unit_id` in values, expanded one level) | Confirms the hierarchy drills ISP -> State and that the grand total equals the 237 analyzed units. |

![Model view: six tables, no relationships, ISP -> State hierarchy in unit_metrics](img/powerbi/03_model_view_flat.png)

*Figure 3. Flat model: six tables and zero relationships; `ISP -> State` hierarchy in `unit_metrics`.*

![Matrix visual with the ISP -> State hierarchy expanded; grand total 237](img/powerbi/04_hierarchy_matrix.png)

*Figure 4. Hierarchy check: ISP level expands into states; the grand total equals 237.*

**Hierarchy check results (analyzed units per ISP)**

| ISP | Population (`fiber_units`) | Insufficient | Analyzed (Matrix) | States |
| :--- | :-: | :-: | :-: | :--- |
| Cincinnati Bell | 120 | 12 | 108 | KY 13, OH 95 |
| Frontier | 62 | 1 | 61 | AL 1, CA 18, CT 2, FL 20, IN 2, TX 18 |
| Verizon | 76 | 8 | 68 | DE 1, MA 9, MD 11, NJ 6, NY 11, PA 12, RI 2, VA 16 |
| **Total** | **258** | **21** | **237** | 16 states |

Analyzed + insufficient = population for every ISP, and the grand total matches the 237 units of `unit_metrics`. Ohio holds 95 of the 237 analyzed units (40 %), a geographic concentration to mention in the findings.

## 5. Session 3 - Base measures (Model the data)

All KPIs are DAX **measures** stored in an empty container table, `_Measures` (created with *Enter data*, placeholder column hidden). The table has no relationships, so the model stays flat.

**Why measures and not calculated columns.** A calculated column is evaluated once per row at load time and stored; a measure is evaluated when a visual is drawn, in the current filter context, so it reacts to slicers, rows and drill-down. The per-unit metrics are already computed by `src/pipeline.py`; Power BI only aggregates them.

| # | Step | Why |
| :-: | :--- | :--- |
| 1 | Create `_Measures` (Home > Enter data > Create/Load) | One home for every KPI; keeps the field list organized. |
| 2 | Create the 11 measures below (Home > New measure) | Counts, rates and data-quality indicators used in all report pages. |
| 3 | Format: integers with thousands separator; `% Analyzed` and `% At Risk` as percentage with 1 decimal | `% At Risk` showed `0` until it was formatted as a percentage (5 / 237 = 0.0211). A format issue, not a calculation error. |
| 4 | Display folders (Model view > Properties > Display folder): `1 Population`, `2 Risk`, `3 Data Quality` | Readable field list. |
| 5 | `COALESCE(..., 0)` on count measures that can be empty | `COUNTROWS` returns BLANK when no row passes the filter. A KPI card should say 0, not blank. |

```dax
-- 1 Population
Analyzed Units = COUNTROWS ( unit_metrics )

Insufficient Units =
CALCULATE (
    COUNTROWS ( units_insufficient ),
    -- no relationships: pass the ISP and state filters to the other table by hand
    TREATAS ( VALUES ( unit_metrics[isp] ),   units_insufficient[isp] ),
    TREATAS ( VALUES ( unit_metrics[state] ), units_insufficient[state] )
)

Population Units = [Analyzed Units] + [Insufficient Units]
% Analyzed       = DIVIDE ( [Analyzed Units], [Population Units] )

-- 2 Risk
At Risk Units = COALESCE ( CALCULATE ( COUNTROWS ( unit_metrics ), unit_metrics[risk_flag] = 1 ), 0 )
Severe Units  = COALESCE ( CALCULATE ( COUNTROWS ( unit_metrics ), unit_metrics[risk_severe] = 1 ), 0 )
% At Risk     = DIVIDE ( [At Risk Units], [Analyzed Units] )
Latency Flags = COALESCE ( CALCULATE ( COUNTROWS ( unit_metrics ), unit_metrics[flag_latency] = 1 ), 0 )
Jitter Flags  = COALESCE ( CALCULATE ( COUNTROWS ( unit_metrics ), unit_metrics[flag_jitter] = 1 ), 0 )
Loss Flags    = COALESCE ( CALCULATE ( COUNTROWS ( unit_metrics ), unit_metrics[flag_loss] = 1 ), 0 )

-- 3 Data quality
Units Null Jitter = COUNTROWS ( unit_metrics ) - COUNT ( unit_metrics[p95_jitter_ms] )
```

- `COUNTROWS` counts rows (units); `COUNT` counts non-blank values, so `Units Null Jitter` = 237 - 144 = 93 without altering the nulls (D-07).
- `DIVIDE` returns blank instead of an error when the denominator is 0.
- The denominator of `% At Risk` is the analyzed units (5 / 237 = 2.1 %), as in the base case of the pipeline.

**Verification against the pipeline reference (no filters)**

| Measure | Expected | Observed |
| :--- | :-: | :-: |
| Analyzed / Insufficient / Population | 237 / 21 / 258 | 237 / 21 / 258 |
| % Analyzed | 91.9 % | 91.9 % |
| At Risk / Severe | 5 / 1 | 5 / 1 |
| % At Risk | 2.1 % | 2.1 % |
| Latency / Jitter / Loss Flags | 5 / 0 / 1 | 5 / 0 / 1 |
| Units Null Jitter | 93 | 93 |

`Insufficient Units` is the delicate measure, because it relies on `TREATAS`. It was checked at ISP and state level: the states with insufficient units are KY 1, OH 11, TX 1, MA 2, NJ 2, PA 1 and VA 3 (total 21), and analyzed + insufficient = population in every ISP and state (Cincinnati Bell 108 + 12 = 120, Frontier 61 + 1 = 62, Verizon 68 + 8 = 76).

![Measures check: totals table and Matrix by ISP and state](img/powerbi/05_measures_check.png)

*Figure 5. Measure totals (table) and `Analyzed`, `Insufficient` and `Population` units by ISP and state (matrix).*

Selecting a row in the Matrix cross-filters the other visuals (for example, selecting FL shows 20 analyzed units, 0 at risk, 1 unit with null jitter). Clear the selection before reading grand totals.

## 6. Session 4A - Audit of latency cleaning (Prepare the data)

**Goal.** Rebuild the latency cleaning of the pipeline (period, validity, duplicates D-05) in Power Query, independently of `src/pipeline.py`, and reconcile the row counts with the pipeline data-quality log.

**Source and its limits.** The audit reads `data/interim/udplatency_ftth.csv`, the output of `step_1.py`. That folder is gitignored, so the audit is reproducible only locally or after re-running `step_1.py`. Because the input is the pipeline's own interim file, this audit does not cover step 1 itself (the 258-unit filter is covered by the test suite). Minor discrepancies against the pipeline are expected and are reported per `Unit ID`, never hidden in totals.

**Query design.** Each stage is its own query referencing the previous one, so the row count of every stage can be read and audited. All staging queries have *Enable load* off; only `aud_dq` is loaded.

| Query | Logic | Loaded |
| :--- | :--- | :-: |
| `aud_lat_raw` | CSV read (UTF-8), headers promoted, explicit types with culture `en-US` | No |
| `aud_lat_period` | `dtime` in [2022-09-12, 2022-11-01) (D-01) | No |
| `aud_lat_valid` | `rtt_avg` not null and >= 0, `successes + failures` > 0 | No |
| `aud_lat_distinct` | `Table.Distinct` on all columns (exact duplicates, D-05) | No |
| `aud_lat_conflicts` | groups of (`unit_id`, `dtime`, `target`) with more than 1 row after exact dedup | No |
| `aud_lat_clean` | `aud_lat_distinct` minus conflicting keys (Left Anti join) | No |
| `aud_dq` | `Table.RowCount` of each stage | Yes |

**Why this order and these tools.**
- Exact duplicates are removed first on all columns. Conflicting duplicates (same key, different values) are then dropped entirely with an anti-join (D-05).
- Remove Duplicates on the three key columns alone would be wrong: it would keep one row of each conflicting group instead of dropping all of them.
- Exact counts come from `Table.RowCount`; the preview shows "999+" for large tables and column profiling defaults to the top 1000 rows (switch it to the entire data set when profiling).

**Verification.**

| Stage | Pipeline log | `aud_dq` |
| :--- | :-: | :-: |
| rows_read | 172,800 | 172,800 |
| rows_in_analysis_period | 172,800 | 172,800 |
| rows_valid | 172,800 | 172,800 |
| rows_after_exact_dedup | 172,791 | 172,791 |
| duplicate_conflicting_groups | 0 | 0 |
| rows_after_cleaning | 172,791 | 172,791 |

![Audit data-quality check: query list and aud_dq](img/powerbi/06_audit_data_quality_check.png)

*Figure 6. `aud_dq` row counts per stage (staging queries in italics are not loaded).*

**Result.** Power Query reproduces the pipeline cleaning for latency: 9 exact extra rows and 0 conflicting groups. Jitter (4 exact extras, 1 conflicting group, unit 943232) is audited in session 5.

## 7. Session 4B - Audit of peak window, primary server, P95 latency and loss (Prepare the data)

**Goal.** Rebuild the per-unit core metrics of the pipeline (peak window D-03, primary server D-04/D-06, minimum records D-02, P95 latency, loss, flags) in Power Query, starting from `aud_lat_clean`, and check totals and two control units. The per-unit reconciliation against `ftth_qoe_unit_metrics.csv` is done in session 7, once jitter and D-10 columns also exist.

### 7.1 Audit parameters

Created inside the Power Query Editor (*Home > Manage Parameters > New Parameter*), as for `RepoPath`. The parameter dialog has no *Whole Number* type, so `N_MIN` is a *Decimal Number*; comparing an integer column with it works the same in M. *Required* stays checked.

| Parameter | Type | Value | Description |
| :--- | :--- | :-: | :--- |
| `N_MIN` | Decimal Number | 50 | Minimum peak-window latency records required for a unit to be analyzed (D-02). Below it, the unit is "insufficient". Mirrors `n_min_peak_records` in `config.yaml`. |
| `THR_LATENCY_MS` | Decimal Number | 20 | P95 latency threshold in ms during the peak window. A unit is flagged when P95 is strictly greater. Mirrors the latency threshold in `config.yaml`. |
| `THR_LOSS_PCT` | Decimal Number | 1 | Packet loss threshold in percent on the primary server's peak records. A unit is flagged when loss is strictly greater. Mirrors the loss threshold in `config.yaml`. |

*Why parameters.* Thresholds live in one place and can change without editing queries, as in the pipeline. They duplicate `config.yaml`, so a change there must be repeated here.

### 7.2 Queries

Each query is created with *Home > New Source > Blank Query*, renamed in *Query Settings*, and its code pasted in the *Advanced Editor*. The order matters because each query references the previous one.

| Query | Purpose | Loaded |
| :--- | :--- | :-: |
| `aud_lat_peak` | Peak window 19:00-22:59 (D-03) | No |
| `aud_primary` | Primary server per unit (D-04, D-06) | No |
| `aud_lat_metrics` | Records, P95 latency and loss on the primary server | No |
| `aud_core` | Status (analyzed / insufficient) and flags per unit | Yes (until session 5B, see 8.2) |

**`aud_lat_peak`**
```m
let
    Source = aud_lat_clean,
    // dtime is already local time (D-03); window 19:00-22:59 => hour >= 19 and < 23
    Result = Table.SelectRows(Source, each Time.Hour([dtime]) >= 19 and Time.Hour([dtime]) < 23)
in
    Result
```

**`aud_primary`**
```m
let
    // peak records per unit and server
    Counts = Table.Group(aud_lat_peak, {"unit_id", "target"},
        {{"n", each Table.RowCount(_), Int64.Type}}),
    // per unit: most records first; tie => alphabetical target
    Result = Table.Group(Counts, {"unit_id"}, {{"primary_target",
        each Table.Sort(_, {{"n", Order.Descending}, {"target", Order.Ascending}}){0}[target],
        type text}})
in
    Result
```
The primary server is chosen once per unit using peak latency records (D-06). Sorting and taking the first row keeps the alphabetical tie-break; `Table.Distinct` would not guarantee it.

**`aud_lat_metrics`**
```m
let
    // keep only the records of each unit's primary server
    Joined = Table.NestedJoin(aud_lat_peak, {"unit_id", "target"},
        aud_primary, {"unit_id", "primary_target"}, "p", JoinKind.Inner),
    OnPrimary = Table.RemoveColumns(Joined, {"p"}),
    WithMs = Table.AddColumn(OnPrimary, "lat_ms", each [rtt_avg] / 1000, type number),  // us -> ms
    Result = Table.Group(WithMs, {"unit_id"}, {
        {"n_peak_records", each Table.RowCount(_), Int64.Type},
        // ExcelInc = PERCENTILE.INC = pandas linear interpolation; set explicitly
        {"p95_latency_ms", each List.Percentile([lat_ms], 0.95,
            [PercentileMode = PercentileMode.ExcelInc]), type number},
        // ratio of sums, not an average of per-row percentages
        {"loss_pct", each List.Sum([failures]) / (List.Sum([successes]) + List.Sum([failures])) * 100, type number}
    })
in
    Result
```
`PercentileMode.ExcelInc` is set on purpose: M's default percentile mode is not the interpolation used by pandas.

**`aud_core`**
```m
let
    Joined = Table.NestedJoin(aud_lat_metrics, {"unit_id"}, aud_primary, {"unit_id"}, "p", JoinKind.Inner),
    WithTarget = Table.ExpandTableColumn(Joined, "p", {"primary_target"}),
    WithStatus = Table.AddColumn(WithTarget, "status",
        each if [n_peak_records] >= N_MIN then "analyzed" else "insufficient", type text),
    // strictly greater than the threshold (spec)
    FlagLat = Table.AddColumn(WithStatus, "flag_latency",
        each if [p95_latency_ms] > THR_LATENCY_MS then 1 else 0, Int64.Type),
    Result = Table.AddColumn(FlagLat, "flag_loss",
        each if [loss_pct] > THR_LOSS_PCT then 1 else 0, Int64.Type)
in
    Result
```

### 7.3 Load and model hygiene

- *Enable load* is off for `aud_lat_peak`, `aud_primary` and `aud_lat_metrics`; only `aud_core` (258 rows) and `aud_dq` are loaded.
- In the Data view, `unit_id`, `n_peak_records`, `p95_latency_ms`, `loss_pct`, `flag_latency` and `flag_loss` of `aud_core` are set to *Summarization: Don't summarize*, so a P95 is never summed by accident.

### 7.4 Verification

Totals and control units were checked with the *DAX query view* (queries are saved in the `.pbix` and are not published). No measures were added to the model.

```dax
EVALUATE
ROW (
    "rows",          COUNTROWS ( aud_core ),
    "analyzed",      CALCULATE ( COUNTROWS ( aud_core ), aud_core[status] = "analyzed" ),
    "insufficient",  CALCULATE ( COUNTROWS ( aud_core ), aud_core[status] = "insufficient" ),
    "flag_latency",  CALCULATE ( SUM ( aud_core[flag_latency] ), aud_core[status] = "analyzed" ),
    "flag_loss",     CALCULATE ( SUM ( aud_core[flag_loss] ), aud_core[status] = "analyzed" )
)
```

| Control | Pipeline reference | `aud_core` |
| :--- | :-: | :-: |
| Units | 258 | 258 |
| Analyzed / insufficient | 237 / 21 | 237 / 21 |
| Latency flags (analyzed) | 5 | 5 |
| Loss flags (analyzed) | 1 | 1 |
| Unit 925942 | `sp1-vm-chicago-us.samknows.com`, 93 records, P95 14.93, loss 0.04 | same |
| Unit 943226 | `sp2-vm-chicago-us.samknows.com`, 53 records, P95 23.13, loss 0.00, latency flag | same |

![aud_core totals in DAX query view](img/powerbi/07_audit_core_totals.png)

*Figure 7. Totals of `aud_core`: 258 units, 237 analyzed, 21 insufficient, 5 latency flags, 1 loss flag.*

![aud_core control units in DAX query view](img/powerbi/08_audit_core_control_units.png)

*Figure 8. Control units 925942 and 943226.*

The threshold edge also behaves as specified: a unit with 49 peak records is `insufficient`, a unit with exactly 50 is `analyzed` (`>= N_MIN`).

**Result.** Power Query reproduces the pipeline totals and both control units. Per-unit differences, if any, are reported in session 7.

## 8. Session 5 - Audit of jitter (Prepare the data)

### 8.1 Session 5A - Jitter cleaning

**Goal.** Rebuild the jitter cleaning of the pipeline (period, validity, duplicates D-05) from `data/interim/udpjitter_ftth.csv`, with the same staging design as 4A, and reconcile the row counts with the pipeline data-quality log. The same limits apply: the file is the output of `step_1.py`, the folder is gitignored, and step 1 itself is not audited.

**Differences from latency.**
- Validity rule: `jitter_up` and `jitter_down` must both be non-null and >= 0 (the latency rules on `rtt_avg`, successes and failures do not apply).
- Unlike latency, jitter has one conflicting duplicate group (same key, different values), so `aud_jit_conflicts` is not empty.

| Query | Logic | Loaded |
| :--- | :--- | :-: |
| `aud_jit_raw` | CSV read (UTF-8), headers promoted, explicit types with culture `en-US` | No |
| `aud_jit_period` | `dtime` in [2022-09-12, 2022-11-01) (D-01) | No |
| `aud_jit_valid` | jitter up and down not null and >= 0 | No |
| `aud_jit_distinct` | `Table.Distinct` on all columns (exact duplicates, D-05) | No |
| `aud_jit_conflicts` | keys (`unit_id`, `dtime`, `target`) with more than 1 row after exact dedup | No |
| `aud_jit_clean` | `aud_jit_distinct` minus conflicting keys (Left Anti join) | No |
| `aud_dq_jit` | `Table.RowCount` of each stage | Yes |

`aud_dq_jit` is a separate query instead of an extension of `aud_dq`, so the verified latency audit is not modified.

**`aud_jit_raw`**
```m
let
    Source = Csv.Document(File.Contents(RepoPath & "data\interim\udpjitter_ftth.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Result = Table.TransformColumnTypes(Promoted, {
        {"unit_id", Int64.Type}, {"dtime", type datetime}, {"target", type text},
        {"jitter_up", type number}, {"jitter_down", type number}}, "en-US")
in
    Result
```

**`aud_jit_period`**
```m
let
    Source = aud_jit_raw,
    Result = Table.SelectRows(Source, each [dtime] >= #datetime(2022,9,12,0,0,0) and [dtime] < #datetime(2022,11,1,0,0,0))
in
    Result
```

**`aud_jit_valid`**
```m
let
    Source = aud_jit_period,
    // invalid: null or negative jitter in either direction
    Result = Table.SelectRows(Source, each [jitter_up] <> null and [jitter_down] <> null and [jitter_up] >= 0 and [jitter_down] >= 0)
in
    Result
```

**`aud_jit_distinct`**
```m
let
    Source = aud_jit_valid,
    // exact duplicates only: all columns must match (D-05)
    Result = Table.Distinct(Source)
in
    Result
```

**`aud_jit_conflicts`**
```m
let
    Source = aud_jit_distinct,
    Grouped = Table.Group(Source, {"unit_id", "dtime", "target"}, {{"n", each Table.RowCount(_), Int64.Type}}),
    Result = Table.SelectRows(Grouped, each [n] > 1)
in
    Result
```

**`aud_jit_clean`**
```m
let
    Keys = {"unit_id", "dtime", "target"},
    Joined = Table.NestedJoin(aud_jit_distinct, Keys, aud_jit_conflicts, Keys, "conf", JoinKind.LeftAnti),
    Result = Table.RemoveColumns(Joined, {"conf"})
in
    Result
```

**`aud_dq_jit`**
```m
let
    Rows = {
        {"rows_read", Table.RowCount(aud_jit_raw)},
        {"rows_in_analysis_period", Table.RowCount(aud_jit_period)},
        {"rows_valid", Table.RowCount(aud_jit_valid)},
        {"rows_after_exact_dedup", Table.RowCount(aud_jit_distinct)},
        {"duplicate_conflicting_groups", Table.RowCount(aud_jit_conflicts)},
        {"rows_after_cleaning", Table.RowCount(aud_jit_clean)}
    },
    Result = Table.FromRows(Rows, type table [stage = text, rows = Int64.Type])
in
    Result
```

**Verification.**

| Stage | Pipeline log | `aud_dq_jit` |
| :--- | :-: | :-: |
| rows_read / in period / valid | 152,730 | 152,730 |
| rows_after_exact_dedup | 152,726 | 152,726 |
| duplicate_conflicting_groups | 1 | 1 |
| rows_after_cleaning | 152,724 | 152,724 |

![Audit jitter data-quality check: aud_dq_jit](img/powerbi/09_audit_jitter_dq_check.png)

*Figure 9. `aud_dq_jit` row counts per stage (staging queries in italics are not loaded).*

![Audit jitter conflicts: aud_jit_conflicts](img/powerbi/10_audit_jitter_conflicts.png)

*Figure 10. The only conflicting group: unit 943232, server `sp1-vm-atlanta-us.samknows.com`, 2022-10-19 21:12:17, 2 rows.*

**Result.** Power Query reproduces the pipeline cleaning for jitter: 4 exact extra rows, 1 conflicting group and 2 rows dropped (152,726 - 2 = 152,724). The conflicting pair falls inside the peak window (hour 21), so Power BI and the pipeline drop it at the same point.

### 8.2 Session 5B - P95 jitter and minimum-records rule (D-06, D-07)

**Goal.** Compute the per-unit jitter metrics on the primary server of the latency file and apply the minimum of peak jitter records.

**Parameters** (created as in 7.1, type Decimal Number):

| Parameter | Value | Description |
| :--- | :-: | :--- |
| `N_JIT_MIN` | 50 | Minimum peak-window jitter records on the primary server required to report P95 jitter (D-07). Below it, jitter is null, never 0. Mirrors `metrics.jitter.min_peak_records` in `config.yaml`. |
| `THR_JITTER_MS` | 5 | P95 jitter threshold in ms during the peak window. A unit is flagged when P95 is strictly greater. Mirrors the jitter threshold in `config.yaml`. |

`N_JIT_MIN` is separate from `N_MIN` because the configuration keeps them as independent rules, although both are 50 today.

**`aud_jit_metrics`**
```m
let
    // jitter peak window (D-03), same hours as latency
    Peak = Table.SelectRows(aud_jit_clean, each Time.Hour([dtime]) >= 19 and Time.Hour([dtime]) < 23),
    // D-06: only the primary server chosen from the LATENCY file
    Joined = Table.NestedJoin(Peak, {"unit_id", "target"}, aud_primary, {"unit_id", "primary_target"}, "p", JoinKind.Inner),
    OnPrimary = Table.RemoveColumns(Joined, {"p"}),
    // jitter_up / jitter_down in us -> average -> ms
    WithMs = Table.AddColumn(OnPrimary, "jit_ms", each ([jitter_up] + [jitter_down]) / 2 / 1000, type number),
    Result = Table.Group(WithMs, {"unit_id"}, {
        {"n_peak_jitter_records", each Table.RowCount(_), Int64.Type},
        {"p95_jitter_raw", each List.Percentile([jit_ms], 0.95, [PercentileMode = PercentileMode.ExcelInc]), type number}
    })
in
    Result
```
The primary server comes from the latency file (D-06); the jitter file does not get its own. `p95_jitter_raw` does not apply the minimum yet; that rule is a visible step in `aud_units`.

**`aud_units`**
```m
let
    // left join: units without jitter records on the primary server must stay
    Joined = Table.NestedJoin(aud_core, {"unit_id"}, aud_jit_metrics, {"unit_id"}, "j", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(Joined, "j", {"n_peak_jitter_records", "p95_jitter_raw"}),
    // a count with no records is a real 0
    Counts = Table.ReplaceValue(Expanded, null, 0, Replacer.ReplaceValue, {"n_peak_jitter_records"}),
    // D-07: P95 only with enough records, otherwise null (never 0)
    P95 = Table.AddColumn(Counts, "p95_jitter_ms",
        each if [n_peak_jitter_records] >= N_JIT_MIN then [p95_jitter_raw] else null, type nullable number),
    // null never raises a flag; the guard is needed because null > 5 returns null in M
    Flag = Table.AddColumn(P95, "flag_jitter",
        each if [p95_jitter_ms] <> null and [p95_jitter_ms] > THR_JITTER_MS then 1 else 0, Int64.Type),
    Result = Table.RemoveColumns(Flag, {"p95_jitter_raw"})
in
    Result
```

**Load.** `aud_jit_metrics` and `aud_core` have *Enable load* off (`aud_units` contains `aud_core`). `aud_units` is loaded (258 rows) and its numeric columns are set to *Don't summarize*. Figures 7 and 8 were taken when `aud_core` was loaded; `aud_units` was the audit table until session 6, where `aud_unit_metrics` supersedes it and `aud_units` stops being loaded.

**Verification (DAX query view).**
```dax
EVALUATE
ROW (
    "rows",        COUNTROWS ( aud_units ),
    "null_jitter", CALCULATE ( COUNTROWS ( aud_units ), aud_units[status] = "analyzed", aud_units[p95_jitter_ms] = BLANK () ),
    "flag_jitter", CALCULATE ( SUM ( aud_units[flag_jitter] ), aud_units[status] = "analyzed" )
)
```

| Control | Pipeline reference | `aud_units` |
| :--- | :-: | :-: |
| Units | 258 | 258 |
| Analyzed units with null jitter | 93 | 93 |
| Jitter flags (analyzed) | 0 | 0 |
| Unit 925942 | 36 peak jitter records, null P95 | 36, null |
| Unit 925886 | 68 records, P95 0.3562 | 68, 0.36 |

![aud_units totals in DAX query view](img/powerbi/11_audit_units_totals.png)

*Figure 11. Totals of `aud_units`: 258 units, 93 analyzed units with null jitter, 0 jitter flags.*

![aud_units jitter control units in DAX query view](img/powerbi/12_audit_units_jitter_controls.png)

*Figure 12. Control units 925942 (below the minimum, null jitter) and 925886 (P95 0.36 ms).*

**Result.** Power Query reproduces the jitter rule of the pipeline: null below 50 peak jitter records, never 0, and no jitter flag in the base case (D-07, D-09). Per-unit differences, if any, are reported in session 7.

## 9. Session 6 - Risk flags, severity and D-10 columns (Prepare the data)

**Goal.** Complete the per-unit audit table with `risk_flag`, `risk_severe` and the two D-10 descriptive columns, so that it has the same columns as `ftth_qoe_unit_metrics.csv` and can be reconciled in session 7. D-10 does not change the risk rule: a latency flag stays a flag even when one episode causes it; the columns only let the report separate persistent from episodic flags.

### 9.1 Severe-threshold parameters

Decimal Number, created as in 7.1.

| Parameter | Value | Description |
| :--- | :-: | :--- |
| `THR_LATENCY_SEV_MS` | 50 | Severe P95 latency threshold in ms. A unit is severe when P95 is strictly greater. Mirrors `thresholds.severe.latency_p95_ms` in `config.yaml`. |
| `THR_JITTER_SEV_MS` | 15 | Severe P95 jitter threshold in ms. Null jitter never makes a unit severe. Mirrors `thresholds.severe.jitter_p95_ms` in `config.yaml`. |
| `THR_LOSS_SEV_PCT` | 10 | Severe packet loss threshold in percent. Mirrors `thresholds.severe.loss_pct` in `config.yaml`. |

### 9.2 Queries

| Query | Purpose | Loaded |
| :--- | :--- | :-: |
| `aud_lat_rows` | Peak records of each unit's primary server, with `lat_ms` and local `day` | No |
| `aud_d10` | D-10 columns per unit | No |
| `aud_unit_metrics` | Final audit table: `aud_units` + D-10 + `risk_flag` + `risk_severe` | Yes |

**`aud_lat_rows`**
```m
let
    Joined = Table.NestedJoin(aud_lat_peak, {"unit_id", "target"}, aud_primary, {"unit_id", "primary_target"}, "p", JoinKind.Inner),
    OnPrimary = Table.RemoveColumns(Joined, {"p"}),
    WithMs = Table.AddColumn(OnPrimary, "lat_ms", each [rtt_avg] / 1000, type number),
    // day = local date of the record (dtime is already local time, D-03)
    Result = Table.AddColumn(WithMs, "day", each Date.From([dtime]), type date)
in
    Result
```
D-10 needs the individual records per day, which `aud_lat_metrics` already aggregates. The logic of the primary-server join is repeated on purpose so the verified query is not modified.

**`aud_d10`**
```m
let
    P95 = (values as list) as nullable number =>
        if List.Count(values) = 0 then null
        else List.Percentile(values, 0.95, [PercentileMode = PercentileMode.ExcelInc]),
    // D-10: P95 after removing the date with most records above the threshold (ties: earliest date)
    WithoutWorstDay = (t as table) as nullable number =>
        let
            Above = Table.SelectRows(t, each [lat_ms] > THR_LATENCY_MS),
            PerDay = Table.Group(Above, {"day"}, {{"n", each Table.RowCount(_), Int64.Type}}),
            MaxN = List.Max(PerDay[n]),
            Worst = List.Min(Table.SelectRows(PerDay, each [n] = MaxN)[day]),
            Rest = Table.SelectRows(t, each [day] <> Worst)
        in
            // no record above the threshold => equals the plain P95
            if Table.RowCount(Above) = 0 then P95(t[lat_ms]) else P95(Rest[lat_ms]),
    Result = Table.Group(aud_lat_rows, {"unit_id"}, {
        {"n_days_above_threshold", each List.Count(List.Distinct(Table.SelectRows(_, each [lat_ms] > THR_LATENCY_MS)[day])), Int64.Type},
        {"p95_latency_without_worst_day_ms", each WithoutWorstDay(_), type nullable number}
    })
in
    Result
```
The tie-break "earliest date" is `List.Min` over the tied dates. The two helper functions keep the `Table.Group` readable and avoid repeating the percentile call.

**`aud_unit_metrics`**
```m
let
    Joined = Table.NestedJoin(aud_units, {"unit_id"}, aud_d10, {"unit_id"}, "d", JoinKind.LeftOuter),
    Expanded = Table.ExpandTableColumn(Joined, "d", {"n_days_above_threshold", "p95_latency_without_worst_day_ms"}),
    // risk_flag: any of the three base flags
    RiskFlag = Table.AddColumn(Expanded, "risk_flag",
        each if [flag_latency] + [flag_jitter] + [flag_loss] > 0 then 1 else 0, Int64.Type),
    // severe: strictly greater than the severe thresholds; null jitter never raises it
    Result = Table.AddColumn(RiskFlag, "risk_severe",
        each if [p95_latency_ms] > THR_LATENCY_SEV_MS
                or ([p95_jitter_ms] <> null and [p95_jitter_ms] > THR_JITTER_SEV_MS)
                or [loss_pct] > THR_LOSS_SEV_PCT then 1 else 0, Int64.Type)
in
    Result
```
The null guard on jitter is required because `null > 15` returns `null` in M, not `false`.

### 9.3 Load

*Enable load* is off for `aud_units`, `aud_lat_rows` and `aud_d10`. Only `aud_unit_metrics` (258 rows) is loaded, with its numeric columns set to *Don't summarize*.

### 9.4 Verification (DAX query view)

```dax
// Control totals of aud_unit_metrics
EVALUATE
ROW (
    "rows",       COUNTROWS ( aud_unit_metrics ),
    "at_risk",    CALCULATE ( COUNTROWS ( aud_unit_metrics ), aud_unit_metrics[status] = "analyzed", aud_unit_metrics[risk_flag] = 1 ),
    "severe",     CALCULATE ( COUNTROWS ( aud_unit_metrics ), aud_unit_metrics[status] = "analyzed", aud_unit_metrics[risk_severe] = 1 ),
    "persistent", CALCULATE ( COUNTROWS ( aud_unit_metrics ), aud_unit_metrics[status] = "analyzed", aud_unit_metrics[flag_latency] = 1, aud_unit_metrics[p95_latency_without_worst_day_ms] > 20 ),
    "episodic",   CALCULATE ( COUNTROWS ( aud_unit_metrics ), aud_unit_metrics[status] = "analyzed", aud_unit_metrics[flag_latency] = 1, aud_unit_metrics[p95_latency_without_worst_day_ms] <= 20 )
)
```

| Control | Pipeline reference | `aud_unit_metrics` |
| :--- | :-: | :-: |
| Units | 258 | 258 |
| At risk / severe (analyzed) | 5 / 1 | 5 / 1 |
| Persistent / episodic latency flags | 4 / 1 | 4 / 1 |

![aud_unit_metrics totals in DAX query view](img/powerbi/13_audit_unit_metrics_totals.png)

*Figure 13. Totals of `aud_unit_metrics`: 258 units, 5 at risk, 1 severe, 4 persistent and 1 episodic latency flags.*

Four control units were checked against the pipeline output:

| Unit | P95 latency | Days above threshold | P95 without worst day | Severe |
| :--- | :-: | :-: | :-: | :-: |
| 925942 | 14.93 | 0 | 14.93 (equals P95) | 0 |
| 24733221 | 23.96 | 7 | 22.73 | 0 |
| 4190285 | 50.00 | 1 | 14.77 | 1 |
| 24840041 | 35.80 | 16 | 35.61 | 0 |

![aud_unit_metrics D-10 control units in DAX query view](img/powerbi/14_audit_unit_metrics_d10_controls.png)

*Figure 14. D-10 control units.*

**Result.** Unit 4190285 is the episodic case: its P95 (50.0035 ms) is just above the severe threshold, and removing one day brings it to 14.77 ms. The other four flagged units stay above 20 ms without their worst day. Per-unit differences, if any, are reported in session 7.

## 10. Session 7 - Per-unit reconciliation (Analyze the data)

Session 7A reconciles the 237 analyzed units (sections 10.1 to 10.4); session 7B reconciles the 21 insufficient units (section 10.5). The result of both is summarized in `docs/reconciliation.md`.

### Session 7A - Analyzed units

**Goal.** Compare, unit by unit, the audit table built in Power Query (`aud_unit_metrics`) with the pipeline output (`unit_metrics`, loaded in session 1 from `data/processed/ftth_qoe_unit_metrics.csv`), as required by `docs/metrics_spec.md`, section 8. Reconciliation is never done by totals only: every unit is compared, and a difference would be analyzed one unit at a time (window, time convention, server rule, nulls).

### 10.1 Design

- **Reference table.** `unit_metrics` is already in the model; nothing new is loaded. It contains only the 237 analyzed units, so the audit side is filtered to `status = "analyzed"`.
- **Full outer join by `unit_id`.** Units present on one side only must appear in the result instead of disappearing, so the presence flags `in_audit` and `in_pipeline` are part of the output.
- **Tolerances** (spec section 8): +/- 0.001 for the three P95 columns (ms) and for `loss_pct` (percentage points); exact match for `n_peak_records`, `n_peak_jitter_records`, `n_days_above_threshold` and `risk_flag`. The audit also checks, with exact match, `primary_target`, `flag_latency`, `flag_jitter`, `flag_loss` and `risk_severe`, which is stricter than the specification.
- **Null jitter** matches only null jitter on the other side (same units with null jitter).
- **Tolerances in one table.** `rec_spec` holds the metric list and tolerances; `rec_units` and `rec_summary` read it, so nothing is repeated.

| Query | Purpose | Loaded |
| :--- | :--- | :-: |
| `rec_spec` | Metrics to reconcile and tolerance of each | No |
| `rec_units` | One row per unit: values from both sides, `ok_<metric>`, `diff_<metric>`, `n_mismatch` | Yes |
| `rec_summary` | One row per metric: units compared, mismatches, maximum absolute difference | Yes |

### 10.2 Queries

**`rec_spec`**
```m
// rec_spec: metrics to reconcile between the audit (aud_unit_metrics) and the pipeline output (unit_metrics)
// and the tolerance for each one (docs/metrics_spec.md, section 8). Single source of truth:
// rec_units and rec_summary both read this table, so tolerances are never repeated.
// tolerance 0 = exact match; > 0 = maximum absolute difference allowed.
let
    // columns: metric name, tolerance, origin of the rule
    Rows = {
        {"primary_target", 0, "exact (stricter than spec)"},
        {"n_peak_records", 0, "exact (spec section 8)"},
        {"n_peak_jitter_records", 0, "exact (spec section 8)"},
        {"p95_latency_ms", 0.001, "+/- 0.001 ms (spec section 8)"},
        {"p95_jitter_ms", 0.001, "+/- 0.001 ms (spec section 8)"},
        {"loss_pct", 0.001, "+/- 0.001 pp (spec section 8)"},
        {"n_days_above_threshold", 0, "exact (spec section 8)"},
        {"p95_latency_without_worst_day_ms", 0.001, "+/- 0.001 ms (spec section 8)"},
        {"flag_latency", 0, "exact (stricter than spec)"},
        {"flag_jitter", 0, "exact (stricter than spec)"},
        {"flag_loss", 0, "exact (stricter than spec)"},
        {"risk_flag", 0, "exact (spec section 8)"},
        {"risk_severe", 0, "exact (stricter than spec)"}
    },
    // explicit column types so downstream queries can rely on them
    Result = Table.FromRows(Rows, type table [metric = text, tolerance = number, rule = text])
in
    Result
```

**`rec_units`**
```m
// rec_units: per-unit reconciliation between the Power Query audit (aud_unit_metrics)
// and the pipeline output (unit_metrics = data/processed/ftth_qoe_unit_metrics.csv).
// One row per unit_id found on either side. For each metric in rec_spec it adds:
//   aud_<m> / pip_<m>  values from each side
//   ok_<m>             true when they match within the tolerance (null equals null only)
//   diff_<m>           absolute difference (null for text columns or when one side is null)
// n_mismatch counts the metrics that do not match. Differences are never fixed here:
// each one is analyzed by Unit ID (docs/metrics_spec.md, section 8, point 3).
let
    // metric list with tolerances; Table.ToRows gives one list per metric: {name, tolerance, rule}
    Spec = Table.ToRows(rec_spec),
    Cols = List.Transform(Spec, each _{0}),
    // audit side: analyzed units only, because the pipeline file contains only analyzed units.
    // Buffered so the join does not enumerate the audit chain more than once.
    AuditRows = Table.Buffer(Table.SelectRows(aud_unit_metrics, each [status] = "analyzed")),
    // prefix every column with its origin so both sides can live in the same row
    A = Table.RenameColumns(Table.SelectColumns(AuditRows, {"unit_id"} & Cols),
            List.Transform({"unit_id"} & Cols, each {_, "aud_" & _})),
    // unit_id is text in unit_metrics and integer in the audit; the join matches nothing unless both sides have the same type
    P0 = Table.TransformColumnTypes(Table.SelectColumns(unit_metrics, {"unit_id"} & Cols), {{"unit_id", Int64.Type}}, "en-US"),
    P = Table.RenameColumns(P0, List.Transform({"unit_id"} & Cols, each {_, "pip_" & _})),
    // full outer join: units present on one side only must show up instead of disappearing
    Joined0 = Table.NestedJoin(A, {"aud_unit_id"}, P, {"pip_unit_id"}, "p", JoinKind.FullOuter),
    Joined = Table.ExpandTableColumn(Joined0, "p", List.Transform({"unit_id"} & Cols, each "pip_" & _)),
    // single unit_id taken from whichever side has it
    WithId = Table.AddColumn(Joined, "unit_id",
        each if [aud_unit_id] <> null then [aud_unit_id] else [pip_unit_id], Int64.Type),
    // presence flags: show units that exist on one side only
    InAudit = Table.AddColumn(WithId, "in_audit", each [aud_unit_id] <> null, type logical),
    InPipeline = Table.AddColumn(InAudit, "in_pipeline", each [pip_unit_id] <> null, type logical),
    // match test: tolerance for numbers, plain equality for the rest.
    // If either side is null the result is a = b, so null matches only null (null jitter in the same units).
    Same = (a, b, tol) =>
        if a = null or b = null then a = b
        else if a is number and b is number then Number.Abs(a - b) <= tol
        else a = b,
    // absolute difference; try ... otherwise null covers text columns and nulls
    Diff = (a, b) => try Number.Abs(a - b) otherwise null,
    // List.Accumulate repeats the same step once per metric (adds the ok_ columns)
    Ok = List.Accumulate(Spec, InPipeline, (state, m) =>
        Table.AddColumn(state, "ok_" & m{0},
            each Same(Record.Field(_, "aud_" & m{0}), Record.Field(_, "pip_" & m{0}), m{1}), type logical)),
    // same pattern for the diff_ columns
    Diffs = List.Accumulate(Spec, Ok, (state, m) =>
        Table.AddColumn(state, "diff_" & m{0},
            each Diff(Record.Field(_, "aud_" & m{0}), Record.Field(_, "pip_" & m{0})), type nullable number)),
    // number of metrics that do not match in each unit (0 = unit fully reconciled)
    Result = Table.AddColumn(Diffs, "n_mismatch",
        each List.Count(List.Select(List.Transform(Cols, (c) => Record.Field(_, "ok_" & c)), each _ = false)), Int64.Type)
in
    Result
```

**`rec_summary`**
```m
// rec_summary: one row per reconciled metric.
//   units_compared  units present on both sides
//   mismatches      units outside the tolerance
//   max_abs_diff    largest absolute difference (null for text columns)
// It summarizes rec_units; reconciliation itself is judged unit by unit, never by these totals alone.
let
    // only units present on both sides are comparable; one-sided units are reported separately.
    // Table.Buffer evaluates rec_units once; without it every reference below re-reads the whole audit chain from the CSV.
    Both = Table.Buffer(Table.SelectRows(rec_units, each [in_audit] and [in_pipeline])),
    // one result row per metric listed in rec_spec
    Rows = List.Transform(Table.ToRows(rec_spec), (m) => {
        m{0},                                                                          // metric
        m{1},                                                                          // tolerance
        Table.RowCount(Both),                                                          // units compared
        Table.RowCount(Table.SelectRows(Both, each Record.Field(_, "ok_" & m{0}) = false)),  // mismatches
        List.Max(Table.Column(Both, "diff_" & m{0}))}),                                // max abs difference
    Result = Table.FromRows(Rows, type table [metric = text, tolerance = number,
        units_compared = Int64.Type, mismatches = Int64.Type, max_abs_diff = nullable number])
in
    Result
```

*Enable load* is off for `rec_spec`; `rec_units` and `rec_summary` are loaded.

### 10.3 Problems found and how they were resolved

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `rec_units` had 474 rows: 237 only in the audit, 237 only in the pipeline, 474 with mismatches | `unit_id` is text in `unit_metrics` (column icon ABC; statistics showed Min 1000023 > Max 998971, text order) and integer in the audit. In M, text "925942" does not equal number 925942, so the join matched nothing | `unit_id` of `unit_metrics` is converted to `Int64` inside `rec_units`. `unit_metrics` itself is not changed: text is reasonable for an identifier and the session 1 query was already verified |
| Loading `rec_summary` read 3.98 GB from `udplatency_ftth.csv` and could not be cancelled quickly | Power Query tables are lazy: each of the ~40 references to `rec_units` re-evaluated the whole audit chain down to the CSV | `Table.Buffer` on `Both` (`rec_summary`) and on `AuditRows` (`rec_units`); loaded in two steps (first `rec_units`, then `rec_summary`) |
| Blank cells instead of 0 in the DAX totals | `CALCULATE ( COUNTROWS (...) )` returns blank, not 0, when no row matches | `COALESCE ( ..., 0 )` in the verification query |
| `rec_summary` showed `0` for every tolerance and difference | The query view rounds to 2 decimals (the tolerance 0.001 was shown as 0) | `FORMAT ( ..., "0.000000" )` in the verification query |

The full outer join and the presence flags made the first problem obvious in the first run. With an inner join the table would have been empty with no explanation.

### 10.4 Verification (DAX query view)

```dax
// Reconciliation totals (blank shown as 0)
EVALUATE
ROW (
    "units",               COUNTROWS ( rec_units ),
    "only_in_audit",       COALESCE ( CALCULATE ( COUNTROWS ( rec_units ), rec_units[in_pipeline] = FALSE () ), 0 ),
    "only_in_pipeline",    COALESCE ( CALCULATE ( COUNTROWS ( rec_units ), rec_units[in_audit] = FALSE () ), 0 ),
    "units_with_mismatch", COALESCE ( CALCULATE ( COUNTROWS ( rec_units ), rec_units[n_mismatch] > 0 ), 0 )
)
```

![Reconciliation totals in DAX query view](img/powerbi/15_reconciliation_totals.png)

*Figure 15. 237 units compared, none present on one side only, none with a mismatch.*

```dax
// rec_summary with 6 decimals (the grid rounds to 2)
EVALUATE
SELECTCOLUMNS (
    rec_summary,
    "metric",         rec_summary[metric],
    "tolerance",      FORMAT ( rec_summary[tolerance], "0.000000" ),
    "units_compared", rec_summary[units_compared],
    "mismatches",     rec_summary[mismatches],
    "max_abs_diff",   FORMAT ( rec_summary[max_abs_diff], "0.000000" )
)
```

![Reconciliation summary by metric in DAX query view](img/powerbi/16_reconciliation_summary.png)

*Figure 16. 13 metrics x 237 units, 0 mismatches; largest difference 0.000050 in P95 latency, P95 jitter, loss and P95 without the worst day.*

| Metric group | Tolerance | Mismatches | Maximum absolute difference |
| :--- | :-: | :-: | :-: |
| `n_peak_records`, `n_peak_jitter_records`, `n_days_above_threshold` | exact | 0 | 0 |
| `flag_latency`, `flag_jitter`, `flag_loss`, `risk_flag`, `risk_severe` | exact | 0 | 0 |
| `primary_target` | exact | 0 | not applicable (text) |
| `p95_latency_ms`, `p95_jitter_ms`, `p95_latency_without_worst_day_ms` | 0.001 ms | 0 | 0.000050 |
| `loss_pct` | 0.001 pp | 0 | 0.000050 |

**Reading of the result.** The pipeline file stores four decimals and the audit computes without rounding, so a maximum difference of 0.000050 (half a unit of the fourth decimal) is the footprint of that rounding. It also shows that the comparison really ran: a maximum of exactly 0 in every numeric metric would have been suspicious. All differences are 20 times smaller than the tolerance. Null jitter coincides in the same 93 units, since `p95_jitter_ms` has 237 units compared and 0 mismatches.

### 10.5 Session 7B - Insufficient units

**Goal.** The 21 units below `N_MIN` are not in `unit_metrics`, so they are reconciled separately against `units_insufficient` (loaded in session 1 from `data/processed/units_insufficient_data.csv`). With 7A this covers the whole population: 237 + 21 = 258.

**Design.** Same pattern as `rec_units`: full outer join by `unit_id` (converted to `Int64` on the pipeline side, as in 10.3), presence flags and an exact comparison of the three columns the pipeline reports for these units: `primary_target`, `n_peak_records` and `n_peak_jitter_records`. No P95, loss or flags exist for them because they are not scored.

**`rec_insufficient`**
```m
// rec_insufficient: per-unit reconciliation of the units below N_MIN.
// Audit side: aud_unit_metrics with status "insufficient".
// Pipeline side: units_insufficient (data/processed/units_insufficient_data.csv).
// Same design as rec_units: full outer join by unit_id, presence flags, exact comparison per metric.
let
    Metrics = {"primary_target", "n_peak_records", "n_peak_jitter_records"},
    // buffered so the join does not enumerate the audit chain more than once
    AuditRows = Table.Buffer(Table.SelectRows(aud_unit_metrics, each [status] = "insufficient")),
    A = Table.RenameColumns(Table.SelectColumns(AuditRows, {"unit_id"} & Metrics),
            List.Transform({"unit_id"} & Metrics, each {_, "aud_" & _})),
    // unit_id must have the same type on both sides (text vs integer would match nothing)
    P0 = Table.TransformColumnTypes(Table.SelectColumns(units_insufficient, {"unit_id"} & Metrics), {{"unit_id", Int64.Type}}, "en-US"),
    P = Table.RenameColumns(P0, List.Transform({"unit_id"} & Metrics, each {_, "pip_" & _})),
    // full outer join: a unit present on one side only must show up
    Joined0 = Table.NestedJoin(A, {"aud_unit_id"}, P, {"pip_unit_id"}, "p", JoinKind.FullOuter),
    Joined = Table.ExpandTableColumn(Joined0, "p", List.Transform({"unit_id"} & Metrics, each "pip_" & _)),
    WithId = Table.AddColumn(Joined, "unit_id",
        each if [aud_unit_id] <> null then [aud_unit_id] else [pip_unit_id], Int64.Type),
    InAudit = Table.AddColumn(WithId, "in_audit", each [aud_unit_id] <> null, type logical),
    InPipeline = Table.AddColumn(InAudit, "in_pipeline", each [pip_unit_id] <> null, type logical),
    // all three metrics are exact (text or counts); null equals null only
    Ok = List.Accumulate(Metrics, InPipeline, (state, m) =>
        Table.AddColumn(state, "ok_" & m,
            each Record.Field(_, "aud_" & m) = Record.Field(_, "pip_" & m), type logical)),
    // metrics that do not match in each unit (0 = unit fully reconciled)
    Result = Table.AddColumn(Ok, "n_mismatch",
        each List.Count(List.Select(List.Transform(Metrics, (c) => Record.Field(_, "ok_" & c)), each _ = false)), Int64.Type)
in
    Result
```
`rec_insufficient` is loaded.

**Verification.**
```dax
// Reconciliation of insufficient units (blank shown as 0)
EVALUATE
ROW (
    "units",               COUNTROWS ( rec_insufficient ),
    "only_in_audit",       COALESCE ( CALCULATE ( COUNTROWS ( rec_insufficient ), rec_insufficient[in_pipeline] = FALSE () ), 0 ),
    "only_in_pipeline",    COALESCE ( CALCULATE ( COUNTROWS ( rec_insufficient ), rec_insufficient[in_audit] = FALSE () ), 0 ),
    "units_with_mismatch", COALESCE ( CALCULATE ( COUNTROWS ( rec_insufficient ), rec_insufficient[n_mismatch] > 0 ), 0 )
)
```

![Reconciliation of the insufficient units in DAX query view](img/powerbi/17_reconciliation_insufficient.png)

*Figure 17. 21 insufficient units compared, none present on one side only, none with a mismatch.*

**Result.** The 21 insufficient units match in primary server, peak latency records and peak jitter records. Together with 7A, every one of the 258 units is reconciled. The result and its limits are documented in `docs/reconciliation.md`.

## 11. Modelling notes

- **Flat by design.** `unit_metrics` is the single fact table (237 analyzed units). ISP, state and Whitebox model are text columns in the same table.
- **Population denominator.** The 258-unit population is computed with a measure (analyzed + `units_insufficient`), not through a relationship.
- **Scenario tables are disconnected.** `variants_matrix` and `sensitivity_grid` hold pre-computed scenario results and are not filtered by slicers.
- **Null jitter (D-07).** 93 analyzed units have no jitter result. Aggregations ignore blanks; they are never replaced with 0.
- **Slicer limitation.** `units_insufficient` is reached only through `TREATAS` on `isp` and `state`. A slicer on any other `unit_metrics` column (Whitebox model, census, speed tiers) filters analyzed units but not insufficient ones, so `Insufficient Units` and `Population Units` ignore it. Population by ISP and state is exact; other cuts need a dimension table.
- **Trade-off.** A star schema would enable cross-filtering and reuse; out of scope here.

## 12. Roadmap

| Session | Content | PL-300 domain |
| :-: | :--- | :--- |
| 3 | Base DAX measures (analyzed, insufficient, at risk, % at risk) - **done** | Model the data |
| 4A | Audit phase 1a: latency cleaning, row counts - **done** | Prepare the data |
| 4B | Audit phase 1b: peak window, primary server, P95 latency, loss, flags - **done** | Prepare the data |
| 5 | Audit phase 2: jitter cleaning (5A), P95 jitter with minimum 50 records (5B) - **done** | Prepare the data |
| 6 | Audit phase 3: `risk_flag`, `risk_severe` and D-10 columns - **done** | Prepare the data |
| 7A | Per-`Unit ID` reconciliation of the 237 analyzed units - **done** | Analyze the data |
| 7B | Reconciliation of the 21 insufficient units; result in `docs/reconciliation.md` - **done** | Analyze the data |
| 8 | Report pages and narrative | Visualize and analyze |
| 9 | Performance, documentation, publishing | Manage and secure |