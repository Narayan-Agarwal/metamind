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

AXIS = dict(gridcolor='#2E2E3A', linecolor='#2E2E3A', tickcolor='#888899', showgrid=True)

def consistency_tier(score):
    s = float(score)
    if s >= 70: return 'Elite', '#00D4FF'
    elif s >= 40: return 'Solid', '#F5C518'
    else: return 'Volatile', '#FF4757'

# ── FILTERS ──
st.markdown('<div class="section-title">SCOUT FILTERS</div>', unsafe_allow_html=True)
f1, f2, f3 = st.columns(3)
with f1:
    tier_filter = st.selectbox("Consistency Tier", ["All", "Elite (70+)", "Solid (40–70)", "Volatile (<40)"])
with f2:
    min_matches = st.slider("Minimum Matches", 5, 30, 10)
with f3:
    sort_options = {"ACS": "avg_acs", "Consistency": "consistency", "KAST": "kast_pct"}
    sort_label = st.selectbox("Sort by", list(sort_options.keys()))
    sort_column = sort_options[sort_label]

# ── SECTION 1: ACS vs Consistency Scatter ──
st.markdown('<div class="section-title">⚡ SKILL vs CONSISTENCY — THE SCOUT\'S MAP</div>', unsafe_allow_html=True)
st.caption("Each dot = one player. Top-right quadrant = elite: high ACS and high consistency.")

dist_df = get_acs_distribution(engine)
if not dist_df.empty:
    acs_f = dist_df['avg_acs'].astype(float).tolist()
    cons_f = dist_df['consistency_score'].astype(float).tolist()
    dot_colors = []
    dot_sizes = []
    for c in cons_f:
        if c >= 70:
            dot_colors.append('#00D4FF')
            dot_sizes.append(7)
        elif c >= 40:
            dot_colors.append('#F5C518')
            dot_sizes.append(6)
        else:
            dot_colors.append('#FF4757')
            dot_sizes.append(5)

    avg_acs_line = sum(acs_f) / len(acs_f)
    avg_cons_line = sum(cons_f) / len(cons_f)

    fig_sc = go.Figure()
    fig_sc.add_trace(go.Scatter(
        x=acs_f,
        y=cons_f,
        mode='markers',
        marker=dict(color=dot_colors, size=dot_sizes, opacity=0.75, line=dict(color='#1C1C24', width=0.5)),
        hovertemplate='ACS: %{x:.0f}<br>Consistency: %{y:.1f}<extra></extra>',
        name='Players'
    ))
    fig_sc.add_vline(x=avg_acs_line, line=dict(color='#444455', width=1, dash='dot'))
    fig_sc.add_hline(y=avg_cons_line, line=dict(color='#444455', width=1, dash='dot'))
    fig_sc.add_annotation(x=max(acs_f)*0.97, y=max(cons_f)*0.97,
        text="ELITE ZONE", showarrow=False,
        font=dict(color='#00D4FF', size=11, family='Rajdhani'),
        bgcolor='rgba(0,212,255,0.08)', bordercolor='#00D4FF', borderwidth=1)
    fig_sc.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='#1C1C24',
        height=400,
        showlegend=False,
        margin=dict(l=40, r=20, t=20, b=40),
        font=dict(color='#888899', family='Inter', size=11)
    )
    fig_sc.update_xaxes(**AXIS, title_text='Average ACS', title_font=dict(color='#888899', size=11), tickfont=dict(color='#888899'))
    fig_sc.update_yaxes(**AXIS, title_text='Consistency Score', title_font=dict(color='#888899', size=11), tickfont=dict(color='#888899'))
    st.plotly_chart(fig_sc, use_container_width=True)
    st.caption("🔵 Elite consistency (70+)   🟡 Solid (40–70)   🔴 Volatile (<40)   Dotted lines = global averages")
else:
    st.info("No scatter data available.")

# ── SECTION 2: Leaderboard Table ──
st.markdown('<div class="section-title">🏆 GLOBAL LEADERBOARD</div>', unsafe_allow_html=True)

lb_df = get_leaderboard(engine, min_matches=min_matches)
if not lb_df.empty:
    lb_df['avg_acs'] = pd.to_numeric(lb_df['avg_acs'], errors='coerce').fillna(0)
    lb_df['avg_kd'] = pd.to_numeric(lb_df['avg_kd'], errors='coerce').fillna(0)
    lb_df['consistency'] = pd.to_numeric(lb_df['consistency'], errors='coerce').fillna(0)
    lb_df['kast_pct'] = pd.to_numeric(lb_df['kast_pct'], errors='coerce').fillna(0)

    if tier_filter == "Elite (70+)":
        lb_df = lb_df[lb_df['consistency'] >= 70]
    elif tier_filter == "Solid (40–70)":
        lb_df = lb_df[(lb_df['consistency'] >= 40) & (lb_df['consistency'] < 70)]
    elif tier_filter == "Volatile (<40)":
        lb_df = lb_df[lb_df['consistency'] < 40]

    lb_df = lb_df.sort_values(by=sort_column, ascending=False).reset_index(drop=True)
    lb_df['rank_display'] = lb_df.index + 1
    total = len(lb_df)
    st.caption(f"{total} players match current filters.")

    per_page = 25
    page = st.number_input('Page', 1, max(1, (total + per_page - 1) // per_page), 1)
    start = (page - 1) * per_page
    chunk = lb_df.iloc[start:start + per_page]

    import numpy as np
    chunk = chunk.copy()
    chunk['region'] = chunk['region'].replace({float('nan'): '—'}).fillna('—')
    chunk['rank'] = chunk['rank_display'].apply(lambda r: '🥇' if r==1 else '🥈' if r==2 else '🥉' if r==3 else f"#{int(r)}")
    chunk['tier'] = chunk['consistency'].apply(lambda c: '🔵 Elite' if float(c)>=70 else '🟡 Solid' if float(c)>=40 else '🔴 Volatile')
    display_df = chunk[['rank','name','region','avg_acs','kast_pct','consistency','tier','matches_played']].copy()
    display_df.columns = ['Rank','Player','Region','ACS','KAST %','Consistency','Tier','Matches']
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Rank': st.column_config.TextColumn(width='small'),
            'Player': st.column_config.TextColumn(width='medium'),
            'Region': st.column_config.TextColumn(width='small'),
            'ACS': st.column_config.NumberColumn(format='%.1f', width='small'),
            'KAST %': st.column_config.NumberColumn(format='%.1f', width='small'),
            'Consistency': st.column_config.NumberColumn(format='%.1f', width='small'),
            'Tier': st.column_config.TextColumn(width='small'),
            'Matches': st.column_config.NumberColumn(format='%d', width='small'),
        }
    )
else:
    st.warning("No players found matching criteria.")

# ── SECTION 3: India Spotlight ──
indian = get_indian_spotlight(engine)
if not indian.empty:
    st.markdown('<div class="section-title">🇮🇳 INDIA SPOTLIGHT</div>', unsafe_allow_html=True)
    ind_cols = st.columns(len(indian))
    indian['region'] = indian['region'].fillna('—') if 'region' in indian.columns else '—'
    for i, (_, r) in enumerate(indian.iterrows()):
        with ind_cols[i]:
            tier_label, tier_color = consistency_tier(r['consistency'])
            st.metric("Player", str(r['name']))
            st.metric("Avg ACS", f"{float(r['avg_acs']):.1f}")
            st.metric("Consistency", f"{float(r['consistency']):.1f}")
            st.metric("Global Rank", f"Top {100 - int(float(r['global_percentile']))}%")

st.markdown('</div>', unsafe_allow_html=True)
render_glossary()
