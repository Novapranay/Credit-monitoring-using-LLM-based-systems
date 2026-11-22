"""AI Leaders Credit Monitor: Streamlit dashboard. Run `python run.py` first, then `streamlit run app.py`."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from aicm.scoring import LABELS, why_moved  # noqa: E402

OUT, PROC = ROOT / "output", ROOT / "data" / "processed"
METRICS = list(LABELS)

# One colour per meaning, used everywhere. Status colours never double as chart-series colours.
STATUS_COLOR = {"Green": "#2e7d32", "Amber": "#ef6c00", "Red": "#c62828", "Not rated": "#757575", "Pending first 10-Q": "#757575"}
STATUS_DOT = {"Green": "🟢", "Amber": "🟠", "Red": "🔴", "Not rated": "⚪", "Pending first 10-Q": "⚪"}
C_CASH, C_CAPEX, C_DEBT, C_DEBT_OLD = "#2b6cb0", "#ef6c00", "#6b4c9a", "#b8a9d0"

# Plain-language description of each metric, shown in tooltips and on the Method tab.
INFO = {
    "net_debt_to_cfo": ("Net debt / operating cash flow", "Years of operating cash flow it would take to repay net debt. Net cash counts as zero risk."),
    "capex_to_cfo": ("Capex / operating cash flow", "Share of operating cash flow spent on building capacity. Above 100% the buildout is funded from reserves or new debt."),
    "fcf_to_debt": ("Free cash flow / debt", "Cash left after capex, relative to total debt. Negative means debt is rising to fund the gap."),
    "debt_growth_yoy": ("Debt growth, year on year", "How fast total debt has grown over the last year."),
    "current_ratio": ("Current ratio", "Short-term assets divided by short-term liabilities. Below 1.0 means near-term bills exceed near-term assets."),
    "op_margin_change_yoy": ("Operating margin change, year on year", "Change in operating margin, in percentage points. A fall means profitability is eroding."),
    "drawdown": ("Share price drawdown from one-year high", "How far the share price is below its one-year high. An equity signal, used as a cross-check."),
}

st.set_page_config(page_title="AI Leaders Credit Monitor", page_icon="📉", layout="wide")
st.markdown(
    """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px;}
