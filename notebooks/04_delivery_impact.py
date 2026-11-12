# %% [markdown]
# # 04 - Do late deliveries cost Olist repeat customers?
# Cells use `# %%` markers: open in VS Code / Jupyter (Interactive window) or run as a script.
#
# **Inputs** (made by `sql/04_delivery_test_datasets.sql`): `mart_delivery_reviews` (order-level) and
# `mart_delivery_repeat` (one row per person). Read from `results/<name>.csv` if present, else from BigQuery.
#
# **Questions**
# 1. Do late orders get more low (1-2 star) reviews?
# 2. Are people whose first order arrived late less likely to buy again within 180 days?
# 3. Does the effect survive a robustness check (largest state only) and adjustment for state and basket value?
# 4. How much revenue does the repeat-purchase gap represent?
#
# Every number printed here is the only source for numbers on the resume.

# %%
import os, json, pathlib, numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, seaborn as sns, scipy.stats as st
import statsmodels.api as sm, statsmodels.formula.api as smf
from statsmodels.stats.proportion import proportions_ztest, confint_proportions_2indep

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = pathlib.Path(os.environ.get("RESULTS_DIR", ROOT / "results"))
RESULTS.mkdir(exist_ok=True, parents=True)
ALPHA = 0.05
sns.set_theme(style="whitegrid", context="notebook")


def load(table: str) -> pd.DataFrame:
    csv = RESULTS / f"{table}.csv"
    if csv.exists():
        print(f"[load] {csv.name} (CSV)")
        return pd.read_csv(csv)
    project = os.environ.get("GCP_PROJECT")
    if not project:
        raise SystemExit(f"{csv} not found and GCP_PROJECT is not set. Export the table to CSV or set GCP_PROJECT.")
    from google.cloud import bigquery
    print(f"[load] shoppulse.{table} (BigQuery)")
    return bigquery.Client(project=project).query(f"SELECT * FROM shoppulse.{table}").to_dataframe()


def two_prop(x_a, n_a, x_b, n_b):
    """Two-sided two-proportion z-test of group A vs group B, plus a 95% CI on (rate_a - rate_b)."""
    z, p = proportions_ztest([x_a, x_b], [n_a, n_b])
    lo, hi = confint_proportions_2indep(x_a, n_a, x_b, n_b, compare="diff", method="newcomb")
    return dict(rate_a=x_a / n_a, rate_b=x_b / n_b, diff=x_a / n_a - x_b / n_b, ci_low=lo, ci_high=hi, z=z, p=p)


