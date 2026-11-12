# ShopPulse — E-Commerce Funnel, Retention & Delivery-Impact Analysis

**Business question:** Do late deliveries cost Olist repeat customers, and how much revenue is at stake?

| | |
|---|---|
| Data | [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — ~100k orders, 2016–2018, 9 tables |
| Stack | BigQuery (SQL), Python (Pandas, SciPy, statsmodels, Seaborn). A Power BI dashboard is specced in `dashboard/` but not built yet. |
| Currency | All money is in Brazilian reais (R$), as in the source data |

## Key findings
> Every number below is produced by the code in this repo (outputs in `results/`). Window: Jan 2017 to Aug 2018. The one-page recommendations memo is in `memo.md`.

- **Fulfilment funnel** (`02a`, `02b`): 99,092 orders placed; 97.09% reached delivery. The biggest drop is at the carrier handover (1,593 orders lost, 98.39% step conversion). Median purchase-to-delivery is 10.2 days (p90 23.1 days).
- **Cohort retention** (`03a`, `03b`): 94,990 customers, of whom 2,887 (3.04%) ordered more than once. Repeat buying is rare in this dataset.
- **Late delivery vs reviews** (`04`): 62.40% of late orders got 1-2 stars vs 9.25% of on-time orders (p < 0.001; 95,560 orders).
- **Late delivery vs repeat purchase** (`04`): repeat rate within 180 days of first delivery is 1.35% (late) vs 1.87% (on-time), gap 0.52 pp, 95% CI -0.01 to 0.91, p = 0.053 (52,310 people). **Borderline, not statistically significant at the 5% level.** Adjusted odds ratio 0.74 (95% CI 0.53 to 1.04); 0.78 (0.56 to 1.10, p = 0.156) when also controlling for purchase month. The repeat rate falls as lateness grows (1.52% for 1-3 days late, 1.22% for 8+), but the test could only detect gaps of about 0.68 pp or more.
- **Revenue at stake** (`04`): R$1,658 over 13.8 months, range R$0 to R$2,919. Observational data and a non-significant gap, so this is an upper-end illustration, not a proven loss.

## Pipeline

```
data/raw/*.csv  ──load_raw.py──▶  olist_raw.*  (STRING, untouched)
                                      │ 00_staging.sql
                                      ▼
                     shoppulse.stg_*  (typed views)  ──▶  shoppulse.fct_orders (1 row per order)
                                                              │ 01_data_checks.sql, 02_…, 03_…
                                                              ▼
                                                   shoppulse.mart_*  ──▶  stats notebook (+ Power BI spec)
```

## Reproduce

1. **BigQuery sandbox (free, no card):** open https://console.cloud.google.com/bigquery, create a project, note its project id.
   Sandbox limits: tables and views expire after 60 days, and INSERT/UPDATE/DELETE are not allowed. Everything here uses `CREATE OR REPLACE`, and re-running the loader rebuilds the raw layer.
2. **Download the data** into `data/raw/` (9 CSVs), either manually from Kaggle or:
   ```bash
   kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
   ```
3. **Load raw tables:**
   ```bash
   pip install -r requirements.txt
   gcloud auth application-default login
   export GCP_PROJECT=your-project-id        # PowerShell: $env:GCP_PROJECT="your-project-id"
   python scripts/load_raw.py
   ```
4. **Run SQL in order** in the BigQuery console (paste the whole file, Run):
   `00_staging` → `01_data_checks` → `02_fulfilment_funnel` → `03_cohorts_rfm` → `04_delivery_test_datasets`
5. **Save each result set** as CSV into `results/` using the file names in the SQL comments.
   For the two `mart_delivery_*` tables: either export them as `results/mart_delivery_reviews.csv` and
   `results/mart_delivery_repeat.csv`, or set `GCP_PROJECT` and the notebook reads them from BigQuery.
6. **Run the stats:** `python notebooks/04_delivery_impact.py`. It writes `results/04_resume_numbers.md`,
   `04_summary.json`, `04_dose_response.csv` and `04_delivery_impact.png`.
7. **Dashboard (optional):** `dashboard/PAGES.md` and `dashboard/measures.dax` specify a 4-page Power BI report over the `mart_*` tables. The `.pbix` is not built yet.
8. **Read the memo:** `memo.md` summarises the findings and recommendations.

Testing the code without the data: `python scripts/make_synthetic_data.py <folder outside results/>` creates fake tables with the
same columns; run the notebook with `RESULTS_DIR=<that folder>`. Synthetic numbers are for testing only, never for the resume.

## Repo structure

```
shoppulse/
├── data/raw/            # source CSVs (git-ignored) + manifest.csv (row counts, SHA-256)
├── scripts/load_raw.py  # CSV → BigQuery raw layer
├── sql/
│   ├── 00_staging.sql          # typed views + fct_orders
│   ├── 01_data_checks.sql      # data-quality report
│   ├── 02_fulfilment_funnel.sql
│   ├── 03_cohorts_rfm.sql       # cohort retention grid + RFM segments
│   └── 04_delivery_test_datasets.sql
├── notebooks/04_delivery_impact.py   # z-tests, CI, robustness, dose-response, revenue sizing
├── scripts/make_synthetic_data.py    # fake data for testing the code only
├── results/             # exported query outputs (CSV) + generated numbers
├── dashboard/           # measures.dax and PAGES.md (Power BI spec; .pbix not built)
└── memo.md              # one-page recommendations memo
```

## Definitions
| Term | Definition |
|---|---|
| Customer | `customer_unique_id` (a person). `customer_id` changes on every order and is never used for repeat analysis. |
| Late order | Delivered on a later calendar day than `order_estimated_delivery_date`. Delivered orders only. |
| Funnel stage reached | Cumulative: an order that reached a later stage counts as having passed the earlier ones. |
| Revenue | Sum of item `price` (excludes freight and instalment interest). |
| Valid order | Status not `canceled` or `unavailable`. |
| Repeat purchase | Another valid order placed after a person's first order was delivered, within 180 days of that delivery (an order placed before delivery cannot be a reaction to it). First orders delivered on or before 2018-03-04, so everyone had full follow-up. |
| RFM | Recency and Monetary in quintiles (5 = best); Frequency is a rule (1 / 2 / 3+) because almost everyone orders only once (3.04% of customers ordered twice or more, Q1 in 03). |
