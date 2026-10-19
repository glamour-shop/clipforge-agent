"""Step 2: Source Video & Rights Clearance."""

import os
import html
import streamlit as st
from ui.theme import section_header, badge
from ui.common import (
    goto,
    list_downloads,
    set_active_source,
    read_credits_creator,
    open_folder_in_explorer,
    DOWNLOADS,
)
from rights import (
    check_rights_clearance,
    approve_and_clear_video,
    download_cleared_video,
    resolve_video_from_url,
    save_local_uploaded_video,
)


def render_step_source():
    section_header(
        "2. Source Video & Rights Clearance",
        "Clear usage rights and import your long-form video via URL, upload, or library.",
    )

    # Tabs for the 3 sourcing methods
    src_tab1, src_tab2, src_tab3 = st.tabs([
        "YouTube URL or Search Pick",
        "Upload Local Video (MP4 / MOV)",
        "Previously Downloaded Library",
    ])

    # --------------------------------------------------------------------------
    # TAB 1: Selected Video or Direct URL
    # --------------------------------------------------------------------------
    with src_tab1:
        sel_vid = st.session_state.get("selected_video")

        # Direct URL input bar if no video chosen or to pick another
        with st.container(border=True):
            st.markdown("##### Enter YouTube Video URL or ID")
            uc1, uc2 = st.columns([3.5, 1.2])
            url_in = uc1.text_input(
                "YouTube Video Link",
                placeholder="https://www.youtube.com/watch?v=... or shorts or video ID",
                label_visibility="collapsed",
                key="source_url_input",
            )
            if uc2.button("Resolve Video", type="secondary", width="stretch"):
                if url_in.strip():
                    with st.spinner("Fetching video metadata..."):
                        resolved_meta, err = resolve_video_from_url(url_in.strip())
                        if resolved_meta:
                            st.session_state["selected_video"] = resolved_meta
                            st.rerun()
                        else:
                            st.error(f"Could not resolve video: {err}")

        # Display currently selected video card
        if sel_vid:
            with st.container(border=True):
                st.markdown("##### Selected Video for Clearance")
                c_left, c_right = st.columns([1.4, 2.6])

                with c_left:
                    thumb = sel_vid.get("thumbnail_url")
                    if thumb:
                        st.image(thumb, use_container_width=True)
                    else:
                        st.markdown("<div style='height:120px; background:var(--bg-2); border-radius:10px;'></div>", unsafe_allow_html=True)

                with c_right:
                    v_title = sel_vid.get("title", "Unknown Title")
                    v_creator = sel_vid.get("channel_title", "Unknown Creator")
                    v_dur = sel_vid.get("duration", "N/A")
                    st.markdown(f"### {html.escape(v_title)}")
                    st.caption(f"Channel: **{html.escape(v_creator)}** • Duration: {v_dur}")

                    # Rights Clearance Status
                    is_cleared, clear_reason = check_rights_clearance(sel_vid)
                    if is_cleared:
                        st.markdown(f"{badge('CLEARED FOR REUSE', 'ok')} <span style='font-size:0.88rem; color:var(--ok);'>{clear_reason}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"{badge('STANDARD LICENSE', 'warn')} <span style='font-size:0.88rem; color:var(--warn);'>{clear_reason}</span>", unsafe_allow_html=True)

                st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

                # Action Button: Download & Proceed
                btn_cols = st.columns([2, 1])
                with btn_cols[0]:
                    download_label = "Download & Go to Create Studio" if is_cleared else "Approve (Fair Use) & Download"
                    if st.button(download_label, type="primary", width="stretch", key="btn_dl_and_proceed"):
                        # If not cleared, auto-approve under fair use
                        video_to_dl = sel_vid
                        if not is_cleared:
                            video_to_dl = approve_and_clear_video(sel_vid, permission_reason="Transformative Fair Use / Commentary")
                            st.session_state["selected_video"] = video_to_dl

                        p_bar = st.progress(0.0, text="Starting high-speed download with yt-dlp...")
                        def dl_hook(pct, speed, eta, text):
                            p_bar.progress(min(1.0, max(0.01, float(pct) / 100.0)), text=str(text))

                        try:
                            dl_res = download_cleared_video(video_to_dl, progress_callback=dl_hook)
                            if dl_res and dl_res.get("success"):
                                set_active_source(dl_res, video_to_dl)
                                st.toast("Video downloaded and ready for editing!")
                                goto(2)  # Go to Step 3: Create
                            else:
                                st.error("Download did not complete. Please verify video link.")
                        except Exception as e:
                            st.error(f"Download failed: {e}")

                with btn_cols[1]:
                    if st.button("Change Video", width="stretch"):
                        st.session_state["selected_video"] = None
                        st.rerun()
        else:
            st.info("No video selected yet. Paste a link above or pick one from Step 1 (Discover).")

    # --------------------------------------------------------------------------
    # TAB 2: Upload Local Video File
    # --------------------------------------------------------------------------
    with src_tab2:
        with st.container(border=True):
            st.markdown("##### Direct Upload")
            st.caption("Upload your own video recording, gameplay, podcast clip, or reaction master (up to 2GB).")
            up_file = st.file_uploader("Select MP4 / MOV file", type=["mp4", "mov", "mkv", "webm"], key="source_file_uploader")

            if up_file is not None:
                st.write(f"File: **{html.escape(up_file.name)}** ({up_file.size / 1024 / 1024:.1f} MB)")
                if st.button("Import & Proceed to Studio", type="primary", width="stretch", key="btn_import_uploaded_file"):
                    p_bar = st.progress(0.0, text="Importing and analyzing video...")
                    def up_hook(pct, text):
                        p_bar.progress(min(1.0, max(0.01, float(pct) / 100.0)), text=str(text))
                    try:
                        dl_res = save_local_uploaded_video(up_file, progress_callback=up_hook)
                        if dl_res and dl_res.get("success"):
                            set_active_source(dl_res)
                            st.toast("Local file imported successfully!")
                            goto(2)

                        else:
                            st.error("Failed to import video file.")
                    except Exception as e:
                        st.error(f"Import error: {e}")

    # --------------------------------------------------------------------------
    # TAB 3: Previously Downloaded Library
    # --------------------------------------------------------------------------
    with src_tab3:
        existing = list_downloads()
        if not existing:
            st.info("No downloaded videos found in your library yet.")
        else:
            fc1, fc2 = st.columns([3, 1])
            search_dl = fc1.text_input(
                "Filter library",
                placeholder="Search downloaded videos by title, creator, or ID...",
                label_visibility="collapsed",
                key="lib_search_filter",
            )
            fc2.caption(f"**{len(existing)}** videos saved on disk")

            filtered = existing
            if search_dl.strip():
                q = search_dl.strip().lower()
                filtered = [
                    v for v in existing
                    if q in str(v.get("title", "")).lower()
                    or q in str(v.get("creator", "")).lower()
                    or q in str(v.get("id", "")).lower()
                    or q in str(v.get("folder_name", "")).lower()
                ]

            if not filtered:
                st.info(f"No downloads matching '{search_dl}'.")
            else:
                for item in filtered:
                    vid_id = item["id"]
                    file_p = item["path"]
                    title = item.get("title") or vid_id
                    creator = item.get("creator") or "Original Creator"
                    file_sz = item.get("file_size_mb", 0)

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1.1, 1.1])
                        with c1:
                            st.markdown(f"**🎬 {html.escape(title)}**")
                            st.caption(f"Channel: **{html.escape(creator)}** • ID: `{vid_id}` • Size: {file_sz:.1f} MB")
                        with c2:
                            if st.button("Reveal Folder", key=f"lib_rev_{vid_id}", width="stretch"):
                                open_folder_in_explorer(file_p)
                        with c3:
                            if st.button("Use This Video", key=f"lib_use_{vid_id}", type="primary", width="stretch"):
                                dl_res = {
                                    "video_id": vid_id,
                                    "file_path": file_p,
                                    "title": title,
                                    "channel_title": creator,
                                    "success": True,
                                }
                                set_active_source(dl_res, {
                                    "title": title,
                                    "video_id": vid_id,
                                    "channel_title": creator,
                                })
                                goto(2)