def fmt_p(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


# %% [markdown]
# ## Load and validate

# %%
rev = load("mart_delivery_reviews")
rep = load("mart_delivery_repeat")
for df, cols in ((rev, ["is_late", "is_low_review"]), (rep, ["is_late", "repeat_180d"])):
    for c in cols:
        df[c] = df[c].astype(bool)

assert rep["customer_unique_id"].is_unique, "repeat table must have one row per person"
assert rev["review_score"].between(1, 5).all(), "review scores must be 1-5"
print(f"reviews table: {len(rev):,} delivered orders | repeat table: {len(rep):,} people")
print(f"late share: orders {rev.is_late.mean():.2%} | people {rep.is_late.mean():.2%}")
print(f"overall 180-day repeat rate: {rep.repeat_180d.mean():.2%}")

out = {"n_orders_reviews": int(len(rev)), "n_people_repeat": int(len(rep))}

# %% [markdown]
# ## Test 1 - review scores: late vs on-time orders
# Primary metric: share of 1-2 star reviews (two-proportion z-test).
# Secondary: full score distribution (Mann-Whitney U, since scores are ordinal, not normal).

# %%
late, ontime = rev[rev.is_late], rev[~rev.is_late]
t1 = two_prop(int(late.is_low_review.sum()), len(late), int(ontime.is_low_review.sum()), len(ontime))
mw = st.mannwhitneyu(late.review_score, ontime.review_score, alternative="two-sided")
out["review_test"] = dict(n_late=len(late), n_ontime=len(ontime),
    low_rate_late=t1["rate_a"], low_rate_ontime=t1["rate_b"], diff=t1["diff"], ci_low=t1["ci_low"], ci_high=t1["ci_high"],
    p=t1["p"], mean_score_late=float(late.review_score.mean()), mean_score_ontime=float(ontime.review_score.mean()),
    mannwhitney_p=float(mw.pvalue))
print(f"\nLow-review share  late {t1['rate_a']:.2%} vs on-time {t1['rate_b']:.2%} | diff {t1['diff']*100:+.2f} pp "
      f"(95% CI {t1['ci_low']*100:+.2f} to {t1['ci_high']*100:+.2f}) | {fmt_p(t1['p'])}")
print(f"Mean score late {late.review_score.mean():.2f} vs on-time {ontime.review_score.mean():.2f} | Mann-Whitney {fmt_p(mw.pvalue)}")

# %% [markdown]
# ## Test 2 - repeat purchase within 180 days (first delivered order, one row per person)
# Compared as on-time minus late, so a positive gap means late deliveries cost repeat buyers.

# %%
lt, ot = rep[rep.is_late], rep[~rep.is_late]
t2 = two_prop(int(ot.repeat_180d.sum()), len(ot), int(lt.repeat_180d.sum()), len(lt))
rel_drop = (t2["rate_a"] - t2["rate_b"]) / t2["rate_a"] if t2["rate_a"] > 0 else float("nan")
out["repeat_test"] = dict(n_late=len(lt), n_ontime=len(ot), repeat_rate_ontime=t2["rate_a"], repeat_rate_late=t2["rate_b"],
    gap_pp=t2["diff"] * 100, ci_low_pp=t2["ci_low"] * 100, ci_high_pp=t2["ci_high"] * 100, p=t2["p"],
    relative_drop_pct=rel_drop * 100, repeaters_late=int(lt.repeat_180d.sum()), repeaters_ontime=int(ot.repeat_180d.sum()))
print(f"\nRepeat rate  on-time {t2['rate_a']:.2%} ({int(ot.repeat_180d.sum()):,}/{len(ot):,}) vs late {t2['rate_b']:.2%} "
      f"({int(lt.repeat_180d.sum()):,}/{len(lt):,})")
print(f"Gap {t2['diff']*100:.2f} pp (95% CI {t2['ci_low']*100:.2f} to {t2['ci_high']*100:.2f}) | relative drop {rel_drop:.1%} | {fmt_p(t2['p'])}")

# %% [markdown]
# ## Robustness - is it just geography?
# (a) Repeat test inside the largest state only. (b) Logistic regression controlling for state and basket value.

# %%
top_state = rep.customer_state.value_counts().idxmax()
sub = rep[rep.customer_state == top_state]
s_lt, s_ot = sub[sub.is_late], sub[~sub.is_late]
t_state = two_prop(int(s_ot.repeat_180d.sum()), len(s_ot), int(s_lt.repeat_180d.sum()), len(s_lt))
out["robustness_state"] = dict(state=top_state, n_late=len(s_lt), n_ontime=len(s_ot), gap_pp=t_state["diff"] * 100,
    ci_low_pp=t_state["ci_low"] * 100, ci_high_pp=t_state["ci_high"] * 100, p=t_state["p"])
print(f"\n{top_state} only: on-time {t_state['rate_a']:.2%} vs late {t_state['rate_b']:.2%} | gap {t_state['diff']*100:.2f} pp | {fmt_p(t_state['p'])}")

top4 = rep.customer_state.value_counts().index[:4]
m = rep.assign(state_grp=np.where(rep.customer_state.isin(top4), rep.customer_state, "Other"),
               y=rep.repeat_180d.astype(int), late_i=rep.is_late.astype(int),
               log_value=np.log1p(rep.first_item_value.fillna(0).astype(float)))
logit = smf.logit("y ~ late_i + log_value + C(state_grp)", data=m).fit(disp=0)
orr = float(np.exp(logit.params["late_i"])); olo, ohi = np.exp(logit.conf_int().loc["late_i"])
out["logit_adjusted"] = dict(odds_ratio_late=orr, ci_low=float(olo), ci_high=float(ohi), p=float(logit.pvalues["late_i"]))
print(f"Adjusted odds ratio for late delivery: {orr:.2f} (95% CI {olo:.2f}-{ohi:.2f}) | {fmt_p(logit.pvalues['late_i'])}")

# Sensitivity: lateness clusters in a few bad months (e.g. Mar 2018), so also control for purchase month.
m["purchase_month"] = pd.to_datetime(m.purchased_at).dt.strftime("%Y-%m")
logit_m = smf.logit("y ~ late_i + log_value + C(state_grp) + C(purchase_month)", data=m).fit(disp=0)
orr_m = float(np.exp(logit_m.params["late_i"])); mlo, mhi = np.exp(logit_m.conf_int().loc["late_i"])
out["logit_adjusted_month"] = dict(odds_ratio_late=orr_m, ci_low=float(mlo), ci_high=float(mhi), p=float(logit_m.pvalues["late_i"]))
print(f"Adjusted OR incl. purchase month: {orr_m:.2f} (95% CI {mlo:.2f}-{mhi:.2f}) | {fmt_p(logit_m.pvalues['late_i'])}")

# Power: smallest repeat-rate gap this sample could detect (80% power, alpha 5%, two-sided).
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize
p_base = t2["rate_a"]
h = NormalIndPower().solve_power(effect_size=None, nobs1=len(lt), ratio=len(ot) / len(lt), alpha=ALPHA, power=0.8, alternative="two-sided")
p_detect = float(np.sin((2 * np.arcsin(np.sqrt(p_base)) - h) / 2) ** 2)
out["power"] = dict(baseline_rate=p_base, mde_gap_pp=(p_base - p_detect) * 100, detectable_late_rate=p_detect)
print(f"Minimum detectable gap (80% power): {(p_base - p_detect)*100:.2f} pp (late rate would need to be <= {p_detect:.2%} vs on-time {p_base:.2%})")

# %% [markdown]
# ## Dose-response - does a longer delay hurt more?

# %%
bins = [-np.inf, -8, -1, 0, 3, 7, np.inf]
labels = ["Early 8+ d", "Early 1-7 d", "On the day", "Late 1-3 d", "Late 4-7 d", "Late 8+ d"]
rep["bucket"] = pd.cut(rep.days_vs_estimate, bins=bins, labels=labels)
rev["bucket"] = pd.cut(rev.days_vs_estimate, bins=bins, labels=labels)
dose = (rep.groupby("bucket", observed=True).agg(people=("repeat_180d", "size"), repeat_rate=("repeat_180d", "mean"))
        .join(rev.groupby("bucket", observed=True).agg(orders=("is_low_review", "size"), low_review_rate=("is_low_review", "mean"))))
dose.to_csv(RESULTS / "04_dose_response.csv")
print("\n", (dose.assign(repeat_rate=lambda d: (d.repeat_rate * 100).round(2), low_review_rate=lambda d: (d.low_review_rate * 100).round(1))).to_string())

# %% [markdown]
# ## Revenue at stake (Day 6)
# `late first-time customers x repeat-rate gap x average value of a repeat order`.
# Range uses the 95% CI bounds of the gap (lower bound floored at 0). All money is in R$.
# **Assumption:** the gap is causal. It is observational data, so treat this as an upper-end estimate and say so in the memo.

# %%
avg_repeat_value = float(rep.loc[rep.repeat_180d, "repeat_item_value"].astype(float).mean())
n_late_people = len(lt)
def at_risk(gap): return n_late_people * max(gap, 0.0) * avg_repeat_value
months = (pd.to_datetime(rep.purchased_at).max() - pd.to_datetime(rep.purchased_at).min()).days / 30.44
est, low, high = at_risk(t2["diff"]), at_risk(t2["ci_low"]), at_risk(t2["ci_high"])
out["revenue_at_stake_brl"] = dict(avg_repeat_order_value=avg_repeat_value, late_first_time_customers=n_late_people,
    window_months=months, estimate=est, low=low, high=high, annualized_estimate=est * 12 / months if months else None)
print(f"\nAvg repeat order value R${avg_repeat_value:,.2f} | late first-time customers {n_late_people:,}")
print(f"Revenue at stake over the {months:.1f}-month window: R${est:,.0f} (range R${low:,.0f} - R${high:,.0f}); annualized ~R${est*12/months:,.0f}")

# %% [markdown]
# ## Charts

# %%
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ax[0].bar(["On-time", "Late"], [t2["rate_a"] * 100, t2["rate_b"] * 100], color=["#4C78A8", "#E4572E"])
ax[0].set(title=f"180-day repeat rate ({fmt_p(t2['p'])})", ylabel="% of first-time customers")
for i, v in enumerate([t2["rate_a"] * 100, t2["rate_b"] * 100]): ax[0].text(i, v, f"{v:.2f}%", ha="center", va="bottom")
d = dose.reset_index()
ax[1].bar(d.bucket.astype(str), d.low_review_rate * 100, color="#E4572E"); ax[1].set(title="1-2 star reviews by delivery timing", ylabel="% of orders")
ax[1].tick_params(axis="x", rotation=35)
plt.tight_layout(); fig.savefig(RESULTS / "04_delivery_impact.png", dpi=150)

# %% [markdown]
# ## Resume-ready lines (generated from the numbers above)

# %%
sig = t2["p"] < ALPHA
rt = out["repeat_test"]
if sig:
    line = (f"Tested whether late deliveries lower repeat purchases on {rt['n_late'] + rt['n_ontime']:,} first-time customers "
            f"(two-proportion z-test, {fmt_p(t2['p'])}); late deliveries had {rel_drop*100:.0f}% fewer repeat buyers within 180 days.")
else:
    line = (f"Tested whether late deliveries lower repeat purchases on {rt['n_late'] + rt['n_ontime']:,} first-time customers "
            f"(two-proportion z-test, {fmt_p(t2['p'])}): no statistically significant difference at the 5% level.")
md = f"""# Numbers cleared for the resume (generated {pd.Timestamp.today():%Y-%m-%d})

Source: notebooks/04_delivery_impact.py. Do not edit by hand, re-run instead.

- Repeat-purchase test: {fmt_p(t2['p'])}; repeat rate on-time {t2['rate_a']:.2%} vs late {t2['rate_b']:.2%} (gap {t2['diff']*100:.2f} pp, 95% CI {t2['ci_low']*100:.2f} to {t2['ci_high']*100:.2f}).
- Relative drop in repeat buyers: {rel_drop*100:.1f}%
- Robustness ({top_state} only): gap {t_state['diff']*100:.2f} pp, {fmt_p(t_state['p'])}
- Adjusted odds ratio (late): {orr:.2f} (95% CI {olo:.2f}-{ohi:.2f})
- Adjusted odds ratio incl. purchase month: {orr_m:.2f} (95% CI {mlo:.2f}-{mhi:.2f}), {fmt_p(logit_m.pvalues['late_i'])}
- Minimum detectable repeat-rate gap (80% power): {(p_base - p_detect)*100:.2f} pp
- Low-review share: late {t1['rate_a']:.1%} vs on-time {t1['rate_b']:.1%}, {fmt_p(t1['p'])}
- Revenue at stake: R${est:,.0f} over {months:.1f} months (range R${low:,.0f} to R${high:,.0f}); all amounts in Brazilian reais.

## Draft resume bullet (check it against the numbers above before using)
{line}
"""
(RESULTS / "04_resume_numbers.md").write_text(md, encoding="utf-8")
(RESULTS / "04_summary.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
print("\n" + md)
