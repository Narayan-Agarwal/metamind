import streamlit as st
import plotly.graph_objects as go
from db.connection import get_engine
from db.queries import get_all_players, get_player_percentiles
from utils.styles import GLOBAL_CSS, PLOTLY_THEME, AXIS_STYLE, render_nav

st.set_page_config(page_title="Player Comparison", layout="wide", initial_sidebar_state="collapsed")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
render_nav(active_page='/Team_Map')
st.markdown('<div class="main-content">', unsafe_allow_html=True)

engine = get_engine()

@st.cache_data(ttl=3600)
def load_players():
    return get_all_players(engine)

players_df = load_players()
if players_df.empty:
    st.error("No player data found.")
    st.stop()

player_names = sorted(players_df['name'].tolist())

st.markdown('<div class="section-title">PLAYER COMPARISON</div>', unsafe_allow_html=True)
st.caption("Select up to 3 players to compare their performance profiles head-to-head.")

col1, col2, col3 = st.columns(3)
with col1:
    p1_name = st.selectbox("Player 1", ["— select —"] + player_names, key="p1")
with col2:
    p2_name = st.selectbox("Player 2", ["— select —"] + player_names, key="p2")
with col3:
    p3_name = st.selectbox("Player 3 (optional)", ["— select —"] + player_names, key="p3")

selected = [n for n in [p1_name, p2_name, p3_name] if n != "— select —"]

if len(selected) < 2:
    st.info("Select at least 2 players to compare.")
    st.stop()

pct_data = {}
for name in selected:
    pid = int(players_df[players_df['name'] == name]['player_id'].iloc[0])
    pct_df = get_player_percentiles(engine, pid)
    if pct_df is not None and not pct_df.empty:
        pct_data[name] = pct_df.iloc[0]

if len(pct_data) < 2:
    st.warning("Not enough percentile data for selected players.")
    st.stop()

RADAR_COLORS = ['#F5C518', '#00D4FF', '#FF4757']
radar_cats = ['ACS Rank', 'KAST %', 'Consistency', 'Experience', 'First Kill %']

def get_radar_vals(pct):
    return [
        float(pct['acs_percentile'] or 0) * 100,
        float(pct['avg_kast'] or 0),
        float(pct['consistency_score'] or 0),
        min(float(pct['matches_played'] or 0) / 50 * 100, 100),
        float(pct['avg_fb'] or 0) * 100
    ]

# ── SECTION 1: KPI cards ──
st.markdown('<div class="section-title">HEAD-TO-HEAD STATS</div>', unsafe_allow_html=True)
kpi_cols = st.columns(len(pct_data))
stat_keys = [
    ("Avg ACS", 'avg_acs', 1),
    ("KAST %", 'avg_kast', 1),
    ("Consistency", 'consistency_score', 1),
    ("Matches", 'matches_played', 0),
]
for i, (name, pct) in enumerate(pct_data.items()):
    with kpi_cols[i]:
        color = RADAR_COLORS[i % len(RADAR_COLORS)]
        st.markdown(f'<div style="border-left:3px solid {color}; padding-left:10px; margin-bottom:16px;"><b style="color:{color}; font-family:Rajdhani,sans-serif; font-size:18px;">{name}</b></div>', unsafe_allow_html=True)
        for label, key, prec in stat_keys:
            val = float(pct[key] or 0)
            st.metric(label, f"{val:.{prec}f}")

# ── SECTION 2: Radar chart ──
st.markdown('<div class="section-title">RADAR COMPARISON</div>', unsafe_allow_html=True)
fig_radar = go.Figure()
for i, (name, pct) in enumerate(pct_data.items()):
    vals = get_radar_vals(pct)
    vals_c = vals + [vals[0]]
    cats_c = radar_cats + [radar_cats[0]]
    c = RADAR_COLORS[i % len(RADAR_COLORS)]
    r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    fig_radar.add_trace(go.Scatterpolar(
        r=vals_c, theta=cats_c, fill='toself',
        fillcolor=f'rgba({r},{g},{b},0.12)',
        line=dict(color=c, width=2.5),
        marker=dict(size=7, color=c),
        name=name
    ))
