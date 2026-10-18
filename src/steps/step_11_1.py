# step_11_1.py
# Objective: Explain why `p95_latency_without_worst_day_ms` of step_11.py (23.98 and 35.81 ms) differs
#            from pipeline.py (22.73 and 35.61 ms) for units 24733221 and 24840041 (decision D-10).
#            D-10 removes the date with the most records above the threshold; with ties, the
#            earliest date. This script lists, for both units, the dates that share the maximum
#            number of records above 20 ms. If several dates tie, step_11.py picked one of them
#            without a stated rule and pipeline.py picked the earliest, so both are correct for
#            their rule; no flag and no conclusion changes (both units stay above 20 ms).
# Inputs:    data/interim/pipeline_udplatency_ftth.csv (created by src/pipeline.py)
# Outputs:   Console only (result below and in docs/decisions.md, D-10)

import pandas as pd

UNITS = [24733221, 24840041]
T_LAT = 20  # ms, base latency threshold

c = pd.read_csv(r"D:\Capstone FTTH\data\interim\pipeline_udplatency_ftth.csv",
                dtype={"dtime": str}, parse_dates=["dtime"])
c = c[c["unit_id"].isin(UNITS)]
c = c[(c["dtime"].dt.hour >= 19) & (c["dtime"].dt.hour < 23)]  # peak window, local hour [19, 23)
c = c[c["dtime"] >= "2022-09-12"]                              # analysis period (D-01)

# Primary server: the target with the most peak records, ties alphabetical (D-04)
prim = (c.groupby(["unit_id", "target"]).size().reset_index(name="n")
          .sort_values(["unit_id", "n", "target"], ascending=[True, False, True])
          .drop_duplicates("unit_id"))
c = c.merge(prim[["unit_id", "target"]], on=["unit_id", "target"])

c["ms"] = c["rtt_avg"] / 1000
a = c[c["ms"] > T_LAT].groupby(["unit_id", c["dtime"].dt.date]).size()  # records above the threshold per day
print(a[a == a.groupby("unit_id").transform("max")])  # days tied at the maximum


'''
OUTPUT:

unit_id   dtime
24733221  2022-09-18    2
          2022-09-20    2
          2022-10-11    2
24840041  2022-09-12    4
          2022-09-16    4
          2022-09-18    4
          2022-10-11    4
          2022-10-12    4
          2022-10-29    4
dtype: int64

24733221: 3 tied days (step_11.py removed 2022-09-20; pipeline.py removes 2022-09-18).
24840041: 6 tied days (step_11.py removed 2022-10-11; pipeline.py removes 2022-09-12).
'''