# step_3.py
# Objective: Sensitivity check of the time convention (docs/metrics_spec.md, section 3).
#            Compute the three metrics and risk_flag per unit under three windows:
#            A) Spec: local time = dtime + timezone_offset_dst, window [19, 23)
#            B) Alternative: dtime already local (no offset applied), window [19, 23)
#            C) Reference: all hours (no window)
#            Then count how many units change risk_flag versus A, using the base
#            thresholds of the spec (section 6).
# Inputs:    data/interim/udplatency_ftth.csv, udpjitter_ftth.csv (created by step_1.py)
#            data/fiber_units.csv
# Outputs:   Console only

import pandas as pd

BASE = r"D:\Capstone FTTH"
INTERIM = BASE + r"\data\interim"

# Base thresholds of the spec
T_LAT, T_JIT, T_LOSS = 20, 5, 1.0

units = pd.read_csv(BASE + r"\data\fiber_units.csv", encoding="utf-8-sig")
units = units.rename(columns={"Unit ID": "unit_id"})
off = units[["unit_id", "timezone_offset_dst"]]

lat = pd.read_csv(INTERIM + r"\udplatency_ftth.csv", parse_dates=["dtime"]).merge(off, on="unit_id")
jit = pd.read_csv(INTERIM + r"\udpjitter_ftth.csv", parse_dates=["dtime"]).merge(off, on="unit_id")

# Values per record: µs -> ms; jitter = average of upstream and downstream
lat["rtt_ms"] = lat["rtt_avg"] / 1000
lat["total"] = lat["successes"] + lat["failures"]
lat = lat[lat["total"] > 0]  # invalid records are excluded, not corrected (spec, section 5)
jit["jitter_ms"] = (jit["jitter_up"] + jit["jitter_down"]) / 2 / 1000

# Hour under each convention
for df in (lat, jit):
    df["h_spec"] = (df["dtime"] + pd.to_timedelta(df["timezone_offset_dst"], unit="h")).dt.hour
    df["h_alt"] = df["dtime"].dt.hour  # dtime taken as local time

def metrics(hour_col):
    # Function to avoid repeating the same calculation three times; hour_col=None uses all hours
    l, j = lat, jit
    if hour_col:
        l = lat[(lat[hour_col] >= 19) & (lat[hour_col] < 23)]
        j = jit[(jit[hour_col] >= 19) & (jit[hour_col] < 23)]
    g = l.groupby("unit_id")
    out = pd.DataFrame({
        "p95_lat": g["rtt_ms"].quantile(0.95),
        "p95_jit": j.groupby("unit_id")["jitter_ms"].quantile(0.95),
        "loss": g["failures"].sum() / g["total"].sum() * 100,  # ratio of sums
    }).reindex(units["unit_id"])  # same 258 units in the three variants
    # A NaN does not exceed any threshold: a unit without data is not flagged (nor filled with 0)
    out["risk"] = ((out["p95_lat"] > T_LAT) | (out["p95_jit"] > T_JIT) | (out["loss"] > T_LOSS)).astype(int)
    return out

A = metrics("h_spec")
B = metrics("h_alt")
C = metrics(None)

print("Unidades con risk_flag = 1 -> spec:", A["risk"].sum(),
      "| dtime como local:", B["risk"].sum(), "| todas las horas:", C["risk"].sum())

for name, X in [("B (dtime como hora local)", B), ("C (todas las horas)", C)]:
    print(f"\nVariante {name} vs spec:")
    print("  Unidades que cambian de risk_flag:", int((A["risk"] != X["risk"]).sum()))
    print("  Diferencia máxima P95 latencia (ms):", round((A["p95_lat"] - X["p95_lat"]).abs().max(), 2))
    print("  Diferencia máxima P95 jitter (ms):", round((A["p95_jit"] - X["p95_jit"]).abs().max(), 2))
    print("  Diferencia máxima pérdida (pp):", round((A["loss"] - X["loss"]).abs().max(), 3))



'''
Unidades con risk_flag = 1 -> spec: 17 | dtime como local: 22 | todas las horas: 21

Variante B (dtime como hora local) vs spec:
  Unidades que cambian de risk_flag: 5
  Diferencia máxima P95 latencia (ms): 31.95
  Diferencia máxima P95 jitter (ms): 3.16
  Diferencia máxima pérdida (pp): 1.651

Variante C (todas las horas) vs spec:
  Unidades que cambian de risk_flag: 4
  Diferencia máxima P95 latencia (ms): 30.3
  Diferencia máxima P95 jitter (ms): 3.95
  Diferencia máxima pérdida (pp): 0.337
  '''