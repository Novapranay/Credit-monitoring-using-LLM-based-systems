"""AI Leaders Credit Monitor: Streamlit dashboard. Run `python run.py` first, then `streamlit run app.py`."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

ROOT = Path(__file__).parent
OUT, PROC = ROOT / "output", ROOT / "data" / "processed"
COLORS = {"Green": "#2e7d32", "Amber": "#ef6c00", "Red": "#c62828", "Not rated": "#757575", "Pending first 10-Q": "#757575"}

st.set_page_config(page_title="AI Leaders Credit Monitor", layout="wide")
st.title("AI Leaders Credit Monitor")
st.caption("Is the AI buildout paid for by cash flow, or increasingly by debt? Public SEC filings and market prices. Not investment advice.")

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
st.caption(f"Newest filing in the data: {latest_filing}. Fundamentals update when a company files a 10-Q or 10-K; prices are daily.")


def badge(status: str) -> str:
    return f"<span style='background:{COLORS.get(status, '#757575')};color:white;padding:2px 10px;border-radius:10px;font-size:0.85em'>{status}</span>"


tab_watch, tab_co, tab_bubble, tab_method = st.tabs(["Watchlist", "Company", "AI-bubble lens", "Method and QA"])

with tab_watch:
    cols = st.columns(4)
    counts = watch["status"].value_counts()
    for c, s in zip(cols, ["Red", "Amber", "Green", "Pending first 10-Q"]):
        c.markdown(f"{badge(s)} &nbsp; **{int(counts.get(s, 0))}**", unsafe_allow_html=True)
    show = watch[["ticker", "name", "layer", "status", "score", "score_change", "watch_level", "net_debt_to_cfo", "capex_to_cfo", "fcf_to_debt",
                  "debt_growth_yoy", "current_ratio", "op_margin_change_yoy", "drawdown", "period_end", "top_alert"]].copy()
    for col in ["capex_to_cfo", "fcf_to_debt", "debt_growth_yoy", "op_margin_change_yoy", "drawdown"]:
        show[col] = show[col] * 100  # stored as fractions; the table prints percentages
    styled = show.style.map(lambda v: f"color:{COLORS.get(v, 'inherit')};font-weight:600" if v in COLORS else "", subset=["status"])
    st.dataframe(styled, hide_index=True, width="stretch", column_config={
        "ticker": "Ticker", "name": "Company", "layer": "Layer", "status": "Status", "watch_level": "Watch level", "period_end": "Period end",
        "score": st.column_config.NumberColumn("Risk score", format="%.0f", help="0 to 100, higher is riskier"),
        "score_change": st.column_config.NumberColumn("Change", format="%+.0f", help="Versus the prior quarter"),
        "net_debt_to_cfo": st.column_config.NumberColumn("Net debt / op. cash flow", format="%.1fx", help="Years of operating cash flow needed to repay net debt. Negative means net cash."),
        "capex_to_cfo": st.column_config.NumberColumn("Capex / op. cash flow", format="%.0f%%", help="Above 100% the buildout is funded from reserves or new debt"),
        "fcf_to_debt": st.column_config.NumberColumn("FCF / debt", format="%.0f%%"),
        "debt_growth_yoy": st.column_config.NumberColumn("Debt growth y/y", format="%.0f%%"),
        "current_ratio": st.column_config.NumberColumn("Current ratio", format="%.2fx"),
        "op_margin_change_yoy": st.column_config.NumberColumn("Op. margin chg y/y", format="%.1f%%"),
        "drawdown": st.column_config.NumberColumn("Drawdown from 1y high", format="%.0f%%"),
        "top_alert": "Top alert"})
    st.caption("Status bands: Green below 30, Amber 30 to 55, Red above 55; hard and watch triggers can override.")
    st.subheader("Alerts")
    sev = st.multiselect("Severity", ["high", "medium", "info"], default=["high", "medium"])
    st.dataframe(alerts[alerts["severity"].isin(sev)], hide_index=True, width="stretch")

with tab_co:
    names = dict(zip(watch["ticker"], watch["name"]))
    t = st.selectbox("Company", list(names), format_func=lambda x: f"{x}: {names[x]}")
    row = watch[watch["ticker"] == t].iloc[0]
    st.markdown(f"### {row['name']} &nbsp; {badge(row['status'])}", unsafe_allow_html=True)
    st.write(f"{row['layer']}. {row['angle']}.")
    if row["status"] == "Pending first 10-Q":
        st.info("Anthropic listed in November 2026 and has only filed a registration statement, so there are no quarterly financials to score yet. It will be scored on the first run after its first 10-Q appears in the SEC data.")
    else:
        m = metrics[metrics["ticker"] == t].sort_values("end")
        s = scores[scores["ticker"] == t].sort_values("end")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Risk score", f"{row['score']:.0f}", None if pd.isna(row["score_change"]) else f"{row['score_change']:+.0f} vs prior quarter", delta_color="inverse")
        c2.metric("Net debt / op. cash flow", "net cash" if row["net_debt"] <= 0 else f"{row['net_debt_to_cfo']:.1f}x")
        c3.metric("Capex / op. cash flow", f"{row['capex_to_cfo']:.0%}")
        c4.metric("Debt growth y/y", "n/a" if pd.isna(row["debt_growth_yoy"]) else f"{row['debt_growth_yoy']:.0%}")
        left, right = st.columns(2)
        fig = go.Figure(go.Scatter(x=s["end"], y=s["score"], mode="lines+markers", line=dict(color="#1565c0")))
        fig.add_hrect(y0=0, y1=cfg["status"]["green_below"], fillcolor="#2e7d32", opacity=0.08, line_width=0)
        fig.add_hrect(y0=cfg["status"]["green_below"], y1=cfg["status"]["red_above"], fillcolor="#ef6c00", opacity=0.08, line_width=0)
        fig.add_hrect(y0=cfg["status"]["red_above"], y1=100, fillcolor="#c62828", opacity=0.08, line_width=0)
        fig.update_layout(title="Risk score history (0 to 100)", yaxis=dict(range=[0, 100]), height=320, margin=dict(t=40, b=20))
        left.plotly_chart(fig, width="stretch")
        fig2 = go.Figure()
        fig2.add_bar(x=m["end"], y=m["cfo"] / 1e9, name="Operating cash flow (TTM)", marker_color="#2e7d32")
        fig2.add_bar(x=m["end"], y=m["capex"] / 1e9, name="Capex (TTM)", marker_color="#ef6c00")
        fig2.add_scatter(x=m["end"], y=m["debt"] / 1e9, name="Debt", line=dict(color="#c62828"))
        fig2.update_layout(title="Cash flow, capex and debt ($bn)", barmode="group", height=320, margin=dict(t=40, b=20), legend=dict(orientation="h", y=-0.12))
        right.plotly_chart(fig2, width="stretch")
        if row["triggers"] and isinstance(row["triggers"], str):
            st.warning(row["triggers"])
        note = OUT / "notes" / f"{t}.md"
        if note.exists():
            st.markdown(note.read_text())
        else:
            st.info("No verified note for this company. See output/needs_review/ for the failed draft.")

with tab_bubble:
    st.subheader("Is the buildout paid for by cash flow or by debt?")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TTM capex", f"${summary['capex'] / 1e9:,.0f}bn")
    c2.metric("TTM operating cash flow", f"${summary['cfo'] / 1e9:,.0f}bn")
    c3.metric("Total debt", f"${summary['debt'] / 1e9:,.0f}bn", f"{summary['debt_growth']:+.0%} year on year", delta_color="inverse")
    c4.metric("Spend more than they earn", f"{summary['outspending']} of {summary['companies']}", ", ".join(summary["outspending_names"]), delta_color="off")
    l = lens.sort_values("capex", ascending=False)
    fig = go.Figure()
    fig.add_bar(x=l["ticker"], y=l["cfo"] / 1e9, name="Operating cash flow (TTM)", marker_color="#2e7d32")
    fig.add_bar(x=l["ticker"], y=l["capex"] / 1e9, name="Capex (TTM)", marker_color="#ef6c00")
    fig.update_layout(title="Capex vs operating cash flow ($bn)", barmode="group", height=380, legend=dict(orientation="h", y=-0.12))
    st.plotly_chart(fig, width="stretch")
    fig = go.Figure()
    fig.add_bar(x=l["ticker"], y=l["prior_debt"] / 1e9, name="Debt a year earlier", marker_color="#90a4ae")
    fig.add_bar(x=l["ticker"], y=l["debt"] / 1e9, name="Debt now", marker_color="#c62828")
    fig.update_layout(title="Debt now vs a year earlier ($bn)", barmode="group", height=380, legend=dict(orientation="h", y=-0.12))
    st.plotly_chart(fig, width="stretch")
    st.caption("Limits: reported debt excludes off-balance-sheet financing such as data-centre joint ventures and leases not yet started. Oracle, CoreWeave and Super Micro are not included because their recent filings do not tag total debt cleanly.")

with tab_method:
    st.subheader("Scorecard")
    w = cfg["weights"]
    table = pd.DataFrame([{"Metric": k, "Weight": w[k], "0 risk points at": cfg["bands"][k][0], "4 risk points at": cfg["bands"][k][4]} for k in w])
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption("Points are linear between the five band thresholds in config/score_config.yaml. Weights and bands are judgment-based, not estimated.")
    st.subheader("Data QA")
    st.markdown((OUT / "qa_report.md").read_text())
    st.subheader("Verifier mutation test")
    st.markdown((OUT / "mutation_report.md").read_text())
