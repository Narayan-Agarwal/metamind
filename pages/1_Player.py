import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from sqlalchemy import text
from db.connection import get_engine
from db.queries import get_all_players, get_player_percentiles, get_player_stats
from utils.styles import GLOBAL_CSS, PLOTLY_THEME, AXIS_STYLE, render_nav

st.set_page_config(page_title="Player Intelligence", layout="wide", initial_sidebar_state="collapsed")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
render_nav(active_page='/Player')

st.markdown('<div class="main-content">', unsafe_allow_html=True)

engine = get_engine()

@st.cache_data(ttl=3600)
def load_players():
    return get_all_players(engine)

players_df = load_players()
if players_df.empty:
    st.error("No player data found.")
    st.stop()

with engine.connect() as conn:
    ds_avg_acs = float(conn.execute(text("SELECT AVG(avg_acs) FROM mv_player_percentiles")).scalar() or 0)
    ds_avg_kd = float(conn.execute(text("SELECT AVG(avg_kd) FROM mv_player_percentiles")).scalar() or 0)
    ds_avg_kast = float(conn.execute(text("SELECT AVG(avg_kast) FROM mv_player_percentiles")).scalar() or 0)
    ds_avg_cons = float(conn.execute(text("SELECT AVG(consistency_score) FROM mv_player_percentiles")).scalar() or 0)

# Player selector OUTSIDE columns so variables are accessible everywhere
player_names = sorted(players_df['name'].tolist())
selected_name = st.selectbox("Select Player", player_names)
selected_id = int(players_df[
    players_df['name'] == selected_name
]['player_id'].iloc[0])

pct_df = get_player_percentiles(engine, selected_id)
if pct_df is None or pct_df.empty:
    st.warning("No percentile data for this player")
    st.stop()

pct = pct_df.iloc[0]
stats_df = get_player_stats(engine, selected_id)

form_status = "CONSISTENT"
badge_class = "badge-consistent"
if not stats_df.empty and len(stats_df) >= 3:
    last_3_acs = stats_df.head(3)['acs'].tolist()
    avg_acs = float(pct['avg_acs'] or 0)
    if all(a > avg_acs for a in last_3_acs):
        form_status = "PEAKING"
        badge_class = "badge-peak"
    elif all(a < avg_acs for a in last_3_acs):
        form_status = "DECLINING"
        badge_class = "badge-decline"

cols = st.columns([1, 3])

with cols[0]:
    st.markdown(f"""
    <div style="margin-top:20px; padding:20px; background:#252530; border-radius:10px; border:1px solid #2E2E3A;">
        <div style="font-family:'Rajdhani',sans-serif; font-size:32px; font-weight:700; color:#EAEAEA; line-height:1.2;">
            {pct['name']}
        </div>
        <div style="color:#888899; font-size:13px; margin-bottom:12px;">
            {pct['region'] or 'Unknown Region'} • {pct['nationality'] or 'Unknown'}
        </div>
        <div class="badge {badge_class}" style="margin-bottom:24px;">{form_status}</div>
        
    </div>
    """, unsafe_allow_html=True)

    st.metric("Matches Played", int(pct['matches_played']))
    st.metric("Avg ACS", f"{float(pct['avg_acs']):.1f}")
    st.metric("Consistency", f"{float(pct['consistency_score']):.1f}")

