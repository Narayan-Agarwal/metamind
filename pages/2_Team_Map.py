import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text
from db.connection import get_engine
from db.queries import (
    get_all_teams, get_team_players, get_team_aggregate_stats,
    get_team_agent_usage, get_global_team_stats
)
from utils.styles import GLOBAL_CSS, PLOTLY_THEME, render_nav

st.set_page_config(page_title="Team Analytics", layout="wide", initial_sidebar_state="collapsed")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
render_nav(active_page='/Team_Map')

st.markdown('<div class="main-content">', unsafe_allow_html=True)

engine = get_engine()

teams_df = get_all_teams(engine)
if teams_df.empty:
    st.error("No teams found in database.")
    st.stop()

team_map = dict(zip(teams_df['name'], teams_df['team_id']))
selected_team = st.selectbox("Select Team", sorted(team_map.keys()))
team_id = team_map[selected_team]

agg = get_team_aggregate_stats(engine, team_id)
players = get_team_players(engine, team_id)
agents = get_team_agent_usage(engine, team_id)

if players.empty:
    st.warning(
        f"No player data found for {selected_team}."
        " Try a different team.")
    st.info("Note: Only teams with tracked players "
            "in the VCT dataset are shown below.")
    st.stop()

# SECTION A
best = players.iloc[0]
top_pct = 100 - int((best['acs_percentile'] or 0) * 100)
summary = (
    f"{selected_team} fields {int(agg['player_count'].iloc[0])} "
    f"tracked players with a team average ACS of {agg['team_avg_acs'].iloc[0]}. "
    f"Star performer: {best['name']} (ACS {best['avg_acs']}, top {top_pct}% globally)."
)

st.markdown(f"""
<div class="hero-card" style="border-left: 4px solid #F5C518;">
    <div class="hero-player-name">{selected_team}</div>
    <div class="hero-summary">{summary}</div>
</div>
""", unsafe_allow_html=True)

# SECTION B
t_acs = agg['team_avg_acs'].iloc[0]
t_kd = agg['team_avg_kd'].iloc[0]
t_kast = agg['team_avg_kast'].iloc[0]
p_count = agg['player_count'].iloc[0]

st.markdown(f"""
<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px;">
    <div class="stat-card" style="border-top-color:#F5C518;"><div class="stat-label">Team Avg ACS</div><div class="stat-value" style="color:#F5C518;">{t_acs}</div></div>
    <div class="stat-card" style="border-top-color:#00D4FF;"><div class="stat-label">Team Avg K/D</div><div class="stat-value" style="color:#00D4FF;">{t_kd}</div></div>
    <div class="stat-card" style="border-top-color:#7F77DD;"><div class="stat-label">Team Avg KAST</div><div class="stat-value" style="color:#7F77DD;">{t_kast}%</div></div>
    <div class="stat-card"><div class="stat-label">Players Tracked</div><div class="stat-value">{p_count}</div></div>
</div>
""", unsafe_allow_html=True)

# SECTION C
st.markdown('<div class="section-title">ROSTER PERFORMANCE</div>', unsafe_allow_html=True)

lb_html = f"""
<div class="lb-table">
    <div class="lb-header" style="grid-template-columns:1fr 100px 100px 100px 120px 100px;">
        <div>PLAYER</div>
        <div style="text-align:right;">ACS</div>
        <div style="text-align:right;">K/D</div>
        <div style="text-align:right;">KAST</div>
        <div style="text-align:right;">CONSISTENCY</div>
        <div style="text-align:right;">MATCHES</div>
    </div>
"""

for i, row in players.iterrows():
    is_top = (i == 0)
    row_style = "border-left: 3px solid #F5C518;" if is_top else "border-left: 3px solid transparent;"
    
    name_disp = row['name']
    if row['nationality'] == 'Indian':
        name_disp += " 🇮🇳"
        
    cons = float(row['consistency_score'] or 0)
    cons_color = "#00D4FF" if cons > 80 else "#F5C518" if cons >= 60 else "#FF4757"
    
    lb_html += f"""
    <div class="lb-row" style="grid-template-columns:1fr 100px 100px 100px 120px 100px; {row_style}">
        <div class="lb-name">{name_disp}</div>
        <div class="lb-stat highlight">{row['avg_acs']:.1f}</div>
        <div class="lb-stat">{row['avg_kd']:.2f}</div>
        <div class="lb-stat">{row['avg_kast']:.1f}%</div>
        <div class="lb-stat" style="color:{cons_color};">{cons:.1f}</div>
        <div class="lb-stat" style="color:#888899;">{row['matches_played']}</div>
    </div>
    """
