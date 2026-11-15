import pandas as pd
df = pd.read_csv("data/fixtures.csv", encoding="utf-8-sig")
sub = df[df["Div"].isin(["E0","D1","F1","I1","SP1"])]
cols = ["Div","HomeTeam","AwayTeam","B365H","B365D","B365A","B365>2.5","B365<2.5","Avg>2.5","Avg<2.5","B365CH","B365CD","B365CA"]
print(sub[cols].head(8).to_string())
print("non-null counts:")
print(sub[["B365>2.5","B365<2.5","Avg>2.5"]].notna().sum())