with cols[1]:
    acs_pct = float(pct['acs_percentile'] or 0)
    avg_acs = float(pct['avg_acs'] or 0)
    matches = int(pct['matches_played'] or 0)
    top_pct = 100 - int(acs_pct * 100)
    
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-player-name">{pct['name']}</div>
        <div class="hero-summary">
            {pct['name']} ranks in the top {top_pct}% globally by ACS ({avg_acs:.0f}) across {matches} matches — currently {form_status.lower()}.
        </div>
    </div>
    """, unsafe_allow_html=True)

    metrics = [
        ("Avg ACS", avg_acs, ds_avg_acs, 1),
        ("K/D", float(pct['avg_kd'] or 0), ds_avg_kd, 2),
        ("KAST %", float(pct['avg_kast'] or 0), ds_avg_kast, 1),
        ("Consistency", float(pct['consistency_score'] or 0), ds_avg_cons, 1),
    ]
    kpi_cols = st.columns(4)
    for i, (label, val, ds_val, prec) in enumerate(metrics):
        delta = val - ds_val
        with kpi_cols[i]:
            st.metric(label=label, value=f"{val:.{prec}f}", delta=f"{delta:+.{prec}f} vs avg")
    
    st.markdown('<div class="section-title">PERFORMANCE PERCENTILES</div>', unsafe_allow_html=True)
    pb_html = ""
    p_metrics = [
        ("ACS", float(pct['acs_percentile'] or 0)),
        ("KAST", float(pct['avg_kast'] or 0) / 100),
        ("Consistency", float(pct['consistency_score'] or 0) / 100),
        ("Matches", min(float(pct['matches_played'] or 0) / 50, 1.0))
    ]
    
    for p_lab, p_val in p_metrics:
        w = int(p_val * 100)
        pb_html += f"""
        <div class="pct-bar">
            <div class="pct-bar-top">
                <span class="pct-bar-label">{p_lab}</span>
                <span class="pct-bar-val">{w}th Pct</span>
            </div>
            <div class="pct-bar-track"><div class="pct-bar-fill" style="width:{w}%;"></div></div>
        </div>
        """
    st.markdown(pb_html, unsafe_allow_html=True)
    
    st.markdown('<div class="section-title">PERFORMANCE TIMELINE</div>', unsafe_allow_html=True)
    if not stats_df.empty:
        stats_df = stats_df.sort_values('match_date').reset_index(drop=True)
        stats_df['match_index'] = stats_df.index + 1
        stats_df['acs_safe'] = stats_df['acs'].fillna(0)
        stats_df['kills_safe'] = stats_df['kills'].fillna(0)
        stats_df['deaths_safe'] = stats_df['deaths'].fillna(1).clip(lower=1)

        tab1, tab2 = st.tabs(["📈 Timeline", "🕸️ Radar"])

        with tab1:
            fig = go.Figure()
            fig.add_trace(go.Scatter3d(
                x=stats_df['match_index'],
                y=stats_df['acs_safe'],
                z=stats_df['kills_safe'],
                mode='lines+markers',
                line=dict(color='#F5C518', width=4),
                marker=dict(
                    size=6,
                    color=stats_df['acs_safe'],
                    colorscale=[[0, '#2E2E3A'], [0.5, '#F5C518'], [1, '#FFD700']],
                    showscale=False
                ),
                text=stats_df.apply(lambda r: f"Match {int(r['match_index'])}<br>ACS: {r['acs_safe']:.0f}<br>Kills: {r['kills_safe']:.0f}", axis=1),
                hoverinfo='text',
                name='Performance'
            ))
            fig.add_trace(go.Scatter3d(
                x=[stats_df.loc[stats_df['acs_safe'].idxmax(), 'match_index']],
                y=[stats_df['acs_safe'].max()],
                z=[stats_df.loc[stats_df['acs_safe'].idxmax(), 'kills_safe']],
                mode='markers',
                marker=dict(size=12, color='#FFD700', symbol='diamond'),
                name='Peak',
                hoverinfo='skip'
            ))
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                scene=dict(
                    bgcolor='#1C1C24',
                    xaxis=dict(title='Match', gridcolor='#2E2E3A', color='#888899', showbackground=False),
                    yaxis=dict(title='ACS', gridcolor='#2E2E3A', color='#888899', showbackground=False),
                    zaxis=dict(title='Kills', gridcolor='#2E2E3A', color='#888899', showbackground=False),
                    camera=dict(eye=dict(x=1.5, y=1.5, z=0.8))
                ),
                height=450,
                showlegend=False,
                margin=dict(l=0, r=0, t=10, b=0),
                font=dict(color='#888899', family='Inter', size=11)
            )
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            radar_vals = [
                float(pct['acs_percentile'] or 0) * 100,
                float(pct['avg_kast'] or 0),
                float(pct['consistency_score'] or 0),
                min(float(pct['matches_played'] or 0) / 50 * 100, 100),
                float(pct['avg_kd'] or 0) * 50
            ]
            radar_cats = ['ACS Rank', 'KAST %', 'Consistency', 'Experience', 'K/D Index']
            radar_vals_closed = radar_vals + [radar_vals[0]]
            radar_cats_closed = radar_cats + [radar_cats[0]]
            fig2 = go.Figure()
            fig2.add_trace(go.Scatterpolar(
                r=radar_vals_closed,
                theta=radar_cats_closed,
                fill='toself',
                fillcolor='rgba(245,197,24,0.15)',
                line=dict(color='#F5C518', width=2),
                marker=dict(size=6, color='#F5C518'),
                name=str(pct['name'])
            ))
            fig2.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                polar=dict(
                    bgcolor='#1C1C24',
                    radialaxis=dict(visible=True, range=[0, 100], gridcolor='#2E2E3A', color='#888899', tickfont=dict(size=10)),
                    angularaxis=dict(gridcolor='#2E2E3A', color='#EAEAEA', tickfont=dict(size=11))
                ),
                showlegend=False,
                height=420,
                margin=dict(l=40, r=40, t=30, b=30),
                font=dict(color='#888899', family='Inter', size=11)
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown('<div class="section-title">ANALYST INSIGHTS</div>', unsafe_allow_html=True)
    
    if acs_pct > 0.85:
        st.markdown(f'<div class="insight"><b>🎯 Elite performer</b> — top {top_pct}% globally by ACS</div>', unsafe_allow_html=True)
    if form_status == "PEAKING":
        st.markdown('<div class="insight"><b>🔺 Currently PEAKING</b> — above season avg for last 3 matches</div>', unsafe_allow_html=True)
    if form_status == "DECLINING":
        st.markdown('<div class="insight"><b>🔻 Currently DECLINING</b> — below season avg for last 3 matches</div>', unsafe_allow_html=True)
    if float(pct['consistency_score'] or 0) > 75:
        st.markdown(f'<div class="insight"><b>📊 High consistency</b> — low variance across matches (score: {pct["consistency_score"]:.1f}/100)</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
