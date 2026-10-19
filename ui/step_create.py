"""Step 3: AI Highlights & Vertical Studio with Reaction Cam."""

import os
import html
import streamlit as st
from ui.theme import section_header, badge, reaction_mock_html
from ui.common import (
    goto,
    fmt_time,
    cache_candidates,
    load_cached_candidates,
    save_reaction_upload,
    LAYOUTS,
    SUB_STYLES,
    SPEEDS,
    REACTION_POSITIONS,
    REACTION_AUDIO,
    PACING_WORDS,
)
from highlights import extract_highlight_candidates, get_video_duration
from editor import render_short_video, generate_pacing_words


def render_step_create():
    section_header(
        "3. AI Highlights & Vertical Studio",
        "Detect high-retention moments, format into 9:16 vertical video, and attach your Reaction Cam.",
    )

    dl_vid = st.session_state.get("downloaded_video")
    if not dl_vid or not os.path.exists(dl_vid.get("file_path", "")):
        with st.container(border=True):
            st.warning("No source video loaded yet. Please select or import a video first.")
            if st.button("Go to Step 2 (Source Video)", type="primary"):
                goto(1)
        return

    source_path = dl_vid["file_path"]
    vid_id = dl_vid.get("video_id", "clip")
    meta = st.session_state.get("selected_video") or dl_vid
    total_dur = get_video_duration(source_path)

    # Active source banner
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1.2, 1.2])
        c1.markdown(f"**Source Video:** {html.escape(meta.get('title', vid_id))}")
        c1.caption(f"Creator: {html.escape(meta.get('channel_title', 'Creator'))} • Duration: {fmt_time(total_dur)}")
        if c2.button("Change Source", width="stretch"):
            goto(1)
        if c3.button("Re-scan AI Highlights", width="stretch"):
            st.session_state["highlight_candidates"] = []
            st.session_state["selected_candidate"] = None
            st.rerun()

    # Load or detect highlight candidates
    candidates = st.session_state.get("highlight_candidates") or load_cached_candidates(source_path)
    if not candidates:
        with st.container(border=True):
            st.markdown("##### Detect Viral Highlights")
            st.write("Scan audio peaks, scene changes, and viral hooks to find the best 30–60s segments.")
            if st.button("Detect Highlights with AI", type="primary", width="stretch"):
                with st.spinner("Analyzing audio energy peaks, visual scene cuts, and viral hook moments..."):
                    candidates = extract_highlight_candidates(source_path, meta.get("title", ""))
                    if candidates:
                        cache_candidates(source_path, candidates)
                        st.session_state["highlight_candidates"] = candidates
                        st.session_state["selected_candidate"] = candidates[0]
                        st.rerun()
                    else:
                        st.error("Highlight extraction did not yield candidates. You can specify a custom clip range below.")

    if not candidates:
        # Fallback candidate so user is never stuck
        candidates = [{
            "clip_id": 1,
            "start_time": 0.0,
            "end_time": min(45.0, total_dur),
            "duration": min(45.0, total_dur),
            "score": 88.0,
            "rationale": "Opening hook sequence",
            "hook_title": "WATCH THIS MOMENT",
            "hook_duration": 5.0,
        }]
        st.session_state["highlight_candidates"] = candidates

    # Set initial selection if not set
    if not st.session_state.get("selected_candidate") and candidates:
        st.session_state["selected_candidate"] = candidates[0]

    sel_cand = st.session_state.get("selected_candidate") or candidates[0]

    # Two-Column Studio Layout
    left_col, right_col = st.columns([1.3, 2.0], gap="medium")

    # ==========================================================================
    # LEFT COLUMN: Candidate Clips List
    # ==========================================================================
    with left_col:
        st.markdown(f"##### Recommended Clips ({len(candidates)})")
        for idx, cand in enumerate(candidates):
            cid = cand.get("clip_id", idx + 1)
            is_active = (sel_cand.get("clip_id") == cid)
            score = cand.get("score", 85)

            with st.container(border=True):
                # Highlight card header
                h_cols = st.columns([2.5, 1])
                h_cols[0].markdown(f"**Clip #{cid}: {html.escape(cand.get('hook_title', 'Highlight')[:26])}**")
                h_cols[1].markdown(f"<div class='cf-score' style='text-align:right;'>{score:.0f}/100</div>", unsafe_allow_html=True)

                st.caption(
                    f"Time: {fmt_time(cand.get('start_time', 0))} - {fmt_time(cand.get('end_time', 45))} "
                    f"({cand.get('duration', 45):.0f}s)"
                )
                if cand.get("rationale"):
                    st.caption(f"_{html.escape(cand['rationale'][:60])}..._")

                btn_type = "primary" if is_active else "secondary"
                btn_label = "Editing This Clip" if is_active else "Select & Edit"
                if st.button(btn_label, key=f"sel_cand_btn_{cid}", type=btn_type, width="stretch"):
                    st.session_state["selected_candidate"] = cand
                    st.rerun()


        # Custom Clip Range (Expandable)
        with st.expander("Custom Time Range", expanded=False):
            st.caption("Override timestamps to trim any custom section of the video.")
            cur_s = float(sel_cand.get("start_time", 0.0))
            cur_e = float(sel_cand.get("end_time", min(cur_s + 45.0, total_dur)))
            cur_s = max(0.0, min(total_dur, cur_s))
            cur_e = max(0.0, min(total_dur, cur_e))

            c_s1, c_s2 = st.columns(2)
            custom_s = c_s1.number_input(
                "Start Time (seconds)",
                min_value=0.0,
                max_value=float(max(0.0, total_dur)),
                value=cur_s,
                step=1.0,
                key="custom_start_sec_input",
            )
            c_s1.caption(f"Start: **{fmt_time(custom_s)}**")

            # Default end time to at least start + 5s if current end is behind
            default_e = cur_e if cur_e > custom_s else min(total_dur, custom_s + 45.0)
            custom_e = c_s2.number_input(
                "End Time (seconds)",
                min_value=0.0,
                max_value=float(max(10.0, total_dur)),
                value=default_e,
                step=1.0,
                key="custom_end_sec_input",
            )
            c_s2.caption(f"End: **{fmt_time(custom_e)}**")

            # Quick Presets for Duration
            st.caption("Quick duration from start:")
            p1, p2, p3 = st.columns(3)
            if p1.button("+30s", width="stretch", key="dur_preset_30s"):
                new_e = min(total_dur, custom_s + 30.0)
                sel_cand["start_time"] = custom_s
                sel_cand["end_time"] = new_e
                sel_cand["duration"] = round(new_e - custom_s, 1)
                st.session_state["selected_candidate"] = sel_cand
                st.rerun()
            if p2.button("+45s (Standard)", width="stretch", key="dur_preset_45s"):
                new_e = min(total_dur, custom_s + 45.0)
                sel_cand["start_time"] = custom_s
                sel_cand["end_time"] = new_e
                sel_cand["duration"] = round(new_e - custom_s, 1)
                st.session_state["selected_candidate"] = sel_cand
                st.rerun()
            if p3.button("+60s (Max)", width="stretch", key="dur_preset_60s"):
                new_e = min(total_dur, custom_s + 60.0)
                sel_cand["start_time"] = custom_s
                sel_cand["end_time"] = new_e
                sel_cand["duration"] = round(new_e - custom_s, 1)
                st.session_state["selected_candidate"] = sel_cand
                st.rerun()

            diff_sec = custom_e - custom_s
            if diff_sec > 0:
                st.caption(f"Selected Duration: **{diff_sec:.1f}s** ({fmt_time(custom_s)} to {fmt_time(custom_e)})")
            else:
                st.warning("End time must be greater than start time.")

            if st.button("Apply Custom Range", type="primary", width="stretch", key="btn_apply_custom_range"):
                final_e = custom_e if custom_e > custom_s else min(total_dur, custom_s + 45.0)
                actual_dur = round(max(3.0, final_e - custom_s), 1)
                sel_cand["start_time"] = custom_s
                sel_cand["end_time"] = final_e
                sel_cand["duration"] = actual_dur
                st.session_state["selected_candidate"] = sel_cand
                st.toast(f"Custom range applied: {fmt_time(custom_s)} - {fmt_time(final_e)} ({actual_dur:.0f}s)")
                st.rerun()


    # ==========================================================================
    # RIGHT COLUMN: 9:16 Editor & Reaction Cam Studio
    # ==========================================================================
    with right_col:
        st.markdown(f"##### Vertical 9:16 Studio (Clip #{sel_cand.get('clip_id', 1)})")

        with st.container(border=True):
            # Source Video Player
            if os.path.exists(source_path):
                st.video(source_path, start_time=int(sel_cand.get("start_time", 0)))

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

            # Core Editor Controls
            col_hk, col_hk_dur = st.columns([2.5, 1.2])
            hook_text = col_hk.text_input(
                "Hook Title Overlay",
                value=sel_cand.get("hook_title", "UNREAL MOMENT"),
                help="Punchy headline burned at the top of the short to capture scrolling viewers.",
            )
            hook_dur = col_hk_dur.slider("Hook Duration", 1.0, 15.0, float(sel_cand.get("hook_duration", 5.0)), 0.5, format="%.1fs")

            col_lay, col_sub, col_spd = st.columns(3)
            layout_label = col_lay.selectbox("Video Layout", list(LAYOUTS.keys()), index=0)
            sub_label = col_sub.selectbox("Captions Style", list(SUB_STYLES.keys()), index=0)
            spd_label = col_spd.selectbox("Speed", list(SPEEDS.keys()), index=0)

            layout_mode = LAYOUTS[layout_label]
            subtitle_style = SUB_STYLES[sub_label]
            speed_val = SPEEDS[spd_label]

            # ------------------------------------------------------------------
            # REACTION CAM PANEL (Picture-in-Picture)
            # ------------------------------------------------------------------
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            use_reaction = st.checkbox(
                "Attach Reaction / Commentary Video (Picture-in-Picture)",
                value=st.session_state.get("use_reaction_cam", False),
                help="Overlay a reaction camera recording of yourself over the short for a personalized, high-engagement touch.",
            )
            st.session_state["use_reaction_cam"] = use_reaction

            reaction_dict = None

            if use_reaction:
                with st.container(border=True):
                    st.markdown("###### Reaction Cam Configuration")
                    st.caption("Upload a video of yourself reacting or commenting to overlay onto this short.")

                    rx_col_left, rx_col_right = st.columns([1.8, 1.2])

                    with rx_col_left:
                        rx_file = st.file_uploader(
                            "Upload Reaction Video (.mp4, .mov, .webm)",
                            type=["mp4", "mov", "webm", "mkv"],
                            key="rx_file_uploader",
                        )
                        if rx_file:
                            saved_rx_path = save_reaction_upload(rx_file)
                            st.session_state["rx_video_path"] = saved_rx_path
                            st.caption(f"Reaction file: `{rx_file.name}` ({rx_file.size / 1024 / 1024:.1f} MB)")

                        # Position Picker (5 positions: 4 corners + bottom strip)
                        st.markdown("**Placement on Frame:**")
                        pos_key = st.selectbox(
                            "Cam Position",
                            options=list(REACTION_POSITIONS.keys()),
                            index=list(REACTION_POSITIONS.keys()).index("bottom_right"),
                            format_func=lambda k: REACTION_POSITIONS[k],
                            label_visibility="collapsed",
                        )

                        # Shape, Size, and Border
                        shape_col, size_col = st.columns(2)
                        cam_shape = shape_col.radio("Shape", ["rounded", "circle"], index=0, format_func=lambda s: "Rounded Box" if s == "rounded" else "Circle", horizontal=True)
                        cam_size = size_col.slider("Cam Size (% width)", min_value=20, max_value=50, value=32, step=2)
                        cam_border = st.checkbox("Accent Border", value=True, help="Crisp purple/white border around your camera")

                        # Audio & Sync
                        st.markdown("**Audio & Sync:**")
                        aud_mode = st.selectbox(
                            "Audio Mode",
                            options=list(REACTION_AUDIO.keys()),
                            index=0,
                            format_func=lambda k: REACTION_AUDIO[k],
                        )

                        aud_c1, aud_c2 = st.columns(2)
                        clip_vol = aud_c1.slider("Clip Volume (when ducked)", 0.0, 1.0, 0.35, 0.05, format="%.2f")
                        sync_off = aud_c2.slider("Timing Offset (seconds)", -5.0, 5.0, 0.0, 0.25, format="%.2fs", help="Adjust if reaction is ahead/behind source audio")

                    with rx_col_right:
                        # Interactive 9:16 Mock Preview
                        st.caption("Live Placement Preview:")
                        mock_html = reaction_mock_html(
                            position=pos_key,
                            size_pct=cam_size,
                            shape=cam_shape,
                            border=cam_border,
                            captions_on=(subtitle_style != "none"),
                        )
                        st.markdown(mock_html, unsafe_allow_html=True)
                        if pos_key.startswith("bottom"):
                            st.caption("Captions automatically move up to keep clear of your cam.")

                    # Build reaction configuration dictionary if path exists
                    active_rx_path = st.session_state.get("rx_video_path")
                    if active_rx_path and os.path.exists(active_rx_path):
                        reaction_dict = {
                            "path": active_rx_path,
                            "position": pos_key,
                            "size_pct": cam_size,
                            "shape": cam_shape,
                            "border": cam_border,
                            "audio_mode": aud_mode,
                            "clip_volume": clip_vol,
                            "offset": sync_off,
                        }
                    else:
                        st.warning("Upload a reaction video above to enable compositing.")

            # ------------------------------------------------------------------
            # ADVANCED OPTIONS (Expandable)
            # ------------------------------------------------------------------
            with st.expander("Advanced Settings (Captions & Transcript)", expanded=False):
                custom_transcript = st.text_area(
                    "Edit On-screen Transcript",
                    value=sel_cand.get("custom_transcript", ""),
                    placeholder="Leave empty to use automatic Whisper transcription, or type words to burn...",
                    help="Custom text will be aligned to word timestamps.",
                )
                gen_pacing = st.checkbox("Insert Pacing Words (e.g. WATCH THIS, WAIT FOR IT)", value=False)

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

            # ------------------------------------------------------------------
            # PRIMARY ACTION: RENDER SHORT VIDEO
            # ------------------------------------------------------------------
            if st.button("Render Vertical Short (1080x1920)", type="primary", width="stretch", key="btn_render_short"):
                # Prepare candidate dictionary
                cand_copy = dict(sel_cand)
                cand_copy["hook_title"] = hook_text.strip()
                cand_copy["hook_duration"] = hook_dur
                cand_copy["speed"] = speed_val

                if gen_pacing and not custom_transcript:
                    cand_copy["words"] = generate_pacing_words(duration=float(cand_copy.get("duration", 45.0)))

                p_bar = st.progress(0.0, text="Initializing render engine...")
                def r_hook(pct, text):
                    p_bar.progress(min(1.0, max(0.01, float(pct) / 100.0)), text=str(text))

                try:
                    render_result = render_short_video(
                        source_video_path=source_path,
                        clip_candidate=cand_copy,
                        video_metadata=meta,
                        layout_mode=layout_mode,
                        subtitle_style=subtitle_style,
                        speed=speed_val,
                        hook_duration=hook_dur,
                        custom_transcript=custom_transcript if custom_transcript.strip() else None,
                        progress_callback=r_hook,
                        reaction=reaction_dict,
                    )

                    if render_result and render_result.get("success"):
                        st.session_state["rendered_clip"] = render_result
                        st.toast("Short rendered successfully! Proceeding to Publish Studio.")
                        goto(3)  # Move to Step 4: Publish
                    else:
                        st.error("Render did not complete successfully.")
                except Exception as e:
                    st.error(f"Render failed: {e}")
