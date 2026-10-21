# Power BI Implementation Log

Living document. It records what was built in Power BI, the reason behind each step, and how each step was verified. Updated after every working session.

- **Tool:** Power BI Desktop 2.157.1354.0 (64-bit)
- **Project file:** `powerbi/ftth_qoe.pbix`
- **Last updated:** 2026-10-21
- **Status:** Sessions 1-3 complete (load, model, base measures). Sessions 4A-4B complete (latency cleaning audit; peak window, primary server, P95 latency, loss, flags). Sessions 5-9 pending.
- **Images:** `docs/img/powerbi/` (`01_unit_metrics_load.png`, `02_unit_metrics_null_jitter.png`, `03_model_view_flat.png`, `04_hierarchy_matrix.png`, `05_measures_check.png`, `06_audit_data_quality_check.png`, `07_audit_core_totals.png`, `08_audit_core_control_units.png`; numbered in order of appearance, matching Figures 1-8)

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
| `aud_core` | Status (analyzed / insufficient) and flags per unit | Yes |

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

## 8. Modelling notes

- **Flat by design.** `unit_metrics` is the single fact table (237 analyzed units). ISP, state and Whitebox model are text columns in the same table.
- **Population denominator.** The 258-unit population is computed with a measure (analyzed + `units_insufficient`), not through a relationship.
- **Scenario tables are disconnected.** `variants_matrix` and `sensitivity_grid` hold pre-computed scenario results and are not filtered by slicers.
- **Null jitter (D-07).** 93 analyzed units have no jitter result. Aggregations ignore blanks; they are never replaced with 0.
- **Slicer limitation.** `units_insufficient` is reached only through `TREATAS` on `isp` and `state`. A slicer on any other `unit_metrics` column (Whitebox model, census, speed tiers) filters analyzed units but not insufficient ones, so `Insufficient Units` and `Population Units` ignore it. Population by ISP and state is exact; other cuts need a dimension table.
- **Trade-off.** A star schema would enable cross-filtering and reuse; out of scope here.

## 9. Roadmap

| Session | Content | PL-300 domain |
| :-: | :--- | :--- |
| 3 | Base DAX measures (analyzed, insufficient, at risk, % at risk) - **done** | Model the data |
| 4A | Audit phase 1a: latency cleaning, row counts - **done** | Prepare the data |
| 4B | Audit phase 1b: peak window, primary server, P95 latency, loss, flags - **done** | Prepare the data |
| 5 | Audit phase 2: jitter with minimum 50 records | Prepare the data |
| 6 | Audit phase 3: D-10 columns | Prepare the data |
| 7 | Per-`Unit ID` reconciliation -> `docs/reconciliation.md` | Analyze the data |
| 8 | Report pages and narrative | Visualize and analyze |
| 9 | Performance, documentation, publishing | Manage and secure |