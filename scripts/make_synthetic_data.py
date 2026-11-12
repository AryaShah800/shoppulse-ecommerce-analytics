"""SYNTHETIC test data with the same columns as the BigQuery marts. For testing the analysis code ONLY.
Refuses to write into results/ so fake numbers can never be mistaken for real ones.
Usage: python scripts/make_synthetic_data.py /some/other/folder"""
import sys, pathlib, numpy as np, pandas as pd
out = pathlib.Path(sys.argv[1]).resolve()
if out.name == "results" or "shoppulse/results" in str(out).replace("\\", "/"):
    sys.exit("Refusing to write synthetic data into results/. Use a different folder.")
out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)

def days(n, late):
    return np.where(late, rng.integers(1, 15, n), -rng.integers(0, 20, n))

n = 30000
late = rng.random(n) < 0.08
state = rng.choice(["SP", "RJ", "MG", "RS", "PR", "BA"], n, p=[.42, .13, .12, .06, .06, .21])
rep_p = np.where(late, 0.020, 0.032)
repeat = rng.random(n) < rep_p
pd.DataFrame({
    "customer_unique_id": [f"u{i}" for i in range(n)], "order_id": [f"o{i}" for i in range(n)],
    "customer_state": state, "purchased_at": pd.to_datetime("2017-01-01") + pd.to_timedelta(rng.integers(0, 430, n), "D"),
    "is_late": late, "days_vs_estimate": days(n, late),
    "review_score": rng.choice([1, 2, 3, 4, 5], n), "first_item_value": rng.gamma(2, 60, n).round(2),
    "repeat_item_value": np.where(repeat, rng.gamma(2, 70, n).round(2), np.nan), "repeat_180d": repeat,
}).to_csv(out / "mart_delivery_repeat.csv", index=False)

m = 60000
late2 = rng.random(m) < 0.08
score = np.where(late2, rng.choice([1, 2, 3, 4, 5], m, p=[.35, .12, .15, .18, .20]), rng.choice([1, 2, 3, 4, 5], m, p=[.06, .03, .08, .21, .62]))
pd.DataFrame({"order_id": [f"r{i}" for i in range(m)], "customer_state": rng.choice(["SP", "RJ", "MG"], m),
    "purchased_at": pd.to_datetime("2017-01-01") + pd.to_timedelta(rng.integers(0, 600, m), "D"),
    "is_late": late2, "days_vs_estimate": days(m, late2), "review_score": score, "is_low_review": score <= 2,
    "item_value": rng.gamma(2, 60, m).round(2)}).to_csv(out / "mart_delivery_reviews.csv", index=False)
print("synthetic files written to", out)
