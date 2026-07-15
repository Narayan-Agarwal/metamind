import streamlit as st
import streamlit.components.v1 as components
from db.connection import get_engine
from db.queries import get_leaderboard
from utils.styles import GLOBAL_CSS, render_nav, HOME_HERO_HTML, render_glossary
import pandas as pd

st.set_page_config(
    page_title="MetaMind — Esports Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
render_nav(active_page='')

# 3D animated hero
components.html(HOME_HERO_HTML, height=320)

st.markdown('<div class="main-content">', unsafe_allow_html=True)

# Live platform stats
engine = get_engine()
with engine.connect() as conn:
    from sqlalchemy import text
    players = conn.execute(text("SELECT COUNT(*) FROM players")).scalar()
    matches = conn.execute(text("SELECT COUNT(*) FROM matches")).scalar()
    maps = conn.execute(text("SELECT COUNT(*) FROM maps")).scalar()
    years = conn.execute(text("SELECT COUNT(DISTINCT year) FROM tournaments")).scalar()

c1,c2,c3,c4 = st.columns(4)
for col, num, label in [
    (c1, f"{players:,}", "PLAYERS"),
    (c2, f"{matches:,}", "MATCHES"),
    (c3, maps, "MAPS"),
    (c4, years, "YEARS OF DATA"),
]:
    col.markdown(f"""
    <div class="platform-stat">
      <div class="platform-num">{num}</div>
      <div class="platform-label">{label}</div>
    </div>""", unsafe_allow_html=True)

st.markdown('<div class="section-title">EXPLORE</div>', unsafe_allow_html=True)

f1,f2,f3 = st.columns(3)
features = [
    ('/Player','👤','PLAYER INTELLIGENCE',
     'Select any VCT pro — see their ACS percentile rank, radar profile, agent DNA, consistency score, and form status against the global field.'),
    ('/Team_Map','⚔️','PLAYER COMPARISON',
     'Compare up to 3 players head-to-head with radar charts, mirrored stat duels, gauge indicators, and a full stat breakdown.'),
    ('/Leaderboard','🏆','SCOUT\'S DASHBOARD',
     'Filter 900+ players by consistency tier. Spot elite talent on the skill vs consistency scatter map, search any player, and track India\'s top pros.'),
]
for col,(href,icon,title,desc) in zip([f1,f2,f3], features):
    col.markdown(f"""
    <a href="{href}" class="feat-card">
      <div class="feat-icon">{icon}</div>
      <div class="feat-title">{title}</div>
      <div class="feat-desc">{desc}</div>
    </a>""", unsafe_allow_html=True)

# Top 5 strip
st.markdown('<div class="section-title">🏆 TOP PERFORMERS</div>', unsafe_allow_html=True)
top5 = get_leaderboard(engine, min_matches=10).head(5)
medals = ['🥇','🥈','🥉','#4','#5']
medal_colors = ['#FFD700','#C0C0C0','#CD7F32','#FF4040','#FF4040']
acs_max_home = float(top5['avg_acs'].max()) if not top5.empty else 300
strip_html = '<div style="display:flex; gap:12px;">'
for i, (_, row) in enumerate(top5.iterrows()):
    acs_pct = int(float(row['avg_acs']) / acs_max_home * 100)
    c = medal_colors[i]
    strip_html += f"""
    <div style="flex:1; background:#1A1A24; border:1px solid #2E2E3A; border-top:3px solid {c};
        border-radius:8px; padding:16px 14px; position:relative; overflow:hidden;">
      <div style="position:absolute; bottom:0; left:0; height:3px; width:{acs_pct}%;
          background:linear-gradient(90deg,#FF4040,#F5C518); opacity:0.5;"></div>
      <div style="font-family:Rajdhani,sans-serif; font-size:13px; color:{c};
          font-weight:700; letter-spacing:1px; margin-bottom:4px;">{medals[i]} RANK {i+1}</div>
      <div style="font-family:Rajdhani,sans-serif; font-size:18px; font-weight:700;
          color:#EAEAEA; margin-bottom:6px; white-space:nowrap; overflow:hidden;
          text-overflow:ellipsis;">{row['name']}</div>
      <div style="font-family:Rajdhani,sans-serif; font-size:28px; font-weight:700;
          color:{c}; line-height:1;">{float(row['avg_acs']):.0f}</div>
      <div style="font-size:10px; color:#555566; letter-spacing:1.5px;
          text-transform:uppercase; margin-top:2px;">AVG ACS</div>
    </div>"""
strip_html += '</div>'
st.markdown(strip_html, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
render_glossary()
