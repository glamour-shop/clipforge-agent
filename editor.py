"""
ClipForge Auto-Editor (Phase 4)
Automated 9:16 Vertical Video Engine:
1. Formats horizontal video to 1080x1920 vertical Shorts/Reels:
   - Blurred Stack (cinematic blurred background + centered crisp video)
   - Smart Center Crop (full 1080x1920 fill)
   - Letterbox Fit (black border fill)
2. Transcribes audio using local faster-whisper with word-level timestamps
3. Generates and burns in animated dynamic ASS subtitles (Alex Hormozi / MrBeast styles)
4. Overlays punchy hook title for customizable duration (default 5.0 seconds)
5. Pins creator attribution watermark
6. Normalizes audio to -14 LUFS (EBU R128)
"""

import os
import re
import subprocess
import shutil
import difflib
from typing import Callable, Optional
from rights import get_ffmpeg_cmd
from database import save_clip, update_clip

# Global cached faster-whisper model
_WHISPER_MODEL = None


def get_whisper_model():
    """Lazily load and cache faster-whisper model in memory on CPU."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        try:
            from faster_whisper import WhisperModel
            # Load tiny model with int8 quantization for ultra-fast CPU inference
            _WHISPER_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
        except Exception as e:
            print(f"[editor] Faster-whisper load notice: {e}")
            _WHISPER_MODEL = False
    return _WHISPER_MODEL if _WHISPER_MODEL is not False else None


def format_ass_timestamp(seconds: float) -> str:
    """Format seconds float into ASS timestamp H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def sanitize_word_timestamps(words: list[dict], duration: float) -> list[dict]:
    """
    Ensure word timestamps are strictly non-overlapping, sequential,
    and fit cleanly within the clip duration.
    """
    if not words:
        return []

    cleaned = []
    for w in words:
        clean_w = str(w.get("word", "")).strip().upper()
        if not clean_w:
            continue
        s = max(0.0, round(float(w.get("start", 0.0)), 2))
        e = max(s + 0.08, round(float(w.get("end", s + 0.25)), 2))
        cleaned.append({"word": clean_w, "start": s, "end": e})

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: x["start"])

    for i in range(len(cleaned)):
        if i > 0 and cleaned[i]["start"] < cleaned[i - 1]["end"]:
            mid = round((cleaned[i]["start"] + cleaned[i - 1]["end"]) / 2, 2)
            if mid > cleaned[i - 1]["start"] + 0.05:
                cleaned[i - 1]["end"] = mid
                cleaned[i]["start"] = mid
            else:
                cleaned[i]["start"] = cleaned[i - 1]["end"]
            cleaned[i]["end"] = max(cleaned[i]["start"] + 0.08, cleaned[i]["end"])
        cleaned[i]["end"] = min(float(duration), cleaned[i]["end"])

    return cleaned


def align_edited_transcript_to_words(
    edited_text: str,
    duration: float,
    reference_words: Optional[list[dict]] = None
) -> list[dict]:
    """
    Map an edited transcript string back to a list of word timestamp dicts.
    Preserves exact Whisper timestamps for matching words, and interpolates for edited/added words.
    """
    clean_tokens = [w.strip() for w in edited_text.split() if w.strip()]
    if not clean_tokens:
        return []

    if not reference_words:
        t_start = 0.5
        t_end = max(t_start + 1.0, float(duration) - 0.5)
        step = (t_end - t_start) / len(clean_tokens)
        res = [
            {
                "word": tok.upper(),
                "start": round(t_start + i * step, 2),
                "end": round(t_start + (i + 1) * step, 2)
            }
            for i, tok in enumerate(clean_tokens)
        ]
        return sanitize_word_timestamps(res, duration)

    if len(clean_tokens) == len(reference_words):
        res = [
            {
                "word": tok.upper(),
                "start": reference_words[i]["start"],
                "end": reference_words[i]["end"]
            }
            for i, tok in enumerate(clean_tokens)
        ]
        return sanitize_word_timestamps(res, duration)

    ref_toks = [r["word"].upper() for r in reference_words]
    new_toks = [t.upper() for t in clean_tokens]
    assigned_times = [None] * len(new_toks)
    matcher = difflib.SequenceMatcher(None, ref_toks, new_toks)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                ref_idx = i1 + offset
                new_idx = j1 + offset
                assigned_times[new_idx] = (
                    reference_words[ref_idx]["start"],
                    reference_words[ref_idx]["end"]
                )

    global_start = reference_words[0]["start"] if reference_words else 0.5
    global_end = min(float(duration) - 0.2, reference_words[-1]["end"]) if reference_words else float(duration) - 0.5
    if global_end <= global_start:
        global_end = global_start + len(new_toks) * 0.4

    idx = 0
    while idx < len(new_toks):
        if assigned_times[idx] is not None:
            idx += 1
            continue
        block_start = idx
        while idx < len(new_toks) and assigned_times[idx] is None:
            idx += 1
        block_end = idx
        prev_t = assigned_times[block_start - 1][1] if block_start > 0 else global_start
        next_t = assigned_times[block_end][0] if block_end < len(new_toks) else global_end
        if next_t <= prev_t:
            next_t = prev_t + (block_end - block_start) * 0.35
        block_len = block_end - block_start
        step = (next_t - prev_t) / block_len
        for b_i in range(block_len):
            w_s = round(prev_t + b_i * step, 2)
            w_e = round(prev_t + (b_i + 1) * step, 2)
            assigned_times[block_start + b_i] = (w_s, w_e)

    res = [
        {
            "word": new_toks[k],
            "start": assigned_times[k][0],
            "end": assigned_times[k][1]
        }
        for k in range(len(new_toks))
    ]
    return sanitize_word_timestamps(res, duration)


