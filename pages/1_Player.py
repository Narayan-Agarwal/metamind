import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
    ds_avg_acs = conn.execute(text("SELECT AVG(avg_acs) FROM mv_player_percentiles")).scalar() or 0
    ds_avg_kd = conn.execute(text("SELECT AVG(avg_kd) FROM mv_player_percentiles")).scalar() or 0
    ds_avg_kast = conn.execute(text("SELECT AVG(avg_kast) FROM mv_player_percentiles")).scalar() or 0
    ds_avg_cons = conn.execute(text("SELECT AVG(consistency_score) FROM mv_player_percentiles")).scalar() or 0

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
        
        <div style="display:grid; gap:16px;">
            <div>
                <div style="font-size:11px; color:#888899; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">Matches Played</div>
                <div style="font-family:'Rajdhani',sans-serif; font-size:28px; font-weight:700; color:#EAEAEA;">
                    {pct['matches_played']}
                </div>
            </div>
            <div>
                <div style="font-size:11px; color:#888899; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">Avg ACS</div>
                <div style="font-family:'Rajdhani',sans-serif; font-size:28px; font-weight:700; color:#EAEAEA;">
                    {pct['avg_acs']:.1f}
                </div>
            </div>
            <div>
                <div style="font-size:11px; color:#888899; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">Consistency</div>
                <div style="font-family:'Rajdhani',sans-serif; font-size:28px; font-weight:700; color:#EAEAEA;">
                    {pct['consistency_score']:.1f}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

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

    kpi_html = ""
    metrics = [
        ("Avg ACS", avg_acs, ds_avg_acs, 1, "teal"),
        ("K/D", float(pct['avg_kd'] or 0), ds_avg_kd, 2, "purple"),
        ("KAST %", float(pct['avg_kast'] or 0), ds_avg_kast, 1, "teal"),
        ("Consistency", float(pct['consistency_score'] or 0), ds_avg_cons, 1, "purple")
    ]
    
    for label, val, ds_val, prec, color in metrics:
        delta = val - ds_val
        d_str = f"+{delta:.{prec}f}" if delta > 0 else f"{delta:.{prec}f}"
        d_cls = "up" if delta > 0 else "down"
        kpi_html += f"""
        <div class="stat-card {color}">
            <div class="stat-label">{label}</div>
            <div class="stat-value">{val:.{prec}f}</div>
            <div class="stat-delta {d_cls}">{d_str} vs avg</div>
        </div>
        """
    
    st.markdown(f'<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px;">{kpi_html}</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-title">PERFORMANCE PERCENTILES</div>', unsafe_allow_html=True)
    pb_html = ""
    p_metrics = [
        ("ACS", float(pct['acs_percentile'] or 0)),
        ("K/D", float(pct['kd_percentile'] or 0)),
        ("FIRST KILL", float(pct['fb_percentile'] or 0)),
        ("KAST", float(pct['avg_kast'] or 0) / 100)
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
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.08)
        
        fig.add_trace(go.Scatter(
            x=stats_df['match_index'], y=stats_df['acs'], mode='lines+markers',
            line=dict(color='#F5C518', width=2.5), marker=dict(size=6, color='#F5C518'),
            fill='tozeroy', fillcolor='rgba(245,197,24,0.05)', name='ACS',
            text=stats_df.apply(lambda r: f"{r['match_date']}<br>{r['map_name']}<br>{r['kills']}K / {r['deaths']}D<br>ACS: {r['acs']}", axis=1),
            hoverinfo="text"
        ), row=1, col=1)
        
        fig.add_hline(y=avg_acs, line_dash="dash", line_color="rgba(255,255,255,0.2)", annotation_text="Season avg", annotation_font_color="#888899", row=1, col=1)
        
        peak_idx = stats_df['acs'].idxmax()
        peak_row = stats_df.iloc[peak_idx]
        fig.add_trace(go.Scatter(
            x=[peak_row['match_index']], y=[peak_row['acs']],
            mode='markers', marker=dict(symbol='star', size=16, color='#FFD700'),
            name='Peak', hoverinfo='skip'
        ), row=1, col=1)
        
        fig.add_trace(go.Bar(
            x=stats_df['match_index'], y=stats_df['kills'],
            marker_color='#00D4FF', opacity=0.7, name="Kills"
        ), row=2, col=1)
        
        fig.update_layout(**PLOTLY_THEME, height=450, showlegend=False, title_text='Performance Timeline', title_font=dict(color='#EAEAEA', family='Rajdhani', size=16))
        fig.update_xaxes(**AXIS_STYLE)
        fig.update_yaxes(**AXIS_STYLE)
        st.plotly_chart(fig, use_container_width=True)
    
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
