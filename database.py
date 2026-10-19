"""
ClipForge Database Module
Handles SQLite storage for API quota tracking, app settings, permission allowlists,
and discovered video metadata.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "clipforge.db")


def get_connection():
    """Get a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite database tables if they do not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Quota tracking table (YouTube Data API daily reset)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quota_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                units INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Key-value settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Channel Permission Allowlist (Phase 2)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allowlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE NOT NULL,
                channel_name TEXT NOT NULL,
                proof_note TEXT,
                added_at TEXT NOT NULL
            )
        """)
        
        # Discovered / Trending Videos cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                channel_title TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                published_at TEXT NOT NULL,
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                duration TEXT,
                license TEXT NOT NULL,
                thumbnail_url TEXT,
                views_per_hour REAL DEFAULT 0.0,
                like_ratio REAL DEFAULT 0.0,
                score REAL DEFAULT 0.0,
                is_cleared INTEGER DEFAULT 0,
                cleared_reason TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Clips table (Phases 3-5)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                duration REAL NOT NULL,
                score REAL NOT NULL,
                rationale TEXT,
                hook_title TEXT,
                hook_duration REAL DEFAULT 5.0,
                caption_text TEXT,
                status TEXT DEFAULT 'pending', -- pending, approved, rejected, published
                file_path TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (video_id) REFERENCES videos(video_id)
            )
        """)

        # Migration: Ensure hook_duration and agent/analytics columns exist in existing clips table
        cursor.execute("PRAGMA table_info(clips)")
        columns = [col[1] for col in cursor.fetchall()]
        migrations = [
            ("hook_duration", "REAL DEFAULT 5.0"),
            ("category", "TEXT DEFAULT 'General'"),
            ("command_query", "TEXT DEFAULT ''"),
            ("youtube_video_id", "TEXT DEFAULT ''"),
            ("published_url", "TEXT DEFAULT ''"),
            ("published_at", "TEXT DEFAULT ''"),
            ("yt_views", "INTEGER DEFAULT 0"),
            ("yt_likes", "INTEGER DEFAULT 0"),
            ("yt_comments", "INTEGER DEFAULT 0"),
            ("hashtags", "TEXT DEFAULT ''"),
            ("custom_title", "TEXT DEFAULT ''"),
            ("custom_caption", "TEXT DEFAULT ''"),
            ("copyright_safe_mode", "INTEGER DEFAULT 1"),
        ]
        for col_name, col_def in migrations:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE clips ADD COLUMN {col_name} {col_def}")

        # Social Accounts & Integrations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS social_accounts (
                platform TEXT PRIMARY KEY, -- 'youtube', 'tiktok', 'instagram', 'twitter'
                account_name TEXT,
                account_handle TEXT,
                is_connected INTEGER DEFAULT 0,
                api_key TEXT,
                access_token TEXT,
                refresh_token TEXT,
                token_expiry TEXT,
                connected_at TEXT
            )
        """)

        # Migration: Ensure client_id, client_secret, channel_id exist on social_accounts
        cursor.execute("PRAGMA table_info(social_accounts)")
        sa_cols = [col[1] for col in cursor.fetchall()]
        for col_name, col_def in [
            ("client_id", "TEXT DEFAULT ''"),
            ("client_secret", "TEXT DEFAULT ''"),
            ("channel_id", "TEXT DEFAULT ''"),
        ]:
            if col_name not in sa_cols:
                cursor.execute(f"ALTER TABLE social_accounts ADD COLUMN {col_name} {col_def}")

        # Autonomous Agent Runs Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_type TEXT DEFAULT 'auto', -- 'auto', 'manual', 'scheduled'
                category TEXT,
                command_query TEXT,
                source_video_id TEXT,
                source_title TEXT,
                clip_id INTEGER,
                hook_title TEXT,
                published_url TEXT,
                status TEXT, -- 'completed', 'failed', 'running'
                log_summary TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Channel Analytics Snapshots (Monetization & Growth Tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                channel_name TEXT,
                subscribers INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                total_videos INTEGER DEFAULT 0,
                shorts_views_90d INTEGER DEFAULT 0,
                watch_hours_365d REAL DEFAULT 0.0,
                uploads_90d INTEGER DEFAULT 0,
                avg_engagement_rate REAL DEFAULT 0.0,
                recorded_at TEXT NOT NULL
            )
        """)

        # Self-Improving Category & Command Performance Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_performance (
                category_key TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                query_command TEXT NOT NULL,
                is_enabled INTEGER DEFAULT 1,
                clips_published INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                avg_views REAL DEFAULT 0.0,
                avg_engagement REAL DEFAULT 0.0,
                weight_score REAL DEFAULT 50.0,
                last_hunted_at TEXT DEFAULT ''
            )
        """)

        # Seed default categories & specific commands if empty
        default_categories = [
            ("football", "⚽ Football", "football highlights skills goals", 1, 85.0),
            ("cricket", "🏏 Cricket", "cricket highlights sixes wickets IPL T20", 1, 85.0),
            ("youtubers", "🎬 YouTubers", "mrbeast sidemen viral youtuber challenge moments", 1, 82.0),
            ("streamers", "🎙️ Streamers", "ishowspeed kai cenat xqc streamer viral reaction", 1, 88.0),
            ("gaming", "🎮 Gaming", "gaming viral moments insane gameplay clutch", 1, 80.0),
            ("cmd_fifa", "⚽ Command: FIFA / EA FC", "FIFA EA FC insane goals skills pack opening", 1, 84.0),
            ("cmd_gta", "🚓 Command: GTA", "GTA 5 GTA 6 RP funny viral moments stunts", 1, 86.0),
            ("cmd_minecraft", "⛏️ Command: Minecraft", "Minecraft speedrun clutch viral moments", 0, 75.0),
            ("cmd_valorant", "🔫 Command: Valorant / FPS", "Valorant CS2 insane ace clutch pro highlights", 0, 75.0),
            ("cmd_ipl", "🏏 Command: IPL & World Cup", "IPL T20 World Cup cricket last over thriller", 1, 83.0),
        ]
        for c_key, d_name, q_cmd, enabled, w_score in default_categories:
            cursor.execute("""
                INSERT OR IGNORE INTO category_performance (
                    category_key, display_name, query_command, is_enabled, weight_score
                ) VALUES (?, ?, ?, ?, ?)
            """, (c_key, d_name, q_cmd, enabled, w_score))

        # User Profile
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY DEFAULT 1,
                name TEXT DEFAULT 'Creator',
                email TEXT DEFAULT '',
                avatar_url TEXT DEFAULT '',
                bio TEXT DEFAULT 'Short-form content creator',
                signed_in INTEGER DEFAULT 1,
                updated_at TEXT
            )
        """)
        
        # Ensure default user profile exists
        cursor.execute("""
            INSERT OR IGNORE INTO user_profile (id, name, email, avatar_url, bio, signed_in, updated_at)
            VALUES (1, 'Creator Studio', 'creator@clipforge.local', '', 'Autonomous Shorts & Reels Creator', 1, datetime('now'))
        """)
        
        conn.commit()


