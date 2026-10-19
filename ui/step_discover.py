"""Step 1: Discover Trending Videos & YouTube Search."""

import html
import streamlit as st
from ui.theme import section_header, badge
from ui.common import goto
from trends import (
    fetch_trending_videos,
    search_niche_videos,
    fetch_video_by_url_or_id,
    get_sample_trending_videos,
)


from ui.common import goto, set_active_source, cache_candidates
from rights import approve_and_clear_video, download_cleared_video
from highlights import extract_highlight_candidates

TOPIC_PRESETS = [
    ("🔥 Trending", ""),
    ("⚽ Football", "football highlights skills goals"),
    ("🏏 Cricket", "cricket highlights sixes wickets IPL T20"),
    ("🎬 YouTubers", "mrbeast sidemen viral youtuber challenge"),
    ("🎙️ Streamers", "ishowspeed kai cenat xqc streamer viral reaction"),
    ("🎮 Gaming", "gaming viral moments insane gameplay clutch"),
    ("⚽ Command: FIFA", "FIFA EA FC insane goals skills pack opening"),
    ("🚓 Command: GTA", "GTA 5 GTA 6 RP funny viral moments stunts"),
]


def render_step_discover():
    section_header(
        "1. Discover Trending Content",
        "Find trending videos by category (Football, Cricket, YouTubers, Streamers, Gaming) or specific command (FIFA, GTA, etc.), and approve them to clip high-engagement Shorts.",
    )

    # Topic & Command Presets Bar
    st.caption("Categories & Specific Commands")
    cols = st.columns(len(TOPIC_PRESETS))
    for i, (label, query) in enumerate(TOPIC_PRESETS):
        if cols[i].button(label, key=f"topic_btn_{i}", width="stretch"):
            st.session_state["search_query"] = query
            with st.spinner(f"Fetching {label.lower()} videos..."):
                if query:
                    vids, _ = search_niche_videos(query, region="ALL", cc_only=False, order="viewCount", min_views=50000)
                else:
                    vids, _ = fetch_trending_videos(region="ALL", min_views=50000)
                if not vids:
                    vids = get_sample_trending_videos(keyword=query, min_views=0)
                st.session_state["discovered_videos"] = vids or []
            st.rerun()

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # Search Bar & Filter Controls
    with st.container(border=True):
        sc1, sc2 = st.columns([3.5, 1.2])
        query = sc1.text_input(
            "Search category, specific command (e.g. FIFA, GTA, Cricket) or paste YouTube URL",
            value=st.session_state.get("search_query", ""),
            placeholder="e.g. FIFA, GTA 6, IPL Cricket, MrBeast, IShowSpeed, or https://youtube.com/watch?v=...",
            label_visibility="collapsed",
            key="disc_query_input",
        )
        run_search = sc2.button("Search Videos", type="primary", width="stretch")


        with st.expander("Search Filters", expanded=False):
            fc1, fc2, fc3, fc4 = st.columns(4)
            region = fc1.selectbox("Region", ["ALL", "US", "GB", "IN", "CA", "AU"], index=0)
            order = fc2.selectbox("Order by", ["relevance", "viewCount", "date", "rating"], index=1)
            cc_only = fc3.checkbox("Creative Commons only", value=False)
            min_views = fc4.select_slider(
                "Min views",
                options=[0, 50000, 100000, 250000, 500000, 1000000],
                value=50000,
            )

    if run_search and query.strip():
        st.session_state["search_query"] = query.strip()
        q_clean = query.strip()
        with st.spinner("Searching YouTube..."):
            if "youtube.com" in q_clean or "youtu.be" in q_clean:
                v_meta, err = fetch_video_by_url_or_id(q_clean)
                if v_meta:
                    st.session_state["discovered_videos"] = [v_meta]
                else:
                    vids, _ = search_niche_videos(q_clean, region=region, cc_only=cc_only, order=order, min_views=min_views)
                    st.session_state["discovered_videos"] = vids or []
            else:
                vids, _ = search_niche_videos(q_clean, region=region, cc_only=cc_only, order=order, min_views=min_views)
                if not vids:
                    vids = get_sample_trending_videos(keyword=q_clean, min_views=0)
                st.session_state["discovered_videos"] = vids or []
        st.rerun()

    # Results List
    vids = st.session_state.get("discovered_videos", [])
    if not vids:
        # Load default samples if list is empty
        vids = get_sample_trending_videos(keyword="", min_views=0)
        st.session_state["discovered_videos"] = vids

    st.markdown(f"##### Results ({len(vids)} videos found)")

    # Grid of video cards (2 columns)
    card_cols = st.columns(2)
    for idx, v in enumerate(vids):
        col = card_cols[idx % 2]
        with col:
            with st.container(border=True):
                # Thumbnail
                thumb = v.get("thumbnail_url")
                if thumb:
                    st.image(thumb, use_container_width=True)

                # Title & channel
                title = v.get("title", "Untitled Video")
                channel = v.get("channel_title", "Unknown Channel")
                st.markdown(f"**{html.escape(title[:75])}{'...' if len(title) > 75 else ''}**")
                st.caption(f"By {html.escape(channel)}")

                # Metrics line
                views = v.get("view_count", 0)
                dur = v.get("duration", "N/A")
                score = v.get("score", 0)
                is_cc = v.get("license") == "creativeCommon" or v.get("is_creative_commons") or v.get("is_cc")

                m_html = (
                    f"<div style='display:flex; justify-content:space-between; align-items:center; margin: 6px 0;'>"
                    f"<div>{badge('CC-BY' if is_cc else 'Transformative Ready', 'ok' if is_cc else '')} "
                    f"<span style='font-size:0.8rem; color:var(--muted);'>{views:,} views • {dur}</span></div>"
                    f"<div class='cf-score'>Viral {score}/100</div>"
                    f"</div>"
                )
                st.markdown(m_html, unsafe_allow_html=True)

                # Primary Action Buttons: Step-by-Step OR One-Click Auto-Approve & Extract High-Engagement Sections
                b_c1, b_c2 = st.columns(2)
                if b_c1.button("Use this video", key=f"use_vid_{idx}_{v.get('video_id')}", type="secondary", width="stretch"):
                    st.session_state["selected_video"] = v
                    goto(1)  # Move to Step 2: Source

                if b_c2.button("⚡ Approve & Clip Shorts", key=f"auto_clip_{idx}_{v.get('video_id')}", type="primary", width="stretch"):
                    with st.spinner("Approving rights, downloading & detecting high-engagement sections..."):
                        approved_v = approve_and_clear_video(v, permission_reason="Transformative Fair Use & Commentary")
                        dl_res = download_cleared_video(approved_v)
                        if dl_res and dl_res.get("success"):
                            set_active_source(dl_res, approved_v)
                            cands = extract_highlight_candidates(dl_res["file_path"], approved_v.get("title", ""), approved_v.get("video_id", ""))
                            if cands:
                                cache_candidates(dl_res["file_path"], cands)
                                st.session_state["highlight_candidates"] = cands
                                st.session_state["selected_candidate"] = cands[0]
                            st.toast("Video approved & high-engagement sections ready!")
                            goto(2)  # Jump directly to Step 3: Create Studio
                        else:
                            st.session_state["selected_video"] = approved_v
                            goto(1)

