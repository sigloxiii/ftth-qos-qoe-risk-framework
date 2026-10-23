# step_9.py
# Objective: Compute the BASE CASE of methodology v3 and fill the sensitivity matrix with one
#            consistent set of rules (docs/metrics_spec.md, sections 3 to 7). Steps 3 to 6 mixed
#            conventions and never applied N_MIN, so their counts (10 / 6 / 17 / 22 flagged,
#            8 / 19 units below N_MIN) are not comparable with each other.
#            Rules applied in every variant:
#            - Period 2022-09-12 to 2022-10-31 (D-01); peak window local hour [19, 23)
#            - Duplicates: keep one if identical, drop all if conflicting (D-05)
#            - Invalid records excluded and counted; no capping, no fillna(0)
#            - Server rule primary_only (D-04): ONE server per unit, the primary server of the
#              LATENCY file (most peak records, ties alphabetical), used for latency, loss and jitter
#            - N_MIN = 50 peak records of the latency file, counted AFTER the server rule (D-02)
#            - Risk flag = latency OR jitter OR loss above the base thresholds (strictly greater)
#            Variants (2 x 2): time reading {local = base case (D-03), UTC = dtime + offset_dst}
#                              x server rule {primary_only = base case (D-04), all_servers}
#            Diagnostics (do not change the base case):
#            1. Distribution of successes + failures per row (dictionary check 6)
#            2. Distribution of loss_pct and p95_jitter per unit (review of the sensitivity grid)
#            3. Units flagged only by jitter
#            4. Jitter with its own primary server (alternative discarded for the base case)
#            5. Peak jitter records per analyzed unit
#            6. Variant: jitter evaluated only with at least N_MIN jitter records
#            7. Sensitivity of the result to N_MIN (30 / 50 / 100)
#            8. Most repeated rtt_avg values of units with severe latency
# Inputs:    data/fiber_units.csv
#            data/interim/udplatency_ftth.csv, udpjitter_ftth.csv (created by step_1.py)
# Outputs:   Console only (paste the result in the OUTPUT docstring at the end of this file)

import pandas as pd

BASE = r"D:\Capstone FTTH"
INTERIM = BASE + r"\data\interim"

# Parameters (mirror of config.yaml); pipeline.py reads them from there
START, END = "2022-09-12", "2022-10-31"
PEAK_START, PEAK_END = 19, 23            # local hour, [19, 23)
N_MIN = 50
T_LAT, T_JIT, T_LOSS = 20, 5, 1.0        # base thresholds
S_LAT, S_JIT, S_LOSS = 50, 15, 10        # severe thresholds
KEY = ["unit_id", "dtime", "target"]

units = pd.read_csv(BASE + r"\data\fiber_units.csv", encoding="utf-8-sig")
units = units.rename(columns={"Unit ID": "unit_id"})
off = units[["unit_id", "timezone_offset_dst"]]
ids = units["unit_id"]

lat = pd.read_csv(INTERIM + r"\udplatency_ftth.csv", parse_dates=["dtime"])
jit = pd.read_csv(INTERIM + r"\udpjitter_ftth.csv", parse_dates=["dtime"])

# --- Data quality: period, duplicates and invalid records (excluded and counted) ---
def prep(df, name, invalid):
    n0 = len(df)
    d = df["dtime"].dt.normalize()  # fails if dtime could not be parsed as a date
    df = df[(d >= START) & (d <= END)]
    n_period = n0 - len(df)
    n1 = len(df)
    df = df.drop_duplicates()                      # exact copies: keep one
    n_exact = n1 - len(df)
    conflict = df.duplicated(KEY, keep=False)      # repeated key with different values
    n_conflict = int(conflict.sum())
    df = df[~conflict]                             # conflicting: drop all
    bad = invalid(df)
    n_bad = int(bad.sum())
    df = df[~bad]
    print(f"{name}: filas {n0} | fuera de periodo {n_period} | copias exactas eliminadas {n_exact} "
          f"| filas en conflicto descartadas {n_conflict} | inválidas {n_bad} | usadas {len(df)}")
    return df.merge(off, on="unit_id")

