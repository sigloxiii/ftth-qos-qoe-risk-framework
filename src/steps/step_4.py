# step_4.py
# Objective: Inspect the duplicate records (same unit_id, dtime and target) found in
#            step_2.py, to decide how to handle them in the pipeline
#            (docs/metrics_spec.md, section 5).
#            Checks whether duplicates are exact copies (all columns equal) or have
#            conflicting values, in the latency and jitter files.
# Inputs:    data/interim/udplatency_ftth.csv, udpjitter_ftth.csv (created by step_1.py)
# Outputs:   Console only (results are documented in docs/data_inspection.md)

import pandas as pd

INTERIM = r"D:\Capstone FTTH\data\interim"
KEY = ["unit_id", "dtime", "target"]

for name in ["udplatency", "udpjitter"]:
    df = pd.read_csv(INTERIM + rf"\{name}_ftth.csv", parse_dates=["dtime"])
    # keep=False marks every row involved, not just the second copy
    dup = df[df.duplicated(KEY, keep=False)].sort_values(KEY)
    exact = df.duplicated(keep=False).sum()  # rows with ALL columns equal to another row
    print(f"\n=== {name} ===")
    print("Filas con clave duplicada:", len(dup),
          "| de ellas, copias exactas:", int(exact))
    print(dup.head(30).to_string())


'''
=== udplatency ===
Filas con clave duplicada: 16 | de ellas, copias exactas: 16
         unit_id               dtime                          target  rtt_avg  rtt_min  successes  failures
112866    943226 2022-09-17 06:41:32  sp2-vm-chicago-us.samknows.com    20344     7769        637         0
141486    943226 2022-09-17 06:41:32  sp2-vm-chicago-us.samknows.com    20344     7769        637         0
160795    943226 2022-09-17 06:41:32  sp2-vm-chicago-us.samknows.com    20344     7769        637         0
26495    1000852 2022-10-27 16:01:39  sp2-vm-chicago-us.samknows.com     9475     8439       1700         0
45696    1000852 2022-10-27 16:01:39  sp2-vm-chicago-us.samknows.com     9475     8439       1700         0
93972    1000852 2022-10-30 23:01:37  sp2-vm-chicago-us.samknows.com     9489     8519       1651         0
113099   1000852 2022-10-30 23:01:37  sp2-vm-chicago-us.samknows.com     9489     8519       1651         0
108621   1011922 2022-09-17 06:47:14  sp1-vm-ashburn-us.samknows.com     4637     1790       2155         0
127611   1011922 2022-09-17 06:47:14  sp1-vm-ashburn-us.samknows.com     4637     1790       2155         0
156381   1011922 2022-09-17 06:47:14  sp1-vm-ashburn-us.samknows.com     4637     1790       2155         0
59702    3551869 2022-10-21 09:18:48  sp1-vm-ashburn-us.samknows.com    12402     6848        737         0
89037    3551869 2022-10-21 09:18:48  sp1-vm-ashburn-us.samknows.com    12402     6848        737         0
94043   24329113 2022-10-13 17:14:54  sp2-vm-chicago-us.samknows.com    10978    10522       1373         0
103626  24329113 2022-10-13 17:14:54  sp2-vm-chicago-us.samknows.com    10978    10522       1373         0
49685   37383721 2022-09-16 16:55:28  sp1-vm-ashburn-us.samknows.com    14720    13490        995         0
88600   37383721 2022-09-16 16:55:28  sp1-vm-ashburn-us.samknows.com    14720    13490        995         0

=== udpjitter ===
Filas con clave duplicada: 10 | de ellas, copias exactas: 8
         unit_id               dtime                          target  jitter_up  jitter_down
16993     943232 2022-10-19 21:12:17  sp1-vm-atlanta-us.samknows.com        294           60
133716    943232 2022-10-19 21:12:17  sp1-vm-atlanta-us.samknows.com        282          120
54388    1000852 2022-10-21 13:00:31  sp1-vm-chicago-us.samknows.com        993           98
120000   1000852 2022-10-21 13:00:31  sp1-vm-chicago-us.samknows.com        993           98
54121   24195149 2022-10-06 18:45:57  sp1-vm-chicago-us.samknows.com        492          258
141482  24195149 2022-10-06 18:45:57  sp1-vm-chicago-us.samknows.com        492          258
109918  38098501 2022-10-27 15:44:21   sp1-vm-dallas-us.samknows.com       1769          798
124451  38098501 2022-10-27 15:44:21   sp1-vm-dallas-us.samknows.com       1769          798
22409   38098501 2022-10-29 01:44:22   sp1-vm-dallas-us.samknows.com       1037          800
51714   38098501 2022-10-29 01:44:22   sp1-vm-dallas-us.samknows.com       1037          800
'''