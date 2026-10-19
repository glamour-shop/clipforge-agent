"""Step 5: Autonomous Daily Agent, Category/Command Hunter & Monetization Analytics."""

import os
import html
import streamlit as st
from ui.theme import section_header, badge
from ui.common import goto, LAYOUTS, SUB_STYLES
from database import (
    get_category_performance,
    upsert_category_command,
    toggle_category_command,
    delete_category_command,
    get_agent_runs,
    get_social_accounts,
    save_social_account,
    get_setting,
    set_setting,
)
from agent import (
    get_agent_config,
    save_agent_config,
    run_autonomous_agent_cycle,
    start_background_agent_daemon,
    stop_background_agent_daemon,
    get_daemon_status,
)
from analytics import (
    sync_channel_and_shorts_analytics,
    evaluate_monetization_status,
)
from publish import authorize_youtube_oauth_interactive


def render_step_agent():
    section_header(
        "5. Autonomous Daily Agent & Monetization Growth",
        "Auto-hunt trending categories & specific commands (Football, Cricket, YouTubers, Streamers, Gaming, FIFA, GTA), render copyright-safe Shorts with captions & hooks, auto-post to YouTube, and optimize for YPP monetization.",
    )

    cfg = get_agent_config()
    daemon_stat = get_daemon_status()
    monetization = evaluate_monetization_status()
    snap = monetization["snapshot"]

    # Top Summary Banner
    with st.container(border=True):
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Daily Auto-Agent", "ACTIVE" if daemon_stat["running"] else ("READY" if cfg["enabled"] else "PAUSED"))
        m2.metric("Shorts Posted Today", f"{daemon_stat['posts_today']} / {cfg['daily_posts_limit']}")
        m3.metric("Channel Subscribers", f"{int(snap.get('subscribers', 0)):,}")
        m4.metric("90d Shorts Views", f"{int(snap.get('shorts_views_90d', 0)):,}")
        m5.metric("YPP Monetization", f"{monetization['tier2']['overall_pct']:.1f}%")

    tab_hunt, tab_analytics, tab_categories, tab_account = st.tabs([
        "⚡ Run & Schedule Daily Agent",
        "📈 Channel Analytics & Monetization",
        "🎯 Categories & Specific Commands",
        "🔑 YouTube Account & Run Logs",
    ])

    # ==========================================================================
    # TAB 1: RUN & SCHEDULE DAILY AGENT
    # ==========================================================================
    with tab_hunt:
        col_run, col_sched = st.columns([1.45, 1.15], gap="medium")

        with col_run:
            with st.container(border=True):
                st.markdown("##### ⚡ Launch Autonomous Hunt, Render & YouTube Post")
                st.caption(
                    "The agent will: (1) analyze channel stats, (2) hunt trending videos for your selected category or command, "
                    "(3) approve & download the video, (4) clip the highest-engagement section, "
                    "(5) render 9:16 with captions, hook title & copyright-safe filters, and (6) post to YouTube."
                )

                cats = get_category_performance(enabled_only=False)
                cat_options = ["auto_best"] + [c["category_key"] for c in cats]
                cat_labels = {
                    "auto_best": f"🤖 AI Auto-Select Best Performing Niche (Top: {monetization['top_category']['display_name']})"
                }
                for c in cats:
                    cat_labels[c["category_key"]] = f"{c['display_name']} — Weight: {c['weight_score']:.1f}/100 ({c['query_command']})"

                c_sel1, c_sel2 = st.columns([1.6, 1.4])
                selected_cat_key = c_sel1.selectbox(
                    "Select Category Preset",
                    options=cat_options,
                    format_func=lambda k: cat_labels.get(k, k),
                    key="agent_cat_select",
                )
                specific_cmd = c_sel2.text_input(
                    "Or Specific Command / Game / Topic",
                    placeholder="e.g. FIFA, GTA 6, IPL Cricket, Sidemen, Babar Azam...",
                    help="Overrides the category preset with your exact command.",
                    key="agent_specific_cmd",
                )

                with st.expander("Customize Title, Caption & Hashtags for this Post (Optional)", expanded=False):
                    custom_title = st.text_input(
                        "Custom Short Title (leave blank for AI Hook Title)",
                        placeholder="e.g. UNBELIEVABLE 90TH MINUTE FIFA GOAL 🔥 #Shorts",
                        key="agent_run_title",
                    )
                    custom_hashtags = st.text_input(
                        "Selected Hashtags (space or comma separated)",
                        value=cfg["custom_hashtags_override"],
                        placeholder="e.g. #Shorts #football #cricket #fifa #gta #viral #trending",
                        key="agent_run_hashtags",
                    )
                    custom_caption = st.text_area(
                        "Custom Caption / Description Body",
                        value=cfg["custom_caption_template"],
                        placeholder="Leave blank to auto-generate high-retention caption + creator attribution credit...",
                        height=90,
                        key="agent_run_caption",
                    )

                if st.button(
                    "🚀 Run Full Autonomous Cycle Now (Hunt → Clip → Render → Post)",
                    type="primary",
                    width="stretch",
                    key="btn_run_agent_now",
                ):
                    target_arg = specific_cmd.strip() if specific_cmd.strip() else ("" if selected_cat_key == "auto_best" else selected_cat_key)
                    p_bar = st.progress(0.01, text="Initializing Autonomous Agent...")
                    status_box = st.empty()

                    def _prog(pct: float, msg: str):
                        p_bar.progress(min(1.0, max(0.01, float(pct) / 100.0)), text=msg)
                        status_box.caption(f"🔄 {msg}")

                    res = run_autonomous_agent_cycle(
                        explicit_category_or_command=target_arg,
                        custom_title=custom_title,
                        custom_caption=custom_caption,
                        custom_hashtags=custom_hashtags,
                        progress_callback=_prog,
                        run_type="manual_ui",
                    )
                    if res.get("success"):
                        st.session_state["last_agent_result"] = res
                        st.session_state["rendered_clip"] = res.get("render_result")
                        st.success(
                            f"Autonomous cycle complete! Rendered & published: **{res['publish_result'].get('title')}** "
                            f"({res['publish_result'].get('published_url')})"
                        )
                    else:
                        st.error(f"Agent cycle encountered an issue: {res.get('error')}")

            # Show latest agent result preview if available
            last_res = st.session_state.get("last_agent_result")
            if last_res and last_res.get("success"):
                r_info = last_res.get("render_result") or {}
                p_info = last_res.get("publish_result") or {}
                v_file = r_info.get("file_path", "")
                if v_file and os.path.exists(v_file):
                    with st.container(border=True):
                        st.markdown("##### 🎬 Latest Agent-Rendered & Published Short")
                        pv1, pv2 = st.columns([1.2, 1.8])
                        with pv1:
                            st.video(v_file)
                        with pv2:
                            st.markdown(f"**Title:** `{html.escape(str(p_info.get('title', r_info.get('hook_title', 'Short'))))}`")
                            st.markdown(f"**Category / Command:** `{html.escape(str(last_res.get('category', '')))}`")
                            st.markdown(f"**Hashtags:** `{html.escape(str(p_info.get('hashtags', '#Shorts')))}`")
                            st.markdown(f"**Published URL:** `{html.escape(str(p_info.get('published_url', '')))}`")
                            st.caption("Complete render with burned-in Hook Title, animated word captions, creator watermark & Copyright-Safe transformative framing.")
                            if st.button("Open in Publish Studio (Step 4)", key="btn_agent_goto_pub"):
                                goto(3)

        with col_sched:
            with st.container(border=True):
                st.markdown("##### ⏰ Daily Autonomous Scheduler & Anti-Copyright Config")
                st.caption("Configure how the agent runs automatically every day.")

                en_auto = st.checkbox("Enable Daily Autonomous Posting", value=cfg["enabled"], key="cfg_en_auto")
                daily_lim = st.slider("Daily Shorts Target (Posts / Day)", 1, 6, int(cfg["daily_posts_limit"]), key="cfg_daily_lim")
                post_time = st.text_input("Preferred Daily Run Time (UTC HH:MM)", value=cfg["post_time_utc"], key="cfg_post_time")

                st.markdown("**Render & Anti-Copyright Safeguards:**")
                cp_safe = st.checkbox(
                    "Copyright-Safe Transformative Mode (Recommended)",
                    value=cfg["copyright_safe"],
                    help="Applies 9:16 transformative framing, subtle 1.03x cadence modulation, color contrast enhancement, burned-in Hook & Captions, and creator attribution to prevent copyright claims.",
                    key="cfg_cp_safe",
                )
                m_flip = st.checkbox(
                    "Horizontal Mirror Flip (Extra Visual Transform)",
                    value=cfg["mirror_flip"],
                    key="cfg_m_flip",
                )
                cc_pref = st.checkbox(
                    "Strictly Search Creative Commons (CC-BY) Only",
                    value=cfg["cc_preferred"],
                    help="When unchecked, the agent hunts all trending videos in your categories and applies Transformative Fair-Use + Anti-Copyright framing.",
                    key="cfg_cc_pref",
                )

                lay_keys = list(LAYOUTS.keys())
                lay_vals = list(LAYOUTS.values())
                cur_lay_idx = lay_vals.index(cfg["layout_mode"]) if cfg["layout_mode"] in lay_vals else 0
                chosen_lay_label = st.selectbox("Default Vertical Layout", lay_keys, index=cur_lay_idx, key="cfg_lay")

                sub_keys = [k for k in SUB_STYLES.keys() if SUB_STYLES[k] != "none"]
                sub_vals = [SUB_STYLES[k] for k in sub_keys]
                cur_sub_idx = sub_vals.index(cfg["subtitle_style"]) if cfg["subtitle_style"] in sub_vals else 0
                chosen_sub_label = st.selectbox("Default Captions Style", sub_keys, index=cur_sub_idx, key="cfg_sub")

                auto_pub_yt = st.checkbox("Automatically Upload to Connected YouTube Account", value=cfg["auto_publish_youtube"], key="cfg_auto_yt")
                priv_stat = st.selectbox("YouTube Privacy Status", ["public", "unlisted", "private"], index=["public", "unlisted", "private"].index(cfg["privacy_status"]) if cfg["privacy_status"] in ["public", "unlisted", "private"] else 0, key="cfg_priv")

                if st.button("Save Agent Configuration", type="primary", width="stretch", key="btn_save_agent_cfg"):
                    save_agent_config({
                        "enabled": en_auto,
                        "daily_posts_limit": daily_lim,
                        "post_time_utc": post_time,
                        "copyright_safe": cp_safe,
                        "mirror_flip": m_flip,
                        "cc_preferred": cc_pref,
                        "layout_mode": LAYOUTS[chosen_lay_label],
                        "subtitle_style": SUB_STYLES[chosen_sub_label],
                        "auto_publish_youtube": auto_pub_yt,
                        "privacy_status": priv_stat,
                    })
                    st.toast("Autonomous Agent settings saved!")
                    st.rerun()

                st.markdown("<hr style='margin: 12px 0; opacity: 0.2;'>", unsafe_allow_html=True)
                st.markdown("**Background Scheduler Daemon:**")
                d_c1, d_c2 = st.columns(2)
                if not daemon_stat["running"]:
                    if d_c1.button("▶️ Start Daily Daemon", type="primary", width="stretch", key="btn_start_daemon"):
                        start_background_agent_daemon(interval_minutes=30)
                        st.toast("Background daily agent daemon started!")
                        st.rerun()
                else:
                    if d_c1.button("⏹️ Stop Daemon", type="secondary", width="stretch", key="btn_stop_daemon"):
                        stop_background_agent_daemon()
                        st.toast("Background daemon stopped.")
                        st.rerun()
                d_c2.caption(f"Status: **{html.escape(daemon_stat['last_status'])}**")

    # ==========================================================================
    # TAB 2: CHANNEL ANALYTICS & MONETIZATION TRACKER
    # ==========================================================================
    with tab_analytics:
        with st.container(border=True):
            top_c1, top_c2 = st.columns([3, 1.2])
            with top_c1:
                st.markdown(f"##### 📊 Channel Performance & Monetization Tracker — **{html.escape(str(snap.get('channel_name', 'YouTube Channel')))}**")
                st.caption("Reads channel statistics, views, and engagements to automatically improve the videos the agent hunts and work toward YouTube Partner Program (YPP) monetization.")
            with top_c2:
                if st.button("🔄 Sync Live Channel Stats", type="primary", width="stretch", key="btn_sync_analytics"):
                    with st.spinner("Syncing YouTube channel statistics, video views & recalculating category weights..."):
                        sync_channel_and_shorts_analytics()
                        st.toast("Channel statistics & AI category weights updated!")
                        st.rerun()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Subscribers", f"{int(snap.get('subscribers', 0)):,}", help="Target: 500 (Tier 1) / 1,000 (Tier 2)")
            k2.metric("Total Channel Views", f"{int(snap.get('total_views', 0)):,}")
            k3.metric("90-Day Shorts Views", f"{int(snap.get('shorts_views_90d', 0)):,}", help="Target: 3M (Tier 1) / 10M (Tier 2)")
            k4.metric("Avg Engagement Rate", f"{float(snap.get('avg_engagement_rate', 0.0)):.2f}%", help="(Likes + Comments) / Views")

        col_t1, col_t2 = st.columns(2, gap="medium")
        t1 = monetization["tier1"]
        t2 = monetization["tier2"]

        with col_t1:
            with st.container(border=True):
                st.markdown(f"##### 🥉 {t1['name']}")
                st.caption("Unlocks Super Thanks, Super Chat, Channel Memberships & Shopping.")
                st.progress(min(1.0, t1["subs_pct"] / 100.0), text=f"Subscribers: {t1['subs_current']:,} / {t1['subs_target']:,} ({t1['subs_pct']}%)")
                st.progress(min(1.0, t1["shorts_views_pct"] / 100.0), text=f"90d Shorts Views: {t1['shorts_views_current']:,} / {t1['shorts_views_target']:,} ({t1['shorts_views_pct']}%)")
                st.progress(min(1.0, t1["watch_hours_pct"] / 100.0), text=f"Or Public Watch Hours: {t1['watch_hours_current']:,.1f} / {t1['watch_hours_target']:,} ({t1['watch_hours_pct']}%)")
                st.caption(f"Public uploads (last 90d): **{t1['uploads_current']} / {t1['uploads_target']}** • Overall Readiness: **{t1['overall_pct']}%**")

        with col_t2:
            with st.container(border=True):
                st.markdown(f"##### 🏆 {t2['name']}")
                st.caption("Unlocks Full Shorts Feed Ad Revenue Sharing & Watch Page Ads.")
                st.progress(min(1.0, t2["subs_pct"] / 100.0), text=f"Subscribers: {t2['subs_current']:,} / {t2['subs_target']:,} ({t2['subs_pct']}%)")
                st.progress(min(1.0, t2["shorts_views_pct"] / 100.0), text=f"90d Shorts Views: {t2['shorts_views_current']:,} / {t2['shorts_views_target']:,} ({t2['shorts_views_pct']}%)")
                st.progress(min(1.0, t2["watch_hours_pct"] / 100.0), text=f"Or Public Watch Hours: {t2['watch_hours_current']:,.1f} / {t2['watch_hours_target']:,} ({t2['watch_hours_pct']}%)")
                st.caption(f"Overall Full YPP Readiness: **{t2['overall_pct']}%**")

        with st.container(border=True):
            st.markdown("##### 🧠 Self-Improving AI Strategy & Hunting Insights")
            for rec in monetization["recommendations"]:
                st.markdown(f"- {rec}")

    # ==========================================================================
    # TAB 3: CATEGORIES & SPECIFIC COMMANDS MANAGER
    # ==========================================================================
    with tab_categories:
        with st.container(border=True):
            st.markdown("##### ➕ Add Specific Command / Niche to Hunting Rotation")
            st.caption("Add any specific game, league, creator, or keyword command (e.g. `FIFA`, `GTA`, `Valorant`, `IPL Cricket`, `WWE`, `MrBeast`, `Ronaldo`).")
            ac1, ac2, ac3 = st.columns([1.4, 2.0, 1.0])
            new_cmd_name = ac1.text_input("Command / Category Label", placeholder="e.g. 🎮 Command: FIFA 25", key="new_cmd_label")
            new_cmd_query = ac2.text_input("Search Command / Keywords", placeholder="e.g. FIFA EA FC 25 insane goals skills pack opening", key="new_cmd_query")
            if ac3.button("Add Command", type="primary", width="stretch", key="btn_add_cmd"):
                if new_cmd_name.strip() and new_cmd_query.strip():
                    slug_k = "cmd_" + "".join(ch if ch.isalnum() else "_" for ch in new_cmd_name.lower()).strip("_")[:18]
                    upsert_category_command(slug_k, new_cmd_name.strip(), new_cmd_query.strip(), is_enabled=True, weight_score=86.0)
                    st.toast(f"Added '{new_cmd_name}' to hunting rotation!")
                    st.rerun()

        st.markdown("##### 🎯 Active Categories & Commands (Ranked by Self-Improving AI Performance Weight)")
        all_cats = get_category_performance(enabled_only=False)
        for cat in all_cats:
            ckey = cat["category_key"]
            with st.container(border=True):
                cc1, cc2, cc3, cc4 = st.columns([2.2, 1.5, 1.0, 1.1])
                with cc1:
                    st.markdown(f"**{html.escape(cat['display_name'])}** (`{html.escape(cat['query_command'])}`)")
                    st.caption(
                        f"Shorts Published: **{cat.get('clips_published', 0)}** • "
                        f"Total Views: **{int(cat.get('total_views', 0)):,}** • "
                        f"Avg Engagement: **{float(cat.get('avg_engagement', 0.0)):.2f}%**"
                    )
                with cc2:
                    st.markdown(f"<div class='cf-score'>AI Weight: {float(cat.get('weight_score', 80.0)):.1f}/100</div>", unsafe_allow_html=True)
                with cc3:
                    is_en = bool(cat.get("is_enabled"))
                    new_en = st.checkbox("Active in Rotation", value=is_en, key=f"cat_en_{ckey}")
                    if new_en != is_en:
                        toggle_category_command(ckey, new_en)
                        st.rerun()
                with cc4:
                    if st.button("Hunt This Now", key=f"hunt_cat_{ckey}", width="stretch"):
                        st.session_state["agent_specific_cmd"] = cat["query_command"]
                        with st.spinner(f"Hunting & rendering Short for {cat['display_name']}..."):
                            res = run_autonomous_agent_cycle(explicit_category_or_command=ckey, run_type="quick_category")
                            if res.get("success"):
                                st.session_state["last_agent_result"] = res
                                st.toast(f"Published Short for {cat['display_name']}!")
                        st.rerun()

    # ==========================================================================
    # TAB 4: YOUTUBE ACCOUNT CREDENTIALS & AGENT RUN LOGS
    # ==========================================================================
    with tab_account:
        col_yt, col_logs = st.columns([1.3, 1.7], gap="medium")

        with col_yt:
            with st.container(border=True):
                st.markdown("##### 🔐 Provide Your YouTube Account for Auto-Posting & Analytics")
                socials = get_social_accounts()
                yt_acc = socials.get("youtube") or {}
                is_conn = bool(yt_acc.get("is_connected"))

                if is_conn:
                    st.markdown(
                        f"{badge('CONNECTED', 'ok')} **{html.escape(yt_acc.get('account_name') or 'YouTube Channel')}** "
                        f"(`{html.escape(yt_acc.get('account_handle') or '')}`)",
                        unsafe_allow_html=True,
                    )

                st.caption("**Option A: One-Click Google OAuth 2.0 (`client_secrets.json`)**")
                sec_upload = st.file_uploader("Upload Google Cloud OAuth client_secrets.json", type=["json"], key="yt_oauth_json_up")
                if sec_upload is not None:
                    sec_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "client_secrets.json")
                    with open(sec_path, "wb") as f:
                        f.write(sec_upload.getbuffer())
                    if st.button("🌐 Authorize YouTube Account in Browser", type="primary", width="stretch", key="btn_oauth_browser"):
                        try:
                            auth_res = authorize_youtube_oauth_interactive(sec_path)
                            st.success(f"Connected to YouTube Channel: {auth_res.get('channel_title')} ({auth_res.get('channel_handle')})")
                            st.rerun()
                        except Exception as e:
                            st.error(f"OAuth flow failed: {e}")

                st.markdown("<hr style='margin: 10px 0; opacity: 0.2;'>", unsafe_allow_html=True)
                st.caption("**Option B: Direct Account & Token / API Credentials**")
                acc_name = st.text_input("Channel Name", value=yt_acc.get("account_name", ""), placeholder="My Viral Shorts Channel", key="yt_in_name")
                acc_handle = st.text_input("Channel Handle", value=yt_acc.get("account_handle", ""), placeholder="@mychannel", key="yt_in_handle")
                acc_chid = st.text_input("YouTube Channel ID (for Analytics)", value=yt_acc.get("channel_id", "") or get_setting("OWN_CHANNEL_ID", ""), placeholder="UC...", key="yt_in_chid")
                acc_apikey = st.text_input("YouTube Data API v3 Key", value=get_setting("YOUTUBE_API_KEY", "") or get_setting("youtube_api_key", ""), type="password", key="yt_in_apikey")
                acc_token = st.text_input("OAuth2 Access Token (for Direct Video Upload)", value=yt_acc.get("access_token", ""), type="password", key="yt_in_token")
                acc_refresh = st.text_input("OAuth2 Refresh Token (for Unattended Daily Renewal)", value=yt_acc.get("refresh_token", ""), type="password", key="yt_in_refresh")
                c_id_in = st.text_input("Google OAuth Client ID (Optional)", value=yt_acc.get("client_id", ""), key="yt_in_cid")
                c_sec_in = st.text_input("Google OAuth Client Secret (Optional)", value=yt_acc.get("client_secret", ""), type="password", key="yt_in_csec")

                if st.button("Save & Connect YouTube Account", type="primary", width="stretch", key="btn_save_yt_acc"):
                    if acc_apikey.strip():
                        set_setting("YOUTUBE_API_KEY", acc_apikey.strip())
                        set_setting("youtube_api_key", acc_apikey.strip())
                    if acc_chid.strip():
                        set_setting("OWN_CHANNEL_ID", acc_chid.strip())
                    save_social_account(
                        platform="youtube",
                        account_name=acc_name.strip() or "YouTube Channel",
                        account_handle=acc_handle.strip() or "@youtube",
                        api_key=acc_apikey.strip(),
                        access_token=acc_token.strip(),
                        refresh_token=acc_refresh.strip(),
                        client_id=c_id_in.strip(),
                        client_secret=c_sec_in.strip(),
                        channel_id=acc_chid.strip(),
                    )
                    st.toast("YouTube account credentials saved & connected!")
                    st.rerun()

        with col_logs:
            with st.container(border=True):
                st.markdown("##### 📜 Autonomous Agent Run History")
                runs = get_agent_runs(limit=20)
                if not runs:
                    st.info("No autonomous agent cycles logged yet. Click 'Run Full Autonomous Cycle Now' in Tab 1 to start!")
                else:
                    for r in runs:
                        st_kind = "ok" if r.get("status") == "completed" else "warn"
                        with st.expander(
                            f"Run #{r['id']} • {r.get('category') or 'Auto'} — {r.get('hook_title') or r.get('status')} ({r.get('created_at', '')[:19]})",
                            expanded=(r == runs[0]),
                        ):
                            st.markdown(
                                f"{badge(r.get('status', 'completed').upper(), st_kind)} "
                                f"**Source:** {html.escape(str(r.get('source_title') or r.get('source_video_id') or 'N/A'))}",
                                unsafe_allow_html=True,
                            )
                            if r.get("published_url"):
                                st.markdown(f"**Published Short:** `{html.escape(str(r['published_url']))}`")
                            if r.get("log_summary"):
                                st.code(r["log_summary"], language=None)