lat = prep(lat, "latencia", lambda d: (~(d["failures"] / (d["successes"] + d["failures"]) * 100).between(0, 100))
          | d["rtt_avg"].isna() | (d["rtt_avg"] < 0))
jit = prep(jit, "jitter", lambda d: d["jitter_up"].isna() | d["jitter_down"].isna()
          | (d["jitter_up"] < 0) | (d["jitter_down"] < 0))

lat["rtt_ms"] = lat["rtt_avg"] / 1000
lat["total"] = lat["successes"] + lat["failures"]
jit["jitter_ms"] = (jit["jitter_up"] + jit["jitter_down"]) / 2 / 1000

# --- Rules ---
def hour_local(df):
    return df["dtime"].dt.hour  # D-03: dtime is already local time

def hour_utc(df):
    # UTC reading (sensitivity): local hour = dtime + timezone_offset_dst
    return (df["dtime"] + pd.to_timedelta(df["timezone_offset_dst"], unit="h")).dt.hour

def peak(df, hour_fn):
    h = hour_fn(df)
    return df[(h >= PEAK_START) & (h < PEAK_END)]

def primary_targets(df):
    # Server with the most peak records per unit; alphabetical tie-break (reproducible)
    cnt = df.groupby(["unit_id", "target"]).size().reset_index(name="n")
    cnt = cnt.sort_values(["unit_id", "n", "target"], ascending=[True, False, True])
    return cnt.drop_duplicates("unit_id")[["unit_id", "target"]]

def run(hour_fn, mode, jitter_server="latency", n_min=N_MIN, jit_min=0):
    # jitter_server: "latency" = base case (one server per unit); "own" = primary server of the jitter file
    # jit_min: minimum jitter records to evaluate jitter (0 = no minimum)
    l, j = peak(lat, hour_fn), peak(jit, hour_fn)
    if mode == "primary_only":
        main_l = primary_targets(l)
        l = l.merge(main_l, on=["unit_id", "target"])
        main_j = main_l if jitter_server == "latency" else primary_targets(j)
        j = j.merge(main_j, on=["unit_id", "target"])
    g = l.groupby("unit_id")
    out = pd.DataFrame({
        "p95_lat": g["rtt_ms"].quantile(0.95),
        "p95_jit": j.groupby("unit_id")["jitter_ms"].quantile(0.95),
        "loss": g["failures"].sum() / g["total"].sum() * 100,  # ratio of sums
    }).reindex(ids)
    # Counts: a unit without peak records has 0 (a real count, not an invented metric)
    out["n_peak"] = g.size().reindex(ids, fill_value=0)
    out["n_peak_jit"] = j.groupby("unit_id").size().reindex(ids, fill_value=0)
    out["scored"] = out["n_peak"] >= n_min  # D-02: the others are reported separately and not scored
    jit_ok = out["n_peak_jit"] >= jit_min
    # A NaN does not exceed any threshold: it is not filled with 0
    out["flag_lat"] = ((out["p95_lat"] > T_LAT) & out["scored"]).astype(int)
    out["flag_jit"] = ((out["p95_jit"] > T_JIT) & out["scored"] & jit_ok).astype(int)
    out["flag_loss"] = ((out["loss"] > T_LOSS) & out["scored"]).astype(int)
    out["risk"] = (out[["flag_lat", "flag_jit", "flag_loss"]].sum(axis=1) > 0).astype(int)
    out["severe"] = (((out["p95_lat"] > S_LAT) | (out["p95_jit"] > S_JIT) | (out["loss"] > S_LOSS))
                     & out["scored"]).astype(int)
    return out

def line(label, o):
    print(f"{label}: {int(o['scored'].sum())} / {int((~o['scored']).sum())} / {int(o['risk'].sum())}"
          f"   (latencia {int(o['flag_lat'].sum())}, jitter {int(o['flag_jit'].sum())}, "
          f"pérdida {int(o['flag_loss'].sum())}, severas {int(o['severe'].sum())})")

