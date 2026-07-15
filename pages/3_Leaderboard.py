import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from db.connection import get_engine
from db.queries import get_leaderboard, get_indian_spotlight, get_acs_distribution
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
    indian = get_indian_spotlight(engine)
    if not indian.empty:
        st.markdown('<div class="section-title">🇮🇳 INDIA SPOTLIGHT</div>', unsafe_allow_html=True)
        st.caption("Top Indian VCT players in the global dataset — ranked by ACS.")

        def tier_info(cons):
            c = float(cons)
            if c >= 70: return 'ELITE', '#00D4FF', 'rgba(0,212,255,0.08)'
            elif c >= 40: return 'SOLID', '#F5C518', 'rgba(245,197,24,0.08)'
            else: return 'VOLATILE', '#FF4757', 'rgba(255,71,87,0.08)'

        def make_stat_bar(label, value, max_val, color, delay):
            pct = min(100, round(float(value) / max_val * 100, 1))
            return f"""
            <div style="margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; margin-bottom:3px;">
                    <span style="font-size:10px; color:#888899; font-family:Inter,sans-serif; letter-spacing:1px; text-transform:uppercase;">{label}</span>
                    <span style="font-size:11px; color:#EAEAEA; font-family:Rajdhani,sans-serif; font-weight:600;">{float(value):.1f}</span>
                </div>
                <div style="background:#1C1C24; border-radius:3px; height:5px; overflow:hidden;">
                    <div style="height:5px; background:{color}; border-radius:3px; width:0%;
                        animation: fillBar{delay} 1.2s ease-out {delay*0.15:.1f}s forwards;">
                    </div>
                </div>
            </div>
            <style>
            @keyframes fillBar{delay} {{
                from {{ width: 0%; }}
                to {{ width: {pct}%; }}
            }}
            </style>
            """

        def make_radar_svg(vals, color):
            import math
            n = len(vals)
            cx, cy, r = 60, 60, 45
            points = []
            for i, v in enumerate(vals):
                angle = math.pi * 2 * i / n - math.pi / 2
                rv = r * (float(v) / 100)
                x = cx + rv * math.cos(angle)
                y = cy + rv * math.sin(angle)
                points.append((x, y))
            grid_points = []
            for i in range(n):
                angle = math.pi * 2 * i / n - math.pi / 2
                x = cx + r * math.cos(angle)
                y = cy + r * math.sin(angle)
                grid_points.append(f"{x:.1f},{y:.1f}")
            polygon_pts = ' '.join([f"{x:.1f},{y:.1f}" for x,y in points])
            grid_poly = ' '.join(grid_points)
            r,g,b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
            return f"""
            <svg width="120" height="120" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
                <polygon points="{grid_poly}" fill="none" stroke="#2E2E3A" stroke-width="1"/>
                <polygon points="{polygon_pts}" fill="rgba({r},{g},{b},0.2)" stroke="{color}" stroke-width="1.5"
                    style="animation: radarPulse 2s ease-in-out infinite alternate;">
                </polygon>
                <style>
                @keyframes radarPulse {{
                    from {{ opacity: 0.7; }}
                    to {{ opacity: 1; }}
                }}
                </style>
            </svg>
            """

        cards_html = """
        <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
        <div style="display:flex; gap:16px; flex-wrap:wrap; padding:8px 0 16px 0;">
        """

        for rank_i, (_, r) in enumerate(indian.iterrows()):
            tier_label, tier_color, tier_bg = tier_info(r['consistency'])
            gp = int(float(r['global_percentile']))
            top_pct = max(1, 100 - gp)

            radar_vals = [
                min(float(r['avg_acs']) / 300 * 100, 100),
                float(r['avg_kast']),
                float(r['consistency']),
                float(r['avg_hs_pct']),
                min(float(r['avg_fb_pct']), 100),
            ]
            radar_svg = make_radar_svg(radar_vals, tier_color)

            stat_bars = (
                make_stat_bar('ACS', r['avg_acs'], 300, tier_color, rank_i*5+1) +
                make_stat_bar('KAST %', r['avg_kast'], 100, tier_color, rank_i*5+2) +
                make_stat_bar('HS %', r['avg_hs_pct'], 50, tier_color, rank_i*5+3) +
                make_stat_bar('FIRST KILL %', r['avg_fb_pct'], 30, tier_color, rank_i*5+4)
            )

            rank_badge = ['🥇','🥈','🥉','④','⑤'][rank_i]

            r_hex = int(tier_color[1:3],16)
            g_hex = int(tier_color[3:5],16)
            b_hex = int(tier_color[5:7],16)

            cards_html += f"""
            <div style="
                flex: 1; min-width: 200px; max-width: 240px;
                background: #1A1A24;
                border: 1px solid rgba({r_hex},{g_hex},{b_hex},0.3);
                border-top: 3px solid {tier_color};
                border-radius: 12px;
                padding: 18px 16px;
                position: relative;
                overflow: hidden;
                animation: cardIn 0.5s ease-out {rank_i*0.1:.1f}s both;
                box-shadow: 0 0 20px rgba({r_hex},{g_hex},{b_hex},0.08);
            ">
                <style>
                @keyframes cardIn {{
                    from {{ opacity:0; transform: translateY(16px); }}
                    to {{ opacity:1; transform: translateY(0); }}
                }}
                </style>

                <div style="position:absolute; top:0; left:0; right:0; bottom:0;
                    background: radial-gradient(ellipse at top left, rgba({r_hex},{g_hex},{b_hex},0.06) 0%, transparent 60%);
                    pointer-events:none;">
                </div>

                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
                    <div>
                        <div style="font-size:11px; color:{tier_color}; font-family:Rajdhani,sans-serif;
                            font-weight:700; letter-spacing:2px; margin-bottom:2px;">
                            {rank_badge} {tier_label}
                        </div>
                        <div style="font-family:Rajdhani,sans-serif; font-size:22px; font-weight:700;
                            color:#EAEAEA; line-height:1.1;
                            text-shadow: 0 0 12px rgba({r_hex},{g_hex},{b_hex},0.5);">
                            {r['name']}
                        </div>
                        <div style="font-size:11px; color:#888899; margin-top:2px;">
                            🇮🇳 Top {top_pct}% globally
                        </div>
                    </div>
                    <div style="opacity:0.9;">{radar_svg}</div>
                </div>

                <div style="background:rgba({r_hex},{g_hex},{b_hex},0.08); border-radius:6px; padding:8px 10px; margin-bottom:12px; text-align:center;">
                    <div style="font-family:Rajdhani,sans-serif; font-size:32px; font-weight:700; color:{tier_color};
                        line-height:1; text-shadow: 0 0 16px rgba({r_hex},{g_hex},{b_hex},0.6);">
                        {float(r['avg_acs']):.0f}
                    </div>
                    <div style="font-size:10px; color:#888899; letter-spacing:1.5px; text-transform:uppercase; margin-top:2px;">
                        Avg ACS · {int(r['matches_played'])} matches
                    </div>
                </div>

                {stat_bars}

            </div>
            """

        cards_html += "</div>"
        components.html(cards_html, height=420, scrolling=False)
except Exception as e:
    st.info(f"India Spotlight temporarily unavailable.")

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

    st.markdown(sb_html, unsafe_allow_html=True)
else:
    st.warning("No players match current filters. Try selecting 'All' tiers or reducing the minimum matches.")

st.markdown('</div>', unsafe_allow_html=True)
render_glossary()
