import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from db.connection import get_engine
from db.queries import get_leaderboard, get_south_asia_spotlight, get_acs_distribution
from utils.styles import GLOBAL_CSS, AXIS_STYLE, render_nav, render_glossary

st.set_page_config(page_title="Global Leaderboard", layout="wide", initial_sidebar_state="collapsed")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown('<style>:root{--page-accent:#FF4757;}</style>', unsafe_allow_html=True)
render_nav(active_page='/Leaderboard')
st.markdown('<div class="main-content">', unsafe_allow_html=True)

engine = get_engine()
AXIS = dict(gridcolor='#2E2E3A', linecolor='#2E2E3A', tickcolor='#888899', showgrid=True)

def consistency_tier(score):
    s = float(score)
    if s >= 70: return 'Elite', '#00D4FF'
    elif s >= 40: return 'Solid', '#F5C518'
    else: return 'Volatile', '#FF4757'

import streamlit.components.v1 as components

try:
    sa_df = get_south_asia_spotlight(engine)
    if not sa_df.empty:
        st.markdown('<div class="section-title">🌏 SOUTH ASIA SPOTLIGHT</div>', unsafe_allow_html=True)
        st.caption(f"Top {len(sa_df)} South Asian VCT pros by ACS — players with 5+ tracked matches.")
        sa_cols = st.columns(len(sa_df))
        for i, (_, r) in enumerate(sa_df.iterrows()):
            cons = float(r['consistency'])
            if cons >= 70:
                tier_label, tier_color = 'Elite', '#00D4FF'
            elif cons >= 40:
                tier_label, tier_color = 'Solid', '#F5C518'
            else:
                tier_label, tier_color = 'Volatile', '#FF4757'
            top_pct = max(1, 100 - int(float(r['global_percentile'])))
            with sa_cols[i]:
                st.markdown(f"""
<div style="background:#1A1A24; border:1px solid {tier_color}33;
    border-top:3px solid {tier_color}; border-radius:10px;
    padding:16px 14px; text-align:center;">
  <div style="font-family:Rajdhani,sans-serif; font-size:18px; font-weight:700;
      color:#EAEAEA; margin-bottom:2px;
      text-shadow:0 0 12px {tier_color}44;">{r['name']}</div>
  <div style="font-size:11px; color:{tier_color}; font-weight:600;
      letter-spacing:1px; margin-bottom:10px;">● {tier_label}</div>
  <div style="font-family:Rajdhani,sans-serif; font-size:32px; font-weight:700;
      color:{tier_color}; line-height:1;">{float(r['avg_acs']):.0f}</div>
  <div style="font-size:10px; color:#555566; letter-spacing:1.5px;
      text-transform:uppercase; margin-bottom:8px;">AVG ACS</div>
  <div style="font-size:12px; color:#888899;">
      KAST {float(r['avg_kast']):.1f}% · {int(r['matches_played'])}M</div>
  <div style="font-size:11px; color:#555566; margin-top:4px;">
      🌏 Top {top_pct}% globally</div>
</div>""", unsafe_allow_html=True)
except Exception:
    pass

st.divider()

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

# ── LOAD DATA ──
lb_raw = get_leaderboard(engine, min_matches=5)
if lb_raw.empty:
    st.warning("No player data available.")
    st.stop()

for col in ['avg_acs', 'avg_kd', 'consistency', 'kast_pct']:
    lb_raw[col] = pd.to_numeric(lb_raw[col], errors='coerce').fillna(0)
lb_raw['matches_played'] = pd.to_numeric(lb_raw['matches_played'], errors='coerce').fillna(0)
lb_raw['region'] = lb_raw['region'].fillna('—').replace('nan', '—')
lb_raw['name'] = lb_raw['name'].fillna('Unknown')

# ── SECTION 2: SCOUT MAP — responds to both filters ──
st.markdown('<div class="section-title">⚡ SKILL vs CONSISTENCY — THE SCOUT\'S MAP</div>', unsafe_allow_html=True)
st.caption("Each dot = one player. Filtered players highlighted — others faded. Hover a dot to see the player name.")