# --- 2 x 2 matrix ---
res = {}
for hname, hfn in [("local", hour_local), ("utc", hour_utc)]:
    for mode in ["primary_only", "all_servers"]:
        res[(hname, mode)] = run(hfn, mode)

print("\n=== Matriz de sensibilidad (N_MIN aplicado; analizadas / insuficientes / risk_flag = 1) ===")
for (hname, mode), o in res.items():
    line(f"{hname:5s} + {mode:12s}", o)

base = res[("local", "primary_only")]
sc = base[base["scored"]]
print(f"\n=== CASO BASE (local + primary_only, jitter con el primario de latencia): {len(sc)} unidades "
      f"analizadas de {len(base)}; {int(base['risk'].sum())} en riesgo ({base['risk'].sum() / len(sc) * 100:.1f} %) ===")
print("Unidades analizadas con p95_jit nulo:", int(sc["p95_jit"].isna().sum()))
print(sc[sc["risk"] == 1][["n_peak", "n_peak_jit", "p95_lat", "p95_jit", "loss",
                           "flag_lat", "flag_jit", "flag_loss", "severe"]].round(2))
print("\nUnidades insuficientes (n_peak < N_MIN), una por línea:")
print(base.loc[~base["scored"], "n_peak"].rename("n_peak").to_string())

# Units that change status between the local and UTC readings (both with primary_only)
utc_p = res[("utc", "primary_only")]
chg = base.index[(base["risk"] != utc_p["risk"]) | (base["scored"] != utc_p["scored"])]
print(f"\nUnidades que cambian de estado entre local y UTC (risk o calificación): {len(chg)}")
print(pd.concat([base.loc[chg, ["n_peak", "p95_lat", "p95_jit", "loss", "risk"]],
                 utc_p.loc[chg, ["n_peak", "p95_lat", "p95_jit", "loss", "risk"]]],
                axis=1, keys=["local", "utc"]).round(2))

# --- Diagnostics ---
print("\n=== 1. successes + failures por fila (periodo completo, latencia) ===")
print(lat["total"].describe().round(1))
print(lat["total"].quantile([0.01, 0.05, 0.5, 0.95, 0.99]).round(0).to_string())

print("\n=== 2. Distribución por unidad (caso base, unidades analizadas) ===")
print("loss_pct:\n", sc["loss"].describe().round(4))
print("Unidades con pérdida > 0.05 / 0.1 / 0.5 / 1 / 2 / 5 %:", [int((sc["loss"] > k).sum()) for k in (0.05, 0.1, 0.5, 1, 2, 5)])
print("Cuantiles de pérdida:", sc["loss"].quantile([0.5, 0.9, 0.95, 0.99]).round(3).to_dict())
print("p95_jit (ms), cuantiles:", sc["p95_jit"].quantile([0.5, 0.9, 0.95, 0.99, 1]).round(2).to_dict())
print("Unidades con p95_jit > 3 / 4 / 5 ms:", [int((sc["p95_jit"] > k).sum()) for k in (3, 4, 5)])

print("\n=== 3. Unidades marcadas SOLO por jitter (caso base) ===")
only_jit = sc[(sc["flag_jit"] == 1) & (sc["flag_lat"] == 0) & (sc["flag_loss"] == 0)]
print(only_jit[["n_peak_jit", "p95_lat", "p95_jit", "loss"]].round(2))

print("\n=== 4. Jitter con su propio primario (alternativa descartada para el caso base) ===")
own = run(hour_local, "primary_only", jitter_server="own")
l0, j0 = peak(lat, hour_local), peak(jit, hour_local)
m = primary_targets(l0).merge(primary_targets(j0), on="unit_id", how="left", suffixes=("_lat", "_jit"))
m = m[m["unit_id"].isin(sc.index)]
print("Unidades analizadas cuyo primario de jitter difiere del de latencia:", int((m["target_lat"] != m["target_jit"]).sum()))
line("local + primary_only, jitter propio ", own)
print("Unidades que cambian de risk_flag respecto al caso base:", list(sc.index[sc["risk"] != own.loc[sc.index, "risk"]]))

