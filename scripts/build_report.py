"""Build docs/index.html (static, offline) from results/*.csv and results/04_summary.json.
Usage: python scripts/build_report.py [--png] [--offline] [--out DIR]   (--offline inlines plotly.js, about 5 MB; default uses a pinned CDN)
#   (--png also writes docs/img/*.png via Playwright)
Needs: pip install plotly pandas (+ playwright for --png). No BigQuery access required."""
import json
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
sys.path.insert(0, str(Path(__file__).parent))
from report_style import BLUE, ORANGE, MUTED, SEQ, style, build_page, screenshot  # noqa: E402

R = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else R / "docs"
res = R / "results"
s = json.load(open(res / "04_summary.json"))
funnel = pd.read_csv(res / "02a_funnel_overall.csv")
monthly = pd.read_csv(res / "02c_funnel_monthly.csv", parse_dates=["purchase_month"])
coh = pd.read_csv(res / "03b_cohort_retention.csv")
rfm = pd.read_csv(res / "03c_rfm_segments.csv")
dose = pd.read_csv(res / "04_dose_response.csv")
rt, pt, rev = s["review_test"], s["repeat_test"], s["revenue_at_stake_brl"]

# Derived numbers (all from the files above)
late_low = rt["n_late"] * rt["low_rate_late"]
ont_low = rt["n_ontime"] * rt["low_rate_ontime"]
share_low = late_low / (late_low + ont_low)
share_orders = rt["n_late"] / (rt["n_late"] + rt["n_ontime"])
worst = monthly.sort_values("on_time_pct").iloc[0]
top2 = rfm[rfm.segment.isin(["Recent high spenders", "Lost high spenders"])]
lost = rfm[rfm.segment == "Lost high spenders"].iloc[0]
d = dose.set_index("bucket")
late4 = int(d.loc["Late 4-7 d", "orders"] + d.loc["Late 8+ d", "orders"])

insights = [
    dict(num=f"{rt['low_rate_late']*100:.1f}% vs {rt['low_rate_ontime']*100:.1f}%",
         what=f"Late orders get 1-2 star reviews at {rt['low_rate_late']/rt['low_rate_ontime']:.1f}x the on-time rate (p < 0.001).",
         action="Treat lateness as the main driver of review score; make on-time rate a headline KPI.",
         impact=f"{share_orders*100:.1f}% of reviewed orders are late, yet they produce {share_low*100:.0f}% of all 1-2 star reviews."),
    dict(num=f"{d.loc['Late 1-3 d','low_review_rate']*100:.0f}% to {d.loc['Late 8+ d','low_review_rate']*100:.0f}%",
         what="The 1-2 star share climbs with every extra day late (1-3 d, 4-7 d, 8+ d: "
              f"{d.loc['Late 1-3 d','low_review_rate']*100:.0f}%, {d.loc['Late 4-7 d','low_review_rate']*100:.0f}%, {d.loc['Late 8+ d','low_review_rate']*100:.0f}%).",
         action="Send a proactive message or goodwill gesture once an order is 4+ days past its estimate, before the customer reviews.",
         impact=f"Targets the 4+ day bucket ({late4:,} reviewed orders in the dose-response table) where reviews turn mostly negative. The gesture's effect is untested."),
    dict(num=f"{worst.on_time_pct:.1f}% on time",
         what=f"On-time delivery fell to {worst.on_time_pct:.1f}% in {worst.purchase_month:%B %Y} (85.9% in Feb 2018, 87.6% in Nov 2017) against 93-99% in most months.",
         action="Add delivery-estimate buffer and review carrier capacity before peak and carnival months.",
         impact="These three months hold the largest on-time shortfall; a better estimate is cheaper than a bad review."),
    dict(num=f"{pt['repeat_rate_late']*100:.2f}% vs {pt['repeat_rate_ontime']*100:.2f}%",
         what=f"Late first deliveries repeat-buy less within 180 days, but the {pt['gap_pp']:.2f} pp gap is NOT significant (p = {pt['p']:.3f}).",
         action="Do not fund retention on delivery alone. Run a randomised goodwill test on late orders and measure 180-day repeat.",
         impact=f"Upper-end value is small: R${rev['estimate']:,.0f} (range R$0 to R${rev['high']:,.0f}) over {rev['window_months']:.1f} months. Observational, not proven causal."),
    dict(num=f"{top2.pct_revenue.sum():.0f}% of revenue",
         what=f"Two segments, {top2.pct_customers.sum():.0f}% of customers, make {top2.pct_revenue.sum():.0f}% of item revenue; the lapsed one (R${lost.revenue_brl/1e6:.1f}M) last ordered about {lost.avg_recency_days:.0f} days ago.",
         action="Run a win-back test aimed at lapsed high spenders; repeat buying is rare overall (3.04% of customers order twice).",
         impact=f"R${lost.revenue_brl/1e6:.1f}M of historic revenue sits in {int(lost.customers):,} lapsed high spenders. Response rate unknown, so test small first."),
]

