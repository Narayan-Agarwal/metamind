import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text
from db.connection import get_engine
from db.queries import get_all_players, get_player_percentiles, get_player_stats

st.set_page_config(page_title="Player Intelligence", layout="wide", initial_sidebar_state="collapsed")

# Inject global CSS from app.py
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

def render_nav(active='Player'):
    pages = [('home','⚡ Home'), ('Player','Player'), ('Team_Map','Team Map'), ('Leaderboard','Leaderboard')]
    links = "".join([f'<a href="/{p}" class="topnav-link {"active" if p==active else ""}">{label}</a>' for p,label in pages])
    st.markdown(f'<div class="topnav"><div class="topnav-logo"><span>META</span>MIND</div><div class="topnav-links">{links}</div></div>', unsafe_allow_html=True)

render_nav('Player')

engine = get_engine()

@st.cache_data(ttl=3600)
def load_players():
    return get_all_players(engine)

players_df = load_players()
if players_df.empty:
    st.error("No player data found.")
    st.stop()

# Calculate dataset averages for deltas
with engine.connect() as conn:
    ds_avg_acs = conn.execute(text("SELECT AVG(avg_acs) FROM mv_player_percentiles")).scalar() or 0
    ds_avg_kd = conn.execute(text("SELECT AVG(avg_kd) FROM mv_player_percentiles")).scalar() or 0
    ds_avg_kast = conn.execute(text("SELECT AVG(avg_kast) FROM mv_player_percentiles")).scalar() or 0
    ds_avg_cons = conn.execute(text("SELECT AVG(consistency_score) FROM mv_player_percentiles")).scalar() or 0

cols = st.columns([1, 3])