# -------------------------------------------------------------
# Quota Tracking Helpers
# -------------------------------------------------------------
def log_quota_usage(endpoint: str, units: int):
    """Log an API call and its unit cost to the database."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO quota_usage (date_str, endpoint, units, timestamp) VALUES (?, ?, ?, ?)",
            (today, endpoint, units, now_iso)
        )
        conn.commit()


def get_daily_quota_used() -> int:
    """Return total YouTube API quota units consumed today (UTC)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(units) FROM quota_usage WHERE date_str = ?", (today,))
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0


def get_quota_breakdown_today() -> list[dict]:
    """Return breakdown of API costs by endpoint today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT endpoint, SUM(units) as total_units, COUNT(*) as call_count "
            "FROM quota_usage WHERE date_str = ? GROUP BY endpoint ORDER BY total_units DESC",
            (today,)
        )
        return [dict(row) for row in cursor.fetchall()]


# -------------------------------------------------------------
# Settings Helpers
# -------------------------------------------------------------
def get_setting(key: str, default: str = "") -> str:
    """Retrieve setting value by key."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    """Save or update setting value."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        conn.commit()


# -------------------------------------------------------------
# Allowlist Helpers (Phase 2 readiness)
# -------------------------------------------------------------
def get_allowlist() -> list[dict]:
    """Retrieve all channels currently on the permission allowlist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM allowlist ORDER BY added_at DESC")
        return [dict(row) for row in cursor.fetchall()]


def is_channel_allowlisted(channel_id: str) -> bool:
    """Check if channel ID exists in the allowlist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM allowlist WHERE channel_id = ?", (channel_id,))
        return cursor.fetchone() is not None


