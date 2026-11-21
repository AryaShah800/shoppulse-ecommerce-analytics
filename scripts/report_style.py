"""Shared report style: dataviz-skill categorical palette, insight-first HTML page.

Copied verbatim into each repo (scripts/report_style.py). Findings lead the page; charts follow.
plotly.js comes from a pinned CDN URL by default; offline=True inlines it (about 5 MB).
"""
from __future__ import annotations
import html
import re
from pathlib import Path
import plotly
import plotly.graph_objects as go
import plotly.io as pio

# Categorical order from the dataviz reference palette (light mode), fixed order, never cycled.
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
SEQ = ["#e8f0fb", "#a9c8f0", "#5f9be3", "#2a78d6", "#18457f"]  # one hue, light to dark
INK, INK2, MUTED, GRID, SURFACE = "#1a1a19", "#4a4a45", "#76766d", "#e6e5df", "#ffffff"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
SIZE_LIMIT = 5_000_000


def style(fig: go.Figure, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK2, size=13), colorway=CATEGORICAL,
        margin=dict(l=56, r=24, t=16, b=48), hovermode="closest",
        showlegend=legend, legend=dict(orientation="h", y=1.12, x=0),
        hoverlabel=dict(font=dict(family=FONT)),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="outside", tickcolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


CSS = f"""
:root{{--bg:#faf9f6;--surface:#fff;--ink:{INK};--ink2:{INK2};--muted:{MUTED};--line:{GRID};--accent:{BLUE};}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#121211;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#9a9a90;--line:#33332f;--accent:#3987e5;}}}}
:root[data-theme="dark"]{{--bg:#121211;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#9a9a90;--line:#33332f;--accent:#3987e5;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font-family:{FONT};line-height:1.5}}
main{{max-width:1040px;margin:0 auto;padding:32px 16px 64px}}
h1{{font-size:1.7rem;line-height:1.2;margin:0 0 6px}} .sub{{color:var(--ink2);margin:0 0 24px}}
h2{{font-size:1.15rem;margin:36px 0 4px}} .note{{color:var(--muted);font-size:.9rem;margin:0 0 8px}}
.insights{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px}} .card{{grid-column:span 2}} .card.wide{{grid-column:span 3}}
@media (max-width:760px){{.insights{{grid-template-columns:1fr}} .card,.card.wide{{grid-column:auto}}}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px}}
.card .num{{font-size:1.9rem;font-weight:700;color:var(--accent);line-height:1.1}}
.card .what{{font-weight:600;margin:4px 0 8px}} .card p{{margin:4px 0;font-size:.92rem;color:var(--ink2)}}
.card b{{color:var(--ink)}}
.chart{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:8px;margin-top:8px;overflow:hidden}}
.caveat{{border-left:3px solid {YELLOW};padding:6px 12px;margin:20px 0 0;color:var(--ink2);font-size:.9rem;background:var(--surface)}}
footer{{margin-top:40px;color:var(--muted);font-size:.85rem}} a{{color:var(--accent)}}
"""


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def build_page(title, subtitle, insights, sections, caveat="", footer="", out="docs/index.html", offline=False):
    """insights: list of dict(num, what, action, impact). sections: list of (heading, note, fig)."""
    n_i = len(insights)
    wide = lambda k: " wide" if n_i % 3 == 2 and k >= n_i - 2 else ""  # last row of 2 -> two wide cards
    cards = "".join(
        f'<div class="card{wide(k)}"><div class="num">{_esc(i["num"])}</div><div class="what">{_esc(i["what"])}</div>'
        f'<p><b>Action:</b> {_esc(i["action"])}</p><p><b>Impact:</b> {_esc(i["impact"])}</p></div>'
        for k, i in enumerate(insights))
    body = []
    for n, (h, note, fig) in enumerate(sections):
        div = pio.to_html(fig, include_plotlyjs=False, full_html=False, config={"displaylogo": False, "responsive": True}, div_id=f"c{n}")
        body.append(f'<h2>{_esc(h)}</h2><p class="note">{_esc(note)}</p><div class="chart">{div}</div>')

    def page(js_tag):
        cav = f'<div class="caveat"><b>Read with care.</b> {_esc(caveat)}</div>' if caveat else ""
        return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<title>{_esc(title)}</title><style>{CSS}</style>{js_tag}</head><body><main><h1>{_esc(title)}</h1>'
                f'<p class="sub">{_esc(subtitle)}</p><section class="insights" aria-label="Key findings">{cards}</section>{cav}'
                f'{"".join(body)}<footer>{footer}</footer></main></body></html>')

    js = (Path(plotly.__file__).parent / "package_data" / "plotly.min.js").read_text(encoding="utf-8")
    ver = re.search(r"plotly\.js v([\d.]+)", js[:200]).group(1)  # CDN pinned to the bundled version
    if offline:  # self-contained file (about 5 MB)
        doc = page(f"<script>{js}</script>")
    else:
        doc = page(f'<script src="https://cdn.plot.ly/plotly-{ver}.min.js" charset="utf-8"></script>')
    p = Path(out); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return p, len(doc.encode("utf-8"))


def screenshot(html_path, png_path, width=1100, height=1500, full=False):
    """Headless Chromium screenshot (Playwright) for README embedding."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="msedge"); pg = b.new_page(viewport={"width": width, "height": height})
        pg.goto(Path(html_path).resolve().as_uri()); pg.wait_for_timeout(1500)
        pg.screenshot(path=str(png_path), full_page=full); b.close()
