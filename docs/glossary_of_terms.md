# Glossary of Terms — FTTH QoE Risk Analysis

Reference for the standards, measurement concepts, network metrics, business concepts and data-engineering terms and Power BI terms used in this project. Terms marked **(project)** have a specific meaning in this repository.

## 1. Standards & Regulatory Bodies

### International
- **ITU-T (International Telecommunication Union – Telecommunication Standardization Sector):** the ITU division that coordinates global telecommunication standards (e.g., the GPON recommendation G.984).
- **IEEE (Institute of Electrical and Electronics Engineers):** professional association that develops networking standards (e.g., Ethernet, IEEE 802.3).
- **ETSI (European Telecommunications Standards Institute):** independent non-profit organization that produces standards for information and communications technologies.

### United States
- **FCC (Federal Communications Commission):** the U.S. federal agency that regulates interstate and international communications by radio, television, wire, satellite and cable.
- **MBA (Measuring Broadband America):** FCC program that collects and publishes performance data on fixed broadband services in the United States. Source of the data in this project.

### Mexico
- **CRT (Comisión Reguladora de Telecomunicaciones):** federal telecommunications regulator in Mexico. It replaced the IFT (Instituto Federal de Telecomunicaciones) under the new telecom framework, alongside the ATDT.
- **ATDT (Agencia de Transformación Digital y Telecomunicaciones):** federal agency created in the same restructuring that replaced the IFT.
- **PROFECO (Procuraduría Federal del Consumidor):** federal consumer protection agency; handles complaints about telecom services.
- **NOM (Norma Oficial Mexicana):** mandatory technical standards in Mexico for safety, performance and equipment compliance.
- **NYCE (Normalización y Certificación):** accredited organization that certifies equipment against Mexican standards.

## 2. Measurement & Data Source

- **SamKnows:** company whose measurement platform (Whitebox devices and software) is used by the FCC MBA program; the MBA documentation refers to SamKnows Whitebox hardware generations.
- **Whitebox:** the measurement device installed at a volunteer home and connected to the home network. Its model (e.g., `skwb8`, `ac1750v2`) is listed in the unit profile. **(project)** The Whitebox is the measurement *instrument*, so a model that cannot forward traffic at line rate distorts the results.
- **Unit (`unit_id`):** one deployed Whitebox, which identifies one participating household.
- **Panelist:** volunteer participant whose connection is measured (FCC terminology).
- **Unit profile:** FCC file with the details of each unit (ISP, technology, state, tier, Whitebox model, time-zone offsets).
- **ISP (Internet Service Provider):** the company that sells the broadband service (here Cincinnati Bell, Frontier and Verizon). **(project)** The `isp` column of the unit profile; results are reported by ISP, but the units are a non-random sample, so the comparison is descriptive.
- **Census region (`census`):** US Census Bureau grouping of states used in the unit profile: Midwest, South, Northeast and West. **(project)** Descriptive column of `ftth_qoe_unit_metrics.csv`; it is not used in the risk rule.
- **RAW data:** the original FCC MBA files exactly as downloaded (`data/raw/`, 6.8 GB). **(project)** They are never edited and are not in the repository; `data/interim/` and `data/processed/` are derived from them.
- **Population / units in scope (project):** the 258 FTTH units that pass the hardware filter. They split into *analyzed* units (237, with at least `N_MIN` peak records) and *insufficient* units (21).
- **Active measurement:** a test that generates its own traffic to measure the network (as opposed to passive monitoring of user traffic). All MBA tests used here are active.
- **Target:** the server or host a test is run against (`target` column).
- **On-net / Off-net node:** a test server inside the ISP's own network (on-net) or outside it (off-net). The MBA documentation states that one of each is tested hourly. **(project)** Whether to analyze them separately is a pending decision in the metrics specification.
- **Peak hours:** evening period with the highest network demand. **(project)** Defined here as local time 19:00–22:59; FCC reports describe an evening peak period, to be confirmed in the Technical Appendix.
- **UTC (Coordinated Universal Time):** the reference time standard. FCC `dtime` values are documented as UTC (with a documented exception for `curr_udpcloss`).
- **DST (Daylight Saving Time):** seasonal clock shift of one hour. It changes the UTC offset used to convert `dtime` into local time (`timezone_offset` vs `timezone_offset_dst`).
- **Epoch time (Unix time):** number of seconds elapsed since 1970-01-01 00:00:00 UTC, a compact way to store a timestamp as a single number. **(project)** Not used by the FCC files analyzed here: `dtime` is a text string in the format `%Y-%m-%d %H:%M:%S` with no time zone marker (data dictionary, check 1), so it is parsed as a date-time and interpreted as local time (decision D-03), not converted from epoch.
- **Time zone offset (`timezone_offset`, `timezone_offset_dst`):** number of hours between a unit's local time and UTC, in the unit profile: `timezone_offset` is the standard-time offset and `timezone_offset_dst` the offset during daylight saving time. **(project)** All 258 units observe DST (values -4, -5 and -7 in `timezone_offset_dst`). The offsets are verified against `State` but are not used to build the peak window, because `dtime` is read as local time (decision D-03); `timezone_offset_dst` is used only in the UTC-reading sensitivity.
- **Time zone (TZ):** region with a common clock time. **(project)** 220 of the 258 units (85 %) are in the US Eastern time zone (EST in standard time, EDT in daylight saving time, UTC-5 and UTC-4); the rest are Central (20 units) or Pacific (18 units). `dtime` carries no time zone marker.
- **Time reading (project):** how `dtime` is interpreted: *local* (base case, D-03) or *UTC* (`dtime` plus the DST offset, reported as a sensitivity).
- **Provisioned speed / tier:** the download and upload speed contracted by the subscriber (`Download` / `Upload` columns, in Mbps).
- **CPE (Customer Premises Equipment):** equipment installed at the customer site (modem, router, ONT).
- **Line rate:** the maximum rate at which a device can forward traffic on an interface without loss.
- **HW NAT (hardware network address translation):** NAT performed by dedicated hardware instead of the CPU, which allows a router to keep high throughput. Devices without it can saturate at lower speeds.

