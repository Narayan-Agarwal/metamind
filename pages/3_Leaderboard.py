import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from db.connection import get_engine
from db.queries import get_leaderboard, get_indian_spotlight, get_acs_distribution
from utils.styles import GLOBAL_CSS, AXIS_STYLE, render_nav, render_glossary

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

# ── SECTION 1: INDIA SPOTLIGHT (fixed, not affected by filters) ──
try:
    indian = get_indian_spotlight(engine)
    if not indian.empty:
        st.markdown('<div class="section-title">🇮🇳 INDIA SPOTLIGHT</div>', unsafe_allow_html=True)
        st.caption("Top Indian VCT players tracked in the dataset.")
        ind_cols = st.columns(len(indian))
        for i, (_, r) in enumerate(indian.iterrows()):
            tier_label, tier_color = consistency_tier(r['consistency'])
            with ind_cols[i]:
                st.markdown(f'<div style="border-left:3px solid {tier_color}; padding-left:8px; margin-bottom:4px;"><b style="color:{tier_color}; font-family:Rajdhani,sans-serif; font-size:16px;">{r["name"]}</b></div>', unsafe_allow_html=True)
                st.metric("Avg ACS", f"{float(r['avg_acs']):.1f}")
                st.metric("Consistency", f"{float(r['consistency']):.1f}")
                st.metric("Global Rank", f"Top {max(1, 100 - int(float(r['global_percentile'])))}%")
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
    podium_medals = ['🥇', '🥈', '🥉']
    podium_colors = ['#FFD700', '#C0C0C0', '#CD7F32']
    podium_count = min(3, total)
    pod_cols = st.columns(podium_count)
    for i in range(podium_count):
        row = lb_df.iloc[i]
        tier_label, tier_color = consistency_tier(row['consistency'])
        with pod_cols[i]:
            st.metric(podium_medals[i] + " #" + str(i+1), row['name'])
            st.metric("Avg ACS", f"{float(row['avg_acs']):.1f}")
            st.metric("Consistency", f"{float(row['consistency']):.1f} · {tier_label}")
            st.metric("Matches", int(row['matches_played']))

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
    chunk['rank'] = chunk['rank_display'].apply(lambda r: '🥇' if r==1 else '🥈' if r==2 else '🥉' if r==3 else f"#{int(r)}")
    chunk['tier'] = chunk['consistency'].apply(lambda c: '🔵 Elite' if float(c)>=70 else '🟡 Solid' if float(c)>=40 else '🔴 Volatile')
    chunk['region'] = chunk['region'].fillna('—').replace('', '—')
    acs_max = float(lb_df['avg_acs'].max())
    acs_min = float(lb_df['avg_acs'].min())
    display_df = chunk[['rank','name','region','avg_acs','kast_pct','consistency','tier','matches_played']].copy()
    display_df.columns = ['Rank','Player','Region','ACS','KAST %','Consistency','Tier','Matches']
    st.dataframe(
        display_df, use_container_width=True, hide_index=True,
        column_config={
            'Rank': st.column_config.TextColumn(width='small'),
            'Player': st.column_config.TextColumn(width='medium'),
            'Region': st.column_config.TextColumn(width='small'),
            'ACS': st.column_config.ProgressColumn('ACS', min_value=acs_min, max_value=acs_max, format='%.1f', width='medium'),
            'KAST %': st.column_config.NumberColumn(format='%.1f', width='small'),
            'Consistency': st.column_config.NumberColumn(format='%.1f', width='small'),
            'Tier': st.column_config.TextColumn(width='small'),
            'Matches': st.column_config.NumberColumn(format='%d', width='small'),
        }
    )
else:
    st.warning(f"No players match current filters. Try selecting 'All' tiers or reducing the minimum matches.")

st.markdown('</div>', unsafe_allow_html=True)
render_glossary()
