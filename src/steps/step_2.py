# step_2.py
# Objective: Complete Step 0 by quantifying two risks for the peak-window metrics.
#            1. Test-server mixing: how much the median RTT differs between the servers
#               (targets) used by the same unit (P95 could reflect the server, not the network)
#            2. Data validity: count of records that break the quality rules in
#               docs/metrics_spec.md, section 5 (these will be excluded, never corrected)
# Inputs:    data/interim/udplatency_ftth.csv, udpjitter_ftth.csv (created by step_1.py)
#            data/fiber_units.csv
# Outputs:   Console diagnostics (results are documented in docs/data_inspection.md)

import pandas as pd

BASE = r"D:\Capstone FTTH"
INTERIM = BASE + r"\data\interim"

units = pd.read_csv(BASE + r"\data\fiber_units.csv", encoding="utf-8-sig")
units = units.rename(columns={"Unit ID": "unit_id"})
lat = pd.read_csv(INTERIM + r"\udplatency_ftth.csv", parse_dates=["dtime"])
jit = pd.read_csv(INTERIM + r"\udpjitter_ftth.csv", parse_dates=["dtime"])

# Local hour = UTC + DST offset (same criterion as step_1.py)
lat = lat.merge(units[["unit_id", "timezone_offset_dst"]], on="unit_id")
lat["h_local"] = (lat["dtime"] + pd.to_timedelta(lat["timezone_offset_dst"], unit="h")).dt.hour
peak = lat[(lat["h_local"] >= 19) & (lat["h_local"] < 23)]  # ventana pico [19, 23)

# --- A) Server mixing within each unit (peak window only) ---
# Median RTT (ms) and number of records of each unit-server pair
pair = peak.groupby(["unit_id", "target"])["rtt_avg"].agg(["median", "count"])
pair["median"] = pair["median"] / 1000  # µs -> ms

# Difference between the server with the highest median RTT and the lowest of the same unit
g = pair.groupby("unit_id")["median"]
spread = g.max() - g.min()
print("Diferencia de RTT mediano entre servidores de una misma unidad (ms):")
print(spread.describe().round(1))
print("Unidades con diferencia > 2 ms / > 5 ms:", int((spread > 2).sum()), int((spread > 5).sum()))

# Share of each unit's records that comes from its primary server
c = pair.groupby("unit_id")["count"]
main_share = c.max() / c.sum() * 100
print("\n% de registros del servidor principal por unidad:")
print(main_share.describe().round(1))

# --- B) Invalid records per the spec, section 5 (full period) ---
total = lat["successes"] + lat["failures"]
loss = lat["failures"] / total * 100  # if total <= 0 the result is not valid
print("\n--- Latencia: registros inválidos ---")
print("successes + failures <= 0:", int((total <= 0).sum()))
print("loss_pct fuera de [0, 100] (con total > 0):",
      int((((loss < 0) | (loss > 100)) & (total > 0)).sum()))
print("rtt_avg nulo / negativo:", int(lat["rtt_avg"].isna().sum()), int((lat["rtt_avg"] < 0).sum()))
print("Duplicados (unit_id, dtime, target):",
      int(lat.duplicated(["unit_id", "dtime", "target"]).sum()))

# Global loss as ratio of sums (same formula as the spec) and loss frequency
print("Pérdida global (%):", round(lat["failures"].sum() / total.sum() * 100, 3))
print("Registros con failures > 0 (%):", round((lat["failures"] > 0).mean() * 100, 1))

print("\n--- Jitter: registros inválidos ---")
for col in ["jitter_up", "jitter_down"]:
    print(col, "nulo / negativo:", int(jit[col].isna().sum()), int((jit[col] < 0).sum()))


'''
OUTPUT:

count    257.0
mean      78.1
std       19.6
min       37.8
25%       62.0
50%       77.7
75%      100.0
max      100.0
Name: count, dtype: float64

--- Latencia: registros inválidos ---
successes + failures <= 0: 0
loss_pct fuera de [0, 100] (con total > 0): 0
rtt_avg nulo / negativo: 0 0
Duplicados (unit_id, dtime, target): 9
Pérdida global (%): 0.022
Registros con failures > 0 (%): 8.1

--- Jitter: registros inválidos ---
jitter_up nulo / negativo: 0 0
jitter_down nulo / negativo: 0 0
'''