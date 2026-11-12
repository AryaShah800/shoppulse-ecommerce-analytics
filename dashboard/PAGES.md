# ShopPulse dashboard: page spec (Power BI Desktop)

Build order matters: model first, then pages. Each page answers one question.

## Model
| Table | Grain | Role |
|---|---|---|
| `fct_orders` | one row per order | main fact |
| `Dim Date` | one row per day | calendar (DAX in `measures.dax`) |
| `mart_funnel_monthly` | month | funnel trend page |
| `mart_cohort_retention` | cohort x month offset | heatmap |
| `mart_rfm` | person | segment page |

Relationship: `Dim Date[Date]` 1-to-many `fct_orders[purchase_date]`. The mart tables stand alone.

## Pages
| # | Page | Question it answers | Visuals |
|---|---|---|---|
| 1 | Overview | How is the business doing? | KPI cards (Orders, Revenue, AOV, On-time %, Avg Review), monthly revenue line, orders by state map/bar |
| 2 | Fulfilment funnel | Where do orders drop out and how slow is each stage? | Funnel visual (Placed, Approved, Carrier, Delivered), stage-duration bars from `results/02b`, monthly Delivered % trend |
| 3 | Retention & segments | Do customers come back? | Cohort heatmap matrix (conditional formatting), repeat-customer % card, RFM segment bar (customers and revenue) |
| 4 | Late delivery impact | Do late orders cost reviews and repeat buyers? | Low Review % late vs on-time, repeat-rate gap card from the notebook, dose-response column chart, revenue-at-risk card with the two what-if sliders |

## Rules that keep it defensible
- Slicers: purchase month and customer state, synced across pages 1, 2 and 4.
- Every currency label says R$. Tooltips show the definition of "late" (calendar day after the estimate).
- Page 4's repeat-rate numbers come from the notebook (`results/04_summary.json`), not recomputed in DAX. Type them into the what-if defaults and say so in the page footnote.
- Colour: one accent for "late" (red/orange), one neutral for "on-time". No rainbow palettes.

## Deliverables to commit
- `dashboard/ShopPulse.pbix`
- `dashboard/ShopPulse.pdf` (File -> Export -> PDF)
- `dashboard/page1.png` ... `page4.png` (screenshots used in the README)

Publishing to the Power BI Service needs a work or school account. If you only have a personal account, commit the `.pbix` and PDF, and keep the resume wording as "Built", not "Published".
