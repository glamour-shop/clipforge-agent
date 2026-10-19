"""
ClipForge - Modern Creator Studio
Find trending YouTube videos (Football, Knowledge, Streamers, Actors, Shows),
verify rights clearance, cut 9:16 vertical Shorts with captions, and publish directly to socials.
"""

import os
import re
import json
import subprocess
import streamlit as st
import pandas as pd
from datetime import datetime

from database import (
    get_daily_quota_used,
    get_quota_breakdown_today,
    get_setting,
    set_setting,
    get_allowlist,
    add_to_allowlist,
    remove_from_allowlist,
    get_cached_videos,
    get_user_profile,
    save_user_profile,
    get_social_accounts,
    save_social_account,
    disconnect_social_account,
    save_clip,
    get_clips,
    update_clip_status,
    delete_clip,
    update_clip
)
from trends import (
    fetch_trending_videos,
    search_niche_videos,
    fetch_video_by_url_or_id,
    get_quota_summary,
    get_api_key,
    duration_to_seconds,
    SUPPORTED_REGIONS,
    STANDARD_CATEGORIES
)
from rights import (
    check_rights_clearance,
    generate_attribution_credits,
    quick_allowlist_channel,
    download_cleared_video,
    inspect_independent_video_url,
    resolve_video_from_url,
    approve_and_clear_video,
    save_local_uploaded_video
)
from highlights import extract_highlight_candidates
from editor import (
    render_short_video,
    transcribe_clip,
    align_edited_transcript_to_words,
    sanitize_word_timestamps
)
from publish import create_export_pack, create_batch_export_pack, publish_short_to_platform


def make_file_downloader(file_path):
    """
    Returns a callable that reads file_path on demand for st.download_button deferred download.
    Avoids reading large files into memory during script renders and prevents WebSocket timeouts.
    """
    def _read_file_bytes():
        with open(file_path, "rb") as f:
            return f.read()
    return _read_file_bytes


def open_folder_in_explorer(file_path):
    """Opens Windows Explorer and highlights the specified file or folder."""
    try:
        abs_p = os.path.abspath(file_path)
        if os.path.isfile(abs_p):
            subprocess.Popen(f'explorer /select,"{abs_p}"')
        elif os.path.isdir(abs_p):
            subprocess.Popen(f'explorer "{abs_p}"')
        return True
    except Exception:
        return False