## 3. Network Architecture & Infrastructure (FTTH / PON)

- **FTTH (Fiber to the Home):** architecture in which optical fiber runs from the central office directly to each residence.
- **PON (Passive Optical Network):** point-to-multipoint architecture that uses unpowered optical splitters so one fiber serves several premises.
- **GPON (Gigabit PON):** PON standard defined by ITU-T G.984, with up to 2.488 Gbps downstream and 1.244 Gbps upstream.
- **XGS-PON:** 10-Gigabit symmetrical PON standard defined by ITU-T G.9807.1.
- **OLT (Optical Line Terminal):** device at the provider's central office that connects the core network to the PON.
- **ONT / ONU (Optical Network Terminal / Unit):** customer-side device that converts optical signals to electrical signals.
- **ODN (Optical Distribution Network):** passive infrastructure (fibers, splitters, splice closures, connectors) between the OLT and the ONTs.
- **DSL / Cable (comparison technologies):** DSL (Digital Subscriber Line) delivers broadband over copper telephone lines; Cable (hybrid fiber-coaxial, HFC) delivers it over the coaxial cable network. **(project)** They are not part of the analyzed population (FTTH only), but the unit profile contains them and their hourly RTT profiles were used to test whether `dtime` is local or UTC (decision D-03), because only 18 Fiber units are in the Pacific time zone.

## 4. Network Performance Metrics (QoS)

- **QoS (Quality of Service):** objective, measurable network performance (bandwidth, delay, jitter, packet loss) managed by operators.
- **Latency:** the delay for a packet to travel across the network. It can be one-way or round-trip; the FCC MBA tests measure round-trip delay.
- **RTT (Round-Trip Time / tiempo de ida y vuelta):** time for a packet to travel from the source to the destination and back. In the data, `rtt_avg`, `rtt_min`, `rtt_max` and `rtt_std` are the average, minimum, maximum and standard deviation of the RTT in one test, in microseconds. **(project)** `p95_latency_ms` is built from `rtt_avg`.
- **Queuing delay:** time a packet waits in device queues. It grows with congestion and explains most of the hour-to-hour variation of RTT on a healthy fiber link.
- **Bufferbloat:** excess latency that appears when a link is saturated and the oversized buffers of a network device fill up, so packets wait in the queue instead of being dropped. **(project)** The executive brief lists it, together with the OLT, as a cause to check remotely before dispatching a technician; this analysis does not measure it directly.
- **Jitter:** variation of packet delay over time. It degrades real-time applications such as VoIP, video calls and gaming. The FCC documentation does not state the unit of `jitter_up` / `jitter_down`; the unit is verified in the data inspection.
- **Packet loss:** share of transmitted packets that never arrive. **(project)** In FCC MBA, a packet is counted as lost if no response arrives within 3 seconds, and loss is computed as `failures / (successes + failures)` from `curr_udplatency`.
- **Throughput:** rate of data actually delivered over a connection (Mbps or Gbps).
- **Bandwidth:** maximum capacity of a link or tier. Throughput is what is achieved; bandwidth is what is available.
- **Outage:** period in which connectivity is lost. In `curr_udpcloss.csv`, each row is an outage event with its `duration` and the number of packets lost (`packets`). **(project)**
- **Availability / uptime:** share of time a service is usable. Possible future metric built from outage events. **(project)**

