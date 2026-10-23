# step_5.py
# Objective: Measure how much test-server mixing within a unit affects risk_flag
#            (docs/data_dictionary.md, check 5; findings in step_2.py).
#            Compare two variants of the unit metrics in the peak window:
#            A) All records of the unit (base case in docs/metrics_spec.md)
#            B) Only records from the unit's primary server (the one with the most peak records)
#            Count how many units change risk_flag, how many records B discards, and list the
#            units with the largest RTT difference between servers.
# Inputs:    data/interim/udplatency_ftth.csv, udpjitter_ftth.csv (created by step_1.py)
#            data/fiber_units.csv
# Outputs:   Console only (results are documented in docs/data_inspection.md)

import pandas as pd

BASE = r"D:\Capstone FTTH"
INTERIM = BASE + r"\data\interim"
T_LAT, T_JIT, T_LOSS = 20, 5, 1.0  # base thresholds of the spec

units = pd.read_csv(BASE + r"\data\fiber_units.csv", encoding="utf-8-sig")
units = units.rename(columns={"Unit ID": "unit_id"})
off = units[["unit_id", "timezone_offset_dst"]]

lat = pd.read_csv(INTERIM + r"\udplatency_ftth.csv", parse_dates=["dtime"]).merge(off, on="unit_id")
jit = pd.read_csv(INTERIM + r"\udpjitter_ftth.csv", parse_dates=["dtime"]).merge(off, on="unit_id")

lat["rtt_ms"] = lat["rtt_avg"] / 1000
lat["total"] = lat["successes"] + lat["failures"]
jit["jitter_ms"] = (jit["jitter_up"] + jit["jitter_down"]) / 2 / 1000

def in_peak(df):
    # Peak window [19, 23) with local hour = UTC + DST offset
    hour = (df["dtime"] + pd.to_timedelta(df["timezone_offset_dst"], unit="h")).dt.hour
    return df[(hour >= 19) & (hour < 23)]

lat, jit = in_peak(lat), in_peak(jit)

def primary_only(df):
    # Keeps only the records of the server with the most peak records in each unit
    cnt = df.groupby(["unit_id", "target"]).size().reset_index(name="n")
    main = cnt.sort_values("n", ascending=False).drop_duplicates("unit_id")[["unit_id", "target"]]
    return df.merge(main, on=["unit_id", "target"])

def metrics(l, j):
    g = l.groupby("unit_id")
    out = pd.DataFrame({
        "p95_lat": g["rtt_ms"].quantile(0.95),
        "p95_jit": j.groupby("unit_id")["jitter_ms"].quantile(0.95),
        "loss": g["failures"].sum() / g["total"].sum() * 100,  # ratio of sums
    }).reindex(units["unit_id"])
    # A NaN does not exceed any threshold: a unit without data is not flagged (nor filled with 0)
    out["risk"] = ((out["p95_lat"] > T_LAT) | (out["p95_jit"] > T_JIT) | (out["loss"] > T_LOSS)).astype(int)
    return out

lat_b, jit_b = primary_only(lat), primary_only(jit)
A = metrics(lat, jit)
B = metrics(lat_b, jit_b)

print("Registros pico de latencia: A =", len(lat), "| B =", len(lat_b),
      "| conservados:", round(len(lat_b) / len(lat) * 100, 1), "%")
print("Unidades con < 50 registros pico (N_MIN): A =",
      int((lat.groupby("unit_id").size() < 50).sum()),
      "| B =", int((lat_b.groupby("unit_id").size() < 50).sum()))
print("\nUnidades con risk_flag = 1: A =", A["risk"].sum(), "| B =", B["risk"].sum())
print("Unidades que cambian de risk_flag:", int((A["risk"] != B["risk"]).sum()))

d = (A["p95_lat"] - B["p95_lat"]).abs()
print("Diferencia en P95 de latencia A vs B (ms):\n", d.describe().round(2))
print("Unidades con diferencia > 1 ms / > 3 ms:", int((d > 1).sum()), int((d > 3).sum()))

# The 5 units with the largest median RTT difference between servers
pair = lat.groupby(["unit_id", "target"])["rtt_ms"].agg(["median", "count"])
g2 = pair.groupby("unit_id")["median"]
spread = (g2.max() - g2.min()).sort_values(ascending=False)
print("\nServidores de las 5 unidades con mayor diferencia (mediana en ms, registros):")
print(pair.loc[spread.head(5).index].round(1))



'''
Registros pico de latencia: A = 28868 | B = 22418 | conservados: 77.7 %
Unidades con < 50 registros pico (N_MIN): A = 7 | B = 18

Unidades con risk_flag = 1: A = 17 | B = 6
Unidades que cambian de risk_flag: 11
Diferencia en P95 de latencia A vs B (ms):
 count    257.00
mean       0.99
std        3.83
min        0.00
25%        0.00
50%        0.05
75%        0.35
max       52.87
Name: p95_lat, dtype: float64
Unidades con diferencia > 1 ms / > 3 ms: 38 22

Servidores de las 5 unidades con mayor diferencia (mediana en ms, registros):
                                            median  count
unit_id  target                                          
24559133 sp1-vm-atlanta-us.samknows.com       13.8     15
         sp1-vm-chicago-us.samknows.com       13.7     50
         sp1-vm-seattle-us.samknows.com       65.5     25
         sp2-vm-chicago-us.samknows.com       13.7     26
948646   sp1-vm-chicago-us.samknows.com       25.0     29
         sp2-vm-chicago-us.samknows.com       12.4     91
55105125 sp1-vm-losangeles-us.samknows.com     4.1     98
         sp1-vm-sanjose-us.samknows.com       13.7     24
1011922  sp1-vm-ashburn-us.samknows.com        5.3    117
         sp1-vm-newyork-us.samknows.com       13.1      3
25314177 sp1-vm-ashburn-us.samknows.com       13.6     12
         sp1-vm-newyork-us.samknows.com       14.3     59
         sp2-vm-newyork-us.samknows.com       21.3     51
'''