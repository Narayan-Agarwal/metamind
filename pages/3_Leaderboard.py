import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db.connection import get_engine
from db.queries import get_leaderboard, get_regional_comparison, get_indian_spotlight
from utils.styles import GLOBAL_CSS, PLOTLY_THEME, AXIS_STYLE, render_nav

st.set_page_config(page_title="Global Leaderboard", layout="wide", initial_sidebar_state="collapsed")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
render_nav(active_page='/Leaderboard')

st.markdown('<div class="main-content">', unsafe_allow_html=True)

engine = get_engine()

st.markdown('<div class="section-title">GLOBAL FILTERS</div>', unsafe_allow_html=True)
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

st.markdown('<div class="section-title">REGIONAL PERFORMANCE COMPARISON</div>', unsafe_allow_html=True)
regional = get_regional_comparison(engine)

if not regional.empty:
    fig = go.Figure()
    
    colors = {
        "Americas": "#E84057", "EMEA": "#7F77DD", "Pacific": "#1D9E75",
        "Korea": "#EF9F27", "South Asia": "#FF6B6B"
    }
    
    for i, row in regional.iterrows():
        region_name = row['region']
        color = colors.get(region_name, '#8888AA')
        fig.add_trace(go.Bar(
            name=region_name,
            x=[region_name],
            y=[row['avg_acs']],
            marker=dict(
                color=color,
                line=dict(color=color, width=1),
                opacity=0.9
            ),
            text=[f"{row['avg_acs']:.0f}"],
            textposition='outside',
            textfont=dict(color='#EAEAEA', size=12, family='Rajdhani'),
            hovertemplate=f"<b>{region_name}</b><br>Avg ACS: %{{y:.1f}}<br>Avg K/D: {row['avg_kd']:.2f}<extra></extra>"
        ))
    fig.update_layout(
        **PLOTLY_THEME,
        barmode='group',
        height=420,
        showlegend=True,
        bargap=0.25,
        bargroupgap=0.1,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title=dict(text='Regional ACS Comparison', font=dict(color='#EAEAEA', family='Rajdhani', size=16))
    )
    fig.update_xaxes(**AXIS_STYLE, tickfont=dict(color='#EAEAEA', size=13, family='Rajdhani'))
    fig.update_yaxes(**AXIS_STYLE, title_text='Average ACS')
    st.plotly_chart(fig, use_container_width=True)

indian = get_indian_spotlight(engine)
if not indian.empty:
    st.markdown('<div class="section-title">🇮🇳 INDIA SPOTLIGHT</div>', unsafe_allow_html=True)
    ind_html = "<div style='display:flex; gap:16px; margin-bottom:24px;'>"
    for _, r in indian.iterrows():
        ind_html += f"""
        <div class="india-card" style="flex:1;">
            <div class="india-header">{r['name']}</div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span class="stat-label" style="margin:0;">ACS</span>
                <span style="font-family:'JetBrains Mono',monospace; font-size:14px; color:#EAEAEA;">{r['avg_acs']:.1f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span class="stat-label" style="margin:0;">K/D</span>
                <span style="font-family:'JetBrains Mono',monospace; font-size:14px; color:#EAEAEA;">{r['avg_kd']:.2f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span class="stat-label" style="margin:0;">GLOBAL PCT</span>
                <span style="font-family:'JetBrains Mono',monospace; font-size:14px; color:#00D4FF;">{r['global_percentile']:.0f}th</span>
            </div>
        </div>
        """
    ind_html += "</div>"
    st.markdown(ind_html, unsafe_allow_html=True)

st.markdown('<div class="section-title">GLOBAL LEADERBOARD</div>', unsafe_allow_html=True)

lb_df = get_leaderboard(engine, min_matches=min_matches)

if not lb_df.empty:
    if selected_region != "All":
        lb_df = lb_df[lb_df['region'] == selected_region]
        
    lb_df = lb_df.sort_values(by=sort_column, ascending=False).reset_index(drop=True)
    lb_df['rank_display'] = lb_df.index + 1
    
    total = len(lb_df)
    per_page = 25
    page = st.number_input('Page', 1, max(1,(total+per_page-1)//per_page), 1)
    start = (page-1)*per_page
    chunk = lb_df.iloc[start:start+per_page]
    
    lb_html = f"""
    <div class="lb-table">
        <div class="lb-header">
            <div style="text-align:center;">RANK</div>
            <div>PLAYER</div>
            <div>REGION</div>
            <div style="text-align:right;">ACS</div>
            <div style="text-align:right;">K/D</div>
            <div style="text-align:right;">CONSISTENCY</div>
            <div style="text-align:right;">MATCHES</div>
        </div>
    """
    
    for _, row in chunk.iterrows():
        rank = int(row['rank_display'])
        row_cls = "lb-row top3" if rank <= 3 else "lb-row top10" if rank <= 10 else "lb-row"
        r_disp = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
        r_cls = "lb-rank r1" if rank == 1 else "lb-rank r2" if rank == 2 else "lb-rank r3" if rank == 3 else "lb-rank"
        
        lb_html += f"""
        <div class="{row_cls}">
            <div class="{r_cls}">{r_disp}</div>
            <div class="lb-name">{row['name']}</div>
            <div class="lb-region">{row['region'] or 'Unknown'}</div>
            <div class="lb-stat highlight">{row['avg_acs']:.1f}</div>
            <div class="lb-stat">{row['avg_kd']:.2f}</div>
            <div class="lb-stat">{row['consistency']:.1f}</div>
            <div class="lb-stat" style="color:#888899;">{row['matches_played']}</div>
        </div>
        """
        
    lb_html += "</div>"
    st.markdown(lb_html, unsafe_allow_html=True)
else:
    st.warning("No players found matching criteria.")

st.markdown('</div>', unsafe_allow_html=True)
