# step_7.py
# Objective: Test whether dtime is UTC or local time, using a reference that does not depend
#            on FTTH (FTTH latency is nearly flat across the day, see step_1.py).
#            Idea: user activity follows LOCAL time, and Pacific units are 3 hours behind
#            Eastern units.
#            - If dtime is UTC, the daily RTT pattern of Pacific units appears 3 hours LATER
#              in dtime than the pattern of Eastern units.
#            - If dtime is local, both patterns appear at the same dtime hour.
#            Uses all units of the unit profile (any technology) with timezone_offset_dst of
#            -4 (Eastern) or -7 (Pacific) and compares the two hourly RTT profiles shifted by
#            0 to 6 hours.
# Inputs:    data/unit-profile-sept2022.xlsx
#            data/raw/validated-data-sept2022/curr_udplatency.csv
# Outputs:   Console only (results are documented in docs/data_inspection.md)

import pandas as pd

BASE = r"D:\Capstone FTTH"
RAW = BASE + r"\data\raw\validated-data-sept2022"

# Groups by time zone during daylight saving time: -4 = Eastern, -7 = Pacific (any technology)
prof = pd.read_excel(BASE + r"\data\unit-profile-sept2022.xlsx")  # needs openpyxl
prof = prof.rename(columns={"Unit ID": "unit_id"})
prof["group"] = prof["timezone_offset_dst"].map({-4: "Eastern", -7: "Pacific"})
grp = prof.dropna(subset=["group"])[["unit_id", "group"]]
print("Unidades por grupo:\n", grp["group"].value_counts())

# Chunked read: sum and count of rtt_avg by group and dtime hour
parts = []
for chunk in pd.read_csv(RAW + r"\curr_udplatency.csv", usecols=["unit_id", "dtime", "rtt_avg"],
                         parse_dates=["dtime"], chunksize=2_000_000):
    chunk = chunk.merge(grp, on="unit_id")  # only Eastern and Pacific units
    chunk["hour"] = chunk["dtime"].dt.hour
    parts.append(chunk.groupby(["group", "hour"])["rtt_avg"].agg(["sum", "count"]))
tot = pd.concat(parts).groupby(level=[0, 1]).sum()
tot["mean_ms"] = tot["sum"] / tot["count"] / 1000  # µs -> ms

east = tot.loc["Eastern", "mean_ms"]
pac = tot.loc["Pacific", "mean_ms"]
print("\nRTT medio (ms) por hora de dtime:\n", pd.DataFrame({"Eastern": east, "Pacific": pac}).round(2))
print("\nAmplitud relativa (máx - mín) / media: Este",
      round((east.max() - east.min()) / east.mean() * 100, 1), "% | Pacífico",
      round((pac.max() - pac.min()) / pac.mean() * 100, 1), "%")

# Correlation between the Eastern profile and the Pacific profile shifted by k hours
print("\nCorrelación Este vs Pacífico desplazado k horas (k = 3: dtime es UTC; k = 0: dtime es local):")
for k in range(7):
    shifted = pd.Series([pac[(h + k) % 24] for h in range(24)], index=range(24))
    print("  k =", k, "->", round(east.corr(shifted), 3))


'''
Unidades por grupo:
 group
Eastern    1007
Pacific     331
Name: count, dtype: int64

RTT medio (ms) por hora de dtime:
       Eastern  Pacific
hour                  
0       19.61    23.57
1       19.69    23.46
2       19.58    23.38
3       19.46    23.42
4       19.44    23.36
5       19.37    23.28
6       19.31    23.26
7       19.31    23.44
8       19.32    23.64
9       19.50    23.84
10      19.58    23.66
11      19.56    23.85
12      19.60    23.81
13      19.57    23.76
14      19.53    23.73
15      19.56    23.77
16      19.58    23.75
17      19.62    23.95
18      19.67    24.13
19      19.81    24.25
20      20.03    24.10
21      20.22    23.98
22      20.13    23.93
23      19.85    23.86

Amplitud relativa (máx - mín) / media: Este 4.7 % | Pacífico 4.2 %

Correlación Este vs Pacífico desplazado k horas (k = 3: dtime es UTC; k = 0: dtime es local):
  k = 0 -> 0.67
  k = 1 -> 0.44
  k = 2 -> 0.179
  k = 3 -> -0.122
  k = 4 -> -0.363
  k = 5 -> -0.505
  k = 6 -> -0.574
  '''