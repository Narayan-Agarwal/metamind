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
        ("KAST %", float(pct['avg_kast'] or 0), ds_avg_kast, 1),
        ("Consistency", float(pct['consistency_score'] or 0), ds_avg_cons, 1),
        ("Matches", float(pct['matches_played'] or 0), 0, 0),
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
    
    st.markdown('<div class="section-title">PERFORMANCE RADAR</div>', unsafe_allow_html=True)
    radar_vals = [
        float(pct['acs_percentile'] or 0) * 100,
        float(pct['avg_kast'] or 0),
        float(pct['consistency_score'] or 0),
        min(float(pct['matches_played'] or 0) / 50 * 100, 100),
        float(pct['avg_fb'] or 0) * 100
    ]
    radar_cats = ['ACS Rank', 'KAST %', 'Consistency', 'Experience', 'First Kill %']
    radar_vals_closed = radar_vals + [radar_vals[0]]
    radar_cats_closed = radar_cats + [radar_cats[0]]
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_vals_closed,
        theta=radar_cats_closed,
        fill='toself',
        fillcolor='rgba(245,197,24,0.15)',
        line=dict(color='#F5C518', width=2.5),
        marker=dict(size=7, color='#F5C518'),
        name=str(pct['name'])
    ))
    fig_radar.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        polar=dict(
            bgcolor='#1C1C24',
            radialaxis=dict(visible=True, range=[0, 100], gridcolor='#2E2E3A', color='#888899', tickfont=dict(size=10)),
            angularaxis=dict(gridcolor='#2E2E3A', color='#EAEAEA', tickfont=dict(size=12, family='Rajdhani'))
        ),
        showlegend=False,
        height=420,
        margin=dict(l=50, r=50, t=30, b=30),
        font=dict(color='#888899', family='Inter', size=11)
    )
    st.plotly_chart(fig_radar, use_container_width=True)
    
    st.markdown('<div class="section-title">ANALYST INSIGHTS</div>', unsafe_allow_html=True)

    gauge_cols = st.columns(3)

    gauge_data = [
        ("ACS Rank", float(pct['acs_percentile'] or 0) * 100, "%", "#F5C518"),
        ("Consistency", float(pct['consistency_score'] or 0), "/100", "#00D4FF"),
        ("KAST Rating", float(pct['avg_kast'] or 0), "%", "#7F77DD"),
    ]

    for i, (label, value, suffix, color) in enumerate(gauge_data):
        with gauge_cols[i]:
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number",
                value=value,
                number=dict(suffix=suffix, font=dict(color=color, size=28, family='Rajdhani')),
                title=dict(text=label, font=dict(color='#888899', size=13, family='Inter')),
                gauge=dict(
                    axis=dict(range=[0, 100], tickcolor='#2E2E3A', tickfont=dict(color='#888899', size=10)),
                    bar=dict(color=color, thickness=0.25),
                    bgcolor='#1C1C24',
                    borderwidth=0,
                    steps=[
                        dict(range=[0, 33], color='#1C1C24'),
                        dict(range=[33, 66], color='#252530'),
                        dict(range=[66, 100], color='#2E2E3A'),
                    ],
                    threshold=dict(line=dict(color=color, width=2), thickness=0.75, value=value)
                )
            ))
            fig_g.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                height=220,
                margin=dict(l=10, r=10, t=30, b=10),
                font=dict(color='#888899')
            )
            st.plotly_chart(fig_g, use_container_width=True)

    if form_status == "PEAKING":
        st.markdown('<div class="insight"><b>🔺 Currently PEAKING</b> — above season avg for last 3 matches</div>', unsafe_allow_html=True)
    elif form_status == "DECLINING":
        st.markdown('<div class="insight"><b>🔻 Currently DECLINING</b> — below season avg for last 3 matches</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="insight"><b>📊 Consistent performer</b> — stable output across recent matches</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
