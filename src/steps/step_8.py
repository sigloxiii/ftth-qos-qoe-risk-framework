# step_8.py
# Objective: Confirm the result of step_7.py with a sharper test of whether dtime is UTC or
#            local time. Improvements over step_7.py:
#            1. Shifts from -6 to +6 hours (step_7.py only tested 0 to 6)
#            2. Eastern vs Pacific compared within the SAME technology (Cable, DSL, Fiber...),
#               to remove differences caused by the technology mix of each region
#            If dtime is UTC, the Pacific pattern lags the Eastern one by 3 hours (best k = 3).
#            If dtime is local, both patterns align (best k near 0).
# Inputs:    data/unit-profile-sept2022.xlsx
#            data/raw/validated-data-sept2022/curr_udplatency.csv
# Outputs:   Console only (results are documented in docs/data_inspection.md)

import pandas as pd

BASE = r"D:\Capstone FTTH"
RAW = BASE + r"\data\raw\validated-data-sept2022"

prof = pd.read_excel(BASE + r"\data\unit-profile-sept2022.xlsx")  # needs openpyxl
prof = prof.rename(columns={"Unit ID": "unit_id"})
prof["group"] = prof["timezone_offset_dst"].map({-4: "Eastern", -7: "Pacific"})
grp = prof.dropna(subset=["group"])[["unit_id", "group", "Technology"]]

# Units by technology and region; only technologies with >= 30 units in both regions are compared
counts = grp.groupby(["Technology", "group"]).size().unstack(fill_value=0)
print("Unidades por tecnología y región:\n", counts)
techs = counts[(counts["Eastern"] >= 30) & (counts["Pacific"] >= 30)].index

# Chunked read: sum and count of rtt_avg by technology, region and dtime hour
parts = []
for chunk in pd.read_csv(RAW + r"\curr_udplatency.csv", usecols=["unit_id", "dtime", "rtt_avg"],
                         parse_dates=["dtime"], chunksize=2_000_000):
    chunk = chunk.merge(grp, on="unit_id")
    chunk["hour"] = chunk["dtime"].dt.hour
    parts.append(chunk.groupby(["Technology", "group", "hour"])["rtt_avg"].agg(["sum", "count"]))
tot = pd.concat(parts).groupby(level=[0, 1, 2]).sum()
tot["mean_ms"] = tot["sum"] / tot["count"] / 1000  # µs -> ms

for tech in techs:
    # reindex(range(24)) guarantees all 24 hours even if one is missing
    east = tot.loc[(tech, "Eastern"), "mean_ms"].reindex(range(24))
    pac = tot.loc[(tech, "Pacific"), "mean_ms"].reindex(range(24))
    print(f"\n=== {tech} ===")
    print("Hora de dtime con el RTT máximo: Este", east.idxmax(), "| Pacífico", pac.idxmax())
    print("Correlación Este vs Pacífico desplazado k horas (k = 3: UTC; k = 0: local):")
    for k in range(-6, 7):
        shifted = pd.Series([pac[(h + k) % 24] for h in range(24)], index=range(24))
        print("  k =", k, "->", round(east.corr(shifted), 3))

'''
Unidades por tecnología y región:
 group       Eastern  Pacific
Technology                  
Cable           321      138
DSL             440      175
Fiber           246       18

=== Cable ===
Hora de dtime con el RTT máximo: Este 21 | Pacífico 20
Correlación Este vs Pacífico desplazado k horas (k = 3: UTC; k = 0: local):
  k = -6 -> 0.191
  k = -5 -> 0.359
  k = -4 -> 0.553
  k = -3 -> 0.745
  k = -2 -> 0.877
  k = -1 -> 0.892
  k = 0 -> 0.762
  k = 1 -> 0.493
  k = 2 -> 0.184
  k = 3 -> -0.107
  k = 4 -> -0.335
  k = 5 -> -0.506
  k = 6 -> -0.604

=== DSL ===
Hora de dtime con el RTT máximo: Este 21 | Pacífico 19
Correlación Este vs Pacífico desplazado k horas (k = 3: UTC; k = 0: local):
  k = -6 -> 0.338
  k = -5 -> 0.478
  k = -4 -> 0.649
  k = -3 -> 0.798
  k = -2 -> 0.799
  k = -1 -> 0.737
  k = 0 -> 0.594
  k = 1 -> 0.429
  k = 2 -> 0.235
  k = 3 -> -0.018
  k = 4 -> -0.286
  k = 5 -> -0.478
  k = 6 -> -0.575
  '''