.hero h1 {margin: 0; font-size: 2.1rem; letter-spacing: -0.01em;}
.hero p {margin: .25rem 0 0; opacity: .75; font-size: 1.02rem;}
.kpi {border: 1px solid rgba(128,128,128,.28); border-left: 6px solid var(--c, #888); border-radius: 10px; padding: 12px 16px; height: 100%;}
.kpi .n {font-size: 2rem; font-weight: 700; line-height: 1.15;}
.kpi .l {opacity: .75; font-size: .85rem;}
.pill {color: #fff; padding: 2px 11px; border-radius: 999px; font-size: .82em; font-weight: 600; white-space: nowrap;}
.asof {display: inline-block; border: 1px solid rgba(128,128,128,.35); border-radius: 999px; padding: 2px 12px; font-size: .82rem; opacity: .85; margin-top: .6rem;}
.headline {font-size: 1.12rem; line-height: 1.5; margin: .2rem 0 1rem;}
.small {opacity: .7; font-size: .85rem;}
.alert {padding: 6px 0; border-bottom: 1px solid rgba(128,128,128,.18);}
div[data-testid="stVerticalBlockBorderWrapper"] h1 {font-size: 1.45rem;}
div[data-testid="stVerticalBlockBorderWrapper"] h2 {font-size: 1.12rem; margin-top: .6rem;}
button[role="tab"] p {font-size: 1.02rem; font-weight: 600;}
</style>
""",
    unsafe_allow_html=True,
)

if not (OUT / "watchlist.csv").exists():
    st.error("No results yet. Run `python run.py` first.")
    st.stop()

watch = pd.read_csv(OUT / "watchlist.csv")
metrics = pd.read_csv(PROC / "metrics.csv")
scores = pd.read_csv(PROC / "scores.csv")
alerts = pd.read_csv(PROC / "alerts.csv")
lens = pd.read_csv(PROC / "bubble_lens.csv")
summary = json.loads((PROC / "bubble_summary.json").read_text())
cfg = yaml.safe_load((ROOT / "config" / "score_config.yaml").read_text())
latest_filing = pd.to_datetime(metrics["filed"]).max().date()
latest_pts = scores.sort_values("end").groupby("ticker").tail(1).set_index("ticker")
W = cfg["weights"]


def pill(status: str) -> str:
    return f"<span class='pill' style='background:{STATUS_COLOR.get(status, '#757575')}'>{status}</span>"


def kpi(label: str, number: str, color: str = "#888", sub: str = "") -> str:
    sub_html = f"<div class='small'>{sub}</div>" if sub else ""
    return f"<div class='kpi' style='--c:{color}'><div class='n'>{number}</div><div class='l'>{label}</div>{sub_html}</div>"


def fmt_value(m: str, row: pd.Series) -> str:
    """A metric value as a short human string, 'n/a' when missing."""
    v = row[m]
    if pd.isna(v):
        return "n/a"
    if m == "net_debt_to_cfo":
        return "net cash" if row["net_debt"] <= 0 else f"{v:.1f}x"
    if m == "fcf_to_debt":
        return f"{v:.0%}"
    if m in ("capex_to_cfo",):
        return f"{v:.0%}"
    if m == "debt_growth_yoy":
        return f"{v:+.0%}"
    if m == "current_ratio":
        return f"{v:.2f}x"
    if m == "op_margin_change_yoy":
        return f"{v * 100:+.1f} pts"
    if m == "drawdown":
        return f"-{v:.0%}"
    return f"{v}"


def fmt_threshold(m: str, v: float) -> str:
    if m == "net_debt_to_cfo":
        return f"{v:.1f}x"
    if m in ("capex_to_cfo", "fcf_to_debt", "debt_growth_yoy", "drawdown"):
        return f"{v:.0%}"
    if m == "current_ratio":
        return f"{v:.2f}x"
    return "no fall" if v == 0 else f"{v * 100:.1f} pts"


# ---------------------------------------------------------------- header
st.markdown(
    "<div class='hero'><h1>AI Leaders Credit Monitor</h1>"
    "<p>Is the AI buildout being paid for by cash flow, or increasingly by borrowed money? "
    "A lender's view of 13 public AI companies, built from SEC filings and market prices.</p>"
    f"<span class='asof'>Newest filing in the data: {latest_filing:%d %b %Y} &nbsp;·&nbsp; fundamentals change when a company files, prices daily &nbsp;·&nbsp; not investment advice</span></div>",
    unsafe_allow_html=True,
)
st.write("")
tab_watch, tab_co, tab_bubble, tab_method = st.tabs(["Watchlist", "Company", "AI-bubble lens", "Method and QA"])

# ---------------------------------------------------------------- watchlist
with tab_watch:
    counts = watch["status"].value_counts()
    n = {s: int(counts.get(s, 0)) for s in ["Red", "Amber", "Green", "Pending first 10-Q"]}
    st.markdown(
        f"<div class='headline'><b>{n['Red']} Red, {n['Amber']} Amber, {n['Green']} Green.</b> "
        f"Across the {summary['companies']} scored companies, capex takes {summary['capex_to_cfo']:.0%} of operating cash flow and total debt is "
        f"{summary['debt_growth']:+.0%} over a year. {summary['outspending']} of them ({', '.join(summary['outspending_names'])}) spend more than they generate.</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    notes = {"Red": "worth a closer look", "Amber": "keep an eye on", "Green": "steady", "Pending first 10-Q": "Anthropic"}
    for c, s in zip(cols, n):
        c.markdown(kpi(f"{s} · {notes[s]}", str(n[s]), STATUS_COLOR[s]), unsafe_allow_html=True)
    st.write("")

    f1, f2 = st.columns([3, 2])
    with f1:
        chosen = st.pills("Show", ["Red", "Amber", "Green", "Pending first 10-Q"], selection_mode="multi",
                          default=["Red", "Amber", "Green", "Pending first 10-Q"], key="status_filter")
    with f2:
        full = st.toggle("Show all seven metrics", value=False, help="Off: the three headline metrics. On: every metric in the scorecard.")

    view = watch[watch["status"].isin(chosen or [])].reset_index(drop=True)
    show = pd.DataFrame({
        "Ticker": view["ticker"], "Company": view["name"], "Layer": view["layer"],
        "Status": [f"{STATUS_DOT.get(s, '')} {s}" for s in view["status"]],
        "Risk score": view["score"], "Change": view["score_change"],
        "Net debt / op. cash flow": view["net_debt_to_cfo"], "Capex / op. cash flow": view["capex_to_cfo"] * 100, "Debt growth y/y": view["debt_growth_yoy"] * 100,
    })
    if full:
        show["FCF / debt"] = view["fcf_to_debt"] * 100
        show["Current ratio"] = view["current_ratio"]
        show["Op. margin chg y/y"] = view["op_margin_change_yoy"] * 100
        show["Drawdown from 1y high"] = view["drawdown"] * 100
    show["Why flagged"] = view["top_alert"].fillna("")
    cc = {
        "Risk score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%.0f", help="0 to 100, higher is riskier. Green below 30, Amber 30 to 55, Red above 55."),
        "Change": st.column_config.NumberColumn("Change", format="%+.0f", help="Score change versus the prior quarter."),
        "Net debt / op. cash flow": st.column_config.NumberColumn(format="%.1fx", help=INFO["net_debt_to_cfo"][1] + " Negative means net cash."),
        "Capex / op. cash flow": st.column_config.NumberColumn(format="%.0f%%", help=INFO["capex_to_cfo"][1]),
        "Debt growth y/y": st.column_config.NumberColumn(format="%+.0f%%", help=INFO["debt_growth_yoy"][1]),
        "FCF / debt": st.column_config.NumberColumn(format="%.0f%%", help=INFO["fcf_to_debt"][1]),
        "Current ratio": st.column_config.NumberColumn(format="%.2fx", help=INFO["current_ratio"][1]),
        "Op. margin chg y/y": st.column_config.NumberColumn(format="%+.1f%%", help=INFO["op_margin_change_yoy"][1]),
        "Drawdown from 1y high": st.column_config.NumberColumn(format="%.0f%%", help=INFO["drawdown"][1]),
        "Why flagged": st.column_config.TextColumn(width="large"),
    }
    event = st.dataframe(show, hide_index=True, width="stretch", column_config=cc, on_select="rerun", selection_mode="single-row",
                         key="watch_table", height=min(40 + 35 * len(show), 560))
    st.caption("Click a row for a quick view. Hover a column title for what it means. Triggers can override the score band: see Method and QA.")

    picked = event.selection.rows if event and event.selection else []
    if picked:
        r = view.iloc[picked[0]]
        st.session_state["company_pick"] = r["ticker"]
        with st.container(border=True):
            st.markdown(f"**{r['name']} ({r['ticker']})** &nbsp; {pill(r['status'])}", unsafe_allow_html=True)
            if r["status"] == "Pending first 10-Q":
                st.write("Listed in November 2026 with only a registration statement filed, so there is nothing to score yet.")
            else:
                st.write(f"Risk score **{r['score']:.0f}** ({r['watch_level']}). {r['top_alert'] if isinstance(r['top_alert'], str) else ''}")
                if isinstance(r["triggers"], str) and r["triggers"]:
                    st.warning(r["triggers"])
            st.caption("Open the Company tab for the full breakdown and credit note.")

    st.subheader("Where each score comes from")
    st.caption("Each cell is one metric: colour shows risk points (0 = no risk, 4 = full risk), the text shows the actual value. Companies are sorted by score.")
    rated = watch[watch["score"].notna()].sort_values("score", ascending=True)
    z, text, tcolor = [], [], []
    for _, r in rated.iterrows():
        pr = latest_pts.loc[r["ticker"]]
        z.append([pr[f"pts_{m}"] for m in METRICS])
        text.append([fmt_value(m, r) for m in METRICS])
    heat = go.Figure(go.Heatmap(
        z=z, x=[INFO[m][0].replace(", year on year", " y/y").replace("Share price drawdown from one-year high", "Drawdown from 1y high").replace(" / ", " /<br>") for m in METRICS],
        y=[f"{t}" for t in rated["ticker"]], zmin=0, zmax=4, xgap=3, ygap=3,
        colorscale=[[0, "#d8ecd9"], [0.5, "#fbe3a8"], [0.75, "#f2a65a"], [1, "#c62828"]],
        colorbar=dict(title="Risk points", tickvals=[0, 2, 4], thickness=12), hoverongaps=False,
        customdata=[[f"{INFO[m][0]}: {text[i][j]}" for j, m in enumerate(METRICS)] for i in range(len(z))],
        hovertemplate="%{y}<br>%{customdata}<br>risk points %{z:.1f} of 4<extra></extra>"))
    for i, row_z in enumerate(z):
        for j, v in enumerate(row_z):
            heat.add_annotation(x=j, y=i, text=text[i][j], showarrow=False, font=dict(size=12, color="#ffffff" if (not pd.isna(v) and v >= 3) else "#1b1b1b"))
    heat.update_layout(height=60 + 34 * len(z), margin=dict(t=10, b=10, l=10, r=10), xaxis=dict(side="top", tickfont=dict(size=11)),
                       yaxis=dict(tickfont=dict(size=12)))
    st.plotly_chart(heat, width="stretch")

    st.subheader("Alerts")
    sev = st.pills("Severity", ["high", "medium", "info"], selection_mode="multi", default=["high", "medium"], key="sev_filter")
    shown = alerts[alerts["severity"].isin(sev or [])]
    if shown.empty:
        st.info("No alerts at this severity.")
    else:
        dots = {"high": "🔴", "medium": "🟠", "info": "⚪"}
        html = "".join(f"<div class='alert'>{dots[r.severity]} <b>{r.ticker}</b> <span class='small'>· {r.type}</span><br>{r.text}</div>" for r in shown.itertuples())
        with st.container(height=360, border=True):
            st.markdown(html, unsafe_allow_html=True)

# ---------------------------------------------------------------- company
with tab_co:
    order = watch.sort_values("score", ascending=False, na_position="last")
    names = dict(zip(watch["ticker"], watch["name"]))
    tickers = list(order["ticker"])
    if st.session_state.get("company_pick_applied") != st.session_state.get("company_pick") and st.session_state.get("company_pick") in tickers:
        st.session_state["company"] = st.session_state["company_pick"]
        st.session_state["company_pick_applied"] = st.session_state["company_pick"]
    t = st.selectbox("Company (sorted by risk score, highest first)", tickers, key="company", format_func=lambda x: f"{x}: {names[x]}")
    row = watch[watch["ticker"] == t].iloc[0]
    st.markdown(f"## {row['name']} &nbsp; {pill(row['status'])}", unsafe_allow_html=True)
    st.markdown(f"<span class='small'>{row['layer']} · {row['angle']}</span>", unsafe_allow_html=True)

    if row["status"] == "Pending first 10-Q":
        st.info("Anthropic listed in November 2026 and has only filed a registration statement, so there are no quarterly financials to score yet. It will be scored on the first run after its first 10-Q appears in the SEC data.")
    else:
        m = metrics[metrics["ticker"] == t].sort_values("end")
        s = scores[scores["ticker"] == t].sort_values("end")
        st.markdown(f"<span class='small'>Period ended {row['period_end']}, filed {row['filed']}. Trailing twelve months unless stated.</span>", unsafe_allow_html=True)
        k = st.columns(5)
        k[0].metric("Risk score", f"{row['score']:.0f} / 100", None if pd.isna(row["score_change"]) else f"{row['score_change']:+.0f} vs prior quarter", delta_color="inverse",
                    help="0 to 100, higher is riskier. Green below 30, Amber 30 to 55, Red above 55.")
        k[1].metric("Net debt / op. cash flow", fmt_value("net_debt_to_cfo", row), help=INFO["net_debt_to_cfo"][1])
        k[2].metric("Capex / op. cash flow", fmt_value("capex_to_cfo", row), help=INFO["capex_to_cfo"][1])
        k[3].metric("FCF / debt", fmt_value("fcf_to_debt", row), help=INFO["fcf_to_debt"][1])
        k[4].metric("Debt growth y/y", fmt_value("debt_growth_yoy", row), help=INFO["debt_growth_yoy"][1])
        if isinstance(row["triggers"], str) and row["triggers"]:
            st.warning(row["triggers"])

        left, right = st.columns(2)
        pr = latest_pts.loc[t]
        avail = {mm: pr[f"pts_{mm}"] for mm in METRICS if not pd.isna(pr[f"pts_{mm}"])}
        wsum = sum(W[mm] for mm in avail)
        contrib = {mm: W[mm] * p / 4 / wsum * 100 for mm, p in avail.items()}
        order_m = sorted(contrib, key=contrib.get)
        fig = go.Figure(go.Bar(
            x=[contrib[mm] for mm in order_m], y=[INFO[mm][0] for mm in order_m], orientation="h",
            marker_color=[STATUS_COLOR["Red"] if avail[mm] >= 3 else (STATUS_COLOR["Amber"] if avail[mm] >= 1.5 else "#8fb996") for mm in order_m],
            text=[f"{fmt_value(mm, row)}  ·  {avail[mm]:.1f} of 4" for mm in order_m], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>adds %{x:.1f} score points<extra></extra>"))
        fig.update_layout(title="What drives the score (points added to the 0 to 100 score)", height=340, margin=dict(t=44, b=20, l=10, r=10),
                          xaxis=dict(title=f"Score points; the sum is {row['score']:.0f}", range=[0, max(max(contrib.values()) * 1.75, 6)]))
        left.plotly_chart(fig, width="stretch")

        fig = go.Figure(go.Scatter(x=s["end"], y=s["score"], mode="lines+markers", line=dict(color="#1565c0", width=3), name="Risk score",
                                   hovertemplate="%{x}<br>score %{y:.0f}<extra></extra>"))
        fig.add_hrect(y0=0, y1=cfg["status"]["green_below"], fillcolor=STATUS_COLOR["Green"], opacity=0.10, line_width=0, annotation_text="Green", annotation_position="top left")
        fig.add_hrect(y0=cfg["status"]["green_below"], y1=cfg["status"]["red_above"], fillcolor=STATUS_COLOR["Amber"], opacity=0.10, line_width=0, annotation_text="Amber", annotation_position="top left")
        fig.add_hrect(y0=cfg["status"]["red_above"], y1=100, fillcolor=STATUS_COLOR["Red"], opacity=0.10, line_width=0, annotation_text="Red", annotation_position="top left")
        fig.update_layout(title="Risk score history (each quarter uses only data filed by then)", yaxis=dict(range=[0, 100]), height=340, margin=dict(t=44, b=20, l=10, r=10), showlegend=False)
        right.plotly_chart(fig, width="stretch")

        left, right = st.columns(2)
        fig = go.Figure()
        fig.add_bar(x=m["end"], y=m["cfo"] / 1e9, name="Operating cash flow", marker_color=C_CASH)
        fig.add_bar(x=m["end"], y=m["capex"] / 1e9, name="Capex", marker_color=C_CAPEX)
        fig.add_scatter(x=m["end"], y=m["debt"] / 1e9, name="Debt", line=dict(color=C_DEBT, width=3), mode="lines+markers")
        fig.update_layout(title="Cash flow, capex and debt ($bn, trailing twelve months)", barmode="group", height=340, margin=dict(t=44, b=20, l=10, r=10),
                          legend=dict(orientation="h", y=-0.18))
        left.plotly_chart(fig, width="stretch")

        with right:
            st.markdown("**What moved since the prior quarter**")
            if len(s) >= 2:
                moved = why_moved(s.iloc[-2], s.iloc[-1], cfg)
                prev_status, cur_status = s.iloc[-2]["status"], s.iloc[-1]["status"]
                st.markdown(f"Status: {pill(prev_status)} → {pill(cur_status)}" if prev_status != cur_status else f"Status unchanged at {pill(cur_status)}", unsafe_allow_html=True)
                if moved:
                    for line in moved:
                        st.markdown(f"- {line}")
                else:
                    st.markdown("- No single metric moved the score by a meaningful amount.")
            else:
                st.markdown("Only one quarter of history, so nothing to compare yet.")
            st.markdown("**This company's alerts**")
            mine = alerts[alerts["ticker"] == t]
            if mine.empty:
                st.markdown("- None.")
            for a in mine.head(6).itertuples():
                st.markdown(f"- {a.type}: {a.text}")

        note = OUT / "notes" / f"{t}.md"
        st.subheader("Credit note")
        with st.container(border=True):
            if note.exists():
                st.markdown(note.read_text())
                st.caption("Written from a template and checked by six automated checks before publishing; every number comes from the computed tables.")
            else:
                st.info("No verified note for this company. See output/needs_review/ for the failed draft.")

# ---------------------------------------------------------------- AI-bubble lens
with tab_bubble:
    st.subheader("Is the buildout paid for by cash flow or by debt?")
    st.markdown(
        f"<div class='headline'>The {summary['companies']} scored companies generate about <b>${summary['cfo'] / 1e9:,.0f}bn</b> of operating cash flow and spend about "
        f"<b>${summary['capex'] / 1e9:,.0f}bn</b> on capex, so cash flow still covers the bill {summary['cfo'] / summary['capex']:.1f} times over. "
        f"The warning sign is direction: total debt is <b>${summary['debt'] / 1e9:,.0f}bn</b>, {summary['debt_growth']:+.0%} on a year ago.</div>",
        unsafe_allow_html=True,
    )
    c = st.columns(4)
    c[0].markdown(kpi("Capex, trailing twelve months", f"${summary['capex'] / 1e9:,.0f}bn", C_CAPEX), unsafe_allow_html=True)
    c[1].markdown(kpi("Operating cash flow, trailing twelve months", f"${summary['cfo'] / 1e9:,.0f}bn", C_CASH), unsafe_allow_html=True)
    c[2].markdown(kpi("Total debt", f"${summary['debt'] / 1e9:,.0f}bn", C_DEBT, f"{summary['debt_growth']:+.0%} year on year"), unsafe_allow_html=True)
    c[3].markdown(kpi("Spend more than they generate", f"{summary['outspending']} of {summary['companies']}", STATUS_COLOR["Red"], ", ".join(summary["outspending_names"])), unsafe_allow_html=True)
    st.write("")

    l = lens.copy()
    l["ratio"] = l["capex"] / l["cfo"]
    l = l.sort_values("ratio")
    CAP = 300
    left, right = st.columns(2)
    fig = go.Figure(go.Bar(
        x=(l["ratio"] * 100).clip(upper=CAP), y=l["ticker"], orientation="h", customdata=l["ratio"] * 100, marker_color=[STATUS_COLOR["Red"] if r > 1 else C_CAPEX for r in l["ratio"]],
        text=[f"{r:.0%}" + (" ▶" if r * 100 > CAP else "") for r in l["ratio"]], textposition="outside", cliponaxis=False, hovertemplate="%{y}: capex is %{customdata:.0f}% of operating cash flow<extra></extra>"))
    fig.add_vline(x=100, line_dash="dash", line_color="#888", annotation_text="100%: spends all its cash flow", annotation_position="bottom right")
    fig.update_layout(title="Capex as a share of operating cash flow", height=470, margin=dict(t=44, b=20, l=10, r=40), xaxis=dict(title="% of operating cash flow", range=[0, CAP * 1.15]))
    left.plotly_chart(fig, width="stretch")
    if l["ratio"].max() * 100 > CAP:
        left.caption(f"Bars stop at {CAP}% so the others stay readable; labels show the true ratio ({l.loc[l['ratio'].idxmax(), 'ticker']}: {l['ratio'].max():.0%}).")

    d = lens.sort_values("debt")
    fig = go.Figure()
    fig.add_bar(y=d["ticker"], x=d["prior_debt"] / 1e9, name="Debt a year earlier", marker_color=C_DEBT_OLD, orientation="h")
    fig.add_bar(y=d["ticker"], x=d["debt"] / 1e9, name="Debt now", marker_color=C_DEBT, orientation="h")
    fig.update_layout(title="Debt now vs a year earlier ($bn)", barmode="group", height=470, margin=dict(t=44, b=20, l=10, r=10), legend=dict(orientation="h", y=-0.12))
    right.plotly_chart(fig, width="stretch")

    st.info("Read with care: reported debt excludes off-balance-sheet financing such as data-centre joint ventures and leases not yet started. "
            "Oracle, CoreWeave and Super Micro are not included because their recent filings do not tag total debt cleanly, so the real picture is probably less calm than these totals.")

# ---------------------------------------------------------------- method
with tab_method:
    st.subheader("How a score is built")
    st.markdown(
        "Each company is judged against **fixed thresholds**, not against the other companies. Each of seven metrics earns 0 to 4 risk points, "
        "rising in a straight line between five thresholds. Points are multiplied by the weight and rescaled to a 0 to 100 score. "
        f"**Green** is below {cfg['status']['green_below']}, **Amber** {cfg['status']['green_below']} to {cfg['status']['red_above']}, **Red** above {cfg['status']['red_above']}. "
        f"If less than {cfg['min_weight_available']:.0%} of the weight is available the company is **Not rated**."
    )
    table = pd.DataFrame([{
        "Metric": INFO[k][0], "What it tells you": INFO[k][1], "Weight": W[k],
        "0 risk points at": fmt_threshold(k, cfg["bands"][k][0]), "4 risk points at": fmt_threshold(k, cfg["bands"][k][4])} for k in W])
    md = "| " + " | ".join(table.columns) + " |\n|" + "---|" * len(table.columns) + "\n" + "\n".join("| " + " | ".join(str(v) for v in r) + " |" for r in table.itertuples(index=False))
    st.markdown(md)
    trig = cfg["triggers"]
    st.markdown(
        "**Triggers that override the band**\n\n"
        "- Forces **Red**: operating cash flow is not positive while debt is outstanding.\n"
        f"- Forces at least **Amber**: capex above {trig['watch_amber']['capex_to_cfo_above']:.0%} of operating cash flow, or debt up by more than {trig['watch_amber']['debt_growth_above']:.0%} in a year."
    )
    st.caption("Weights and thresholds are judgment, not estimated from defaults. They live in config/score_config.yaml; change them and re-run `python run.py`.")

    st.subheader("Checks behind the numbers")
    with st.expander("Data QA report", expanded=False):
        st.markdown((OUT / "qa_report.md").read_text())
    with st.expander("Verifier mutation test", expanded=False):
        st.markdown((OUT / "mutation_report.md").read_text())

    st.subheader("Limits")
    st.markdown(
        "- The universe leaves out Oracle, CoreWeave and Super Micro (debt not cleanly tagged), so the aggregate looks calmer than the whole market.\n"
        "- Off-balance-sheet financing is not in reported debt.\n"
        "- Equinix is a REIT whose capex is growth spending, so it scores Red mainly on structure.\n"
        "- Share price drawdown is an equity signal, not a credit signal. Bond prices and credit default swap spreads are not used.\n"
        "- Fundamentals change only when a company files; prices come from an unofficial Yahoo endpoint.\n"
        "- The verifier results are regression tests of the checks, not an estimate of accuracy."
    )