f1 = go.Figure(go.Bar(x=funnel.orders, y=funnel.stage, orientation="h", marker_color=BLUE,
                      text=[f"{o:,} ({p:.1f}%)" for o, p in zip(funnel.orders, funnel.pct_of_placed)], textposition="outside",
                      hovertemplate="%{y}: %{x:,} orders<extra></extra>"))
f1.update_yaxes(autorange="reversed")
f1.update_xaxes(range=[0, funnel.orders.max() * 1.3])
style(f1, 300, False)

f2 = go.Figure(go.Scatter(x=monthly.purchase_month, y=monthly.on_time_pct, mode="lines+markers", line=dict(color=BLUE, width=2),
                          marker=dict(size=8), hovertemplate="%{x|%b %Y}: %{y:.1f}% on time<extra></extra>"))
f2.add_hline(y=95, line_dash="dot", line_color=MUTED, annotation_text="95%", annotation_position="bottom right")
f2.update_yaxes(title="% delivered on time", range=[78, 100])
style(f2, 360, False)

order = ["Early 8+ d", "Early 1-7 d", "On the day", "Late 1-3 d", "Late 4-7 d", "Late 8+ d"]
dd = d.loc[order].reset_index()
f3 = go.Figure(go.Bar(x=dd.bucket, y=dd.low_review_rate * 100, marker_color=[BLUE] * 3 + [ORANGE] * 3,
                      text=[f"{v*100:.0f}%" for v in dd.low_review_rate], textposition="outside",
                      customdata=dd.orders, hovertemplate="%{x}: %{y:.1f}% 1-2 star (%{customdata:,} orders)<extra></extra>"))
f3.update_yaxes(title="% of orders with a 1-2 star review", range=[0, 95])
style(f3, 340, False)

piv = coh[(coh.month_offset >= 1) & (coh.month_offset <= 12)].pivot(index="cohort_month", columns="month_offset", values="retention_pct")
piv = piv.loc[piv.index.astype(str) <= "2018-02-01"]
f4 = go.Figure(go.Heatmap(z=piv.values, x=[f"M+{c}" for c in piv.columns], y=[str(i)[:7] for i in piv.index],
                          colorscale=[[0, SEQ[0]], [.25, SEQ[1]], [.5, SEQ[2]], [.75, SEQ[3]], [1, SEQ[4]]], zmin=0, zmax=1.2,
                          colorbar=dict(title="% retained"), hovertemplate="Cohort %{y}, %{x}: %{z:.2f}%<extra></extra>"))
f4.update_yaxes(autorange="reversed")
style(f4, 420, False)

rr = rfm.sort_values("revenue_brl")
f5 = go.Figure(go.Bar(x=rr.pct_revenue, y=rr.segment, orientation="h", marker_color=BLUE,
                      text=[f"{p:.0f}% of revenue, {c:.0f}% of customers" for p, c in zip(rr.pct_revenue, rr.pct_customers)],
                      textposition="outside", hovertemplate="%{y}: %{x:.1f}% of revenue<extra></extra>"))
f5.update_xaxes(title="% of item revenue", range=[0, 60])
style(f5, 340, False)
f5.update_layout(margin=dict(l=170, r=24, t=16, b=48))

sections = [
    ("Late delivery vs reviews", "Share of orders with a 1-2 star review by days relative to the estimated date. Blue = early or on the day, orange = late.", f3),
    ("On-time rate by purchase month", "Share of delivered orders arriving on or before the estimated calendar day. Dotted line = 95%.", f2),
    ("Fulfilment funnel", "Order pipeline: placed, approved, handed to carrier, delivered. The biggest loss is at carrier handover.", f1),
    ("Where the revenue sits (RFM segments)", "Share of item revenue and of customers by segment.", f5),
    ("Monthly cohort retention", "Percent of each first-purchase month's customers who ordered again, by months since first order. Almost every cell is under 1.2%.", f4),
]
out, size = build_page(
    "ShopPulse: late deliveries, reviews and repeat buying",
    "Olist Brazilian e-commerce, Jan 2017 to Aug 2018, about 99k orders. Money in Brazilian reais (R$), item price only.",
    insights, sections,
    caveat="Observational data. Late delivery is strongly linked to bad reviews, but its link to repeat purchase is borderline (p = 0.053) and the test could only detect gaps of about 0.68 pp or more. Every number comes from this repo's code (results/).",
    footer='Source: <a href="https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce">Olist dataset</a> (CC BY-NC-SA 4.0). Method: README and memo.md in the repo.',
    out=str(OUT / "index.html"), offline="--offline" in sys.argv)
print("wrote", out, f"{size/1e6:.2f} MB")
if "--png" in sys.argv:
    (OUT / "img").mkdir(exist_ok=True)
    screenshot(out, OUT / "img" / "report-top.png", height=1100)
    screenshot(out, OUT / "img" / "report-full.png", full=True)
