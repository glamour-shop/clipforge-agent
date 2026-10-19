"""
ClipForge Autonomous Daily Shorts Agent
1. Analyzes channel statistics & YPP monetization progress to optimize category/command selection
2. Hunts trending videos for any selected category (Football, Cricket, YouTubers, Streamers, Gaming) or specific command (FIFA, GTA, IPL, etc.)
3. Auto-adds & approves videos under Creative Commons / Transformative Fair Use
4. Extracts high-engagement sections (YouTube Most Replayed heatmap + Audio RMS peaks + AI Hook scoring)
5. Renders complete 1080x1920 vertical Shorts with animated captions, punchy Hook Title, and Copyright-Safe transformative processing
6. Automatically posts Shorts to the connected YouTube account with optimized/custom Title, Caption, and Hashtags
7. Supports daily autonomous background scheduling (in-app daemon thread + CLI daemon mode)
"""

import os
import sys
import time
import random
import argparse
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from database import (
    get_connection,
    get_clips,
    update_clip,
    get_setting,
    set_setting,
    get_category_performance,
    upsert_category_command,
    log_agent_run,
    get_agent_runs,
)
from trends import search_niche_videos, get_sample_trending_videos
from rights import approve_and_clear_video, download_cleared_video
from highlights import extract_highlight_candidates
from editor import render_short_video
from publish import publish_short_to_platform, build_platform_metadata
from analytics import sync_channel_and_shorts_analytics


# Global Background Daemon State
_DAEMON_THREAD: Optional[threading.Thread] = None
_DAEMON_STOP_EVENT = threading.Event()
_DAEMON_STATUS = {
    "running": False,
    "last_run_at": "",
    "next_run_at": "",
    "last_status": "Idle",
    "posts_today": 0,
}


def get_agent_config() -> dict:
    """Retrieve autonomous agent configuration from settings."""
    return {
        "enabled": get_setting("AGENT_AUTO_ENABLED", "1") == "1",
        "daily_posts_limit": int(get_setting("AGENT_DAILY_POSTS", "2") or 2),
        "post_time_utc": get_setting("AGENT_POST_TIME", "14:00"),
        "layout_mode": get_setting("AGENT_LAYOUT_MODE", "blurred_stack"),
        "subtitle_style": get_setting("AGENT_SUBTITLE_STYLE", "hormozi_yellow"),
        "hook_duration": float(get_setting("AGENT_HOOK_DURATION", "5.0") or 5.0),
        "copyright_safe": get_setting("AGENT_COPYRIGHT_SAFE", "1") == "1",
        "mirror_flip": get_setting("AGENT_MIRROR_FLIP", "0") == "1",
        "cc_preferred": get_setting("AGENT_CC_PREFERRED", "0") == "1",
        "auto_publish_youtube": get_setting("AGENT_AUTO_PUBLISH_YT", "1") == "1",
        "privacy_status": get_setting("AGENT_PRIVACY_STATUS", "public"),
        "custom_caption_template": get_setting("AGENT_CAPTION_TEMPLATE", ""),
        "custom_hashtags_override": get_setting("AGENT_HASHTAGS_OVERRIDE", ""),
        "custom_title_prefix": get_setting("AGENT_TITLE_PREFIX", ""),
    }