def add_to_allowlist(channel_id: str, channel_name: str, proof_note: str = "") -> bool:
    """Add or update a channel in the allowlist."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO allowlist (channel_id, channel_name, proof_note, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    channel_name = excluded.channel_name,
                    proof_note = excluded.proof_note,
                    added_at = excluded.added_at
                """,
                (channel_id.strip(), channel_name.strip(), proof_note.strip(), now_iso)
            )
            conn.commit()
            return True
    except Exception:
        return False


def remove_from_allowlist(channel_id: str):
    """Remove a channel from the allowlist."""
    with get_connection() as conn:
        conn.execute("DELETE FROM allowlist WHERE channel_id = ?", (channel_id,))
        conn.commit()


# -------------------------------------------------------------
# Video Cache Helpers
# -------------------------------------------------------------
def save_videos(videos: list[dict]):
    """Upsert discovered videos into SQLite."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        for v in videos:
            conn.execute("""
                INSERT INTO videos (
                    video_id, title, channel_title, channel_id, published_at,
                    view_count, like_count, comment_count, duration, license,
                    thumbnail_url, views_per_hour, like_ratio, score,
                    is_cleared, cleared_reason, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?
                ) ON CONFLICT(video_id) DO UPDATE SET
                    title = excluded.title,
                    channel_title = excluded.channel_title,
                    view_count = excluded.view_count,
                    like_count = excluded.like_count,
                    comment_count = excluded.comment_count,
                    duration = excluded.duration,
                    license = excluded.license,
                    thumbnail_url = excluded.thumbnail_url,
                    views_per_hour = excluded.views_per_hour,
                    like_ratio = excluded.like_ratio,
                    score = excluded.score,
                    is_cleared = excluded.is_cleared,
                    cleared_reason = excluded.cleared_reason,
                    updated_at = excluded.updated_at
            """, (
                v["video_id"], v["title"], v["channel_title"], v["channel_id"], v["published_at"],
                v.get("view_count", 0), v.get("like_count", 0), v.get("comment_count", 0),
                v.get("duration", ""), v.get("license", "unknown"), v.get("thumbnail_url", ""),
                v.get("views_per_hour", 0.0), v.get("like_ratio", 0.0), v.get("score", 0.0),
                1 if v.get("is_cleared") else 0, v.get("cleared_reason", ""), now_iso
            ))
        conn.commit()


def get_cached_videos(min_views: int = 0, sort_by: str = "score", limit: int = 50) -> list[dict]:
    """Retrieve cached videos filtered and sorted."""
    sort_column = {
        "score": "score DESC",
        "views_per_hour": "views_per_hour DESC",
        "views": "view_count DESC",
        "likes": "like_count DESC",
        "recent": "published_at DESC"
    }.get(sort_by, "score DESC")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM videos WHERE view_count >= ? ORDER BY {sort_column} LIMIT ?",
            (min_views, limit)
        )
        return [dict(row) for row in cursor.fetchall()]


# -------------------------------------------------------------
# User Profile & Social Accounts Helpers
# -------------------------------------------------------------
def get_user_profile() -> dict:
    """Retrieve creator profile information."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_profile WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {"name": "Creator Studio", "email": "creator@clipforge.local", "bio": "Autonomous Shorts Creator", "signed_in": 1}


def save_user_profile(name: str, email: str, bio: str, avatar_url: str = ""):
    """Update creator profile information."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            UPDATE user_profile SET
                name = ?, email = ?, bio = ?, avatar_url = ?, signed_in = 1, updated_at = ?
            WHERE id = 1
        """, (name.strip(), email.strip(), bio.strip(), avatar_url.strip(), now_iso))
        conn.commit()


def get_social_accounts() -> dict[str, dict]:
    """Retrieve status of all connected social accounts."""
    platforms = ["youtube", "tiktok", "instagram", "twitter"]
    results = {}
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM social_accounts")
        rows = {row["platform"]: dict(row) for row in cursor.fetchall()}
        
    for p in platforms:
        if p in rows:
            results[p] = rows[p]
        else:
            results[p] = {
                "platform": p,
                "account_name": "",
                "account_handle": "",
                "is_connected": 0,
                "api_key": "",
                "access_token": "",
                "refresh_token": "",
                "connected_at": ""
            }
    return results


