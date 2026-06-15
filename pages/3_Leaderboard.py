import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db.connection import get_engine
from db.queries import get_leaderboard, get_regional_comparison, get_indian_spotlight

st.set_page_config(page_title="Global Leaderboard", layout="wide", initial_sidebar_state="collapsed")

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

def render_nav(active='Leaderboard'):
    pages = [('home','⚡ Home'), ('Player','Player'), ('Team_Map','Team Map'), ('Leaderboard','Leaderboard')]
    links = "".join([f'<span class="topnav-link {"active" if p==active else ""}" onclick="window.parent.location.href=\'/{p}\'">{label}</span>' for p,label in pages])
    st.markdown(f'<div class="topnav"><div class="topnav-logo"><span>META</span>MIND</div><div class="topnav-links">{links}</div></div>', unsafe_allow_html=True)

render_nav('Leaderboard')

engine = get_engine()

st.markdown('<div class="section-header">Global Filters</div>', unsafe_allow_html=True)
cols = st.columns(3)
with cols[0]:
    region_options = ["All", "Americas", "EMEA", "Pacific", "Korea", "South Asia"]
    selected_region = st.selectbox("Region", region_options)
with cols[1]:
    min_matches = st.slider("Minimum Matches", 5, 30, 10)
with cols[2]:
    sort_options = {"ACS": "avg_acs", "K/D": "avg_kd", "Consistency Score": "consistency", "KAST": "kast_pct", "First Kill %": "first_kill_pct"}
    sort_label = st.selectbox("Sort by", list(sort_options.keys()))
    sort_column = sort_options[sort_label]

st.markdown('<div class="section-header">Regional Performance Comparison</div>', unsafe_allow_html=True)
regional = get_regional_comparison(engine)

if not regional.empty:
    fig = go.Figure()
    
    colors = {
        "Americas": "#E84057", "EMEA": "#7F77DD", "Pacific": "#1D9E75",
        "Korea": "#EF9F27", "South Asia": "#FF6B6B"
    }
    
    # We will use map to get colors, default to gray if missing
    marker_colors = [colors.get(r, "#8888AA") for r in regional['region']]
    
    fig.add_trace(go.Bar(
        name="Avg ACS", x=regional['region'], y=regional['avg_acs'],
        marker_color=marker_colors
    ))
    # Normalized KD
    fig.add_trace(go.Bar(
        name="Avg K/D (x100)", x=regional['region'], y=regional['avg_kd'] * 100,
        marker_color=[c for c in marker_colors],
        opacity=0.7
    ))
    
    fig.update_layout(barmode='group', height=400, margin=dict(l=40, r=20, t=20, b=40), legend=dict(orientation="h", y=1.1), **PLOTLY_DARK)
    st.plotly_chart(fig, use_container_width=True)

indian = get_indian_spotlight(engine)
if not indian.empty:
    st.markdown('<div class="section-header">🇮🇳 India Spotlight</div>', unsafe_allow_html=True)
    ind_html = "<div style='display:flex; gap:16px;'>"
    for _, r in indian.iterrows():
        ind_html += f"""
        <div class="kpi-card" style="flex:1;">
            <div style="font-family:'Rajdhani',sans-serif; font-size:24px; color:#EEEEF5; margin-bottom:8px;">{r['name']}</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span class="kpi-label">ACS</span><span style="color:#EEEEF5; font-weight:600;">{r['avg_acs']:.1f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span class="kpi-label">K/D</span><span style="color:#EEEEF5; font-weight:600;">{r['avg_kd']:.2f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span class="kpi-label">Global Pct</span><span style="color:#7F77DD; font-weight:600;">{r['global_percentile']:.0f}th</span>
            </div>
        </div>
        """
    ind_html += "</div>"
    st.markdown(ind_html, unsafe_allow_html=True)

st.markdown('<div class="section-header">Global Leaderboard</div>', unsafe_allow_html=True)

lb_df = get_leaderboard(engine, min_matches=min_matches)

if not lb_df.empty:
    if selected_region != "All":
        lb_df = lb_df[lb_df['region'] == selected_region]
        
    lb_df = lb_df.sort_values(by=sort_column, ascending=False).reset_index(drop=True)
    lb_df['rank'] = lb_df.index + 1
    
    page_size = 25
    total_pages = max(1, (len(lb_df) + page_size - 1) // page_size)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    start_idx = (page - 1) * page_size
    page_df = lb_df.iloc[start_idx:start_idx + page_size]
    
    lb_html = f"""
    <div style="border:1px solid #2A2A45; border-radius:8px; overflow:hidden; margin-bottom:20px;">
        <div class="lb-row" style="background:#111118; border-bottom:2px solid #2A2A45; color:#8888AA; font-weight:600;">
            <div style="text-align:center;">Rank</div>
            <div>Player</div>
            <div>Region</div>
            <div style="text-align:right;">ACS</div>
            <div style="text-align:right;">K/D</div>
            <div style="text-align:right;">Cons.</div>
            <div style="text-align:right;">Matches</div>
        </div>
    """
    
    for _, row in page_df.iterrows():
        rank = int(row['rank'])
        bg = "rgba(255,215,0,0.05)" if rank <= 10 else "rgba(127,119,221,0.05)" if rank <= 50 else "transparent"
        r_disp = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
        r_cls = "gold" if rank == 1 else "silver" if rank == 2 else "bronze" if rank == 3 else ""
        
        lb_html += f"""
        <div class="lb-row" style="background:{bg};">
            <div class="lb-rank {r_cls}">{r_disp}</div>
            <div class="lb-name">{row['name']}</div>
            <div class="lb-region">{row['region'] or 'Unknown'}</div>
            <div class="lb-stat">{row['avg_acs']:.1f}</div>
            <div class="lb-stat">{row['avg_kd']:.2f}</div>
            <div class="lb-stat">{row['consistency']:.1f}</div>
            <div class="lb-stat" style="color:#8888AA;">{row['matches_played']}</div>
        </div>
        """
        
    lb_html += "</div>"
    st.markdown(lb_html, unsafe_allow_html=True)
else:
    st.warning("No players found matching criteria.")
