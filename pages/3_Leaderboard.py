import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from db.connection import get_engine
from db.queries import get_leaderboard, get_indian_spotlight, get_top_players, get_acs_distribution
from utils.styles import GLOBAL_CSS, PLOTLY_THEME, AXIS_STYLE, render_nav, render_glossary

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

# ── SECTION 1: Top 15 Players ──
st.markdown('<div class="section-title">🏆 GLOBAL TOP 15 PLAYERS BY ACS</div>', unsafe_allow_html=True)
top_df = get_top_players(engine, limit=15)
if not top_df.empty:
    top_df = top_df.sort_values('avg_acs', ascending=True)
    def consistency_color(score):
        if float(score) >= 70: return '#00D4FF'
        elif float(score) >= 40: return '#F5C518'
        else: return '#FF4757'
    bar_colors = [consistency_color(s) for s in top_df['consistency_score']]
    fig_top = go.Figure(go.Bar(
        x=top_df['avg_acs'].astype(float),
        y=top_df['name'],
        orientation='h',
        marker=dict(color=bar_colors, opacity=0.9, line=dict(color=bar_colors, width=1)),
        text=top_df['avg_acs'].apply(lambda v: f"{float(v):.0f}"),
        textposition='outside',
        textfont=dict(color='#EAEAEA', family='Rajdhani', size=12),
        hovertemplate='<b>%{y}</b><br>Avg ACS: %{x:.1f}<extra></extra>'
    ))
    fig_top.update_layout(
        **PLOTLY_THEME,
        height=480,
        showlegend=False,
        margin=dict(l=120, r=60, t=20, b=20),
        xaxis=dict(gridcolor='#2E2E3A', color='#888899', title='Average ACS', tickfont=dict(color='#888899')),
        yaxis=dict(gridcolor='#2E2E3A', color='#EAEAEA', tickfont=dict(color='#EAEAEA', family='Rajdhani', size=12))
    )
    st.plotly_chart(fig_top, use_container_width=True)
    st.caption("Bar color — 🔵 High consistency (70+)   🟡 Medium (40–70)   🔴 Low (<40)")
else:
    st.info("No player data available.")

# ── SECTION 2: ACS Distribution ──
st.markdown('<div class="section-title">📊 ACS DISTRIBUTION — THE COMPETITIVE FIELD</div>', unsafe_allow_html=True)
dist_df = get_acs_distribution(engine)
if not dist_df.empty:
    acs_vals = dist_df['avg_acs'].astype(float).tolist()
    avg_acs_all = sum(acs_vals) / len(acs_vals)
    fig_dist = go.Figure()
    fig_dist.add_trace(go.Histogram(
        x=acs_vals,
        nbinsx=40,
        marker=dict(color='#F5C518', opacity=0.75, line=dict(color='#1C1C24', width=1)),
        name='Players',
        hovertemplate='ACS Range: %{x}<br>Players: %{y}<extra></extra>'
    ))
    fig_dist.add_vline(
        x=avg_acs_all,
        line=dict(color='#00D4FF', width=2, dash='dash'),
        annotation_text=f'Avg {avg_acs_all:.0f}',
        annotation_font=dict(color='#00D4FF', size=12, family='Rajdhani'),
        annotation_position='top right'
    )
    fig_dist.update_layout(
        **PLOTLY_THEME,
        height=320,
        showlegend=False,
        bargap=0.05,
        xaxis=dict(gridcolor='#2E2E3A', color='#888899', title='Average ACS', tickfont=dict(color='#888899')),
        yaxis=dict(gridcolor='#2E2E3A', color='#888899', title='Number of Players', tickfont=dict(color='#888899'))
    )
    st.plotly_chart(fig_dist, use_container_width=True)
    st.caption(f"Distribution of {len(acs_vals):,} players with 3+ matches. Dashed line = global average ACS.")
else:
    st.info("No distribution data available.")

# ── SECTION 3: India Spotlight ──
indian = get_indian_spotlight(engine)
if not indian.empty:
    st.markdown('<div class="section-title">🇮🇳 INDIA SPOTLIGHT</div>', unsafe_allow_html=True)
    ind_cols = st.columns(len(indian))
    for i, (_, r) in enumerate(indian.iterrows()):
        with ind_cols[i]:
            st.metric("Player", r['name'])
            st.metric("Avg ACS", f"{float(r['avg_acs']):.1f}")
            st.metric("Consistency", f"{float(r['consistency']):.1f}")
            st.metric("Global Rank", f"{float(r['global_percentile']):.0f}th Pct")

# ── SECTION 4: Global Leaderboard Table ──
st.markdown('<div class="section-title">GLOBAL LEADERBOARD</div>', unsafe_allow_html=True)
lb_df = get_leaderboard(engine, min_matches=min_matches)
if not lb_df.empty:
    if selected_region != "All":
        lb_df = lb_df[lb_df['region'] == selected_region]
    lb_df = lb_df.sort_values(by=sort_column, ascending=False).reset_index(drop=True)
    lb_df['rank_display'] = lb_df.index + 1
    total = len(lb_df)
    per_page = 25
    page = st.number_input('Page', 1, max(1, (total + per_page - 1) // per_page), 1)
    start = (page - 1) * per_page
    chunk = lb_df.iloc[start:start + per_page]
    lb_html = """
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
            <div class="lb-stat highlight">{float(row['avg_acs']):.1f}</div>
            <div class="lb-stat">{float(row['avg_kd']):.2f}</div>
            <div class="lb-stat">{float(row['consistency']):.1f}</div>
            <div class="lb-stat" style="color:#888899;">{row['matches_played']}</div>
        </div>
        """
    lb_html += "</div>"
    st.markdown(lb_html, unsafe_allow_html=True)
else:
    st.warning("No players found matching criteria.")

st.markdown('</div>', unsafe_allow_html=True)
render_glossary()
