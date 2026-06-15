import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db.connection import get_engine
from db.queries import get_all_teams, get_team_map_stats

st.set_page_config(page_title="Team Map Strategy", layout="wide", initial_sidebar_state="collapsed")

try:
    with open("app.py", "r", encoding="utf-8") as f:
        content = f.read()
        css_start = content.find('GLOBAL_CSS = """') + 16
        css_end = content.find('"""', css_start)
        st.markdown(content[css_start:css_end], unsafe_allow_html=True)
except Exception:
    pass

PLOTLY_DARK = dict(
    paper_bgcolor='#0A0A0F',
    plot_bgcolor='#0A0A0F',
    font=dict(color='#8888AA', family='Inter'),
    xaxis=dict(gridcolor='#2A2A45', linecolor='#2A2A45', tickcolor='#8888AA'),
    yaxis=dict(gridcolor='#2A2A45', linecolor='#2A2A45', tickcolor='#8888AA'),
    hoverlabel=dict(bgcolor='#111118', bordercolor='#7F77DD', font=dict(color='#EEEEF5'))
)

def render_nav(active='Team_Map'):
    pages = [('home','⚡ Home'), ('Player','Player'), ('Team_Map','Team Map'), ('Leaderboard','Leaderboard')]
    links = "".join([f'<span class="topnav-link {"active" if p==active else ""}" onclick="window.parent.location.href=\'/{p}\'">{label}</span>' for p,label in pages])
    st.markdown(f'<div class="topnav"><div class="topnav-logo"><span>META</span>MIND</div><div class="topnav-links">{links}</div></div>', unsafe_allow_html=True)

render_nav('Team_Map')

engine = get_engine()

@st.cache_data(ttl=3600)
def load_teams():
    return get_all_teams(engine)

teams_df = load_teams()
if teams_df.empty:
    st.error("No team data found.")
    st.stop()

team_options = teams_df['name'].tolist()
selected_team = st.selectbox("Select Team", team_options)

if selected_team:
    t_row = teams_df[teams_df['name'] == selected_team].iloc[0]
    tid = int(t_row['team_id'])
    
    map_stats = get_team_map_stats(engine, tid)
    
    if not map_stats.empty:
        # Calculate globals
        total_wins = map_stats['wins'].sum()
        total_played = map_stats['matches_played'].sum()
        overall_wr = (total_wins / total_played * 100) if total_played > 0 else 0
        
        best_map_row = map_stats.iloc[0]
        worst_map_row = map_stats.iloc[-1]
        
        best_map = best_map_row['map_name']
        best_pct = float(best_map_row['win_pct'])
        worst_map = worst_map_row['map_name']
        worst_pct = float(worst_map_row['win_pct'])
        
        avg_atk = map_stats['avg_atk_rounds'].mean()
        avg_def = map_stats['avg_def_rounds'].mean()
        
        st.markdown(f"""
        <div class="hero-card">
            <div class="hero-name">{selected_team}</div>
            <div class="hero-summary">
                {selected_team} dominates {best_map} ({best_pct:.1f}% win rate) but struggles on {worst_map} ({worst_pct:.1f}%). 
                Overall: {int(total_wins)}/{int(total_played)} maps won.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # C) KPI Row
        kpi_html = f"""
        <div style="display:grid; grid-template-columns:repeat(5,1fr); gap:16px; margin-bottom:24px;">
            <div class="kpi-card"><div class="kpi-label">Win Rate</div><div class="kpi-value">{overall_wr:.1f}%</div></div>
            <div class="kpi-card"><div class="kpi-label">Best Map</div><div class="kpi-value" style="font-size:24px;">{best_map}</div></div>
            <div class="kpi-card"><div class="kpi-label">Worst Map</div><div class="kpi-value" style="font-size:24px;">{worst_map}</div></div>
            <div class="kpi-card"><div class="kpi-label">Attack Win%</div><div class="kpi-value">{avg_atk/(avg_atk+avg_def)*100:.1f}%</div></div>
            <div class="kpi-card"><div class="kpi-label">Defense Win%</div><div class="kpi-value">{avg_def/(avg_atk+avg_def)*100:.1f}%</div></div>
        </div>
        """
        st.markdown(kpi_html, unsafe_allow_html=True)
        
        cols = st.columns([1, 2])
        
        with cols[0]:
            st.markdown('<div class="section-header">Map Win Rates</div>', unsafe_allow_html=True)
            map_html = ""
            for _, r in map_stats.iterrows():
                m_name = r['map_name']
                w_pct = float(r['win_pct'])
                played = int(r['matches_played'])
                
                f_color = "#1D9E75" if w_pct > 65 else "#EF9F27" if w_pct >= 45 else "#E84057"
                
                map_html += f"""
                <div class="map-bar-wrap">
                    <div class="map-bar-header">
                        <span class="map-name">{m_name}</span>
                        <span class="map-pct">{w_pct:.1f}% ({played} matches)</span>
                    </div>
                    <div class="map-bar-track">
                        <div style="height:100%; border-radius:4px; width:{w_pct}%; background:{f_color};"></div>
                    </div>
                </div>
                """
            st.markdown(map_html, unsafe_allow_html=True)
            
        with cols[1]:
            st.markdown('<div class="section-header">Attack vs Defense Biases</div>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=map_stats['map_name'], y=map_stats['avg_atk_rounds'], name='Attack Rounds', marker_color='#9B94E8'))
            fig.add_trace(go.Bar(x=map_stats['map_name'], y=map_stats['avg_def_rounds'], name='Defense Rounds', marker_color='#1D9E75'))
            fig.update_layout(barmode='group', height=400, margin=dict(l=40, r=20, t=20, b=40), legend=dict(orientation="h", y=1.1), **PLOTLY_DARK)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('<div class="section-header">Analyst Insights</div>', unsafe_allow_html=True)
            bias = "attack-sided" if avg_atk > avg_def else "defense-sided"
            atk_pct = avg_atk / (avg_atk + avg_def) * 100
            def_pct = avg_def / (avg_atk + avg_def) * 100
            st.markdown(f'<div class="insight-card"><strong>⚔️ {selected_team} is {bias}</strong> — winning {atk_pct:.1f}% of rounds on attack vs {def_pct:.1f}% on defense</div>', unsafe_allow_html=True)
            
            strong_maps = len(map_stats[map_stats['win_pct'] > 50])
            st.markdown(f'<div class="insight-card"><strong>🗺️ Map pool strength:</strong> {strong_maps} of {len(map_stats)} maps above 50% win rate</div>', unsafe_allow_html=True)
    else:
        st.warning("No map stats available for this team.")
