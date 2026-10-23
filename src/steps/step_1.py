# step_1.py
# Objective: Cache the FTTH-only records and run the diagnostics needed to close Step 0
#            (docs/metrics_spec.md, section 2, checks 4 and 5).
#            1. Filter the three raw files to the 258 FTTH units and save them as interim CSVs
#            2. Tests per hour (UTC vs local time) to validate the time zone convention
#            3. Test servers per unit and median RTT by state (possible geographic bias)
#            4. Peak-window records per unit (full period vs September only) to set the
#               date range and N_MIN
# Inputs:    data/fiber_units.csv
#            data/raw/validated-data-sept2022/curr_udplatency.csv, curr_udpjitter.csv, curr_udpcloss.csv
# Outputs:   data/interim/udplatency_ftth.csv, udpjitter_ftth.csv, udpcloss_ftth.csv (gitignored)
#            Console diagnostics (results are documented in docs/data_inspection.md)

import os
import pandas as pd

BASE = r"D:\Capstone FTTH"
RAW = BASE + r"\data\raw\validated-data-sept2022"
INTERIM = BASE + r"\data\interim"
os.makedirs(INTERIM, exist_ok=True)  # creates the folder if it does not exist

units = pd.read_csv(BASE + r"\data\fiber_units.csv", encoding="utf-8-sig")
units = units.rename(columns={"Unit ID": "unit_id"})
ids = set(units["unit_id"])  # the 258 FTTH units

# --- Stage 1: raw CSV -> CSV filtered to the 258 FTTH units ---
# Read in chunks of 2M rows: the files are too large to load at once
SPECS = {
    "udplatency": ["unit_id", "dtime", "target", "rtt_avg", "rtt_min", "successes", "failures"],
    "udpjitter":  ["unit_id", "dtime", "target", "jitter_up", "jitter_down"],
    "udpcloss":   ["unit_id", "dtime", "duration", "packets"],
}
for name, cols in SPECS.items():
    out = INTERIM + rf"\{name}_ftth.csv"
    if os.path.exists(out):
        continue  # already created: avoids repeating the long read
    parts = []
    for chunk in pd.read_csv(RAW + rf"\curr_{name}.csv", usecols=cols,
                             parse_dates=["dtime"], chunksize=2_000_000):
        parts.append(chunk[chunk["unit_id"].isin(ids)])  # keeps only FTTH units
    pd.concat(parts).to_csv(out, index=False)

# --- Stage 2: latency analysis ---
lat = pd.read_csv(INTERIM + r"\udplatency_ftth.csv", parse_dates=["dtime"])
lat = lat.merge(units[["unit_id", "State", "timezone_offset_dst"]], on="unit_id")

lat["h_utc"] = lat["dtime"].dt.hour
# Local hour = UTC + offset in hours (DST applies to the whole period)
lat["h_dst"] = (lat["dtime"] + pd.to_timedelta(lat["timezone_offset_dst"], unit="h")).dt.hour

# A) Tests per hour: is there a trough in the local evening under either convention?
print(pd.DataFrame({"utc": lat["h_utc"].value_counts().sort_index(),
                    "dst": lat["h_dst"].value_counts().sort_index()}))

# B) Servers per unit and median RTT by state (possible geographic bias)
print("\nTargets por unidad:\n", lat.groupby("unit_id")["target"].nunique().value_counts().sort_index())
unit_med = lat.groupby(["unit_id", "State"])["rtt_avg"].median().div(1000).reset_index(name="rtt_med_ms")
print("\nRTT mediano por unidad (ms):\n", unit_med["rtt_med_ms"].describe().round(1))
print(unit_med.groupby("State")["rtt_med_ms"].agg(["count", "median", "max"]).round(1))

# C) Records in the peak window [19, 23) per unit: basis for defining N_MIN
peak = lat[(lat["h_dst"] >= 19) & (lat["h_dst"] < 23)]
# reindex: units without peak records count 0 (a real count, not an invented metric)
n_peak = peak.groupby("unit_id").size().reindex(units["unit_id"], fill_value=0)
print("\nn_peak (periodo completo):\n", n_peak.describe().round(1))
print("Unidades con n_peak < 30 / 50 / 100:", [int((n_peak < k).sum()) for k in (30, 50, 100)])

# D) Same count with September only, to support the date range decision
n_sep = peak[peak["dtime"].dt.month == 9].groupby("unit_id").size()
n_sep = n_sep.reindex(units["unit_id"], fill_value=0)
print("\nn_peak (solo septiembre):\n", n_sep.describe().round(1))



'''
OUTPUT:

    utc   dst
0   7165  7206
1   7144  7223
2   7172  7275
3   7200  7326
4   7182  7258
5   7247  7275
6   7323  7192
7   7352  7068
8   7228  7121
9   7285  7200
10  7205  7120
11  7099  7041
12  7147  7081
13  7232  7016
14  7079  7059
15  6979  7051
16  7015  7308
17  7054  7494
18  7057  7391
19  7083  7311
20  7356  7175
21  7501  7175
22  7398  7207
23  7297  7227

Targets por unidad:
 target
1     68
2    131
3     45
4     14
Name: count, dtype: int64

RTT mediano por unidad (ms):
 count    258.0
mean      10.5
std        3.6
min        2.5
25%        8.2
50%       11.2
75%       13.8
max       17.2
Name: rtt_med_ms, dtype: float64
       count  median   max
State                     
AL         1     3.9   3.9
CA        18     4.4   9.6
CT         2    10.4  11.0
DE         1    14.6  14.6
FL        20    10.4  14.1
IN         2     8.3   9.7
KY        14    13.3  14.7
MA        11    11.4  16.6
MD        11     7.9  15.6
NJ         8    10.0  16.0
NY        11     7.6  14.6
OH       106    13.6  16.8
PA        13    10.3  17.2
RI         2    10.4  11.3
TX        19     4.1  10.8
VA        19     8.1  13.0

n_peak (periodo completo):
 count    258.0
mean     111.9
std       20.8
min        0.0
25%      113.0
50%      120.0
75%      122.0
max      133.0
dtype: float64
Unidades con n_peak < 30 / 50 / 100: [3, 8, 44]

n_peak (solo septiembre):
 count    258.0
mean      29.6
std        7.2
min        0.0
25%       31.0
50%       32.0
75%       32.0
max       40.0
dtype: float64
'''