def save_agent_config(cfg: dict):
    """Persist autonomous agent configuration into settings."""
    if "enabled" in cfg:
        set_setting("AGENT_AUTO_ENABLED", "1" if cfg["enabled"] else "0")
    if "daily_posts_limit" in cfg:
        set_setting("AGENT_DAILY_POSTS", str(int(cfg["daily_posts_limit"])))
    if "post_time_utc" in cfg:
        set_setting("AGENT_POST_TIME", str(cfg["post_time_utc"]).strip())
    if "layout_mode" in cfg:
        set_setting("AGENT_LAYOUT_MODE", str(cfg["layout_mode"]))
    if "subtitle_style" in cfg:
        set_setting("AGENT_SUBTITLE_STYLE", str(cfg["subtitle_style"]))
    if "hook_duration" in cfg:
        set_setting("AGENT_HOOK_DURATION", str(float(cfg["hook_duration"])))
    if "copyright_safe" in cfg:
        set_setting("AGENT_COPYRIGHT_SAFE", "1" if cfg["copyright_safe"] else "0")
    if "mirror_flip" in cfg:
        set_setting("AGENT_MIRROR_FLIP", "1" if cfg["mirror_flip"] else "0")
    if "cc_preferred" in cfg:
        set_setting("AGENT_CC_PREFERRED", "1" if cfg["cc_preferred"] else "0")
    if "auto_publish_youtube" in cfg:
        set_setting("AGENT_AUTO_PUBLISH_YT", "1" if cfg["auto_publish_youtube"] else "0")
    if "privacy_status" in cfg:
        set_setting("AGENT_PRIVACY_STATUS", str(cfg["privacy_status"]))
    if "custom_caption_template" in cfg:
        set_setting("AGENT_CAPTION_TEMPLATE", str(cfg["custom_caption_template"]).strip())
    if "custom_hashtags_override" in cfg:
        set_setting("AGENT_HASHTAGS_OVERRIDE", str(cfg["custom_hashtags_override"]).strip())
    if "custom_title_prefix" in cfg:
        set_setting("AGENT_TITLE_PREFIX", str(cfg["custom_title_prefix"]).strip())


def select_best_category_to_hunt(explicit_category_or_command: str = "") -> dict:
    """
    Choose which category or specific command to hunt next.
    - If explicit_category_or_command is passed (e.g. 'FIFA', 'GTA', 'cricket', 'football'), use or register it.
    - Otherwise use the self-improving weight_score from category_performance (with smart rotation so it doesn't repeat the exact same category back-to-back if multiple are enabled).
    """
    all_cats = get_category_performance(enabled_only=False)
    if explicit_category_or_command and explicit_category_or_command.strip():
        raw = explicit_category_or_command.strip()
        raw_l = raw.lower()
        for c in all_cats:
            if c["category_key"] == raw_l or raw_l in c["display_name"].lower() or raw_l == c["query_command"].lower():
                return c
        # Dynamic custom command (e.g. "FIFA", "GTA 6", "WWE", "Babar Azam")
        custom_key = f"cmd_{raw_l.replace(' ', '_')[:20]}"
        display = f"🎯 Command: {raw}"
        query = f"{raw} viral highlights moments" if len(raw.split()) <= 2 else raw
        upsert_category_command(custom_key, display, query, is_enabled=True, weight_score=88.0)
        return {
            "category_key": custom_key,
            "display_name": display,
            "query_command": query,
            "weight_score": 88.0,
        }

    enabled_cats = [c for c in all_cats if c.get("is_enabled")]
    if not enabled_cats:
        enabled_cats = all_cats

    # Sort by weight_score descending, breaking ties by least-recently hunted
    enabled_cats.sort(key=lambda x: (float(x.get("weight_score", 50.0)), -(len(str(x.get("last_hunted_at") or "")))), reverse=True)

    # Epsilon-greedy selection among top 3 highest-weighted categories to keep variety & exploration
    top_pool = enabled_cats[: min(3, len(enabled_cats))]
    weights = [max(10.0, float(c.get("weight_score", 75.0))) for c in top_pool]
    chosen = random.choices(top_pool, weights=weights, k=1)[0]
    return chosen