fig_radar.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    polar=dict(
        bgcolor='#1C1C24',
        radialaxis=dict(visible=True, range=[0,100], gridcolor='#2E2E3A', color='#888899', tickfont=dict(size=10)),
        angularaxis=dict(gridcolor='#2E2E3A', color='#EAEAEA', tickfont=dict(size=13, family='Rajdhani'))
    ),
    showlegend=True,
    legend=dict(font=dict(color='#EAEAEA', family='Rajdhani', size=13), bgcolor='rgba(0,0,0,0)', orientation='h', y=-0.12),
    height=500, margin=dict(l=60,r=60,t=30,b=30),
    font=dict(color='#888899', family='Inter', size=11)
)
st.plotly_chart(fig_radar, use_container_width=True)

# ── SECTION 3: Per-stat bar comparison ──
st.markdown('<div class="section-title">STAT BREAKDOWN</div>', unsafe_allow_html=True)
bar_stats = [
    ("Avg ACS", 'avg_acs'),
    ("KAST %", 'avg_kast'),
    ("Consistency", 'consistency_score'),
]
bar_cols = st.columns(len(bar_stats))
for col_i, (label, key) in enumerate(bar_stats):
    with bar_cols[col_i]:
        names = list(pct_data.keys())
        vals = [float(pct_data[n][key] or 0) for n in names]
        colors_list = [RADAR_COLORS[i % len(RADAR_COLORS)] for i in range(len(names))]
        fig_bar = go.Figure(go.Bar(
            x=names, y=vals,
            marker=dict(color=colors_list, opacity=0.85, line=dict(color=colors_list, width=1)),
            text=[f"{v:.1f}" for v in vals],
            textposition='outside',
            textfont=dict(color='#EAEAEA', family='Rajdhani', size=13),
            hovertemplate='<b>%{x}</b><br>' + label + ': %{y:.1f}<extra></extra>'
        ))
        fig_bar.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='#1C1C24',
            height=260, margin=dict(l=10,r=10,t=30,b=10),
            title=dict(text=label, font=dict(color='#EAEAEA', family='Rajdhani', size=14)),
            showlegend=False,
            xaxis=dict(gridcolor='#2E2E3A', color='#888899', tickfont=dict(color='#EAEAEA', family='Rajdhani')),
            yaxis=dict(gridcolor='#2E2E3A', color='#888899', showgrid=True),
            font=dict(color='#888899')
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ── SECTION 4: Gauge indicators ──
st.markdown('<div class="section-title">PERFORMANCE GAUGES</div>', unsafe_allow_html=True)
gauge_cols = st.columns(len(pct_data))
for i, (name, pct) in enumerate(pct_data.items()):
    with gauge_cols[i]:
        c = RADAR_COLORS[i % len(RADAR_COLORS)]
        acs_rank = float(pct['acs_percentile'] or 0) * 100
        fig_g = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=acs_rank,
            delta=dict(reference=50, increasing=dict(color=c), decreasing=dict(color='#FF4757')),
            number=dict(suffix="th Pct", font=dict(color=c, size=26, family='Rajdhani')),
            title=dict(text=f"{name}<br><span style='font-size:12px;color:#888899'>ACS Percentile Rank</span>", font=dict(color='#EAEAEA', size=14, family='Rajdhani')),
            gauge=dict(
                axis=dict(range=[0,100], tickcolor='#2E2E3A', tickfont=dict(color='#888899', size=9)),
                bar=dict(color=c, thickness=0.3),
                bgcolor='#1C1C24', borderwidth=0,
                steps=[
                    dict(range=[0,33], color='#1C1C24'),
                    dict(range=[33,66], color='#252530'),
                    dict(range=[66,100], color='#2E2E3A'),
                ],
                threshold=dict(line=dict(color=c, width=3), thickness=0.85, value=acs_rank)
            )
        ))
        fig_g.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            height=260, margin=dict(l=20,r=20,t=50,b=10),
            font=dict(color='#888899')
        )
        st.plotly_chart(fig_g, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)
