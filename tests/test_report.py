"""The headline numbers on the report cards must equal values computed from results/ (no hardcoded copies)."""
import json
import subprocess
import sys
from pathlib import Path
import pandas as pd
import pytest

R = Path(__file__).resolve().parents[1]
res = R / "results"


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    out = tmp_path_factory.mktemp("report")
    subprocess.run([sys.executable, str(R / "scripts" / "build_report.py"), "--out", str(out)], check=True, cwd=R)
    return (out / "index.html").read_text(encoding="utf-8")


def test_findings_come_before_charts(page):
    assert page.index("Key findings") < page.index('id="c0"')


def test_headline_numbers_match_results(page):
    s = json.load(open(res / "04_summary.json"))
    rt, pt, rev = s["review_test"], s["repeat_test"], s["revenue_at_stake_brl"]
    monthly = pd.read_csv(res / "02c_funnel_monthly.csv")
    rfm = pd.read_csv(res / "03c_rfm_segments.csv")
    top2 = rfm[rfm.segment.isin(["Recent high spenders", "Lost high spenders"])]
    expected = [
        f"{rt['low_rate_late']*100:.1f}%", f"{rt['low_rate_ontime']*100:.1f}%",
        f"{monthly.on_time_pct.min():.1f}%",
        f"{pt['repeat_rate_late']*100:.2f}%", f"{pt['repeat_rate_ontime']*100:.2f}%",
        f"p = {pt['p']:.3f}", f"{pt['gap_pp']:.2f} pp",
        f"{top2.pct_revenue.sum():.0f}% of revenue",
        f"R${rev['estimate']:,.0f}", f"R${rev['high']:,.0f}",
    ]
    for e in expected:
        assert e in page, e


def test_known_values_sanity():
    # guards the source files themselves, so a silent data change is noticed
    s = json.load(open(res / "04_summary.json"))
    assert round(s["repeat_test"]["p"], 3) == 0.053
    assert s["repeat_test"]["p"] > 0.05  # must stay framed as not significant