def run_autonomous_agent_cycle(
    explicit_category_or_command: str = "",
    custom_title: str = "",
    custom_caption: str = "",
    custom_hashtags: str = "",
    progress_callback: Optional[Callable[[float, str], None]] = None,
    run_type: str = "auto",
) -> dict:
    """
    Execute a complete end-to-end Autonomous Agent cycle:
    1. Sync channel stats & recalculate self-improving category weights
    2. Select target category or specific command (e.g. Football, Cricket, YouTubers, Streamers, Gaming, FIFA, GTA)
    3. Hunt trending videos on YouTube & pick highest-momentum unclipped video
    4. Auto-approve & clear rights + download source MP4
    5. Detect high-engagement sections (Heatmap + Audio RMS peaks + AI Hook Title) & approve best candidate
    6. Render complete 9:16 vertical Short with dynamic captions, Hook Title, and Copyright-Safe filters
    7. Auto-publish to connected YouTube account with selected Title, Caption & Hashtags
    """
    cfg = get_agent_config()
    logs = []

    def _step(pct: float, msg: str):
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        if progress_callback:
            progress_callback(pct, msg)

    try:
        # 1. Analyze Channel Statistics & Update Self-Improving Weights
        _step(8.0, "Analyzing YouTube channel statistics & updating category learning weights...")
        ch_snapshot = sync_channel_and_shorts_analytics()

        # 2. Pick Category / Command
        target_cat = select_best_category_to_hunt(explicit_category_or_command)
        cat_key = target_cat["category_key"]
        cat_label = target_cat["display_name"]
        query_cmd = target_cat["query_command"]
        _step(16.0, f"Hunting trending videos for [{cat_label}] (Query: '{query_cmd}')...")

        # Mark last_hunted_at
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute("UPDATE category_performance SET last_hunted_at = ? WHERE category_key = ?", (now_iso, cat_key))
            conn.commit()

        # 3. Hunt Trending Videos
        discovered, _ = search_niche_videos(
            query=query_cmd,
            region="ALL",
            min_views=25000,
            max_results=25,
            cc_only=cfg["cc_preferred"],
            order="viewCount",
            duration="any",
        )
        if not discovered:
            discovered = get_sample_trending_videos(keyword=query_cmd, min_views=0)
        if not discovered:
            discovered = get_sample_trending_videos(keyword="", min_views=0)

        # Filter out videos we already clipped if alternatives exist
        existing_clips = get_clips()
        already_clipped_ids = {c.get("video_id") for c in existing_clips}
        fresh_videos = [v for v in discovered if v.get("video_id") not in already_clipped_ids]
        candidate_videos = fresh_videos if fresh_videos else discovered

        # Sort by viral momentum score & views
        candidate_videos.sort(key=lambda v: (float(v.get("score", 0.0)), int(v.get("view_count", 0))), reverse=True)
        chosen_video = candidate_videos[0]
        vid_id = chosen_video.get("video_id", "sample")
        vid_title = chosen_video.get("title", "Trending Video")
        _step(28.0, f"Selected high-momentum video: '{vid_title[:60]}' ({chosen_video.get('view_count', 0):,} views, Score {chosen_video.get('score', 90)}/100)")

        # 4. Auto-Approve Rights & Download Source Video
        _step(36.0, "Approving video for transformative clipping & downloading source media...")
        cleared_video = approve_and_clear_video(
            chosen_video,
            permission_reason="Autonomous Agent Transformative Fair Use & Attribution",
        )
        cleared_video["category"] = cat_key
        cleared_video["command_query"] = query_cmd

        dl_res = download_cleared_video(cleared_video)
        if not dl_res or not dl_res.get("success") or not os.path.exists(dl_res.get("file_path", "")):
            raise RuntimeError("Failed to download source video for clipping.")

        source_path = dl_res["file_path"]
        _step(52.0, f"Source video ready ({os.path.basename(source_path)}). Scanning high-engagement sections...")

        # 5. Extract High-Engagement Sections & Approve Best Candidate
        candidates = extract_highlight_candidates(source_path, video_title=vid_title, video_id=vid_id)
        if not candidates:
            raise RuntimeError("No highlight candidates extracted.")

        best_cand = candidates[0]
        # Apply optional title prefix if configured
        hook_title = best_cand.get("hook_title", "UNBELIEVABLE MOMENT")
        if cfg["custom_title_prefix"]:
            hook_title = f"{cfg['custom_title_prefix'].upper()} {hook_title}"[:45]
        best_cand["hook_title"] = hook_title
        best_cand["hook_duration"] = cfg["hook_duration"]
        best_cand["category"] = cat_key
        best_cand["command_query"] = query_cmd
        best_cand["status"] = "approved"

        _step(
            65.0,
            f"Approved high-engagement section ({best_cand['start_formatted']}–{best_cand['end_formatted']}, "
            f"Score {best_cand['score']}/100) with Hook: '{hook_title}'",
        )

        # 6. Render Complete 9:16 Short with Captions, Hook Title & Copyright-Safe Filters
        _step(75.0, "Rendering 1080x1920 vertical Short with burned-in captions, Hook Title & Copyright-Safe filters...")
        render_res = render_short_video(
            source_video_path=source_path,
            clip_candidate=best_cand,
            video_metadata=cleared_video,
            layout_mode=cfg["layout_mode"],
            subtitle_style=cfg["subtitle_style"],
            speed=1.0,
            hook_duration=cfg["hook_duration"],
            copyright_safe=cfg["copyright_safe"],
            mirror_flip=cfg["mirror_flip"],
            ensure_captions=True,
        )

        if not render_res or not render_res.get("success"):
            raise RuntimeError("Short video rendering failed.")

        clip_db_id = render_res["clip_db_id"]
        update_clip(clip_db_id, {"status": "approved", "category": cat_key, "command_query": query_cmd})

        # 7. Auto-Publish to YouTube with Selected Title, Caption & Hashtags
        final_title_in = custom_title.strip() if custom_title else ""
        final_caption_in = custom_caption.strip() if custom_caption else cfg["custom_caption_template"]
        final_hashtags_in = custom_hashtags.strip() if custom_hashtags else cfg["custom_hashtags_override"]

        pub_res = {"published_url": "", "status": "approved", "title": hook_title}
        if cfg["auto_publish_youtube"]:
            _step(90.0, "Publishing Short to connected YouTube channel with captions & hashtags...")
            pub_res = publish_short_to_platform(
                clip_id=clip_db_id,
                platform="youtube",
                custom_title=final_title_in,
                custom_caption=final_caption_in,
                custom_hashtags=final_hashtags_in,
                privacy_status=cfg["privacy_status"],
            )
            _step(97.0, f"Published Short: {pub_res.get('published_url')}")
        else:
            meta_preview = build_platform_metadata(
                best_cand,
                cleared_video,
                category=cat_key,
                custom_hashtags=final_hashtags_in,
                custom_title=final_title_in,
                custom_caption=final_caption_in,
            )
            update_clip(clip_db_id, {
                "custom_title": meta_preview["youtube"]["title"],
                "custom_caption": meta_preview["youtube"]["description"],
                "hashtags": meta_preview["youtube"].get("hashtags_str", "#Shorts"),
            })

        # Sync analytics again so the newly published clip is reflected in channel stats & category weights
        sync_channel_and_shorts_analytics()

        _step(100.0, "Autonomous agent cycle completed successfully!")
        run_id = log_agent_run({
            "run_type": run_type,
            "category": cat_label,
            "command_query": query_cmd,
            "source_video_id": vid_id,
            "source_title": vid_title,
            "clip_id": clip_db_id,
            "hook_title": hook_title,
            "published_url": pub_res.get("published_url", ""),
            "status": "completed",
            "log_summary": "\n".join(logs),
        })

        _DAEMON_STATUS["last_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _DAEMON_STATUS["last_status"] = f"Completed: {hook_title}"
        _DAEMON_STATUS["posts_today"] = int(_DAEMON_STATUS.get("posts_today", 0)) + 1

        return {
            "success": True,
            "run_id": run_id,
            "category": cat_label,
            "command_query": query_cmd,
            "source_video": cleared_video,
            "render_result": render_res,
            "publish_result": pub_res,
            "channel_snapshot": ch_snapshot,
            "logs": logs,
        }

    except Exception as e:
        err_msg = f"Agent cycle error: {str(e)}"
        logs.append(err_msg)
        log_agent_run({
            "run_type": run_type,
            "category": explicit_category_or_command or "Auto",
            "command_query": explicit_category_or_command,
            "status": "failed",
            "log_summary": "\n".join(logs),
        })
        _DAEMON_STATUS["last_status"] = f"Error: {str(e)[:80]}"
        return {
            "success": False,
            "error": str(e),
            "logs": logs,
        }


# ------------------------------------------------------------------------------
# Daily Autonomous Background Scheduler Daemon
# ------------------------------------------------------------------------------
def get_today_completed_runs_count() -> int:
    """Count how many autonomous runs completed today (UTC)."""
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    runs = get_agent_runs(limit=50)
    return sum(
        1 for r in runs
        if r.get("status") == "completed" and str(r.get("created_at", "")).startswith(today_prefix)
    )


def _daemon_loop(interval_minutes: int = 30):
    """Background worker loop checking if daily quota of Shorts has been posted today."""
    _DAEMON_STATUS["running"] = True
    while not _DAEMON_STOP_EVENT.is_set():
        cfg = get_agent_config()
        if cfg["enabled"]:
            done_today = get_today_completed_runs_count()
            _DAEMON_STATUS["posts_today"] = done_today
            target_daily = max(1, int(cfg.get("daily_posts_limit", 1)))
            if done_today < target_daily:
                _DAEMON_STATUS["last_status"] = f"Running daily cycle ({done_today + 1}/{target_daily})..."
                run_autonomous_agent_cycle(run_type="scheduled_daily")
                done_today = get_today_completed_runs_count()
                _DAEMON_STATUS["posts_today"] = done_today
            else:
                _DAEMON_STATUS["last_status"] = f"Daily target met ({done_today}/{target_daily} Shorts posted today)"
        else:
            _DAEMON_STATUS["last_status"] = "Paused (Auto-Agent disabled in config)"

        # Wait until next check
        for _ in range(interval_minutes * 60):
            if _DAEMON_STOP_EVENT.is_set():
                break
            time.sleep(1)

    _DAEMON_STATUS["running"] = False


def start_background_agent_daemon(interval_minutes: int = 30) -> bool:
    """Start the background autonomous daily agent thread if not already running."""
    global _DAEMON_THREAD
    if _DAEMON_THREAD and _DAEMON_THREAD.is_alive():
        _DAEMON_STATUS["running"] = True
        return True
    _DAEMON_STOP_EVENT.clear()
    _DAEMON_THREAD = threading.Thread(target=_daemon_loop, args=(interval_minutes,), daemon=True)
    _DAEMON_THREAD.start()
    _DAEMON_STATUS["running"] = True
    return True


def stop_background_agent_daemon():
    """Stop the background autonomous daily agent thread."""
    _DAEMON_STOP_EVENT.set()
    _DAEMON_STATUS["running"] = False
    _DAEMON_STATUS["last_status"] = "Stopped"


def get_daemon_status() -> dict:
    """Return live status of the background daily agent."""
    global _DAEMON_THREAD
    is_alive = bool(_DAEMON_THREAD and _DAEMON_THREAD.is_alive() and not _DAEMON_STOP_EVENT.is_set())
    _DAEMON_STATUS["running"] = is_alive
    _DAEMON_STATUS["posts_today"] = get_today_completed_runs_count()
    return dict(_DAEMON_STATUS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClipForge Autonomous Daily Shorts Agent")
    parser.add_argument("--category", type=str, default="", help="Specific category or command (e.g. football, cricket, FIFA, GTA)")
    parser.add_argument("--daemon", action="store_true", help="Run continuously on a daily schedule")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in minutes for daemon mode")
    args = parser.parse_args()

    if args.daemon:
        print("[ClipForge Agent] Starting continuous daily autonomous daemon...")
        _DAEMON_STOP_EVENT.clear()
        try:
            _daemon_loop(interval_minutes=max(5, args.interval))
        except KeyboardInterrupt:
            print("\n[ClipForge Agent] Daemon stopped by user.")
            sys.exit(0)
    else:
        print(f"[ClipForge Agent] Running single autonomous cycle (Target: {args.category or 'Best AI Weight'})...")
        res = run_autonomous_agent_cycle(
            explicit_category_or_command=args.category,
            progress_callback=lambda pct, msg: print(f"[{pct:5.1f}%] {msg}"),
            run_type="cli_manual",
        )
        if res.get("success"):
            print(f"\n[SUCCESS] Rendered & Published Short: {res['publish_result'].get('published_url')}")
        else:
            print(f"\n[ERROR] {res.get('error')}")
            sys.exit(1)