## 5. Quality of Experience & Service Management

- **QoE (Quality of Experience):** overall acceptability of a service as perceived by the end user.
- **MOS (Mean Opinion Score):** rating from 1 (bad) to 5 (excellent) used to quantify perceived quality of voice, video or gaming.
- **KPI (Key Performance Indicator):** quantitative metric used to evaluate network or operational performance (e.g., latency, availability).
- **KQI (Key Quality Indicator):** indicator that reflects user perception of a specific service (e.g., video buffering time).
- **SLA / SLO (Service Level Agreement / Objective):** commitments on availability, latency and performance between a provider and a customer.
- **MTTR (Mean Time to Repair):** average time to troubleshoot and restore a failed network element or degraded service.
- **NOC (Network Operations Center):** team (or facility) that monitors the network and handles incidents and repairs. **(project)** The NOC manager is one of the two stakeholders of the executive brief and wants an actionable list of the units to review.

## 6. Risk Assessment (Project)

- **`risk_flag` (project):** 1 if a unit exceeds at least one threshold (latency, jitter or loss) during peak hours; 0 otherwise. Thresholds are parameters in `config.yaml`.
- **`risk_severe` (project):** second tier for extreme cases.
- **Threshold:** limit above which a metric marks a unit as at risk. Project-defined operating values, not attributed to a standard until verified in the source.
- **Sensitivity analysis:** reporting how results change when thresholds vary (e.g., latency × loss grid), instead of presenting a single arbitrary cut-off.
- **Sensitivity grid (project):** table of the number of units at risk for every combination of `N_MIN` (30, 50, 100), latency (20, 30, 50 ms), jitter (3, 4, 5 ms) and loss (0.05, 0.1, 0.5, 1 %) thresholds: 108 rows in `sensitivity_grid.csv` (decision D-08). Not to be confused with the 2x2 `variants_matrix.csv`, which varies the time reading and the server rule.
- **Server rule (project):** how many test servers feed a unit's metrics: `primary_only` (base case, D-04) or `all_servers` (sensitivity).
- **Analyzed vs insufficient unit (project):** an *analyzed* unit has at least `N_MIN` peak latency records and receives metrics and flags; an *insufficient* unit has fewer, is reported in `units_insufficient_data.csv` and is not scored. Percentages at risk use the analyzed units as denominator.
- **Severe (`risk_severe`) thresholds (project):** 50 ms P95 latency, 15 ms P95 jitter or 10 % loss, defined in `config.yaml`.
- **Peak window (project):** local hours 19:00 to 22:59 (`dtime` hour in [19, 23)). `dtime` is treated as the unit's local time, with no offset added (decision D-03).
- **Primary server (project):** the test server (`target`) with the most peak-window latency records for a unit. Latency, loss and jitter are all computed on that single server (decisions D-04 and D-06); ties go to the alphabetical order of the target.
- **`N_MIN` (project):** minimum number of peak latency records (50) for a unit to be scored, counted after the server rule. Units below it are listed in `units_insufficient_data.csv` and left out of the risk denominator (decision D-02).
- **Jitter minimum (project):** a unit's P95 jitter is computed only with at least 50 peak jitter records on the primary server; otherwise it stays null, never 0, and the unit is still scored on latency and loss (decision D-07).
- **Episodic vs persistent flag (project):** a latency flag is *episodic* when the P95 without the worst day (`p95_latency_without_worst_day_ms`) falls to the threshold or below, and *persistent* otherwise. Descriptive wording only: it does not change `risk_flag` (decision D-10).
- **Risk score / risk index:** generic term for a calculated measure of the probability and impact of degradation. Not used in this project, which reports binary flags.

## 7. Financial & Operational Concepts

- **CAPEX (Capital Expenditure):** upfront spending to acquire, upgrade and maintain physical assets such as fiber, OLTs and splitters.
- **OPEX (Operational Expenditure):** recurring costs of running the network and business: maintenance, truck rolls, customer support, power.
- **Truck roll:** a technician dispatch to the customer site. A key OPEX driver.
- **ROI (Return on Investment):** profitability ratio used to evaluate an investment or strategy.
- **Churn rate:** percentage of subscribers who cancel in a period; often linked to poor QoE.
- **ARPU (Average Revenue Per User):** average revenue per active subscriber.
- **CXO (C-level executive):** generic term for a top executive such as the CEO, CFO, CTO or COO. **(project)** One of the two stakeholders of the executive brief: the CXO wants the size of the problem (share of analyzed units at risk), while the NOC manager wants the list of units to act on.