print("\n=== 5. Registros pico de jitter por unidad analizada (servidor primario de latencia) ===")
print(sc["n_peak_jit"].describe().round(1))
print("Unidades analizadas con < 50 registros de jitter:", int((sc["n_peak_jit"] < N_MIN).sum()))

print("\n=== 6. Variante: jitter evaluado solo con >= N_MIN registros de jitter ===")
v6 = run(hour_local, "primary_only", jit_min=N_MIN)
line("local + primary_only, jitter con mínimo", v6)
print("Unidades analizadas cuyo jitter no se evalúa:", int(((v6["scored"]) & (v6["n_peak_jit"] < N_MIN)).sum()))
print("Unidades que cambian de risk_flag respecto al caso base:", list(sc.index[sc["risk"] != v6.loc[sc.index, "risk"]]))

print("\n=== 7. Sensibilidad a N_MIN (caso base; analizadas / insuficientes / risk_flag = 1) ===")
for k in (30, 50, 100):
    o = run(hour_local, "primary_only", n_min=k)
    line(f"N_MIN = {k:3d}", o)
    print("   unidades en riesgo:", list(o.index[o["risk"] == 1]))

print("\n=== 8. Valores más repetidos de rtt_avg (µs) en unidades con latencia severa ===")
l_primary = l0.merge(primary_targets(l0), on=["unit_id", "target"])
for u in base.index[(base["severe"] == 1) & (base["p95_lat"] > S_LAT * 0.9)]:
    print(f"unit_id {u}:")
    print(l_primary.loc[l_primary["unit_id"] == u, "rtt_avg"].value_counts().head(5).to_string())

