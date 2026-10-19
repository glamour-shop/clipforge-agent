"""Shared helpers for ClipForge UI steps (navigation, file helpers, option maps)."""

import os
import json
import subprocess
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS = os.path.join(ROOT, "downloads")
EXPORT_PACKS = os.path.join(DOWNLOADS, "export_packs")
REACTIONS_DIR = os.path.join(DOWNLOADS, "reactions")

STEPS = ["Discover", "Source", "Create", "Publish", "Auto-Agent"]

LAYOUTS = {
    "Blurred background": "blurred_stack",
    "Smart center crop": "smart_crop",
    "Letterbox (black bars)": "fit_letterbox",
}
SUB_STYLES = {
    "Bold yellow (Hormozi)": "hormozi_yellow",
    "Clean white & gold": "beast_white",
    "Neon cyan": "neon_cyan",
    "None (clean video)": "none",
}
SPEEDS = {"1.0x": 1.0, "1.25x": 1.25, "1.5x": 1.5, "2.0x": 2.0}
PACING_WORDS = "WATCH THIS UNBELIEVABLE MOMENT WAIT FOR IT"

REACTION_POSITIONS = {
    "top_left": "Top left",
    "top_right": "Top right",
    "bottom_left": "Bottom left",
    "bottom_right": "Bottom right",
    "bottom_strip": "Bottom strip",
}
REACTION_AUDIO = {
    "mix": "Mix my mic with the clip",
    "original": "Original clip audio only",
    "reaction": "Reaction audio only",
}


def goto(step: int):
    st.session_state["step"] = max(0, min(len(STEPS) - 1, int(step)))
    st.rerun()


def make_file_downloader(file_path):
    """Deferred reader for st.download_button so big files are read only on click."""
    def _read():
        with open(file_path, "rb") as f:
            return f.read()
    return _read


def open_folder_in_explorer(file_path):
    try:
        abs_p = os.path.abspath(file_path)
        if os.path.isfile(abs_p):
            subprocess.Popen(f'explorer /select,"{abs_p}"')
        elif os.path.isdir(abs_p):
            subprocess.Popen(f'explorer "{abs_p}"')
        return True
    except Exception:
        return False


def fmt_time(sec) -> str:
    sec = float(sec or 0)
    return f"{int(sec // 60):02d}:{int(sec % 60):02d}"


def read_credits_info(video_dir: str) -> dict:
    c_file = os.path.join(video_dir, "credits.json")
    info = {"title": None, "creator": "Original Creator", "url": ""}
    if os.path.exists(c_file):
        try:
            with open(c_file, "r", encoding="utf-8") as cf:
                data = json.load(cf)
                info["creator"] = data.get("creator", "Original Creator")
                info["url"] = data.get("url", "")
                desc = data.get("description_credit", "")
                for line in desc.split("\n"):
                    if line.startswith("Original Video:") or line.startswith("Uploaded File:"):
                        info["title"] = line.split(":", 1)[1].strip(" \"")
                        break
        except Exception:
            pass
    return info


def read_credits_creator(video_dir: str) -> str:
    return read_credits_info(video_dir).get("creator", "Original Creator")


def list_downloads():
    out = []
    if not os.path.exists(DOWNLOADS):
        return out

    for d in sorted(os.listdir(DOWNLOADS)):
        full_d = os.path.join(DOWNLOADS, d)
        if not os.path.isdir(full_d) or d in ("export_packs", "reactions"):
            continue

        # Locate the source MP4 in this folder
        source_mp4 = None
        for f in os.listdir(full_d):
            if f.endswith(".mp4") and "_short_" not in f and "_reaction" not in f and "_rx_" not in f:
                source_mp4 = os.path.join(full_d, f)
                break

        if not source_mp4 or not os.path.exists(source_mp4):
            continue

        # Extract video_id from brackets [vid_id] if present
        vid_id = d
        if "[" in d and d.endswith("]"):
            vid_id = d[d.rfind("[") + 1 : -1]

        cred = read_credits_info(full_d)
        title = cred["title"]
        if not title:
            title = d[: d.rfind("[")].strip() if "[" in d else d

        sz_mb = round(os.path.getsize(source_mp4) / 1024 / 1024, 1)
        mtime = os.path.getmtime(source_mp4)

        out.append({
            "id": vid_id,
            "title": title,
            "creator": cred["creator"],
            "path": source_mp4,
            "dir_path": full_d,
            "folder_name": d,
            "file_size_mb": sz_mb,
            "modified_time": mtime,
        })

    # Sort newest first
    out.sort(key=lambda x: x["modified_time"], reverse=True)
    return out


def cache_candidates(video_path: str, cands):
    try:
        with open(os.path.join(os.path.dirname(video_path), "candidates.json"), "w", encoding="utf-8") as f:
            json.dump(cands, f, indent=2)
    except Exception:
        pass


def load_cached_candidates(video_path: str):
    p = os.path.join(os.path.dirname(video_path), "candidates.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def reset_video_state():
    """Clear everything tied to the currently active source video."""
    st.session_state["downloaded_video"] = None
    st.session_state["highlight_candidates"] = []
    st.session_state["selected_candidate"] = None
    st.session_state["rendered_clip"] = None


def set_active_source(dl_res: dict, meta: dict = None):
    st.session_state["downloaded_video"] = dl_res
    st.session_state["selected_video"] = meta or {
        "title": dl_res.get("title", "Imported video"),
        "video_id": dl_res.get("video_id", "imported"),
        "channel_title": dl_res.get("channel_title", "Creator"),
    }
    st.session_state["highlight_candidates"] = []
    st.session_state["selected_candidate"] = None


def save_reaction_upload(uploaded) -> str:
    """Persist an uploaded reaction clip into downloads/reactions/ and return its path."""
    os.makedirs(REACTIONS_DIR, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in uploaded.name)
    path = os.path.join(REACTIONS_DIR, safe)
    if not (os.path.exists(path) and os.path.getsize(path) == uploaded.size):
        with open(path, "wb") as f:
            f.write(uploaded.getbuffer())
    return path


def progress_hook(bar, scale: float = 1.0):
    def _hook(pct, *args):
        text = args[-1] if args else ""
        bar.progress(min(1.0, max(0.01, float(pct) / 100.0 * scale)), text=str(text))
    return _hook
