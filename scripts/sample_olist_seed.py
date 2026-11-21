"""Deterministic sample of the Olist dataset for the dbt project (dbt/seeds/).

Usage: python scripts/sample_olist_seed.py [RAW_DIR]     (default: data/raw; needs the 9 Kaggle CSVs)
Picks N_ORDERS orders with a fixed seed from the sorted order ids, keeps all rows that belong to them, and drops
free-text review comments. Same input -> same output (the sha256 of each seed is printed).

Source: Olist Brazilian E-Commerce Public Dataset, CC BY-NC-SA 4.0 (https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
The sample is a derivative shared under the same licence, for non-commercial use, with attribution.
"""
import hashlib
import random
import sys
from pathlib import Path
import pandas as pd

SEED = 42
N_ORDERS = 5000
raw = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "raw"
out = Path(__file__).resolve().parents[1] / "dbt" / "seeds"
out.mkdir(parents=True, exist_ok=True)


def read(name):
    return pd.read_csv(raw / name, dtype=str, keep_default_na=False)


orders = read("olist_orders_dataset.csv").sort_values("order_id")
ids = sorted(random.Random(SEED).sample(list(orders.order_id), N_ORDERS))
orders = orders[orders.order_id.isin(ids)]
customers = read("olist_customers_dataset.csv")
customers = customers[customers.customer_id.isin(orders.customer_id)].sort_values("customer_id")
items = read("olist_order_items_dataset.csv")
items = items[items.order_id.isin(ids)].sort_values(["order_id", "order_item_id"])
pay = read("olist_order_payments_dataset.csv")
pay = pay[pay.order_id.isin(ids)].sort_values(["order_id", "payment_sequential"])
rev = read("olist_order_reviews_dataset.csv")
rev = rev[rev.order_id.isin(ids)].drop(columns=["review_comment_title", "review_comment_message"]).sort_values(["order_id", "review_id"])
prods = read("olist_products_dataset.csv")
prods = prods[prods.product_id.isin(items.product_id)][["product_id", "product_category_name", "product_weight_g"]].sort_values("product_id")
trans = read("product_category_name_translation.csv")

tables = {"raw_orders": orders, "raw_customers": customers, "raw_order_items": items, "raw_payments": pay,
          "raw_reviews": rev, "raw_products": prods, "raw_category_translation": trans}
for name, df in tables.items():
    p = out / f"{name}.csv"
    df.to_csv(p, index=False, lineterminator="\n")
    print(f"{name}: {len(df):,} rows, {p.stat().st_size/1e3:.0f} KB, sha256 {hashlib.sha256(p.read_bytes()).hexdigest()[:12]}")
