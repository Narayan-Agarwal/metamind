import streamlit as st

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

* {box-sizing:border-box;}
.stApp {
  background:#1C1C24 !important;
  font-family:'Inter',sans-serif;
}
[data-testid="stSidebar"] {display:none !important;}
[data-testid="collapsedControl"] {
  display:none !important;
}
#MainMenu,footer,header {visibility:hidden;}
.block-container {
  padding-top:0 !important;
  max-width:100% !important;
}

/* ── TOP BAR ── */
.topbar {
  position:sticky; top:0; z-index:1000;
  background:#14141C;
  border-bottom:1px solid #2E2E3A;
  display:flex; align-items:center;
  justify-content:space-between;
  padding:0 28px; height:52px;
}
.topbar-logo {
  font-family:'Rajdhani',sans-serif;
  font-size:20px; font-weight:700;
  letter-spacing:2px; color:#EAEAEA;
}
.topbar-logo em {
  color:#F5C518; font-style:normal;
}
.topbar-nav {
  display:flex; gap:4px;
}
.topbar-nav a {
  font-family:'Inter',sans-serif;
  font-size:13px; font-weight:500;
  color:#888899; text-decoration:none;
  padding:6px 16px; border-radius:6px;
  transition:all 0.15s;
}
.topbar-nav a:hover {
  color:#EAEAEA; background:#252530;
}
.topbar-nav a.active {
  color:#F5C518; background:#252530;
}

/* ── LEFT ICON RAIL ── */
.icon-rail {
  position:fixed; left:0; top:52px;
  width:56px; height:calc(100vh - 52px);
  background:#14141C;
  border-right:1px solid #2E2E3A;
  display:flex; flex-direction:column;
  align-items:center; padding-top:16px;
  gap:8px; z-index:999;
}
.rail-icon {
  width:40px; height:40px;
  display:flex; align-items:center;
  justify-content:center;
  border-radius:8px; cursor:pointer;
  color:#888899; font-size:18px;
  transition:all 0.15s;
  text-decoration:none;
}
.rail-icon:hover {
  background:#252530; color:#EAEAEA;
}
.rail-icon.active {
  background:#252530; color:#F5C518;
}
.main-content {
  margin-left:56px;
  padding:24px 28px;
}

