# step_0.py
# Objective: Initial data inspection of the raw FCC MBA files, restricted to the
#            258 FTTH units (Step 0 in docs/metrics_spec.md, section 2).
#            - Coverage: units with data, row counts, date range, rows per month
#            - Distinct test servers (target) and rows per unit
#            - Check 4: mean rtt_avg by hour under UTC, standard offset and DST offset
# Inputs:    data/fiber_units.csv
#            data/raw/validated-data-sept2022/curr_udplatency.csv, curr_udpjitter.csv, curr_udpcloss.csv
# Outputs:   Console only (results are documented in docs/data_inspection.md)


import pandas as pd

RAW = r"D:\Capstone FTTH\data\raw\validated-data-sept2022"
REF = r"D:\Capstone FTTH\data\fiber_units.csv"

# FTTH population (258 units); utf-8-sig because the file starts with a BOM
units = pd.read_csv(REF, encoding="utf-8-sig").rename(columns={"Unit ID": "unit_id"})
ids = set(units["unit_id"])
print("Unidades en fiber_units.csv:", len(ids))

def ftth_chunks(name, cols):
    # Reads 2M rows at a time and keeps only the FTTH units
    for ch in pd.read_csv(rf"{RAW}\{name}.csv", usecols=cols,
                          parse_dates=["dtime"], chunksize=2_000_000):
        yield ch[ch["unit_id"].isin(ids)]

latency = None
for name, cols in [
    ("curr_udplatency", ["unit_id", "dtime", "target", "rtt_avg", "successes", "failures"]),
    ("curr_udpjitter",  ["unit_id", "dtime", "target", "jitter_up", "jitter_down"]),
    ("curr_udpcloss",   ["unit_id", "dtime", "target", "duration", "packets"]),
]:
    df = pd.concat(ftth_chunks(name, cols))
    print(f"\n=== {name} ===")
    print("Filas FTTH:", len(df), "| Unidades con datos:", df["unit_id"].nunique(), "/ 258")
    print("dtime min/max:", df["dtime"].min(), df["dtime"].max())
    print("Filas por mes:\n", df["dtime"].dt.to_period("M").value_counts().sort_index())
    print("Targets distintos:\n", df["target"].value_counts().head(10))
    print("Filas por unidad:\n", df.groupby("unit_id").size().describe())
    if name == "curr_udplatency":
        latency = df  # kept for the time zone check

# Check 4: mean rtt_avg (ms) by hour under UTC, standard offset and DST offset (September only)
lat = latency.merge(units[["unit_id", "timezone_offset", "timezone_offset_dst"]], on="unit_id")
lat = lat[lat["dtime"].dt.month == 9]
lat["h_utc"] = lat["dtime"].dt.hour
lat["h_std"] = (lat["dtime"] + pd.to_timedelta(lat["timezone_offset"], unit="h")).dt.hour
lat["h_dst"] = (lat["dtime"] + pd.to_timedelta(lat["timezone_offset_dst"], unit="h")).dt.hour
by_hour = pd.DataFrame({c: lat.groupby(c)["rtt_avg"].mean() / 1000
                        for c in ["h_utc", "h_std", "h_dst"]}).round(2)
print("\nrtt_avg medio (ms) por hora:\n", by_hour)
print("timezone_offset_dst distintos:", units["timezone_offset_dst"].value_counts().to_dict())


'''
OUTPUT:
Unidades en fiber_units.csv: 258

=== curr_udplatency ===
Filas FTTH: 172800 | Unidades con datos: 258 / 258
dtime min/max: 2022-09-12 00:00:05 2022-10-31 23:59:58
Filas por mes:
 dtime
2022-09     46205
2022-10    126595
Freq: M, Name: count, dtype: int64
Targets distintos:
 target
sp2-vm-chicago-us.samknows.com       32074
sp1-vm-chicago-us.samknows.com       26931
sp1-vm-ashburn-us.samknows.com       26760
sp1-vm-atlanta-us.samknows.com       17494
sp2-vm-newyork-us.samknows.com       15570
sp1-vm-miami-us.samknows.com         14400
sp1-vm-newyork-us.samknows.com       14237
sp1-vm-dallas-us.samknows.com        13306
sp1-vm-losangeles-us.samknows.com    11737
sp1-vm-sanjose-us.samknows.com         147
Name: count, dtype: int64
Filas por unidad:
 count    258.000000
mean     669.767442
std      122.212611
min        7.000000
25%      674.000000
50%      722.000000
75%      733.000000
max      769.000000
dtype: float64

=== curr_udpjitter ===
Filas FTTH: 152730 | Unidades con datos: 258 / 258
dtime min/max: 2022-09-12 00:00:16 2022-10-31 23:59:42
Filas por mes:
 dtime
2022-09     40862
2022-10    111868
Freq: M, Name: count, dtype: int64
Targets distintos:
 target
sp2-vm-chicago-us.samknows.com       31154
sp1-vm-ashburn-us.samknows.com       24750
sp1-vm-chicago-us.samknows.com       22915
sp1-vm-atlanta-us.samknows.com       13452
sp1-vm-newyork-us.samknows.com       13238
sp2-vm-newyork-us.samknows.com       12989
sp1-vm-miami-us.samknows.com         12236
sp1-vm-dallas-us.samknows.com        11033
sp1-vm-losangeles-us.samknows.com    10767
sp2-vm-ashburn-us.samknows.com         143
Name: count, dtype: int64
Filas por unidad:
 count    258.000000
mean     591.976744
std      140.405996
min       35.000000
25%      557.250000
50%      642.500000
75%      694.500000
max      720.000000
dtype: float64

=== curr_udpcloss ===
Filas FTTH: 4919 | Unidades con datos: 242 / 258
dtime min/max: 2022-09-12 00:10:17 2022-10-31 23:49:37
Filas por mes:
 dtime
2022-09    1265
2022-10    3654
Freq: M, Name: count, dtype: int64
Targets distintos:
 target
samk01.lsan.ca.frontiernet.net       762
newyorkfcc.west.verizon.net          610
sp1-vm-miami-us.samknows.com         537
sp1-vm-losangeles-us.samknows.com    520
sp2-vm-newyork-us.samknows.com       453
sp2-vm-chicago-us.samknows.com       388
restonfcc.west.verizon.net           321
sp1-vm-newyork-us.samknows.com       234
sp1-vm-chicago-us.samknows.com       213
samk01.asbn.va.frontiernet.net       205
Name: count, dtype: int64
Filas por unidad:
 count    242.000000
mean      20.326446
std       69.398339
min        1.000000
25%        2.000000
50%        6.000000
75%       13.000000
max      874.000000
dtype: float64

rtt_avg medio (ms) por hora:
     h_utc  h_std  h_dst
0   11.34  11.17  11.14
1   11.27  11.21  11.17
2   11.27  11.10  11.21
3   11.26  11.16  11.10
4   11.23  11.23  11.16
5   11.15  11.22  11.23
6   11.10  11.16  11.22
7   11.01  11.15  11.16
8   11.12  11.14  11.15
9   11.19  11.14  11.14
10  11.19  11.05  11.14
11  11.12  11.02  11.05
12  11.13  11.22  11.02
13  11.11  11.22  11.22
14  11.13  11.27  11.22
15  11.01  11.34  11.27
16  10.99  11.36  11.34
17  11.17  11.27  11.36
18  11.21  11.20  11.27
19  11.27  11.25  11.20
20  11.33  11.19  11.25
21  11.40  11.16  11.19
22  11.30  11.18  11.16
23  11.27  11.14  11.18
timezone_offset_dst distintos: {-4: 220, -5: 20, -7: 18}
'''