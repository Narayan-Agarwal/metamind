"""
MetaMind — Page 3: Tournament Leaderboard
Who are the best performers globally, and where does each region stand?
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.connection import get_engine
from db.queries import (
    get_all_tournaments,
    get_leaderboard,
    get_regional_comparison,
    get_indian_spotlight,
)
from analytics.insights import generate_leaderboard_insights

st.set_page_config(page_title="Tournament Leaderboard — MetaMind", layout="wide", page_icon="🏆")

# ── Dark Plotly template ────────────────────────────────────────────
PLOTLY_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#c9d1d9", family="Inter, sans-serif"),
        xaxis=dict(gridcolor="#21262d", zerolinecolor="#21262d"),
        yaxis=dict(gridcolor="#21262d", zerolinecolor="#21262d"),
    )
)


def render_insight_card(insight: dict):
    """Render an analyst commentary card."""
    st.markdown(
        f"""
        <div class="insight-card">
            <div class="insight-title">{insight.get('icon', '💡')} {insight.get('title', '')}</div>
            <div class="insight-body">{insight.get('body', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Load data ───────────────────────────────────────────────────────
try:
    engine = get_engine()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()


@st.cache_data(ttl=3600)
def load_tournaments():
    return get_all_tournaments(engine)


tournaments_df = load_tournaments()

# ── Sidebar filters ─────────────────────────────────────────────────
st.sidebar.markdown("## 🏆 Tournament Leaderboard")

tournament_options = ["All"] + sorted(tournaments_df["name"].unique().tolist()) if not tournaments_df.empty else ["All"]
selected_tournament = st.sidebar.selectbox("Tournament", tournament_options)
tournament_id = None
if selected_tournament != "All" and not tournaments_df.empty:
    t_row = tournaments_df[tournaments_df["name"] == selected_tournament].iloc[0]
    tournament_id = int(t_row["tournament_id"])

region_options = ["All", "Americas", "EMEA", "Pacific", "Korea", "South Asia"]
selected_region = st.sidebar.selectbox("Region", region_options)
region = selected_region if selected_region != "All" else None

min_matches = st.sidebar.slider("Minimum Matches", 5, 30, 10)

sort_options = {
    "ACS": "avg_acs",
    "K/D": "avg_kd",
    "Consistency Score": "consistency_score",
    "KAST": "avg_kast",
    "First Kill %": "avg_fb",
}
sort_label = st.sidebar.selectbox("Sort by", list(sort_options.keys()))
sort_column = sort_options[sort_label]

# ════════════════════════════════════════════════════════════════════
# Section A — Region Comparison
# ════════════════════════════════════════════════════════════════════
st.markdown("## Regional Performance Comparison")

regional = get_regional_comparison(engine)

if not regional.empty:
    fig_region = go.Figure()

    fig_region.add_trace(go.Bar(
        name="Avg ACS",
        x=regional["region"],
        y=regional["avg_acs"],
        marker_color="#58a6ff",
    ))

    fig_region.add_trace(go.Bar(
        name="Avg K/D (×100)",
        x=regional["region"],
        y=regional["avg_kd"] * 100,
        marker_color="#f0883e",
    ))

    fig_region.add_trace(go.Bar(
        name="Avg Consistency",
        x=regional["region"],
        y=regional["avg_consistency"],
        marker_color="#3fb950",
    ))

    fig_region.update_layout(
        template=PLOTLY_TEMPLATE,
        barmode="group",
        height=400,
        margin=dict(l=40, r=20, t=30, b=40),
        legend=dict(orientation="h", y=1.1),
        yaxis_title="Value",
    )

    st.plotly_chart(fig_region, use_container_width=True)

# ════════════════════════════════════════════════════════════════════
# Section B — Indian Player Spotlight
# ════════════════════════════════════════════════════════════════════
indian = get_indian_spotlight(engine)

if not indian.empty:
    st.markdown("### 🇮🇳 India's Top Performers — Global Percentile Ranking")

    top_3 = indian.head(3)

    cols = st.columns(len(top_3))
    for i, (_, row) in enumerate(top_3.iterrows()):
        with cols[i]:
            acs_pct = float(row.get("acs_percentile", 0)) * 100
            st.markdown(
                f"""
                <div class="kpi-card" style="text-align:center;">
                    <div class="kpi-label" style="font-size:1.1em; font-weight:700;">
                        🇮🇳 {row.get('name', 'Unknown')}
                    </div>
                    <div style="color:#8b949e; font-size:0.85em;">{row.get('team', '') or 'Free Agent'}</div>
                    <div class="kpi-value" style="margin-top:8px;">ACS {row.get('avg_acs', 0):.1f}</div>
                    <div style="color:#3fb950; font-size:0.9em;">
                        {acs_pct:.0f}th percentile globally
                    </div>
                    <div style="color:#8b949e; font-size:0.82em; margin-top:4px;">
                        Consistency: {row.get('consistency_score', 0):.1f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ════════════════════════════════════════════════════════════════════
# Section C — Global Leaderboard Table
# ════════════════════════════════════════════════════════════════════
st.markdown("### Global Leaderboard")

# Pagination
page_size = 25
total_df = get_leaderboard(engine, sort_by=sort_column, region=region, min_matches=min_matches, limit=500)

if not total_df.empty:
    total_pages = max(1, (len(total_df) + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    start_idx = (page - 1) * page_size
    page_df = total_df.iloc[start_idx:start_idx + page_size].copy()

    # Add rank column
    page_df.insert(0, "Rank", range(start_idx + 1, start_idx + 1 + len(page_df)))

    # Add nationality flag
    if "nationality" in page_df.columns:
        page_df["nationality"] = page_df["nationality"].apply(
            lambda n: f"🇮🇳" if n == "Indian" else (f"🌍" if n else "🌍")
        )

    # Prepare display columns
    display_cols = [c for c in [
        "Rank", "name", "nationality", "team", "region",
        "avg_acs", "avg_kd", "consistency_score", "avg_kast",
        "avg_fb", "matches_played"
    ] if c in page_df.columns]

    display_df = page_df[display_cols].copy()

    col_rename = {
        "name": "Player",
        "nationality": "🏳️",
        "team": "Team",
        "region": "Region",
        "avg_acs": "Avg ACS",
        "avg_kd": "K/D",
        "consistency_score": "Consistency",
        "avg_kast": "KAST %",
        "avg_fb": "First Kill %",
        "matches_played": "Matches",
    }
    display_df = display_df.rename(columns=col_rename)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Avg ACS": st.column_config.NumberColumn(format="%.1f"),
            "K/D": st.column_config.NumberColumn(format="%.2f"),
            "Consistency": st.column_config.NumberColumn(format="%.1f"),
            "KAST %": st.column_config.NumberColumn(format="%.1f"),
            "First Kill %": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    st.caption(f"Showing {start_idx + 1}–{min(start_idx + page_size, len(total_df))} of {len(total_df)} players (min {min_matches} matches)")

else:
    st.warning("No data available for the selected filters.")

# ════════════════════════════════════════════════════════════════════
# Section D — Analyst Commentary
# ════════════════════════════════════════════════════════════════════
st.markdown("### 🎙️ Analyst Commentary")

leaderboard_data = {}
if not total_df.empty:
    top_player = total_df.iloc[0]
    leaderboard_data["top_player_name"] = top_player.get("name", "Unknown")
    leaderboard_data["top_player_acs"] = float(top_player.get("avg_acs", 0))
    leaderboard_data["top_player_matches"] = int(top_player.get("matches_played", 0))

if not regional.empty:
    most_consistent = regional.loc[regional["avg_consistency"].idxmax()]
    global_avg = regional["avg_consistency"].mean()
    leaderboard_data["most_consistent_region"] = most_consistent["region"]
    leaderboard_data["most_consistent_score"] = float(most_consistent["avg_consistency"])
    leaderboard_data["global_avg_consistency"] = float(global_avg)

if not indian.empty:
    top_indian = indian.iloc[0]
    leaderboard_data["top_indian_name"] = top_indian.get("name", "Unknown")
    leaderboard_data["top_indian_acs"] = float(top_indian.get("avg_acs", 0))
    leaderboard_data["top_indian_percentile"] = float(top_indian.get("acs_percentile", 0)) * 100

    # Find global rank
    if not total_df.empty:
        global_sorted = total_df.sort_values("avg_acs", ascending=False).reset_index(drop=True)
        indian_idx = global_sorted[global_sorted["name"] == top_indian["name"]].index
        if len(indian_idx) > 0:
            leaderboard_data["top_indian_rank"] = int(indian_idx[0]) + 1

insights = generate_leaderboard_insights(leaderboard_data)
if insights:
    for insight in insights:
        render_insight_card(insight)
else:
    st.info("Not enough data to generate leaderboard insights.")