/* ── STAT CARDS ── */
.stat-card {
  background:#252530;
  border:1px solid #2E2E3A;
  border-radius:10px;
  padding:20px 24px;
  position:relative; overflow:hidden;
}
.stat-card::before {
  content:'';
  position:absolute; top:0; left:0;
  right:0; height:3px;
  background:#F5C518;
}
.stat-card.teal::before {background:#00D4FF;}
.stat-card.red::before {background:#FF4757;}
.stat-card.purple::before {background:#7F77DD;}
.stat-label {
  font-size:11px; font-weight:600;
  color:#888899; letter-spacing:1.5px;
  text-transform:uppercase; margin-bottom:10px;
}
.stat-value {
  font-family:'Rajdhani',sans-serif;
  font-size:36px; font-weight:700;
  color:#EAEAEA; line-height:1;
}
.stat-delta {
  font-size:12px; margin-top:6px;
}
.stat-delta.up {color:#00D4FF;}
.stat-delta.down {color:#FF4757;}

/* ── SECTION TITLE ── */
.section-title {
  font-family:'Rajdhani',sans-serif;
  font-size:18px; font-weight:700;
  color:#EAEAEA; letter-spacing:1px;
  text-transform:uppercase;
  margin:28px 0 16px;
  padding-left:12px;
  border-left:3px solid #F5C518;
}

/* ── INSIGHT CARDS ── */
.insight {
  background:#252530;
  border:1px solid #2E2E3A;
  border-radius:8px;
  padding:14px 18px; margin-bottom:10px;
  font-size:13px; color:#AAAABC;
  line-height:1.6;
  border-left:3px solid #F5C518;
}
.insight b {color:#EAEAEA;}

/* ── FORM BADGE ── */
.badge {
  display:inline-flex; align-items:center;
  gap:6px; padding:4px 12px;
  border-radius:20px; font-size:12px;
  font-weight:600; letter-spacing:0.5px;
}
.badge-peak {
  background:rgba(0,212,255,0.1);
  color:#00D4FF;
  border:1px solid rgba(0,212,255,0.25);
}
.badge-decline {
  background:rgba(255,71,87,0.1);
  color:#FF4757;
  border:1px solid rgba(255,71,87,0.25);
}
.badge-consistent {
  background:rgba(245,197,24,0.1);
  color:#F5C518;
  border:1px solid rgba(245,197,24,0.25);
}

/* ── HERO CARD ── */
.hero-card {
  background:linear-gradient(
    135deg, #252530 0%, #1C1C24 100%);
  border:1px solid #2E2E3A;
  border-radius:12px; padding:32px;
  margin-bottom:24px; position:relative;
  overflow:hidden;
}
.hero-card::after {
  content:'';
  position:absolute; top:-60px; right:-60px;
  width:200px; height:200px;
  background:radial-gradient(
    circle, rgba(245,197,24,0.08) 0%, 
    transparent 70%);
  border-radius:50%;
}
.hero-player-name {
  font-family:'Rajdhani',sans-serif;
  font-size:52px; font-weight:700;
  color:#EAEAEA; line-height:1;
  margin-bottom:10px;
}
.hero-summary {
  font-size:14px; color:#AAAABC;
  line-height:1.7; max-width:600px;
}

/* ── LEADERBOARD ROWS ── */
.lb-table {width:100%;}
.lb-header {
  display:grid;
  grid-template-columns:
    56px 1fr 120px 90px 90px 90px 80px;
  padding:8px 16px;
  font-size:11px; font-weight:600;
  color:#888899; letter-spacing:1px;
  text-transform:uppercase;
  border-bottom:1px solid #2E2E3A;
}
.lb-row {
  display:grid;
  grid-template-columns:
    56px 1fr 120px 90px 90px 90px 80px;
  padding:12px 16px;
  border-bottom:1px solid #1C1C24;
  align-items:center;
  transition:background 0.1s;
}
.lb-row:hover {background:#252530;}
.lb-row.top10 {background:rgba(245,197,24,0.03);}
.lb-row.top3 {background:rgba(245,197,24,0.06);}
.lb-rank {
  font-family:'Rajdhani',sans-serif;
  font-size:20px; font-weight:700;
  color:#888899; text-align:center;
}
.lb-rank.r1 {color:#FFD700;}
.lb-rank.r2 {color:#C0C0C0;}
.lb-rank.r3 {color:#CD7F32;}
.lb-name {
  font-size:14px; font-weight:600;
  color:#EAEAEA;
}
.lb-region {
  font-size:11px; color:#888899;
  margin-top:2px;
}
.lb-stat {
  font-family:'JetBrains Mono',monospace;
  font-size:14px; color:#EAEAEA;
  text-align:right;
}
.lb-stat.highlight {color:#F5C518;}

/* ── MAP BARS ── */
.map-bar {margin-bottom:14px;}
.map-bar-info {
  display:flex; justify-content:space-between;
  margin-bottom:5px;
}
.map-bar-name {
  font-size:13px; font-weight:500;
  color:#EAEAEA;
}
.map-bar-pct {
  font-family:'JetBrains Mono',monospace;
  font-size:13px; color:#888899;
}
.map-bar-track {
  height:10px; background:#2E2E3A;
  border-radius:5px; overflow:hidden;
}
.map-bar-fill {
  height:100%; border-radius:5px;
  transition:width 0.8s ease;
}
.fill-win {background:#00D4FF;}
.fill-mid {background:#F5C518;}
.fill-loss {background:#FF4757;}

/* ── INDIA SPOTLIGHT ── */
.india-card {
  background:#252530;
  border:1px solid #2E2E3A;
  border-top:3px solid #FF6B35;
  border-radius:10px; padding:20px 24px;
  margin-bottom:24px;
}
.india-header {
  font-family:'Rajdhani',sans-serif;
  font-size:16px; font-weight:700;
  color:#EAEAEA; letter-spacing:1px;
  margin-bottom:14px;
}

/* ── PERCENTILE BARS ── */
.pct-bar {margin-bottom:12px;}
.pct-bar-top {
  display:flex; justify-content:space-between;
  margin-bottom:4px;
}
.pct-bar-label {
  font-size:12px; color:#888899;
  text-transform:uppercase;
  letter-spacing:0.5px;
}
.pct-bar-val {
  font-family:'JetBrains Mono',monospace;
  font-size:12px; color:#F5C518;
}
.pct-bar-track {
  height:6px; background:#2E2E3A;
  border-radius:3px; overflow:hidden;
}
.pct-bar-fill {
  height:100%; border-radius:3px;
  background:linear-gradient(
    90deg, #F5C518, #FFD700);
}

/* ── HOME HERO ── */
@keyframes pulse {
  0%,100% {opacity:0.6;}
  50% {opacity:1;}
}
@keyframes float {
  0%,100% {transform:translateY(0);}
  50% {transform:translateY(-8px);}
}
.home-hero {
  text-align:center;
  padding:64px 32px 48px;
  position:relative;
}
.home-hero-title {
  font-family:'Rajdhani',sans-serif;
  font-size:80px; font-weight:700;
  color:#EAEAEA; line-height:1;
  letter-spacing:4px;
}
.home-hero-title span {
  color:#F5C518;
  animation:pulse 3s ease infinite;
  display:inline-block;
}
.home-hero-sub {
  font-size:16px; color:#888899;
  margin-top:12px; letter-spacing:0.5px;
}
.home-glow {
  position:absolute;
  width:400px; height:400px;
  background:radial-gradient(
    circle, rgba(245,197,24,0.06) 0%, 
    transparent 70%);
  top:50%; left:50%;
  transform:translate(-50%,-50%);
  pointer-events:none;
}

/* ── FEATURE CARDS ── */
.feat-card {
  background:#252530;
  border:1px solid #2E2E3A;
  border-radius:10px; padding:28px;
  height:100%;
  transition:border-color 0.2s,
    box-shadow 0.2s, transform 0.2s;
  cursor:pointer; text-decoration:none;
  display:block;
}
.feat-card:hover {
  border-color:#F5C518;
  box-shadow:0 8px 32px rgba(245,197,24,0.1);
  transform:translateY(-2px);
}
.feat-icon {
  font-size:32px; margin-bottom:16px;
}
.feat-title {
  font-family:'Rajdhani',sans-serif;
  font-size:20px; font-weight:700;
  color:#EAEAEA; margin-bottom:8px;
}
.feat-desc {
  font-size:13px; color:#888899;
  line-height:1.6;
}

/* ── STAT PLATFORM COUNTS ── */
.platform-stat {
  text-align:center; padding:24px;
  background:#252530;
  border:1px solid #2E2E3A;
  border-radius:10px;
}
.platform-num {
  font-family:'Rajdhani',sans-serif;
  font-size:48px; font-weight:700;
  color:#F5C518; line-height:1;
}
.platform-label {
  font-size:11px; color:#888899;
  letter-spacing:2px;
  text-transform:uppercase;
  margin-top:6px;
}

/* ── PLOTLY OVERRIDE ── */
.js-plotly-plot .plotly {
  background:transparent !important;
}

/* ── STREAMLIT WIDGET OVERRIDES ── */
.stSelectbox > div > div {
  background:#252530 !important;
  border:1px solid #2E2E3A !important;
  color:#EAEAEA !important;
  border-radius:8px !important;
}
.stSlider .stSlider {accent-color:#F5C518;}
[data-testid="stMetricValue"] {
  font-family:'Rajdhani',sans-serif !important;
  color:#EAEAEA !important;
}
[data-testid="stMetricLabel"] {
  color:#888899 !important;
  font-size:11px !important;
  letter-spacing:1px !important;
  text-transform:uppercase !important;
}
</style>
"""

PLOTLY_THEME = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='#252530',
    font=dict(
        color='#888899', family='Inter',
        size=12
    ),
    hoverlabel=dict(
        bgcolor='#252530',
        bordercolor='#F5C518',
        font=dict(color='#EAEAEA', size=13),
    ),
    margin=dict(l=40,r=20,t=40,b=40),
)

AXIS_STYLE = dict(gridcolor='#2E2E3A', linecolor='#2E2E3A', tickcolor='#888899', showgrid=True)

def render_nav(active_page=''):
    st.markdown(f"""
    <div class="topbar">
      <div class="topbar-logo">
        <em>META</em>MIND
      </div>
    </div>
    <div class="icon-rail">
      <a href="/" title="Home" class="rail-icon">🏠</a>
      <a href="/Player" title="Player" class="rail-icon">👤</a>
      <a href="/Team_Map" title="Team Map" class="rail-icon">🗺️</a>
      <a href="/Leaderboard" title="Leaderboard" class="rail-icon">🏆</a>
    </div>
    """, unsafe_allow_html=True)
    
    gap,h,p,tm,lb = st.columns([4,1,1,1,1])
    with h:
        st.page_link("app.py", label="Home", use_container_width=True)
    with p:
        st.page_link("pages/1_Player.py", label="Player", use_container_width=True)
    with tm:
        st.page_link("pages/2_Team_Map.py", label="Team Map", use_container_width=True)
    with lb:
        st.page_link("pages/3_Leaderboard.py", label="Leaderboard", use_container_width=True)
    
    st.markdown("""
    <style>
    [data-testid="stPageLink"] {
        background:transparent !important;
        border:none !important;
        color:#888899 !important;
        font-family:'Inter',sans-serif !important;
        font-size:13px !important;
        padding:0 !important;
    }
    [data-testid="stPageLink"]:hover {
        color:#EAEAEA !important;
    }
    [data-testid="stPageLink-container"] {
        margin-top:-52px;
    }
    </style>
    """, unsafe_allow_html=True)

HOME_HERO_HTML = """
<!DOCTYPE html>
<html>
<head>
<style>
  * {margin:0;padding:0;box-sizing:border-box;}
  body {
    background:#1C1C24;
    font-family:'Rajdhani',sans-serif;
    overflow:hidden;
    height:320px;
  }
  canvas {
    position:absolute;top:0;left:0;
    width:100%;height:100%;
  }
  .content {
    position:relative;z-index:2;
    text-align:center;padding-top:80px;
  }
  h1 {
    font-size:72px;font-weight:700;
    color:#EAEAEA;letter-spacing:6px;
    line-height:1;
    font-family:'Rajdhani',sans-serif;
  }
  h1 span {color:#F5C518;}
  p {
    font-size:16px;color:#888899;
    margin-top:12px;letter-spacing:1px;
    font-family:'Inter',sans-serif;
  }
  @keyframes fadeUp {
    from {opacity:0;transform:translateY(20px);}
    to {opacity:1;transform:translateY(0);}
  }
  h1 {animation:fadeUp 0.8s ease forwards;}
  p {
    animation:fadeUp 0.8s 0.2s ease 
    both forwards;opacity:0;
  }
</style>
</head>
<body>
<canvas id="c"></canvas>
<div class="content">
  <h1><span>META</span>MIND</h1>
  <p>VALORANT PRO ANALYTICS PLATFORM</p>
</div>
<script>
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
canvas.width = window.innerWidth;
canvas.height = 320;

const particles = [];
for(let i=0;i<80;i++){
  particles.push({
    x: Math.random()*canvas.width,
    y: Math.random()*canvas.height,
    r: Math.random()*1.5+0.5,
    dx: (Math.random()-0.5)*0.4,
    dy: (Math.random()-0.5)*0.4,
    o: Math.random()*0.4+0.1
  });
}

function draw(){
  ctx.clearRect(0,0,canvas.width,canvas.height);
  
  // Draw connections
  particles.forEach((p,i)=>{
    particles.slice(i+1).forEach(q=>{
      const d = Math.hypot(p.x-q.x,p.y-q.y);
      if(d<120){
        ctx.beginPath();
        ctx.moveTo(p.x,p.y);
        ctx.lineTo(q.x,q.y);
        ctx.strokeStyle = `rgba(245,197,24,${0.08*(1-d/120)})`;
        ctx.lineWidth=0.5;
        ctx.stroke();
      }
    });
    
    // Draw particle
    ctx.beginPath();
    ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
    ctx.fillStyle=`rgba(245,197,24,${p.o})`;
    ctx.fill();
    
    p.x+=p.dx; p.y+=p.dy;
    if(p.x<0||p.x>canvas.width) p.dx*=-1;
    if(p.y<0||p.y>canvas.height) p.dy*=-1;
  });
  
  requestAnimationFrame(draw);
}
draw();
</script>
</body>
</html>
"""
