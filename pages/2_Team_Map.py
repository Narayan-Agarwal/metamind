"""
MetaMind — Page 2: Team Map Strategy
What is this team's strategic identity — where do they win, how do they
manage economy, and what does their map profile look like?
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.connection import get_engine
from db.queries import (
    get_all_teams,
    get_all_tournaments,
    get_team_kpis,
    get_team_map_winrates,
    get_team_economy,
    get_team_players,
)
from analytics.insights import generate_team_insights

st.set_page_config(page_title="Team Map Strategy — MetaMind", layout="wide", page_icon="🗺️")

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


# ── Helpers ─────────────────────────────────────────────────────────
def render_kpi_card(label: str, value: str, delta: float | None = None):
    """Render a styled KPI card with optional delta."""
    delta_html = ""
    if delta is not None:
        color = "#3fb950" if delta >= 0 else "#f85149"
        sign = "+" if delta >= 0 else ""
        delta_html = f'<div style="color:{color}; font-size:0.85em">{sign}{delta:.1f} vs avg</div>'
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
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
def load_teams():
    return get_all_teams(engine)


@st.cache_data(ttl=3600)
def load_tournaments():
    return get_all_tournaments(engine)


teams_df = load_teams()
tournaments_df = load_tournaments()

if teams_df.empty:
    st.warning("No team data found. Run the ETL pipeline first.")
    st.stop()

# ── Sidebar filters ─────────────────────────────────────────────────
st.sidebar.markdown("## 🗺️ Team Map Strategy")

team_names = sorted(teams_df["name"].unique().tolist())
selected_team_name = st.sidebar.selectbox("Select Team", team_names, index=0)
selected_team = teams_df[teams_df["name"] == selected_team_name].iloc[0]
team_id = int(selected_team["team_id"])

tournament_options = ["All"] + sorted(tournaments_df["name"].unique().tolist())
selected_tournament = st.sidebar.selectbox("Tournament", tournament_options)
tournament_id = None
if selected_tournament != "All":
    t_row = tournaments_df[tournaments_df["name"] == selected_tournament].iloc[0]
    tournament_id = int(t_row["tournament_id"])

# ── Load team data ──────────────────────────────────────────────────
kpis = get_team_kpis(engine, team_id, tournament_id=tournament_id)
map_wr = get_team_map_winrates(engine, team_id)
economy = get_team_economy(engine, team_id)
players = get_team_players(engine, team_id)

# ════════════════════════════════════════════════════════════════════
# Section A — Team KPI cards
# ════════════════════════════════════════════════════════════════════
st.markdown(f"## {selected_team_name}")
region = selected_team.get("region", "Unknown") or "Unknown"
st.markdown(f'<span class="badge badge-region">{region}</span>', unsafe_allow_html=True)

st.markdown("### Key Performance Indicators")

if not kpis.empty:
    k = kpis.iloc[0]
    kpi_cols = st.columns(4)

    with kpi_cols[0]:
        render_kpi_card("Overall Win Rate", f"{k.get('overall_win_rate', 0) * 100:.1f}%")
    with kpi_cols[1]:
        render_kpi_card("Avg Rounds Won", f"{k.get('avg_rounds_won', 0):.1f}")
    with kpi_cols[2]:
        render_kpi_card("Avg Rounds Lost", f"{k.get('avg_rounds_lost', 0):.1f}")
    with kpi_cols[3]:
        render_kpi_card("Total Matches", f"{int(k.get('total_matches', 0))}")

# ════════════════════════════════════════════════════════════════════
# Section B — Map Win Rate bar chart
# ════════════════════════════════════════════════════════════════════
st.markdown("### Map Win Rates")

if not map_wr.empty:
    sorted_maps = map_wr.sort_values("win_pct", ascending=True)

    colors = []
    for wp in sorted_maps["win_pct"]:
        if wp >= 65:
            colors.append("#3fb950")
        elif wp >= 45:
            colors.append("#d29922")
        else:
            colors.append("#f85149")

    fig_bar = go.Figure(go.Bar(
        x=sorted_maps["win_pct"],
        y=sorted_maps["map_name"],
        orientation="h",
        marker_color=colors,
        text=[f"{wp:.1f}% ({gp} games)" for wp, gp in
              zip(sorted_maps["win_pct"], sorted_maps["games_played"])],
        textposition="auto",
        textfont=dict(color="#c9d1d9"),
    ))

    fig_bar.update_layout(
        template=PLOTLY_TEMPLATE,
        height=max(250, len(sorted_maps) * 50),
        margin=dict(l=80, r=20, t=10, b=30),
        xaxis_title="Win %",
        xaxis=dict(range=[0, 100]),
    )

    st.plotly_chart(fig_bar, use_container_width=True)

# ════════════════════════════════════════════════════════════════════
# Section C & D — Map DNA Radar + Attack vs Defense
# ════════════════════════════════════════════════════════════════════
col_radar, col_sides = st.columns(2)

with col_radar:
    st.markdown("### Map DNA Radar")

    if not map_wr.empty and len(map_wr) >= 3:
        categories = map_wr["map_name"].tolist()

        # Normalize each metric to 0-1
        def _normalize(series):
            mn, mx = series.min(), series.max()
            rng = mx - mn if mx != mn else 1
            return ((series - mn) / rng).tolist()

        win_norm = _normalize(map_wr["win_pct"])
        games_norm = _normalize(map_wr["games_played"])
        atk_norm = _normalize(map_wr["avg_atk_rounds"].fillna(0))
        def_norm = _normalize(map_wr["avg_def_rounds"].fillna(0))

        # Score margin (win% - 50 as proxy)
        margin = (map_wr["win_pct"] - 50).clip(lower=0)
        margin_norm = _normalize(margin)

        fig_radar = go.Figure()

        for dim_name, dim_data, raw_data in [
            ("Win %", win_norm, map_wr["win_pct"].tolist()),
            ("Games Played", games_norm, map_wr["games_played"].tolist()),
            ("Atk Rounds", atk_norm, map_wr["avg_atk_rounds"].fillna(0).tolist()),
            ("Def Rounds", def_norm, map_wr["avg_def_rounds"].fillna(0).tolist()),
            ("Score Margin", margin_norm, margin.tolist()),
        ]:
            fig_radar.add_trace(go.Scatterpolar(
                r=dim_data + [dim_data[0]],
                theta=categories + [categories[0]],
                fill="toself",
                name=dim_name,
                customdata=raw_data + [raw_data[0]],
                hovertemplate="%{theta}: %{customdata:.1f}<extra></extra>",
            ))

        fig_radar.update_layout(
            template=PLOTLY_TEMPLATE,
            polar=dict(
                bgcolor="#0e1117",
                radialaxis=dict(visible=True, range=[0, 1], gridcolor="#21262d"),
                angularaxis=dict(gridcolor="#21262d"),
            ),
            height=400,
            margin=dict(l=60, r=60, t=30, b=30),
            legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
        )

        st.plotly_chart(fig_radar, use_container_width=True)

with col_sides:
    st.markdown("### Attack vs Defense by Map")

    if not map_wr.empty:
        fig_sides = go.Figure()

        fig_sides.add_trace(go.Bar(
            name="Avg Attack Rounds",
            x=map_wr["map_name"],
            y=map_wr["avg_atk_rounds"].fillna(0),
            marker_color="#f0883e",
        ))

        fig_sides.add_trace(go.Bar(
            name="Avg Defense Rounds",
            x=map_wr["map_name"],
            y=map_wr["avg_def_rounds"].fillna(0),
            marker_color="#58a6ff",
        ))

        fig_sides.update_layout(
            template=PLOTLY_TEMPLATE,
            barmode="group",
            height=400,
            margin=dict(l=40, r=20, t=30, b=40),
            legend=dict(orientation="h", y=1.1),
            yaxis_title="Avg Rounds Won",
        )

        st.plotly_chart(fig_sides, use_container_width=True)

# ════════════════════════════════════════════════════════════════════
# Section E — Economy Analysis
# ════════════════════════════════════════════════════════════════════
st.markdown("### Economy Analysis")

if not economy.empty:
    econ_metrics = ["pistol_win_pct", "eco_win_pct", "semi_buy_win_pct", "full_buy_win_pct"]
    econ_labels = ["Pistol Win %", "Eco Win %", "Semi-buy Win %", "Full-buy Win %"]
    econ_colors = ["#f0883e", "#58a6ff", "#d29922", "#3fb950"]

    fig_econ = go.Figure()

    for metric, label, color in zip(econ_metrics, econ_labels, econ_colors):
        if metric in economy.columns:
            fig_econ.add_trace(go.Bar(
                name=label,
                x=economy["map_name"],
                y=economy[metric].fillna(0),
                marker_color=color,
            ))

    fig_econ.update_layout(
        template=PLOTLY_TEMPLATE,
        barmode="group",
        height=400,
        margin=dict(l=40, r=20, t=30, b=40),
        legend=dict(orientation="h", y=1.1),
        yaxis_title="Win %",
    )

    st.plotly_chart(fig_econ, use_container_width=True)

# ════════════════════════════════════════════════════════════════════
# Section F — Top Players on Team
# ════════════════════════════════════════════════════════════════════
st.markdown("### Top Players")

if not players.empty:
    display_cols = [c for c in ["name", "nationality", "avg_acs", "avg_kd",
                                 "consistency_score", "best_map"]
                    if c in players.columns]

    display_df = players[display_cols].copy()

    # Add flag emoji for Indian players
    if "nationality" in display_df.columns:
        display_df["nationality"] = display_df["nationality"].apply(
            lambda n: f"🇮🇳 {n}" if n == "Indian" else (n or "")
        )

    col_map = {
        "name": "Player",
        "nationality": "Nationality",
        "avg_acs": "Avg ACS",
        "avg_kd": "K/D",
        "consistency_score": "Consistency",
        "best_map": "Best Map",
    }
    display_df = display_df.rename(columns=col_map)

    if "Avg ACS" in display_df.columns:
        display_df = display_df.sort_values("Avg ACS", ascending=False)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Avg ACS": st.column_config.NumberColumn(format="%.1f"),
            "K/D": st.column_config.NumberColumn(format="%.2f"),
            "Consistency": st.column_config.NumberColumn(format="%.1f"),
        },
    )

# ════════════════════════════════════════════════════════════════════
# Section G — Analyst Commentary
# ════════════════════════════════════════════════════════════════════
st.markdown("### 🎙️ Analyst Commentary")

team_data = {}
if not map_wr.empty:
    best_map = map_wr.loc[map_wr["win_pct"].idxmax()]
    worst_map = map_wr.loc[map_wr["win_pct"].idxmin()]
    team_data["best_map"] = best_map["map_name"]
    team_data["best_map_wr"] = float(best_map["win_pct"])
    team_data["worst_map"] = worst_map["map_name"]
    team_data["worst_map_wr"] = float(worst_map["win_pct"])

if not economy.empty:
    team_data["avg_pistol_pct"] = float(economy.get("pistol_win_pct", pd.Series([0])).mean())
    team_data["avg_eco_pct"] = float(economy.get("eco_win_pct", pd.Series([0])).mean())
    team_data["avg_full_buy_pct"] = float(economy.get("full_buy_win_pct", pd.Series([0])).mean())

if not kpis.empty:
    k = kpis.iloc[0]
    team_data["overall_win_rate"] = float(k.get("overall_win_rate", 0))
    team_data["total_matches"] = int(k.get("total_matches", 0))

insights = generate_team_insights(team_data)
if insights:
    for insight in insights:
        render_insight_card(insight)
else:
    st.info("Not enough data to generate team insights.")