dist_df = get_acs_distribution(engine, min_matches=min_matches)
if not dist_df.empty:
    dist_df['avg_acs'] = pd.to_numeric(dist_df['avg_acs'], errors='coerce').fillna(0)
    dist_df['consistency_score'] = pd.to_numeric(dist_df['consistency_score'], errors='coerce').fillna(0)
    dist_df['name'] = dist_df['name'].fillna('')

    def in_filter(cons):
        if tier_filter == "Elite (70+)": return cons >= 70
        elif tier_filter == "Solid (40–70)": return 40 <= cons < 70
        elif tier_filter == "Volatile (<40)": return cons < 40
        return True

    acs_vals = dist_df['avg_acs'].tolist()
    cons_vals = dist_df['consistency_score'].tolist()
    names_all = dist_df['name'].tolist()
    avg_acs_line = float(np.mean(acs_vals)) if acs_vals else 200
    avg_cons_line = float(np.mean(cons_vals)) if cons_vals else 60

    h_x, h_y, h_c, h_names = [], [], [], []
    f_x, f_y = [], []

    for acs, cons, name in zip(acs_vals, cons_vals, names_all):
        if in_filter(cons):
            h_x.append(acs)
            h_y.append(cons)
            h_names.append(name)
            h_c.append('#00D4FF' if cons >= 70 else '#F5C518' if cons >= 40 else '#FF4757')
        else:
            f_x.append(acs)
            f_y.append(cons)

    fig_sc = go.Figure()
    if f_x:
        fig_sc.add_trace(go.Scatter(
            x=f_x, y=f_y, mode='markers',
            marker=dict(color='#2E2E3A', size=5, opacity=0.25),
            hoverinfo='skip', showlegend=False
        ))
    if h_x:
        fig_sc.add_trace(go.Scatter(
            x=h_x, y=h_y, mode='markers',
            marker=dict(color=h_c, size=7, opacity=0.85, line=dict(color='#1C1C24', width=0.5)),
            text=h_names,
            hovertemplate='<b>%{text}</b><br>ACS: %{x:.0f}<br>Consistency: %{y:.1f}<extra></extra>',
            showlegend=False
        ))
    if acs_vals:
        fig_sc.add_vline(x=avg_acs_line, line=dict(color='#444455', width=1, dash='dot'))
        fig_sc.add_hline(y=avg_cons_line, line=dict(color='#444455', width=1, dash='dot'))
        fig_sc.add_annotation(
            x=max(acs_vals) * 0.97, y=max(cons_vals) * 0.97,
            text="ELITE ZONE", showarrow=False,
            font=dict(color='#00D4FF', size=11, family='Rajdhani'),
            bgcolor='rgba(0,212,255,0.08)', bordercolor='#00D4FF', borderwidth=1
        )
    fig_sc.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='#1C1C24',
        height=420, showlegend=False,
        margin=dict(l=40, r=20, t=20, b=40),
        font=dict(color='#888899', family='Inter', size=11)
    )
    fig_sc.update_xaxes(**AXIS, title_text='Average ACS', title_font=dict(color='#888899', size=11), tickfont=dict(color='#888899'))
    fig_sc.update_yaxes(**AXIS, title_text='Consistency Score', title_font=dict(color='#888899', size=11), tickfont=dict(color='#888899'))
    st.plotly_chart(fig_sc, use_container_width=True)
    st.caption(f"Showing {len(h_x)} highlighted / {len(acs_vals)} total players with {min_matches}+ matches   🔵 Elite   🟡 Solid   🔴 Volatile   Dotted = global averages")

# ── APPLY FILTERS ──
lb_df = lb_raw[lb_raw['matches_played'] >= min_matches].copy()
if tier_filter == "Elite (70+)":
    lb_df = lb_df[lb_df['consistency'] >= 70]
elif tier_filter == "Solid (40–70)":
    lb_df = lb_df[(lb_df['consistency'] >= 40) & (lb_df['consistency'] < 70)]
elif tier_filter == "Volatile (<40)":
    lb_df = lb_df[lb_df['consistency'] < 40]

lb_df = lb_df.sort_values(by=sort_column, ascending=False).reset_index(drop=True)
lb_df['rank_display'] = lb_df.index + 1
total = len(lb_df)

# ── SECTION 3: PODIUM ──
if total >= 1:
    st.markdown('<div class="section-title">🏆 TOP PERFORMERS</div>', unsafe_allow_html=True)
    podium_medals = ['🥇','🥈','🥉']
    podium_classes = ['p1','p2','p3']
    podium_count = min(3, total)
    pod_html = '<div style="display:grid; grid-template-columns:repeat(' + str(podium_count) + ',1fr); gap:16px; margin-bottom:8px;">'
    for i in range(podium_count):
        row = lb_df.iloc[i]
        tier_label, tier_color = consistency_tier(row['consistency'])
        pc = podium_classes[i]
        pod_html += f"""
        <div class="podium-card {pc}">
            <div class="podium-medal">{podium_medals[i]}</div>
            <div class="podium-name">{row['name']}</div>
            <div style="font-size:11px; color:#555566; margin-bottom:10px; text-transform:uppercase; letter-spacing:1px;">{row['region'] if row['region'] != '—' else 'Unknown Region'}</div>
            <div class="podium-acs {pc}">{float(row['avg_acs']):.1f}</div>
            <div class="podium-label">AVG ACS · {int(row['matches_played'])} MATCHES</div>
            <div class="podium-tier" style="color:{tier_color};">● {tier_label} · {float(row['consistency']):.1f}</div>
        </div>"""
    pod_html += '</div>'
    st.markdown(pod_html, unsafe_allow_html=True)

