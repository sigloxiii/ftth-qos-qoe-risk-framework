# FTTH QoE Risk Analysis - Executive Project Brief
### Capstone: Google Data Analytics + FCC MBA Data | 2022-09-12 to 2022-10-31 | Methodology v3.0

> Quick technical cheat-sheet and business context for non-technical readers. Source of truth for every rule and value: `docs/metrics_spec.md` (v1.2.0) and `config.yaml`.

---

### 1. What is this project about? (For everyone)

Imagine you are a fiber ISP (FTTH). Some of your homes have a small white box (Whitebox) that measures internet quality every hour.

The question: in the local evening peak (19:00-22:59), when many people stream, game and video-call, which homes show degraded quality? And how much of that degradation is real, versus an artifact of the measuring device or of the analysis?

**Key result:** of the 258 FTTH units in scope, 237 could be analyzed (21 have too few records) and 5 of them (2.1%) are at risk: 4 with a persistent latency problem and 1 episodic. The count depends on the minimum-records rule (between 1 and 7 units at risk) and was confirmed unit by unit between Python and Power BI (0 mismatches). Figures from earlier versions (v1, v2.x) are invalid and are not reused.
The only severe case is the episodic one (unit 4190285), and its severe tier rests on a P95 just above the threshold.

### 2. What does each record measure? (No jargon)

Each row in the raw data is NOT a customer and NOT a single packet. It is **one hourly test** of one Whitebox.

*   **Latency test (`curr_udplatency`):** one row summarizes the test: average round-trip time (`rtt_avg`) and how many packets got a reply (`successes`) or not (`failures`). The packet count varies by row (131 to 2,365 in the first rows inspected).
*   **Jitter test (`curr_udpjitter`):** one row is one UDP stream; it reports how much the delay varied (`jitter_up`, `jitter_down`).
*   **Path:** Whitebox -> home network -> ISP -> Internet -> test server (all servers are SamKnows-hosted).

**Reference values observed in the data:** median RTT per unit between 2.5 and 17.2 ms; global packet loss about 0.022%.

**When we mark `risk_flag = 1`:**
During the peak window, against the unit's primary server, over the 50 observed days, at least one of these holds:
- P95 latency > 20 ms, or
- P95 jitter > 5 ms, or
- packet loss > 1%.

These thresholds are **project-defined operating thresholds**, not values from a standard. P95 means that 95% of the unit's peak-hour tests are at or below that value; a unit is flagged when its worst 5% of peak-hour tests are already above the limit. It is computed over hourly averages, so brief spikes inside a single test are not visible in it.

### 3. Datasets Used (Technical Cheat-Sheet)

| File | Role | 1 row = | Key Columns |
| :--- | :--- | :--- | :--- |
| `unit-profile-sept2022.xlsx` | DIM - Who | 1 Whitebox / home | `Unit ID, ISP, Technology, State, Whitebox Model, Download, Upload, timezone_offset_dst` |
| `fiber_units.csv` | Clean DIM (258) | 1 in-scope home | Filter: `Whitebox Model IN (skwb8 227, ac1750v2 28, skwb8p 3)` |
| `curr_udplatency.csv` | FACT - Latency + loss | 1 hourly test | `unit_id, dtime, target, rtt_avg (µs), successes, failures` |
| `curr_udpjitter.csv` | FACT - Jitter | 1 UDP stream test | `unit_id, dtime, target, jitter_up, jitter_down` |
| `curr_udpcloss.csv` | Outage events (reference only) | 1 outage event | `unit_id, dtime, duration, packets` - NOT a loss percentage |
| `ftth_qoe_unit_metrics.csv` | Output FACT | 1 analyzed unit | `unit_id, p95_latency_ms, p95_jitter_ms, loss_pct, risk_flag, risk_severe` |

**Golden rules:**
- raw microseconds / 1000 = ms.
- P95 uses linear interpolation (`quantile(0.95)` in pandas = `PERCENTILE.INC` in Excel and Power BI), never `AVERAGE`.
- Loss = `sum(failures) / sum(successes + failures) * 100` (ratio of sums, from `curr_udplatency`).
- No capping and no `fillna(0)`: invalid records are excluded and counted.

