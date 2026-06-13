"""
MetaMind — Esports Analytics Platform
Entry point: dark theme injection, sidebar navigation, scheduler start.
"""

import streamlit as st
import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="MetaMind — Esports Analytics",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark theme CSS injection ────────────────────────────────────────
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* Global dark styling */
        html, body, [class*="st-"] {
            font-family: 'Inter', sans-serif;
        }

        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #161b22;
        }
        [data-testid="stSidebar"] .stMarkdown h2 {
            color: #58a6ff;
            font-size: 1.2em;
        }

        /* KPI card styling */
        .kpi-card {
            background: linear-gradient(135deg, #161b22 0%, #1c2333 100%);
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: #58a6ff;
        }
        .kpi-label {
            color: #8b949e;
            font-size: 0.82em;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }
        .kpi-value {
            color: #f0f6fc;
            font-size: 1.8em;
            font-weight: 700;
            line-height: 1.2;
        }

        /* Badge styles */
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.82em;
            font-weight: 600;
            margin: 4px 2px;
        }
        .badge-peaking {
            background: rgba(63, 185, 80, 0.15);
            color: #3fb950;
            border: 1px solid rgba(63, 185, 80, 0.3);
        }
        .badge-declining {
            background: rgba(248, 81, 73, 0.15);
            color: #f85149;
            border: 1px solid rgba(248, 81, 73, 0.3);
        }
        .badge-consistent {
            background: rgba(88, 166, 255, 0.15);
            color: #58a6ff;
            border: 1px solid rgba(88, 166, 255, 0.3);
        }
        .badge-region {
            background: rgba(210, 153, 34, 0.15);
            color: #d29922;
            border: 1px solid rgba(210, 153, 34, 0.3);
        }

        /* Agent pills */
        .agent-pill {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 500;
            background: rgba(88, 166, 255, 0.1);
            color: #58a6ff;
            border: 1px solid rgba(88, 166, 255, 0.2);
            margin: 2px;
        }

        /* Percentile bar */
        .pct-bar-container {
            background: #21262d;
            border-radius: 8px;
            height: 8px;
            overflow: hidden;
        }
        .pct-bar-fill {
            height: 100%;
            border-radius: 8px;
            transition: width 0.6s ease;
        }

        /* Insight card */
        .insight-card {
            background: linear-gradient(135deg, #161b22 0%, #1a2233 100%);
            border: 1px solid #30363d;
            border-left: 4px solid #58a6ff;
            border-radius: 8px;
            padding: 16px 20px;
            margin: 8px 0;
            transition: border-color 0.2s ease;
        }
        .insight-card:hover {
            border-left-color: #f0883e;
        }
        .insight-title {
            color: #f0f6fc;
            font-size: 0.95em;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .insight-body {
            color: #8b949e;
            font-size: 0.85em;
            line-height: 1.5;
        }

        /* Data table tweaks */
        [data-testid="stDataFrame"] {
            border-radius: 8px;
            overflow: hidden;
        }

        /* Hide default Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Smooth transitions */
        * { transition: background-color 0.2s ease; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar navigation ─────────────────────────────────────────────
st.sidebar.markdown("# 🧠 MetaMind")
st.sidebar.markdown("*Esports Analytics Platform*")
st.sidebar.markdown("---")

# Refresh button
if st.sidebar.button("🔄 Refresh Data Cache"):
    st.cache_data.clear()
    st.toast("Cache cleared! Data will reload on next query.", icon="✅")

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style="color:#8b949e; font-size:0.78em; line-height:1.6;">
        <strong>Pages</strong><br>
        📊 Player Intelligence<br>
        🗺️ Team Map Strategy<br>
        🏆 Tournament Leaderboard<br>
        <br>
        <strong>Data</strong><br>
        VCT 2021–2026 · CT2024<br>
        VLR.gg South Asia events<br>
        <br>
        Built by Narayan Agarwal
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Start scheduler ────────────────────────────────────────────────
try:
    from data.scheduler import start_scheduler
    start_scheduler()
except Exception:
    pass  # Scheduler is optional — don't block the app

# ── Main landing page ───────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align:center; padding:40px 0;">
        <h1 style="font-size:3em; margin-bottom:0; color:#f0f6fc;">
            🧠 MetaMind
        </h1>
        <p style="color:#8b949e; font-size:1.2em; max-width:600px; margin:12px auto 0;">
            Esports Analytics Platform — transforming 5 years of Valorant
            pro match data into interactive performance insights
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Feature cards
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="kpi-card">
            <div class="kpi-value" style="font-size:1.5em;">📊</div>
            <div class="kpi-label" style="margin-top:12px; font-size:0.95em; color:#f0f6fc;">
                Player Intelligence
            </div>
            <div style="color:#8b949e; font-size:0.82em; margin-top:8px;">
                Form curves, percentile rankings, consistency scores,
                and head-to-head comparisons
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div class="kpi-card">
            <div class="kpi-value" style="font-size:1.5em;">🗺️</div>
            <div class="kpi-label" style="margin-top:12px; font-size:0.95em; color:#f0f6fc;">
                Team Map Strategy
            </div>
            <div style="color:#8b949e; font-size:0.82em; margin-top:8px;">
                Map DNA radar, attack vs defense splits,
                economy analysis, and strategic identity
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div class="kpi-card">
            <div class="kpi-value" style="font-size:1.5em;">🏆</div>
            <div class="kpi-label" style="margin-top:12px; font-size:0.95em; color:#f0f6fc;">
                Tournament Leaderboard
            </div>
            <div style="color:#8b949e; font-size:0.82em; margin-top:8px;">
                Regional comparisons, Indian spotlight,
                global rankings with analyst commentary
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div style="text-align:center; margin-top:40px; color:#8b949e; font-size:0.85em;">
        Select a page from the sidebar to start exploring →
    </div>
    """,
    unsafe_allow_html=True,
)