# ── SECTION 4: PLAYER LOOKUP ──
st.markdown('<div class="section-title">🔍 PLAYER LOOKUP</div>', unsafe_allow_html=True)
search_name = st.text_input("Search player by name", placeholder="e.g. Wardell, aspas, Derke...")
if search_name.strip():
    found = lb_raw[lb_raw['name'].str.contains(search_name.strip(), case=False, na=False)]
    if not found.empty:
        for _, r in found.head(3).iterrows():
            tier_label, tier_color = consistency_tier(r['consistency'])
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Player", r['name'])
            with c2: st.metric("Avg ACS", f"{float(r['avg_acs']):.1f}")
            with c3: st.metric("KAST %", f"{float(r['kast_pct']):.1f}%")
            with c4: st.metric("Consistency", f"{float(r['consistency']):.1f} ({tier_label})")
            radar_vals = [
                min(float(r['avg_acs']) / 300 * 100, 100),
                float(r['kast_pct']),
                float(r['consistency']),
                min(float(r['matches_played']) / 30 * 100, 100),
            ]
            radar_cats = ['ACS', 'KAST %', 'Consistency', 'Experience']
            rv_c = radar_vals + [radar_vals[0]]
            rc_c = radar_cats + [radar_cats[0]]
            rgb = (int(tier_color[1:3],16), int(tier_color[3:5],16), int(tier_color[5:7],16))
            fig_r = go.Figure()
            fig_r.add_trace(go.Scatterpolar(
                r=rv_c, theta=rc_c, fill='toself',
                fillcolor=f'rgba({rgb[0]},{rgb[1]},{rgb[2]},0.15)',
                line=dict(color=tier_color, width=2),
                marker=dict(size=6, color=tier_color)
            ))
            fig_r.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                polar=dict(
                    bgcolor='#1C1C24',
                    radialaxis=dict(visible=True, range=[0,100], gridcolor='#2E2E3A', color='#888899', tickfont=dict(size=9)),
                    angularaxis=dict(gridcolor='#2E2E3A', color='#EAEAEA', tickfont=dict(size=12, family='Rajdhani'))
                ),
                showlegend=False, height=300,
                margin=dict(l=40, r=40, t=20, b=20),
                font=dict(color='#888899', family='Inter', size=11)
            )
            st.plotly_chart(fig_r, use_container_width=True)
            st.divider()
    else:
        st.info(f"No players found matching '{search_name}'.")

