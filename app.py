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
     'Track individual form, peak matches, percentile rankings and performance trends across the full VCT dataset.'),
    ('/Team_Map','🗺️','TEAM MAP STRATEGY',
     'Analyze map win rates, attack vs defense splits, and economy patterns for any pro team.'),
    ('/Leaderboard','🏆','GLOBAL LEADERBOARD',
     'Rank all 11,000+ players by ACS, K/D, and consistency. Includes Indian pro player spotlight.'),
]
for col,(href,icon,title,desc) in zip([f1,f2,f3], features):
    col.markdown(f"""
    <a href="{href}" class="feat-card">
      <div class="feat-icon">{icon}</div>
      <div class="feat-title">{title}</div>
      <div class="feat-desc">{desc}</div>
    </a>""", unsafe_allow_html=True)

# Top 5 strip
st.markdown('<div class="section-title">TOP PERFORMERS</div>', unsafe_allow_html=True)
top5 = get_leaderboard(engine, min_matches=10).head(5)
cols = st.columns(5)
for col, (_, row) in zip(cols, top5.iterrows()):
    col.markdown(f"""
    <div class="stat-card teal">
      <div class="stat-label">RANK #{int(row['rank'])}</div>
      <div class="stat-value" style="font-size:22px">
        {row['name']}</div>
      <div class="stat-delta up">
        ACS {row['avg_acs']}</div>
    </div>""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
render_glossary()
