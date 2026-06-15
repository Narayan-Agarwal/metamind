import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db.connection import get_engine
from db.queries import get_all_teams, get_team_map_stats
from utils.styles import GLOBAL_CSS, PLOTLY_THEME, render_nav

st.set_page_config(page_title="Team Map Strategy", layout="wide", initial_sidebar_state="collapsed")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
render_nav(active_page='/Team_Map')

st.markdown('<div class="main-content">', unsafe_allow_html=True)

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
            <div class="hero-player-name">{selected_team}</div>
            <div class="hero-summary">
                {selected_team} dominates {best_map} ({best_pct:.1f}% win rate) but struggles on {worst_map} ({worst_pct:.1f}%). 
                Overall: {int(total_wins)}/{int(total_played)} maps won.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        kpi_html = f"""
        <div style="display:grid; grid-template-columns:repeat(5,1fr); gap:16px; margin-bottom:24px;">
            <div class="stat-card"><div class="stat-label">Win Rate</div><div class="stat-value">{overall_wr:.1f}%</div></div>
            <div class="stat-card teal"><div class="stat-label">Best Map</div><div class="stat-value" style="font-size:24px;">{best_map}</div></div>
            <div class="stat-card red"><div class="stat-label">Worst Map</div><div class="stat-value" style="font-size:24px;">{worst_map}</div></div>
            <div class="stat-card purple"><div class="stat-label">Attack Win%</div><div class="stat-value">{avg_atk/(avg_atk+avg_def)*100:.1f}%</div></div>
            <div class="stat-card teal"><div class="stat-label">Defense Win%</div><div class="stat-value">{avg_def/(avg_atk+avg_def)*100:.1f}%</div></div>
        </div>
        """
        st.markdown(kpi_html, unsafe_allow_html=True)
        
        cols = st.columns([1, 2])
        
        with cols[0]:
            st.markdown('<div class="section-title">MAP WIN RATES</div>', unsafe_allow_html=True)
            map_html = ""
            for _, r in map_stats.iterrows():
                m_name = r['map_name']
                w_pct = float(r['win_pct'])
                played = int(r['matches_played'])
                
                f_color = "fill-win" if w_pct > 65 else "fill-mid" if w_pct >= 45 else "fill-loss"
                
                map_html += f"""
                <div class="map-bar">
                    <div class="map-bar-info">
                        <span class="map-bar-name">{m_name}</span>
                        <span class="map-bar-pct">{w_pct:.1f}% ({played} matches)</span>
                    </div>
                    <div class="map-bar-track">
                        <div class="map-bar-fill {f_color}" style="width:{w_pct}%;"></div>
                    </div>
                </div>
                """
            st.markdown(map_html, unsafe_allow_html=True)
            
        with cols[1]:
            st.markdown('<div class="section-title">ATTACK VS DEFENSE BIASES</div>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Bar(x=map_stats['map_name'], y=map_stats['avg_atk_rounds'], name='Attack Rounds', marker_color='#7F77DD'))
            fig.add_trace(go.Bar(x=map_stats['map_name'], y=map_stats['avg_def_rounds'], name='Defense Rounds', marker_color='#00D4FF'))
            fig.update_layout(barmode='group', height=400, legend=dict(orientation="h", y=1.1), **PLOTLY_THEME)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown('<div class="section-title">ANALYST INSIGHTS</div>', unsafe_allow_html=True)
            bias = "attack-sided" if avg_atk > avg_def else "defense-sided"
            atk_pct = avg_atk / (avg_atk + avg_def) * 100 if (avg_atk + avg_def) > 0 else 0
            def_pct = avg_def / (avg_atk + avg_def) * 100 if (avg_atk + avg_def) > 0 else 0
            st.markdown(f'<div class="insight"><b>⚔️ {selected_team} is {bias}</b> — winning {atk_pct:.1f}% of rounds on attack vs {def_pct:.1f}% on defense</div>', unsafe_allow_html=True)
            
            strong_maps = len(map_stats[map_stats['win_pct'] > 50])
            st.markdown(f'<div class="insight"><b>🗺️ Map pool strength:</b> {strong_maps} of {len(map_stats)} maps above 50% win rate</div>', unsafe_allow_html=True)
    else:
        st.warning("No map stats available for this team.")

st.markdown('</div>', unsafe_allow_html=True)
