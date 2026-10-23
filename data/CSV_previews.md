# CSV Previews — First 10 Rows of the Raw Files

**Purpose:** show the structure of the three raw FCC MBA files used in this project and record what the first rows confirm for the data inspection (Step 0 in `docs/metrics_spec.md`).

**Important limits of this preview**

- These are the **first 10 rows of each complete file**, not a sample of the FTTH population. Checking the unit profile shows that **none of these units is in the 258-unit FTTH population**: they are Cable units (Cox, Optimum) and DSL units (CenturyLink, Windstream).
- Use the previews to understand **structure, units and meaning of columns**, not to draw conclusions about latency, jitter or loss of FTTH units. Values such as `rtt_avg` of 66–158 ms belong to DSL units testing against a distant server and must not be compared with FTTH results.
- Source column meanings: `docs/data_dictionary.md`.

---

## 1. `curr_udpcloss.csv` — Outage / Disconnection Events

Each row is an **outage event**, not a loss percentage (see `docs/data_dictionary.md`). `duration` is in microseconds and `packets` is the number of packets lost during the event.

| # | unit_id | dtime | ddate | duration | target | address | packets |
|---:|---:|---|---|---:|---|---|---:|
| 0 | 55492301 | 2022-09-12 03:29:44 | 2022-09-12 | 4500670 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 2 |
| 1 | 55492301 | 2022-09-12 04:07:26 | 2022-09-12 | 4499269 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 2 |
| 2 | 3898881 | 2022-09-12 15:19:21 | 2022-09-12 | 4500536 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 2 |
| 3 | 55518537 | 2022-09-12 15:19:20 | 2022-09-12 | 4500548 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 2 |
| 4 | 1001172 | 2022-09-12 14:57:45 | 2022-09-12 | 5997850 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 3 |
| 5 | 1001172 | 2022-09-12 09:35:19 | 2022-09-12 | 4482312 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 2 |
| 6 | 1001172 | 2022-09-12 11:02:24 | 2022-09-12 | 10507162 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 3 |
| 7 | 55492301 | 2022-09-12 01:21:16 | 2022-09-12 | 4499062 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 2 |
| 8 | 55492301 | 2022-09-12 04:04:37 | 2022-09-12 | 4500040 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 2 |
| 9 | 3767145 | 2022-09-12 14:08:27 | 2022-09-12 | 4499515 | 1-atlanta-on.east.cox.net | 68.1.16.52 | 2 |

## 2. `curr_udpjitter.csv` — UDP Jitter Test

The wide table is split in two for readability.

### Table 1: Test configuration

| # | unit_id | dtime | ddate | target | packet_size | stream_rate | duration |
|---:|---:|---|---|---|---:|---:|---:|
| 0 | 3898625 | 2022-10-04 08:31:35 | 2022-10-04 | sk-1.uhnet.net | 160 | 64000 | 14996277 |
| 1 | 40730149 | 2022-10-31 07:37:31 | 2022-10-31 | sk-1.uhnet.net | 160 | 64000 | 14992530 |
| 2 | 1006638 | 2022-10-27 16:22:37 | 2022-10-27 | sk-1.uhnet.net | 160 | 64000 | 14993764 |
| 3 | 40518705 | 2022-10-31 05:59:42 | 2022-10-31 | sk-1.uhnet.net | 160 | 64000 | 14998970 |
| 4 | 40844089 | 2022-10-29 16:14:07 | 2022-10-29 | sk-1.uhnet.net | 160 | 64000 | 14996406 |
| 5 | 80307525 | 2022-10-15 22:09:47 | 2022-10-15 | sk-1.uhnet.net | 160 | 64000 | 14997091 |
| 6 | 80307525 | 2022-10-16 04:09:47 | 2022-10-16 | sk-1.uhnet.net | 160 | 64000 | 14995037 |
| 7 | 1006922 | 2022-10-24 13:26:22 | 2022-10-24 | sk-1.uhnet.net | 160 | 64000 | 14999534 |
| 8 | 40518741 | 2022-10-11 17:33:27 | 2022-10-11 | sk-1.uhnet.net | 160 | 64000 | 14990880 |
| 9 | 40518741 | 2022-10-11 04:33:27 | 2022-10-11 | sk-1.uhnet.net | 160 | 64000 | 14999179 |

### Table 2: Traffic, jitter and latency

| # | unit_id | packets_up_sent | packets_down_sent | packets_up_recv | packets_down_recv | jitter_up | jitter_down | latency | successes | failures |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3898625 | 500 | 500 | 500 | 500 | 1093 | 1294 | 68075 | 1 | 0 |
| 1 | 40730149 | 500 | 500 | 500 | 494 | 466 | 218 | 120102 | 1 | 0 |
| 2 | 1006638 | 500 | 500 | 500 | 500 | 1666 | 363 | 112897 | 1 | 0 |
| 3 | 40518705 | 500 | 500 | 500 | 500 | 3077 | 708 | 118118 | 1 | 0 |
| 4 | 40844089 | 500 | 500 | 500 | 500 | 1782 | 825 | 161416 | 1 | 0 |
| 5 | 80307525 | 500 | 500 | 500 | 500 | 796 | 536 | 98761 | 1 | 0 |
| 6 | 80307525 | 500 | 500 | 497 | 500 | 55714 | 783 | 179859 | 1 | 0 |
| 7 | 1006922 | 500 | 500 | 499 | 500 | 561 | 218 | 85353 | 1 | 0 |
| 8 | 40518741 | 500 | 500 | 500 | 500 | 2092 | 424 | 131238 | 1 | 0 |
| 9 | 40518741 | 500 | 500 | 500 | 500 | 2165 | 613 | 128728 | 1 | 0 |

