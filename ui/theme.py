"""Premium dark design system for ClipForge (CSS + small HTML helpers)."""

import html
import streamlit as st


from pathlib import Path

STYLE_FILE = Path(__file__).parent / "style.css"


def inject_theme():
    if hasattr(st, "html") and STYLE_FILE.exists():
        st.html(STYLE_FILE)
    elif STYLE_FILE.exists():
        with open(STYLE_FILE, "r", encoding="utf-8") as f:
            css_txt = f.read()
        st.markdown(f"<style>{css_txt}</style>", unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    st.markdown(
        f'<div class="cf-h"><div class="t">{html.escape(title)}</div>'
        f'<div class="s">{html.escape(subtitle)}</div></div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "") -> str:
    return f'<span class="cf-badge {kind}">{html.escape(str(text))}</span>'


def render_brand(socials: dict, quota: dict):
    pills = []
    for key, label in (("youtube", "YouTube"), ("tiktok", "TikTok"), ("instagram", "Instagram")):
        on = (socials.get(key) or {}).get("is_connected")
        pills.append(f'<span class="cf-pill {"on" if on else ""}">{label}{" connected" if on else ""}</span>')
    try:
        pills.append(f'<span class="cf-pill">{int(quota.get("remaining", 0)):,} API quota</span>')
    except Exception:
        pass
    st.markdown(
        f"""<div class="cf-brand"><div><div class="cf-logo">ClipForge</div>
        <div class="cf-tag">Turn long videos into ready-to-post Shorts</div></div>
        <div class="cf-pills">{''.join(pills)}</div></div>""",
        unsafe_allow_html=True,
    )


def reaction_mock_html(position: str, size_pct: int, shape: str, border: bool, captions_on: bool = True) -> str:
    """Small 9:16 mock showing where the reaction cam lands."""
    w = 150
    h = w * 16 / 9
    margin = 6
    cls = "cam border" if border else "cam"
    radius = "50%" if shape == "circle" else "10px"
    cap_bottom = 18  # percent
    if position == "bottom_strip":
        cam_h = h * 0.32
        style = f"left:0;right:0;bottom:0;height:{cam_h:.0f}px;border-radius:0;"
        cap_bottom = 36
    else:
        cw = w * size_pct / 100
        ch = cw if shape == "circle" else cw * 16 / 9 * 0.75
        top_off = h * 0.20  # pushed below hook title
        v = f"top:{top_off:.0f}px;" if position.startswith("top") else f"bottom:{margin}px;"
        hz = f"left:{margin}px;" if position.endswith("left") else f"right:{margin}px;"
        style = f"{v}{hz}width:{cw:.0f}px;height:{ch:.0f}px;border-radius:{radius};"
        if position.startswith("bottom"):
            cap_bottom = min(60, int((ch + margin * 2) / h * 100) + 2)
    cap = f'<div class="cap" style="bottom:{cap_bottom}%"></div>' if captions_on else ""
    return (
        f'<div class="cf-mock-wrap"><div class="cf-mock"><div class="hook"></div><div class="vid"></div>'
        f'{cap}<div class="{cls}" style="{style}"></div></div></div>'
    )