### 4. Full Process (6 Steps for Quick Review)

**Step 1 - Population (instrument bias fix):**
The Whitebox is the measuring instrument; a legacy model that cannot forward at line rate creates the degradation it reports. From 285 FTTH units, keep Whitebox models `skwb8`, `skwb8p`, `ac1750v2` -> **258 units**. The 27 legacy units are listed in `data/excluded_legacy_ftth_units.csv`. The filter uses the nominal capability of each model, not a per-unit throughput test.

**Step 2 - Peak window (D-03):**
`dtime` is treated as the unit's **local** time (the data does not behave as UTC, as the FCC documentation says). `local_hour = hour(dtime)`, no offset added. Peak window: local hour >= 19 and < 23. The UTC reading is reported as a sensitivity with every result.

**Step 3 - Server rule (D-04):**
A unit uses 1 to 4 test servers at different distances. Metrics use the unit's **primary server** (the target with the most peak-window records; ties by alphabetical order). All servers pooled is reported as a sensitivity.

**Step 4 - Metrics per unit (peak window only):**
`p95_latency = P95(rtt_avg / 1000)`, `p95_jitter = P95((jitter_up + jitter_down) / 2 / 1000)`, `loss_pct` as above. Units with fewer than 50 peak records (`N_MIN`, D-02) are reported separately and are not scored.

**Step 5 - Risk flag:**
`risk_flag = 1` if latency > 20 ms OR jitter > 5 ms OR loss > 1% (strictly greater). `risk_severe` uses 50 ms / 15 ms / 10%. A threshold sensitivity grid is reported with every result.

**Step 6 - Power BI:**
  Power BI consumes `data/processed/ftth_qoe_unit_metrics.csv`, `units_insufficient_data.csv`, `variants_matrix.csv`, `sensitivity_grid.csv` and `data_quality_log.csv`; it does not recalculate metrics. Python and Power BI are reconciled per `Unit ID` with explicit tolerances (`docs/reconciliation.md`).

### 5. Quick Glossary (For non-technical stakeholder)
 (FULL Glossary in `docs/glossary_of_terms.md`)
*   **FTTH:** Fiber To The Home.
*   **Whitebox:** FCC measurement device, not the customer router.
*   **P95:** 95% of the tests are at or below this value. If P95 is high, the worst tests at peak are bad.
*   **Bufferbloat:** Packet queue in the home router when upload saturates.
*   **OLT/ONT:** OLT is at the ISP central office, ONT is the box at home. Light travels between them.
*   **Churn:** Customer leaving.

### 6. Stakeholders & Business Questions

**Stakeholders:** NOC Manager (wants an actionable list), CXO (wants the size of the problem).

**3 Business Questions Answered:**
1. What share of the analyzed fiber units has poor QoE at peak?
2. Which are the specific units to review?
3. How robust is that result to the time convention, the server rule and the thresholds (sensitivity analysis)?

**3 Proposed Actions (to be confirmed once results exist):**
1. Alert when a unit's peak P95 stays above the threshold for several consecutive days (number of days to be defined).
2. Remote triage (OLT, bufferbloat) before dispatching a technician.
3. Contact flagged customers proactively.

Financial impact (churn, truck rolls) is not estimated: there is no source for the unit costs. If an estimate is added, it will be a clearly labeled scenario with explicit assumptions.

### 7. Limitations

- Two months of data from a non-random sample of volunteer units; results do not represent all FTTH subscribers.
- 220 of the 258 units (85%) are in the US Eastern time zone.
- The local-time reading of `dtime` rests on indirect evidence and contradicts the FCC general note.
- The jitter unit (µs) is supported indirectly (per-unit jitter against `rtt_std`) but not documented by the FCC, and jitter is dominated by the upstream value. It is evaluated only for units with at least 50 peak jitter records (decision D-07); the rest are scored on latency and loss.