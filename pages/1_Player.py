"""
MetaMind — Page 1: Player Intelligence
Is this player currently performing at their peak, and how do they compare?
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.connection import get_engine
from db.queries import (
    get_all_players,
    get_all_tournaments,
    get_player_career_stats,
    get_player_form,
    get_player_percentiles,
    get_player_agent_breakdown,
    get_compare_players,
    get_dataset_averages,
    get_all_percentiles,
)
from analytics.consistency import compute_consistency_score
from analytics.form_engine import compute_form_status
from analytics.edge_score import compute_edge_score
from analytics.insights import generate_player_insights

st.set_page_config(page_title="Player Intelligence — MetaMind", layout="wide", page_icon="🧠")

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


# ── Helper functions ────────────────────────────────────────────────
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


def render_percentile_bar(label: str, percentile: float):
    """Render a horizontal percentile bar."""
    pct = min(100, max(0, percentile * 100))
    # Color gradient: red → amber → green
    if pct >= 75:
        color = "#3fb950"
    elif pct >= 50:
        color = "#d29922"
    else:
        color = "#f85149"
    st.markdown(
        f"""
        <div style="margin: 6px 0;">
            <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span style="color:#8b949e; font-size:0.82em;">{label}</span>
                <span style="color:{color}; font-size:0.82em; font-weight:600;">{pct:.0f}th percentile</span>
            </div>
            <div class="pct-bar-container">
                <div class="pct-bar-fill" style="width:{pct}%; background-color:{color};">
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_form_badge(status: str):
    """Render a colored form status badge."""
    css_class = {
        "PEAKING": "badge-peaking",
        "DECLINING": "badge-declining",
        "CONSISTENT": "badge-consistent",
    }.get(status, "badge-consistent")
    emoji = {"PEAKING": "🔥", "DECLINING": "📉", "CONSISTENT": "⚡"}.get(status, "⚡")
    st.markdown(
        f'<span class="badge {css_class}">{emoji} {status}</span>',
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
def load_players():
    return get_all_players(engine)


@st.cache_data(ttl=3600)
def load_tournaments():
    return get_all_tournaments(engine)


@st.cache_data(ttl=3600)
def load_averages():
    return get_dataset_averages(engine)


players_df = load_players()
tournaments_df = load_tournaments()

if players_df.empty:
    st.warning("No player data found. Run the ETL pipeline first.")
    st.stop()

# ── Sidebar filters ─────────────────────────────────────────────────
st.sidebar.markdown("## 📊 Player Intelligence")

player_names = sorted(players_df["name"].unique().tolist())
selected_player_name = st.sidebar.selectbox("Select Player", player_names, index=0)
selected_player = players_df[players_df["name"] == selected_player_name].iloc[0]
player_id = int(selected_player["player_id"])

tournament_options = ["All"] + sorted(tournaments_df["name"].unique().tolist())
selected_tournament = st.sidebar.selectbox("Tournament", tournament_options)
tournament_id = None
if selected_tournament != "All":
    t_row = tournaments_df[tournaments_df["name"] == selected_tournament].iloc[0]
    tournament_id = int(t_row["tournament_id"])

# ── Load player data ────────────────────────────────────────────────
career_stats = get_player_career_stats(engine, player_id, tournament_id=tournament_id)
form_data = get_player_form(engine, player_id, window=10)
percentile_data = get_player_percentiles(engine, player_id)
agent_data = get_player_agent_breakdown(engine, player_id)
averages = load_averages()

# ── Compute derived metrics ─────────────────────────────────────────
if not career_stats.empty:
    acs_values = career_stats["acs"].dropna().tolist()
    consistency = compute_consistency_score(acs_values)
    season_avg = career_stats["acs"].mean() if not career_stats.empty else 0
    acs_std = career_stats["acs"].std() if len(career_stats) > 1 else 0
    acs_mean = career_stats["acs"].mean()

    recent_acs = career_stats["acs"].dropna().tolist()
    form_status = compute_form_status(recent_acs, season_avg, acs_std, acs_mean)
else:
    consistency = None
    form_status = "CONSISTENT"
    season_avg = 0

# ── Layout: Two-column [1, 3] ──────────────────────────────────────
left_col, right_col = st.columns([1, 3])

# ════════════════════════════════════════════════════════════════════
# LEFT COLUMN — Player Info Panel
# ════════════════════════════════════════════════════════════════════
with left_col:
    st.markdown(f"## {selected_player_name}")

    # Region + nationality badge
    region = selected_player.get("region", "Unknown") or "Unknown"
    nationality = selected_player.get("nationality", "") or ""
    badge_text = region
    if nationality:
        badge_text = f"{region} · {nationality}"
        if nationality == "Indian":
            badge_text = f"🇮🇳 {badge_text}"
    st.markdown(f'<span class="badge badge-region">{badge_text}</span>', unsafe_allow_html=True)

    # Team name
    team_name = selected_player.get("team", "Unknown") or "Unknown"
    st.markdown(f"**Team:** {team_name}")

    # Matches played
    matches_count = len(career_stats)
    st.markdown(f"**Matches:** {matches_count}")

    # Agent pool pills
    if "agent_pool" in selected_player and selected_player["agent_pool"]:
        agents = selected_player["agent_pool"]
        if isinstance(agents, str):
            agents = [a.strip() for a in agents.strip("{}").split(",")]
        pills = " ".join([f'<span class="agent-pill">{a}</span>' for a in agents if a])
        st.markdown(f"**Agents:** {pills}", unsafe_allow_html=True)

    # Form status badge
    st.markdown("**Form Status:**")
    render_form_badge(form_status)

# ════════════════════════════════════════════════════════════════════
# RIGHT COLUMN — Analytics
# ════════════════════════════════════════════════════════════════════
with right_col:
    # ── Section A: Career KPIs ──────────────────────────────────────
    st.markdown("### Career Performance")

    if not career_stats.empty and not averages.empty:
        avg_row = averages.iloc[0]
        kpi_cols = st.columns(4)

        with kpi_cols[0]:
            avg_acs = career_stats["acs"].mean()
            delta_acs = avg_acs - float(avg_row.get("avg_acs", 0))
            render_kpi_card("Avg ACS", f"{avg_acs:.1f}", delta_acs)

        with kpi_cols[1]:
            avg_kd = career_stats["kd_ratio"].mean()
            delta_kd = avg_kd - float(avg_row.get("avg_kd", 0))
            render_kpi_card("K/D Ratio", f"{avg_kd:.2f}", delta_kd)

        with kpi_cols[2]:
            avg_kast = career_stats["kast"].mean()
            delta_kast = avg_kast - float(avg_row.get("avg_kast", 0))
            render_kpi_card("KAST %", f"{avg_kast:.1f}%", delta_kast)

        with kpi_cols[3]:
            cons_display = f"{consistency:.1f}" if consistency is not None else "N/A"
            render_kpi_card("Consistency", cons_display)

    # ── Section B: Percentile Rank Bars ─────────────────────────────
    st.markdown("### Percentile Rankings")

    if not percentile_data.empty:
        p = percentile_data.iloc[0]
        render_percentile_bar("ACS", float(p.get("acs_percentile", 0)))
        render_percentile_bar("K/D", float(p.get("kd_percentile", 0)))
        render_percentile_bar("First Kill %", float(p.get("fb_percentile", 0)))

        # Compute HS and KAST percentiles from full dataset
        all_pcts = get_all_percentiles(engine)
        if not all_pcts.empty:
            player_hs = float(p.get("avg_hs", 0))
            player_kast = float(p.get("avg_kast", 0))
            hs_pct = (all_pcts["avg_hs"] <= player_hs).mean()
            kast_pct = (all_pcts["avg_kast"] <= player_kast).mean()
            render_percentile_bar("Headshot %", hs_pct)
            render_percentile_bar("KAST", kast_pct)

    # ── Section C: Form Curve ───────────────────────────────────────
    st.markdown("### Form Curve")

    if not form_data.empty:
        metric_choice = st.radio(
            "Metric", ["ACS", "K/D", "Kills"], horizontal=True, key="form_metric"
        )
        metric_map = {"ACS": "acs", "K/D": "kd_ratio", "Kills": "kills"}
        rolling_map = {"ACS": "rolling_acs", "K/D": "rolling_kd", "Kills": "rolling_kills"}

        selected_metric = metric_map[metric_choice]
        selected_rolling = rolling_map[metric_choice]

        window_size = st.slider("Rolling window (matches)", 3, 20, 10, key="form_window")

        # Requery with selected window
        form_data = get_player_form(engine, player_id, window=window_size)

        if not form_data.empty:
            fig = go.Figure()

            # Main metric line
            fig.add_trace(go.Scatter(
                x=form_data["match_num"],
                y=form_data[selected_metric],
                mode="lines+markers",
                name=metric_choice,
                line=dict(color="#58a6ff", width=2),
                marker=dict(size=5, color="#58a6ff"),
            ))

            # Rolling average overlay
            if selected_rolling in form_data.columns:
                fig.add_trace(go.Scatter(
                    x=form_data["match_num"],
                    y=form_data[selected_rolling],
                    mode="lines",
                    name=f"{window_size}-match avg",
                    line=dict(color="#f0883e", width=2, dash="dot"),
                ))

            # Season average dashed line
            s_avg = form_data[selected_metric].mean()
            fig.add_hline(
                y=s_avg,
                line_dash="dash",
                line_color="#8b949e",
                annotation_text=f"Season avg: {s_avg:.1f}",
                annotation_font_color="#8b949e",
            )

            # Peak match marker
            peak_idx = form_data[selected_metric].idxmax()
            if pd.notna(peak_idx):
                peak_row = form_data.loc[peak_idx]
                fig.add_trace(go.Scatter(
                    x=[peak_row["match_num"]],
                    y=[peak_row[selected_metric]],
                    mode="markers",
                    name="Peak",
                    marker=dict(size=12, color="#d4a017", symbol="star"),
                    hovertext=f"Peak: {peak_row[selected_metric]:.1f}",
                ))

            # Shaded last 3 matches
            if len(form_data) >= 3:
                last_3 = form_data.tail(3)
                fig.add_vrect(
                    x0=last_3["match_num"].iloc[0] - 0.5,
                    x1=last_3["match_num"].iloc[-1] + 0.5,
                    fillcolor="#1f6feb",
                    opacity=0.1,
                    line_width=0,
                    annotation_text="Recent",
                    annotation_font_color="#58a6ff",
                )

            fig.update_layout(
                template=PLOTLY_TEMPLATE,
                height=400,
                margin=dict(l=40, r=20, t=30, b=40),
                legend=dict(orientation="h", y=1.1),
                xaxis_title="Match #",
                yaxis_title=metric_choice,
            )

            st.plotly_chart(fig, use_container_width=True)

    # ── Section D: Agent Performance Table ──────────────────────────
    st.markdown("### Agent Performance")

    if not agent_data.empty:
        display_df = agent_data[["agent", "matches_played", "avg_acs", "avg_kd", "win_rate"]].copy()
        display_df.columns = ["Agent", "Matches", "Avg ACS", "Avg K/D", "Win Rate %"]
        display_df = display_df.sort_values("Avg ACS", ascending=False)
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Avg ACS": st.column_config.NumberColumn(format="%.1f"),
                "Avg K/D": st.column_config.NumberColumn(format="%.2f"),
                "Win Rate %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

    # ── Section E: Compare with another player ──────────────────────
    with st.expander("🔀 Compare with another player", expanded=False):
        compare_names = [n for n in player_names if n != selected_player_name]
        if compare_names:
            compare_player_name = st.selectbox("Select opponent", compare_names, key="compare")
            compare_player = players_df[players_df["name"] == compare_player_name].iloc[0]
            compare_id = int(compare_player["player_id"])

            compare_data = get_compare_players(engine, player_id, compare_id)

            if len(compare_data) == 2:
                p_a = compare_data[compare_data["player_id"] == player_id].iloc[0]
                p_b = compare_data[compare_data["player_id"] == compare_id].iloc[0]

                # Radar chart — 5 metrics normalized 0-100
                categories = ["ACS", "K/D", "Consistency", "First Kill %", "KAST"]
                raw_a = [
                    float(p_a.get("avg_acs", 0)),
                    float(p_a.get("avg_kd", 0)),
                    float(p_a.get("consistency_score", 0)),
                    float(p_a.get("avg_fb", 0)),
                    float(p_a.get("avg_kast", 0)),
                ]
                raw_b = [
                    float(p_b.get("avg_acs", 0)),
                    float(p_b.get("avg_kd", 0)),
                    float(p_b.get("consistency_score", 0)),
                    float(p_b.get("avg_fb", 0)),
                    float(p_b.get("avg_kast", 0)),
                ]

                # Min-max normalize
                norm_a, norm_b = [], []
                for va, vb in zip(raw_a, raw_b):
                    mn, mx = min(va, vb), max(va, vb)
                    rng = mx - mn if mx != mn else 1
                    norm_a.append((va - mn) / rng * 100)
                    norm_b.append((vb - mn) / rng * 100)

                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=norm_a + [norm_a[0]],
                    theta=categories + [categories[0]],
                    fill="toself",
                    name=selected_player_name,
                    line_color="#58a6ff",
                    fillcolor="rgba(88,166,255,0.15)",
                    customdata=raw_a + [raw_a[0]],
                    hovertemplate="%{theta}: %{customdata:.1f}<extra></extra>",
                ))
                fig_radar.add_trace(go.Scatterpolar(
                    r=norm_b + [norm_b[0]],
                    theta=categories + [categories[0]],
                    fill="toself",
                    name=compare_player_name,
                    line_color="#f0883e",
                    fillcolor="rgba(240,136,62,0.15)",
                    customdata=raw_b + [raw_b[0]],
                    hovertemplate="%{theta}: %{customdata:.1f}<extra></extra>",
                ))
                fig_radar.update_layout(
                    template=PLOTLY_TEMPLATE,
                    polar=dict(
                        bgcolor="#0e1117",
                        radialaxis=dict(visible=True, range=[0, 100], gridcolor="#21262d"),
                        angularaxis=dict(gridcolor="#21262d"),
                    ),
                    height=400,
                    margin=dict(l=60, r=60, t=40, b=40),
                    legend=dict(orientation="h", y=-0.1),
                )
                st.plotly_chart(fig_radar, use_container_width=True)

                # Delta table
                delta_rows = []
                for i, cat in enumerate(categories):
                    d = raw_a[i] - raw_b[i]
                    delta_rows.append({
                        "Metric": cat,
                        selected_player_name: f"{raw_a[i]:.1f}",
                        compare_player_name: f"{raw_b[i]:.1f}",
                        "Delta": f"{'+' if d >= 0 else ''}{d:.1f}",
                    })
                st.dataframe(pd.DataFrame(delta_rows), use_container_width=True, hide_index=True)

                # Edge Score
                edge = compute_edge_score(
                    {
                        "avg_acs": raw_a[0], "avg_kd": raw_a[1],
                        "consistency_score": raw_a[2], "avg_fb": raw_a[3],
                        "avg_kast": raw_a[4],
                    },
                    {
                        "avg_acs": raw_b[0], "avg_kd": raw_b[1],
                        "consistency_score": raw_b[2], "avg_fb": raw_b[3],
                        "avg_kast": raw_b[4],
                    },
                )

                ec1, ec2 = st.columns(2)
                with ec1:
                    st.metric(
                        f"{selected_player_name} Edge Score",
                        f"{edge['player_a_score']:.1f}",
                        f"{edge['player_a_wins']}/5 categories",
                    )
                with ec2:
                    st.metric(
                        f"{compare_player_name} Edge Score",
                        f"{edge['player_b_score']:.1f}",
                        f"{edge['player_b_wins']}/5 categories",
                    )

    # ── Section F: Analyst Commentary ───────────────────────────────
    st.markdown("### 🎙️ Analyst Commentary")

    if not percentile_data.empty:
        p_data = percentile_data.iloc[0].to_dict()
        p_data["form_status"] = form_status
        p_data["consistency_score"] = consistency

        if not career_stats.empty:
            p_data["last_match_acs"] = career_stats["acs"].iloc[-1] if len(career_stats) > 0 else 0
            p_data["season_best_acs"] = career_stats["acs"].max()
            p_data["nationality"] = nationality

            # Compute India rank if Indian
            if nationality == "Indian":
                all_p = get_all_percentiles(engine)
                indian = all_p[all_p["nationality"] == "Indian"].sort_values("avg_acs", ascending=False)
                if not indian.empty:
                    rank = indian.index.get_loc(
                        indian[indian["player_id"] == player_id].index[0]
                    ) + 1 if player_id in indian["player_id"].values else None
                    p_data["india_rank"] = rank

        insights = generate_player_insights(p_data)
        if insights:
            for insight in insights:
                render_insight_card(insight)
        else:
            st.info("Not enough data to generate insights for this player.")