# Page Configuration
st.set_page_config(
    page_title="ClipForge Studio 🎬",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom High-End Cyber/Obsidian Studio Styling
st.markdown("""
<style>
    /* Global Background & Font Polish */
    .stApp {
        background: radial-gradient(circle at 15% 10%, #171923 0%, #0d0f15 90%);
        color: #E2E8F0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Studio Header */
    .studio-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(22, 26, 38, 0.75);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 16px 24px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
    }
    .brand-title {
        font-size: 2.1rem;
        font-weight: 900;
        background: linear-gradient(135deg, #FF3366 0%, #FF9933 50%, #FFCC00 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
        margin: 0;
        line-height: 1.1;
    }
    .brand-subtitle {
        font-size: 0.88rem;
        color: #94A3B8;
        margin-top: 3px;
    }
    
    /* Social Status Pills in Header */
    .social-pill-on {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34D399;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 20px;
    }
    .social-pill-off {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(100, 116, 139, 0.12);
        border: 1px solid rgba(100, 116, 139, 0.3);
        color: #94A3B8;
        font-size: 0.78rem;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 20px;
    }
    
    /* Topic Chips */
    .topic-chip {
        display: inline-block;
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #CBD5E1;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 8px;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .topic-chip:hover {
        background: linear-gradient(135deg, rgba(255, 51, 102, 0.2), rgba(255, 153, 51, 0.2));
        border-color: #FF4B4B;
        color: #FFFFFF;
    }
    
    /* Video Cards */
    .card-cleared {
        background: linear-gradient(180deg, rgba(26, 32, 44, 0.9) 0%, rgba(17, 24, 39, 0.95) 100%);
        border: 1px solid rgba(52, 211, 153, 0.35);
        border-radius: 12px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25), 0 0 15px rgba(52, 211, 153, 0.08);
        padding: 16px;
        margin-bottom: 16px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .card-cleared:hover {
        transform: translateY(-2px);
        border-color: rgba(52, 211, 153, 0.7);
    }
    .card-locked {
        background: linear-gradient(180deg, rgba(20, 24, 33, 0.8) 0%, rgba(13, 17, 23, 0.85) 100%);
        border: 1px solid rgba(248, 113, 113, 0.25);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        opacity: 0.88;
    }
    
    /* Badges */
    .badge-cleared {
        background: linear-gradient(90deg, #059669 0%, #10B981 100%);
        color: #FFFFFF;
        font-size: 0.75rem;
        font-weight: 800;
        padding: 3px 10px;
        border-radius: 14px;
        letter-spacing: 0.5px;
        display: inline-block;
    }
    .badge-locked {
        background: linear-gradient(90deg, #DC2626 0%, #EF4444 100%);
        color: #FFFFFF;
        font-size: 0.75rem;
        font-weight: 800;
        padding: 3px 10px;
        border-radius: 14px;
        letter-spacing: 0.5px;
        display: inline-block;
    }
    .badge-cc {
        background: rgba(14, 165, 233, 0.15);
        border: 1px solid rgba(14, 165, 233, 0.4);
        color: #38BDF8;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 10px;
        display: inline-block;
    }
    .badge-yt {
        background: rgba(148, 163, 184, 0.15);
        border: 1px solid rgba(148, 163, 184, 0.3);
        color: #94A3B8;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 10px;
        display: inline-block;
    }
    
    /* Momentum Score Meter */
    .score-badge {
        background: linear-gradient(135deg, #FF3366 0%, #FF8533 100%);
        color: white;
        font-weight: 800;
        font-size: 0.95rem;
        padding: 5px 12px;
        border-radius: 18px;
        display: inline-block;
        box-shadow: 0 4px 12px rgba(255, 51, 102, 0.3);
    /* Main Segmented Control Navigation */
    div[data-testid="stSegmentedControl"] {
        background: rgba(17, 24, 39, 0.95) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 14px !important;
        padding: 6px !important;
        margin-bottom: 24px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35) !important;
        width: 100% !important;
    }
    div[data-testid="stSegmentedControl"] button {
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 0.92rem !important;
        padding: 10px 18px !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div[data-testid="stSegmentedControl"] button[aria-selected="true"] {
        background: linear-gradient(135deg, #FF4B4B 0%, #FF8A00 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 0 20px rgba(255, 75, 75, 0.45) !important;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State
if "discovered_videos" not in st.session_state:
    st.session_state["discovered_videos"] = get_cached_videos(limit=25)
    if not st.session_state["discovered_videos"]:
        # Prepopulate with top trending curated samples so the app is instantly rich
        from trends import get_sample_trending_videos
        st.session_state["discovered_videos"] = get_sample_trending_videos(keyword="", min_views=0)

if "selected_video" not in st.session_state:
    st.session_state["selected_video"] = None
if "downloaded_video" not in st.session_state:
    st.session_state["downloaded_video"] = None
if "highlight_candidates" not in st.session_state:
    st.session_state["highlight_candidates"] = []
if "selected_candidate" not in st.session_state:
    st.session_state["selected_candidate"] = None
if "current_search_query" not in st.session_state or st.session_state.get("current_search_query") == "football":
    st.session_state["current_search_query"] = ""
if "status_toast" not in st.session_state:
    st.session_state["status_toast"] = None


# Load User Profile & Socials
user_profile = get_user_profile()
socials = get_social_accounts()
quota = get_quota_summary()


# ==============================================================================
# TOP STUDIO HEADER & SOCIAL CONNECT STATUS
# ==============================================================================
h_col1, h_col2 = st.columns([2.8, 1.2])

with h_col1:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 14px;">
        <span style="font-size: 2.4rem;">🎬</span>
        <div>
            <div class="brand-title">ClipForge Studio</div>
            <div class="brand-subtitle">AI-Powered YouTube Shorts & Reels Automation Pipeline</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with h_col2:
    # Social indicators
    yt_badge = '<span class="social-pill-on">🔴 YT Connected</span>' if socials["youtube"]["is_connected"] else '<span class="social-pill-off">🔴 YouTube</span>'
    tt_badge = '<span class="social-pill-on">⚫ TT Connected</span>' if socials["tiktok"]["is_connected"] else '<span class="social-pill-off">⚫ TikTok</span>'
    ig_badge = '<span class="social-pill-on">🟣 IG Connected</span>' if socials["instagram"]["is_connected"] else '<span class="social-pill-off">🟣 Instagram</span>'
    
    st.markdown(f"""
    <div style="display: flex; justify-content: flex-end; align-items: center; gap: 8px; flex-wrap: wrap;">
        {yt_badge} {tt_badge} {ig_badge}
        <span class="social-pill-on" style="background: rgba(255, 75, 75, 0.15); border-color: rgba(255, 75, 75, 0.4); color: #FF6B6B;">
            ⚡ {quota['remaining']:,} Quota Left
        </span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)


# ==============================================================================
# MAIN NAVIGATION TABS (Programmatic & Interactive)
# ==============================================================================
NAV_TABS = [
    "🔥 1. Trend Finder & Search",
    "🛡️ 2. Rights Clearance & Download",
    "✂️ 3. Highlight Detection",
    "🎬 4. Auto-Editor 9:16",
    "👁️ 5. Review & Approve",
    "🚀 6. Publish & Socials",
    "👤 7. Creator Account & Keys"
]

# Handle programmatic tab switching
if "target_tab" in st.session_state:
    st.session_state["main_nav"] = st.session_state.pop("target_tab")
elif "main_nav" not in st.session_state or st.session_state["main_nav"] not in NAV_TABS:
    st.session_state["main_nav"] = NAV_TABS[0]

def switch_to_tab(tab_name_or_index):
    """Switch active tab programmatically without requiring the user to scroll up."""
    if isinstance(tab_name_or_index, int):
        target = NAV_TABS[tab_name_or_index]
    else:
        target = tab_name_or_index
    st.session_state["target_tab"] = target
    st.rerun()


def hard_refresh_phase(phase_index: int):
    """
    Clears all active edits, in-progress tasks, and intermediate state on the current phase only,
    starting from a clean slate on that same page. Does NOT switch tabs.
    """
    if phase_index == 0:  # Phase 1: Trend Finder & Search
        st.session_state["discovered_videos"] = []
        st.session_state["current_search_query"] = ""
        st.session_state["selected_video"] = None
        for k in list(st.session_state.keys()):
            if k.startswith("feed_") or k in ["niche_query", "direct_url", "creator_filter"]:
                st.session_state.pop(k, None)
        st.toast("🔄 Phase 1 refreshed: All searches and discovered video tasks cleared to a clean slate.")

    elif phase_index == 1:  # Phase 2: Rights Clearance & Download
        st.session_state["downloaded_video"] = None
        st.session_state["download_result"] = None
        st.session_state["selected_video"] = None
        for k in list(st.session_state.keys()):
            if k.startswith("tab2_"):
                st.session_state.pop(k, None)
        st.toast("🔄 Phase 2 refreshed: Video selection and download tasks cleared to a clean slate.")

    elif phase_index == 2:  # Phase 3: Highlight Detection
        st.session_state["highlight_candidates"] = []
        st.session_state["selected_candidate"] = None
        st.session_state.pop("t3_independent_preview", None)
        st.session_state.pop("t3_independent_preview_url", None)
        for k in list(st.session_state.keys()):
            if k.startswith("t3_") or k.startswith("cand_") or k in ["direct_tab3_link", "direct_tab3_independent_link"]:
                st.session_state.pop(k, None)
        st.toast("🔄 Phase 3 refreshed: All highlight candidates and link analysis tasks cleared to a clean slate.")

    elif phase_index == 3:  # Phase 4: Auto-Editor 9:16
        st.session_state["rendered_clip"] = None
        for c in st.session_state.get("highlight_candidates", []):
            c.pop("custom_transcript", None)
            c.pop("words", None)
        if st.session_state.get("selected_candidate"):
            st.session_state["selected_candidate"].pop("custom_transcript", None)
            st.session_state["selected_candidate"].pop("words", None)
        for k in list(st.session_state.keys()):
            if k.startswith("t4_") or k.startswith("tab4_") or k in ["batch_layout_choice", "batch_sub_choice", "batch_speed_choice"]:
                st.session_state.pop(k, None)
        st.toast("🔄 Phase 4 refreshed: Auto-editor rendering configurations cleared to a clean slate.")

    elif phase_index == 4:  # Phase 5: Review & Approve
        st.session_state["active_export_pack"] = None
        for k in list(st.session_state.keys()):
            if k.startswith("t5_") or k.startswith("edit_text_") or k.startswith("review_"):
                st.session_state.pop(k, None)
        st.toast("🔄 Phase 5 refreshed: Review studio text edits and export tasks cleared to a clean slate.")

    elif phase_index == 5:  # Phase 6: Publish & Socials
        for k in list(st.session_state.keys()):
            if k.startswith("t6_") or k.startswith("pub_") or k.startswith("sim_"):
                st.session_state.pop(k, None)
        st.toast("🔄 Phase 6 refreshed: Publishing queues and post drafts cleared to a clean slate.")

    elif phase_index == 6:  # Phase 7: Creator Account & Keys
        for k in list(st.session_state.keys()):
            if k.startswith("t7_") or k in ["p_name", "p_email", "p_bio", "yt_in_name", "yt_in_token", "tt_in_handle", "tt_in_token", "ig_in_handle", "ig_in_token"]:
                st.session_state.pop(k, None)
        st.toast("🔄 Phase 7 refreshed: Unsaved account forms cleared to a clean slate.")

    st.rerun()


def render_phase_header(phase_index: int, title: str, subtitle: str):
    """
    Renders a unified phase header with separate, dedicated action buttons:
    1. '⬅️ Back to Phase X': Navigates cleanly to the previous phase without affecting current work.
    2. '🔄 Hard Refresh': Wipes all tasks and edits on THIS page only, starting fresh from a clean slate.
    """
    with st.container():
        if phase_index > 0:
            h_col1, h_back_col, h_ref_col = st.columns([3.1, 1.0, 1.0])
        else:
            h_col1, h_ref_col = st.columns([3.8, 1.1])
            h_back_col = None

        with h_col1:
            st.markdown(f"### {title}")
            st.caption(subtitle)

        if h_back_col is not None:
            with h_back_col:
                st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                prev_phase_num = phase_index
                if st.button(
                    f"⬅️ Back to Phase {prev_phase_num}",
                    key=f"back_phase_{phase_index}",
                    help=f"Navigate back to Phase {prev_phase_num} ({NAV_TABS[phase_index - 1]}). Work on other pages is preserved.",
                    width="stretch"
                ):
                    switch_to_tab(NAV_TABS[phase_index - 1])

        with h_ref_col:
            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
            if st.button(
                "🔄 Hard Refresh",
                key=f"hard_refresh_phase_{phase_index}",
                help=f"Remove all tasks, active edits, and inputs on Phase {phase_index + 1} only, starting from a clean slate.",
                width="stretch"
            ):
                hard_refresh_phase(phase_index)
        st.divider()


current_tab = st.segmented_control(
    "Navigation Tabs",
    NAV_TABS,
    key="main_nav",
    label_visibility="collapsed"
)
if not current_tab:
    current_tab = st.session_state.get("main_nav", NAV_TABS[0])


# ==============================================================================
# TAB 1: TREND FINDER & SEARCH
# ==============================================================================
if current_tab == NAV_TABS[0]:
    render_phase_header(
        0,
        "🔥 Phase 1: Trend Finder & YouTube Search",
        "Discover viral videos, analyze real-time engagement momentum, and filter for Creative Commons or community clipping."
    )
    # Topic Preset Chips Bar
    st.markdown("##### ⚡ Quick Topic Presets")
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    
    selected_preset = None
    if c1.button("⚽ Football", width="stretch"):
        selected_preset = "football"
    if c2.button("🧠 Knowledge", width="stretch"):
        selected_preset = "knowledge"
    if c3.button("🎮 Streamers", width="stretch"):
        selected_preset = "streamer"
    if c4.button("🎭 Actors", width="stretch"):
        selected_preset = "actor"
    if c5.button("📺 Shows", width="stretch"):
        selected_preset = "show"
    if c6.button("🚀 Tech & AI", width="stretch"):
        selected_preset = "ai"
    if c7.button("🔥 Trending", width="stretch"):
        selected_preset = ""

    if selected_preset is not None:
        st.session_state["current_search_query"] = selected_preset
        # Auto-fetch for the chosen preset
        with st.spinner(f"Extracting high-engagement {selected_preset or 'trending'} clips..."):
            if selected_preset:
                vids, err = search_niche_videos(selected_preset, region="ALL", cc_only=False, order="viewCount", min_views=500000)
            else:
                vids, err = fetch_trending_videos(region="ALL", min_views=500000)
            if vids:
                st.session_state["discovered_videos"] = vids
                st.rerun()

    # Search Box & Advanced Controls
    with st.container(border=True):
        mode_col, query_col, cc_col = st.columns([1.2, 2.5, 1.3])
        
        with mode_col:
            search_mode = st.radio(
                "Mode",
                ["🔎 Topic Search", "🔥 Most Popular", "📥 Direct URL / ID"],
                horizontal=False,
                label_visibility="collapsed"
            )
            
        with query_col:
            if "Direct URL" in search_mode:
                direct_url = st.text_input(
                    "YouTube Video Link",
                    placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
                    label_visibility="collapsed"
                )
            elif "Topic Search" in search_mode:
                niche_query = st.text_input(
                    "Search Topics & Keywords",
                    value=st.session_state.get("current_search_query", ""),
                    placeholder="Search topics, creators, streamers, shows, science...",
                    label_visibility="collapsed"
                )
            else:
                st.info("🔥 Top trending videos from YouTube in selected region and category.")
                niche_query = ""
                
        with cc_col:
            cc_only_filter = st.checkbox(
                "🛡️ CC-BY Only",
                value=False,
                help="Unchecked (Recommended): Discovers all viral videos with millions of views (podcasts, creators, gaming, sports). Checked: Restricts strictly to Creative Commons license."
            )
            min_views_preset = st.selectbox(
                "Min Views",
                [
                    "🌐 Any Views (0+ / All Relevant Matches)",
                    "⚡ 500,000+ Views (High Momentum)",
                    "🔥 1,000,000+ Views (Viral Millions)",
                    "🚀 5,000,000+ Views (Mega Viral)",
                    "👑 10,000,000+ Views (Blockbusters)",
                    "📈 100,000+ Views",
                    "⚙️ Custom Threshold"
                ],
                index=0,
                label_visibility="collapsed",
                help="Default is Any Views (0+) to show all relevant videos matching your search term. Increase to filter for high view counts."
            )
            min_views_preset_map = {
                "🌐 Any Views (0+ / All Relevant Matches)": 0,
                "⚡ 500,000+ Views (High Momentum)": 500000,
                "🔥 1,000,000+ Views (Viral Millions)": 1000000,
                "🚀 5,000,000+ Views (Mega Viral)": 5000000,
                "👑 10,000,000+ Views (Blockbusters)": 10000000,
                "📈 100,000+ Views": 100000
            }
            if min_views_preset == "⚙️ Custom Threshold":
                min_views_val = st.number_input("Custom Min Views", min_value=0, value=1000000, step=100000, label_visibility="collapsed")
            else:
                min_views_val = min_views_preset_map[min_views_preset]

        # Second row: Research & Discovery Options
        st.markdown("###### 🔬 Video Research Tools & Viral Filters")
        r_col1, r_col2, r_col3, r_col4 = st.columns([1.2, 1.3, 1.2, 1.3])
        with r_col1:
            order_choice = st.selectbox(
                "Search Ranking",
                [
                    "🎯 Relevance (Best Match / Official YouTube Rank)",
                    "🔥 View Count (Most Viewed / Millions of Views)",
                    "⚡ Date (Newly Uploaded / Fresh)",
                    "⭐ Top Rated"
                ],
                index=0,
                help="Default is Relevance (Best Match) to match official YouTube search results."
            )
            order_map = {
                "🎯 Relevance (Best Match / Official YouTube Rank)": "relevance",
                "🔥 View Count (Most Viewed / Millions of Views)": "viewCount",
                "⚡ Date (Newly Uploaded / Fresh)": "date",
                "⭐ Top Rated": "rating"
            }
        with r_col2:
            duration_choice = st.selectbox(
                "Duration Filter",
                [
                    "🌐 Any Duration (All Videos & Shorts)",
                    "🎬 Long-Form (≥ 3 min, Exclude Shorts)",
                    "⚡ YouTube Shorts & Clips (< 4 min / < 60s)",
                    "⏱️ Deep Dives (> 20 min)"
                ],
                index=0,
                help="Choose duration filter: Any Duration includes all matching videos; Long-Form excludes shorts under 3 minutes."
            )
            dur_map = {
                "🌐 Any Duration (All Videos & Shorts)": "any",
                "🎬 Long-Form (≥ 3 min, Exclude Shorts)": "medium_or_long",
                "⚡ YouTube Shorts & Clips (< 4 min / < 60s)": "short",
                "⏱️ Deep Dives (> 20 min)": "long"
            }
        with r_col3:
            timeframe_choice = st.selectbox(
                "Upload Timeframe",
                ["All Time", "Past 24 Hours", "This Week", "This Month", "This Year"],
                help="Filter by recent uploads to find hot fresh moments."
            )
            timeframe_map = {
                "All Time": "all_time",
                "Past 24 Hours": "today",
                "This Week": "this_week",
                "This Month": "this_month",
                "This Year": "this_year"
            }
        with r_col4:
            creator_filter = st.text_input(
                "Creator / Channel (Optional)",
                placeholder="e.g. Kai Cenat, Sky Sports, Lex Fridman",
                help="Search specifically within a creator or organization."
            )

        # Third row: Region, Category, Results count, and Discover Button
        f_reg, f_cat, f_num, f_action = st.columns([1.1, 1.1, 0.8, 1.2])
        with f_reg:
            region_val = st.selectbox(
                "Region",
                list(SUPPORTED_REGIONS.keys()),
                index=0,
                format_func=lambda x: f"🌐 {SUPPORTED_REGIONS[x]}" if x == "ALL" else f"{x} - {SUPPORTED_REGIONS[x]}",
                help="Choose 'ALL' to search globally across all countries worldwide."
            )
        with f_cat:
            cat_val = st.selectbox("Category", list(STANDARD_CATEGORIES.keys()), format_func=lambda x: STANDARD_CATEGORIES[x])
        with f_num:
            max_results_val = st.selectbox("Max Results", [25, 50], index=1)
        with f_action:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            find_btn = st.button("🚀 Discover Videos & Shorts", type="primary", width="stretch")

    # Handle Search / Import Action
    if find_btn:
        with st.spinner("Finding and analyzing high-performing videos & shorts..."):
            if "Direct URL" in search_mode and direct_url.strip():
                imported_video, err = fetch_video_by_url_or_id(direct_url.strip())
                if imported_video:
                    st.session_state["discovered_videos"] = [imported_video] + st.session_state["discovered_videos"]
                    st.session_state["selected_video"] = imported_video
                    st.success(f"Successfully imported: '{imported_video['title']}'! Ready for clipping.")
                else:
                    st.error(err or "Failed to import video.")
            elif "Topic Search" in search_mode and niche_query.strip():
                st.session_state["current_search_query"] = niche_query.strip()
                vids, err = search_niche_videos(
                    niche_query.strip(),
                    region=region_val,
                    min_views=min_views_val,
                    max_results=max_results_val,
                    cc_only=cc_only_filter,
                    order=order_map.get(order_choice, "relevance"),
                    duration=dur_map.get(duration_choice, "any"),
                    timeframe=timeframe_map.get(timeframe_choice, "all_time"),
                    channel_name=creator_filter.strip()
                )
                if err:
                    st.info(f"ℹ️ {err}")
                if vids:
                    st.session_state["discovered_videos"] = vids
                    st.success(f"Discovered and scored {len(vids)} videos matching '{niche_query}'!")
                else:
                    st.warning("No videos matched your exact query. Try expanding the timeframe or duration filter.")
            else:
                vids, err = fetch_trending_videos(region=region_val, category_id=cat_val, min_views=min_views_val, max_results=max_results_val)
                if err:
                    st.info(f"ℹ️ {err}")
                if vids:
                    st.session_state["discovered_videos"] = vids
                    st.success(f"Retrieved {len(vids)} trending videos!")

    # Display Videos
    vids = st.session_state.get("discovered_videos", [])
    
    if vids:
        # Overview Metrics Bar
        total_found = len(vids)
        cleared_found = sum(1 for v in vids if check_rights_clearance(v)[0])
        avg_velocity = int(sum(v.get("views_per_hour", 0) for v in vids) / max(total_found, 1))
        highest_score = max((v.get("score", 0) for v in vids), default=0)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Videos Discovered", total_found)
        m2.metric("Cleared for Clipping", f"{cleared_found} / {total_found}", f"{(cleared_found/total_found)*100:.0f}% Cleared")
        m3.metric("Avg Velocity", f"{avg_velocity:,} views/hr")
        m4.metric("Top Momentum Score", f"{highest_score} / 100")

        st.divider()

        # Dedicated Results Sort & Filter Toolbar
        with st.container(border=True):
            st.markdown("##### 🎛️ Sort & Filter Discovered Results")
            tb_c1, tb_c2, tb_c3, tb_c4 = st.columns([1.6, 1.3, 1.2, 1.4])

            with tb_c1:
                feed_sort = st.selectbox(
                    "Sort Results By",
                    [
                    "🎯 Relevance / Original Search Order",
                        "👀 Views: Most Viewed (Total)",
                        "🏆 Score: Highest Momentum",
                        "⚡ Velocity: Fastest Growing (Views/Hr)",
                        "📅 Date: Newest First",
                        "📅 Date: Oldest First",
                        "👍 Likes: Highest Ratio (%)",
                        "⏱️ Duration: Shortest First",
                        "⏳ Duration: Longest First",
                        "💬 Comments: Most Discussed"
                    ],
                    index=0,
                    key="feed_sort_choice"
                )

            with tb_c2:
                feed_rights = st.selectbox(
                    "Clearance Status",
                    [
                        "All Discovered Videos",
                        "✅ Cleared Only (CC-BY & Allowlisted)",
                        "🔒 Locked Only"
                    ],
                    index=0,
                    key="feed_rights_choice"
                )

            with tb_c3:
                feed_format = st.selectbox(
                    "Video Format",
                    [
                        "All Formats",
                        "🎬 Long-Form (≥ 3 min)",
                        "⚡ Shorts & Quick Clips (< 3 min)"
                    ],
                    index=0,
                    key="feed_format_choice"
                )

            with tb_c4:
                feed_filter_kw = st.text_input(
                    "Search within results",
                    placeholder="Filter title, channel, tags...",
                    key="feed_filter_kw"
                )

        # Apply in-memory filtering
        displayed_vids = list(vids)

        # 1. Filter by keyword
        if feed_filter_kw and feed_filter_kw.strip():
            kw_clean = feed_filter_kw.strip().lower()
            displayed_vids = [
                v for v in displayed_vids
                if kw_clean in v.get("title", "").lower()
                or kw_clean in v.get("channel_title", "").lower()
                or any(kw_clean in str(t).lower() for t in v.get("tags", []))
            ]

        # 2. Filter by rights clearance
        if "Cleared Only" in feed_rights:
            displayed_vids = [v for v in displayed_vids if check_rights_clearance(v)[0]]
        elif "Locked Only" in feed_rights:
            displayed_vids = [v for v in displayed_vids if not check_rights_clearance(v)[0]]

        # 3. Filter by video format
        if "Long-Form" in feed_format:
            displayed_vids = [v for v in displayed_vids if duration_to_seconds(v.get("duration", "00:00")) >= 180]
        elif "Shorts" in feed_format:
            displayed_vids = [v for v in displayed_vids if duration_to_seconds(v.get("duration", "00:00")) < 180]

        # 4. Sort results
        if "Relevance" in feed_sort:
            pass  # Preserve YouTube native search ranking
        elif "Score" in feed_sort:
            displayed_vids.sort(key=lambda x: x.get("score", 0), reverse=True)
        elif "Velocity" in feed_sort:
            displayed_vids.sort(key=lambda x: x.get("views_per_hour", 0), reverse=True)
        elif "Views: Most" in feed_sort:
            displayed_vids.sort(key=lambda x: x.get("view_count", 0), reverse=True)
        elif "Newest First" in feed_sort:
            displayed_vids.sort(key=lambda x: str(x.get("published_at", "")), reverse=True)
        elif "Oldest First" in feed_sort:
            displayed_vids.sort(key=lambda x: str(x.get("published_at", "")), reverse=False)
        elif "Likes" in feed_sort:
            displayed_vids.sort(key=lambda x: x.get("like_ratio", 0), reverse=True)
        elif "Shortest First" in feed_sort:
            displayed_vids.sort(key=lambda x: duration_to_seconds(x.get("duration", "00:00")), reverse=False)
        elif "Longest First" in feed_sort:
            displayed_vids.sort(key=lambda x: duration_to_seconds(x.get("duration", "00:00")), reverse=True)
        elif "Comments" in feed_sort:
            displayed_vids.sort(key=lambda x: x.get("comment_count", 0), reverse=True)

        st.caption(f"Showing **{len(displayed_vids)}** of **{len(vids)}** discovered videos (Sorted by {feed_sort})")

        if not displayed_vids:
            st.info("ℹ️ No videos match your current filter selections. Try selecting 'All Discovered Videos' or clearing the search filter.")
        else:
            # Display Cards
            for v in displayed_vids:
                is_cleared, clear_reason = check_rights_clearance(v)
                card_border = "card-cleared" if is_cleared else "card-locked"
            
                with st.container(border=True):
                    c_thumb, c_details, c_stats, c_cta = st.columns([1.8, 3.2, 2.2, 1.8])
                    
                    with c_thumb:
                        if v.get("thumbnail_url"):
                            st.image(v["thumbnail_url"], width="stretch")
                        else:
                            st.write("📷 *No thumbnail*")
                        st.caption(f"⏱️ Duration: **{v.get('duration', 'N/A')}**")
                        
                    with c_details:
                        st.markdown(f"#### [{v['title']}](https://www.youtube.com/watch?v={v['video_id']})")
                        st.markdown(f"**Channel:** {v['channel_title']}")
                        
                        # Clearance & License Badges
                        if is_cleared:
                            st.markdown(f'<span class="badge-cleared">✅ CLEARED: {clear_reason}</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<span class="badge-locked">🔒 STANDARD LICENSE: {clear_reason}</span>', unsafe_allow_html=True)
                            
                        if v.get("is_cc"):
                            st.markdown('<span class="badge-cc">Creative Commons (CC-BY)</span>', unsafe_allow_html=True)
                        else:
                            st.markdown('<span class="badge-yt">Standard YouTube</span>', unsafe_allow_html=True)
                            
                    with c_stats:
                        st.markdown(f'<div class="score-badge">Score: {v.get("score", 0)} / 100</div>', unsafe_allow_html=True)
                        st.write(f"👀 **Views:** {v.get('view_count', 0):,}")
                        st.write(f"⚡ **Velocity:** {v.get('views_per_hour', 0):,.1f} /hr")
                        st.write(f"👍 **Like Ratio:** {v.get('like_ratio', 0):.2f}% ({v.get('like_count', 0):,} likes)")
                        st.write(f"💬 **Comments:** {v.get('comment_count', 0):,}")
    
                    with c_cta:
                        if is_cleared:
                            if st.button("✂️ Select & Clip", key=f"clip_{v['video_id']}", type="primary", width="stretch"):
                                # If picking a different video, clear stale clip states
                                if (st.session_state.get("selected_video") or {}).get("video_id") != v["video_id"]:
                                    st.session_state["downloaded_video"] = None
                                    st.session_state["highlight_candidates"] = []
                                    st.session_state["selected_candidate"] = None
                                    st.session_state["rendered_clip"] = None
                                st.session_state["selected_video"] = v
                                switch_to_tab(NAV_TABS[1])
                        else:
                            if st.button("✂️ Select & Clip (Fair Use)", key=f"clip_fu_{v['video_id']}", type="primary", width="stretch", help="Clip video under fair use / transformative commentary"):
                                if (st.session_state.get("selected_video") or {}).get("video_id") != v["video_id"]:
                                    st.session_state["downloaded_video"] = None
                                    st.session_state["highlight_candidates"] = []
                                    st.session_state["selected_candidate"] = None
                                    st.session_state["rendered_clip"] = None
                                st.session_state["selected_video"] = v
                                switch_to_tab(NAV_TABS[1])
                            
                            # 1-Click Allowlist Button to immediately add channel to allowlist
                            if st.button("🔓 Add to Allowlist", key=f"unlock_{v['video_id']}", help="Add this creator to your Permission Allowlist.", width="stretch"):
                                quick_allowlist_channel(v["channel_id"], v["channel_title"], "Streamer / Show fair-use commentary clipping")
                                st.success(f"Added '{v['channel_title']}' to allowlist! Refreshing...")
                                st.rerun()
    else:
        st.info("No videos in current filter. Try clicking one of the preset chips above (e.g. ⚽ Football, 🧠 Knowledge, 🎮 Streamers)!")


# ==============================================================================
# TAB 2: RIGHTS CLEARANCE & DOWNLOAD (Phase 2 Functional)
# ==============================================================================
elif current_tab == NAV_TABS[1]:
    render_phase_header(
        1,
        "🛡️ Phase 2: Rights Clearance & Safe yt-dlp Download",
        "Evaluate copyright license, verify permission allowlist, and download high-resolution source video."
    )
    # Direct Link Input & Instant Rights Approval
    with st.container(border=True):
        st.markdown("#### 🔗 Paste Video Link for Rights Clearance & Download")
        st.caption(
            "Paste ANY YouTube URL (Standard or Shorts) or independent platform video link "
            "(TikTok, Instagram, Twitter/X, Facebook, Vimeo, direct MP4). "
            "Inspect copyright status, grant clearance / allowlist approval, and download in one place."
        )

        pasted_phase2_url = st.text_input(
            "Paste Video URL",
            placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/... or TikTok / IG / X link",
            key="tab2_paste_link_input",
            label_visibility="collapsed"
        )

        p2_c1, p2_c2, p2_c3 = st.columns([1, 1.3, 1.4])
        with p2_c1:
            btn_inspect = st.button("🔍 Inspect Rights", width="stretch", key="tab2_inspect_btn")
        with p2_c2:
            btn_paste_approve = st.button("✅ Paste & Approve Link", type="primary", width="stretch", key="tab2_paste_approve_btn")
        with p2_c3:
            btn_paste_appr_dl = st.button("⚡ Approve & Download", width="stretch", key="tab2_paste_appr_dl_btn")

        if btn_inspect:
            if not pasted_phase2_url.strip():
                st.warning("⚠️ Please paste a valid video URL first.")
            else:
                with st.spinner("Inspecting video metadata and evaluating copyright status..."):
                    resolved_meta, err = resolve_video_from_url(pasted_phase2_url.strip())
                    if resolved_meta:
                        st.session_state["selected_video"] = resolved_meta
                        st.toast(f"✅ Loaded: {resolved_meta.get('title', 'Video')[:35]}...")
                        st.rerun()
                    else:
                        st.error(f"❌ Could not resolve video link: {err}")

        if btn_paste_approve:
            if not pasted_phase2_url.strip():
                st.warning("⚠️ Please paste a valid video URL first.")
            else:
                with st.spinner("Resolving metadata and granting rights clearance..."):
                    resolved_meta, err = resolve_video_from_url(pasted_phase2_url.strip())
                    if resolved_meta:
                        cleared_meta = approve_and_clear_video(
                            resolved_meta,
                            permission_reason="User Approved for Transformative Community Clipping / Fair Use"
                        )
                        st.session_state["selected_video"] = cleared_meta
                        st.toast("✅ Video approved and added to allowlist!")
                        st.rerun()
                    else:
                        st.error(f"❌ Could not resolve video link: {err}")

        if btn_paste_appr_dl:
            if not pasted_phase2_url.strip():
                st.warning("⚠️ Please paste a valid video URL first.")
            else:
                with st.spinner("Resolving metadata and preparing download..."):
                    resolved_meta, err = resolve_video_from_url(pasted_phase2_url.strip())
                    if resolved_meta:
                        cleared_meta = approve_and_clear_video(
                            resolved_meta,
                            permission_reason="User Approved for Transformative Community Clipping / Fair Use"
                        )
                        st.session_state["selected_video"] = cleared_meta
                        
                        p_bar = st.progress(0.0, text="Initializing high-speed download with yt-dlp...")
                        def dl_hook(pct, speed, eta, text):
                            p_bar.progress(min(1.0, max(0.01, pct / 100.0)), text=text)
                        try:
                            dl_res = download_cleared_video(cleared_meta, progress_callback=dl_hook)
                            st.session_state["downloaded_video"] = dl_res
                            st.toast(f"✅ Download ready: {os.path.basename(dl_res['file_path'])}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Download failed: {str(e)}")
                    else:
                        st.error(f"❌ Could not resolve video link: {err}")

        st.divider()
        st.markdown("#### 📁 Or Upload Video File from Your Computer")
        st.caption("Upload an MP4, MOV, MKV, AVI, WEBM, or M4V video directly from your system with auto rights clearance:")
        tab2_upload_file = st.file_uploader(
            "Upload local video file",
            type=["mp4", "mov", "mkv", "avi", "webm", "m4v"],
            key="tab2_local_video_uploader"
        )
        if tab2_upload_file is not None:
            t2_up_col1, t2_up_col2 = st.columns([2.5, 1.5])
            with t2_up_col1:
                st.caption(f"📁 Selected: `{tab2_upload_file.name}` ({tab2_upload_file.size / (1024*1024):.1f} MB)")
            with t2_up_col2:
                if st.button("📥 Import & Go to Phase 3", type="primary", key="btn_tab2_import_upload", width="stretch"):
                    with st.spinner("Importing local video and granting clearance..."):
                        up_res = save_local_uploaded_video(tab2_upload_file)
                        st.session_state["downloaded_video"] = up_res
                        st.session_state["selected_video"] = {
                            "title": up_res["title"],
                            "video_id": up_res["video_id"],
                            "channel_title": up_res["channel_title"],
                            "is_cleared": True
                        }
                        switch_to_tab(NAV_TABS[2])
                        st.rerun()

    sel = st.session_state.get("selected_video")
    
    if sel:
        with st.container(border=True):
            hdr_left, hdr_right = st.columns([3, 1])
            with hdr_left:
                st.markdown("#### 🎯 Active Video for Rights Clearance")
            with hdr_right:
                if st.button("🔄 Clear / Change Video", key="tab2_clear_sel_btn", width="stretch"):
                    st.session_state["selected_video"] = None
                    st.session_state["downloaded_video"] = None
                    st.rerun()

            r1, r2 = st.columns([1.5, 3])
            with r1:
                if sel.get("thumbnail_url"):
                    st.image(sel["thumbnail_url"], width="stretch")
                plat = sel.get("platform", "YouTube")
                plat_icon = sel.get("platform_icon", "▶️")
                dur = sel.get("duration", "N/A")
                st.caption(f"{plat_icon} **Platform:** {plat} | ⏱️ **Duration:** {dur}")
            with r2:
                st.markdown(f"### {sel.get('title', 'Untitled Video')}")
                st.markdown(f"**Creator / Channel:** `{sel.get('channel_title', 'Unknown')}` | **License:** `{sel.get('license', 'Standard YouTube')}`")
                cleared, reason = check_rights_clearance(sel)
                
                if cleared:
                    st.success(f"✅ Cleared for Clipping: {reason}")
                else:
                    st.error(f"❌ Rights Locked: {reason}")

            # If locked, provide interactive clearance and approval options
            if not cleared:
                st.markdown("##### 🛡️ Approve Link & Clearance Options")
                st.info(
                    "This video is marked under a Standard license. To safely clip it, "
                    "select an approval basis below to add the creator to your Allowlist and unlock downloading."
                )
                
                appr_c1, appr_c2 = st.columns([2, 1.2])
                with appr_c1:
                    clearance_reason = st.selectbox(
                        "Clearance Basis / Permission Type",
                        [
                            "Transformative Community Fair Use / Shorts Clipping",
                            "Creator / Streamer Express Permission",
                            "Commentary, Critique & Educational Fair Use",
                            "Verified Rights Holder / Own Channel"
                        ],
                        key="tab2_clearance_reason_select"
                    )
                with appr_c2:
                    custom_note = st.text_input(
                        "Permission Note / Proof (Optional)",
                        placeholder="e.g. Public clip permissions / Discord",
                        key="tab2_custom_note"
                    )
                
                note_final = f"{clearance_reason}" + (f" - {custom_note.strip()}" if custom_note.strip() else "")
                
                btn_appr_col1, btn_appr_col2 = st.columns([1, 1])
                with btn_appr_col1:
                    if st.button("✅ Approve Link & Grant Clearance", type="primary", width="stretch", key="tab2_btn_approve_only"):
                        sel_approved = approve_and_clear_video(sel, permission_reason=note_final)
                        st.session_state["selected_video"] = sel_approved
                        st.toast("✅ Video approved and added to allowlist!")
                        st.rerun()
                with btn_appr_col2:
                    if st.button("⚡ Approve & Download Now", type="secondary", width="stretch", key="tab2_btn_appr_dl_action"):
                        sel_approved = approve_and_clear_video(sel, permission_reason=note_final)
                        st.session_state["selected_video"] = sel_approved
                        p_bar = st.progress(0.0, text="Initializing high-speed download with yt-dlp...")
                        def dl_hook(pct, speed, eta, text):
                            p_bar.progress(min(1.0, max(0.01, pct / 100.0)), text=text)
                        try:
                            dl_res = download_cleared_video(sel_approved, progress_callback=dl_hook)
                            st.session_state["downloaded_video"] = dl_res
                            st.success(f"✅ Download ready! Saved to: {os.path.basename(dl_res['file_path'])}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Download failed: {str(e)}")
            else:
                # Mandatory Creator Attribution
                credits = generate_attribution_credits(sel)
                st.markdown("#### 📝 Mandatory Creator Attribution (Auto-Generated)")
                st.code(credits["description_credit"], language="text")

                # High-speed yt-dlp download button
                dl_btn = st.button("⬇️ Download High-Res Video with yt-dlp", type="primary", width="stretch", key="tab2_dl_cleared_btn")
                if dl_btn:
                    p_bar = st.progress(0.0, text="Initializing high-speed download with yt-dlp...")
                    def dl_hook(pct, speed, eta, text):
                        p_bar.progress(min(1.0, max(0.01, pct / 100.0)), text=text)
                    try:
                        download_result = download_cleared_video(sel, progress_callback=dl_hook)
                        st.session_state["downloaded_video"] = download_result
                        st.success(f"✅ Video ready for clipping! Saved to: {os.path.basename(download_result['file_path'])}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Download failed: {str(e)}")

        # Show Downloaded Video Player if ready
        dl_vid = st.session_state.get("downloaded_video")
        if dl_vid and os.path.exists(dl_vid.get("file_path", "")):
            with st.container(border=True):
                st.markdown("#### 🎬 Downloaded Source Video Preview")
                st.video(dl_vid["file_path"])
                st.caption(f"File: `{dl_vid['file_path']}` | Credits: `{dl_vid.get('credits_path', '')}`")
                if st.button("👉 Proceed to AI Highlight Detection (Tab 3)", key="tab2_to_tab3_btn", type="primary", width="stretch"):
                    switch_to_tab(NAV_TABS[2])
    else:
        st.info("💡 Paste any video link in the box above to inspect and approve rights, or select a video from Tab 1 (Discovery).")

    st.divider()
    
    # Permission Allowlist Management & Educational Explanation
    st.markdown("#### 📋 Permission Allowlist Management")
    
    with st.expander("💡 What is the Permission Allowlist? (Click to understand)", expanded=True):
        st.markdown("""
        **How It Works & Why It's Here:**
        1. **Strict Copyright Protection**: By default, standard YouTube videos cannot be downloaded or clipped without permission. ClipForge only unlocks videos that are verified **Creative Commons (CC-BY)**.
        2. **Streamer & Fair-Use Partnerships**: However, many popular creators—such as streamers (Kai Cenat, xQc, IShowSpeed), podcast networks, and talk shows—**explicitly allow or encourage** community clipping on TikTok and Shorts.
        3. **Your VIP List**: When you add a channel here with a permission note (or click **'🔓 Unlock Channel'** on any search card), ClipForge adds them to your Allowlist.
        4. **Automatic Unlocking**: All videos from that channel are instantly unlocked for clipping with compliant attribution credits automatically attached.
        """)

    with st.expander("➕ Add New Channel to Allowlist"):
        with st.form("add_allowlist_form"):
            new_ch_id = st.text_input("Channel ID (e.g. UC_xQc_official)")
            new_ch_name = st.text_input("Channel Name (e.g. Kai Cenat Live)")
            new_ch_note = st.text_area("Permission Note / Proof URL (e.g. Streamer allows transformative short clips on TikTok)")
            if st.form_submit_button("➕ Add Channel to Allowlist"):
                if new_ch_id and new_ch_name:
                    add_to_allowlist(new_ch_id, new_ch_name, new_ch_note)
                    st.success(f"Added '{new_ch_name}' to allowlist!")
                    st.rerun()

    al = get_allowlist()
    if al:
        st.dataframe(pd.DataFrame(al), hide_index=True, width="stretch")
    else:
        st.caption("No custom channels in allowlist yet. Use the form above or click '🔓 Unlock Channel' on any card.")


# ==============================================================================
# TAB 3: HIGHLIGHT DETECTION (Phase 3 Functional & Independent)
# ==============================================================================
elif current_tab == NAV_TABS[2]:
    render_phase_header(
        2,
        "✂️ Phase 3: AI Highlight & Viral Hook Detection",
        "Analyzes audio energy peaks, visual scene cuts, viral hook patterns, and LLM scoring to produce candidate clips."
    )
    
    # DIRECT VIDEO LINK & LOCAL UPLOAD PANEL (INDEPENDENT MODE)
    with st.container(border=True):
        st.markdown("#### ⚡ Direct Video Link & Local Upload Analysis (Independent Mode)")
        st.caption("Skip Tab 1 and Tab 2! Paste ANY YouTube video link, ANY social video link, or upload a video directly from your system to analyze highlights and convert into multiple short videos immediately:")

        # Field 1: YouTube Video URL
        st.markdown("##### 🔴 Option A: YouTube Video Link")
        t3_col1, t3_col2 = st.columns([3.2, 1.2])
        with t3_col1:
            direct_link_input = st.text_input(
                "YouTube Video URL",
                placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
                key="direct_tab3_link",
                label_visibility="collapsed"
            )
        with t3_col2:
            direct_analyze_btn = st.button("⚡ Analyze YouTube Link", type="primary", width="stretch", key="btn_yt_analyze_t3")

        if direct_analyze_btn:
            if direct_link_input.strip():
                t3_p_bar = st.progress(0.0, text="Fetching video & initializing download...")
                def t3_dl_hook(pct, speed, eta, text):
                    t3_p_bar.progress(min(1.0, max(0.01, pct / 100.0)), text=text)
                try:
                    dl_res = download_cleared_video(direct_link_input.strip(), progress_callback=t3_dl_hook)
                    st.session_state["downloaded_video"] = dl_res
                    st.session_state["selected_video"] = {
                        "title": dl_res.get("title", "Direct Imported Video"),
                        "video_id": dl_res.get("video_id", "imported"),
                        "channel_title": dl_res.get("channel_title", "Creator")
                    }
                    with st.spinner("Scanning audio energy peaks, visual scene cuts, and viral hook moments..."):
                        cands = extract_highlight_candidates(dl_res["file_path"], dl_res.get("title", "Video"))
                        st.session_state["highlight_candidates"] = cands
                    st.success(f"Generated {len(cands)} highlight candidates directly from YouTube link!")
                    st.rerun()
                except Exception as err:
                    st.error(f"Failed to process YouTube link: {str(err)}")
            else:
                st.warning("Please enter a valid YouTube URL.")

        st.divider()

        # Field 2: Independent Video Link (Facebook, Instagram, TikTok, etc.)
        st.markdown("##### 🌐 Option B: Any Independent Video Link (Facebook, Instagram, TikTok, X / Twitter, Vimeo, etc.)")
        st.caption("Paste any link from any social channel or website. ClipForge will inspect the video, preview it, and let you confirm download & highlight detection:")

        indep_col1, indep_col2 = st.columns([3.2, 1.2])
        with indep_col1:
            independent_link_input = st.text_input(
                "Independent Video Link",
                placeholder="https://www.tiktok.com/@... or https://www.instagram.com/reel/... or https://www.facebook.com/... or https://x.com/...",
                key="direct_tab3_independent_link",
                label_visibility="collapsed"
            )
        with indep_col2:
            detect_preview_btn = st.button("🔍 Detect & Preview Video", type="secondary", width="stretch", key="btn_indep_detect_t3")

        if detect_preview_btn:
            if independent_link_input and independent_link_input.strip():
                with st.spinner("Detecting video and extracting preview from link..."):
                    meta, err = inspect_independent_video_url(independent_link_input.strip())
                    if meta:
                        st.session_state["t3_independent_preview"] = meta
                        st.session_state["t3_independent_preview_url"] = independent_link_input.strip()
                    else:
                        st.error(f"Could not inspect video link: {err}")
            else:
                st.warning("Please enter a video URL from Facebook, Instagram, TikTok, X, or Vimeo.")

        # Independent Video Preview & Download Card
        indep_preview = st.session_state.get("t3_independent_preview")
        if indep_preview:
            with st.container(border=True):
                p_c1, p_c2 = st.columns([1.3, 2.7])
                with p_c1:
                    thumb_url = indep_preview.get("thumbnail_url")
                    if thumb_url and thumb_url.startswith("http"):
                        st.image(thumb_url, width="stretch")
                    else:
                        st.markdown(f"<div style='background:#1e293b;padding:30px;border-radius:10px;text-align:center;font-size:2rem;'>{indep_preview.get('platform_icon', '🎬')}<br><span style='font-size:1rem;color:#94a3b8;'>{indep_preview.get('platform', 'Web Video')}</span></div>", unsafe_allow_html=True)
                with p_c2:
                    p_badge = f"<span style='background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%); color: white; padding: 3px 10px; border-radius: 6px; font-weight: bold; font-size: 0.8rem;'>{indep_preview.get('platform_icon', '🌐')} {indep_preview.get('platform', 'INDEPENDENT')}</span>"
                    st.markdown(p_badge, unsafe_allow_html=True)
                    st.markdown(f"#### {indep_preview.get('title', 'Detected Video')}")
                    st.markdown(f"👤 **Creator:** `{indep_preview.get('channel_title', 'Creator')}` | ⏱️ **Duration:** `{indep_preview.get('duration', '01:00')}`")
                    st.caption(f"🔗 Source: `{indep_preview.get('webpage_url', '')}`")
                    if indep_preview.get("inspection_warning"):
                        st.caption(f"ℹ️ {indep_preview.get('inspection_warning')}")

                    b_c1, b_c2 = st.columns([2.4, 1.1])
                    with b_c1:
                        confirm_download_btn = st.button("📥 Download & Detect Highlights Now", key="btn_confirm_dl_indep", type="primary", width="stretch")
                    with b_c2:
                        if st.button("❌ Cancel / Clear", key="btn_cancel_indep", width="stretch"):
                            st.session_state.pop("t3_independent_preview", None)
                            st.session_state.pop("t3_independent_preview_url", None)
                            st.rerun()

                    if confirm_download_btn:
                        indep_pbar = st.progress(0.0, text="Downloading independent video media with yt-dlp...")
                        def indep_dl_hook(pct, speed, eta, text):
                            indep_pbar.progress(min(1.0, max(0.01, pct / 100.0)), text=text)
                        try:
                            dl_res = download_cleared_video(indep_preview, progress_callback=indep_dl_hook)
                            st.session_state["downloaded_video"] = dl_res
                            st.session_state["selected_video"] = {
                                "title": dl_res.get("title", indep_preview.get("title")),
                                "video_id": dl_res.get("video_id", indep_preview.get("video_id")),
                                "channel_title": indep_preview.get("channel_title", "Creator")
                            }
                            st.session_state.pop("t3_independent_preview", None)
                            with st.spinner("Extracting audio energy peaks, visual scene cuts, and viral hook moments..."):
                                cands = extract_highlight_candidates(dl_res["file_path"], dl_res.get("title", "Video"))
                                st.session_state["highlight_candidates"] = cands
                            st.success(f"🎉 Downloaded from {indep_preview.get('platform')} and generated {len(cands)} highlight candidates!")
                            st.rerun()
                        except Exception as dl_err:
                            st.error(f"Failed to download independent video: {str(dl_err)}")

        st.divider()

        # Field 3: Upload Local Video from System
        st.markdown("##### 📁 Option C: Upload Local Video from Your System (PC / Mac)")
        st.caption(
            "Upload any video file from your computer (MP4, MOV, MKV, AVI, WEBM, M4V). "
            "ClipForge will import it, analyze viral energy peaks & hook moments, and convert it into multiple vertical short videos:"
        )

        t3_upload_file = st.file_uploader(
            "Upload a video file from your system",
            type=["mp4", "mov", "mkv", "avi", "webm", "m4v"],
            key="tab3_local_video_uploader",
            help="Select a video file from your local computer to convert into multiple Shorts."
        )

        if t3_upload_file is not None:
            with st.container(border=True):
                file_size_mb = t3_upload_file.size / (1024 * 1024)
                default_title = os.path.splitext(t3_upload_file.name)[0].replace("_", " ").replace("-", " ").title()

                u_col1, u_col2 = st.columns([1.5, 2.5])
                with u_col1:
                    st.video(t3_upload_file)
                    st.caption(f"📁 **File:** `{t3_upload_file.name}` | 📦 **Size:** `{file_size_mb:.1f} MB`")
                with u_col2:
                    t3_up_title = st.text_input(
                        "Video Title",
                        value=default_title,
                        key="tab3_upload_title_field",
                        help="Title used for metadata, attribution, and clip descriptions."
                    )
                    t3_up_creator = st.text_input(
                        "Creator / Channel Name",
                        value="My Upload",
                        key="tab3_upload_creator_field",
                        help="Channel or creator attribution name."
                    )

                    st.markdown("###### ⚙️ Auto-Editor Presets for Generated Shorts:")
                    p_c1, p_c2, p_c3 = st.columns([1.4, 1.4, 1.0])
                    with p_c1:
                        up_layout = st.selectbox(
                            "Visual Layout",
                            ["🎨 Blurred Background Stack", "✂️ Smart Center Vertical Crop", "⬛ Fit Letterbox (Clean Black Bars)"],
                            key="t3_up_layout_sel"
                        )
                        up_layout_mode = {
                            "🎨 Blurred Background Stack": "blurred_stack",
                            "✂️ Smart Center Vertical Crop": "smart_crop",
                            "⬛ Fit Letterbox (Clean Black Bars)": "fit_letterbox"
                        }.get(up_layout, "blurred_stack")
                    with p_c2:
                        up_sub = st.selectbox(
                            "Subtitle Preset",
                            ["🟡 Alex Hormozi Bold Yellow", "⚪ MrBeast Clean White & Gold", "🔵 Cyber Neon Cyan", "🚫 None (No Text / Clean Video)"],
                            key="t3_up_sub_sel",
                            help="Select subtitle style or 'None' for clean video."
                        )
                        up_sub_style = {
                            "🟡 Alex Hormozi Bold Yellow": "hormozi_yellow",
                            "⚪ MrBeast Clean White & Gold": "beast_white",
                            "🔵 Cyber Neon Cyan": "neon_cyan",
                            "🚫 None (No Text / Clean Video)": "none"
                        }.get(up_sub, "hormozi_yellow")
                    with p_c3:
                        up_spd = st.selectbox(
                            "Speed",
                            ["1.0x (Normal)", "1.25x", "1.5x", "2.0x"],
                            key="t3_up_spd_sel",
                            help="Playback speed multiplier."
                        )
                        up_speed = {"1.0x (Normal)": 1.0, "1.25x": 1.25, "1.5x": 1.5, "2.0x": 2.0}.get(up_spd, 1.0)

                    btn_c1, btn_c2 = st.columns([1.3, 1.7])
                    with btn_c1:
                        btn_upload_detect = st.button(
                            "🔍 Detect Highlights & Review",
                            type="secondary",
                            width="stretch",
                            key="btn_t3_upload_detect",
                            help="Imports the video and detects all viral candidate moments for editing & customization."
                        )
                    with btn_c2:
                        btn_upload_batch = st.button(
                            "⚡ Convert into Multiple Shorts (Batch Render All)",
                            type="primary",
                            width="stretch",
                            key="btn_t3_upload_batch",
                            help="Imports video, extracts highlights, and automatically renders 9:16 vertical shorts from all candidate moments!"
                        )

                if btn_upload_detect:
                    up_pbar = st.progress(0.1, text="Importing and saving uploaded video...")
                    def up_dl_hook(pct, text):
                        up_pbar.progress(min(0.8, max(0.05, pct / 100.0)), text=text)
                    try:
                        up_res = save_local_uploaded_video(
                            t3_upload_file,
                            custom_title=t3_up_title,
                            creator_name=t3_up_creator,
                            progress_callback=up_dl_hook
                        )
                        st.session_state["downloaded_video"] = up_res
                        st.session_state["selected_video"] = {
                            "title": up_res["title"],
                            "video_id": up_res["video_id"],
                            "channel_title": up_res["channel_title"]
                        }
                        up_pbar.progress(0.85, text="Scanning audio energy peaks, visual scene cuts, and viral hook moments...")
                        cands = extract_highlight_candidates(up_res["file_path"], up_res["title"])
                        st.session_state["highlight_candidates"] = cands
                        if cands:
                            st.session_state["selected_candidate"] = cands[0]
                        cand_cache_file = os.path.join(os.path.dirname(up_res["file_path"]), "candidates.json")
                        try:
                            with open(cand_cache_file, "w") as f:
                                json.dump(cands, f, indent=2)
                        except Exception:
                            pass
                        up_pbar.progress(1.0, text=f"Generated {len(cands)} highlight candidates!")
                        st.success(f"🎉 Imported local video and detected {len(cands)} highlight candidates ready to convert into shorts!")
                        st.rerun()
                    except Exception as up_err:
                        st.error(f"Failed to process uploaded video: {str(up_err)}")

                if btn_upload_batch:
                    up_pbar = st.progress(0.05, text="Importing and saving uploaded video...")
                    def up_batch_hook(pct, text):
                        up_pbar.progress(min(0.25, max(0.05, (pct / 100.0) * 0.25)), text=text)
                    try:
                        up_res = save_local_uploaded_video(
                            t3_upload_file,
                            custom_title=t3_up_title,
                            creator_name=t3_up_creator,
                            progress_callback=up_batch_hook
                        )
                        vid_path = up_res["file_path"]
                        curr_vid_id = up_res["video_id"]
                        st.session_state["downloaded_video"] = up_res
                        st.session_state["selected_video"] = {
                            "title": up_res["title"],
                            "video_id": curr_vid_id,
                            "channel_title": up_res["channel_title"]
                        }
                        up_pbar.progress(0.25, text="Analyzing viral hook patterns and scene transitions...")
                        cands = extract_highlight_candidates(vid_path, up_res["title"])
                        st.session_state["highlight_candidates"] = cands
                        if cands:
                            st.session_state["selected_candidate"] = cands[0]
                        cand_cache_file = os.path.join(os.path.dirname(vid_path), "candidates.json")
                        try:
                            with open(cand_cache_file, "w") as f:
                                json.dump(cands, f, indent=2)
                        except Exception:
                            pass

                        v_meta_base = {
                            "video_id": curr_vid_id,
                            "title": up_res["title"],
                            "channel_title": up_res["channel_title"]
                        }
                        rendered_count = 0
                        for b_idx, c_item in enumerate(cands):
                            cand_pct = 0.3 + (0.65 * (b_idx / max(1, len(cands))))
                            up_pbar.progress(cand_pct, text=f"Rendering Short {b_idx + 1}/{len(cands)}: #{c_item['clip_id']} `{c_item.get('hook_title')}` ({up_speed}x)...")
                            try:
                                res_item = render_short_video(
                                    source_video_path=vid_path,
                                    clip_candidate=c_item,
                                    video_metadata=v_meta_base,
                                    layout_mode=up_layout_mode,
                                    subtitle_style=up_sub_style,
                                    speed=up_speed
                                )
                                st.session_state[f"rendered_cand_{c_item['clip_id']}"] = res_item
                                try:
                                    create_export_pack(res_item.get("clip_db_id", c_item["clip_id"]), video_id=curr_vid_id)
                                except Exception:
                                    pass
                                rendered_count += 1
                            except Exception as render_err:
                                st.error(f"Candidate #{c_item['clip_id']} render failed: {render_err}")

                        up_pbar.progress(0.97, text="Packaging Master ZIP archive...")
                        try:
                            create_batch_export_pack(curr_vid_id)
                        except Exception:
                            pass
                        up_pbar.progress(1.0, text="Conversion complete!")
                        st.success(f"🚀 Successfully imported and converted local video into {rendered_count} of {len(cands)} vertical 9:16 Shorts!")
                        st.rerun()
                    except Exception as batch_err:
                        st.error(f"Failed to convert video into shorts: {str(batch_err)}")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Discover all downloaded source videos on disk
    available_downloads = []
    dl_root = os.path.join(os.path.dirname(__file__), "downloads")
    if os.path.exists(dl_root):
        for d in os.listdir(dl_root):
            mp4 = os.path.join(dl_root, d, f"{d}_source.mp4")
            if os.path.exists(mp4):
                available_downloads.append({"id": d, "path": mp4})

    active_download = st.session_state.get("downloaded_video")
    sel_vid = st.session_state.get("selected_video")

    # Determine current active video ID
    current_vid_id = None
    if active_download and active_download.get("video_id"):
        current_vid_id = active_download["video_id"]
    elif sel_vid and sel_vid.get("video_id"):
        current_vid_id = sel_vid["video_id"]
    elif available_downloads:
        current_vid_id = available_downloads[0]["id"]

    # Active Video Selector Card in Phase 3
    if available_downloads:
        avail_ids = [x["id"] for x in available_downloads]
        default_idx = avail_ids.index(current_vid_id) if current_vid_id in avail_ids else 0

        # Ensure active_download and selected_video are synchronized
        if not active_download or active_download.get("video_id") != current_vid_id or not os.path.exists(active_download.get("file_path", "")):
            matched_p = next((x["path"] for x in available_downloads if x["id"] == current_vid_id), available_downloads[0]["path"])
            current_vid_id = os.path.basename(os.path.dirname(matched_p))
            c_file = os.path.join(os.path.dirname(matched_p), "credits.json")
            c_creator = "Original Creator"
            c_title = f"Video ({current_vid_id})"
            if os.path.exists(c_file):
                try:
                    with open(c_file, "r") as cf:
                        c_data = json.load(cf)
                        c_creator = c_data.get("creator", "Original Creator")
                except Exception:
                    pass
            active_download = {"video_id": current_vid_id, "file_path": matched_p, "title": c_title}
            st.session_state["downloaded_video"] = active_download
            if not sel_vid or sel_vid.get("video_id") != current_vid_id:
                sel_vid = {"video_id": current_vid_id, "title": c_title, "channel_title": c_creator}
                st.session_state["selected_video"] = sel_vid

        with st.container(border=True):
            av_col1, av_col2 = st.columns([2.5, 1.5])
            with av_col1:
                cur_title = (st.session_state.get("selected_video") or {}).get("title") or f"Video ({current_vid_id})"
                cur_creator = (st.session_state.get("selected_video") or {}).get("channel_title") or "Creator"
                st.markdown(f"#### 🎥 Active Source: **{cur_title}**")
                st.caption(f"Creator: **{cur_creator}** | Video ID: `{current_vid_id}`")
            with av_col2:
                selected_choice = st.selectbox(
                    "Switch Video to Edit",
                    avail_ids,
                    index=default_idx,
                    help="Choose which downloaded video to edit into a Short.",
                    key="tab3_switch_video_to_edit"
                )
                if selected_choice != current_vid_id:
                    current_vid_id = selected_choice
                    matched_path = next(x["path"] for x in available_downloads if x["id"] == current_vid_id)
                    c_file = os.path.join(os.path.dirname(matched_path), "credits.json")
                    c_creator = "Original Creator"
                    c_title = f"Video ({current_vid_id})"
                    if os.path.exists(c_file):
                        try:
                            with open(c_file, "r") as cf:
                                c_data = json.load(cf)
                                c_creator = c_data.get("creator", "Original Creator")
                        except Exception:
                            pass
                    st.session_state["downloaded_video"] = {"video_id": current_vid_id, "file_path": matched_path, "title": c_title}
                    st.session_state["selected_video"] = {"video_id": current_vid_id, "title": c_title, "channel_title": c_creator}
                    st.session_state["selected_candidate"] = None
                    st.session_state["rendered_clip"] = None
                    st.session_state["highlight_candidates"] = []
                    cand_cache_file = os.path.join(os.path.dirname(matched_path), "candidates.json")
                    if os.path.exists(cand_cache_file):
                        try:
                            with open(cand_cache_file, "r") as f:
                                st.session_state["highlight_candidates"] = json.load(f)
                        except Exception:
                            pass
                    st.rerun()

    # If no video downloaded yet, offer demo video or prompt
    if not active_download or not os.path.exists(active_download.get("file_path", "")):
        with st.container(border=True):
            st.info("Or test with a sample long-form clip below:")
            if st.button("⚡ Test Highlight Detection on Sample Football/Science Video", type="secondary"):
                demo_sel = {
                    "video_id": "demo_football_highlight",
                    "title": "Lionel Messi & Ronaldinho: Iconic Football Skills & Solo Goals",
                    "channel_title": "Open Sports Archive CC",
                    "channel_id": "UC_open_sports_archive",
                    "is_cc": True,
                    "license": "Creative Commons"
                }
                res = download_cleared_video(demo_sel)
                st.session_state["downloaded_video"] = res
                st.rerun()
    else:
        vid_path = active_download["file_path"]
        vid_title = (st.session_state.get("selected_video") or {}).get("title", os.path.basename(vid_path))
        
        with st.container(border=True):
            v_col1, v_col2 = st.columns([1.5, 2.5])
            with v_col1:
                st.video(vid_path)
            with v_col2:
                st.markdown(f"#### 🎬 Source Video: {vid_title}")
                st.caption(f"Path: `{vid_path}`")
                
                scan_btn = st.button("🔍 Scan for Viral Highlights & Hook Moments", type="primary", width="stretch")
                if scan_btn:
                    with st.spinner("Analyzing audio energy peaks, scene cuts, and viral hook patterns..."):
                        candidates = extract_highlight_candidates(vid_path, vid_title)
                        st.session_state["highlight_candidates"] = candidates
                        # Cache candidates to disk for persistence across page refreshes
                        cand_cache_file = os.path.join(os.path.dirname(vid_path), "candidates.json")
                        try:
                            with open(cand_cache_file, "w") as f:
                                json.dump(candidates, f, indent=2)
                        except Exception:
                            pass
                        st.success(f"Generated {len(candidates)} high-engagement candidate clips!")

        # Render Highlight Candidates & Sections
        candidates = st.session_state.get("highlight_candidates", [])
        # Auto-restore candidates from cache if session state cleared
        if not candidates and vid_path:
            cand_cache_file = os.path.join(os.path.dirname(vid_path), "candidates.json")
            if os.path.exists(cand_cache_file):
                try:
                    with open(cand_cache_file, "r") as f:
                        candidates = json.load(f)
                    st.session_state["highlight_candidates"] = candidates
                except Exception:
                    pass

        if candidates:
            # Active video & candidate synchronization
            curr_vid_id = (st.session_state.get("selected_video") or {}).get("video_id") or os.path.basename(os.path.dirname(vid_path))
            sel_cand = st.session_state.get("selected_candidate")
            if not sel_cand or sel_cand.get("clip_id") not in [c["clip_id"] for c in candidates]:
                sel_cand = candidates[0]
                st.session_state["selected_candidate"] = sel_cand

            work_dir = os.path.dirname(vid_path)
            
            # Discover any rendered shorts on disk for this video
            disk_rendered_files = {}
            if os.path.exists(work_dir):
                for f in os.listdir(work_dir):
                    if f.startswith(f"{curr_vid_id}_short_clip_") and f.endswith(".mp4"):
                        cid_m = re.search(r"_short_clip_(\d+)\.mp4", f)
                        if cid_m:
                            disk_rendered_files[int(cid_m.group(1))] = os.path.join(work_dir, f)

            rendered_for_vid = [c for c in get_clips(video_id=curr_vid_id) if os.path.exists(c.get("file_path", ""))]
            
            # Auto-register any disk-rendered shorts not yet indexed in clips DB
            for cid_num, f_path in disk_rendered_files.items():
                if not any(rc.get("file_path") == f_path or os.path.basename(rc.get("file_path", "")) == os.path.basename(f_path) for rc in rendered_for_vid):
                    match_cand = next((cand for cand in candidates if cand["clip_id"] == cid_num), None)
                    save_clip({
                        "video_id": curr_vid_id,
                        "start_time": match_cand["start_time"] if match_cand else 0.0,
                        "end_time": match_cand["end_time"] if match_cand else 45.0,
                        "duration": match_cand["duration"] if match_cand else 45.0,
                        "score": match_cand.get("score", 80.0) if match_cand else 80.0,
                        "rationale": match_cand.get("rationale", "") if match_cand else "",
                        "hook_title": match_cand.get("hook_title", f"Short Clip #{cid_num}") if match_cand else f"Short Clip #{cid_num}",
                        "file_path": f_path,
                        "status": "approved"
                    })
            rendered_for_vid = [c for c in get_clips(video_id=curr_vid_id) if os.path.exists(c.get("file_path", ""))]

            st.divider()
            st.markdown(f"#### 🏆 Highlight Management & Candidate Sections")
            
            # Interactive Filter Switch between Sections
            t3_section = st.radio(
                "Filter View",
                [
                    f"📋 All Detected Candidates ({len(candidates)})",
                    f"🎯 Active Candidate #{sel_cand['clip_id']} ({sel_cand['start_formatted']} ➔ {sel_cand['end_formatted']})",
                    f"📱 Rendered Shorts ({len(rendered_for_vid)})"
                ],
                horizontal=True,
                key="t3_section_radio_filter"
            )

            # ==========================================
            # SECTION 1: ALL DETECTED CANDIDATES
            # ==========================================
            if "All Detected Candidates" in t3_section:
                st.info("💡 **All Detected Moments:** Each moment below features full inline **Auto-Editor controls** (Visual Layout, Dynamic Subtitles, Hook Title, Timing, and Watermarks). You can customize and render each Short directly from here, or use the 1-Click Batch Engine to produce and export all Shorts!")

                # --- BATCH PRODUCTION & MASTER EXPORT BAR ---
                with st.container(border=True):
                    st.markdown("#### ⚡ Batch Production & Master Export (.zip)")
                    st.caption("Apply universal presets across all detections, batch render all candidates with 1-click, and download a single Master ZIP containing all generated shorts and metadata!")

                    b_c1, b_c2, b_c3, b_c4 = st.columns([1.3, 1.3, 1.1, 1.6])
                    with b_c1:
                        batch_layout_choice = st.selectbox(
                            "Batch Visual Layout",
                            [
                                "🎨 Blurred Background Stack",
                                "✂️ Smart Center Vertical Crop",
                                "⬛ Fit Letterbox (Clean Black Bars)"
                            ],
                            key="batch_layout_choice"
                        )
                        batch_layout_mode = {
                            "🎨 Blurred Background Stack": "blurred_stack",
                            "✂️ Smart Center Vertical Crop": "smart_crop",
                            "⬛ Fit Letterbox (Clean Black Bars)": "fit_letterbox"
                        }.get(batch_layout_choice, "blurred_stack")

                    with b_c2:
                        batch_sub_choice = st.selectbox(
                            "Batch Subtitle Preset",
                            [
                                "🟡 Alex Hormozi Bold Yellow",
                                "⚪ MrBeast Clean White & Gold",
                                "🔵 Cyber Neon Cyan",
                                "🚫 None (No Text / Clean Video)"
                            ],
                            key="batch_sub_choice",
                            help="Select subtitle style, or select 'None' to export clean video without any text overlays."
                        )
                        batch_subtitle_style = {
                            "🟡 Alex Hormozi Bold Yellow": "hormozi_yellow",
                            "⚪ MrBeast Clean White & Gold": "beast_white",
                            "🔵 Cyber Neon Cyan": "neon_cyan",
                            "🚫 None (No Text / Clean Video)": "none"
                        }.get(batch_sub_choice, "hormozi_yellow")

                    with b_c3:
                        batch_speed_choice = st.selectbox(
                            "⚡ Playback Speed",
                            [
                                "1.0x (Normal)",
                                "1.25x (1.25x Faster)",
                                "1.5x (1.5x Speed Up)",
                                "2.0x (2.0x Double Speed)"
                            ],
                            index=0,
                            key="batch_speed_choice",
                            help="Speed up video and audio with pitch-corrected audio normalization."
                        )
                        batch_speed = {
                            "1.0x (Normal)": 1.0,
                            "1.25x (1.25x Faster)": 1.25,
                            "1.5x (1.5x Speed Up)": 1.5,
                            "2.0x (2.0x Double Speed)": 2.0
                        }.get(batch_speed_choice, 1.0)

                    with b_c4:
                        st.write("")
                        st.write("")
                        batch_render_btn = st.button(
                            f"⚡ Batch Render All ({len(candidates)} Candidates)",
                            key="t3_batch_render_btn",
                            type="primary",
                            width="stretch",
                            help="Sequentially renders vertical 9:16 Shorts from all detected moments using selected batch preset and speed."
                        )

                    master_zip_name = f"ClipForge_All_Shorts_{curr_vid_id}.zip"
                    master_zip_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", master_zip_name)

                    b_stat1, b_stat2 = st.columns([1.9, 2.1])
                    with b_stat1:
                        st.write(f"📊 **Render Status:** **{len(rendered_for_vid)} of {len(candidates)}** candidate moments rendered & ready.")
                    with b_stat2:
                        if os.path.exists(master_zip_path) and os.path.getsize(master_zip_path) > 0:
                            mz_size_mb = os.path.getsize(master_zip_path) / (1024 * 1024)
                            mz_c1, mz_c2 = st.columns([3.0, 1.2])
                            with mz_c1:
                                st.download_button(
                                    label=f"📦 Download All Shorts Master ZIP ({mz_size_mb:.1f} MB)",
                                    data=make_file_downloader(master_zip_path),
                                    file_name=master_zip_name,
                                    mime="application/zip",
                                    key="t3_master_zip_dl",
                                    type="primary",
                                    width="stretch",
                                    on_click="ignore",
                                    help="Download all rendered shorts, platform captions, and metadata archive directly to your downloads."
                                )
                            with mz_c2:
                                if st.button("📂 Open Folder", key="t3_open_master_folder", help="Open download folder in Windows File Explorer", width="stretch"):
                                    open_folder_in_explorer(master_zip_path)
                                    st.toast("📂 Highlighted Master ZIP in File Explorer!")
                        elif len(rendered_for_vid) > 0:
                            if st.button("📦 Build Master ZIP (All Shorts)", key="t3_build_master_zip", width="stretch"):
                                with st.spinner("Bundling all rendered shorts and metadata into master zip..."):
                                    try:
                                        m_res = create_batch_export_pack(curr_vid_id)
                                        st.success(f"Master ZIP created ({m_res['zip_size_mb']} MB)!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed to create Master ZIP: {e}")

                    if batch_render_btn:
                        batch_pbar = st.progress(0, text="Initializing batch render engine...")
                        batch_msg = st.empty()
                        v_meta_base = st.session_state.get("selected_video") or {
                            "video_id": curr_vid_id,
                            "channel_title": "Original Creator"
                        }
                        rendered_count = 0
                        for b_idx, c_item in enumerate(candidates):
                            cand_pct = int((b_idx / len(candidates)) * 100)
                            batch_pbar.progress(cand_pct, text=f"Rendering Short {b_idx + 1}/{len(candidates)}: #{c_item['clip_id']} `{c_item.get('hook_title')}` ({batch_speed}x)...")
                            batch_msg.info(f"⏳ Processing candidate #{c_item['clip_id']} ({c_item['start_formatted']} ➔ {c_item['end_formatted']} @ {batch_speed}x)...")
                            try:
                                res_item = render_short_video(
                                    source_video_path=vid_path,
                                    clip_candidate=c_item,
                                    video_metadata=v_meta_base,
                                    layout_mode=batch_layout_mode,
                                    subtitle_style=batch_subtitle_style,
                                    speed=batch_speed
                                )
                                st.session_state[f"rendered_cand_{c_item['clip_id']}"] = res_item
                                try:
                                    create_export_pack(res_item.get("clip_db_id", c_item["clip_id"]), video_id=curr_vid_id)
                                except Exception:
                                    pass
                                rendered_count += 1
                            except Exception as err:
                                st.error(f"Candidate #{c_item['clip_id']} render failed: {err}")

                        batch_pbar.progress(100, text="Batch rendering complete!")
                        try:
                            create_batch_export_pack(curr_vid_id)
                        except Exception:
                            pass
                        st.success(f"🎉 Successfully rendered {rendered_count} of {len(candidates)} Shorts!")
                        st.rerun()

                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

                # --- CANDIDATE CARDS WITH FULL AUTO-EDITOR CONTROLS & EXPORT ---
                for c in candidates:
                    cid = c["clip_id"]
                    is_active = (cid == sel_cand.get("clip_id"))

                    # Pre-sync timing from active inputs if present
                    if f"t3_start_m_{cid}" in st.session_state and f"t3_start_s_{cid}" in st.session_state:
                        c["start_time"] = round(float(st.session_state[f"t3_start_m_{cid}"]) * 60.0 + float(st.session_state[f"t3_start_s_{cid}"]), 1)
                    if f"t3_dur_m_{cid}" in st.session_state and f"t3_dur_s_{cid}" in st.session_state:
                        c["duration"] = max(3.0, round(float(st.session_state[f"t3_dur_m_{cid}"]) * 60.0 + float(st.session_state[f"t3_dur_s_{cid}"]), 1))
                    c["end_time"] = round(c["start_time"] + c["duration"], 1)
                    c["start_formatted"] = f"{int(c['start_time'] // 60):02d}:{int(c['start_time'] % 60):02d}"
                    c["end_formatted"] = f"{int(c['end_time'] // 60):02d}:{int(c['end_time'] % 60):02d}"
                    
                    cand_out_file = disk_rendered_files.get(cid) or os.path.join(work_dir, f"{curr_vid_id}_short_clip_{cid}.mp4")
                    cand_is_rendered = os.path.exists(cand_out_file) or (f"rendered_cand_{cid}" in st.session_state)
                    
                    matching_rendered = next((rc for rc in rendered_for_vid if rc.get("file_path") == cand_out_file or f"_short_clip_{cid}.mp4" in rc.get("file_path", "")), None)
                    clip_db_id = matching_rendered["id"] if matching_rendered else cid

                    with st.container(border=True):
                        c_player_col, c_info_col = st.columns([1.8, 2.2])

                        with c_player_col:
                            st.markdown(f"##### ▶️ Candidate #{cid} Source Segment")
                            st.video(vid_path, start_time=int(c['start_time']), end_time=int(c['end_time']))
                            st.caption(f"⏱️ **Window:** {c['start_formatted']} ➔ {c['end_formatted']} ({c['duration']}s segment)")

                            if cand_is_rendered and os.path.exists(cand_out_file):
                                st.divider()
                                st.markdown(f"##### 📱 Finished 9:16 Vertical Short #{cid}")
                                st.video(cand_out_file)
                                st.caption("✅ **1080x1920 Vertical Short** (Word-level Whisper captions + EBU R128 audio)")

                        with c_info_col:
                            badge_html = ""
                            if is_active:
                                badge_html += '<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.75rem; margin-right: 6px;">⭐ ACTIVE SELECTION</span>'
                            if cand_is_rendered:
                                badge_html += '<span style="background: #6366f1; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.75rem;">✅ 9:16 RENDERED</span>'
                            if badge_html:
                                st.markdown(badge_html, unsafe_allow_html=True)

                            st.markdown(f'<div class="score-badge">Viral Score: {c["score"]} / 100</div>', unsafe_allow_html=True)
                            st.markdown(f"#### 🔥 `{c['hook_title']}`")
                            st.write(f"💡 **AI Rationale:** {c['rationale']}")

                            # Auto-Editor inline controls box
                            with st.container(border=True):
                                st.markdown(f"##### 🎬 Auto-Editor Configuration for Short #{cid}")

                                # 1. Hook Title & Duration
                                c_h1, c_h2 = st.columns([2.3, 1.1])
                                with c_h1:
                                    c_hook = st.text_input(
                                        "🔥 Hook Title Overlay",
                                        value=c.get("hook_title", "UNBELIEVABLE MOMENT"),
                                        key=f"t3_hook_{cid}",
                                        help="Bold attention-grabbing title placed in the upper third."
                                    )
                                with c_h2:
                                    c_hook_dur = st.number_input(
                                        "⏱️ Hook Time (s)",
                                        min_value=0.5,
                                        max_value=None,
                                        value=float(c.get("hook_duration") or 5.0),
                                        step=0.5,
                                        key=f"t3_hook_dur_{cid}",
                                        help="Overlay duration in seconds for the hook title banner (e.g. 3.0s, 5.0s, 8.0s)."
                                    )

                                # 2. Layout & Captions
                                # 2. Layout, Captions & Speed
                                c_l_col, c_s_col, c_spd_col = st.columns([1.3, 1.3, 1.0])
                                with c_l_col:
                                    c_layout_choice = st.selectbox(
                                        "📐 Visual Layout (1080x1920)",
                                        [
                                            "🎨 Blurred Background Stack",
                                            "✂️ Smart Center Vertical Crop",
                                            "⬛ Fit Letterbox (Clean Black Bars)"
                                        ],
                                        index=0,
                                        key=f"t3_layout_{cid}",
                                        help="Blurred Stack keeps full action while filling 9:16 vertical frame."
                                    )
                                    c_layout_mode = {
                                        "🎨 Blurred Background Stack": "blurred_stack",
                                        "✂️ Smart Center Vertical Crop": "smart_crop",
                                        "⬛ Fit Letterbox (Clean Black Bars)": "fit_letterbox"
                                    }.get(c_layout_choice, "blurred_stack")

                                with c_s_col:
                                    c_sub_choice = st.selectbox(
                                        "💬 Caption Preset",
                                        [
                                            "🟡 Alex Hormozi Bold Yellow",
                                            "⚪ MrBeast Clean White & Gold",
                                            "🔵 Cyber Neon Cyan",
                                            "🚫 None (No Text / Clean Video)"
                                        ],
                                        index=0,
                                        key=f"t3_sub_{cid}",
                                        help="Word-level active animation using faster-whisper timestamps, or select None to render clean video without any text overlays."
                                    )
                                    c_subtitle_style = {
                                        "🟡 Alex Hormozi Bold Yellow": "hormozi_yellow",
                                        "⚪ MrBeast Clean White & Gold": "beast_white",
                                        "🔵 Cyber Neon Cyan": "neon_cyan",
                                        "🚫 None (No Text / Clean Video)": "none"
                                    }.get(c_sub_choice, "hormozi_yellow")
                                    if c_subtitle_style == "none":
                                        st.caption("🚫 Clean Video: No captions or text overlays will be added.")

                                with c_spd_col:
                                    c_speed_choice = st.selectbox(
                                        "⚡ Playback Speed",
                                        [
                                            "1.0x (Normal)",
                                            "1.25x (1.25x Faster)",
                                            "1.5x (1.5x Speed Up)",
                                            "2.0x (2.0x Double Speed)"
                                        ],
                                        index=0,
                                        key=f"t3_speed_{cid}",
                                        help="Speed up video and audio (with pitch-corrected EBU R128 audio normalization)."
                                    )
                                    c_speed = {
                                        "1.0x (Normal)": 1.0,
                                        "1.25x (1.25x Faster)": 1.25,
                                        "1.5x (1.5x Speed Up)": 1.5,
                                        "2.0x (2.0x Double Speed)": 2.0
                                    }.get(c_speed_choice, 1.0)

                                # 3. Timing Adjustments (Minutes & Seconds)
                                st.markdown("⏱️ **Timing & Clip Window (Minutes & Seconds)**")
                                t_c1, t_c2, t_c3, t_c4 = st.columns([1.0, 1.0, 1.0, 1.0])

                                init_start = float(c.get("start_time", 0.0))
                                init_start_m = int(init_start // 60)
                                init_start_s = round(init_start % 60, 1)
                                if init_start_s >= 60.0:
                                    init_start_m += 1
                                    init_start_s = 0.0

                                init_dur = float(c.get("duration", 45.0))
                                init_dur_m = int(init_dur // 60)
                                init_dur_s = round(init_dur % 60, 1)
                                if init_dur_s >= 60.0:
                                    init_dur_m += 1
                                    init_dur_s = 0.0

                                with t_c1:
                                    c_start_m = st.number_input(
                                        "Start (min)",
                                        min_value=0,
                                        value=init_start_m,
                                        step=1,
                                        key=f"t3_start_m_{cid}",
                                        help="Start minute of the source video (e.g. 2 for 2m 15s)"
                                    )
                                with t_c2:
                                    c_start_s = st.number_input(
                                        "Start (sec)",
                                        min_value=0.0,
                                        value=float(init_start_s),
                                        step=1.0,
                                        key=f"t3_start_s_{cid}",
                                        help="Start second of the source video (e.g. 15 for 2m 15s)"
                                    )
                                with t_c3:
                                    c_dur_m = st.number_input(
                                        "Duration (min)",
                                        min_value=0,
                                        value=init_dur_m,
                                        step=1,
                                        key=f"t3_dur_m_{cid}",
                                        help="Clip duration in minutes (e.g. 0 min for under 60s, 1 min for 60s+)"
                                    )
                                with t_c4:
                                    c_dur_s = st.number_input(
                                        "Duration (sec)",
                                        min_value=0.0,
                                        value=float(init_dur_s),
                                        step=1.0,
                                        key=f"t3_dur_s_{cid}",
                                        help="Clip duration in seconds (e.g. 45 for standard Short)"
                                    )

                                c_start = round(c_start_m * 60.0 + c_start_s, 1)
                                c_dur = round(c_dur_m * 60.0 + c_dur_s, 1)
                                if c_dur < 3.0:
                                    c_dur = 3.0
                                c_end = round(c_start + c_dur, 1)
                                c_out_dur = round(c_dur / c_speed, 1)

                                start_fmt = f"{int(c_start // 60):02d}:{int(c_start % 60):02d}"
                                end_fmt = f"{int(c_end // 60):02d}:{int(c_end % 60):02d}"
                                dur_fmt = f"{int(c_dur // 60):02d}:{int(c_dur % 60):02d}"

                                c["start_time"] = c_start
                                c["duration"] = c_dur
                                c["end_time"] = c_end
                                c["start_formatted"] = start_fmt
                                c["end_formatted"] = end_fmt

                                if c_speed != 1.0:
                                    st.caption(
                                        f"🎯 **Window:** `{start_fmt}` ➔ `{end_fmt}` ({c_start}s ➔ {c_end}s) | "
                                        f"⏱️ **Clip Length:** `{dur_fmt}` ({c_dur}s) | "
                                        f"⚡ **Output Short ({c_speed}x):** `{c_out_dur}s`"
                                    )
                                else:
                                    st.caption(
                                        f"🎯 **Window:** `{start_fmt}` ➔ `{end_fmt}` ({c_start}s ➔ {c_end}s) | "
                                        f"⏱️ **Clip Length:** `{dur_fmt}` ({c_dur}s total)"
                                    )

                                # 4. Watermark Attribution Credit
                                creator_hint = (st.session_state.get("selected_video") or {}).get("channel_title") or "Original Creator"
                                c_wm = st.text_input(
                                    "🏷️ Watermark Overlay",
                                    value=f"Original: @{creator_hint} (CC-BY)",
                                    key=f"t3_wm_{cid}",
                                    help="Bottom-pinned creator watermark."
                                )

                                # 5. On-Screen Captions Editor
                                with st.expander("💬 Edit On-Screen Captions / Subtitles Text", expanded=False):
                                    t3_init_cap = st.session_state.get(f"t3_caps_{cid}", c.get("caption_text", ""))
                                    if t3_init_cap and "WATCH THIS UNBELIEVABLE MOMENT" in t3_init_cap:
                                        t3_init_cap = ""
                                    t3_bcol1, t3_bcol2 = st.columns(2)
                                    with t3_bcol1:
                                        if st.button("🗑️ Clear Bottom Text", key=f"t3_btn_clear_{cid}", help="Remove all bottom text overlays."):
                                            st.session_state[f"t3_caps_{cid}"] = ""
                                            st.rerun()
                                    with t3_bcol2:
                                        if st.button("⚡ Add Pacing Words", key=f"t3_btn_pacing_{cid}", help="Insert sample pacing hook words."):
                                            st.session_state[f"t3_caps_{cid}"] = "WATCH THIS UNBELIEVABLE MOMENT WAIT FOR IT"
                                            st.rerun()
                                    t3_cap_text = st.text_area(
                                        "Captions Text (Words burned on-screen)",
                                        value=t3_init_cap,
                                        key=f"t3_caps_in_{cid}",
                                        height=80,
                                        placeholder="Leave empty for no bottom text on the video.",
                                        help="Edit words to burn into the video. Leave blank for no bottom text."
                                    )
                                    st.session_state[f"t3_caps_{cid}"] = t3_cap_text

                                # 6. Action Buttons
                                btn_c1, btn_c2, btn_c3 = st.columns([1.6, 1.1, 1.1])
                                with btn_c1:
                                    render_this_now = st.button(
                                        "🚀 Render Short (9:16)",
                                        key=f"render_direct_{cid}",
                                        type="primary",
                                        width="stretch",
                                        help="Instantly render 1080x1920 vertical Short with chosen layout, speed, and captions."
                                    )
                                with btn_c2:
                                    if st.button("⭐ Set Active", key=f"set_act_{cid}", width="stretch", help="Set this as the active candidate."):
                                        st.session_state["selected_candidate"] = c
                                        st.rerun()
                                with btn_c3:
                                    if st.button("🎨 Full Editor", key=f"cand_{cid}", width="stretch", help="Open in Tab 4 Auto-Editor."):
                                        st.session_state["selected_candidate"] = c
                                        switch_to_tab(NAV_TABS[3])

                                # 7. Render Execution
                                if render_this_now:
                                    cand_pbar = st.progress(0, text=f"Rendering vertical 9:16 Short #{cid} ({c_speed}x speed)...")
                                    def on_cand_progress(pct, msg):
                                        cand_pbar.progress(int(pct), text=msg)

                                    try:
                                        clean_t3_caps = t3_cap_text.strip() if t3_cap_text else ""
                                        cand_payload = dict(c)
                                        cand_payload["hook_title"] = c_hook
                                        cand_payload["hook_duration"] = float(c_hook_dur)
                                        cand_payload["start_time"] = c_start
                                        cand_payload["duration"] = c_dur
                                        cand_payload["end_time"] = c_end
                                        cand_payload["speed"] = c_speed
                                        cand_payload["custom_transcript"] = clean_t3_caps
                                        cand_payload["caption_text"] = clean_t3_caps
                                        if not clean_t3_caps:
                                            cand_payload["disable_captions"] = True

                                        v_meta = dict(st.session_state.get("selected_video") or {
                                            "video_id": curr_vid_id,
                                            "channel_title": creator_hint
                                        })
                                        v_meta["channel_title"] = c_wm.replace("Original: @", "").replace(" (CC-BY)", "")

                                        res = render_short_video(
                                            source_video_path=vid_path,
                                            clip_candidate=cand_payload,
                                            video_metadata=v_meta,
                                            layout_mode=c_layout_mode,
                                            subtitle_style=c_subtitle_style,
                                            speed=c_speed,
                                            hook_duration=float(c_hook_dur),
                                            custom_transcript=clean_t3_caps,
                                            progress_callback=on_cand_progress
                                        )
                                        st.session_state[f"rendered_cand_{cid}"] = res
                                        st.session_state["rendered_clip"] = res

                                        # Auto-build export pack zip for this clip immediately
                                        try:
                                            create_export_pack(res.get("clip_db_id", cid), video_id=curr_vid_id)
                                        except Exception:
                                            pass

                                        st.success(f"🎉 Short #{cid} successfully rendered and saved to Studio!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Render failed: {str(e)}")

                                # 8. Downloads & Export Pack Handler
                                if cand_is_rendered:
                                    st.divider()
                                    st.markdown(f"##### 📥 Download Final Video & Assets")
                                    
                                    # Direct MP4 Download
                                    cand_mp4_path = os.path.join(os.path.dirname(vid_path), f"{curr_vid_id}_short_clip_{cid}.mp4")
                                    if os.path.exists(cand_mp4_path):
                                        c_sz_mb = os.path.getsize(cand_mp4_path) / (1024 * 1024)
                                        st.download_button(
                                            label=f"📥 Download Final Short (.mp4) ({c_sz_mb:.1f} MB)",
                                            data=make_file_downloader(cand_mp4_path),
                                            file_name=f"{curr_vid_id}_short_clip_{cid}.mp4",
                                            mime="video/mp4",
                                            key=f"t3_dl_mp4_{cid}",
                                            type="primary",
                                            width="stretch",
                                            on_click="ignore",
                                            help="Directly download the rendered 1080x1920 vertical MP4 video."
                                        )

                                    st.caption("Or download complete multi-platform package with formatted titles, captions, and attribution:")
                                    pack_zip_name = f"ClipForge_Export_Clip_{clip_db_id}_{curr_vid_id}.zip"
                                    pack_zip_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", pack_zip_name)
                                    if not os.path.exists(pack_zip_path):
                                        alt_name = f"ClipForge_Export_Clip_{cid}_{curr_vid_id}.zip"
                                        alt_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", alt_name)
                                        if os.path.exists(alt_path):
                                            pack_zip_path = alt_path
                                            pack_zip_name = alt_name

                                    if os.path.exists(pack_zip_path) and os.path.getsize(pack_zip_path) > 0:
                                        pz_sz_mb = os.path.getsize(pack_zip_path) / (1024 * 1024)
                                        z_col1, z_col2 = st.columns([2.2, 1.4])
                                        with z_col1:
                                            st.download_button(
                                                label=f"📦 Download Export Pack (.zip) ({pz_sz_mb:.1f} MB)",
                                                data=make_file_downloader(pack_zip_path),
                                                file_name=pack_zip_name,
                                                mime="application/zip",
                                                key=f"t3_dl_zip_{cid}",
                                                width="stretch",
                                                on_click="ignore"
                                            )
                                        with z_col2:
                                            if st.button("🔄 Re-bundle .zip", key=f"t3_rezip_{cid}", width="stretch"):
                                                with st.spinner("Re-bundling export pack..."):
                                                    try:
                                                        pack_res = create_export_pack(clip_db_id, video_id=curr_vid_id)
                                                        st.success(f"Export Pack re-generated ({pack_res['zip_size_mb']} MB)!")
                                                        st.rerun()
                                                    except Exception as ez:
                                                        st.error(f"Failed to regenerate zip: {ez}")
                                    else:
                                        if st.button("📦 Generate Export Pack (.zip)", key=f"t3_genzip_{cid}", type="primary", width="stretch"):
                                            with st.spinner("Bundling vertical MP4, metadata, and attribution texts into .zip..."):
                                                try:
                                                    pack_res = create_export_pack(clip_db_id, video_id=curr_vid_id)
                                                    st.success(f"Export Pack generated ({pack_res['zip_size_mb']} MB)!")
                                                    st.rerun()
                                                except Exception as ez:
                                                    st.error(f"Failed to generate zip: {ez}")

            # ==========================================
            # SECTION 2: ACTIVE SELECTED CANDIDATE
            # ==========================================
            elif "Active Candidate" in t3_section:
                with st.container(border=True):
                    st.markdown(f"### 🎯 Active Candidate Focus: #{sel_cand['clip_id']}")

                    # Quick Switcher Dropdown
                    cand_opts = {
                        c["clip_id"]: f"Candidate #{c['clip_id']} ({c['start_formatted']} ➔ {c['end_formatted']}) - Score: {c['score']}/100 | {c['hook_title']}"
                        for c in candidates
                    }
                    new_active_cid = st.selectbox(
                        "Quick Switch Active Candidate",
                        list(cand_opts.keys()),
                        index=list(cand_opts.keys()).index(sel_cand['clip_id']),
                        format_func=lambda x: cand_opts[x],
                        key="t3_act_switcher"
                    )
                    if new_active_cid != sel_cand['clip_id']:
                        st.session_state["selected_candidate"] = next(c for c in candidates if c["clip_id"] == new_active_cid)
                        st.rerun()

                    act_cid = sel_cand['clip_id']

                    # Pre-sync timing from active inputs if present
                    if f"t3_act_start_m_{act_cid}" in st.session_state and f"t3_act_start_s_{act_cid}" in st.session_state:
                        sel_cand["start_time"] = round(float(st.session_state[f"t3_act_start_m_{act_cid}"]) * 60.0 + float(st.session_state[f"t3_act_start_s_{act_cid}"]), 1)
                    if f"t3_act_dur_m_{act_cid}" in st.session_state and f"t3_act_dur_s_{act_cid}" in st.session_state:
                        sel_cand["duration"] = max(3.0, round(float(st.session_state[f"t3_act_dur_m_{act_cid}"]) * 60.0 + float(st.session_state[f"t3_act_dur_s_{act_cid}"]), 1))
                    sel_cand["end_time"] = round(sel_cand["start_time"] + sel_cand["duration"], 1)
                    sel_cand["start_formatted"] = f"{int(sel_cand['start_time'] // 60):02d}:{int(sel_cand['start_time'] % 60):02d}"
                    sel_cand["end_formatted"] = f"{int(sel_cand['end_time'] // 60):02d}:{int(sel_cand['end_time'] % 60):02d}"

                    act_out_file = disk_rendered_files.get(act_cid) or os.path.join(work_dir, f"{curr_vid_id}_short_clip_{act_cid}.mp4")
                    act_is_rendered = os.path.exists(act_out_file) or (f"rendered_cand_{act_cid}" in st.session_state)
                    matching_act = next((rc for rc in rendered_for_vid if rc.get("file_path") == act_out_file or f"_short_clip_{act_cid}.mp4" in rc.get("file_path", "")), None)
                    act_db_id = matching_act["id"] if matching_act else act_cid

                    act_v1, act_v2 = st.columns([1.8, 2.2])
                    with act_v1:
                        st.markdown(f"##### ▶️ Active Candidate #{act_cid} Source")
                        st.video(vid_path, start_time=int(sel_cand['start_time']), end_time=int(sel_cand['end_time']))
                        st.caption(f"Playing window: **{sel_cand['start_formatted']} ➔ {sel_cand['end_formatted']}** ({sel_cand['duration']}s)")

                        if act_is_rendered and os.path.exists(act_out_file):
                            st.divider()
                            st.markdown(f"##### 📱 Finished 9:16 Vertical Short #{act_cid}")
                            st.video(act_out_file)
                            st.caption("✅ 1080x1920 Vertical Short (Rendered)")

                    with act_v2:
                        st.markdown(f"#### 🔥 `{sel_cand['hook_title']}`")
                        st.markdown(f'<div class="score-badge">Viral Score: {sel_cand["score"]} / 100</div>', unsafe_allow_html=True)
                        st.write(f"💡 **AI Rationale:** {sel_cand['rationale']}")

                        with st.container(border=True):
                            st.markdown("##### 🎬 Auto-Editor Configuration")
                            act_h1, act_h2 = st.columns([2.3, 1.1])
                            with act_h1:
                                act_hook = st.text_input(
                                    "🔥 Hook Title Overlay",
                                    value=sel_cand.get("hook_title", "UNBELIEVABLE MOMENT"),
                                    key="t3_act_hook_in",
                                    help="Bold attention-grabbing title placed in the upper third."
                                )
                            with act_h2:
                                act_hook_dur = st.number_input(
                                    "⏱️ Hook Time (s)",
                                    min_value=0.5,
                                    max_value=None,
                                    value=float(sel_cand.get("hook_duration") or 5.0),
                                    step=0.5,
                                    key="t3_act_hook_dur_in",
                                    help="Overlay duration in seconds for the hook title banner (e.g. 3.0s, 5.0s, 8.0s)."
                                )

                            act_l_col, act_s_col, act_spd_col = st.columns([1.3, 1.3, 1.0])
                            with act_l_col:
                                act_layout_choice = st.selectbox(
                                    "📐 Visual Layout",
                                    [
                                        "🎨 Blurred Background Stack",
                                        "✂️ Smart Center Vertical Crop",
                                        "⬛ Fit Letterbox (Clean Black Bars)"
                                    ],
                                    index=0,
                                    key="t3_act_layout_in"
                                )
                                act_layout_mode = {
                                    "🎨 Blurred Background Stack": "blurred_stack",
                                    "✂️ Smart Center Vertical Crop": "smart_crop",
                                    "⬛ Fit Letterbox (Clean Black Bars)": "fit_letterbox"
                                }.get(act_layout_choice, "blurred_stack")

                            with act_s_col:
                                act_sub_choice = st.selectbox(
                                    "💬 Subtitle Preset",
                                    [
                                        "🟡 Alex Hormozi Bold Yellow",
                                        "⚪ MrBeast Clean White & Gold",
                                        "🔵 Cyber Neon Cyan",
                                        "🚫 None (No Text / Clean Video)"
                                    ],
                                    index=0,
                                    key="t3_act_sub_in",
                                    help="Word-level active animation using faster-whisper timestamps, or select None to render clean video without any text overlays."
                                )
                                act_subtitle_style = {
                                    "🟡 Alex Hormozi Bold Yellow": "hormozi_yellow",
                                    "⚪ MrBeast Clean White & Gold": "beast_white",
                                    "🔵 Cyber Neon Cyan": "neon_cyan",
                                    "🚫 None (No Text / Clean Video)": "none"
                                }.get(act_sub_choice, "hormozi_yellow")
                                if act_subtitle_style == "none":
                                    st.caption("🚫 Clean Video: No captions or text overlays will be added.")

                            with act_spd_col:
                                act_speed_choice = st.selectbox(
                                    "⚡ Playback Speed",
                                    [
                                        "1.0x (Normal)",
                                        "1.25x (1.25x Faster)",
                                        "1.5x (1.5x Speed Up)",
                                        "2.0x (2.0x Double Speed)"
                                    ],
                                    index=0,
                                    key="t3_act_speed_in",
                                    help="Speed up video and audio (with pitch-corrected EBU R128 audio normalization)."
                                )
                                act_speed = {
                                    "1.0x (Normal)": 1.0,
                                    "1.25x (1.25x Faster)": 1.25,
                                    "1.5x (1.5x Speed Up)": 1.5,
                                    "2.0x (2.0x Double Speed)": 2.0
                                }.get(act_speed_choice, 1.0)

                            st.markdown("⏱️ **Timing & Clip Window (Minutes & Seconds)**")
                            at_c1, at_c2, at_c3, at_c4 = st.columns([1.0, 1.0, 1.0, 1.0])

                            init_act_start = float(sel_cand.get("start_time", 0.0))
                            init_act_start_m = int(init_act_start // 60)
                            init_act_start_s = round(init_act_start % 60, 1)
                            if init_act_start_s >= 60.0:
                                init_act_start_m += 1
                                init_act_start_s = 0.0

                            init_act_dur = float(sel_cand.get("duration", 45.0))
                            init_act_dur_m = int(init_act_dur // 60)
                            init_act_dur_s = round(init_act_dur % 60, 1)
                            if init_act_dur_s >= 60.0:
                                init_act_dur_m += 1
                                init_act_dur_s = 0.0

                            with at_c1:
                                act_start_m = st.number_input(
                                    "Start (min)",
                                    min_value=0,
                                    value=init_act_start_m,
                                    step=1,
                                    key=f"t3_act_start_m_{act_cid}",
                                    help="Start minute of the source video (e.g. 2 for 2m 15s)"
                                )
                            with at_c2:
                                act_start_s = st.number_input(
                                    "Start (sec)",
                                    min_value=0.0,
                                    value=float(init_act_start_s),
                                    step=1.0,
                                    key=f"t3_act_start_s_{act_cid}",
                                    help="Start second of the source video (e.g. 15 for 2m 15s)"
                                )
                            with at_c3:
                                act_dur_m = st.number_input(
                                    "Duration (min)",
                                    min_value=0,
                                    value=init_act_dur_m,
                                    step=1,
                                    key=f"t3_act_dur_m_{act_cid}",
                                    help="Clip duration in minutes (e.g. 0 min for under 60s, 1 min for 60s+)"
                                )
                            with at_c4:
                                act_dur_s = st.number_input(
                                    "Duration (sec)",
                                    min_value=0.0,
                                    value=float(init_act_dur_s),
                                    step=1.0,
                                    key=f"t3_act_dur_s_{act_cid}",
                                    help="Clip duration in seconds (e.g. 45 for standard Short)"
                                )

                            act_start = round(act_start_m * 60.0 + act_start_s, 1)
                            act_dur = round(act_dur_m * 60.0 + act_dur_s, 1)
                            if act_dur < 3.0:
                                act_dur = 3.0
                            act_end = round(act_start + act_dur, 1)
                            act_out_dur = round(act_dur / act_speed, 1)

                            act_start_fmt = f"{int(act_start // 60):02d}:{int(act_start % 60):02d}"
                            act_end_fmt = f"{int(act_end // 60):02d}:{int(act_end % 60):02d}"
                            act_dur_fmt = f"{int(act_dur // 60):02d}:{int(act_dur % 60):02d}"

                            sel_cand["start_time"] = act_start
                            sel_cand["duration"] = act_dur
                            sel_cand["end_time"] = act_end
                            sel_cand["start_formatted"] = act_start_fmt
                            sel_cand["end_formatted"] = act_end_fmt

                            if act_speed != 1.0:
                                st.caption(
                                    f"🎯 **Window:** `{act_start_fmt}` ➔ `{act_end_fmt}` ({act_start}s ➔ {act_end}s) | "
                                    f"⏱️ **Clip Length:** `{act_dur_fmt}` ({act_dur}s) | "
                                    f"⚡ **Output Short ({act_speed}x):** `{act_out_dur}s`"
                                )
                            else:
                                st.caption(
                                    f"🎯 **Window:** `{act_start_fmt}` ➔ `{act_end_fmt}` ({act_start}s ➔ {act_end}s) | "
                                    f"⏱️ **Clip Length:** `{act_dur_fmt}` ({act_dur}s total)"
                                )

                            act_creator_hint = (st.session_state.get("selected_video") or {}).get("channel_title") or "Original Creator"
                            act_wm = st.text_input(
                                "🏷️ Watermark Overlay",
                                value=f"Original: @{act_creator_hint} (CC-BY)",
                                key="t3_act_wm_in"
                            )

                            with st.expander("💬 Edit On-Screen Captions / Subtitles Text", expanded=False):
                                act_init_cap = st.session_state.get(f"t3_act_caps_{act_cid}", sel_cand.get("caption_text", ""))
                                if act_init_cap and "WATCH THIS UNBELIEVABLE MOMENT" in act_init_cap:
                                    act_init_cap = ""
                                act_b1, act_b2 = st.columns(2)
                                with act_b1:
                                    if st.button("🗑️ Clear Bottom Text", key="act_btn_clear_caps", help="Remove all bottom text overlays."):
                                        st.session_state[f"t3_act_caps_{act_cid}"] = ""
                                        st.rerun()
                                with act_b2:
                                    if st.button("⚡ Add Pacing Words", key="act_btn_pacing_caps", help="Insert sample pacing hook words."):
                                        st.session_state[f"t3_act_caps_{act_cid}"] = "WATCH THIS UNBELIEVABLE MOMENT WAIT FOR IT"
                                        st.rerun()
                                act_cap_text = st.text_area(
                                    "Captions Text (Words burned on-screen)",
                                    value=act_init_cap,
                                    key="t3_act_caps_in",
                                    height=80,
                                    placeholder="Leave empty for no bottom text on the video.",
                                    help="Edit words to burn into the video. Leave blank for no bottom text."
                                )
                                st.session_state[f"t3_act_caps_{act_cid}"] = act_cap_text

                            a_b1, a_b2 = st.columns(2)
                            with a_b1:
                                render_act_btn = st.button("🚀 Render Short (9:16)", key="t3_act_render_btn", type="primary", width="stretch")
                            with a_b2:
                                if st.button("🎨 Full Editor (Tab 4)", key="t3_open_editor_btn", width="stretch"):
                                    switch_to_tab(NAV_TABS[3])

                            if render_act_btn:
                                act_pbar = st.progress(0, text=f"Rendering vertical 9:16 Short ({act_speed}x speed)...")
                                def on_act_p(pct, msg):
                                    act_pbar.progress(int(pct), text=msg)

                                try:
                                    clean_act_caps = act_cap_text.strip() if act_cap_text else ""
                                    act_payload = dict(sel_cand)
                                    act_payload["hook_title"] = act_hook
                                    act_payload["hook_duration"] = float(act_hook_dur)
                                    act_payload["start_time"] = act_start
                                    act_payload["duration"] = act_dur
                                    act_payload["end_time"] = act_end
                                    act_payload["speed"] = act_speed
                                    act_payload["custom_transcript"] = clean_act_caps
                                    act_payload["caption_text"] = clean_act_caps
                                    if not clean_act_caps:
                                        act_payload["disable_captions"] = True

                                    v_meta_act = dict(st.session_state.get("selected_video") or {"video_id": curr_vid_id, "channel_title": act_creator_hint})
                                    v_meta_act["channel_title"] = act_wm.replace("Original: @", "").replace(" (CC-BY)", "")

                                    res = render_short_video(
                                        source_video_path=vid_path,
                                        clip_candidate=act_payload,
                                        video_metadata=v_meta_act,
                                        layout_mode=act_layout_mode,
                                        subtitle_style=act_subtitle_style,
                                        speed=act_speed,
                                        hook_duration=float(act_hook_dur),
                                        custom_transcript=clean_act_caps,
                                        progress_callback=on_act_p
                                    )
                                    st.session_state[f"rendered_cand_{act_cid}"] = res
                                    st.session_state["rendered_clip"] = res
                                    try:
                                        create_export_pack(res.get("clip_db_id", act_cid), video_id=curr_vid_id)
                                    except Exception:
                                        pass
                                    st.success("Render complete!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Render failed: {str(e)}")

                            if act_is_rendered:
                                st.divider()
                                st.markdown("##### 📥 Download Final Video & Assets")
                                
                                act_mp4_path = os.path.join(os.path.dirname(vid_path), f"{curr_vid_id}_short_clip_{act_cid}.mp4")
                                if os.path.exists(act_mp4_path):
                                    a_sz_mb = os.path.getsize(act_mp4_path) / (1024 * 1024)
                                    st.download_button(
                                        label=f"📥 Download Final Short (.mp4) ({a_sz_mb:.1f} MB)",
                                        data=make_file_downloader(act_mp4_path),
                                        file_name=f"{curr_vid_id}_short_clip_{act_cid}.mp4",
                                        mime="video/mp4",
                                        key="t3_act_dl_mp4_btn",
                                        type="primary",
                                        width="stretch",
                                        on_click="ignore",
                                        help="Directly download the rendered 1080x1920 vertical MP4 video."
                                    )

                                st.caption("Or download complete multi-platform package:")
                                act_zip_name = f"ClipForge_Export_Clip_{act_db_id}_{curr_vid_id}.zip"
                                act_zip_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", act_zip_name)
                                if not os.path.exists(act_zip_path):
                                    alt_act_name = f"ClipForge_Export_Clip_{act_cid}_{curr_vid_id}.zip"
                                    alt_act_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", alt_act_name)
                                    if os.path.exists(alt_act_path):
                                        act_zip_path = alt_act_path
                                        act_zip_name = alt_act_name

                                if os.path.exists(act_zip_path) and os.path.getsize(act_zip_path) > 0:
                                    az_sz_mb = os.path.getsize(act_zip_path) / (1024 * 1024)
                                    az_c1, az_c2 = st.columns([2.2, 1.4])
                                    with az_c1:
                                        st.download_button(
                                            label=f"⬇️ Download Export Pack (.zip) ({az_sz_mb:.1f} MB)",
                                            data=make_file_downloader(act_zip_path),
                                            file_name=act_zip_name,
                                            mime="application/zip",
                                            key="t3_act_dl_zip",
                                            type="primary",
                                            width="stretch",
                                            on_click="ignore"
                                        )
                                    with az_c2:
                                        if st.button("🔄 Re-bundle .zip", key="t3_act_rezip", width="stretch"):
                                            try:
                                                create_export_pack(act_db_id, video_id=curr_vid_id)
                                                st.success("Re-generated!")
                                                st.rerun()
                                            except Exception as ez:
                                                st.error(f"Error: {ez}")
                                else:
                                    if st.button("📦 Generate Export Pack (.zip)", key="t3_act_gen_zip", type="primary", width="stretch"):
                                        try:
                                            pack_res = create_export_pack(act_db_id, video_id=curr_vid_id)
                                            st.success("Export Pack generated!")
                                            st.rerun()
                                        except Exception as ez:
                                            st.error(f"Error: {ez}")

            # ==========================================
            # SECTION 3: RENDERED SHORTS FOR THIS VIDEO
            # ==========================================
            elif "Rendered Shorts" in t3_section:
                if not rendered_for_vid:
                    st.info("ℹ️ No shorts rendered for this video yet. Switch to **'All Detected Candidates'** and click **🚀 Render Short (9:16)**!")
                else:
                    st.success(f"🎉 **{len(rendered_for_vid)} Vertical Shorts Rendered & Ready for Distribution!**")
                    
                    # Master ZIP download button at top
                    master_zip_name = f"ClipForge_All_Shorts_{curr_vid_id}.zip"
                    master_zip_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", master_zip_name)
                    with st.container(border=True):
                        s3_c1, s3_c2 = st.columns([2.5, 1.5])
                        with s3_c1:
                            st.markdown("#### 📦 Master Batch Export Archive")
                            st.caption("Contains all rendered vertical Shorts MP4 files, captions for YouTube/TikTok/Instagram, attribution text, and manifest.")
                        with s3_c2:
                            if os.path.exists(master_zip_path) and os.path.getsize(master_zip_path) > 0:
                                mz_size_mb = os.path.getsize(master_zip_path) / (1024 * 1024)
                                s3_b1, s3_b2 = st.columns([3.0, 1.2])
                                with s3_b1:
                                    st.download_button(
                                        label=f"📦 Download All Shorts (.zip) ({mz_size_mb:.1f} MB)",
                                        data=make_file_downloader(master_zip_path),
                                        file_name=master_zip_name,
                                        mime="application/zip",
                                        key="t3_s3_master_dl",
                                        type="primary",
                                        width="stretch",
                                        on_click="ignore"
                                    )
                                with s3_b2:
                                    if st.button("📂 Open", key="t3_s3_open_folder_btn", help="Open folder in File Explorer", width="stretch"):
                                        open_folder_in_explorer(master_zip_path)
                                        st.toast("📂 Highlighted Master ZIP in File Explorer!")
                            else:
                                if st.button("📦 Build Master ZIP (All Shorts)", key="t3_s3_build_master", type="primary", width="stretch"):
                                    with st.spinner("Bundling all rendered shorts..."):
                                        try:
                                            m_res = create_batch_export_pack(curr_vid_id)
                                            st.success(f"Master ZIP ready ({m_res['zip_size_mb']} MB)!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error: {e}")

                    for r_clip in rendered_for_vid:
                        with st.container(border=True):
                            rc_v1, rc_v2 = st.columns([1.6, 2.4])
                            with rc_v1:
                                st.video(r_clip["file_path"])
                            with rc_v2:
                                st.markdown(f"#### 🏆 Short #{r_clip['id']}: `{r_clip.get('hook_title')}`")
                                st.write(f"⏱️ **Duration:** {r_clip.get('duration', 0):.1f}s | **Status:** `{r_clip.get('status', 'pending')}`")
                                if r_clip.get("caption_text"):
                                    st.caption(f"Captions: \"{r_clip['caption_text']}\"")
                                st.write(f"📁 **File:** `{os.path.basename(r_clip['file_path'])}`")

                                # Export Pack (.zip) Handler for this clip
                                r_zip_name = f"ClipForge_Export_Clip_{r_clip['id']}_{r_clip['video_id']}.zip"
                                r_zip_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", r_zip_name)

                                r_z1, r_z2 = st.columns([2.0, 1.5])
                                with r_z1:
                                    if os.path.exists(r_zip_path) and os.path.getsize(r_zip_path) > 0:
                                        rz_sz_mb = os.path.getsize(r_zip_path) / (1024 * 1024)
                                        st.download_button(
                                            label=f"⬇️ Download Export Pack (.zip) ({rz_sz_mb:.1f} MB)",
                                            data=make_file_downloader(r_zip_path),
                                            file_name=r_zip_name,
                                            mime="application/zip",
                                            key=f"t3_s3_dl_zip_{r_clip['id']}",
                                            type="primary",
                                            width="stretch",
                                            on_click="ignore"
                                        )
                                    else:
                                        if st.button("📦 Generate Export Pack (.zip)", key=f"t3_s3_gen_zip_{r_clip['id']}", width="stretch"):
                                            try:
                                                pack = create_export_pack(r_clip["id"])
                                                st.success("Export pack created!")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"Error: {e}")
                                with r_z2:
                                    if st.button("👉 Review in Studio (Tab 5)", key=f"t3_rev_{r_clip['id']}", width="stretch"):
                                        switch_to_tab(NAV_TABS[4])


# ==============================================================================
# TAB 4: AUTO-EDITOR (Phase 4 Functional)
# ==============================================================================
elif current_tab == NAV_TABS[3]:
    render_phase_header(
        3,
        "🎬 Phase 4: Vertical 9:16 Auto-Editor",
        "AI-powered 1080x1920 vertical video production with word-level Whisper captions, punchy hook cards, and EBU R128 audio normalization."
    )

    sel_cand = st.session_state.get("selected_candidate")
    sel_vid = st.session_state.get("selected_video")
    dl_res = st.session_state.get("downloaded_video") or st.session_state.get("download_result")

    # Discover all available downloaded videos on disk
    dl_root = os.path.join(os.path.dirname(__file__), "downloads")
    available_downloads = []
    if os.path.exists(dl_root):
        for d in os.listdir(dl_root):
            mp4 = os.path.join(dl_root, d, f"{d}_source.mp4")
            if os.path.exists(mp4):
                available_downloads.append({"id": d, "path": mp4})

    # Determine current active video ID
    current_vid_id = None
    if dl_res and dl_res.get("video_id"):
        current_vid_id = dl_res["video_id"]
    elif sel_vid and sel_vid.get("video_id"):
        current_vid_id = sel_vid["video_id"]
    elif available_downloads:
        current_vid_id = available_downloads[0]["id"]

    # Active Video Selector Card
    if available_downloads:
        avail_ids = [x["id"] for x in available_downloads]
        default_idx = avail_ids.index(current_vid_id) if current_vid_id in avail_ids else 0

        with st.container(border=True):
            av_col1, av_col2 = st.columns([2.5, 1.5])
            with av_col1:
                cur_title = sel_vid.get("title") if sel_vid else f"Video ({current_vid_id})"
                cur_creator = sel_vid.get("channel_title") if sel_vid else "Creator"
                st.markdown(f"#### 🎥 Active Source: **{cur_title}**")
                st.caption(f"Creator: **{cur_creator}** | Video ID: `{current_vid_id}`")
            with av_col2:
                selected_choice = st.selectbox(
                    "Switch Video to Edit",
                    avail_ids,
                    index=default_idx,
                    help="Choose which downloaded video to edit into a Short.",
                    key="tab4_switch_video_to_edit"
                )
                if selected_choice != current_vid_id:
                    current_vid_id = selected_choice
                    matched_path = next(x["path"] for x in available_downloads if x["id"] == current_vid_id)
                    c_file = os.path.join(os.path.dirname(matched_path), "credits.json")
                    c_creator = "Original Creator"
                    c_title = f"Video ({current_vid_id})"
                    if os.path.exists(c_file):
                        try:
                            with open(c_file, "r") as cf:
                                c_data = json.load(cf)
                                c_creator = c_data.get("creator", "Original Creator")
                        except Exception:
                            pass
                    st.session_state["downloaded_video"] = {"video_id": current_vid_id, "file_path": matched_path, "title": c_title}
                    st.session_state["selected_video"] = {"video_id": current_vid_id, "title": c_title, "channel_title": c_creator}
                    st.session_state["selected_candidate"] = None
                    st.session_state["rendered_clip"] = None
                    st.session_state["highlight_candidates"] = []
                    cand_cache_file = os.path.join(os.path.dirname(matched_path), "candidates.json")
                    if os.path.exists(cand_cache_file):
                        try:
                            with open(cand_cache_file, "r") as f:
                                st.session_state["highlight_candidates"] = json.load(f)
                        except Exception:
                            pass
                    st.rerun()

        source_file_path = next((x["path"] for x in available_downloads if x["id"] == current_vid_id), None)
    else:
        source_file_path = None
        st.warning("⚠️ No downloaded video found yet. Please discover and download a video in Tab 1 & Tab 2, or paste a link in Tab 3.")

    # Candidate details - synchronize with current video & auto-restore candidates cache
    cands_in_state = st.session_state.get("highlight_candidates", [])
    if not cands_in_state and source_file_path:
        cand_cache_file = os.path.join(os.path.dirname(source_file_path), "candidates.json")
        if os.path.exists(cand_cache_file):
            try:
                with open(cand_cache_file, "r") as f:
                    cands_in_state = json.load(f)
                st.session_state["highlight_candidates"] = cands_in_state
            except Exception:
                pass

    if not sel_cand or sel_cand.get("video_id", current_vid_id) != current_vid_id:
        if cands_in_state:
            sel_cand = cands_in_state[0]
            st.session_state["selected_candidate"] = sel_cand
        else:
            vid_title_hint = (sel_vid.get("title", "HIGHLIGHT MOMENT")[:35]).upper() if sel_vid else "VIRAL HIGHLIGHT MOMENT"
            sel_cand = {
                "clip_id": 1,
                "video_id": current_vid_id,
                "start_time": 0.0,
                "end_time": 45.0,
                "duration": 45.0,
                "score": 90.0,
                "hook_title": vid_title_hint,
                "rationale": "High-velocity momentum clip"
            }

    # Highlight Candidate Switcher in Tab 4 (Access All Moments!)
    if cands_in_state:
        with st.container(border=True):
            st.markdown("#### 🎯 Highlight Candidate Switcher (Access All Detected Moments)")
            st.caption("Switch between any of your detected highlight moments below to preview, customize, and render each Short:")
            
            cand_map = {
                c["clip_id"]: f"Candidate #{c['clip_id']} ({c['start_formatted']} ➔ {c['end_formatted']}) | Score: {c['score']}/100 | Hook: {c['hook_title']}"
                for c in cands_in_state
            }
            
            cur_cid = sel_cand.get("clip_id") if sel_cand and sel_cand.get("clip_id") in cand_map else list(cand_map.keys())[0]
            
            t4_sw1, t4_sw2 = st.columns([3.2, 1.2])
            with t4_sw1:
                chosen_cid = st.selectbox(
                    "Choose Highlight Moment to Edit",
                    list(cand_map.keys()),
                    index=list(cand_map.keys()).index(cur_cid),
                    format_func=lambda x: cand_map[x],
                    key="tab4_moment_select_box"
                )
            with t4_sw2:
                curr_pos = list(cand_map.keys()).index(chosen_cid) + 1
                st.write("")
                st.caption(f"Moment **{curr_pos} of {len(cand_map)}**")
                
            if chosen_cid != sel_cand.get("clip_id"):
                sel_cand = next(c for c in cands_in_state if c["clip_id"] == chosen_cid)
                st.session_state["selected_candidate"] = sel_cand
                st.rerun()

    # Interactive Candidate Source Segment Preview Player
    if source_file_path and os.path.exists(source_file_path):
        t4_cid = sel_cand.get("clip_id", 1)
        # Pre-sync timing from active inputs if present
        if f"t4_start_m_{current_vid_id}_{t4_cid}" in st.session_state and f"t4_start_s_{current_vid_id}_{t4_cid}" in st.session_state:
            sel_cand["start_time"] = round(float(st.session_state[f"t4_start_m_{current_vid_id}_{t4_cid}"]) * 60.0 + float(st.session_state[f"t4_start_s_{current_vid_id}_{t4_cid}"]), 1)
        if f"t4_dur_m_{current_vid_id}_{t4_cid}" in st.session_state and f"t4_dur_s_{current_vid_id}_{t4_cid}" in st.session_state:
            sel_cand["duration"] = max(3.0, round(float(st.session_state[f"t4_dur_m_{current_vid_id}_{t4_cid}"]) * 60.0 + float(st.session_state[f"t4_dur_s_{current_vid_id}_{t4_cid}"]), 1))
        sel_cand["end_time"] = round(sel_cand["start_time"] + sel_cand["duration"], 1)
        sel_cand["start_formatted"] = f"{int(sel_cand['start_time'] // 60):02d}:{int(sel_cand['start_time'] % 60):02d}"
        sel_cand["end_formatted"] = f"{int(sel_cand['end_time'] // 60):02d}:{int(sel_cand['end_time'] % 60):02d}"

        with st.container(border=True):
            st.markdown("#### 🎬 Candidate Segment Playback Preview")
            p_v1, p_v2 = st.columns([1.8, 2.2])
            with p_v1:
                st.video(source_file_path, start_time=int(sel_cand.get("start_time", 0)), end_time=int(sel_cand.get("end_time", 45)))
            with p_v2:
                p_start_sec = float(sel_cand.get('start_time', 0.0))
                p_end_sec = float(sel_cand.get('end_time', 45.0))
                p_dur_sec = float(sel_cand.get('duration', 45.0))
                p_start_fmt = f"{int(p_start_sec // 60):02d}:{int(p_start_sec % 60):02d}"
                p_end_fmt = f"{int(p_end_sec // 60):02d}:{int(p_end_sec % 60):02d}"
                p_dur_fmt = f"{int(p_dur_sec // 60):02d}:{int(p_dur_sec % 60):02d}"

                st.markdown(f"##### Previewing: `{sel_cand.get('hook_title', 'Candidate Segment')}`")
                st.write(f"⏱️ **Window:** `{p_start_fmt}` ➔ `{p_end_fmt}` ({p_start_sec:.1f}s ➔ {p_end_sec:.1f}s)")
                st.write(f"⏳ **Duration:** `{p_dur_fmt}` ({p_dur_sec:.1f} seconds)")
                st.caption("Hit ▶️ on the player to watch this segment. Use the controls below to adjust timing, layout, and caption styles.")

    with st.container(border=True):
        st.markdown("#### ⚙️ Short Configuration & Layout Canvas")
        ec1, ec2 = st.columns([1.5, 2.5])

        with ec1:
            st.markdown("##### 📐 Visual Layout")
            layout_choice = st.radio(
                "Vertical Format (1080x1920)",
                [
                    "🎨 Blurred Background Stack",
                    "✂️ Smart Center Vertical Crop",
                    "⬛ Fit Letterbox (Clean Black Bars)"
                ],
                help="Blurred Stack is recommended for Podcasts, Football, and Gaming because it preserves all graphics without cutting off action."
            )
            layout_key_map = {
                "🎨 Blurred Background Stack": "blurred_stack",
                "✂️ Smart Center Vertical Crop": "smart_crop",
                "⬛ Fit Letterbox (Clean Black Bars)": "fit_letterbox"
            }
            layout_mode = layout_key_map.get(layout_choice, "blurred_stack")

            st.markdown("##### 💬 Caption Style")
            sub_choice = st.radio(
                "Dynamic Subtitle Preset",
                [
                    "🟡 Alex Hormozi Bold Yellow",
                    "⚪ MrBeast Clean White & Gold",
                    "🔵 Cyber Neon Cyan",
                    "🚫 None (No Text / Clean Video)"
                ],
                help="Word-level active animation using faster-whisper timestamps, or select None to render clean video without any text overlays."
            )
            sub_key_map = {
                "🟡 Alex Hormozi Bold Yellow": "hormozi_yellow",
                "⚪ MrBeast Clean White & Gold": "beast_white",
                "🔵 Cyber Neon Cyan": "neon_cyan",
                "🚫 None (No Text / Clean Video)": "none"
            }
            subtitle_style = sub_key_map.get(sub_choice, "hormozi_yellow")
            if subtitle_style == "none":
                st.caption("🚫 Clean Video: No captions or text overlays will be added.")

            st.markdown("##### ⚡ Playback Speed")
            speed_choice = st.radio(
                "Video Speed Multiplier",
                [
                    "1.0x (Normal)",
                    "1.25x (1.25x Faster)",
                    "1.5x (1.5x Speed Up)",
                    "2.0x (2.0x Double Speed)"
                ],
                help="Speed up video and audio (with pitch-corrected EBU R128 audio normalization)."
            )
            speed_key_map = {
                "1.0x (Normal)": 1.0,
                "1.25x (1.25x Faster)": 1.25,
                "1.5x (1.5x Speed Up)": 1.5,
                "2.0x (2.0x Double Speed)": 2.0
            }
            playback_speed = speed_key_map.get(speed_choice, 1.0)

        with ec2:
            st.markdown("##### 🎯 Hook & Timing Settings")
            t4_h1, t4_h2 = st.columns([2.3, 1.1])
            with t4_h1:
                hook_input = st.text_input(
                    "🔥 Hook Title Overlay Text",
                    value=sel_cand.get("hook_title", "UNBELIEVABLE MOMENT"),
                    help="Bold attention-grabbing title placed in the upper third."
                )
            with t4_h2:
                hook_dur_in = st.number_input(
                    "⏱️ Hook Time (s)",
                    min_value=0.5,
                    max_value=None,
                    value=float(sel_cand.get("hook_duration") or 5.0),
                    step=0.5,
                    key="t4_hook_dur_input",
                    help="Hook title overlay duration in seconds (e.g. 3.0s, 5.0s, 10.0s)."
                )
            sel_cand["hook_title"] = hook_input
            sel_cand["hook_duration"] = float(hook_dur_in)

            st.markdown("⏱️ **Timing & Clip Window (Minutes & Seconds)**")
            t4_c1, t4_c2, t4_c3, t4_c4 = st.columns([1.0, 1.0, 1.0, 1.0])

            init_t4_start = float(sel_cand.get("start_time", 0.0))
            init_t4_start_m = int(init_t4_start // 60)
            init_t4_start_s = round(init_t4_start % 60, 1)
            if init_t4_start_s >= 60.0:
                init_t4_start_m += 1
                init_t4_start_s = 0.0

            init_t4_dur = float(sel_cand.get("duration", 45.0))
            init_t4_dur_m = int(init_t4_dur // 60)
            init_t4_dur_s = round(init_t4_dur % 60, 1)
            if init_t4_dur_s >= 60.0:
                init_t4_dur_m += 1
                init_t4_dur_s = 0.0

            with t4_c1:
                start_m_in = st.number_input(
                    "Start (min)",
                    min_value=0,
                    value=init_t4_start_m,
                    step=1,
                    key=f"t4_start_m_{current_vid_id}_{t4_cid}",
                    help="Start minute of the source video (e.g. 2 for 2m 15s)"
                )
            with t4_c2:
                start_s_in = st.number_input(
                    "Start (sec)",
                    min_value=0.0,
                    value=float(init_t4_start_s),
                    step=1.0,
                    key=f"t4_start_s_{current_vid_id}_{t4_cid}",
                    help="Start second of the source video (e.g. 15 for 2m 15s)"
                )
            with t4_c3:
                dur_m_in = st.number_input(
                    "Duration (min)",
                    min_value=0,
                    value=init_t4_dur_m,
                    step=1,
                    key=f"t4_dur_m_{current_vid_id}_{t4_cid}",
                    help="Clip duration in minutes (e.g. 0 min for under 60s, 1 min for 60s+)"
                )
            with t4_c4:
                dur_s_in = st.number_input(
                    "Duration (sec)",
                    min_value=0.0,
                    value=float(init_t4_dur_s),
                    step=1.0,
                    key=f"t4_dur_s_{current_vid_id}_{t4_cid}",
                    help="Clip duration in seconds (e.g. 45 for standard Short)"
                )

            start_in = round(start_m_in * 60.0 + start_s_in, 1)
            dur_in = round(dur_m_in * 60.0 + dur_s_in, 1)
            if dur_in < 3.0:
                dur_in = 3.0
            end_calc = round(start_in + dur_in, 1)
            out_dur_calc = round(dur_in / playback_speed, 1)

            t4_start_fmt = f"{int(start_in // 60):02d}:{int(start_in % 60):02d}"
            t4_end_fmt = f"{int(end_calc // 60):02d}:{int(end_calc % 60):02d}"
            t4_dur_fmt = f"{int(dur_in // 60):02d}:{int(dur_in % 60):02d}"

            sel_cand["start_time"] = start_in
            sel_cand["duration"] = dur_in
            sel_cand["end_time"] = end_calc
            sel_cand["start_formatted"] = t4_start_fmt
            sel_cand["end_formatted"] = t4_end_fmt

            if playback_speed != 1.0:
                st.caption(
                    f"🎯 **Window:** `{t4_start_fmt}` ➔ `{t4_end_fmt}` ({start_in}s ➔ {end_calc}s) | "
                    f"⏱️ **Clip Length:** `{t4_dur_fmt}` ({dur_in}s) | "
                    f"⚡ **Output Short ({playback_speed}x):** `{out_dur_calc}s`"
                )
            else:
                st.caption(
                    f"🎯 **Window:** `{t4_start_fmt}` ➔ `{t4_end_fmt}` ({start_in}s ➔ {end_calc}s) | "
                    f"⏱️ **Clip Length:** `{t4_dur_fmt}` ({dur_in}s total)"
                )

            creator_credit = st.text_input(
                "Watermark Credit Overlay",
                value=f"Original: @{sel_vid.get('channel_title', 'Creator') if sel_vid else 'Creator'} (CC-BY)"
            )

            # On-Screen Bottom Text / Captions Editor
            with st.expander("💬 Bottom Text Overlay / Captions (Change, Add, or Remove)", expanded=True):
                st.caption(
                    "Control the text displayed on the lower third of the video. "
                    "You can edit the wording, transcribe spoken words from the audio, insert pacing words, or remove bottom text entirely."
                )
                t4_cid = sel_cand.get("clip_id", 1)
                t4_caps_chk_key = f"tab4_caps_enabled_{current_vid_id}_{t4_cid}"
                if t4_caps_chk_key not in st.session_state:
                    st.session_state[t4_caps_chk_key] = True

                t4_caps_enabled = st.toggle(
                    "Show text / captions on the video below",
                    value=st.session_state[t4_caps_chk_key],
                    key=f"t4_toggle_caps_{current_vid_id}_{t4_cid}",
                    help="Turn off to completely eliminate any lower text or subtitles on this video."
                )
                st.session_state[t4_caps_chk_key] = t4_caps_enabled

                t4_saved_caps = st.session_state.get(f"tab4_cap_text_{current_vid_id}_{t4_cid}")
                if t4_saved_caps is None:
                    t4_saved_caps = sel_cand.get("caption_text", "")
                if t4_saved_caps and "WATCH THIS UNBELIEVABLE MOMENT" in t4_saved_caps:
                    t4_saved_caps = ""

                # 3 quick-action buttons: Transcribe, Add Pacing Words, Clear / Remove Text
                t4_b1, t4_b2, t4_b3 = st.columns([1.3, 1.3, 1.4])
                with t4_b1:
                    if st.button("🎙️ Transcribe Audio", key=f"t4_pretranscribe_{t4_cid}", help="Extract spoken words from the video clip audio with Whisper."):
                        with st.spinner("Extracting audio words with Whisper..."):
                            pre_words = transcribe_clip(source_file_path, start_in, dur_in)
                            st.session_state[f"tab4_words_{current_vid_id}_{t4_cid}"] = pre_words
                            if pre_words:
                                t4_saved_caps = " ".join(w["word"] for w in pre_words)
                            else:
                                t4_saved_caps = ""
                                st.info("No spoken dialogue detected in this clip.")
                            st.session_state[f"tab4_cap_text_{current_vid_id}_{t4_cid}"] = t4_saved_caps
                            st.session_state[t4_caps_chk_key] = True
                            st.rerun()
                with t4_b2:
                    if st.button("⚡ Add Pacing Words", key=f"t4_pacing_{t4_cid}", help="Insert sample pacing hook words if you want them on the video."):
                        st.session_state[f"tab4_cap_text_{current_vid_id}_{t4_cid}"] = "WATCH THIS UNBELIEVABLE MOMENT WAIT FOR IT"
                        st.session_state.pop(f"tab4_words_{current_vid_id}_{t4_cid}", None)
                        st.session_state[t4_caps_chk_key] = True
                        st.rerun()
                with t4_b3:
                    if st.button("🗑️ Remove / Clear Text", key=f"t4_clear_{t4_cid}", help="Remove all text so no words appear on the video below."):
                        st.session_state[f"tab4_cap_text_{current_vid_id}_{t4_cid}"] = ""
                        st.session_state[f"tab4_words_{current_vid_id}_{t4_cid}"] = []
                        st.session_state[t4_caps_chk_key] = False
                        st.rerun()

                if t4_caps_enabled:
                    t4_edited_caps = st.text_area(
                        "Bottom On-Screen Text (Burned onto video)",
                        value=t4_saved_caps,
                        height=90,
                        key=f"t4_cap_textarea_{t4_cid}",
                        placeholder="Type any words here to burn onto the lower video, or click 'Remove / Clear Text' to leave empty.",
                        help="Edit any words here before rendering. Word timestamps will automatically align across the clip!"
                    )
                    st.session_state[f"tab4_cap_text_{current_vid_id}_{t4_cid}"] = t4_edited_caps
                    if t4_edited_caps.strip():
                        w_cnt = len(t4_edited_caps.strip().split())
                        st.caption(f"✍️ **{w_cnt} words** will be animated on the lower third of the video.")
                    else:
                        st.caption("ℹ️ Text is empty: **No text will appear on the video below.**")
                else:
                    t4_edited_caps = ""
                    st.session_state[f"tab4_cap_text_{current_vid_id}_{t4_cid}"] = ""
                    st.session_state[f"tab4_words_{current_vid_id}_{t4_cid}"] = []
                    st.info("🚫 **Bottom text overlay is turned off.** The video will render completely clean at the bottom.")

            r_c1, r_c2, r_c3 = st.columns([2.4, 1.0, 1.0])
            with r_c1:
                render_btn = st.button("🚀 Render 9:16 Vertical Short (1080x1920)", type="primary", width="stretch", disabled=not source_file_path)
            with r_c2:
                if st.button("⬅️ Back to Phase 3", key="t4_bottom_back", help="Navigate back to Phase 3 Highlight Detection", width="stretch"):
                    switch_to_tab(NAV_TABS[2])
            with r_c3:
                if st.button("🔄 Clean Slate", key="t4_bottom_hard_refresh", help="Discard all editor configurations and restart Phase 4 cleanly", width="stretch"):
                    hard_refresh_phase(3)

    # Render Execution
    if render_btn and source_file_path:
        render_pbar = st.progress(0, text="Initializing render engine...")
        render_status = st.empty()

        def on_render_progress(pct: float, msg: str):
            render_pbar.progress(int(pct), text=msg)
            render_status.caption(f"⚡ Status: {msg}")

        try:
            with st.spinner("Processing video, formatting layout, and rendering short..."):
                v_meta = sel_vid or {"video_id": sel_cand.get("video_id", "clip"), "channel_title": "Creator"}
                v_meta["channel_title"] = creator_credit.replace("Original: @", "").replace(" (CC-BY)", "")
                
                if not t4_caps_enabled or not t4_edited_caps.strip():
                    sel_cand["custom_transcript"] = ""
                    sel_cand["caption_text"] = ""
                    sel_cand["words"] = []
                    sel_cand["disable_captions"] = True
                    pass_transcript = ""
                    pass_words = []
                else:
                    sel_cand["custom_transcript"] = t4_edited_caps.strip()
                    sel_cand["caption_text"] = t4_edited_caps.strip()
                    sel_cand["disable_captions"] = False
                    pass_transcript = t4_edited_caps.strip()
                    pass_words = st.session_state.get(f"tab4_words_{current_vid_id}_{t4_cid}")

                render_res = render_short_video(
                    source_video_path=source_file_path,
                    clip_candidate=sel_cand,
                    video_metadata=v_meta,
                    layout_mode=layout_mode,
                    subtitle_style=subtitle_style,
                    speed=playback_speed,
                    hook_duration=float(hook_dur_in),
                    custom_transcript=pass_transcript,
                    custom_words=pass_words,
                    progress_callback=on_render_progress
                )
                st.session_state["rendered_clip"] = render_res
                st.success("🎉 Short rendered successfully in full 1080x1920 vertical resolution!")
        except Exception as e:
            st.error(f"Render failed: {str(e)}")

    # Display All Rendered Shorts for Active Video
    all_rendered_for_vid = [c for c in get_clips(video_id=current_vid_id) if os.path.exists(c.get("file_path", ""))]

    if all_rendered_for_vid:
        st.divider()
        t4_h1, t4_h2, t4_h3 = st.columns([1.9, 2.1, 1.0])
        with t4_h1:
            st.markdown(f"### 📱 Rendered Shorts for this Video ({len(all_rendered_for_vid)} Ready)")
            st.caption("All vertical 1080x1920 Shorts produced from your detected candidates for this video:")
        with t4_h2:
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            t4_mz_name = f"ClipForge_All_Shorts_{current_vid_id}.zip"
            t4_mz_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", t4_mz_name)
            
            if os.path.exists(t4_mz_path) and os.path.getsize(t4_mz_path) > 0:
                t4_mz_sz = os.path.getsize(t4_mz_path) / (1024 * 1024)
                z_b1, z_b2 = st.columns([3.0, 1.2])
                with z_b1:
                    st.download_button(
                        label=f"📦 Download All ({len(all_rendered_for_vid)}) ZIP ({t4_mz_sz:.1f} MB)",
                        data=make_file_downloader(t4_mz_path),
                        file_name=t4_mz_name,
                        mime="application/zip",
                        key="t4_master_zip_dl_btn",
                        type="primary",
                        width="stretch",
                        on_click="ignore",
                        help="Download master archive containing all 5 rendered Shorts and platform export packs."
                    )
                with z_b2:
                    if st.button("📂 Open", key="t4_open_folder_master_btn", help="Open export pack folder in Windows File Explorer", width="stretch"):
                        open_folder_in_explorer(t4_mz_path)
                        st.toast("📂 Highlighted Master ZIP in File Explorer!")
            else:
                if st.button(f"📦 Download All ({len(all_rendered_for_vid)}) ZIP", key="t4_build_master_zip_btn", type="primary", width="stretch", help="Bundle all rendered shorts and export packs into master zip"):
                    with st.spinner("Bundling all rendered shorts and export packs into master zip..."):
                        try:
                            m_res = create_batch_export_pack(current_vid_id)
                            st.toast(f"📦 Master ZIP created ({m_res['zip_size_mb']} MB)!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to create Master ZIP: {e}")
        with t4_h3:
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            with st.popover(f"🗑️ Delete All ({len(all_rendered_for_vid)})", help="Delete all rendered shorts for this video"):
                st.markdown(f"##### ⚠️ Delete All {len(all_rendered_for_vid)} Shorts?")
                st.write(f"This will permanently delete all **{len(all_rendered_for_vid)}** rendered shorts for this video from the studio.")
                if st.button(f"🚨 Confirm Delete All ({len(all_rendered_for_vid)})", type="primary", key="confirm_delete_all_tab4_btn", width="stretch"):
                    for rc in list(all_rendered_for_vid):
                        delete_clip(rc["id"])
                        fp = rc.get("file_path")
                        if fp and os.path.exists(fp):
                            try:
                                os.remove(fp)
                            except Exception:
                                pass
                    st.session_state["rendered_clip"] = None
                    st.toast(f"🗑️ Successfully deleted all {len(all_rendered_for_vid)} rendered shorts!")
                    st.rerun()

        for idx, r_clip in enumerate(all_rendered_for_vid):
            with st.container(border=True):
                v_col1, v_col2 = st.columns([1.6, 2.4])
                
                with v_col1:
                    st.video(r_clip["file_path"])
                
                with v_col2:
                    st.markdown(f"#### 🏆 Short #{r_clip['id']}: `{r_clip.get('hook_title')}`")
                    r_dur_val = float(r_clip.get('duration', 0) or 0)
                    r_dur_fmt = f"{int(r_dur_val // 60):02d}:{int(r_dur_val % 60):02d}"
                    st.write(f"⏱️ **Duration:** `{r_dur_fmt}` ({r_dur_val:.1f}s) | 🎯 **Hook Time:** {r_clip.get('hook_duration', 5.0)}s | **Status:** `{r_clip.get('status', 'pending')}`")
                    st.write(f"📐 **Resolution:** 1080 x 1920 (Vertical 9:16 @ 30fps)")
                    st.write(f"🔊 **Audio Normalization:** EBU R128 (-14 LUFS)")
                    if r_clip.get("caption_text"):
                        st.caption(f"Captions snippet: \"{r_clip['caption_text']}\"")
                    st.write(f"📂 **File:** `{os.path.basename(r_clip['file_path'])}`")

                    # Direct MP4 Download Button
                    if os.path.exists(r_clip["file_path"]):
                        rf_sz_mb = os.path.getsize(r_clip["file_path"]) / (1024 * 1024)
                        st.download_button(
                            label=f"📥 Download Final Short (.mp4) ({rf_sz_mb:.1f} MB)",
                            data=make_file_downloader(r_clip["file_path"]),
                            file_name=os.path.basename(r_clip["file_path"]),
                            mime="video/mp4",
                            key=f"t4_dl_mp4_{r_clip['id']}",
                            type="primary",
                            width="stretch",
                            on_click="ignore",
                            help="Directly download this 1080x1920 vertical MP4 video."
                        )
                    
                    t4_btn1, t4_btn2 = st.columns(2)
                    with t4_btn1:
                        if st.button("👉 Review in Studio (Tab 5)", key=f"t4_rev_short_{r_clip['id']}", width="stretch"):
                            switch_to_tab(NAV_TABS[4])
                    with t4_btn2:
                        if st.button("📦 Export Pack (Tab 6)", key=f"t4_exp_short_{r_clip['id']}", width="stretch"):
                            switch_to_tab(NAV_TABS[5])


# ==============================================================================
# TAB 5: REVIEW & APPROVE (Phase 5 Functional)
# ==============================================================================
elif current_tab == NAV_TABS[4]:
    render_phase_header(
        4,
        "👁️ Phase 5: Interactive Review Studio",
        "Inspect rendered vertical Shorts, fine-tune on-screen captions, and approve clips for cross-platform distribution."
    )

    db_clips = get_clips()
    
    if not db_clips:
        st.info("No rendered clips in the studio yet. You can render highlight moments directly from Tab 3 or customize them in Tab 4!")
        g_c1, g_c2 = st.columns(2)
        with g_c1:
            if st.button("✂️ Go to AI Highlights (Tab 3)", key="tab5_to_tab3", type="primary", width="stretch"):
                switch_to_tab(NAV_TABS[2])
        with g_c2:
            if st.button("🎬 Go to Auto-Editor (Tab 4)", key="tab5_to_tab4", width="stretch"):
                switch_to_tab(NAV_TABS[3])
    else:
        # Overview stats
        total_clips = len(db_clips)
        approved_clips = [c for c in db_clips if c.get("status") == "approved"]
        pending_clips = [c for c in db_clips if c.get("status") == "pending"]
        published_clips = [c for c in db_clips if c.get("status") == "published"]

        st_m1, st_m2, st_m3, st_m4 = st.columns(4)
        st_m1.metric("Total Shorts Rendered", total_clips)
        st_m2.metric("Pending Review", len(pending_clips))
        st_m3.metric("Approved for Publishing", len(approved_clips))
        st_m4.metric("Published", len(published_clips))

        st.divider()

        # Filter selector & Delete All Action Row
        filt_col, act_col = st.columns([3.3, 1.5])
        with filt_col:
            filter_status = st.radio("Filter Clips", ["All", "Pending Review", "Approved", "Published"], horizontal=True)
            filtered_clips = db_clips
            if filter_status == "Pending Review":
                filtered_clips = pending_clips
            elif filter_status == "Approved":
                filtered_clips = approved_clips
            elif filter_status == "Published":
                filtered_clips = published_clips

        with act_col:
            st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
            del_count = len(filtered_clips)
            if del_count > 0:
                with st.popover(f"🗑️ Delete All ({del_count} Shorts)", help="Delete all shorts currently showing up on this page"):
                    st.markdown(f"##### ⚠️ Delete All {del_count} Shorts?")
                    st.write(f"This will permanently delete all **{del_count}** shorts showing up on this page from the database and remove their generated files.")
                    if st.button(f"🚨 Yes, Delete All ({del_count})", type="primary", key="confirm_delete_all_phase5_btn", width="stretch"):
                        for c in list(filtered_clips):
                            delete_clip(c["id"])
                            file_p = c.get("file_path")
                            if file_p and os.path.exists(file_p):
                                try:
                                    os.remove(file_p)
                                except Exception:
                                    pass
                            zip_name = f"ClipForge_Export_Clip_{c['id']}_{c.get('video_id', '')}.zip"
                            zip_p = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", zip_name)
                            if os.path.exists(zip_p):
                                try:
                                    os.remove(zip_p)
                                except Exception:
                                    pass
                            cid = c["id"]
                            for k in [f"t5_hook_in_{cid}", f"t5_hook_dur_in_{cid}", f"t5_wm_in_{cid}", f"t5_style_in_{cid}", f"t5_caps_in_{cid}"]:
                                st.session_state.pop(k, None)
                        st.session_state["rendered_clip"] = None
                        st.toast(f"🗑️ Successfully deleted all {del_count} shorts!")
                        st.rerun()

        if not filtered_clips:
            st.info(f"ℹ️ No shorts currently found matching the '{filter_status}' filter.")

        # Render list of clips
        for clip in filtered_clips:
            c_status = clip.get("status", "pending")
            status_badge = {
                "approved": "✅ APPROVED",
                "pending": "⏳ PENDING REVIEW",
                "published": "🚀 PUBLISHED",
                "rejected": "❌ REJECTED"
            }.get(c_status, "PENDING")

            with st.container(border=True):
                r_vcol, r_meta, r_actions = st.columns([1.6, 2.6, 1.8])

                with r_vcol:
                    clip_file = clip.get("file_path", "")
                    if not (clip_file and os.path.exists(clip_file)):
                        alt_cand = os.path.join(os.path.dirname(__file__), "downloads", clip.get("video_id", ""), os.path.basename(clip_file))
                        if os.path.exists(alt_cand):
                            clip_file = alt_cand
                    if clip_file and os.path.exists(clip_file):
                        st.video(clip_file)
                    else:
                        st.warning("Video file not found.")

                with r_meta:
                    st.markdown(f"#### Short #{clip['id']}: `{clip.get('hook_title', 'Untitled')}`")
                    c_dur_val = float(clip.get('duration', 0) or 0)
                    c_st_val = float(clip.get('start_time', 0) or 0)
                    c_et_val = float(clip.get('end_time', 0) or 0)
                    c_dur_fmt = f"{int(c_dur_val // 60):02d}:{int(c_dur_val % 60):02d}"
                    c_st_fmt = f"{int(c_st_val // 60):02d}:{int(c_st_val % 60):02d}"
                    c_et_fmt = f"{int(c_et_val // 60):02d}:{int(c_et_val % 60):02d}"
                    st.markdown(f"**Status:** `{status_badge}` | **Duration:** `{c_dur_fmt}` ({c_dur_val:.1f}s) | 🎯 **Hook Time:** {clip.get('hook_duration', 5.0):.1f}s")
                    st.write(f"⏱️ **Window:** `{c_st_fmt}` ➔ `{c_et_fmt}` ({c_st_val:.1f}s ➔ {c_et_val:.1f}s)")
                    st.write(f"💡 **AI Rationale:** {clip.get('rationale', 'N/A')}")
                    st.caption(f"Captions snippet: \"{clip.get('caption_text', '')}\"")

                with r_actions:
                    st.markdown("##### Actions")
                    if c_status != "approved" and c_status != "published":
                        if st.button("✅ Approve for Publishing", key=f"appr_{clip['id']}", type="primary", width="stretch"):
                            update_clip_status(clip["id"], "approved")
                            switch_to_tab(NAV_TABS[5])
                    else:
                        if st.button("🚀 View in Publishing Studio (Tab 6)", key=f"view_pub_{clip['id']}", width="stretch"):
                            switch_to_tab(NAV_TABS[5])

                    # Direct MP4 Video Download Button
                    if clip_file and os.path.exists(clip_file):
                        v_sz_mb = os.path.getsize(clip_file) / (1024 * 1024)
                        hook_slug = re.sub(r"[^\w\-]", "_", clip.get("hook_title", "short"))[:35]
                        st.download_button(
                            label=f"📥 Download Final Short (.mp4) ({v_sz_mb:.1f} MB)",
                            data=make_file_downloader(clip_file),
                            file_name=f"{hook_slug}_{clip['id']}.mp4",
                            mime="video/mp4",
                            key=f"dl_mp4_tab5_{clip['id']}",
                            type="primary",
                            width="stretch",
                            on_click="ignore",
                            help="Download the final rendered 1080x1920 vertical MP4 video file directly."
                        )

                    # Export Pack (.zip) Handler with direct Download Button
                    zip_name = f"ClipForge_Export_Clip_{clip['id']}_{clip['video_id']}.zip"
                    zip_path = os.path.join(os.path.dirname(__file__), "downloads", "export_packs", zip_name)

                    if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
                        zp_sz_mb = os.path.getsize(zip_path) / (1024 * 1024)
                        st.download_button(
                            label=f"📦 Download Export Pack ({zp_sz_mb:.1f} MB)",
                            data=make_file_downloader(zip_path),
                            file_name=zip_name,
                            mime="application/zip",
                            key=f"dl_zip_{clip['id']}",
                            width="stretch",
                            on_click="ignore",
                            help="Click to download .zip containing vertical MP4, platform captions, and attribution credits."
                        )
                        if st.button("🔄 Re-generate .zip", key=f"re_exp_{clip['id']}", help="Re-bundle fresh captions and metadata into a new zip file.", width="stretch"):
                            with st.spinner("Re-bundling vertical MP4, metadata, and attribution texts into .zip..."):
                                try:
                                    pack = create_export_pack(clip["id"])
                                    st.session_state["active_export_pack"] = pack
                                    st.success(f"Export Pack re-generated ({pack['zip_size_mb']} MB)!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to generate Export Pack: {e}")
                    else:
                        if st.button("📦 Generate Export Pack (.zip)", key=f"exp_{clip['id']}", width="stretch"):
                            with st.spinner("Bundling vertical MP4, metadata, and attribution texts into .zip..."):
                                try:
                                    pack = create_export_pack(clip["id"])
                                    st.session_state["active_export_pack"] = pack
                                    st.success(f"Export Pack generated ({pack['zip_size_mb']} MB)!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to generate Export Pack: {e}")

                    if st.button("🗑️ Delete Short", key=f"del_{clip['id']}", width="stretch"):
                        delete_clip(clip["id"])
                        st.warning(f"Short #{clip['id']} deleted.")
                        st.rerun()

                # On-Screen Text Editor & Re-render Panel before final download
                with st.expander("✏️ Edit On-Screen Text & Re-Render Before Download", expanded=False):
                    st.caption("Change the on-screen hook title, hook overlay time, watermark credit, captions words, or subtitle styling, then re-render to update the final MP4 and Export Pack.")
                    t5_e1, t5_e2, t5_e3, t5_e4 = st.columns([1.6, 1.0, 1.2, 1.2])
                    with t5_e1:
                        new_t5_hook = st.text_input("🔥 Hook Title", value=clip.get("hook_title", ""), key=f"t5_hook_in_{clip['id']}")
                    with t5_e2:
                        new_t5_hook_dur = st.number_input(
                            "⏱️ Hook Time (s)",
                            min_value=0.5,
                            max_value=None,
                            value=float(clip.get("hook_duration") or 5.0),
                            step=0.5,
                            key=f"t5_hook_dur_in_{clip['id']}",
                            help="Hook title overlay duration in seconds (e.g. 3.0s, 5.0s, 8.0s)."
                        )
                    with t5_e3:
                        new_t5_credit = st.text_input("🏷️ Watermark Overlay", value=f"Original: @{clip.get('video_id', 'Creator')} (CC-BY)", key=f"t5_wm_in_{clip['id']}")
                    with t5_e4:
                        new_t5_style = st.selectbox(
                            "💬 Subtitle Style",
                            ["🟡 Alex Hormozi Bold Yellow", "⚪ MrBeast Clean White", "🔵 Cyber Neon Cyan", "🚫 Clean Video (No Text)"],
                            key=f"t5_style_in_{clip['id']}"
                        )
                        t5_s_map = {
                            "🟡 Alex Hormozi Bold Yellow": "hormozi_yellow",
                            "⚪ MrBeast Clean White": "beast_white",
                            "🔵 Cyber Neon Cyan": "neon_cyan",
                            "🚫 Clean Video (No Text)": "none"
                        }
                        chosen_t5_s = t5_s_map.get(new_t5_style, "hormozi_yellow")

                    t5_c_b1, t5_c_b2 = st.columns(2)
                    with t5_c_b1:
                        if st.button("🗑️ Clear Bottom Text", key=f"t5_clear_btn_{clip['id']}", help="Clear bottom text so no words appear on the video below."):
                            st.session_state[f"t5_caps_in_{clip['id']}"] = ""
                            st.rerun()
                    with t5_c_b2:
                        if st.button("⚡ Add Pacing Words", key=f"t5_pacing_btn_{clip['id']}", help="Insert sample pacing hook words."):
                            st.session_state[f"t5_caps_in_{clip['id']}"] = "WATCH THIS UNBELIEVABLE MOMENT WAIT FOR IT"
                            st.rerun()

                    t5_init_caps = st.session_state.get(f"t5_caps_in_{clip['id']}", clip.get("caption_text", ""))
                    if t5_init_caps and "WATCH THIS UNBELIEVABLE MOMENT" in t5_init_caps:
                        t5_init_caps = ""

                    new_t5_caps = st.text_area(
                        "💬 On-Screen Captions / Bottom Text",
                        value=t5_init_caps,
                        height=90,
                        placeholder="Leave empty for no bottom text overlays on the video.",
                        key=f"t5_caps_in_{clip['id']}",
                        help="Edit the words burned onto the video. Leave blank for no bottom text."
                    )

                    t5_rb1, t5_rb2, t5_rb3 = st.columns([2.4, 1.0, 1.0])
                    with t5_rb1:
                        re_render_btn = st.button("⚡ Apply Changes & Re-Render Short", key=f"t5_apply_btn_{clip['id']}", type="primary", width="stretch")
                    with t5_rb2:
                        if st.button("⬅️ Back to Phase 4", key=f"t5_back_btn_{clip['id']}", help="Navigate back to Phase 4 Auto-Editor", width="stretch"):
                            switch_to_tab(NAV_TABS[3])
                    with t5_rb3:
                        if st.button("🔄 Discard Edits", key=f"t5_discard_btn_{clip['id']}", help="Discard active edits and reset to clean state", width="stretch"):
                            hard_refresh_phase(4)

                    if re_render_btn:
                        src_v_path = os.path.join(os.path.dirname(__file__), "downloads", clip["video_id"], f"{clip['video_id']}_source.mp4")
                        if not os.path.exists(src_v_path):
                            dl_base = os.path.join(os.path.dirname(__file__), "downloads")
                            if os.path.exists(dl_base):
                                for d_item in os.listdir(dl_base):
                                    pot = os.path.join(dl_base, d_item, f"{clip['video_id']}_source.mp4")
                                    if os.path.exists(pot):
                                        src_v_path = pot
                                        break

                        if not os.path.exists(src_v_path):
                            st.error(f"Source video file for '{clip['video_id']}' not found on disk to re-render.")
                        else:
                            with st.spinner("Re-rendering short with updated on-screen text & rock-solid subtitles..."):
                                try:
                                    clean_t5_caps = new_t5_caps.strip() if new_t5_caps else ""
                                    clean_t5_hook = new_t5_hook.strip() if new_t5_hook else ""
                                    cand_t5_payload = {
                                        "clip_id": clip["id"],
                                        "clip_db_id": clip["id"],
                                        "start_time": clip.get("start_time", 0.0),
                                        "duration": clip.get("duration", 45.0),
                                        "end_time": clip.get("end_time", clip.get("start_time", 0.0) + clip.get("duration", 45.0)),
                                        "hook_title": clean_t5_hook,
                                        "hook_duration": float(new_t5_hook_dur),
                                        "caption_text": clean_t5_caps,
                                        "custom_transcript": clean_t5_caps,
                                        "disable_captions": (not bool(clean_t5_caps))
                                    }
                                    v_meta_t5 = {
                                        "video_id": clip["video_id"],
                                        "channel_title": new_t5_credit.replace("Original: @", "").replace(" (CC-BY)", "")
                                    }
                                    res_t5 = render_short_video(
                                        source_video_path=src_v_path,
                                        clip_candidate=cand_t5_payload,
                                        video_metadata=v_meta_t5,
                                        layout_mode="blurred_stack",
                                        subtitle_style=chosen_t5_s,
                                        hook_duration=float(new_t5_hook_dur),
                                        custom_transcript=clean_t5_caps
                                    )
                                    try:
                                        create_export_pack(clip["id"], video_id=clip["video_id"])
                                    except Exception:
                                        pass
                                    st.success("Short successfully re-rendered with your updated on-screen text!")
                                    st.rerun()
                                except Exception as err_t5:
                                    st.error(f"Re-render failed: {err_t5}")


# ==============================================================================
# TAB 6: PUBLISH & SOCIALS (Phase 6 Functional)
# ==============================================================================
elif current_tab == NAV_TABS[5]:
    render_phase_header(
        5,
        "🚀 Phase 6: Publishing & Cross-Posting Studio",
        "Deploy approved vertical Shorts directly to connected socials or download complete multi-platform Export Packs."
    )

    approved_list = [c for c in get_clips() if c.get("status") in ["approved", "published"]]

    if not approved_list:
        st.info("ℹ️ No approved clips ready for publishing yet. Please approve a rendered Short in Tab 5 (Review & Approve).")
    else:
        # Select clip to publish
        clip_opts = {c["id"]: f"Short #{c['id']} - {c.get('hook_title', 'Untitled')} ({c.get('duration', 0):.1f}s)" for c in approved_list}
        active_clip_id = st.selectbox("Select Approved Short to Publish / Export", list(clip_opts.keys()), format_func=lambda x: clip_opts[x])
        active_clip = next(c for c in approved_list if c["id"] == active_clip_id)

        # Active Short Video Player
        with st.container(border=True):
            st.markdown("#### 📱 Approved Short Preview")
            c_p1, c_p2 = st.columns([1.5, 2.5])
            with c_p1:
                clip_file = active_clip.get("file_path", "")
                if not (clip_file and os.path.exists(clip_file)):
                    alt_cand = os.path.join(os.path.dirname(__file__), "downloads", active_clip.get("video_id", ""), os.path.basename(clip_file))
                    if os.path.exists(alt_cand):
                        clip_file = alt_cand
                if clip_file and os.path.exists(clip_file):
                    st.video(clip_file)
                else:
                    st.warning("Video file not found.")
            with c_p2:
                st.markdown(f"### `{active_clip.get('hook_title', 'Untitled Short')}`")
                st.write(f"⏱️ **Duration:** {active_clip.get('duration', 0):.1f}s | **Status:** `{active_clip.get('status', 'approved')}`")
                st.caption(f"Captions: \"{active_clip.get('caption_text', '')}\"")
                st.caption(f"File: `{os.path.basename(clip_file)}`")

        # 1-Click Multi-Platform Export Pack Generator
        with st.container(border=True):
            st.markdown("#### 📦 Multi-Platform Export Pack (.zip)")
            st.caption("Bundles the rendered 1080x1920 MP4, formatted titles, platform character-limited descriptions, hashtags, and attribution license statement.")

            p_col1, p_col2 = st.columns([2.5, 1.5])
            with p_col1:
                st.write(f"Short: **{active_clip.get('hook_title')}**")
                st.write(f"Duration: **{active_clip.get('duration')}s** | File: `{os.path.basename(active_clip.get('file_path', ''))}`")
            with p_col2:
                # Direct MP4 Download Button
                if clip_file and os.path.exists(clip_file):
                    t6_sz_mb = os.path.getsize(clip_file) / (1024 * 1024)
                    st.download_button(
                        label=f"📥 Download Final Short (.mp4) ({t6_sz_mb:.1f} MB)",
                        data=make_file_downloader(clip_file),
                        file_name=os.path.basename(clip_file),
                        mime="video/mp4",
                        key="t6_direct_mp4_dl",
                        type="primary",
                        width="stretch",
                        on_click="ignore"
                    )

                # Build pack
                try:
                    pack = create_export_pack(active_clip["id"])
                    if os.path.exists(pack["zip_path"]):
                        st.download_button(
                            label=f"📦 Download Export Pack ({pack['zip_size_mb']} MB)",
                            data=make_file_downloader(pack["zip_path"]),
                            file_name=pack["zip_filename"],
                            mime="application/zip",
                            key=f"t6_dl_pack_{active_clip['id']}",
                            width="stretch",
                            on_click="ignore"
                        )
                except Exception as e:
                    st.error(f"Failed to generate Export Pack: {e}")

        st.divider()

        # Connected Socials Direct Deployment
        st.markdown("#### 🌐 Direct 1-Click Social Distribution")
        col_p1, col_p2, col_p3 = st.columns(3)

        with col_p1:
            with st.container(border=True):
                st.markdown("#### 🔴 YouTube Shorts")
                yt_acc = socials["youtube"]
                if yt_acc["is_connected"]:
                    st.success(f"Connected: **{yt_acc['account_name'] or 'My Channel'}**")
                    if st.button("🚀 Publish to YouTube Shorts", type="primary", key="pub_yt_btn", width="stretch"):
                        res = publish_short_to_platform(active_clip["id"], "youtube", yt_acc.get("access_token", ""))
                        st.success(f"Successfully deployed Short to YouTube! {res.get('published_url', '')}")
                        st.rerun()
                else:
                    st.warning("Not Connected")
                    st.caption("Attach token in Tab 7 or click below to simulate publishing.")
                    if st.button("Simulate YouTube Publish", key="sim_yt_btn", width="stretch"):
                        res = publish_short_to_platform(active_clip["id"], "youtube")
                        st.success("Short published to local YouTube queue!")
                        st.rerun()

        with col_p2:
            with st.container(border=True):
                st.markdown("#### ⚫ TikTok")
                tt_acc = socials["tiktok"]
                if tt_acc["is_connected"]:
                    st.success(f"Connected: **@{tt_acc['account_handle']}**")
                    if st.button("🚀 Post to TikTok", type="primary", key="pub_tt_btn", width="stretch"):
                        res = publish_short_to_platform(active_clip["id"], "tiktok")
                        st.success("Clip queued to TikTok developer profile!")
                        st.rerun()
                else:
                    st.warning("Not Connected")
                    st.caption("Attach handle in Tab 7.")
                    if st.button("Simulate TikTok Publish", key="sim_tt_btn", width="stretch"):
                        res = publish_short_to_platform(active_clip["id"], "tiktok")
                        st.success("Clip queued to TikTok creator drafts!")
                        st.rerun()

        with col_p3:
            with st.container(border=True):
                st.markdown("#### 🟣 Instagram Reels")
                ig_acc = socials["instagram"]
                if ig_acc["is_connected"]:
                    st.success(f"Connected: **@{ig_acc['account_handle']}**")
                    if st.button("🚀 Publish Reel", type="primary", key="pub_ig_btn", width="stretch"):
                        res = publish_short_to_platform(active_clip["id"], "instagram")
                        st.success("Reel published to Meta Graph API!")
                        st.rerun()
                else:
                    st.warning("Not Connected")
                    st.caption("Attach Meta token in Tab 7.")
                    if st.button("Simulate Reels Publish", key="sim_ig_btn", width="stretch"):
                        res = publish_short_to_platform(active_clip["id"], "instagram")
                        st.success("Reel queued to Instagram profile!")
                        st.rerun()

        # Pre-formatted Copy/Paste Cards for manual uploaders
        st.divider()
        st.markdown("#### 📋 Pre-Formatted Platform Copy-Paste Assets")
        try:
            pack_meta = create_export_pack(active_clip["id"])["metadata"]
            t_yt, t_tt, t_ig = st.tabs(["🔴 YouTube Shorts Copy", "⚫ TikTok Caption Copy", "🟣 Instagram Reels Copy"])
            
            with t_yt:
                st.code(pack_meta["youtube"]["title"], language="text")
                st.caption("Title (Max 100 characters)")
                st.text_area("Description & CC-BY Attribution Credit", value=pack_meta["youtube"]["description"], height=140)

            with t_tt:
                st.text_area("TikTok Caption & Hashtags", value=pack_meta["tiktok"]["caption"], height=120)

            with t_ig:
                st.text_area("Instagram Reels Caption & 15 Hashtags", value=pack_meta["instagram"]["caption"], height=140)
        except Exception:
            pass



# ==============================================================================
# TAB 7: CREATOR ACCOUNT & SOCIALS SETUP
# ==============================================================================
elif current_tab == NAV_TABS[6]:
    render_phase_header(
        6,
        "👤 Phase 7: Creator Profile & Connected Social Accounts",
        "Sign in and link your accounts to automatically distribute Shorts and Reels from ClipForge."
    )
    
    acc_col1, acc_col2 = st.columns([1.5, 2.5])
    
    with acc_col1:
        with st.container(border=True):
            st.markdown("#### 🧑‍🎨 Creator Profile")
            p_name = st.text_input("Creator / Channel Name", value=user_profile.get("name", "Creator Studio"))
            p_email = st.text_input("Email", value=user_profile.get("email", "creator@clipforge.local"))
            p_bio = st.text_area("Bio / Niche", value=user_profile.get("bio", "Autonomous Shorts & Reels Creator"))
            
            if st.button("💾 Save Profile", type="primary", width="stretch"):
                save_user_profile(p_name, p_email, p_bio)
                st.success("Creator profile updated!")
                st.rerun()
                
            st.divider()
            st.markdown("#### 🔑 Free API Keys")
            yt_key = st.text_input("YouTube Data API v3 Key", value=get_api_key(), type="password")
            if yt_key != get_api_key():
                set_setting("YOUTUBE_API_KEY", yt_key.strip())
                st.success("YouTube API Key saved!")
                st.rerun()

            gemini_key = st.text_input("Gemini API Key (Free)", value=get_setting("GEMINI_API_KEY", ""), type="password")
            if gemini_key != get_setting("GEMINI_API_KEY", ""):
                set_setting("GEMINI_API_KEY", gemini_key.strip())
                st.success("Gemini API Key saved!")
                st.rerun()

    with acc_col2:
        with st.container(border=True):
            st.markdown("#### 🔗 Connected Social Accounts")
            st.caption("Link your social profiles to enable automated or 1-click publishing.")
            
            # YouTube Integration Card
            with st.expander("🔴 YouTube Channel (Shorts Direct Publishing)", expanded=True):
                yt_acc = socials["youtube"]
                if yt_acc["is_connected"]:
                    st.success(f"Status: **Connected as {yt_acc['account_name'] or 'Verified Channel'}**")
                    if st.button("Disconnect YouTube", key="disc_yt"):
                        disconnect_social_account("youtube")
                        st.rerun()
                else:
                    yt_name = st.text_input("YouTube Channel Name / Handle", key="yt_in_name", placeholder="@MyShortsChannel")
                    yt_token = st.text_input("OAuth Access Token / Client Secret", key="yt_in_token", type="password", help="Enter OAuth token from Google Cloud Console or client_secrets.json")
                    if st.button("Connect YouTube Channel", type="primary", key="conn_yt"):
                        save_social_account("youtube", yt_name or "YouTube Creator", yt_name, access_token=yt_token)
                        st.success("YouTube Channel successfully attached!")
                        st.rerun()

            # TikTok Integration Card
            with st.expander("⚫ TikTok Account (Shorts & Reels)", expanded=True):
                tt_acc = socials["tiktok"]
                if tt_acc["is_connected"]:
                    st.success(f"Status: **Connected as @{tt_acc['account_handle']}**")
                    if st.button("Disconnect TikTok", key="disc_tt"):
                        disconnect_social_account("tiktok")
                        st.rerun()
                else:
                    tt_handle = st.text_input("TikTok Handle", key="tt_in_handle", placeholder="@my_tiktok")
                    tt_key = st.text_input("TikTok Client Key / Access Token", key="tt_in_token", type="password")
                    if st.button("Connect TikTok Account", type="primary", key="conn_tt"):
                        save_social_account("tiktok", tt_handle, tt_handle, access_token=tt_key)
                        st.success("TikTok account attached!")
                        st.rerun()

            # Instagram Reels Integration Card
            with st.expander("🟣 Instagram Reels (Meta Graph API)", expanded=True):
                ig_acc = socials["instagram"]
                if ig_acc["is_connected"]:
                    st.success(f"Status: **Connected as @{ig_acc['account_handle']}**")
                    if st.button("Disconnect Instagram", key="disc_ig"):
                        disconnect_social_account("instagram")
                        st.rerun()
                else:
                    ig_handle = st.text_input("Instagram Username", key="ig_in_handle", placeholder="@my_insta_reels")
                    ig_token = st.text_input("Meta Graph User Access Token", key="ig_in_token", type="password")
                    if st.button("Connect Instagram Reels", type="primary", key="conn_ig"):
                        save_social_account("instagram", ig_handle, ig_handle, access_token=ig_token)
                        st.success("Instagram account attached!")
                        st.rerun()