## 8. Data Engineering & Methodology

- **Data pipeline:** automated flow that ingests, cleans, transforms and loads data. **(project)** Here a batch pipeline, CSV only: raw FCC CSV files → interim CSV (filtered to the 258 units) → unit-level metrics CSV in `data/processed/` → Power BI. Implemented in `src/pipeline.py`.
- **Interim vs processed data (project):** two layers of files between the raw data and Power BI. *Interim* files (`data/interim/`: filtered raw rows and caches such as `pipeline_udplatency_ftth.csv`) can be regenerated and are gitignored; *processed* files (`data/processed/`: unit metrics, insufficient units, data-quality log, variants matrix and sensitivity grid) are the output of `pipeline.py`, are versioned, and are the only data Power BI consumes. The raw FCC files (6.8 GB) are in neither layer and are not in the repository.
- **ETL / ELT:** extract-transform-load (or load-then-transform) patterns for moving and preparing data.
- **Data lineage:** record of where data comes from and every transformation applied to it.
- **Data dictionary:** documentation of the meaning, type and unit of each column.
- **DIM table (dimension table):** table that describes the entities of an analysis (who, what, where), with one row per entity and a key that other tables refer to; the opposite of a fact table, which stores the measurements or events. **(project)** `unit-profile-sept2022.xlsx` is the DIM of the units (who), and `fiber_units.csv` is the clean DIM of the 258 in-scope units; both are joined to the measurements by `unit_id` (`Unit ID`).
- **FACT table:** table that stores the measurements or events of an analysis, one row per event, with keys that point to DIM tables. **(project)** `curr_udplatency.csv` (one hourly test per row) and `curr_udpjitter.csv` (one UDP stream test per row) are the input FACT tables; `ftth_qoe_unit_metrics.csv` (one analyzed unit per row) is the output FACT table.
- **Data-quality log:** table that counts records discarded by each validation rule. **(project)**
- **DQ (data quality):** shorthand for the checks on record validity and duplicates. **(project)** Used in the names of the audit tables of the Power BI model (`aud_dq`, `aud_dq_jit`) and in `data_quality_log.csv`.
- **Capping / zero-filling (project):** capping replaces values above a limit with the limit (for example `min(x, 100)` on a loss percentage); zero-filling replaces nulls with 0 (`fillna(0)`). Both are forbidden in v3 because they hide problems and an invented zero makes a unit without data look perfect (they were part of the v2.2 failure). Invalid records are excluded and counted in the data-quality log, and a null jitter stays null.
- **Duplicate records (project):** rows that repeat the key (`unit_id`, `dtime`, `target`). Decision D-05: if the repeated rows are identical, one is kept; if their values conflict, all of them are dropped. Found in the FTTH rows: `curr_udplatency` 16 rows in 7 groups, all exact (9 extra rows removed); `curr_udpjitter` 10 rows, 8 exact (4 extra rows removed) and 2 conflicting (unit 943232, both dropped).
- **Outlier:** value far from the rest of the data; it can be a real event or a data error and must be investigated before being removed.
- **Percentile (P1, P50, P95, P99):** value below which a given share of observations falls. P50 is the median; P95 describes the poorer end of the distribution; P1 and P99 describe the extremes and are used in the data inspection to read the spread of a column (for example, `successes + failures` per row has P1 = 65).
- **Linear interpolation (percentile method):** when a percentile falls between two sorted observations, its value is computed proportionally between them. It is the default of pandas `quantile` and of `PERCENTILE.INC` in Excel and Power BI. **(project)** The P95 of unit 4190285 is 50.00 ms by interpolation between 39.26 and 53.59 ms (sorted positions 62 and 63 of 66); no record equals 50.0 ms, so it is not a measurement ceiling.
- **Correlation (Pearson / Spearman):** measures of how closely two series move together, from -1 to 1. Pearson measures linear association between the values; Spearman measures it between their ranks, so it tolerates outliers and non-linear monotonic relations. **(project)** Decision D-03 uses Pearson (pandas default) between the hourly RTT profile of Eastern units and that of Pacific units shifted by *k* hours; `step_10.py` uses Spearman (0.816) between the per-unit median jitter and median `rtt_std` to support the jitter unit.
- **Ratio of sums (weighted aggregation):** computing a rate as `sum(numerator) / sum(denominator)` instead of averaging per-row percentages, so each row counts in proportion to its size. **(project)** Used for loss because the number of packets varies by hour.
- **Reconciliation:** comparing two implementations of the same metric record by record to find where they differ. **(project)** Python vs Power BI, per `Unit ID`.
- **Automated tests / regression test (project):** code that checks the pipeline output without manual review. `tests/test_unit_metrics.py` (pytest) runs 21 checks of spec section 9; its last test is a regression test that compares the output with the reference base case (237 analyzed / 21 insufficient / 5 at risk) and fails when data, configuration or code change that result.
- **Convenience bias:** error from analyzing the data that is easiest to reach (e.g., the first rows of a file) instead of a representative sample. **(project)** Cause of the v1 failure.
- **Instrument bias:** error introduced by the measuring device itself. **(project)** Legacy Whiteboxes that cannot sustain line rate created false latency and loss in v2.
- **Measurement artifact (project):** a result produced by the measuring device or by the analysis instead of by the network the subscriber experiences. Examples handled in this project: legacy Whitebox models that created false latency and loss (instrument bias), mixing test servers at different distances, reading `dtime` with the wrong time convention, and treating `curr_udpcloss` outage counts as a loss percentage. Separating real degradation from artifacts is the goal of methodology v3.
- **Power Query (M) / DAX:** Power BI languages for data transformation (Power Query) and calculated measures (DAX).

