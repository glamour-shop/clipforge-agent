"""Step 4: Review, Reaction Cam Overlay & Publish Studio."""

import os
import html
import streamlit as st
from ui.theme import section_header, badge, reaction_mock_html
from ui.common import (
    goto,
    make_file_downloader,
    open_folder_in_explorer,
    save_reaction_upload,
    REACTION_POSITIONS,
    REACTION_AUDIO,
)
from database import get_clips, update_clip_status, delete_clip
from publish import build_platform_metadata, create_export_pack
from editor import apply_reaction_overlay


def render_step_publish():
    section_header(
        "4. Review & Publish Studio",
        "Review your rendered 9:16 vertical shorts, attach reaction overlays, copy social captions, and export.",
    )

    all_clips = get_clips()
    if not all_clips:
        with st.container(border=True):
            st.info("No rendered clips found in your studio library yet.")
            if st.button("Go to Step 3 (Create Shorts)", type="primary"):
                goto(2)
        return

    # Determine currently active clip (latest rendered or chosen from library)
    rendered_info = st.session_state.get("rendered_clip")
    active_clip = None

    if rendered_info and rendered_info.get("clip_db_id"):
        for c in all_clips:
            if c["id"] == rendered_info["clip_db_id"]:
                active_clip = c
                break

    if not active_clip:
        active_clip = all_clips[0]

    # Clip Selector Bar if multiple clips exist
    if len(all_clips) > 1:
        st.markdown(f"##### Library ({len(all_clips)} shorts available)")
        clip_options = {c["id"]: f"Clip #{c['id']} — {c.get('hook_title') or 'Highlight'} ({c.get('duration', 0):.0f}s)" for c in all_clips}
        chosen_id = st.selectbox(
            "Select Short to Review",
            options=list(clip_options.keys()),
            index=list(clip_options.keys()).index(active_clip["id"]),
            format_func=lambda cid: clip_options[cid],
            label_visibility="collapsed",
        )
        active_clip = next(c for c in all_clips if c["id"] == chosen_id)

    short_path = active_clip.get("file_path", "")
    if not os.path.exists(short_path):
        st.error(f"Video file missing on disk: {short_path}")
        return

    # Two columns: Video Player on the left, Publishing & Assets on the right
    pv_col, ps_col = st.columns([1.3, 1.7], gap="medium")

    # ==========================================================================
    # LEFT COLUMN: 9:16 Vertical Video Player
    # ==========================================================================
    with pv_col:
        with st.container(border=True):
            st.video(short_path)

            file_sz = os.path.getsize(short_path) / 1024 / 1024
            dur = active_clip.get("duration", 45)
            status = active_clip.get("status", "pending")

            st.markdown(f"**{html.escape(active_clip.get('hook_title') or 'Vertical Short')}**")
            st.caption(f"Duration: {dur:.1f}s • Size: {file_sz:.1f} MB • {badge(status.upper(), 'ok' if status == 'approved' else 'warn')}", unsafe_allow_html=True)

            # Quick action buttons
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                with open(short_path, "rb") as vf:
                    v_bytes = vf.read()
                st.download_button(
                    "Download MP4",
                    data=v_bytes,
                    file_name=os.path.basename(short_path),
                    mime="video/mp4",
                    type="primary",
                    width="stretch",
                )
            with d_col2:
                if st.button("Reveal in Folder", width="stretch"):
                    open_folder_in_explorer(short_path)

            # Approval Status Toggles
            st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
            stat_c1, stat_c2 = st.columns(2)
            if status != "approved":
                if stat_c1.button("Mark Approved", width="stretch"):
                    update_clip_status(active_clip["id"], "approved")
                    st.rerun()
            else:
                if stat_c1.button("Mark Pending", width="stretch"):
                    update_clip_status(active_clip["id"], "pending")
                    st.rerun()

            if stat_c2.button("Delete Short", type="secondary", width="stretch"):
                delete_clip(active_clip["id"])
                st.session_state["rendered_clip"] = None
                st.toast("Short deleted.")
                st.rerun()


    # ==========================================================================
    # RIGHT COLUMN: Reaction Cam Overlay + Social Media Copy
    # ==========================================================================
    with ps_col:
        # ----------------------------------------------------------------------
        # REACTION CAM OVERLAY (Apply or Modify on Existing Short)
        # ----------------------------------------------------------------------
        with st.expander("Attach Reaction Cam to this Short", expanded=False):
            st.caption("Overlay your webcam or reaction commentary onto this rendered video in seconds without re-processing captions.")
            rx_f = st.file_uploader(
                "Upload reaction video (.mp4, .mov, .webm)",
                type=["mp4", "mov", "webm", "mkv"],
                key=f"post_rx_uploader_{active_clip['id']}",
            )
            rx_path = save_reaction_upload(rx_f) if rx_f else st.session_state.get("rx_video_path")

            if rx_path and os.path.exists(rx_path):
                st.caption(f"Using reaction: `{os.path.basename(rx_path)}`")
                rc1, rc2 = st.columns(2)
                p_choice = rc1.selectbox("Placement", list(REACTION_POSITIONS.keys()), index=3, format_func=lambda k: REACTION_POSITIONS[k], key=f"post_pos_{active_clip['id']}")
                s_choice = rc2.radio("Shape", ["rounded", "circle"], horizontal=True, key=f"post_shp_{active_clip['id']}")

                sz_choice = st.slider("Cam Size (%)", 20, 50, 32, 2, key=f"post_sz_{active_clip['id']}")
                b_choice = st.checkbox("Accent Border", value=True, key=f"post_brd_{active_clip['id']}")

                aud_choice = st.selectbox("Audio Mode", list(REACTION_AUDIO.keys()), index=0, format_func=lambda k: REACTION_AUDIO[k], key=f"post_aud_{active_clip['id']}")
                clip_v = st.slider("Clip Volume when ducked", 0.0, 1.0, 0.35, 0.05, key=f"post_vol_{active_clip['id']}")

                if st.button("Composite Reaction Overlay Now", type="primary", width="stretch", key=f"btn_apply_post_rx_{active_clip['id']}"):
                    with st.spinner("Compositing reaction video onto short with FFmpeg..."):
                        try:
                            new_out = apply_reaction_overlay(
                                short_path=short_path,
                                reaction_path=rx_path,
                                position=p_choice,
                                size_pct=sz_choice,
                                shape=s_choice,
                                border=b_choice,
                                audio_mode=aud_choice,
                                clip_volume=clip_v,
                            )
                            # Overwrite current video with reaction composite
                            os.replace(new_out, short_path)
                            st.toast("Reaction cam added to short successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Overlay failed: {e}")
            else:
                st.info("Upload a video of yourself above to attach a reaction overlay.")

        # ----------------------------------------------------------------------
        # PLATFORM COPY, EDITABLE YOUTUBE POSTING & EXPORT
        # ----------------------------------------------------------------------
        with st.container(border=True):
            st.markdown("##### 🚀 Post Short to YouTube & Multi-Platform Captions")

            orig_meta = {
                "title": active_clip.get("hook_title", "Viral Clip"),
                "channel_title": active_clip.get("creator", "Original Creator"),
            }
            platform_meta = build_platform_metadata(active_clip, orig_meta)

            t_yt, t_tt, t_ig = st.tabs([
                "YouTube Shorts (Direct Post)",
                "TikTok",
                "Instagram Reels",
            ])

            with t_yt:
                yt_title_edit = st.text_input(
                    "YouTube Short Title",
                    value=active_clip.get("custom_title") or platform_meta["youtube"]["title"],
                    key=f"yt_pub_title_{active_clip['id']}",
                )
                yt_hashtags_edit = st.text_input(
                    "Selected Hashtags",
                    value=active_clip.get("hashtags") or platform_meta["youtube"].get("hashtags_str", "#Shorts #viral #trending"),
                    key=f"yt_pub_tags_{active_clip['id']}",
                )
                yt_desc_edit = st.text_area(
                    "Caption / Description",
                    value=active_clip.get("custom_caption") or platform_meta["youtube"]["description"],
                    height=135,
                    key=f"yt_pub_desc_{active_clip['id']}",
                )
                priv_col, post_col = st.columns([1.1, 1.9])
                yt_privacy = priv_col.selectbox(
                    "Visibility",
                    ["public", "unlisted", "private"],
                    index=0,
                    label_visibility="collapsed",
                    key=f"yt_pub_priv_{active_clip['id']}",
                )
                if post_col.button("🚀 Post Short to YouTube Account", type="primary", width="stretch", key=f"btn_yt_post_{active_clip['id']}"):
                    from publish import publish_short_to_platform
                    with st.spinner("Uploading Short to YouTube with selected Title, Caption & Hashtags..."):
                        try:
                            pub_res = publish_short_to_platform(
                                clip_id=active_clip["id"],
                                platform="youtube",
                                custom_title=yt_title_edit,
                                custom_caption=yt_desc_edit,
                                custom_hashtags=yt_hashtags_edit,
                                privacy_status=yt_privacy,
                            )
                            if pub_res and pub_res.get("success"):
                                st.success(pub_res.get("message") or f"Published: {pub_res.get('published_url')}")
                                st.rerun()
                        except Exception as e:
                            st.error(f"YouTube publish failed: {e}")

                if active_clip.get("published_url"):
                    st.caption(f"Published URL: `{active_clip['published_url']}`")

            with t_tt:
                st.markdown("**TikTok Caption:**")
                st.text_area("TT Caption", value=platform_meta["tiktok"]["caption"], height=130, label_visibility="collapsed")

            with t_ig:
                st.markdown("**Instagram Reels Caption:**")
                st.text_area("IG Caption", value=platform_meta["instagram"]["caption"], height=150, label_visibility="collapsed")

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

            # Full Export Pack (.zip)
            if st.button("Generate Complete Export Pack (.ZIP)", type="secondary", width="stretch", key="btn_gen_zip"):
                with st.spinner("Bundling video, captions, and attribution assets into .zip..."):
                    try:
                        pack_res = create_export_pack(active_clip["id"])
                        if pack_res and pack_res.get("zip_path"):
                            st.session_state["latest_zip_path"] = pack_res["zip_path"]
                            st.success(f"Export pack created: {pack_res.get('zip_filename') or os.path.basename(pack_res['zip_path'])}")
                    except Exception as e:
                        st.error(f"Failed to generate export pack: {e}")

            zip_p = st.session_state.get("latest_zip_path")
            if zip_p and os.path.exists(zip_p):
                with open(zip_p, "rb") as zf:
                    z_bytes = zf.read()
                st.download_button(
                    "Download Export Pack (.zip)",
                    data=z_bytes,
                    file_name=os.path.basename(zip_p),
                    mime="application/zip",
                    width="stretch",
                )