## 3. `curr_udplatency.csv` — UDP Latency (RTT) and Packet Loss

| # | unit_id | dtime | ddate | target | rtt_avg | rtt_min | rtt_max | rtt_std | successes | failures |
|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 0 | 3898625 | 2022-10-06 22:35:03 | 2022-10-06 | sk-1.uhnet.net | 66286 | 65422 | 69438 | 329 | 931 | 0 |
| 1 | 39827785 | 2022-10-11 15:54:33 | 2022-10-11 | sk-1.uhnet.net | 114964 | 113642 | 126049 | 791 | 2150 | 0 |
| 2 | 39827785 | 2022-10-16 02:54:26 | 2022-10-16 | sk-1.uhnet.net | 117649 | 111246 | 231499 | 18112 | 674 | 2 |
| 3 | 39827785 | 2022-10-16 01:54:26 | 2022-10-16 | sk-1.uhnet.net | 127296 | 111549 | 395900 | 39790 | 186 | 5 |
| 4 | 39827785 | 2022-10-13 22:54:30 | 2022-10-13 | sk-1.uhnet.net | 127514 | 111250 | 282912 | 35201 | 883 | 6 |
| 5 | 39827785 | 2022-10-15 22:54:26 | 2022-10-15 | sk-1.uhnet.net | 158707 | 111409 | 284944 | 57311 | 131 | 5 |
| 6 | 39827785 | 2022-10-13 08:54:30 | 2022-10-13 | sk-1.uhnet.net | 114841 | 113570 | 115791 | 403 | 2365 | 12 |
| 7 | 40518741 | 2022-10-16 10:35:41 | 2022-10-16 | sk-1.uhnet.net | 127209 | 123964 | 149148 | 1880 | 2147 | 0 |
| 8 | 40518741 | 2022-10-13 02:56:26 | 2022-10-13 | sk-1.uhnet.net | 126267 | 121329 | 135527 | 1838 | 2085 | 2 |
| 9 | 40518741 | 2022-10-13 09:56:26 | 2022-10-13 | sk-1.uhnet.net | 126089 | 121521 | 129875 | 1825 | 2260 | 3 |

---

## 4. What the Previews Show (Step 0 Findings)

| Check | Observation | Status |
| :--- | :--- | :--- |
| Headers vs dictionary | All three files include a `ddate` column that the dictionary does not list for `curr_udplatency` and `curr_udpjitter`. `location_id` (listed for `curr_udplatency`) is not present. The jitter file header uses `latency` in lowercase; the dictionary writes `Latency` | Differences found; use the real headers |
| `curr_udpcloss` meaning | `duration` ≈ 4.5 s with `packets` = 2 per event. The latency test sends about one packet every 1.8 s (~2,000 per hour), so ~4.5 s of outage corresponds to 2–3 lost packets. This is consistent with `packets` being a count of lost packets per event, not a percentage | Consistent with the dictionary (inference, not proof) |
| Time unit | `duration` in `curr_udpjitter` ≈ 14,996,277, i.e. about 15 s if the unit is microseconds | µs confirmed for `duration`; jitter unit indirectly supported |
| Jitter magnitude | `jitter_up` / `jitter_down` between 218 and 55,714; as microseconds this is 0.2–55.7 ms, a plausible range | Consistent with µs, not proven |
| Jitter test length | Dictionary documents a 10 s test at 64 kbps; the preview shows `duration` ≈ 15 s with 500 packets per direction at 160 bytes | Discrepancy to explain; not used in metrics |
| `successes` / `failures` in jitter | Always 1 / 0 in the preview, as the dictionary states | Not usable as a loss count |
| Variable packet counts | `successes + failures` in `curr_udplatency` ranges from 131 to 2,365 per row | Supports the ratio-of-sums loss formula |
| `dtime` time zone | `ddate` equals the date part of `dtime` in all 30 rows, so these rows cannot show whether `dtime` is UTC or local | Inconclusive; check 3 and 4 remain open |
| Date range | `dtime` values range from 2022-09-12 to 2022-10-31 across the three previews | The data is not limited to September; confirm the full range |
| `target` values | `1-atlanta-on.east.cox.net` (`curr_udpcloss`) and `sk-1.uhnet.net` (jitter and latency) | Compare targets used by the 258 FTTH units (check 5) |

**Next step:** repeat the inspection filtered to the 258 FTTH `unit_id` values (first rows, date range, distinct `target` values, rows per unit).