'''
OUTPUT:
latencia: filas 172800 | fuera de periodo 0 | copias exactas eliminadas 9 | filas en conflicto descartadas 0 | inválidas 0 | usadas 172791
jitter: filas 152730 | fuera de periodo 0 | copias exactas eliminadas 4 | filas en conflicto descartadas 2 | inválidas 0 | usadas 152724

=== Matriz de sensibilidad (N_MIN aplicado; analizadas / insuficientes / risk_flag = 1) ===
local + primary_only: 237 / 21 / 5   (latencia 5, jitter 0, pérdida 1, severas 1)
local + all_servers : 248 / 10 / 21   (latencia 21, jitter 0, pérdida 1, severas 1)
utc   + primary_only: 239 / 19 / 4   (latencia 4, jitter 0, pérdida 0, severas 0)
utc   + all_servers : 250 / 8 / 17   (latencia 17, jitter 0, pérdida 0, severas 1)

=== CASO BASE (local + primary_only, jitter con el primario de latencia): 237 unidades analizadas de 258; 5 en riesgo (2.1 %) ===
Unidades analizadas con p95_jit nulo: 0
          n_peak  n_peak_jit  p95_lat  p95_jit  loss  flag_lat  flag_jit  flag_loss  severe
unit_id                                                                                    
943226        53          10    23.13     0.41  0.00         1         0          0       0
4190285       66          76    50.00     4.48  0.05         1         0          0       1
24733221      59          25    23.96     1.23  0.01         1         0          0       0
24840041     131         106    35.80     3.89  1.66         1         0          1       0
25314177      62          17    30.48     1.31  0.00         1         0          0       0

Unidades insuficientes (n_peak < N_MIN), una por línea:
unit_id
925928      45
940736      45
943230      26
1000774     32
1000946     48
3551873     12
3602917     49
3799009     13
3814781     43
3892905     48
24559133    44
24807209    49
25170393    38
25170473    45
25314149    48
25658017    24
25755241    45
26114189    43
37476529    36
55458489     2
55518553    40

Unidades que cambian de estado entre local y UTC (risk o calificación): 12
          local                               utc                           
         n_peak p95_lat p95_jit  loss risk n_peak p95_lat p95_jit  loss risk
unit_id                                                                     
925928       45   15.91    1.09  0.01    0     74   16.02    1.11  0.00    0
942200       52    8.43    3.22  0.01    0     47    8.29    2.58  0.13    0
943226       53   23.13    0.41  0.00    1     56   19.87    0.77  0.00    0
1000161      58    9.94    1.62  0.00    0     48    9.95    1.60  0.02    0
1006958      51   17.96    0.83  0.03    0     51   22.36    1.36  0.08    1
3799009      13    9.50    0.72  0.00    0     55   10.69    0.76  0.00    0
3814781      43   14.97    0.46  0.01    0     89   14.89    0.41  0.00    0
3892905      48   23.04    0.17  0.01    0     71   21.63    0.19  0.01    1
4190285      66   50.00    4.48  0.05    1     63   14.71    2.69  0.01    0
24559133     44   13.70    0.42  0.02    0     50   13.68    0.46  0.01    0
24840041    131   35.80    3.89  1.66    1    121    3.86    0.73  0.01    0
55105449     54   14.45    0.69  0.01    0     48   14.42    0.68  0.00    0

=== 1. successes + failures por fila (periodo completo, latencia) ===
count    172791.0
mean       1736.6
std         668.0
min          50.0
25%        1408.0
50%        2065.0
75%        2235.0
max        2401.0
Name: total, dtype: float64
0.01      65.0
0.05     231.0
0.50    2065.0
0.95    2303.0
0.99    2356.0

=== 2. Distribución por unidad (caso base, unidades analizadas) ===
loss_pct:
 count    237.0000
mean       0.0289
std        0.1272
min        0.0000
25%        0.0016
50%        0.0072
75%        0.0165
max        1.6617
Name: loss, dtype: float64
Unidades con pérdida > 0.05 / 0.1 / 0.5 / 1 / 2 / 5 %: [18, 10, 2, 1, 0, 0]
Cuantiles de pérdida: {0.5: 0.007, 0.9: 0.04, 0.95: 0.072, 0.99: 0.433}
p95_jit (ms), cuantiles: {0.5: 1.0, 0.9: 2.74, 0.95: 2.96, 0.99: 3.97, 1.0: 4.48}
Unidades con p95_jit > 3 / 4 / 5 ms: [10, 3, 0]

=== 3. Unidades marcadas SOLO por jitter (caso base) ===
Empty DataFrame
Columns: [n_peak_jit, p95_lat, p95_jit, loss]
Index: []

=== 4. Jitter con su propio primario (alternativa descartada para el caso base) ===
Unidades analizadas cuyo primario de jitter difiere del de latencia: 68
local + primary_only, jitter propio : 237 / 21 / 6   (latencia 5, jitter 1, pérdida 1, severas 1)
Unidades que cambian de risk_flag respecto al caso base: [3798765]

=== 5. Registros pico de jitter por unidad analizada (servidor primario de latencia) ===
count    237.0
mean      62.6
std       30.9
min       10.0
25%       39.0
50%       56.0
75%       85.0
max      120.0
Name: n_peak_jit, dtype: float64
Unidades analizadas con < 50 registros de jitter: 93

=== 6. Variante: jitter evaluado solo con >= N_MIN registros de jitter ===
local + primary_only, jitter con mínimo: 237 / 21 / 5   (latencia 5, jitter 0, pérdida 1, severas 1)
Unidades analizadas cuyo jitter no se evalúa: 93
Unidades que cambian de risk_flag respecto al caso base: []

=== 7. Sensibilidad a N_MIN (caso base; analizadas / insuficientes / risk_flag = 1) ===
N_MIN =  30: 253 / 5 / 7   (latencia 7, jitter 0, pérdida 1, severas 1)
   unidades en riesgo: [943226, 3892905, 4190285, 24733221, 24840041, 25314177, 25755241]
N_MIN =  50: 237 / 21 / 5   (latencia 5, jitter 0, pérdida 1, severas 1)
   unidades en riesgo: [943226, 4190285, 24733221, 24840041, 25314177]
N_MIN = 100: 89 / 169 / 1   (latencia 1, jitter 0, pérdida 1, severas 0)
   unidades en riesgo: [24840041]

=== 8. Valores más repetidos de rtt_avg (µs) en unidades con latencia severa ===
unit_id 4190285:
rtt_avg
14070    2
14135    2
14774    2
14150    2
13980    1
'''