lb_html += "</div>"
st.markdown(lb_html, unsafe_allow_html=True)

# SECTION D & E
cols = st.columns(2)

with cols[0]:
    st.markdown('<div class="section-title">AGENT DNA</div>', unsafe_allow_html=True)
    if not agents.empty:
        agents_rev = agents.iloc[::-1]
        fig_agent = go.Figure(go.Bar(
            x=agents_rev['avg_acs_on_agent'],
            y=agents_rev['agent'],
            orientation='h',
            marker=dict(
                color='#F5C518',
                line=dict(color='rgba(245,197,24,0.5)', width=1)
            ),
            text=agents_rev['times_played'].apply(lambda x: f"{x}x"),
            textposition='inside',
            insidetextanchor='end',
            textfont=dict(color='#1C1C24', family='Inter')
        ))
        fig_agent.update_layout(
            **PLOTLY_THEME,
            title="Avg ACS by Agent",
            title_font=dict(color='#EAEAEA', family='Rajdhani', size=16),
            height=350,
            showlegend=False
        )
        st.plotly_chart(fig_agent, use_container_width=True)
        
with cols[1]:
    st.markdown('<div class="section-title">GLOBAL RANKING</div>', unsafe_allow_html=True)
    global_teams = get_global_team_stats(engine)
    if not global_teams.empty:
        global_teams['rank'] = global_teams['team_avg_acs'].rank(ascending=False, method='min')
        t_rank_row = global_teams[global_teams['team_id'] == team_id]
        
        if not t_rank_row.empty:
            t_rank = int(t_rank_row.iloc[0]['rank'])
            st.markdown(f'<div style="color:#888899; font-size:14px; margin-bottom:10px;">Ranked <b>#{t_rank}</b> of {len(global_teams)} teams by average ACS</div>', unsafe_allow_html=True)
            
            top_teams = global_teams.head(10).copy()
            if t_rank > 10:
                top_teams = pd.concat([top_teams, t_rank_row])
            
            top_teams = top_teams.sort_values('team_avg_acs', ascending=True)
            
            colors = ['#F5C518' if r['team_id'] == team_id else '#2E2E3A' for _, r in top_teams.iterrows()]
            
            fig_rank = go.Figure(go.Bar(
                x=top_teams['team_avg_acs'],
                y=top_teams['team_name'],
                orientation='h',
                marker_color=colors,
                text=top_teams['team_avg_acs'],
                textposition='outside',
                textfont=dict(color='#888899', size=11)
            ))
            fig_rank.update_layout(
                **PLOTLY_THEME,
                height=350,
                showlegend=False,
                margin=dict(l=100, r=20, t=20, b=40)
            )
            st.plotly_chart(fig_rank, use_container_width=True)

# SECTION F
st.markdown('<div class="section-title">ANALYST INSIGHTS</div>', unsafe_allow_html=True)
if not agents.empty:
    top_agent = agents.iloc[0]['agent']
    n = agents.iloc[0]['times_played']
    acs = agents.iloc[0]['avg_acs_on_agent']
    st.markdown(f'<div class="insight">🎮 <b>{selected_team}</b>\'s most played agent is <b>{top_agent}</b> — used {n} times with avg ACS of {acs}</div>', unsafe_allow_html=True)

with engine.connect() as conn:
    g_avg = conn.execute(text("SELECT AVG(avg_acs) FROM mv_player_percentiles")).scalar()
    if g_avg:
        g_avg = float(g_avg)
        above_below = "above" if t_acs > g_avg else "below"
        st.markdown(f'<div class="insight">📊 <b>{selected_team}</b> sits {above_below} the global player average (ACS {g_avg:.0f})</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
