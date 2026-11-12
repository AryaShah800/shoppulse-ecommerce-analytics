"""
Load the 9 Olist CSVs into BigQuery as raw, untouched STRING tables.

- Raw layer = exact copy of the source files (all columns STRING). Typing happens in SQL staging views.
- Writes data/raw/manifest.csv with row counts + SHA-256 per file, so the source export is verifiable.
- Safe to re-run at any time (WRITE_TRUNCATE load jobs). Re-run it if the sandbox's 60-day expiry deletes tables.

Usage:
    gcloud auth application-default login
    set GCP_PROJECT=your-project-id          (PowerShell: $env:GCP_PROJECT="your-project-id")
    python scripts/load_raw.py
"""
import os, sys, csv, hashlib, pathlib, pandas as pd; from google.cloud import bigquery

RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"
RAW_DATASET = "olist_raw"
WORK_DATASET = "shoppulse"
LOCATION = "US"

# BigQuery table name -> Kaggle file name (dataset: olistbr/brazilian-ecommerce)
FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    project = os.environ.get("GCP_PROJECT")
    if not project:
        sys.exit("Set the GCP_PROJECT environment variable to your BigQuery project id.")

    missing = [name for name in FILES.values() if not (RAW_DIR / name).exists()]
    if missing:
        sys.exit(f"Missing files in {RAW_DIR}:\n  " + "\n  ".join(missing))

    client = bigquery.Client(project=project)
    for ds in (RAW_DATASET, WORK_DATASET):
        dataset = bigquery.Dataset(f"{project}.{ds}")
        dataset.location = LOCATION
        client.create_dataset(dataset, exists_ok=True)

    manifest = []
    for table, filename in FILES.items():
        path = RAW_DIR / filename
        # dtype=str keeps the raw layer faithful (no silent type guessing);
        # utf-8-sig strips a byte-order mark if a header has one;
        # pandas handles the multi-line quoted text in the reviews file.
        # keep_default_na=False: text such as "NA" or "null" stays as text; only truly empty cells become NULL.
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False, na_values=[""])
        df.columns = [c.strip() for c in df.columns]

        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_TRUNCATE",
            schema=[bigquery.SchemaField(c, "STRING") for c in df.columns],
        )
        table_id = f"{project}.{RAW_DATASET}.{table}"
        client.load_table_from_dataframe(df, table_id, job_config=job_config).result()

        loaded = client.get_table(table_id).num_rows
        status = "OK" if loaded == len(df) else "ROW COUNT MISMATCH"
        print(f"{table:<22} {len(df):>9,} rows in file  {loaded:>9,} rows loaded  {status}")
        manifest.append({"table": table, "file": filename, "rows": len(df), "sha256": sha256(path)})

    with open(RAW_DIR / "manifest.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["table", "file", "rows", "sha256"])
        writer.writeheader()
        writer.writerows(manifest)
    print(f"\nManifest written to {RAW_DIR / 'manifest.csv'}")


if __name__ == "__main__":
    main()
