import pandas as pd

df = pd.read_csv(
    "/home/dharshan/Documents/Eureka-statathon-Kabhilan/data/raw/nco_dataset_v6_final.csv",
    dtype=str
)

print(df.columns.tolist())