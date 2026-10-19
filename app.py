"""
ClipForge - AI Vertical Shorts & Reaction Studio
Main Application Router
"""

import streamlit as st
from database import init_db, get_social_accounts
from trends import get_quota_summary
from ui.theme import inject_theme, render_brand
from ui.common import STEPS, goto
from ui.step_discover import render_step_discover
from ui.step_source import render_step_source
from ui.step_create import render_step_create
from ui.step_publish import render_step_publish
from ui.step_agent import render_step_agent
from ui.settings import render_sidebar

# Initialize SQLite database tables
init_db()

# Streamlit Page Configuration
st.set_page_config(
    page_title="ClipForge — AI Shorts & Autonomous Agent Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Inject modern dark theme & typography
inject_theme()

# Session State Defaults
if "step" not in st.session_state:
    st.session_state["step"] = 0
if "selected_video" not in st.session_state:
    st.session_state["selected_video"] = None
if "downloaded_video" not in st.session_state:
    st.session_state["downloaded_video"] = None
if "highlight_candidates" not in st.session_state:
    st.session_state["highlight_candidates"] = []
if "selected_candidate" not in st.session_state:
    st.session_state["selected_candidate"] = None
if "rendered_clip" not in st.session_state:
    st.session_state["rendered_clip"] = None

# Brand Bar & Status Pills
socials = get_social_accounts()
quota = get_quota_summary()
render_brand(socials, quota)

# ------------------------------------------------------------------------------
# STEPPER NAVIGATION (5 Guided Steps)
# ------------------------------------------------------------------------------
cur_step = st.session_state.get("step", 0)

step_cols = st.columns(len(STEPS))
step_labels = [
    "1. Discover",
    "2. Source & Clear",
    "3. Create & Reaction",
    "4. Review & Publish",
    "5. Auto-Agent & Growth",
]

for i, label in enumerate(step_labels):
    is_active = (i == cur_step)
    btn_type = "primary" if is_active else "secondary"
    if step_cols[i].button(label, key=f"nav_step_{i}", type=btn_type, width="stretch"):
        goto(i)


# Progress indicator bar
pct_complete = (cur_step + 1) / len(STEPS) * 100
st.markdown(
    f'<div class="cf-progress"><div style="width: {pct_complete:.0f}%;"></div></div>',
    unsafe_allow_html=True,
)
st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# RENDER ACTIVE STEP
# ------------------------------------------------------------------------------
if cur_step == 0:
    render_step_discover()
elif cur_step == 1:
    render_step_source()
elif cur_step == 2:
    render_step_create()
elif cur_step == 3:
    render_step_publish()
elif cur_step == 4:
    render_step_agent()
else:
    render_step_discover()

# Render Settings in Sidebar
render_sidebar()