## 9. Power BI (Project)

Terms used in `docs/powerbi_implementation.md`.

- **`.pbix`:** Power BI Desktop file that stores the model (tables, relationships, measures) and the report pages in one file. **(project)** `powerbi/ftth_qoe.pbix` (295 KB).
- **Semantic model (data model):** the tables, relationships and measures behind the report. Visuals read from it; they do not hold data themselves.
- **Flat model vs star schema:** a flat model keeps everything in one table; a star schema separates a fact table from dimension tables joined by relationships. **(project)** The report uses a flat model (`unit_metrics` is the single fact table) by design; the trade-offs are in section 13 of `docs/powerbi_implementation.md`.
- **Measure:** a DAX calculation evaluated at query time in the context of the filters (for example `Analyzed Units`, `% At Risk`). Not stored per row, unlike a calculated column.
- **Calculated column:** a DAX column computed row by row when the data is loaded and stored in the model. **(project)** `unit_metrics[Latency Pattern]` (Persistent / Episodic).
- **Display folder:** a label that groups measures in the field list. **(project)** `1 Population`, `2 Risk`, `3 Data Quality`, `4 Report`.
- **Slicer:** a visual that filters the rest of the page. **(project)** The ISP slicer is synced across pages; the `N_MIN` and jitter-threshold slicers on page 5 drive the sensitivity view.
- **Disconnected table:** a table with no relationship to the rest of the model, so slicers and filters do not reach it. **(project)** `variants_matrix`, `sensitivity_grid` and `data_quality_log`.
- **`TREATAS`:** DAX function that applies the values of one column as a filter on another column without a relationship. **(project)** It carries the ISP and state selection from `unit_metrics` to `units_insufficient`.
- **Row-level security (RLS):** a role defined by a DAX filter on a table, which restricts the rows a user can see in the same report. Users are assigned to roles in the Power BI Service; in Desktop it is tested with *View as*. It differs from object-level security, which hides tables or columns. **(project)** Role `ISP_Verizon` (`[isp] = "Verizon"`); its limits are in section 12.5 of `docs/powerbi_implementation.md`.
- **Performance Analyzer:** Power BI Desktop tool that times each visual: DAX query, visual display and other. **(project)** The DAX query is the value that reflects the model; all queries here are under 25 ms.
- **Theme:** JSON file with the colours, fonts and visual defaults of a report. **(project)** `powerbi/theme/ftth_qoe_theme.json`.
- **Audit and reconciliation tables (project):** Power Query tables (`aud_*`, `rec_*`) that recompute the metrics from `data/interim/` and compare them with `data/processed/` per `Unit ID`. They are hidden in the report view; hiding is not a security measure.

## Sources

- FCC. *Technical Appendix – Fixed Broadband, 2023* (test descriptions, loss definition, data dictionary): https://data.fcc.gov/download/measuring-broadband-america/2023/Technical-Appendix-fixed-2023.pdf
- FCC. *2023 Fixed Measuring Broadband America Report*: https://data.fcc.gov/download/measuring-broadband-america/2023/2023-Fixed-Measuring-Broadband-America-Report.pdf
- IB Lenhardt. *Mexico introduces new telecom law: IFT replaced by ATDT and CRT*: https://ib-lenhardt.com/news/mexico-introduces-new-telecom-law-ift-replaced-by-atdt-and-crt