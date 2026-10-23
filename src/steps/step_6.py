# step_6.py
# Objective: Repeat the time-convention sensitivity check of step_3.py applying the
#            primary-server rule (config.yaml, server_rule). step_3.py mixed test servers,
#            which confounds the effect of the time window with the effect of distant servers.
#            Variants: A) spec (dtime + timezone_offset_dst, window [19, 23)),
#                      B) dtime read as local time (window [19, 23)),
#                      C) all hours.
#            In each variant the primary server is the one with the most records in that
#            variant's window. Reports how many units change risk_flag and lists them.
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

# Hour under each convention
for df in (lat, jit):
    df["h_spec"] = (df["dtime"] + pd.to_timedelta(df["timezone_offset_dst"], unit="h")).dt.hour
    df["h_alt"] = df["dtime"].dt.hour  # dtime taken as local time

def primary_only(df):
    # Keeps only the records of the server with the most records in the unit
    cnt = df.groupby(["unit_id", "target"]).size().reset_index(name="n")
    # Reproducible tie-break: most records first; if tied, alphabetical name
    main = cnt.sort_values(["n", "target"], ascending=[False, True]).drop_duplicates("unit_id")
    return df.merge(main[["unit_id", "target"]], on=["unit_id", "target"])

def metrics(hour_col):
    # hour_col=None uses all hours
    l, j = lat, jit
    if hour_col:
        l = lat[(lat[hour_col] >= 19) & (lat[hour_col] < 23)]
        j = jit[(jit[hour_col] >= 19) & (jit[hour_col] < 23)]
    l, j = primary_only(l), primary_only(j)
    g = l.groupby("unit_id")
    out = pd.DataFrame({
        "p95_lat": g["rtt_ms"].quantile(0.95),
        "p95_jit": j.groupby("unit_id")["jitter_ms"].quantile(0.95),
        "loss": g["failures"].sum() / g["total"].sum() * 100,  # ratio of sums
    }).reindex(units["unit_id"])
    # A NaN does not exceed any threshold: a unit without data is not flagged (nor filled with 0)
    out["risk"] = ((out["p95_lat"] > T_LAT) | (out["p95_jit"] > T_JIT) | (out["loss"] > T_LOSS)).astype(int)
    return out

A, B, C = metrics("h_spec"), metrics("h_alt"), metrics(None)
print("Unidades con risk_flag = 1 -> spec:", A["risk"].sum(),
      "| dtime como local:", B["risk"].sum(), "| todas las horas:", C["risk"].sum())

for name, X in [("B (dtime como hora local)", B), ("C (todas las horas)", C)]:
    changed = A.index[A["risk"] != X["risk"]]
    print(f"\nVariante {name} vs spec: {len(changed)} unidades cambian de risk_flag")
    if len(changed) > 0:
        # Metrics of the units that change, side by side
        print(pd.concat([A.loc[changed], X.loc[changed]], axis=1, keys=["spec", "variante"]).round(2))
    print("  Diferencia máxima P95 latencia (ms):", round((A["p95_lat"] - X["p95_lat"]).abs().max(), 2))
    print("  Diferencia máxima P95 jitter (ms):", round((A["p95_jit"] - X["p95_jit"]).abs().max(), 2))
    print("  Diferencia máxima pérdida (pp):", round((A["loss"] - X["loss"]).abs().max(), 3))

'''
Unidades con risk_flag = 1 -> spec: 6 | dtime como local: 10 | todas las horas: 8

Variante B (dtime como hora local) vs spec: 6 unidades cambian de risk_flag
            spec                    variante                   
         p95_lat p95_jit  loss risk  p95_lat p95_jit  loss risk
unit_id                                                        
943226     19.87    0.59  0.00    0    23.13    0.45  0.00    1
1006958    22.36    1.36  0.08    1    17.96    1.59  0.03    0
3798765    13.08    3.67  0.00    0    13.20    5.67  0.02    1
4190285    14.71    2.69  0.01    0    50.00    4.48  0.05    1
24840041    3.86    0.73  0.01    0    35.80    3.89  1.66    1
25314149   15.42    0.66  0.02    0    15.29    5.06  0.05    1
  Diferencia máxima P95 latencia (ms): 35.29
  Diferencia máxima P95 jitter (ms): 4.41
  Diferencia máxima pérdida (pp): 1.651

Variante C (todas las horas) vs spec: 2 unidades cambian de risk_flag
            spec                    variante                   
         p95_lat p95_jit  loss risk  p95_lat p95_jit  loss risk
unit_id                                                        
943226     19.87    0.59  0.00    0    22.85    0.48  0.00    1
24840041    3.86    0.73  0.01    0    34.15    4.68  0.35    1
  Diferencia máxima P95 latencia (ms): 30.3
  Diferencia máxima P95 jitter (ms): 3.95
  Diferencia máxima pérdida (pp): 0.337
'''