import streamlit as st
import plotly.graph_objects as go
from db.connection import get_engine
from db.queries import get_all_players, get_player_percentiles, get_player_stats, get_team_agent_usage
from utils.styles import GLOBAL_CSS, PLOTLY_THEME, AXIS_STYLE, render_nav
import pandas as pd

st.set_page_config(page_title="Player Comparison", layout="wide", initial_sidebar_state="collapsed")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
render_nav(active_page='/Team_Map')

st.markdown('<div class="main-content">', unsafe_allow_html=True)

engine = get_engine()

@st.cache_data(ttl=3600)
def load_players():
    return get_all_players(engine)

players_df = load_players()
if players_df.empty:
    st.error("No player data found.")
    st.stop()

player_names = sorted(players_df['name'].tolist())

st.markdown('<div class="section-title">PLAYER COMPARISON</div>', unsafe_allow_html=True)
st.caption("Select up to 3 players to compare their performance profiles head-to-head.")

col1, col2, col3 = st.columns(3)
with col1:
    p1_name = st.selectbox("Player 1", ["— select —"] + player_names, key="p1")
with col2:
    p2_name = st.selectbox("Player 2", ["— select —"] + player_names, key="p2")
with col3:
    p3_name = st.selectbox("Player 3 (optional)", ["— select —"] + player_names, key="p3")

selected = [n for n in [p1_name, p2_name, p3_name] if n != "— select —"]

if len(selected) < 2:
    st.info("Select at least 2 players to compare.")
    st.stop()

pct_data = {}
for name in selected:
    pid = int(players_df[players_df['name'] == name]['player_id'].iloc[0])
    pct_df = get_player_percentiles(engine, pid)
    if pct_df is not None and not pct_df.empty:
        pct_data[name] = pct_df.iloc[0]

if len(pct_data) < 2:
    st.warning("Not enough percentile data for selected players.")
    st.stop()

# KPI comparison table
st.markdown('<div class="section-title">HEAD-TO-HEAD STATS</div>', unsafe_allow_html=True)
kpi_cols = st.columns(len(pct_data))
for i, (name, pct) in enumerate(pct_data.items()):
    with kpi_cols[i]:
        st.metric("Player", name)
        st.metric("Avg ACS", f"{float(pct['avg_acs'] or 0):.1f}")
        st.metric("KAST %", f"{float(pct['avg_kast'] or 0):.1f}")
        st.metric("Consistency", f"{float(pct['consistency_score'] or 0):.1f}")
        st.metric("Matches", int(pct['matches_played'] or 0))

# Radar comparison chart
st.markdown('<div class="section-title">RADAR COMPARISON</div>', unsafe_allow_html=True)

radar_cats = ['ACS Rank', 'KAST %', 'Consistency', 'Experience', 'First Kill']
radar_colors = ['#F5C518', '#00D4FF', '#FF4757']

fig = go.Figure()
for i, (name, pct) in enumerate(pct_data.items()):
    vals = [
        float(pct['acs_percentile'] or 0) * 100,
        float(pct['avg_kast'] or 0),
        float(pct['consistency_score'] or 0),
        min(float(pct['matches_played'] or 0) / 50 * 100, 100),
        float(pct['avg_fb'] or 0) * 100
    ]
    vals_closed = vals + [vals[0]]
    cats_closed = radar_cats + [radar_cats[0]]
    color = radar_colors[i % len(radar_colors)]
    fig.add_trace(go.Scatterpolar(
        r=vals_closed,
        theta=cats_closed,
        fill='toself',
        fillcolor=f'rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15)',
        line=dict(color=color, width=2),
        marker=dict(size=6, color=color),
        name=name
    ))

fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    polar=dict(
        bgcolor='#1C1C24',
        radialaxis=dict(visible=True, range=[0, 100], gridcolor='#2E2E3A', color='#888899', tickfont=dict(size=10)),
        angularaxis=dict(gridcolor='#2E2E3A', color='#EAEAEA', tickfont=dict(size=12, family='Rajdhani'))
    ),
    showlegend=True,
    legend=dict(font=dict(color='#EAEAEA'), bgcolor='rgba(0,0,0,0)'),
    height=500,
    margin=dict(l=60, r=60, t=40, b=40),
    font=dict(color='#888899', family='Inter', size=11)
)
st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)