def save_social_account(
    platform: str,
    account_name: str,
    account_handle: str,
    api_key: str = "",
    access_token: str = "",
    refresh_token: str = "",
    client_id: str = "",
    client_secret: str = "",
    channel_id: str = "",
):
    """Connect or update a social media account with full OAuth / API credentials."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO social_accounts (
                platform, account_name, account_handle, is_connected,
                api_key, access_token, refresh_token, client_id, client_secret, channel_id, connected_at
            ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform) DO UPDATE SET
                account_name = excluded.account_name,
                account_handle = excluded.account_handle,
                is_connected = 1,
                api_key = CASE WHEN excluded.api_key != '' THEN excluded.api_key ELSE social_accounts.api_key END,
                access_token = CASE WHEN excluded.access_token != '' THEN excluded.access_token ELSE social_accounts.access_token END,
                refresh_token = CASE WHEN excluded.refresh_token != '' THEN excluded.refresh_token ELSE social_accounts.refresh_token END,
                client_id = CASE WHEN excluded.client_id != '' THEN excluded.client_id ELSE social_accounts.client_id END,
                client_secret = CASE WHEN excluded.client_secret != '' THEN excluded.client_secret ELSE social_accounts.client_secret END,
                channel_id = CASE WHEN excluded.channel_id != '' THEN excluded.channel_id ELSE social_accounts.channel_id END,
                connected_at = excluded.connected_at
        """, (
            platform,
            account_name.strip(),
            account_handle.strip(),
            api_key.strip(),
            access_token.strip(),
            refresh_token.strip(),
            client_id.strip(),
            client_secret.strip(),
            channel_id.strip(),
            now_iso,
        ))
        conn.commit()


def disconnect_social_account(platform: str):
    """Disconnect a social media account."""
    with get_connection() as conn:
        conn.execute("UPDATE social_accounts SET is_connected = 0, access_token = '', refresh_token = '', api_key = '' WHERE platform = ?", (platform,))
        conn.commit()


# -------------------------------------------------------------
# Clips Management Helpers (Phases 4-6)
# -------------------------------------------------------------
def save_clip(clip_data: dict) -> int:
    """Save or update a rendered clip in SQLite."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clips (
                video_id, start_time, end_time, duration, score,
                rationale, hook_title, hook_duration, caption_text, status, file_path,
                category, command_query, hashtags, custom_title, custom_caption, copyright_safe_mode,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clip_data.get("video_id", "unknown"),
            clip_data.get("start_time", 0.0),
            clip_data.get("end_time", 0.0),
            clip_data.get("duration", 0.0),
            clip_data.get("score", 0.0),
            clip_data.get("rationale", ""),
            clip_data.get("hook_title", ""),
            float(clip_data.get("hook_duration", 5.0)),
            clip_data.get("caption_text", ""),
            clip_data.get("status", "pending"),
            clip_data.get("file_path", ""),
            clip_data.get("category", "General"),
            clip_data.get("command_query", ""),
            clip_data.get("hashtags", ""),
            clip_data.get("custom_title", ""),
            clip_data.get("custom_caption", ""),
            1 if clip_data.get("copyright_safe_mode", True) else 0,
            now_iso
        ))
        conn.commit()
        return cursor.lastrowid


def get_clips(video_id: str = None, status: str = None) -> list[dict]:
    """Retrieve clips optionally filtered by video_id or status."""
    query = "SELECT * FROM clips"
    params = []
    clauses = []
    if video_id:
        clauses.append("video_id = ?")
        params.append(video_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id DESC"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def update_clip_status(clip_id: int, status: str, hook_title: str = None, caption_text: str = None, hook_duration: float = None):
    """Update clip status (approved, rejected, published) and metadata."""
    with get_connection() as conn:
        updates = ["status = ?"]
        params = [status]
        if hook_title is not None:
            updates.append("hook_title = ?")
            params.append(hook_title)
        if hook_duration is not None:
            updates.append("hook_duration = ?")
            params.append(float(hook_duration))
        if caption_text is not None:
            updates.append("caption_text = ?")
            params.append(caption_text)
        params.append(clip_id)
        conn.execute(f"UPDATE clips SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()


def delete_clip(clip_id: int):
    """Delete a clip record from the database."""
    with get_connection() as conn:
        conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
        conn.commit()


def update_clip(clip_id: int, updates: dict):
    """Update arbitrary fields of a clip record in SQLite."""
    if not updates:
        return
    fields = []
    values = []
    for k, v in updates.items():
        fields.append(f"{k} = ?")
        values.append(v)
    values.append(clip_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE clips SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()


# -------------------------------------------------------------
# Autonomous Agent, Category Performance & Channel Analytics Helpers
# -------------------------------------------------------------
def get_category_performance(enabled_only: bool = False) -> list[dict]:
    """Retrieve all configured categories and specific commands ordered by weight_score DESC."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if enabled_only:
            cursor.execute("SELECT * FROM category_performance WHERE is_enabled = 1 ORDER BY weight_score DESC")
        else:
            cursor.execute("SELECT * FROM category_performance ORDER BY weight_score DESC")
        return [dict(row) for row in cursor.fetchall()]