# ── SECTION 5: FULL TABLE ──
st.markdown('<div class="section-title">📋 FULL LEADERBOARD</div>', unsafe_allow_html=True)
if total > 0:
    st.caption(f"{total} players match current filters.")
    per_page = 25
    max_page = max(1, (total + per_page - 1) // per_page)
    page = st.number_input('Page', 1, max_page, 1)
    start = (page - 1) * per_page
    chunk = lb_df.iloc[start:start + per_page].copy()
    acs_max = float(lb_df['avg_acs'].max()) if total > 0 else 300.0

    sb_html = """
    <div class="sb-header">
        <div>RANK</div><div>PLAYER</div><div>REGION</div>
        <div>ACS</div><div>KAST %</div><div>CONSISTENCY</div>
        <div>TIER</div><div>MATCHES</div>
    </div>
    """
    for _, row in chunk.iterrows():
        rank = int(row['rank_display'])
        cons = float(row['consistency'])
        acs = float(row['avg_acs'])
        kast = float(row['kast_pct'])
        region = str(row['region']) if row['region'] != '—' else '—'
        matches = int(row['matches_played'])

        if rank == 1:
            row_cls = 'sb-row rank-1'
            rank_cls = 'sb-rank r1'
            rank_disp = '🥇'
        elif rank == 2:
            row_cls = 'sb-row rank-2'
            rank_cls = 'sb-rank r2'
            rank_disp = '🥈'
        elif rank == 3:
            row_cls = 'sb-row rank-3'
            rank_cls = 'sb-rank r3'
            rank_disp = '🥉'
        elif rank <= 10:
            row_cls = 'sb-row top10'
            rank_cls = 'sb-rank rtop'
            rank_disp = f'#{rank}'
        else:
            row_cls = 'sb-row'
            rank_cls = 'sb-rank'
            rank_disp = f'#{rank}'

        if cons >= 70:
            tier_cls = 'sb-tier elite'
            tier_txt = '● ELITE'
        elif cons >= 40:
            tier_cls = 'sb-tier solid'
            tier_txt = '● SOLID'
        else:
            tier_cls = 'sb-tier volatile'
            tier_txt = '● VOLATILE'

        acs_bar_pct = int(acs / acs_max * 100) if acs_max > 0 else 0

        sb_html += f"""
        <div class="{row_cls}">
            <div class="{rank_cls}">{rank_disp}</div>
            <div class="sb-name">{row['name']}</div>
            <div class="sb-region">{region}</div>
            <div class="sb-acs">
                <span class="sb-acs-val">{acs:.0f}</span>
                <div class="sb-acs-bar-track">
                    <div class="sb-acs-bar-fill" style="width:{acs_bar_pct}%;"></div>
                </div>
            </div>
            <div class="sb-stat">{kast:.1f}%</div>
            <div class="sb-stat">{cons:.1f}</div>
            <div><span class="{tier_cls}">{tier_txt}</span></div>
            <div class="sb-matches">{matches}</div>
        </div>
        """

    # Wrap with full HTML doc so CSS classes and inline styles both render
    full_sb_html = f"""
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=Inter:wght@400;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
    body {{ margin:0; background:transparent; }}
    .sb-header {{
      display:grid;
      grid-template-columns: 64px 1fr 100px 140px 90px 100px 80px 70px;
      padding:10px 16px;
      background:#0F0F18;
      border-top:2px solid #FF4040;
      border-bottom:1px solid #2E2E3A;
      font-size:10px; font-weight:700;
      color:#888899; letter-spacing:1.5px;
      text-transform:uppercase;
      font-family:'Inter',sans-serif;
    }}
    .sb-row {{
      display:grid;
      grid-template-columns: 64px 1fr 100px 140px 90px 100px 80px 70px;
      padding:0 16px; height:52px;
      align-items:center;
      border-bottom:1px solid rgba(46,46,58,0.6);
      transition:background 0.12s;
    }}
    .sb-row:hover {{ background:rgba(255,64,64,0.04); }}
    .sb-row.rank-1 {{ background:rgba(255,215,0,0.04); border-left:3px solid #FFD700; }}
    .sb-row.rank-2 {{ background:rgba(192,192,192,0.03); border-left:3px solid #C0C0C0; }}
    .sb-row.rank-3 {{ background:rgba(205,127,50,0.03); border-left:3px solid #CD7F32; }}
    .sb-row.top10 {{ border-left:3px solid rgba(255,64,64,0.3); }}
    .sb-rank {{ font-family:'Rajdhani',sans-serif; font-size:22px; font-weight:700; color:#444455; text-align:center; }}
    .sb-rank.r1 {{ color:#FFD700; font-size:26px; }}
    .sb-rank.r2 {{ color:#C0C0C0; font-size:24px; }}
    .sb-rank.r3 {{ color:#CD7F32; font-size:24px; }}
    .sb-rank.rtop {{ color:#FF4040; font-size:18px; }}
    .sb-name {{ font-size:14px; font-weight:600; color:#EAEAEA; letter-spacing:0.3px; font-family:'Inter',sans-serif; }}
    .sb-region {{ font-size:11px; color:#555566; text-transform:uppercase; letter-spacing:1px; font-family:'Inter',sans-serif; }}
    .sb-acs {{ display:flex; align-items:center; gap:8px; }}
    .sb-acs-val {{ font-family:'Rajdhani',sans-serif; font-size:16px; font-weight:700; color:#F5C518; min-width:40px; }}
    .sb-acs-bar-track {{ flex:1; height:4px; background:#2E2E3A; border-radius:2px; overflow:hidden; }}
    .sb-acs-bar-fill {{ height:4px; border-radius:2px; background:linear-gradient(90deg,#FF4040,#F5C518); }}
    .sb-stat {{ font-family:'JetBrains Mono',monospace; font-size:13px; color:#AAAABC; text-align:right; }}
    .sb-tier {{ font-size:11px; font-weight:600; letter-spacing:0.5px; text-align:center; padding:3px 8px; border-radius:4px; }}
    .sb-tier.elite {{ color:#00D4FF; background:rgba(0,212,255,0.08); border:1px solid rgba(0,212,255,0.2); }}
    .sb-tier.solid {{ color:#F5C518; background:rgba(245,197,24,0.08); border:1px solid rgba(245,197,24,0.2); }}
    .sb-tier.volatile {{ color:#FF4757; background:rgba(255,71,87,0.08); border:1px solid rgba(255,71,87,0.2); }}
    .sb-matches {{ font-size:12px; color:#555566; text-align:right; font-family:'Inter',sans-serif; }}
    </style>
    {sb_html}
    """
    components.html(full_sb_html, height=min(52 * len(chunk) + 60, 1400), scrolling=True)
else:
    st.warning("No players match current filters. Try selecting 'All' tiers or reducing the minimum matches.")

st.markdown('</div>', unsafe_allow_html=True)
render_glossary()
