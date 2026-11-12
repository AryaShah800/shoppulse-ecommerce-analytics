# Memo: Late deliveries and lost repeat customers

**To:** Olist operations and growth leads  **From:** Arya Shah  **Data:** Olist orders, Jan 2017 to Aug 2018 (R$)

## Bottom line
Late delivery strongly damages reviews (62.4% of late orders get 1-2 stars vs 9.2% on-time), but I found **no statistically significant effect on repeat purchase** (2.70% vs 3.20%, p = 0.083). The revenue at stake is small and not distinguishable from zero (R$2,392, range R$0 to R$4,718 over 13.9 months).

## What I found
| Question | Result |
|---|---|
| Share of delivered orders that arrive late | 6.77% (`01_data_checks`, check 14) |
| Late vs on-time: 1-2 star reviews | 62.40% vs 9.25% (gap +53.15 pp, 95% CI +51.94 to +54.35), p < 0.001; mean score 2.27 vs 4.29 |
| Repeat purchase within 180 days: on-time vs late | 3.20% vs 2.70% (gap 0.50 pp, 95% CI -0.07 to 0.99), p = 0.083 |
| Holds inside the largest state (SP)? After adjustment? | SP only: gap 0.89 pp, p = 0.137. Adjusted odds ratio for late 0.86 (95% CI 0.70 to 1.05), p = 0.137; also controlling for purchase month 0.86 (0.70 to 1.06), p = 0.155. The result stays non-significant in every check. |
| Does a longer delay hurt more? | For reviews, yes: 1-2 star share rises from 32.1% (1-3 days late) to 67.6% (4-7 days) to 79.3% (8+ days). For repeat purchase there is no clean pattern (3.18%, 2.15%, 2.74%). |
| Was the test able to detect a gap? | Only gaps of about 0.77 pp or more (80% power). The observed 0.50 pp gap is below that, so "not significant" means "cannot tell", not "no effect". |

Context: only 3.04% of customers ever ordered a second time (2,887 of 94,990), and 6.99% of the 56,154 first-time customers in the test received a late first order (3,924 people).

## What it is worth
Late first-time customers 3,924 x repeat gap 0.50 pp x average repeat order R$121.47 = **R$2,392** over 13.9 months (range R$0 to R$4,718; the lower bound is floored at zero because the CI includes zero).

Caveat: this is observational data, so the gap is an association, not proof that lateness caused it. The gap is also not statistically significant, so treat this figure as an upper-end illustration, not a finding.

## Recommendations
1. **Fix the delivery promise where it is breaking.** Action: review carrier performance and estimate accuracy in the worst months (on-time rate fell to 81.0% in March 2018, 85.9% in February 2018 and 87.6% in November 2017, against 93% to 99% in most other months). Metric: monthly on-time rate and the share of 1-2 star reviews. Supported by: the review test (p < 0.001) and the monthly funnel.
2. **Intervene on orders that are 4 or more days late.** Action: proactive messaging or a goodwill gesture for these orders before the customer reviews. Metric: 1-2 star share among late orders. Supported by: dose-response (32.1% at 1-3 days late, 67.6% at 4-7, 79.3% at 8+).
3. **Do not justify retention spend on delivery alone; test it.** Action: run a randomised test of a goodwill gesture on late orders and measure 180-day repeat purchase. Metric: repeat rate. Supported by: the non-significant repeat result (p = 0.083), an underpowered observational test (minimum detectable gap 0.77 pp), and the low baseline repeat rate (3.04% of customers).

## Method, in four lines
- Customer = `customer_unique_id`. Late = delivered on a later calendar day than the estimate.
- Repeat test: one row per person (first delivered order), outcome = another order within 180 days; cohort cut off so everyone had 180 days of follow-up.
- Two-proportion z-test, 95% CI on the gap (Newcombe), checked in the largest state and with logistic regression (state, basket value, purchase month).
- Money is Brazilian reais, item price only (no freight).