def upsert_category_command(category_key: str, display_name: str, query_command: str, is_enabled: bool = True, weight_score: float = 85.0):
    """Add or update a category or custom command (e.g., FIFA, GTA, Cricket, Streamers) for the agent."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO category_performance (
                category_key, display_name, query_command, is_enabled, weight_score
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category_key) DO UPDATE SET
                display_name = excluded.display_name,
                query_command = excluded.query_command,
                is_enabled = excluded.is_enabled,
                weight_score = excluded.weight_score
        """, (category_key.strip().lower(), display_name.strip(), query_command.strip(), 1 if is_enabled else 0, float(weight_score)))
        conn.commit()


def toggle_category_command(category_key: str, is_enabled: bool):
    """Enable or disable a category/command in the autonomous hunting rotation."""
    with get_connection() as conn:
        conn.execute("UPDATE category_performance SET is_enabled = ? WHERE category_key = ?", (1 if is_enabled else 0, category_key))
        conn.commit()


def delete_category_command(category_key: str):
    """Delete a custom category/command from the rotation."""
    with get_connection() as conn:
        conn.execute("DELETE FROM category_performance WHERE category_key = ?", (category_key,))
        conn.commit()


def log_agent_run(run_data: dict) -> int:
    """Record an autonomous agent execution cycle."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_runs (
                run_type, category, command_query, source_video_id, source_title,
                clip_id, hook_title, published_url, status, log_summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_data.get("run_type", "auto"),
            run_data.get("category", ""),
            run_data.get("command_query", ""),
            run_data.get("source_video_id", ""),
            run_data.get("source_title", ""),
            run_data.get("clip_id", 0),
            run_data.get("hook_title", ""),
            run_data.get("published_url", ""),
            run_data.get("status", "completed"),
            run_data.get("log_summary", ""),
            now_iso,
        ))
        conn.commit()
        return cursor.lastrowid


def get_agent_runs(limit: int = 30) -> list[dict]:
    """Retrieve recent autonomous agent runs."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_runs ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


def save_channel_analytics_snapshot(stats: dict):
    """Save a channel analytics snapshot for growth and monetization tracking."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO channel_analytics (
                channel_id, channel_name, subscribers, total_views, total_videos,
                shorts_views_90d, watch_hours_365d, uploads_90d, avg_engagement_rate, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stats.get("channel_id", ""),
            stats.get("channel_name", "Creator Channel"),
            int(stats.get("subscribers", 0)),
            int(stats.get("total_views", 0)),
            int(stats.get("total_videos", 0)),
            int(stats.get("shorts_views_90d", 0)),
            float(stats.get("watch_hours_365d", 0.0)),
            int(stats.get("uploads_90d", 0)),
            float(stats.get("avg_engagement_rate", 0.0)),
            now_iso,
        ))
        conn.commit()


def get_latest_channel_analytics() -> dict | None:
    """Return the most recent channel analytics snapshot."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channel_analytics ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None


def get_channel_analytics_history(limit: int = 30) -> list[dict]:
    """Return historical channel analytics snapshots ordered chronologically."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM channel_analytics ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        rows.reverse()
        return rows


# Initialize database schema on module load
init_db()

