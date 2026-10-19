"""Settings & Creator Profile (Sidebar / Modal)."""

import html
import streamlit as st
from database import (
    get_setting,
    set_setting,
    get_user_profile,
    save_user_profile,
    get_social_accounts,
    save_social_account,
    disconnect_social_account,
    get_allowlist,
    add_to_allowlist,
    remove_from_allowlist,
    get_daily_quota_used,
)
from trends import get_quota_summary
from ui.common import reset_video_state, goto


def render_sidebar():
    st.sidebar.markdown("### Settings & Profile")

    # Quota Meter
    quota = get_quota_summary()
    used = quota.get("used", 0)
    limit = quota.get("limit", 10000)
    pct = min(1.0, max(0.0, used / limit if limit else 0.0))
    st.sidebar.caption(f"YouTube Quota Today: {used:,} / {limit:,} units")
    st.sidebar.progress(pct)

    # Creator Profile Expander
    with st.sidebar.expander("Creator Profile", expanded=False):
        prof = get_user_profile()
        c_name = st.text_input("Creator Name", value=prof.get("name", "ClipForge Creator"), key="sb_prof_name")
        c_bio = st.text_area("Bio / Attribution", value=prof.get("bio", "Transformative clips & commentary"), key="sb_prof_bio")
        if st.button("Save Profile", key="sb_save_prof", width="stretch"):
            save_user_profile(c_name, prof.get("email", ""), c_bio)
            st.toast("Profile saved!")

    # API Keys Expander
    with st.sidebar.expander("API Keys", expanded=False):
        yt_key = st.text_input(
            "YouTube API v3 Key",
            value=get_setting("youtube_api_key", ""),
            type="password",
            help="Required for live trending and search queries.",
        )
        gemini_key = st.text_input(
            "Gemini API Key",
            value=get_setting("gemini_api_key", ""),
            type="password",
            help="For AI viral hook rating pass.",
        )
        if st.button("Save Keys", key="sb_save_keys", width="stretch"):
            set_setting("youtube_api_key", yt_key.strip())
            set_setting("gemini_api_key", gemini_key.strip())
            st.toast("API keys saved!")

    # Connected Platforms
    with st.sidebar.expander("Social Accounts", expanded=False):
        accs = get_social_accounts()
        for plat, label in [("youtube", "YouTube"), ("tiktok", "TikTok"), ("instagram", "Instagram")]:
            connected = (accs.get(plat) or {}).get("is_connected", False)
            handle = (accs.get(plat) or {}).get("account_handle", "")
            if connected:
                st.caption(f"**{label}:** Connected ({html.escape(handle)})")
                if st.button(f"Disconnect {label}", key=f"dc_{plat}", width="stretch"):
                    disconnect_social_account(plat)
                    st.rerun()
            else:
                st.caption(f"**{label}:** Not connected")
                h_in = st.text_input(f"{label} Handle", key=f"conn_h_{plat}", placeholder=f"@{plat}_handle")
                if st.button(f"Connect {label}", key=f"conn_btn_{plat}", width="stretch"):
                    if h_in.strip():
                        save_social_account(plat, label, h_in.strip())
                        st.toast(f"{label} connected!")
                        st.rerun()

    # Channel Allowlist Expander
    with st.sidebar.expander("Rights Allowlist", expanded=False):
        al = get_allowlist()
        st.caption(f"{len(al)} pre-cleared channels")
        new_ch_id = st.text_input("Channel ID", placeholder="UC...", key="sb_al_chid")
        new_ch_nm = st.text_input("Channel Name", placeholder="Creator Name", key="sb_al_chnm")
        if st.button("Add to Allowlist", key="sb_al_add", width="stretch"):
            if new_ch_id.strip() and new_ch_nm.strip():
                add_to_allowlist(new_ch_id.strip(), new_ch_nm.strip(), "Added via settings")
                st.toast("Channel allowlisted!")
                st.rerun()

    st.sidebar.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Clean Slate / Reset Button
    if st.sidebar.button("Start Over (Clean Slate)", width="stretch", help="Reset active clip and start from scratch"):

        reset_video_state()
        goto(0)
