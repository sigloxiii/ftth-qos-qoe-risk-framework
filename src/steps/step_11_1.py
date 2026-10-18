import pandas as pd
c = pd.read_csv(r"D:\Capstone FTTH\data\interim\pipeline_udplatency_ftth.csv", dtype={"dtime": str}, parse_dates=["dtime"])
c = c[c["unit_id"].isin([24733221, 24840041])]
c = c[(c["dtime"].dt.hour >= 19) & (c["dtime"].dt.hour < 23)]
c = c[c["dtime"] >= "2022-09-12"]
prim = c.groupby(["unit_id", "target"]).size().reset_index(name="n").sort_values(["unit_id", "n", "target"], ascending=[True, False, True]).drop_duplicates("unit_id")
c = c.merge(prim[["unit_id", "target"]], on=["unit_id", "target"])
c["ms"] = c["rtt_avg"] / 1000
a = c[c["ms"] > 20].groupby(["unit_id", c["dtime"].dt.date]).size()
print(a[a == a.groupby("unit_id").transform("max")])  # días empatados en el máximo