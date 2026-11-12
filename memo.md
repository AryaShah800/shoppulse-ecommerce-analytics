# Memo: Late deliveries and lost repeat customers

**To:** Olist operations and growth leads  **From:** Arya Shah  **Data:** Olist orders, Jan 2017 to Aug 2018 (R$)

## Bottom line
Late delivery strongly damages reviews (62.4% of late orders get 1-2 stars vs 9.2% on-time). Its effect on repeat purchase is **borderline and not statistically significant at the 5% level**: 1.35% of late-delivered customers order again within 180 days of delivery vs 1.87% of on-time ones (p = 0.053). The revenue at stake is small and not distinguishable from zero (R$1,658, range R$0 to R$2,919 over 13.8 months).

## What I found
| Question | Result |
|---|---|
| Share of delivered orders that arrive late | 6.77% (`01_data_checks`, check 14) |
| Late vs on-time: 1-2 star reviews | 62.40% vs 9.25% (gap +53.15 pp, 95% CI +51.94 to +54.35), p < 0.001; mean score 2.27 vs 4.29 |
| Repeat purchase within 180 days of first delivery: on-time vs late | 1.87% (926 of 49,642) vs 1.35% (36 of 2,668); gap 0.52 pp, 95% CI -0.01 to 0.91, p = 0.053 |
| Holds inside the largest state (SP)? After adjustment? | SP only: gap 0.59 pp, p = 0.270. Adjusted odds ratio for late 0.74 (95% CI 0.53 to 1.04), p = 0.079; also controlling for purchase month 0.78 (0.56 to 1.10), p = 0.156. The direction is consistent (late customers repeat less) but no check reaches significance. |
| Does a longer delay hurt more? | Reviews: yes, 1-2 star share rises from 32.1% (1-3 days late) to 67.6% (4-7) to 79.3% (8+). Repeat rate also falls with lateness (1.52%, 1.37%, 1.22% vs about 1.87% for on-time or early), though this is descriptive and not tested for trend. |
| Was the test able to detect a gap? | Only gaps of about 0.68 pp or more (80% power). The observed 0.52 pp gap is below that, so "not significant" means "cannot tell", not "no effect". |

Context: 3.04% of customers ever placed a second order (2,887 of 94,990). In the repeat test, 5.10% of the 52,310 first-time customers (2,668 people) received a late first delivery.

## What it is worth
Late first-time customers 2,668 x repeat gap 0.52 pp x average repeat order R$120.40 = **R$1,658** over 13.8 months (range R$0 to R$2,919; the lower bound is floored at zero because the CI includes zero).

Caveat: this is observational data, so the gap is an association, not proof that lateness caused it. The gap is also not statistically significant, so treat this figure as an upper-end illustration, not a finding.

## Recommendations
1. **Fix the delivery promise where it is breaking.** Action: review carrier performance and estimate accuracy in the worst months (on-time rate fell to 81.0% in March 2018, 85.9% in February 2018 and 87.6% in November 2017, against 93% to 99% in most other months). Metric: monthly on-time rate and the share of 1-2 star reviews. Supported by: the review test (p < 0.001) and the monthly funnel.
2. **Intervene on orders that are 4 or more days late.** Action: proactive messaging or a goodwill gesture for these orders before the customer reviews. Metric: 1-2 star share among late orders. Supported by: dose-response (32.1% at 1-3 days late, 67.6% at 4-7, 79.3% at 8+).
3. **Do not justify retention spend on delivery alone; test it.** Action: run a randomised test of a goodwill gesture on late orders and measure 180-day repeat purchase. Metric: repeat rate. Supported by: the borderline, non-significant repeat result (p = 0.053), an underpowered observational test (minimum detectable gap 0.68 pp), and the very low baseline repeat rate (1.84% within 180 days of delivery).

## Method, in four lines
- Customer = `customer_unique_id`. Late = delivered on a later calendar day than the estimate.
- Repeat test: one row per person (first valid order, if delivered); outcome = another valid order placed after that delivery and within 180 days of it; first orders delivered on or before 2018-03-04 so everyone had 180 days of follow-up.
- Two-proportion z-test, 95% CI on the gap (Newcombe), checked in the largest state and with logistic regression (state, basket value, purchase month).
- Money is Brazilian reais, item price only (no freight).
