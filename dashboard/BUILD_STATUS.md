# ShopPulse Power BI build

Status on 2026-11-14: the four-page PBIP and semantic model are generated and pass the official Microsoft report JSON schemas. **Not yet opened or refreshed in Desktop. No ShopPulse PBIX, PDF or page screenshots are claimed.** The Windows computer-use helper became unavailable before this step; reconnect it to continue.

## Reproduce

From the ShopPulse repository, using the existing authenticated BigQuery project:

```powershell
python scripts/export_dashboard_data.py --project shoppulse-514512 --tables fct_orders
python scripts/build_powerbi_project.py
```

`--resume` can resume an interrupted download only if the source table is unchanged. The exporter uses read-only table access; it does not rerun SQL or change BigQuery data. `dashboard/data/` is ignored by Git.

Open `ShopPulse.pbip` in Power BI Desktop. The `DataFolder` parameter points to this checkout's absolute `dashboard/data/` path; change it when moving machines. Refresh the tables, inspect all four pages and the slicer interactions, save `ShopPulse.pbix`, then export `ShopPulse.pdf` and page images. These actions remain pending. Matrix formatting and the scenario controls also need checking in Desktop; schema validation does not establish their appearance or interaction.

## Data and reconciliation

- Full `fct_orders`: 99,441 distinct 32-character order ids, exported from the existing BigQuery table.
- Power Query filters the Orders table to purchases from 2017-01-01 through 2018-08-31: 99,092 orders, 96,211 delivered (97.09%).
- Reviews are derived from the exported order fact using the same conditions as `sql/04`: 95,560 reviewed delivered orders with known lateness. Late: 6,378; on-time: 89,182. The low-review proportions match `04_summary.json` exactly.
- The 210-row cohort table, seven RFM segment aggregates, repeat snapshot, saved approximate stage durations and dose-response outputs come from the existing `results/` exports. These are fixed snapshots, not recalculated under state/month slicers. RFM revenue inherits the SQL export's rounding to whole R$.
- Four pages, 14 imported tables, 20 DAX measures. Dates and states filter the Orders and Reviews tables in one direction. Month/state slicers are configured in shared sync groups on the descriptive pages; verify this behavior in Desktop.
- Repeat inference remains the fixed 52,310-person analysis, with full 180-day follow-up measured after first delivery. The 0.52 pp gap has p=0.053 and a CI crossing zero. It is not significant at 5%; no causal effect is claimed.
- The revenue scenario explicitly makes an unsupported causal assumption. Unfiltered controls use the saved analysis defaults; filtered controls use their highest selected value. It is an illustration, not a forecast or proven loss.

## Verification performed

The generator fails on wrong order counts, duplicate/truncated ids, wrong delivered count, wrong review sample sizes or changed low-review rates. It ran successfully. All 45 schema-bearing report/page/visual files validated with zero errors against [Microsoft's published schemas](https://github.com/microsoft/json-schemas/tree/main/fabric/item/report/definition). Validation output is in the workspace's `docs/shoppulse_schema_validation.json`.

The original `PAGES.md` and `measures.dax` remain the design reference. The generated report uses a CSV snapshot of existing marts instead of a live BigQuery connector, so it opens without cloud credentials after export. Do not put an unverified ShopPulse dashboard claim on the resume.