with cols[0]:
    player_options = players_df['name'].tolist()
    selected_player = st.selectbox("Select Player", player_options)
    
    if selected_player:
        p_row = players_df[players_df['name'] == selected_player].iloc[0]
        pid = int(p_row['player_id'])
        
        pct_df = get_player_percentiles(engine, pid)
        stats_df = get_player_stats(engine, pid)
        
        if not pct_df.empty:
            pct = pct_df.iloc[0]
            
            # Determine form status
            form_status = "CONSISTENT"
            badge_class = "badge-consistent"
            if not stats_df.empty and len(stats_df) >= 3:
                last_3_acs = stats_df.head(3)['acs'].tolist()
                avg_acs = float(pct['avg_acs'] or 0)
                if all(a > avg_acs for a in last_3_acs):
                    form_status = "PEAKING"
                    badge_class = "badge-peaking"
                elif all(a < avg_acs for a in last_3_acs):
                    form_status = "DECLINING"
                    badge_class = "badge-declining"
            
            st.markdown(f"""
            <div style="margin-top:20px; padding:20px; background:#111118; border-radius:8px; border:1px solid #2A2A45;">
                <div style="font-family:'Rajdhani',sans-serif; font-size:28px; font-weight:700; color:#EEEEF5; line-height:1.2;">
                    {pct['name']}
                </div>
                <div style="color:#8888AA; font-size:13px; margin-bottom:12px;">
                    {pct['region'] or 'Unknown Region'} • {pct['nationality'] or 'Unknown'}
                </div>
                <div class="badge {badge_class}" style="margin-bottom:20px;">{form_status}</div>
                
                <div style="display:grid; gap:12px;">
                    <div>
                        <div style="font-size:11px; color:#8888AA; text-transform:uppercase;">Matches Played</div>
                        <div style="font-family:'Rajdhani',sans-serif; font-size:24px; font-weight:700; color:#EEEEF5;">
                            {pct['matches_played']}
                        </div>
                    </div>
                    <div>
                        <div style="font-size:11px; color:#8888AA; text-transform:uppercase;">Avg ACS</div>
                        <div style="font-family:'Rajdhani',sans-serif; font-size:24px; font-weight:700; color:#EEEEF5;">
                            {pct['avg_acs']:.1f}
                        </div>
                    </div>
                    <div>
                        <div style="font-size:11px; color:#8888AA; text-transform:uppercase;">Consistency</div>
                        <div style="font-family:'Rajdhani',sans-serif; font-size:24px; font-weight:700; color:#EEEEF5;">
                            {pct['consistency_score']:.1f}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

with cols[1]:
    if selected_player and not pct_df.empty:
        # A) Hero card
        acs_pct = float(pct['acs_percentile'] or 0)
        avg_acs = float(pct['avg_acs'] or 0)
        matches = int(pct['matches_played'] or 0)
        top_pct = 100 - int(acs_pct * 100)
        
        st.markdown(f"""
        <div class="hero-card">
            <div class="hero-name">{pct['name']}</div>
            <div class="hero-summary">
                {pct['name']} ranks in the top {top_pct}% globally by ACS ({avg_acs:.0f}) across {matches} matches — currently {form_status}.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # B) KPI row
        kpi_html = ""
        metrics = [
            ("Avg ACS", avg_acs, ds_avg_acs, 1),
            ("K/D", float(pct['avg_kd'] or 0), ds_avg_kd, 2),
            ("KAST %", float(pct['avg_kast'] or 0), ds_avg_kast, 1),
            ("Consistency", float(pct['consistency_score'] or 0), ds_avg_cons, 1)
        ]
        
        for label, val, ds_val, prec in metrics:
            delta = val - ds_val
            d_str = f"+{delta:.{prec}f}" if delta > 0 else f"{delta:.{prec}f}"
            d_cls = "pos" if delta > 0 else "neg"
            kpi_html += f"""
            <div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{val:.{prec}f}</div>
                <div class="kpi-delta {d_cls}">{d_str} vs avg</div>
            </div>
            """
        
        st.markdown(f'<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px;">{kpi_html}</div>', unsafe_allow_html=True)
        
        # C) Percentile bars
        st.markdown('<div class="section-header">Performance Percentiles</div>', unsafe_allow_html=True)
        pb_html = ""
        p_metrics = [
            ("ACS", float(pct['acs_percentile'] or 0)),
            ("K/D", float(pct['kd_percentile'] or 0)),
            ("First Kill", float(pct['fb_percentile'] or 0)),
            ("KAST", float(pct['avg_kast'] or 0) / 100) # Estimate percentile if not avail
        ]
        
        for p_lab, p_val in p_metrics:
            w = int(p_val * 100)
            pb_html += f"""
            <div class="stat-bar-wrap">
                <div class="stat-bar-label"><span>{p_lab}</span><span>{w}th Pct</span></div>
                <div class="stat-bar-track"><div class="stat-bar-fill" style="width:{w}%;"></div></div>
            </div>
            """
        st.markdown(pb_html, unsafe_allow_html=True)
        
        # D) Interactive form curve
        st.markdown('<div class="section-header">Form Tracker</div>', unsafe_allow_html=True)
        if not stats_df.empty:
            stats_df = stats_df.sort_values('match_date').reset_index(drop=True)
            stats_df['match_index'] = stats_df.index + 1
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            
            # Line chart
            fig.add_trace(go.Scatter(
                x=stats_df['match_index'], y=stats_df['acs'], mode='lines+markers',
                line=dict(color='#7F77DD', width=2.5), fill='tozeroy', fillcolor='rgba(127,119,221,0.1)',
                name="ACS",
                text=stats_df.apply(lambda r: f"{r['match_date']}<br>{r['map_name']}<br>{r['kills']}K / {r['deaths']}D<br>ACS: {r['acs']}", axis=1),
                hoverinfo="text"
            ), row=1, col=1)
            
            # Avg Line
            fig.add_hline(y=avg_acs, line_dash="dash", line_color="rgba(238,238,245,0.4)", row=1, col=1)
            
            # Peak star
            peak_idx = stats_df['acs'].idxmax()
            peak_row = stats_df.iloc[peak_idx]
            fig.add_trace(go.Scatter(
                x=[peak_row['match_index']], y=[peak_row['acs']],
                mode='markers', marker=dict(symbol='star', size=16, color='#FFD700'),
                name='Peak', hoverinfo='skip'
            ), row=1, col=1)
            
            # Bar chart
            fig.add_trace(go.Bar(
                x=stats_df['match_index'], y=stats_df['kills'],
                marker_color='#1D9E75', name="Kills"
            ), row=2, col=1)
            
            fig.update_layout(**PLOTLY_DARK, height=500, margin=dict(l=40, r=20, t=20, b=40), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        # E) Insights
        st.markdown('<div class="section-header">Analyst Insights</div>', unsafe_allow_html=True)
        
        if acs_pct > 0.85:
            st.markdown(f'<div class="insight-card"><strong>🎯 Elite performer</strong> — top {top_pct}% globally by ACS</div>', unsafe_allow_html=True)
        if form_status == "PEAKING":
            st.markdown('<div class="insight-card"><strong>🔺 Currently PEAKING</strong> — above season avg for last 3 matches</div>', unsafe_allow_html=True)
        if form_status == "DECLINING":
            st.markdown('<div class="insight-card"><strong>🔻 Currently DECLINING</strong> — below season avg for last 3 matches</div>', unsafe_allow_html=True)
        if float(pct['consistency_score'] or 0) > 75:
            st.markdown(f'<div class="insight-card"><strong>📊 High consistency</strong> — low variance across matches (score: {pct["consistency_score"]:.1f}/100)</div>', unsafe_allow_html=True)
