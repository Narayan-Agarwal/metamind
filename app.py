import streamlit as st
import pandas as pd
from sqlalchemy import text
from db.connection import get_engine

st.set_page_config(
    page_title="MetaMind",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=Inter:wght@400;500;600&display=swap');

[data-testid="stSidebar"] {display:none !important;}
[data-testid="collapsedControl"] {display:none !important;}
#MainMenu, footer, header {visibility:hidden;}
.stApp {background:#0A0A0F !important;}

/* Top nav bar */
.topnav {
  display:flex; align-items:center;
  justify-content:space-between;
  background:#111118;
  border-bottom:1px solid #2A2A45;
  padding:0 32px; height:56px;
  position:sticky; top:0; z-index:999;
}
.topnav-logo {
  font-family:'Rajdhani',sans-serif;
  font-size:22px; font-weight:700;
  color:#EEEEF5; letter-spacing:1px;
}
.topnav-logo span {color:#7F77DD;}
.topnav-links {display:flex; gap:32px;}
.topnav-link {
  font-family:'Inter',sans-serif;
  font-size:13px; color:#8888AA;
  text-decoration:none; cursor:pointer;
  padding-bottom:4px;
  border-bottom:2px solid transparent;
  transition:all 0.2s;
}
.topnav-link:hover {color:#EEEEF5;}
.topnav-link.active {
  color:#7F77DD;
  border-bottom:2px solid #7F77DD;
}

/* KPI cards */
.kpi-card {
  background:#111118;
  border:1px solid #2A2A45;
  border-radius:8px;
  padding:20px 24px;
  border-left:3px solid #7F77DD;
}
.kpi-label {
  font-family:'Inter',sans-serif;
  font-size:11px; color:#8888AA;
  letter-spacing:1.5px;
  text-transform:uppercase; margin-bottom:8px;
}
.kpi-value {
  font-family:'Rajdhani',sans-serif;
  font-size:32px; font-weight:700;
  color:#EEEEF5; line-height:1;
}
.kpi-delta {font-size:12px; margin-top:4px;}
.kpi-delta.pos {color:#1D9E75;}
.kpi-delta.neg {color:#E84057;}

/* Hero card */
.hero-card {
  background:linear-gradient(135deg,#111118,#1A1A2E);
  border:1px solid #2A2A45;
  border-radius:12px; padding:32px;
  margin-bottom:24px;
}
.hero-name {
  font-family:'Rajdhani',sans-serif;
  font-size:48px; font-weight:700;
  color:#EEEEF5; line-height:1;
  margin-bottom:8px;
}
.hero-summary {
  font-family:'Inter',sans-serif;
  font-size:15px; color:#AAAACC;
  line-height:1.6;
}

/* Form status badges */
.badge {
  display:inline-block;
  padding:4px 14px; border-radius:20px;
  font-family:'Inter',sans-serif;
  font-size:12px; font-weight:600;
  letter-spacing:0.5px;
}
.badge-peaking {
  background:rgba(29,158,117,0.15);
  color:#1D9E75;
  border:1px solid rgba(29,158,117,0.3);
}
.badge-declining {
  background:rgba(232,64,87,0.15);
  color:#E84057;
  border:1px solid rgba(232,64,87,0.3);
}
.badge-consistent {
  background:rgba(127,119,221,0.15);
  color:#7F77DD;
  border:1px solid rgba(127,119,221,0.3);
}

/* Insight cards */
.insight-card {
  background:rgba(127,119,221,0.06);
  border-left:3px solid #7F77DD;
  border-radius:6px; padding:14px 18px;
  margin-bottom:10px;
  font-family:'Inter',sans-serif;
  font-size:13px; color:#AAAACC;
  line-height:1.6;
}
.insight-card strong {color:#EEEEF5;}

/* Section headers */
.section-header {
  font-family:'Rajdhani',sans-serif;
  font-size:20px; font-weight:700;
  color:#EEEEF5; margin:28px 0 16px;
  padding-bottom:8px;
  border-bottom:1px solid #2A2A45;
}

/* Stat bars */
.stat-bar-wrap {margin-bottom:12px;}
.stat-bar-label {
  display:flex; justify-content:space-between;
  font-family:'Inter',sans-serif;
  font-size:12px; color:#8888AA;
  margin-bottom:4px;
}
.stat-bar-track {
  background:#1A1A2E; border-radius:3px;
  height:8px; overflow:hidden;
}
.stat-bar-fill {
  height:100%; border-radius:3px;
  background:linear-gradient(90deg,#7F77DD,#9B94E8);
  transition:width 0.6s ease;
}

/* Map win rate bars */
.map-bar-wrap {margin-bottom:10px;}
.map-bar-header {
  display:flex; justify-content:space-between;
  font-family:'Inter',sans-serif;
  font-size:13px; margin-bottom:4px;
}
.map-name {color:#EEEEF5; font-weight:500;}
.map-pct {color:#8888AA;}
.map-bar-track {
  background:#1A1A2E; border-radius:4px;
  height:10px; overflow:hidden;
}

/* Leaderboard table styling */
.lb-row {
  display:grid;
  grid-template-columns:48px 1fr 100px 80px 80px 80px;
  gap:8px; padding:10px 16px;
  border-bottom:1px solid #1A1A2E;
  align-items:center;
  font-family:'Inter',sans-serif;
  font-size:13px;
}
.lb-row:hover {background:rgba(127,119,221,0.05);}
.lb-rank {
  font-family:'Rajdhani',sans-serif;
  font-size:18px; font-weight:700;
  color:#8888AA; text-align:center;
}
.lb-rank.gold {color:#FFD700;}
.lb-rank.silver {color:#C0C0C0;}
.lb-rank.bronze {color:#CD7F32;}
.lb-name {color:#EEEEF5; font-weight:500;}
.lb-region {color:#8888AA; font-size:11px;}
.lb-stat {
  color:#EEEEF5; text-align:right;
  font-family:'Rajdhani',sans-serif;
  font-size:16px;
}

/* Hero section */
@keyframes bgPulse {
  0%,100% {background-position:0% 50%;}
  50% {background-position:100% 50%;}
}
.hero-section {
  background:linear-gradient(-45deg, #0A0A0F,#1A1A2E,#0F0F1E,#111118);
  background-size:400% 400%;
  animation:bgPulse 8s ease infinite;
  padding:60px 32px; text-align:center;
  border-radius:12px; margin-bottom:32px;
}
.hero-title {
  font-family:'Rajdhani',sans-serif;
  font-size:72px; font-weight:700;
  color:#7F77DD; line-height:1;
  text-shadow:0 0 40px rgba(127,119,221,0.4);
}
.hero-subtitle {
  font-family:'Inter',sans-serif;
  font-size:18px; color:#8888AA;
  margin-top:8px;
}

/* Stat cards on home */
.stat-card {
  background:#111118;
  border:1px solid #2A2A45;
  border-top:3px solid #7F77DD;
  border-radius:8px; padding:24px;
  text-align:center;
}
.stat-card-num {
  font-family:'Rajdhani',sans-serif;
  font-size:44px; font-weight:700;
  color:#EEEEF5;
}
.stat-card-label {
  font-family:'Inter',sans-serif;
  font-size:11px; color:#8888AA;
  letter-spacing:2px;
  text-transform:uppercase;
  margin-top:4px;
}

/* Feature cards */
.feature-card {
  background:#111118;
  border:1px solid #2A2A45;
  border-radius:10px; padding:28px;
  transition:border-color 0.2s, box-shadow 0.2s;
  cursor:pointer;
  height:100%;
}
.feature-card:hover {
  border-color:#7F77DD;
  box-shadow:0 0 24px rgba(127,119,221,0.15);
}
.feature-title {
  font-family:'Rajdhani',sans-serif;
  font-size:20px; font-weight:700;
  color:#EEEEF5; margin-bottom:10px;
}
.feature-desc {
  font-family:'Inter',sans-serif;
  font-size:13px; color:#8888AA;
  line-height:1.6;
}

/* Streamlit widget overrides */
.stSelectbox > div > div {
  background:#111118 !important;
  border:1px solid #2A2A45 !important;
  color:#EEEEF5 !important;
}
.stSlider > div {accent-color:#7F77DD;}
[data-testid="stMetricValue"] {
  color:#EEEEF5 !important;
  font-family:'Rajdhani',sans-serif !important;
  font-size:28px !important;
}
</style>
"""

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

if 'page' not in st.session_state:
    st.session_state.page = 'home'

def render_nav(active='home'):
    pages = [
        ('home','⚡ Home'),
        ('Player','Player'),
        ('Team_Map','Team Map'),
        ('Leaderboard','Leaderboard')
    ]
    links = ""
    for p,label in pages:
        cls = "topnav-link active" if p==active else "topnav-link"
        links += f'''
        <span class="{cls}" 
          onclick="window.parent.location.href='/{p}'"
        >{label}</span>'''
    st.markdown(f"""
    <div class="topnav">
      <div class="topnav-logo">
        <span>META</span>MIND
      </div>
      <div class="topnav-links">{links}</div>
    </div>
    """, unsafe_allow_html=True)

render_nav('home')

st.markdown("""
<div class="hero-section">
    <div class="hero-title">METAMIND</div>
    <div class="hero-subtitle">Advanced Esports Analytics & Strategy Platform</div>
</div>
""", unsafe_allow_html=True)

engine = get_engine()

with engine.connect() as conn:
    total_players = conn.execute(text("SELECT COUNT(*) FROM players")).scalar()
    total_matches = conn.execute(text("SELECT COUNT(*) FROM matches")).scalar()
    total_maps = conn.execute(text("SELECT COUNT(*) FROM maps")).scalar()
    total_years = conn.execute(text("SELECT COUNT(DISTINCT year) FROM tournaments")).scalar()
    
    top_players = pd.read_sql("SELECT name, avg_acs FROM mv_player_percentiles ORDER BY avg_acs DESC LIMIT 5", conn)

st.markdown(f"""
<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:16px; margin-bottom:32px;">
    <div class="stat-card">
        <div class="stat-card-num">{total_players:,}</div>
        <div class="stat-card-label">Total Players</div>
    </div>
    <div class="stat-card">
        <div class="stat-card-num">{total_matches:,}</div>
        <div class="stat-card-label">Matches Analyzed</div>
    </div>
    <div class="stat-card">
        <div class="stat-card-num">{total_maps:,}</div>
        <div class="stat-card-label">Maps Covered</div>
    </div>
    <div class="stat-card">
        <div class="stat-card-num">{total_years}</div>
        <div class="stat-card-label">Years of Data</div>
    </div>
</div>
""", unsafe_allow_html=True)

cols = st.columns(3)
with cols[0]:
    st.markdown("""
    <div class="feature-card" onclick="window.parent.location.href='/Player'">
        <div class="feature-title">🎯 Player Intelligence</div>
        <div class="feature-desc">Deep-dive into individual player performance, agent pools, and historical form tracking with interactive visualizations.</div>
    </div>
    """, unsafe_allow_html=True)
with cols[1]:
    st.markdown("""
    <div class="feature-card" onclick="window.parent.location.href='/Team_Map'">
        <div class="feature-title">🗺️ Team & Map Strategy</div>
        <div class="feature-desc">Analyze team map pools, economy round win rates, and attack vs defense side biases to find strategic edges.</div>
    </div>
    """, unsafe_allow_html=True)
with cols[2]:
    st.markdown("""
    <div class="feature-card" onclick="window.parent.location.href='/Leaderboard'">
        <div class="feature-title">🏆 Global Leaderboard</div>
        <div class="feature-desc">Compare the world's best players across regions, sort by key metrics, and discover rising stars.</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="section-header">Top 5 Players Globally (by ACS)</div>', unsafe_allow_html=True)

lb_html = ""
for i, row in top_players.iterrows():
    rank = i + 1
    rank_cls = "gold" if rank == 1 else "silver" if rank == 2 else "bronze" if rank == 3 else ""
    lb_html += f"""
    <div class="lb-row">
        <div class="lb-rank {rank_cls}">#{rank}</div>
        <div class="lb-name">{row['name']}</div>
        <div></div>
        <div></div>
        <div></div>
        <div class="lb-stat">{row['avg_acs']:.1f} ACS</div>
    </div>
    """
st.markdown(f"<div>{lb_html}</div>", unsafe_allow_html=True)