def transcribe_clip(audio_or_video_path: str, start_time: float, duration: float) -> list[dict]:
    """
    Extract words with timestamps relative to the clip start using faster-whisper.
    Returns list of dicts: [{'word': str, 'start': float, 'end': float}]
    """
    model = get_whisper_model()
    words = []
    
    if model:
        # Fast slice extraction with FFmpeg
        ff_bin = get_ffmpeg_cmd()
        work_dir = os.path.dirname(audio_or_video_path)
        slice_wav = os.path.join(work_dir, f"temp_slice_{int(start_time)}_{int(duration)}.wav")
        try:
            subprocess.run([
                ff_bin, "-y", "-ss", str(start_time), "-t", str(duration),
                "-i", audio_or_video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                slice_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # Transcribe only the slice
            segments, info = model.transcribe(
                slice_wav,
                word_timestamps=True,
                vad_filter=True
            )
            for seg in segments:
                for w in (seg.words or []):
                    rel_start = max(0.0, round(w.start, 2))
                    rel_end = min(duration, round(w.end, 2))
                    clean_w = re.sub(r"[^\w\s\$\%\!\?\'\-]", "", w.word).strip()
                    if clean_w and rel_end > rel_start:
                        words.append({
                            "word": clean_w.upper(),
                            "start": rel_start,
                            "end": rel_end
                        })
        except Exception as e:
            print(f"[editor] Whisper transcription error: {e}")
        finally:
            if os.path.exists(slice_wav):
                try:
                    os.remove(slice_wav)
                except Exception:
                    pass

    # If audio was silent, instrumental, or whisper failed, return clean empty list (never force fake text)
    if not words:
        return []

    return sanitize_word_timestamps(words, duration)


def generate_pacing_words(phrases: list[str] = None, duration: float = 45.0) -> list[dict]:
    """
    Generate pacing word cards across the duration ONLY when explicitly requested by user.
    """
    if not phrases:
        phrases = ["WATCH THIS", "UNBELIEVABLE MOMENT", "PAY ATTENTION", "DID YOU SEE THAT", "WAIT FOR IT", "ICONIC"]
    phrase_len = 3.0
    curr = 0.5
    idx = 0
    words = []
    while curr < duration - 1.0:
        phrase = phrases[idx % len(phrases)]
        w_list = phrase.split()
        w_step = phrase_len / len(w_list)
        for j, w in enumerate(w_list):
            words.append({
                "word": w,
                "start": round(curr + j * w_step, 2),
                "end": round(curr + (j + 1) * w_step, 2)
            })
        curr += phrase_len + 1.5
        idx += 1
    return sanitize_word_timestamps(words, duration)


def create_ass_subtitles(
    ass_path: str,
    words: list[dict],
    hook_title: str = "",
    credit_text: str = "",
    duration: float = 45.0,
    style_preset: str = "hormozi_yellow",
    hook_duration: float = 5.0,
    caption_y: int = 1540
) -> str:
    """
    Build a rock-solid ASS subtitle script with:
    - Fixed bottom-anchor positioning (\\an2\\pos(540, 1540)) that never jumps, stacks, or floats
    - Strictly non-overlapping, continuous word highlight intervals (zero collisions, zero duplication)
    - Dedicated layers for hook title (top Layer 1), watermark (corner Layer 0), and captions (lower Layer 2)
    - Configurable hook title duration (defaults to 5.0s, completely customizable)
    """
    # Color presets (ASS uses &HAABBGGRR)
    if style_preset == "beast_white":
        primary_color = "&H00FFFFFF"
        active_color = "&H0000D7FF"
    elif style_preset == "neon_cyan":
        primary_color = "&H00FFFF00"
        active_color = "&H00FF00FF"
    else:  # hormozi_yellow (default)
        primary_color = "&H0000FFFF"
        active_color = "&H0000FF00"

    ass_content = f"""[Script Info]
Title: ClipForge Vertical Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Captions,Arial,68,{primary_color},&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,6,3,2,60,60,380,1
Style: HookTitle,Arial,80,&H00FFFFFF,&H000000FF,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,1,8,4,8,80,80,380,1
Style: Watermark,Arial,32,&H70FFFFFF,&H000000FF,&H70000000,&H00000000,0,0,0,0,100,100,0,0,1,3,0,7,40,40,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # 1. Hook Title Overlay (0.0s to hook_duration) - Layer 1, fixed top position
    if hook_title:
        hook_dur_actual = max(0.5, min(duration, float(hook_duration if hook_duration is not None else 5.0)))
        hook_end_time_str = format_ass_timestamp(hook_dur_actual)
        clean_hook = hook_title.upper().strip()
        ass_content += f"Dialogue: 1,0:00:00.00,{hook_end_time_str},HookTitle,,0,0,0,,{{\\an8\\pos(540,360)\\b1\\bord7\\shad4\\c&H0000FFFF}}🔥 {clean_hook} 🔥\n"

    # 2. Creator Credit Watermark Overlay - Layer 0, fixed top-left position
    if credit_text:
        end_time_str = format_ass_timestamp(duration)
        clean_credit = credit_text.replace("\n", " ").strip()
        ass_content += f"Dialogue: 0,0:00:00.00,{end_time_str},Watermark,,0,0,0,,{{\\an7\\pos(50,80)}}cc {clean_credit}\n"

    # 3. Dynamic Word Captions - Layer 2, fixed lower position (\\an2\\pos(540, 1540))
    if words:
        words = sanitize_word_timestamps(words, duration)

        # Group words into clusters (max 3 words or max 24 chars)
        clusters = []
        cur_c = []
        cur_len = 0
        for w in words:
            w_len = len(w["word"]) + 1
            if cur_c and (len(cur_c) >= 3 or cur_len + w_len > 24 or cur_c[-1]["word"].endswith((".", "!", "?"))):
                clusters.append(cur_c)
                cur_c = []
                cur_len = 0
            cur_c.append(w)
            cur_len += w_len
        if cur_c:
            clusters.append(cur_c)

        for c_idx, cluster in enumerate(clusters):
            c_start = cluster[0]["start"]
            if c_idx + 1 < len(clusters):
                next_start = clusters[c_idx + 1][0]["start"]
                c_end = max(cluster[-1]["end"], c_start + 0.4)
                if next_start > c_start:
                    if next_start - c_end < 0.35:
                        c_end = next_start
                    else:
                        c_end = min(c_end, next_start)
                else:
                    c_end = c_start + 0.3
            else:
                c_end = min(float(duration), max(cluster[-1]["end"] + 0.25, c_start + 0.5))

            m = len(cluster)
            t_prev = c_start
            for active_idx in range(m):
                t_s = t_prev
                if active_idx == m - 1:
                    t_e = c_end
                else:
                    target = cluster[active_idx + 1]["start"]
                    remaining = m - 1 - active_idx
                    max_allowed = c_end - (remaining * 0.08)
                    t_e = max(t_s + 0.08, min(target, max_allowed))
                t_prev = t_e

                if t_e <= t_s:
                    continue

                # Build active word highlighted line without styles reset
                parts = []
                for idx, item in enumerate(cluster):
                    w_text = item["word"]
                    if idx == active_idx:
                        parts.append(f"{{\\c{active_color}\\b1}}{w_text}{{\\c{primary_color}\\b0}}")
                    else:
                        parts.append(f"{{\\c{primary_color}}}{w_text}")
                phrase_text = " ".join(parts)
                t_start_str = format_ass_timestamp(t_s)
                t_end_str = format_ass_timestamp(t_e)
                # Pin with explicit \\an2\\pos(540,1540) to guarantee rock-solid positioning
                ass_content += f"Dialogue: 2,{t_start_str},{t_end_str},Captions,,0,0,0,,{{\\an2\\pos(540,{int(caption_y)})}}{phrase_text}\n"

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return ass_path


def build_render_command(
    source_video_path: str,
    output_mp4_path: str,
    start_time: float,
    duration: float,
    layout_mode: str,
    ass_relative_filename: Optional[str],
    speed: float = 1.0,
    copyright_safe: bool = True,
    mirror_flip: bool = False,
) -> list[str]:
    """
    Construct the optimal FFmpeg command combining trimming, layout conversion,
    copyright-safe transformative framing/color-grading, playback speed adjustment,
    subtitle burn-in, and audio loudness normalization in a single pass.
    """
    ff_bin = get_ffmpeg_cmd()
    speed_val = float(speed or 1.0)
    # In copyright_safe mode, if speed is exactly 1.0, apply a subtle 1.03x cadence shift
    # that is natural to human ears/eyes while altering raw frame/audio duration fingerprints
    if copyright_safe and abs(speed_val - 1.0) < 0.005:
        speed_val = 1.03

    flip_op = ",hflip" if mirror_flip else ""
    color_op = ",eq=contrast=1.05:saturation=1.06:brightness=0.01" if copyright_safe else ""

    # Define visual layout filtergraph
    # Target: 1080x1920 @ 30 fps
    if layout_mode == "smart_crop":
        # 9:16 Center Crop: width = ih * (9/16)
        v_filter = f"[0:v]crop=ih*(9/16):ih:(iw-ih*(9/16))/2:0,scale=1080:1920:flags=lanczos{flip_op}{color_op},fps=30[base]"
    elif layout_mode == "fit_letterbox":
        # Scale to 1080 wide and pad top/bottom with black bars
        v_filter = f"[0:v]scale=1080:-2{flip_op}{color_op},pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30[base]"
    else:
        # Default: blurred_stack (cinematic blurred background + sharp centered 1080 wide video)
        v_filter = (
            "[0:v]split=2[bg_in][fg_in];"
            "[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5,eq=brightness=-0.15,fps=30[bg];"
            f"[fg_in]scale=1080:-2{flip_op}{color_op},fps=30[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[base]"
        )

    # Attach ASS subtitle filter and video/audio speed scaling
    if abs(speed_val - 1.0) >= 0.005:
        if ass_relative_filename:
            full_vfilter = f"{v_filter};[base]ass={ass_relative_filename}[subbed];[subbed]setpts=PTS/{speed_val}[outv]"
        else:
            full_vfilter = f"{v_filter};[base]setpts=PTS/{speed_val}[outv]"
        a_filter = f"atempo={speed_val},loudnorm=I=-14:LRA=11:TP=-1.5"
    else:
        if ass_relative_filename:
            full_vfilter = f"{v_filter};[base]ass={ass_relative_filename}[outv]"
        else:
            full_vfilter = f"{v_filter};[base]null[outv]"
        a_filter = "loudnorm=I=-14:LRA=11:TP=-1.5"

    cmd = [
        ff_bin, "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", source_video_path,
        "-filter_complex", full_vfilter,
        "-map", "[outv]",
        "-map", "0:a?",
        "-af", a_filter,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "21",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_mp4_path
    ]

    return cmd


# ==============================================================================
# REACTION CAM (picture-in-picture creator reaction overlay)
# ==============================================================================
FRAME_W, FRAME_H = 1080, 1920
REACTION_POSITIONS = ["bottom_right", "bottom_left", "top_right", "top_left", "bottom_strip"]
_EDGE_MARGIN = 40
_TOP_Y = 560        # below the hook title area
_BOTTOM_PAD = 140   # keep clear of platform UI at the very bottom
_STRIP_H = 640


def reaction_layout(position: str = "bottom_right", size_pct: float = 32, shape: str = "rounded") -> dict:
    """Compute reaction cam box (x, y, w, h) on the 1080x1920 frame plus a safe caption Y."""
    position = position if position in REACTION_POSITIONS else "bottom_right"
    if position == "bottom_strip":
        y = FRAME_H - _STRIP_H
        return {"x": 0, "y": y, "w": FRAME_W, "h": _STRIP_H, "caption_y": y - 40, "position": position}

    w = int(FRAME_W * max(20.0, min(50.0, float(size_pct))) / 100) // 2 * 2
    h = w if shape == "circle" else (int(w * 4 / 3) // 2 * 2)
    x = _EDGE_MARGIN if position.endswith("left") else FRAME_W - w - _EDGE_MARGIN
    y = _TOP_Y if position.startswith("top") else FRAME_H - h - _BOTTOM_PAD
    caption_y = 1540
    if position.startswith("bottom"):
        caption_y = min(1540, y - 40)
    return {"x": x, "y": y, "w": w, "h": h, "caption_y": caption_y, "position": position}


def _probe_media(path: str) -> dict:
    """Lightweight probe using ffmpeg stderr: duration and whether an audio stream exists."""
    info = {"duration": None, "has_audio": False}
    try:
        proc = subprocess.run([get_ffmpeg_cmd(), "-hide_banner", "-i", path],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                              encoding="utf-8", errors="ignore")
        err = proc.stderr or ""
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
        if m:
            info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        info["has_audio"] = bool(re.search(r"Stream #.*Audio:", err))
    except Exception as e:
        print(f"[editor] probe notice: {e}")
    return info


def _mask_expr(shape: str, radius_frac: float = 0.12) -> str:
    """geq alpha expression for circle / rounded rectangle masks."""
    if shape == "circle":
        return "if(lte(hypot(X-W/2,Y-H/2),W/2),255,0)"
    r = f"(min(W,H)*{radius_frac})"
    return (
        f"if(gt(abs(X-W/2),W/2-{r})*gt(abs(Y-H/2),H/2-{r}),"
        f"if(lte(hypot(abs(X-W/2)-(W/2-{r}),abs(Y-H/2)-(H/2-{r})),{r}),255,0),255)"
    )


def apply_reaction_overlay(
    short_path: str,
    reaction_path: str,
    position: str = "bottom_right",
    size_pct: float = 32,
    shape: str = "rounded",
    border: bool = True,
    audio_mode: str = "mix",
    clip_volume: float = 0.35,
    offset: float = 0.0,
    output_path: Optional[str] = None,
    border_color: str = "0x8B5CF6",
) -> str:
    """
    Overlay a creator reaction video onto an already-rendered 1080x1920 short.
    - position: top_left | top_right | bottom_left | bottom_right | bottom_strip
    - shape: rounded | circle (ignored for bottom_strip)
    - audio_mode: mix (clip ducked to clip_volume + reaction) | original | reaction
    - offset: seconds; >0 delays the reaction, <0 skips the start of the reaction video
    Reaction shorter than the short holds its last frame; longer is trimmed.
    """
    if not os.path.exists(short_path):
        raise FileNotFoundError(f"Short not found: {short_path}")
    if not os.path.exists(reaction_path):
        raise FileNotFoundError(f"Reaction video not found: {reaction_path}")

    if not output_path:
        base, _ = os.path.splitext(short_path)
        output_path = f"{base}_reaction.mp4"

    lay = reaction_layout(position, size_pct, shape)
    w, h, x, y = lay["w"], lay["h"], lay["x"], lay["y"]
    is_strip = lay["position"] == "bottom_strip"

    short_info = _probe_media(short_path)
    react_info = _probe_media(reaction_path)
    out_dur = short_info["duration"]
    offset = float(offset or 0.0)
    delay = max(0.0, offset)

    ff_bin = get_ffmpeg_cmd()
    cmd = [ff_bin, "-y", "-i", short_path]
    if offset < 0:
        cmd += ["-ss", str(abs(offset))]
    cmd += ["-i", reaction_path]

    # --- Video graph ---
    cam = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
           f"setsar=1,fps=30,setpts=PTS-STARTPTS+{delay}/TB")
    graph = []
    if is_strip:
        graph.append(f"{cam}[cam]")
        if border:
            graph.append(f"[cam]drawbox=x=0:y=0:w=iw:h=6:color={border_color}:t=fill[camb]")
            cam_label = "[camb]"
        else:
            cam_label = "[cam]"
    else:
        mask = _mask_expr(shape)
        graph.append(f"{cam},format=yuva420p,geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='{mask}'[cam]")
        cam_label = "[cam]"
        if border:
            b = 8
            bw, bh = w + 2 * b, h + 2 * b
            frame_mask = _mask_expr(shape, radius_frac=(0.12 * w + b) / bw) if shape != "circle" else _mask_expr("circle")
            graph.append(
                f"color=c={border_color}:s={bw}x{bh}:r=30,format=yuva420p,"
                f"geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='{frame_mask}'[ring]"
            )
            graph.append(f"[ring][cam]overlay={b}:{b}:shortest=0:eof_action=repeat[camb]")
            cam_label = "[camb]"
            x, y = x - b, y - b

    graph.append(
        f"[0:v]{cam_label}overlay={x}:{y}:eof_action=repeat:enable='gte(t,{delay})'[outv]"
    )

    # --- Audio graph ---
    audio_map = []
    mode = audio_mode if audio_mode in ("mix", "original", "reaction") else "mix"
    if mode == "reaction" and not react_info["has_audio"]:
        mode = "original"
    if mode == "mix" and not react_info["has_audio"]:
        mode = "original"
    if mode == "mix" and not short_info["has_audio"]:
        mode = "reaction"

    delay_ms = int(delay * 1000)
    if mode == "mix":
        cv = max(0.0, min(1.0, float(clip_volume)))
        graph.append(f"[0:a]volume={cv}[a0]")
        graph.append(f"[1:a]asetpts=PTS-STARTPTS,adelay={delay_ms}|{delay_ms},volume=1.0[a1]")
        graph.append("[a0][a1]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout]")
        audio_map = ["-map", "[aout]"]
    elif mode == "reaction":
        graph.append(f"[1:a]asetpts=PTS-STARTPTS,adelay={delay_ms}|{delay_ms}[aout]")
        audio_map = ["-map", "[aout]"]
    else:
        audio_map = ["-map", "0:a?"]

    cmd += ["-filter_complex", ";".join(graph), "-map", "[outv]"] + audio_map
    if out_dur:
        cmd += ["-t", f"{out_dur:.3f}"]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-b:a", "160k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        output_path,
    ]

    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                          encoding="utf-8", errors="ignore")
    if proc.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"Reaction overlay failed: {(proc.stderr or '')[-600:]}")
    return output_path


def render_short_video(
    source_video_path: str,
    clip_candidate: dict,
    video_metadata: dict,
    layout_mode: str = "blurred_stack",
    subtitle_style: str = "hormozi_yellow",
    speed: float = 1.0,
    hook_duration: Optional[float] = None,
    custom_words: Optional[list[dict]] = None,
    custom_transcript: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    reaction: Optional[dict] = None,
    copyright_safe: bool = True,
    mirror_flip: bool = False,
    ensure_captions: bool = True,
) -> dict:
    """
    Complete Phase 4 Pipeline:
    1. Transcribes clip audio or uses custom/edited word timestamps (with smart caption fallback if ensure_captions=True)
    2. Builds rock-solid non-overlapping .ass subtitles with hook title and creator watermark
    3. Renders 1080x1920 vertical MP4 using FFmpeg (with copyright-safe transformative filters, speed multiplier & loudness normalization)
    4. Registers or updates rendered clip in SQLite database
    """
    if not os.path.exists(source_video_path):
        raise FileNotFoundError(f"Source video not found: {source_video_path}")

    vid_id = video_metadata.get("video_id", "clip")
    clip_id = clip_candidate.get("clip_id", 1)
    start_time = float(clip_candidate.get("start_time", 0.0))
    duration = float(clip_candidate.get("duration", 45.0))
    end_time = float(clip_candidate.get("end_time", start_time + duration))
    hook_title = clip_candidate.get("hook_title", "")
    if hook_title is None:
        hook_title = ""
    hook_time_sec = float(hook_duration if hook_duration is not None else (clip_candidate.get("hook_duration") or clip_candidate.get("hook_time") or 5.0))
    credit_text = video_metadata.get("channel_title") or clip_candidate.get("creator") or "Original Creator"
    speed_float = float(clip_candidate.get("speed") or speed or 1.0)
    output_duration = round(duration / speed_float, 1)

    work_dir = os.path.dirname(source_video_path)
    output_filename = f"{vid_id}_short_clip_{clip_id}.mp4"
    output_mp4_path = os.path.join(work_dir, output_filename)
    ass_filename = f"subs_{vid_id}_clip_{clip_id}.ass"
    ass_path = os.path.join(work_dir, ass_filename)

    # Reaction cam: decide caption placement up-front so captions never sit under the cam
    use_reaction = bool(reaction and reaction.get("path") and os.path.exists(reaction.get("path")))
    caption_y = 1540
    if use_reaction:
        caption_y = reaction_layout(
            reaction.get("position", "bottom_right"),
            reaction.get("size_pct", 32),
            reaction.get("shape", "rounded"),
        )["caption_y"]

    if subtitle_style in ["none", "no_text", "clean"]:
        words = []
        ass_relative_name = None
        if progress_callback:
            progress_callback(30.0, f"Preparing clean vertical video ({speed_float}x speed, no text overlays)...")
    else:
        # Determine words from custom input, edited transcript, or Whisper
        ref_words = clip_candidate.get("words")

        if custom_words is not None:
            words = sanitize_word_timestamps(custom_words, duration) if custom_words else []
            if progress_callback:
                if words:
                    progress_callback(30.0, f"Applying {len(words)} custom timed words to subtitles...")
                else:
                    progress_callback(30.0, "Bottom text cleared (0 words)...")
        elif custom_transcript is not None:
            raw_text = str(custom_transcript).strip()
            if raw_text:
                words = align_edited_transcript_to_words(raw_text, duration, reference_words=ref_words)
                if progress_callback:
                    progress_callback(30.0, f"Aligned edited on-screen transcript ({len(words)} words)...")
            else:
                words = []
                if progress_callback:
                    progress_callback(30.0, "Bottom text explicitly cleared (clean lower video)...")
        elif "custom_transcript" in clip_candidate and clip_candidate["custom_transcript"] is not None:
            raw_text = str(clip_candidate["custom_transcript"]).strip()
            if raw_text:
                words = align_edited_transcript_to_words(raw_text, duration, reference_words=ref_words)
            else:
                words = []
        elif clip_candidate.get("disable_captions"):
            words = []
            if progress_callback:
                progress_callback(30.0, "Bottom captions disabled (clean lower video)...")
        elif clip_candidate.get("words"):
            words = sanitize_word_timestamps(clip_candidate["words"], duration)
            if progress_callback:
                progress_callback(30.0, f"Using {len(words)} pre-transcribed words...")
        else:
            if progress_callback:
                progress_callback(10.0, "Transcribing clip audio with Whisper word timestamps...")
            words = transcribe_clip(source_video_path, start_time, duration)
            # If audio had crowd/music only and ensure_captions is True, generate context-aware dynamic captions
            if not words and ensure_captions:
                context_phrases = [
                    hook_title.upper() if hook_title else "WATCH THIS UNREAL MOMENT",
                    "WAIT UNTIL THE VERY END",
                    re.sub(r"\[.*?\]", "", str(clip_candidate.get("rationale") or "HIGH ENGAGEMENT HIGHLIGHT")).strip().upper()[:48] or "PEAK VIRAL HIGHLIGHT",
                    "DID YOU SEE THAT HAPPEN",
                    "DROP YOUR THOUGHTS IN COMMENTS",
                    "FOLLOW FOR DAILY VIRAL SHORTS",
                ]
                words = generate_pacing_words(phrases=context_phrases, duration=duration)

        if progress_callback:
            if words:
                progress_callback(40.0, f"Generating dynamic captions & overlays ({len(words)} words)...")
            else:
                progress_callback(40.0, "No bottom captions to render (clean lower screen)...")

        # Step 2: Build ASS subtitles if any overlay (hook, watermark, or captions) exists
        clean_hook = hook_title.strip() if hook_title else ""
        clean_credit = credit_text.strip() if credit_text else ""
        if words or clean_hook or clean_credit:
            create_ass_subtitles(
                ass_path,
                words=words,
                hook_title=clean_hook,
                credit_text=clean_credit,
                duration=duration,
                style_preset=subtitle_style,
                hook_duration=hook_time_sec,
                caption_y=caption_y
            )
            ass_relative_name = ass_filename
        else:
            ass_relative_name = None

    if progress_callback:
        progress_callback(55.0, f"Rendering 1080x1920 vertical video with FFmpeg ({layout_mode} @ {speed_float}x)...")

    # Step 3: Run FFmpeg from work_dir to keep subtitle path relative
    cmd = build_render_command(
        source_video_path=source_video_path,
        output_mp4_path=output_mp4_path,
        start_time=start_time,
        duration=duration,
        layout_mode=layout_mode,
        ass_relative_filename=ass_relative_name,
        speed=speed_float,
        copyright_safe=copyright_safe,
        mirror_flip=mirror_flip,
    )

    try:
        proc = subprocess.run(
            cmd,
            cwd=work_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        # Fallback if ASS filter failed (e.g. fontconfig issue): render without subtitles
        print(f"[editor] Subtitle burn-in warning: {e.stderr[-300:] if e.stderr else 'error'}. Falling back without subtitles.")
        cmd_fallback = build_render_command(
            source_video_path=source_video_path,
            output_mp4_path=output_mp4_path,
            start_time=start_time,
            duration=duration,
            layout_mode=layout_mode,
            ass_relative_filename=None,
            speed=speed_float,
            copyright_safe=copyright_safe,
            mirror_flip=mirror_flip,
        )
        subprocess.run(cmd_fallback, cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Step 3b: Reaction cam overlay (picture-in-picture)
    if use_reaction:
        if progress_callback:
            progress_callback(80.0, "Compositing your reaction cam...")
        tmp_out = output_mp4_path.replace(".mp4", "_rx_tmp.mp4")
        try:
            apply_reaction_overlay(
                output_mp4_path,
                reaction["path"],
                position=reaction.get("position", "bottom_right"),
                size_pct=reaction.get("size_pct", 32),
                shape=reaction.get("shape", "rounded"),
                border=reaction.get("border", True),
                audio_mode=reaction.get("audio_mode", "mix"),
                clip_volume=reaction.get("clip_volume", 0.35),
                offset=reaction.get("offset", 0.0),
                output_path=tmp_out,
            )
            os.replace(tmp_out, output_mp4_path)
        except Exception as e:
            print(f"[editor] Reaction overlay warning: {e}")
            if os.path.exists(tmp_out):
                try:
                    os.remove(tmp_out)
                except Exception:
                    pass

    if progress_callback:
        progress_callback(90.0, "Saving rendered clip metadata to SQLite...")

    # Step 4: Persist in SQLite
    transcript_summary = " ".join([w["word"] for w in words]) if words else ""
    cat_val = clip_candidate.get("category") or video_metadata.get("category") or "General"
    cmd_val = clip_candidate.get("command_query") or video_metadata.get("command_query") or ""
    status_val = clip_candidate.get("status", "pending")

    existing_db_id = clip_candidate.get("clip_db_id") or clip_candidate.get("id")
    if existing_db_id:
        try:
            update_clip(int(existing_db_id), {
                "start_time": start_time,
                "end_time": end_time,
                "duration": output_duration,
                "hook_title": hook_title,
                "hook_duration": hook_time_sec,
                "caption_text": transcript_summary,
                "file_path": output_mp4_path,
                "category": cat_val,
                "command_query": cmd_val,
                "copyright_safe_mode": 1 if copyright_safe else 0,
            })
            db_clip_id = int(existing_db_id)
        except Exception:
            db_clip_id = save_clip({
                "video_id": vid_id,
                "start_time": start_time,
                "end_time": end_time,
                "duration": output_duration,
                "score": clip_candidate.get("score", 85.0),
                "rationale": clip_candidate.get("rationale", ""),
                "hook_title": hook_title,
                "hook_duration": hook_time_sec,
                "caption_text": transcript_summary,
                "status": status_val,
                "file_path": output_mp4_path,
                "category": cat_val,
                "command_query": cmd_val,
                "copyright_safe_mode": copyright_safe,
            })
    else:
        db_clip_id = save_clip({
            "video_id": vid_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration": output_duration,
            "score": clip_candidate.get("score", 85.0),
            "rationale": clip_candidate.get("rationale", ""),
            "hook_title": hook_title,
            "hook_duration": hook_time_sec,
            "caption_text": transcript_summary,
            "status": status_val,
            "file_path": output_mp4_path,
            "category": cat_val,
            "command_query": cmd_val,
            "copyright_safe_mode": copyright_safe,
        })

    if progress_callback:
        progress_callback(100.0, "Render complete! Short ready for review.")

    return {
        "success": True,
        "clip_db_id": db_clip_id,
        "clip_id": clip_id,
        "video_id": vid_id,
        "file_path": output_mp4_path,
        "duration": output_duration,
        "source_duration": duration,
        "speed": speed_float,
        "hook_title": hook_title,
        "hook_duration": hook_time_sec,
        "words": words,
        "caption_text": transcript_summary,
        "words_count": len(words),
        "layout_mode": layout_mode,
        "subtitle_style": subtitle_style,
        "copyright_safe": copyright_safe,
    }

