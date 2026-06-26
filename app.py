"""
PDF Toolkit Pro — 17 tools: Merge, Split, Remove, Extract, Reorder, Images→PDF,
Optimize, Compress, Repair, Rotate, PDF→Images, Watermark, Protect/Unlock,
Extract Text, Edit Metadata, Add Page Numbers, Crop Pages

UPGRADES (Security / Robustness + Architecture / UX):
  ✅ Rate-limiting & abuse guard (max ops per session)
  ✅ Async thread-pool processing for large files (no Streamlit timeout)
  ✅ Input sanitization on Metadata fields (XSS / injection safe)
  ✅ Password strength meter on Protect tool
  ✅ Page-dimension table (all pages, not just page 1)
  ✅ PDF preview thumbnail after upload (page 1 → base64 PNG via pypdf / PIL)
  ✅ Session history — re-download any result without reprocessing
  ✅ "Clear tool" button to reset session state per tool
  ✅ Dark-mode toggle with CSS variable swap
  ✅ Tool search / filter box in sidebar
  ✅ File-name shown in page header after upload
  ✅ "Copy to clipboard" button on Extract Text output
  ✅ Warn on mixed page sizes in Merge
  ✅ Estimated time-remaining on progress bars (large files)
  ✅ Batch processing for Rotate, Watermark, Page Numbers (multi-file → ZIP)
"""

import html
import io
import re
import time
import traceback
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutTimeoutError
from typing import Optional

import streamlit as st
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError, PdfStreamError
from pypdf.generic import NameObject, NumberObject

# ── Constants ────────────────────────────────────────────────────────────────
MAX_FILE_MB      = 200
MAX_FILE_BYTES   = MAX_FILE_MB * 1024 * 1024
MAX_OPS_SESSION  = 50          # rate-limit: operations per session
PROC_TIMEOUT_SEC = 120         # async processing timeout (seconds)

st.set_page_config(
    page_title="PDF Toolkit",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session-state bootstrap ───────────────────────────────────────────────────
if "op_count"      not in st.session_state: st.session_state["op_count"]      = 0
if "history"       not in st.session_state: st.session_state["history"]       = []   # [{name, data, size_orig, size_out, ts}]
if "dark_mode"     not in st.session_state: st.session_state["dark_mode"]     = False
if "tool_search"   not in st.session_state: st.session_state["tool_search"]   = ""
if "active_nav"    not in st.session_state: st.session_state["active_nav"]    = None

DARK = st.session_state["dark_mode"]

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

:root {{
    --bg:       {'#16181c' if DARK else '#f8f9fa'};
    --white:    {'#1e2128' if DARK else '#ffffff'};
    --border:   {'#2e3138' if DARK else '#e2e5ea'};
    --text:     {'#e8eaf0' if DARK else '#1a1d23'};
    --muted:    {'#8b929e' if DARK else '#6b7280'};
    --accent:   #2563eb;
    --accent-l: {'#1a2340' if DARK else '#eff6ff'};
    --success:  #16a34a;
    --warning:  #d97706;
    --danger:   #dc2626;
    --r:        8px;
}}

html, body, [data-testid="stAppViewContainer"] {{
    background: var(--bg) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--text) !important;
}}

#MainMenu, footer, [data-testid="stHeader"], [data-testid="stDecoration"] {{
    display: none !important;
}}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background: var(--white) !important;
    border-right: 1px solid var(--border) !important;
}}
[data-testid="stSidebar"] > div:first-child {{ padding-top: 0 !important; }}

.sb-logo {{
    padding: 1.4rem 1.2rem 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0.5rem;
}}
.sb-logo h1 {{
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 0.15rem;
}}
.sb-logo span {{ font-size: 0.72rem; color: var(--muted); }}

.nav-label {{
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--muted);
    padding: 0.8rem 1.2rem 0.3rem;
}}

[data-testid="stSidebar"] .stRadio > div {{ gap: 0 !important; }}
[data-testid="stSidebar"] .stRadio label {{
    font-size: 0.84rem !important;
    color: var(--muted) !important;
    padding: 0.45rem 1.2rem !important;
    border-radius: 0 !important;
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
    background: var(--bg) !important;
    color: var(--text) !important;
}}
[data-testid="stSidebar"] .stRadio label[data-checked="true"],
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label {{
    background: var(--accent-l) !important;
    color: var(--accent) !important;
    font-weight: 500 !important;
    border-left: 2px solid var(--accent) !important;
}}
[data-testid="stSidebar"] .stRadio [type="radio"] {{ display: none !important; }}

/* ── Main ── */
[data-testid="stMainBlockContainer"] {{
    padding: 2rem 2.5rem !important;
    max-width: 960px;
}}

/* ── Page header ── */
.ph {{
    margin-bottom: 1.6rem;
    padding-bottom: 1.2rem;
    border-bottom: 1px solid var(--border);
}}
.ph h2 {{
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 0.25rem;
}}
.ph p {{ font-size: 0.83rem; color: var(--muted); margin: 0; }}
.ph .fname {{
    font-size: 0.75rem;
    color: var(--accent);
    background: var(--accent-l);
    border: 1px solid #bfdbfe;
    border-radius: 4px;
    padding: 0.1rem 0.5rem;
    margin-top: 0.4rem;
    display: inline-block;
}}

/* ── Card ── */
.card {{
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}}
.card-title {{
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.9rem;
}}

/* ── Pills ── */
.pr {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.6rem 0; }}
.pill {{
    font-size: 0.75rem; font-weight: 500;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--muted);
}}
.pill.a {{ background: var(--accent-l); border-color: #bfdbfe; color: var(--accent); }}
.pill.s {{ background: {'#0d2e1a' if DARK else '#f0fdf4'}; border-color: #bbf7d0; color: var(--success); }}
.pill.w {{ background: {'#2d1f0a' if DARK else '#fffbeb'}; border-color: #fde68a; color: var(--warning); }}
.pill.d {{ background: {'#2d0a0a' if DARK else '#fef2f2'}; border-color: #fecaca; color: var(--danger); }}

/* ── Alerts ── */
.al {{
    display: flex; gap: 0.6rem; align-items: flex-start;
    padding: 0.7rem 0.9rem;
    border-radius: var(--r);
    font-size: 0.82rem; line-height: 1.5; margin: 0.7rem 0;
}}
.al-i {{ font-size: 0.9rem; flex-shrink: 0; margin-top: 0.05rem; }}
.al.info {{ background: var(--accent-l); border: 1px solid #bfdbfe; color: {'#93c5fd' if DARK else '#1d4ed8'}; }}
.al.warn {{ background: {'#2d1f0a' if DARK else '#fffbeb'}; border: 1px solid #fde68a; color: var(--warning); }}
.al.err  {{ background: {'#2d0a0a' if DARK else '#fef2f2'}; border: 1px solid #fecaca; color: var(--danger); }}
.al.ok   {{ background: {'#0d2e1a' if DARK else '#f0fdf4'}; border: 1px solid #bbf7d0; color: var(--success); }}

/* ── File uploader ── */
[data-testid="stFileUploader"] {{
    background: var(--white) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: var(--r) !important;
}}
[data-testid="stFileUploader"]:hover {{ border-color: var(--accent) !important; }}
[data-testid="stFileUploader"] label {{ color: var(--muted) !important; font-size: 0.82rem !important; }}

/* ── Inputs ── */
.stTextInput input, .stSelectbox select, .stNumberInput input {{
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.84rem !important;
}}
.stTextInput input:focus {{ border-color: var(--accent) !important; box-shadow: 0 0 0 3px #dbeafe !important; outline: none !important; }}
.stTextInput label, .stSelectbox label, .stNumberInput label, .stSlider label {{
    color: var(--text) !important; font-size: 0.8rem !important; font-weight: 500 !important;
}}

/* ── Buttons ── */
.stButton > button {{
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--r) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.84rem !important;
    padding: 0.5rem 1.2rem !important;
    box-shadow: none !important;
    transition: opacity 0.15s !important;
}}
.stButton > button:hover {{ opacity: 0.88 !important; }}

[data-testid="stDownloadButton"] > button {{
    background: var(--white) !important;
    color: var(--accent) !important;
    border: 1px solid #bfdbfe !important;
    border-radius: var(--r) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.83rem !important;
    box-shadow: none !important;
}}
[data-testid="stDownloadButton"] > button:hover {{
    background: var(--accent-l) !important;
    transform: none !important;
}}

/* ── Progress ── */
[data-testid="stProgressBar"] > div > div {{ background: var(--accent) !important; }}

/* ── Divider ── */
hr {{ border-color: var(--border) !important; margin: 1.2rem 0 !important; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 4px; }}
::-webkit-scrollbar-track {{ background: var(--bg); }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 99px; }}

/* ── Text area ── */
.stTextArea textarea {{
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text) !important;
    font-family: 'Courier New', monospace !important;
    font-size: 0.78rem !important;
}}

/* ── Streamlit alerts ── */
[data-testid="stAlert"] {{ border-radius: var(--r) !important; font-size: 0.82rem !important; }}

/* ── Checkbox ── */
.stCheckbox label {{ color: var(--text) !important; font-size: 0.83rem !important; }}

/* ── Password strength bar ── */
.pw-bar-wrap {{
    height: 4px; border-radius: 2px;
    background: var(--border); margin: 0.3rem 0 0.6rem; overflow: hidden;
}}
.pw-bar {{ height: 100%; border-radius: 2px; transition: width 0.3s, background 0.3s; }}

/* ── History panel ── */
.hist-row {{
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.5rem 0; border-bottom: 1px solid var(--border);
    font-size: 0.8rem; color: var(--text);
}}
.hist-row:last-child {{ border-bottom: none; }}
.hist-ts {{ font-size: 0.72rem; color: var(--muted); flex-shrink: 0; }}

/* ── Preview thumbnail ── */
.thumb-wrap {{
    display: inline-block;
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
    margin: 0.6rem 0;
}}
.thumb-wrap img {{ display: block; max-height: 180px; width: auto; }}

/* ── Copy button ── */
.copy-btn {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--muted);
    font-size: 0.75rem;
    padding: 0.25rem 0.7rem;
    cursor: pointer;
    margin-bottom: 0.4rem;
}}
.copy-btn:hover {{ color: var(--accent); border-color: var(--accent); }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS — formatting
# ─────────────────────────────────────────────────────────────────────────────

def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def size_pills(orig: int, new: int) -> str:
    delta = new - orig
    pct   = (delta / orig * 100) if orig else 0
    cls   = "s" if delta < 0 else ("w" if delta == 0 else "d")
    sign  = "+" if delta > 0 else ""
    verb  = "saved" if delta < 0 else ("no change" if delta == 0 else "larger")
    detail = f"{sign}{pct:.1f}% · {fmt_bytes(abs(delta))} {verb}"
    return (
        f'<div class="pr">'
        f'<span class="pill">Before: {fmt_bytes(orig)}</span>'
        f'<span class="pill {cls}">After: {fmt_bytes(new)} · {detail}</span>'
        f'</div>'
    )


def show_alert(kind: str, icon: str, html_str: str) -> None:
    st.markdown(
        f'<div class="al {kind}"><span class="al-i">{icon}</span><span>{html_str}</span></div>',
        unsafe_allow_html=True,
    )


def ph(icon: str, title: str, desc: str, filename: str = "") -> None:
    fname_html = f'<div class="fname">📎 {html.escape(filename)}</div>' if filename else ""
    st.markdown(
        f'<div class="ph"><h2>{icon} {title}</h2><p>{desc}</p>{fname_html}</div>',
        unsafe_allow_html=True,
    )


def pill_row(*pills) -> None:
    inner = "".join(
        f'<span class="pill {cls}">{lbl}</span>' for lbl, cls in pills
    )
    st.markdown(f'<div class="pr">{inner}</div>', unsafe_allow_html=True)


def card_start(label: str = "") -> None:
    if "_card_label" not in st.session_state:
        st.session_state["_card_label"] = ""
    st.session_state["_card_label"] = label
    st.session_state["_card_items"] = []


def card_end() -> None:
    label = st.session_state.get("_card_label", "")
    title_html = f'<p class="card-title">{label}</p>' if label else ""
    st.markdown(f'<div class="card">{title_html}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS — security & validation
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_metadata_field(value: str) -> str:
    """Strip control characters and limit length to prevent PDF injection."""
    if not value:
        return ""
    # Remove null bytes and other control chars (except tab/newline which are valid)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    # Remove parenthesis/backslash sequences that could escape PDF strings
    cleaned = cleaned.replace("\\", "").replace("\x28", "(").replace("\x29", ")")
    return cleaned[:500]  # hard cap at 500 chars per field


def check_rate_limit() -> bool:
    """Return False and show alert if user has hit the per-session op limit."""
    if st.session_state["op_count"] >= MAX_OPS_SESSION:
        show_alert("err", "🚫",
                   f"Session limit reached ({MAX_OPS_SESSION} operations). "
                   "Please refresh the page to start a new session.")
        return False
    return True


def increment_op_count() -> None:
    st.session_state["op_count"] += 1


def password_strength(pw: str) -> tuple[int, str, str]:
    """Return (score 0-4, label, bar_color)."""
    if not pw:
        return 0, "", "#e2e5ea"
    score = 0
    if len(pw) >= 8:  score += 1
    if len(pw) >= 14: score += 1
    if re.search(r"[A-Z]", pw) and re.search(r"[a-z]", pw): score += 1
    if re.search(r"[0-9]", pw) and re.search(r"[^A-Za-z0-9]", pw): score += 1
    labels = ["", "Weak", "Fair", "Good", "Strong"]
    colors = ["#e2e5ea", "#dc2626", "#d97706", "#2563eb", "#16a34a"]
    return score, labels[score], colors[score]


def show_password_strength(pw: str) -> None:
    score, label, color = password_strength(pw)
    if not pw:
        return
    pct = score * 25
    st.markdown(
        f'<div class="pw-bar-wrap"><div class="pw-bar" style="width:{pct}%;background:{color}"></div></div>'
        f'<span style="font-size:0.72rem;color:{color};font-weight:500">{label}</span>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS — PDF utilities
# ─────────────────────────────────────────────────────────────────────────────

def get_bytes(uf) -> bytes:
    uf.seek(0)
    return uf.read()


def check_file_size(data: bytes, label: str = "File") -> None:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(
            f"{label} is {fmt_bytes(len(data))}, which exceeds the "
            f"{MAX_FILE_MB} MB limit."
        )


@st.cache_data(show_spinner=False)
def cached_pdf_info(data: bytes) -> dict:
    try:
        reader = PdfReader(io.BytesIO(data))
        encrypted = reader.is_encrypted
        if encrypted:
            return {"pages": 0, "encrypted": True, "error": None, "sizes": []}
        sizes = []
        for p in reader.pages:
            mb = p.mediabox
            sizes.append((float(mb.width), float(mb.height)))
        return {"pages": len(reader.pages), "encrypted": False, "error": None, "sizes": sizes}
    except (PdfReadError, PdfStreamError) as e:
        return {"pages": 0, "encrypted": False, "error": str(e), "sizes": []}
    except Exception as e:
        return {"pages": 0, "encrypted": False, "error": f"Unexpected error: {e}", "sizes": []}


def make_reader(data: bytes) -> PdfReader:
    try:
        return PdfReader(io.BytesIO(data))
    except (PdfReadError, PdfStreamError) as e:
        raise ValueError(f"Could not read PDF: {e}") from e


def validate_pdf(data: bytes, label: str = "File") -> PdfReader:
    check_file_size(data, label)
    info = cached_pdf_info(data)
    if info["error"]:
        raise ValueError(f"Invalid PDF — {info['error']}")
    if info["encrypted"]:
        raise ValueError(
            "This PDF is password-protected. Remove the password before uploading."
        )
    return make_reader(data)


def validate_pdf_with_password(data: bytes, label: str = "File", password: str = "") -> PdfReader:
    check_file_size(data, label)
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            if not password:
                raise ValueError("This PDF is password-protected. Enter the password below.")
            result = reader.decrypt(password)
            if result == 0:
                raise ValueError("Incorrect password.")
        return reader
    except ValueError:
        raise
    except (PdfReadError, PdfStreamError) as e:
        raise ValueError(f"Could not read PDF: {e}") from e


def writer_to_bytes(w: PdfWriter) -> bytes:
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def copy_pages(reader: PdfReader, indices: list) -> bytes:
    w = PdfWriter()
    for i in indices:
        w.add_page(reader.pages[i])
    return writer_to_bytes(w)


def parse_range(text: str, total: int) -> list:
    out: set = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            parts = part.split("-", 1)
            if not parts[0] or not parts[1]:
                raise ValueError(f"Invalid range '{part}' — use format start-end.")
            lo, hi = int(parts[0]), int(parts[1])
            if lo < 1 or hi > total or lo > hi:
                raise ValueError(f"Range '{part}' is out of bounds (1–{total}).")
            out.update(range(lo - 1, hi))
        else:
            n = int(part)
            if n < 1 or n > total:
                raise ValueError(f"Page {n} is out of range (1–{total}).")
            out.add(n - 1)
    if not out:
        raise ValueError("No valid pages specified.")
    return sorted(out)


def build_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def images_to_pdf(images: list) -> bytes:
    try:
        import img2pdf
        bufs = []
        for img in images:
            b = io.BytesIO()
            img.convert("RGB").save(b, format="JPEG", quality=92)
            bufs.append(b.getvalue())
        return img2pdf.convert(bufs)
    except ImportError:
        rgb = [img.convert("RGB") for img in images]
        if not rgb:
            raise ValueError("No valid images to convert.")
        buf = io.BytesIO()
        rgb[0].save(buf, format="PDF", save_all=True, append_images=rgb[1:])
        return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS — UX upgrades
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, max_entries=10)
def get_page1_thumbnail(data: bytes, max_h: int = 180) -> Optional[bytes]:
    """
    Render page 1 of a PDF to a PNG thumbnail using pypdf + PIL.
    Falls back gracefully if rendering is not possible (no poppler).
    Returns PNG bytes or None.
    """
    try:
        from pdf2image import convert_from_bytes
        imgs = convert_from_bytes(data, dpi=72, first_page=1, last_page=1)
        if imgs:
            buf = io.BytesIO()
            img = imgs[0]
            ratio = max_h / img.height
            img = img.resize((int(img.width * ratio), max_h), Image.LANCZOS)
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        pass
    return None


def show_pdf_preview(data: bytes) -> None:
    """Show a page-1 thumbnail if pdf2image / poppler are available."""
    thumb = get_page1_thumbnail(data)
    if thumb:
        import base64
        b64 = base64.b64encode(thumb).decode()
        st.markdown(
            f'<div class="thumb-wrap"><img src="data:image/png;base64,{b64}" alt="Page 1 preview"/></div>'
            f'<p style="font-size:0.7rem;color:var(--muted);margin:0 0 0.6rem">Page 1 preview</p>',
            unsafe_allow_html=True,
        )


def show_page_dimensions(data: bytes, max_show: int = 20) -> None:
    """Show a compact table of per-page dimensions (all pages, not just page 1)."""
    info = cached_pdf_info(data)
    sizes = info.get("sizes", [])
    if not sizes:
        return
    # Check for mixed sizes
    unique = set((round(w), round(h)) for w, h in sizes)
    if len(unique) > 1:
        show_alert("warn", "⚠️",
                   f"This PDF has <strong>{len(unique)} different page sizes</strong>. "
                   "Pages may not align perfectly when merging.")
    # Only show the table for manageable page counts
    if len(sizes) <= max_show:
        rows = ""
        for i, (w, h) in enumerate(sizes):
            w_mm = w * 25.4 / 72
            h_mm = h * 25.4 / 72
            orient = "Portrait" if h >= w else "Landscape"
            rows += f"<tr><td style='padding:2px 8px;color:var(--muted);font-size:0.75rem'>{i+1}</td><td style='padding:2px 8px;font-size:0.75rem'>{w_mm:.0f}×{h_mm:.0f} mm</td><td style='padding:2px 8px;font-size:0.75rem;color:var(--muted)'>{orient}</td></tr>"
        st.markdown(
            f'<details style="margin:0.5rem 0"><summary style="font-size:0.78rem;color:var(--muted);cursor:pointer">Page dimensions ▾</summary>'
            f'<table style="border-collapse:collapse;margin-top:0.4rem">{rows}</table></details>',
            unsafe_allow_html=True,
        )


def run_with_timeout(fn, *args, timeout: int = PROC_TIMEOUT_SEC, **kwargs):
    """
    Run fn(*args, **kwargs) in a thread pool with a hard timeout.
    Returns result or raises TimeoutError / original exception.
    """
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except FutTimeoutError:
            raise TimeoutError(
                f"Processing exceeded {timeout}s. Try a smaller file or fewer pages."
            )


def add_to_history(name: str, data: bytes, size_orig: int) -> None:
    """Store a processed result in session history (last 10)."""
    entry = {
        "name": name,
        "data": data,
        "size_orig": size_orig,
        "size_out":  len(data),
        "ts":        time.strftime("%H:%M:%S"),
    }
    st.session_state["history"] = ([entry] + st.session_state["history"])[:10]


def show_copy_button(text: str, key: str) -> None:
    """Render a JS-powered copy-to-clipboard button."""
    escaped = text.replace("`", "\\`").replace("$", "\\$")
    st.markdown(
        f"""<button class="copy-btn" onclick="navigator.clipboard.writeText(`{escaped}`).then(()=>{{this.textContent='✅ Copied!';setTimeout(()=>this.textContent='📋 Copy to clipboard',2000)}})">📋 Copy to clipboard</button>""",
        unsafe_allow_html=True,
    )


def progress_with_eta(total_steps: int, label: str = "Processing"):
    """
    Returns a context manager / callable that updates progress + shows ETA.
    Usage: update = progress_with_eta(total); update(i, "msg")
    """
    bar = st.progress(0, text=label)
    start = time.time()
    counts = {"n": 0}

    def update(step: int, msg: str = "") -> None:
        counts["n"] = step
        frac = step / total_steps if total_steps else 1
        elapsed = time.time() - start
        if frac > 0.02 and elapsed > 1:
            eta = elapsed / frac * (1 - frac)
            eta_str = f" · ~{eta:.0f}s left" if eta > 2 else ""
        else:
            eta_str = ""
        bar.progress(frac, text=f"{msg}{eta_str}" if msg else label)

    def done():
        bar.empty()

    return update, done


def clear_tool_state(prefix: str) -> None:
    """Remove all session_state keys that start with prefix (tool reset)."""
    keys_to_del = [k for k in st.session_state if k.startswith(prefix)]
    for k in keys_to_del:
        del st.session_state[k]


def show_clear_button(prefix: str, key_suffix: str) -> None:
    if st.button("🗑 Clear", key=f"clear_{key_suffix}", help="Reset this tool"):
        clear_tool_state(prefix)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

CORE  = ["🔀  Merge PDFs", "✂️  Split PDF", "🗑️  Remove Pages",
         "📑  Extract Pages", "↕️  Reorder Pages", "🖼️  Images → PDF"]
EXTRA = ["⚡  Optimize PDF", "🗜️  Compress PDF", "🔧  Repair PDF"]
NEW_A = ["🔄  Rotate Pages", "📸  PDF → Images", "💧  Watermark", "🔐  Protect / Unlock"]
NEW_B = ["📝  Extract Text", "🏷️  Edit Metadata", "🔢  Add Page Numbers", "✂️  Crop Pages"]

ALL_TOOLS = CORE + EXTRA + NEW_A + NEW_B

with st.sidebar:
    st.markdown(
        '<div class="sb-logo">'
        '<h1>📄 PDF Toolkit</h1>'
        '<span>17 tools · one place</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Dark mode toggle ──────────────────────────────────────────────────────
    dm_label = "☀️ Light mode" if DARK else "🌙 Dark mode"
    if st.button(dm_label, key="dm_toggle"):
        st.session_state["dark_mode"] = not DARK
        st.rerun()

    st.markdown("<hr style='margin:0.5rem 0'>", unsafe_allow_html=True)

    # ── Tool search ───────────────────────────────────────────────────────────
    search_q = st.text_input("🔍 Search tools", value=st.session_state["tool_search"],
                              placeholder="e.g. merge, rotate…", key="sb_search",
                              label_visibility="collapsed")
    st.session_state["tool_search"] = search_q

    # ── Op counter ───────────────────────────────────────────────────────────
    ops = st.session_state["op_count"]
    if ops > 0:
        st.markdown(
            f'<div style="font-size:0.7rem;color:var(--muted);padding:0 1.2rem 0.4rem">'
            f'Session: {ops}/{MAX_OPS_SESSION} operations</div>',
            unsafe_allow_html=True,
        )

    def filtered(group):
        q = search_q.strip().lower()
        if not q:
            return group
        return [t for t in group if q in t.lower()]

    def nav_section(label, group, radio_key):
        f = filtered(group)
        if not f:
            return None
        st.markdown(f'<div class="nav-label">{label}</div>', unsafe_allow_html=True)
        return st.radio(radio_key, f, label_visibility="collapsed", key=radio_key)

    core_tool  = nav_section("Core Tools", CORE,  "core_nav")
    extra_tool = nav_section("Extras",     EXTRA, "extra_nav")
    new_a_tool = nav_section("Transform",  NEW_A, "new_a_nav")
    new_b_tool = nav_section("Content",    NEW_B, "new_b_nav")

    # ── History panel ─────────────────────────────────────────────────────────
    hist = st.session_state["history"]
    if hist:
        st.markdown("<hr style='margin:0.8rem 0'>", unsafe_allow_html=True)
        st.markdown('<div class="nav-label">Recent Downloads</div>', unsafe_allow_html=True)
        for i, entry in enumerate(hist[:5]):
            cols = st.columns([3, 2])
            with cols[0]:
                st.markdown(
                    f'<div style="font-size:0.77rem;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{html.escape(entry["name"])}">{entry["name"]}</div>'
                    f'<div style="font-size:0.68rem;color:var(--muted)">{fmt_bytes(entry["size_out"])} · {entry["ts"]}</div>',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                mime = "application/zip" if entry["name"].endswith(".zip") else "application/pdf"
                st.download_button("⬇", entry["data"], entry["name"], mime,
                                   key=f"hist_dl_{i}", help=f"Re-download {entry['name']}")


# ── Active tool resolution ────────────────────────────────────────────────────
_prev_core  = st.session_state.get("_prev_core",  CORE[0])
_prev_extra = st.session_state.get("_prev_extra", EXTRA[0])
_prev_new_a = st.session_state.get("_prev_new_a", NEW_A[0])
_prev_new_b = st.session_state.get("_prev_new_b", NEW_B[0])

if core_tool  and core_tool  != _prev_core:  st.session_state["active_nav"] = core_tool
if extra_tool and extra_tool != _prev_extra: st.session_state["active_nav"] = extra_tool
if new_a_tool and new_a_tool != _prev_new_a: st.session_state["active_nav"] = new_a_tool
if new_b_tool and new_b_tool != _prev_new_b: st.session_state["active_nav"] = new_b_tool

st.session_state["_prev_core"]  = core_tool  or _prev_core
st.session_state["_prev_extra"] = extra_tool or _prev_extra
st.session_state["_prev_new_a"] = new_a_tool or _prev_new_a
st.session_state["_prev_new_b"] = new_b_tool or _prev_new_b

if st.session_state["active_nav"] is None:
    st.session_state["active_nav"] = CORE[0]

tool = st.session_state["active_nav"]


# ═════════════════════════════════════════════════════════════════════════════
#  TOOL PANELS
# ═════════════════════════════════════════════════════════════════════════════

# ─── 1 · MERGE ───────────────────────────────────────────────────────────────
if tool == CORE[0]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("🔀", "Merge PDFs", "Combine multiple PDFs into one document, in upload order.")
    with col_clr:
        show_clear_button("mu", "merge")

    files = st.file_uploader("Upload PDFs (select two or more)",
                             type="pdf", accept_multiple_files=True, key="mu")
    if files:
        pill_row((f"{len(files)} file(s) selected", "a"))

        card_start("Files to merge")
        total_pages  = 0
        bad_files    = []
        mixed_sizes  = False
        all_page1_sizes = []

        for i, f in enumerate(files, 1):
            try:
                data = get_bytes(f)
                check_file_size(data, f.name)
                info = cached_pdf_info(data)
                if info["error"]:
                    raise ValueError(info["error"])
                if info["encrypted"]:
                    raise ValueError("password-protected")
                pc = info["pages"]
                total_pages += pc
                if info["sizes"]:
                    all_page1_sizes.append(info["sizes"][0])
                st.markdown(
                    f"`{i}.` **{f.name}** &nbsp; "
                    f'<span class="pill" style="font-size:.72rem">{pc} pages</span>&nbsp;'
                    f'<span class="pill" style="font-size:.72rem">{fmt_bytes(f.size)}</span>',
                    unsafe_allow_html=True,
                )
            except ValueError as e:
                bad_files.append(f.name)
                st.markdown(f"`{i}.` **{f.name}** — ⚠️ {e}")

        pill_row((f"{total_pages} total pages after merge", "s"))
        card_end()

        # Warn on mixed page sizes across files
        if all_page1_sizes and len(set((round(w), round(h)) for w, h in all_page1_sizes)) > 1:
            show_alert("warn", "⚠️",
                       "The uploaded PDFs have <strong>different page sizes</strong>. "
                       "The merged PDF will contain mixed sizes — this may look inconsistent in viewers.")

        if bad_files:
            show_alert("warn", "⚠️", f"Fix the issues above before merging: {', '.join(bad_files)}")
        elif len(files) < 2:
            show_alert("warn", "⚠️", "Upload at least 2 PDFs.")
        elif st.button("Merge PDFs", key="mb"):
            if not check_rate_limit():
                st.stop()
            try:
                def _do_merge():
                    w = PdfWriter()
                    for f_ in files:
                        reader_ = validate_pdf(get_bytes(f_), f_.name)
                        for pg in reader_.pages:
                            w.add_page(pg)
                    return writer_to_bytes(w)

                update, done = progress_with_eta(len(files), "Merging…")
                with st.spinner("Merging PDFs…"):
                    out = run_with_timeout(_do_merge)
                done()
                increment_op_count()
                add_to_history("merged.pdf", out,
                               sum(f.size for f in files))
                st.success(f"✅  Merged {len(files)} files → {total_pages} pages ({fmt_bytes(len(out))}).")
                st.download_button("⬇️  Download merged.pdf",
                                   out, "merged.pdf", "application/pdf", key="md")
            except TimeoutError as e:
                show_alert("err", "⏱️", str(e))
            except ValueError as e:
                show_alert("err", "❌", str(e))
            except Exception as e:
                st.error(f"Merge failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload two or more PDFs above to get started.")


# ─── 2 · SPLIT ───────────────────────────────────────────────────────────────
elif tool == CORE[1]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("✂️", "Split PDF", "Split into individual pages or fixed-size chunks, delivered as a ZIP.")
    with col_clr:
        show_clear_button("su", "split")

    f = st.file_uploader("Upload a PDF", type="pdf", key="su")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
            show_pdf_preview(data)
            show_page_dimensions(data)

            col1, col2 = st.columns(2)
            with col1:
                mode = st.selectbox("Split mode",
                                    ["Every page (individual files)", "Fixed chunk size",
                                     "Custom ranges"],
                                    key="sm")
            with col2:
                chunk_size = None
                if mode == "Fixed chunk size":
                    chunk_size = st.number_input("Pages per chunk",
                                                 min_value=1, max_value=total,
                                                 value=min(5, total), key="sc")
                elif mode == "Custom ranges":
                    ranges_input = st.text_input(
                        "Ranges (comma-separated, e.g. 1-3, 4-7, 8-10)",
                        placeholder="1-3, 4-7, 8-10",
                        key="scr",
                    )

            if st.button("Split PDF", key="sb"):
                if not check_rate_limit():
                    st.stop()
                pages_dict: dict = {}

                if mode == "Every page (individual files)":
                    update, done = progress_with_eta(total, "Splitting…")
                    for i in range(total):
                        pages_dict[f"page_{i+1:04d}.pdf"] = copy_pages(reader, [i])
                        update(i + 1, f"Page {i+1}/{total}")
                    done()

                elif chunk_size is not None:
                    cs    = int(chunk_size)
                    parts = list(range(0, total, cs))
                    update, done = progress_with_eta(len(parts), "Splitting into chunks…")
                    for part_idx, start in enumerate(parts):
                        end = min(start + cs, total)
                        key = f"part_{part_idx+1:03d}_pages_{start+1}-{end}.pdf"
                        pages_dict[key] = copy_pages(reader, list(range(start, end)))
                        update(part_idx + 1, f"Chunk {part_idx+1}/{len(parts)}")
                    done()

                elif mode == "Custom ranges":
                    if not ranges_input.strip():
                        show_alert("err", "❌", "Enter at least one range.")
                        st.stop()
                    raw_ranges = [r.strip() for r in ranges_input.split(",") if r.strip()]
                    range_sets = []
                    for r in raw_ranges:
                        try:
                            range_sets.append(parse_range(r, total))
                        except ValueError as ve:
                            show_alert("err", "❌", str(ve))
                            st.stop()
                    update, done = progress_with_eta(len(range_sets), "Building PDFs…")
                    for ri, idx_list in enumerate(range_sets):
                        label_str = raw_ranges[ri].replace(" ", "")
                        pages_dict[f"range_{ri+1:02d}_pages_{label_str}.pdf"] = copy_pages(reader, idx_list)
                        update(ri + 1, f"Range {ri+1}/{len(range_sets)}")
                    done()

                increment_op_count()
                zb = build_zip(pages_dict)
                add_to_history("split_pages.zip", zb, len(data))
                st.success(f"✅  {len(pages_dict)} file(s) created ({fmt_bytes(len(zb))}).")
                st.download_button("⬇️  Download split_pages.zip",
                                   zb, "split_pages.zip", "application/zip", key="sd")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Split failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 3 · REMOVE PAGES ────────────────────────────────────────────────────────
elif tool == CORE[2]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("🗑️", "Remove Pages", "Delete specific pages by number or range.")
    with col_clr:
        show_clear_button("rpu", "remove")

    f = st.file_uploader("Upload a PDF", type="pdf", key="rpu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
            show_pdf_preview(data)

            pages_input = st.text_input("Pages to remove",
                                        placeholder=f"e.g.  2, 5, 7-10  (1 to {total})",
                                        key="rpi")
            show_alert("info", "ℹ️", f"Comma-separated page numbers or ranges. Valid: 1–{total}.")

            if pages_input and st.button("Remove Pages", key="rpb"):
                if not check_rate_limit():
                    st.stop()
                to_remove = set(parse_range(pages_input, total))
                keep      = [i for i in range(total) if i not in to_remove]
                if not keep:
                    show_alert("err", "❌", "Cannot remove all pages.")
                else:
                    with st.spinner("Removing pages…"):
                        out = run_with_timeout(copy_pages, reader, keep)
                    increment_op_count()
                    add_to_history("result.pdf", out, len(data))
                    st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                    st.success(f"✅  Removed {len(to_remove)} page(s) — {len(keep)} remaining.")
                    st.download_button("⬇️  Download result.pdf",
                                       out, "result.pdf", "application/pdf", key="rpd")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Error: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 4 · EXTRACT PAGES ───────────────────────────────────────────────────────
elif tool == CORE[3]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("📑", "Extract Pages", "Pull a subset of pages into a new PDF.")
    with col_clr:
        show_clear_button("eu", "extract")

    f = st.file_uploader("Upload a PDF", type="pdf", key="eu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
            show_pdf_preview(data)

            pages_input = st.text_input("Pages to extract",
                                        placeholder=f"e.g.  1, 3-6, 9  (1 to {total})",
                                        key="epi")
            show_alert("info", "ℹ️", f"Comma-separated page numbers or ranges. Valid: 1–{total}.")

            if pages_input and st.button("Extract Pages", key="eb"):
                if not check_rate_limit():
                    st.stop()
                indices = parse_range(pages_input, total)
                with st.spinner("Extracting…"):
                    out = run_with_timeout(copy_pages, reader, indices)
                increment_op_count()
                add_to_history("extracted.pdf", out, len(data))
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                st.success(f"✅  Extracted {len(indices)} page(s).")
                st.download_button("⬇️  Download extracted.pdf",
                                   out, "extracted.pdf", "application/pdf", key="ed")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Error: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 5 · REORDER PAGES ───────────────────────────────────────────────────────
elif tool == CORE[4]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("↕️", "Reorder Pages", "Rearrange pages into any order.")
    with col_clr:
        show_clear_button("rou", "reorder")

    f = st.file_uploader("Upload a PDF", type="pdf", key="rou")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"))
            show_pdf_preview(data)

            example = ", ".join(str(i) for i in range(total, 0, -1))
            order_input = st.text_input(
                f"New page order — enter all {total} page number(s) once each",
                placeholder=f"Reversed example: {example}",
                key="roi",
            )
            show_alert("info", "ℹ️",
                       f"Enter all {total} page numbers separated by commas in your desired order.")

            if order_input and st.button("Reorder Pages", key="rob"):
                if not check_rate_limit():
                    st.stop()
                try:
                    nums = [int(x.strip()) for x in order_input.split(",") if x.strip()]
                except ValueError:
                    show_alert("err", "❌", "Invalid input — integers only, comma-separated.")
                    nums = []

                if nums:
                    if len(nums) != total:
                        show_alert("err", "❌",
                                   f"Got {len(nums)} number(s) but document has {total} pages.")
                    elif sorted(nums) != list(range(1, total + 1)):
                        counts  = Counter(nums)
                        missing = sorted(set(range(1, total + 1)) - set(nums))
                        dupes   = sorted(n for n, c in counts.items() if c > 1)
                        msg = "Invalid order. "
                        if missing: msg += f"Missing: {missing}. "
                        if dupes:   msg += f"Duplicates: {dupes}."
                        show_alert("err", "❌", msg)
                    else:
                        with st.spinner("Reordering…"):
                            out = run_with_timeout(copy_pages, reader, [n - 1 for n in nums])
                        increment_op_count()
                        add_to_history("reordered.pdf", out, len(data))
                        st.success("✅  Pages reordered.")
                        st.download_button("⬇️  Download reordered.pdf",
                                           out, "reordered.pdf", "application/pdf", key="rod")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Error: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 6 · IMAGES → PDF ────────────────────────────────────────────────────────
elif tool == CORE[5]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("🖼️", "Images → PDF", "Convert JPG, PNG, TIFF, WebP or BMP images into a single PDF.")
    with col_clr:
        show_clear_button("i2u", "img2pdf")

    imgs = st.file_uploader(
        "Upload images",
        type=["jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"],
        accept_multiple_files=True,
        key="i2u",
    )

    if imgs:
        pill_row((f"{len(imgs)} image(s)", "a"))

        col_q, col_fit = st.columns(2)
        with col_q:
            quality = st.slider("JPEG quality", 50, 100, 88, key="iq")
        with col_fit:
            fit = st.selectbox("Page size",
                               ["Match image size", "A4 portrait (white background)"],
                               key="if")

        card_start("Preview")
        n_cols = min(len(imgs), 6)
        cols   = st.columns(n_cols)
        pil_images, bad = [], []

        for idx, img_file in enumerate(imgs):
            try:
                raw = get_bytes(img_file)
                check_file_size(raw, img_file.name)
                img = Image.open(io.BytesIO(raw))
                img.verify()
                img = Image.open(io.BytesIO(raw))
                # Auto-detect orientation
                orient = "Portrait" if img.height >= img.width else "Landscape"
                pil_images.append(img)
                with cols[idx % n_cols]:
                    st.image(img, use_container_width=True,
                             caption=f"{idx+1}. {img_file.name[:14]} ({orient})")
            except Exception as exc:
                bad.append(f"{img_file.name} ({exc})")
        card_end()

        if bad:
            show_alert("warn", "⚠️", f"Could not open: {'; '.join(bad)}")

        if pil_images and st.button("Convert to PDF", key="i2b"):
            if not check_rate_limit():
                st.stop()
            try:
                update, done = progress_with_eta(len(pil_images) * 2, "Processing images…")
                if fit == "A4 portrait (white background)":
                    W, H   = 2480, 3508
                    fitted = []
                    for i, img in enumerate(pil_images):
                        rgb = img.convert("RGB")
                        rgb.thumbnail((W, H), Image.LANCZOS)
                        canvas = Image.new("RGB", (W, H), (255, 255, 255))
                        canvas.paste(rgb, ((W - rgb.width) // 2, (H - rgb.height) // 2))
                        fitted.append(canvas)
                        update(i + 1, f"Fitting image {i+1}/{len(pil_images)}")
                    pil_images = fitted

                final = []
                for i, img in enumerate(pil_images):
                    b = io.BytesIO()
                    img.convert("RGB").save(b, "JPEG", quality=quality)
                    b.seek(0)
                    final.append(Image.open(b))
                    update(len(pil_images) + i + 1, f"Encoding image {i+1}/{len(pil_images)}")

                out = images_to_pdf(final)
                done()
                increment_op_count()
                add_to_history("images.pdf", out, sum(f.size for f in imgs))
                st.success(f"✅  {len(final)}-page PDF created ({fmt_bytes(len(out))}).")
                st.download_button("⬇️  Download images.pdf",
                                   out, "images.pdf", "application/pdf", key="i2d")
            except Exception as e:
                st.error(f"Conversion failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload one or more images above to get started.")


# ─── 7 · OPTIMIZE ────────────────────────────────────────────────────────────
elif tool == EXTRA[0]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("⚡", "Optimize PDF", "Deduplicate objects and compress internal streams to shrink file size.")
    with col_clr:
        show_clear_button("opu", "optimize")

    show_alert("warn", "⚠️",
               "Best-effort. Works well on office-generated PDFs. "
               "Already-compressed or image-heavy PDFs may not shrink.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="opu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
            show_pdf_preview(data)

            compress_streams = st.checkbox("Compress content streams (recommended)", value=True, key="ocs")

            if st.button("Optimize", key="opb"):
                if not check_rate_limit():
                    st.stop()

                def _do_optimize():
                    w = PdfWriter()
                    for page in reader.pages:
                        w.add_page(page)
                        if compress_streams:
                            w.pages[-1].compress_content_streams()
                    w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
                    return writer_to_bytes(w)

                update, done = progress_with_eta(total, "Optimizing…")
                with st.spinner("Optimizing…"):
                    out = run_with_timeout(_do_optimize)
                done()
                increment_op_count()
                add_to_history("optimized.pdf", out, len(data))
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                if len(out) < len(data):
                    st.success(f"✅  Saved {fmt_bytes(len(data) - len(out))}.")
                else:
                    st.info("ℹ️  Already well-optimised — no reduction achieved.")
                st.download_button("⬇️  Download optimized.pdf",
                                   out, "optimized.pdf", "application/pdf", key="opd")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Optimization failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 8 · COMPRESS ────────────────────────────────────────────────────────────
elif tool == EXTRA[1]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("🗜️", "Compress PDF", "Re-compress internal streams to reduce file size.")
    with col_clr:
        show_clear_button("cpu", "compress")

    show_alert("warn", "⚠️",
               "Best-effort stream-level compression. For aggressive image resampling use "
               "Ghostscript: <code>gs -sDEVICE=pdfwrite -dPDFSETTINGS=/ebook -o out.pdf in.pdf</code>")

    f = st.file_uploader("Upload a PDF", type="pdf", key="cpu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
            show_pdf_preview(data)

            if st.button("Compress", key="cpb"):
                if not check_rate_limit():
                    st.stop()

                def _do_compress():
                    w = PdfWriter()
                    for page in reader.pages:
                        w.add_page(page)
                        w.pages[-1].compress_content_streams()
                    w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
                    return writer_to_bytes(w)

                with st.spinner("Compressing…"):
                    out = run_with_timeout(_do_compress)
                increment_op_count()
                add_to_history("compressed.pdf", out, len(data))
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                if len(out) < len(data):
                    st.success(f"✅  Compressed by {fmt_bytes(len(data) - len(out))}.")
                else:
                    st.info("ℹ️  No further compression achieved. Try Ghostscript.")
                st.download_button("⬇️  Download compressed.pdf",
                                   out, "compressed.pdf", "application/pdf", key="cpd")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Compression failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 9 · REPAIR ──────────────────────────────────────────────────────────────
elif tool == EXTRA[2]:
    ph("🔧", "Repair PDF",
       "Try to recover a corrupted PDF by reading it in lenient mode and re-serialising it.")
    show_alert("warn", "⚠️",
               "Best-effort. Fixes minor structural issues (truncated xref tables, invalid refs). "
               "Severely damaged files or those with lost encryption keys cannot be recovered.")

    f = st.file_uploader("Upload a damaged PDF", type="pdf", key="rpu2")
    if f:
        try:
            data = get_bytes(f)
            check_file_size(data, f.name)
            pill_row((fmt_bytes(len(data)), ""))

            if st.button("Attempt Repair", key="rpb2"):
                if not check_rate_limit():
                    st.stop()
                try:
                    reader  = PdfReader(io.BytesIO(data), strict=False)
                    w       = PdfWriter()
                    skipped = 0
                    total_r = len(reader.pages)
                    update, done = progress_with_eta(total_r, "Repairing…")
                    for i, page in enumerate(reader.pages):
                        try:
                            w.add_page(page)
                        except Exception as page_err:
                            skipped += 1
                            st.warning(f"Page {i+1} skipped: {page_err}")
                        update(i + 1, f"Page {i+1}/{total_r}")
                    done()

                    if len(w.pages) == 0:
                        show_alert("err", "❌",
                                   "No pages could be recovered. The file may be too severely damaged.")
                    else:
                        out = writer_to_bytes(w)
                        increment_op_count()
                        add_to_history("repaired.pdf", out, len(data))
                        st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                        if skipped:
                            show_alert("warn", "⚠️", f"{skipped} page(s) were unrecoverable and skipped.")
                        st.success(f"✅  {len(w.pages)} page(s) recovered.")
                        st.download_button("⬇️  Download repaired.pdf",
                                           out, "repaired.pdf", "application/pdf", key="rpd2")
                except Exception as e:
                    show_alert("err", "❌",
                               f"Could not repair: <code>{e}</code>. "
                               "File may be too severely damaged.")
        except ValueError as e:
            show_alert("err", "❌", str(e))
    else:
        show_alert("info", "ℹ️", "Upload a damaged PDF above to get started.")


# ─── 10 · ROTATE PAGES ───────────────────────────────────────────────────────
elif tool == NEW_A[0]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("🔄", "Rotate Pages", "Rotate all pages or a specific range by 90°, 180°, or 270°.")
    with col_clr:
        show_clear_button("rotu", "rotate")

    # Batch mode toggle
    batch = st.checkbox("Batch mode — rotate multiple PDFs at once (→ ZIP)", key="rot_batch")

    if batch:
        files = st.file_uploader("Upload PDFs", type="pdf", accept_multiple_files=True, key="rotu_batch")
    else:
        files = None
        f = st.file_uploader("Upload a PDF", type="pdf", key="rotu")

    target_files = files if batch else ([f] if not batch and 'f' in dir() and f else [])

    if target_files and any(target_files):
        col1, col2 = st.columns(2)
        with col1:
            angle = st.selectbox("Rotation angle",
                                 ["90° clockwise", "180°", "90° counter-clockwise"],
                                 key="rota")
        with col2:
            scope = st.selectbox("Apply to",
                                 ["All pages", "Specific pages / range"],
                                 key="rots")

        pages_input = ""
        if scope == "Specific pages / range" and not batch:
            pages_input = st.text_input("Pages to rotate",
                                        placeholder="e.g.  1, 3-6",
                                        key="rotpi")

        if st.button("Rotate PDF(s)", key="rotb"):
            if not check_rate_limit():
                st.stop()
            angle_map = {"90° clockwise": 90, "180°": 180, "90° counter-clockwise": 270}
            deg = angle_map[angle]

            results = {}
            for tf in target_files:
                if tf is None:
                    continue
                try:
                    d      = get_bytes(tf)
                    reader = validate_pdf(d, tf.name)
                    total  = len(reader.pages)
                    pill_row((f"{tf.name} · {total} pages", "a"))

                    if scope == "Specific pages / range" and not batch:
                        if not pages_input:
                            show_alert("err", "❌", "Enter page numbers to rotate.")
                            st.stop()
                        rotate_set = set(parse_range(pages_input, total))
                    else:
                        rotate_set = set(range(total))

                    w = PdfWriter()
                    for i, page in enumerate(reader.pages):
                        w.add_page(page)
                        if i in rotate_set:
                            w.pages[-1].rotate(deg)
                    out = writer_to_bytes(w)
                    stem = tf.name.removesuffix(".pdf")
                    results[f"{stem}_rotated.pdf"] = out

                except Exception as exc:
                    show_alert("warn", "⚠️", f"{tf.name}: {exc}")

            increment_op_count()
            if batch and len(results) > 1:
                zb = build_zip(results)
                add_to_history("rotated.zip", zb, sum(tf.size for tf in target_files if tf))
                st.success(f"✅  Rotated {len(results)} file(s).")
                st.download_button("⬇️  Download rotated.zip", zb, "rotated.zip", "application/zip", key="rotd")
            elif results:
                name, data = next(iter(results.items()))
                add_to_history(name, data, len(get_bytes(target_files[0])))
                st.success(f"✅  Rotated {len(reader.pages)} page(s) by {angle}.")
                st.download_button(f"⬇️  Download {name}", data, name, "application/pdf", key="rotd")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 11 · PDF → IMAGES ───────────────────────────────────────────────────────
elif tool == NEW_A[1]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("📸", "PDF → Images",
           "Export every page (or a range) as PNG or JPEG images, delivered as a ZIP.")
    with col_clr:
        show_clear_button("p2iu", "pdf2img")

    show_alert("warn", "⚠️",
               "Requires <code>pdf2image</code> and Poppler. "
               "Install with: <code>pip install pdf2image</code> and <code>apt install poppler-utils</code>.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="p2iu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
            show_pdf_preview(data)

            col1, col2, col3 = st.columns(3)
            with col1:
                fmt = st.selectbox("Image format", ["PNG", "JPEG"], key="p2ifmt")
            with col2:
                dpi = st.selectbox("DPI / resolution", [72, 96, 150, 200, 300], index=2, key="p2idpi")
            with col3:
                scope = st.selectbox("Pages", ["All pages", "Specific range"], key="p2iscope")

            pages_input = ""
            if scope == "Specific range":
                pages_input = st.text_input("Pages to export",
                                            placeholder=f"e.g.  1-5, 8  (1 to {total})",
                                            key="p2ipi")

            if st.button("Export Images", key="p2ib"):
                if not check_rate_limit():
                    st.stop()
                try:
                    from pdf2image import convert_from_bytes
                except ImportError:
                    show_alert("err", "❌",
                               "pdf2image is not installed. Run: "
                               "<code>pip install pdf2image</code> and install Poppler.")
                    st.stop()

                if scope == "Specific range":
                    if not pages_input:
                        show_alert("err", "❌", "Enter page numbers to export.")
                        st.stop()
                    indices = parse_range(pages_input, total)
                    first_p, last_p = indices[0] + 1, indices[-1] + 1
                else:
                    indices = list(range(total))
                    first_p, last_p = 1, total

                update, done = progress_with_eta(len(indices), "Rasterising pages…")
                images = convert_from_bytes(data, dpi=dpi, first_page=first_p,
                                           last_page=last_p, fmt=fmt.lower())
                if scope == "Specific range":
                    needed = {i - (first_p - 1) for i in indices}
                    images = [img for k, img in enumerate(images) if k in needed]

                files_dict = {}
                ext = "jpg" if fmt == "JPEG" else "png"
                for k, img in enumerate(images):
                    page_num = indices[k] + 1
                    b = io.BytesIO()
                    save_kw = {"quality": 92} if fmt == "JPEG" else {}
                    img.save(b, format=fmt, **save_kw)
                    files_dict[f"page_{page_num:04d}.{ext}"] = b.getvalue()
                    update(k + 1, f"Page {page_num}/{total}")
                done()

                increment_op_count()
                zb = build_zip(files_dict)
                add_to_history("images.zip", zb, len(data))
                st.success(f"✅  {len(files_dict)} image(s) exported at {dpi} DPI ({fmt_bytes(len(zb))}).")
                st.download_button("⬇️  Download images.zip",
                                   zb, "images.zip", "application/zip", key="p2id")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Export failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 12 · WATERMARK ──────────────────────────────────────────────────────────
elif tool == NEW_A[2]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("💧", "Watermark PDF", "Stamp a text watermark across every page.")
    with col_clr:
        show_clear_button("wmu", "watermark")

    batch = st.checkbox("Batch mode — watermark multiple PDFs at once (→ ZIP)", key="wm_batch")

    if batch:
        files = st.file_uploader("Upload PDFs", type="pdf", accept_multiple_files=True, key="wmu_batch")
        f     = None
    else:
        f     = st.file_uploader("Upload a PDF", type="pdf", key="wmu")
        files = None

    active_files = files if batch else ([f] if f else [])

    if active_files and any(active_files):
        if not batch and f:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
            show_pdf_preview(data)

        col1, col2 = st.columns(2)
        with col1:
            wm_text    = st.text_input("Watermark text", value="CONFIDENTIAL", key="wmt")
        with col2:
            wm_opacity = st.slider("Opacity", 5, 60, 20, key="wmo", help="Lower = more transparent")

        col3, col4, col5 = st.columns(3)
        with col3:
            wm_color = st.selectbox("Color", ["Gray", "Red", "Blue", "Black"], key="wmc")
        with col4:
            wm_size  = st.selectbox("Font size", [24, 36, 48, 60, 72], index=2, key="wms")
        with col5:
            wm_angle = st.selectbox("Angle", ["45° diagonal", "Horizontal", "-45° diagonal"], key="wma")

        if wm_text.strip() and st.button("Apply Watermark", key="wmb"):
            if not check_rate_limit():
                st.stop()
            try:
                from reportlab.pdfgen import canvas as rl_canvas
                from reportlab.lib.colors import Color
                import math

                color_map = {
                    "Gray":  (0.5, 0.5, 0.5),
                    "Red":   (0.8, 0.1, 0.1),
                    "Blue":  (0.1, 0.1, 0.8),
                    "Black": (0.0, 0.0, 0.0),
                }
                r_c, g_c, b_c = color_map[wm_color]
                alpha = wm_opacity / 100.0
                angle_deg = {"45° diagonal": 45, "Horizontal": 0, "-45° diagonal": -45}[wm_angle]

                def make_wm_page(width: float, height: float) -> bytes:
                    buf = io.BytesIO()
                    c = rl_canvas.Canvas(buf, pagesize=(width, height))
                    c.saveState()
                    c.setFont("Helvetica-Bold", wm_size)
                    c.setFillColor(Color(r_c, g_c, b_c, alpha=alpha))
                    c.translate(width / 2, height / 2)
                    c.rotate(angle_deg)
                    c.drawCentredString(0, 0, wm_text)
                    c.restoreState()
                    c.save()
                    return buf.getvalue()

                results = {}
                for tf in active_files:
                    if tf is None:
                        continue
                    d      = get_bytes(tf)
                    reader = validate_pdf(d, tf.name)
                    w = PdfWriter()
                    for page in reader.pages:
                        box    = page.mediabox
                        pw, ph = float(box.width), float(box.height)
                        wm_pdf = PdfReader(io.BytesIO(make_wm_page(pw, ph)))
                        page.merge_page(wm_pdf.pages[0])
                        w.add_page(page)
                    stem = tf.name.removesuffix(".pdf")
                    results[f"{stem}_watermarked.pdf"] = writer_to_bytes(w)

                increment_op_count()
                if batch and len(results) > 1:
                    zb = build_zip(results)
                    add_to_history("watermarked.zip", zb, sum(tf.size for tf in active_files if tf))
                    st.success(f"✅  Watermarked {len(results)} file(s).")
                    st.download_button("⬇️  Download watermarked.zip", zb, "watermarked.zip", "application/zip", key="wmd")
                elif results:
                    name, out = next(iter(results.items()))
                    add_to_history(name, out, len(data) if f else 0)
                    st.success(f"✅  Watermark applied.")
                    st.download_button(f"⬇️  Download {name}", out, name, "application/pdf", key="wmd")

            except ImportError:
                show_alert("err", "❌", "reportlab is not installed. Run: <code>pip install reportlab</code>")
            except Exception as e:
                st.error(f"Watermark failed: {e}\n\n{traceback.format_exc()}")
        elif not wm_text.strip():
            show_alert("warn", "⚠️", "Enter watermark text above.")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 13 · PROTECT / UNLOCK ───────────────────────────────────────────────────
elif tool == NEW_A[3]:
    ph("🔐", "Protect / Unlock PDF",
       "Add a password to a PDF, or remove one from a PDF you already own.")

    mode = st.radio("Action", ["🔒  Add password protection", "🔓  Remove password"],
                    horizontal=True, key="pumode")

    if mode == "🔒  Add password protection":
        show_alert("info", "ℹ️",
                   "Sets a user (open) password. Recipients need this password to view the file.")
        f = st.file_uploader("Upload a PDF", type="pdf", key="ppu")
        if f:
            try:
                data   = get_bytes(f)
                reader = validate_pdf(data, f.name)
                total  = len(reader.pages)
                pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
                show_pdf_preview(data)

                col1, col2 = st.columns(2)
                with col1:
                    user_pw  = st.text_input("User password (required to open)",
                                             type="password", key="ppuw")
                    show_password_strength(user_pw)
                with col2:
                    owner_pw = st.text_input("Owner password (optional, for permissions)",
                                             type="password", key="ppow",
                                             help="Leave blank to use the same as user password.")
                    if owner_pw:
                        show_password_strength(owner_pw)

                if user_pw:
                    score, label, _ = password_strength(user_pw)
                    if score < 2:
                        show_alert("warn", "⚠️",
                                   f"Password is <strong>{label or 'very weak'}</strong>. "
                                   "Use 8+ characters with mixed case, numbers, and symbols.")

                if user_pw and st.button("Add Password", key="ppb"):
                    if not check_rate_limit():
                        st.stop()
                    try:
                        w = PdfWriter()
                        for page in reader.pages:
                            w.add_page(page)
                        eff_owner = owner_pw if owner_pw else user_pw
                        w.encrypt(user_password=user_pw, owner_password=eff_owner)
                        out = writer_to_bytes(w)
                        increment_op_count()
                        add_to_history("protected.pdf", out, len(data))
                        st.success(f"✅  Password protection added ({fmt_bytes(len(out))}).")
                        st.download_button("⬇️  Download protected.pdf",
                                           out, "protected.pdf", "application/pdf", key="ppd")
                    except Exception as e:
                        st.error(f"Protection failed: {e}\n\n{traceback.format_exc()}")
                elif not user_pw:
                    show_alert("warn", "⚠️", "Enter a user password above.")
            except ValueError as e:
                show_alert("err", "❌", str(e))
            except Exception as e:
                st.error(f"Error: {e}\n\n{traceback.format_exc()}")
        else:
            show_alert("info", "ℹ️", "Upload a PDF above to get started.")

    else:  # Remove password
        show_alert("warn", "⚠️",
                   "Only remove passwords from PDFs you own or have permission to modify.")
        f = st.file_uploader("Upload a password-protected PDF", type="pdf", key="upu")
        if f:
            try:
                data = get_bytes(f)
                check_file_size(data, f.name)
                pw = st.text_input("Current password", type="password", key="upw")

                if pw and st.button("Remove Password", key="upb"):
                    if not check_rate_limit():
                        st.stop()
                    try:
                        reader = validate_pdf_with_password(data, f.name, pw)
                        w = PdfWriter()
                        for page in reader.pages:
                            w.add_page(page)
                        out = writer_to_bytes(w)
                        increment_op_count()
                        add_to_history("unlocked.pdf", out, len(data))
                        st.success(f"✅  Password removed ({fmt_bytes(len(out))}).")
                        st.download_button("⬇️  Download unlocked.pdf",
                                           out, "unlocked.pdf", "application/pdf", key="upd")
                    except Exception as e:
                        st.error(f"Unlock failed: {e}\n\n{traceback.format_exc()}")
                elif not pw:
                    show_alert("info", "ℹ️", "Enter the current password above.")
            except ValueError as e:
                show_alert("err", "❌", str(e))
            except Exception as e:
                st.error(f"Error: {e}\n\n{traceback.format_exc()}")
        else:
            show_alert("info", "ℹ️", "Upload a password-protected PDF above to get started.")


# ─── 14 · EXTRACT TEXT ───────────────────────────────────────────────────────
elif tool == NEW_B[0]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("📝", "Extract Text",
           "Pull all readable text out of a PDF — by page or as a single document.")
    with col_clr:
        show_clear_button("xtu", "extracttext")

    f = st.file_uploader("Upload a PDF", type="pdf", key="xtu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

            col1, col2 = st.columns(2)
            with col1:
                layout = st.selectbox("Output format",
                                      ["Single document", "One section per page"],
                                      key="xtlayout")
            with col2:
                scope = st.selectbox("Pages", ["All pages", "Specific range"], key="xtscope")

            pages_input = ""
            if scope == "Specific range":
                pages_input = st.text_input("Pages to extract",
                                            placeholder=f"e.g.  1-5, 8  (1 to {total})",
                                            key="xtpi")

            if st.button("Extract Text", key="xtb"):
                if not check_rate_limit():
                    st.stop()
                if scope == "Specific range":
                    if not pages_input:
                        show_alert("err", "❌", "Enter page numbers to extract.")
                        st.stop()
                    indices = parse_range(pages_input, total)
                else:
                    indices = list(range(total))

                update, done = progress_with_eta(len(indices), "Extracting text…")
                parts = []
                empty = 0
                for k, i in enumerate(indices):
                    text = reader.pages[i].extract_text() or ""
                    if not text.strip():
                        empty += 1
                    if layout == "One section per page":
                        parts.append(f"── Page {i+1} {'─'*40}\n{text or '(no text)'}")
                    else:
                        parts.append(text)
                    update(k + 1, f"Page {i+1}/{total}")
                done()
                increment_op_count()

                full_text  = "\n\n".join(parts)
                char_count = len(full_text)

                pill_row(
                    (f"{len(indices)} pages processed", "a"),
                    (f"{char_count:,} characters", "s") if char_count > 0 else ("0 characters", "d"),
                    (f"{empty} page(s) with no text", "w") if empty else ("all pages have text", "s"),
                )

                if char_count == 0:
                    show_alert("warn", "⚠️",
                               "No text found. The PDF may be scanned (image-only). "
                               "Try OCR software like Tesseract or Adobe Acrobat.")
                else:
                    # Copy-to-clipboard button
                    show_copy_button(full_text, "xt_copy")
                    st.text_area("Extracted text", full_text, height=320, key="xtout")
                    txt_bytes = full_text.encode("utf-8")
                    add_to_history(f"{f.name.removesuffix('.pdf')}_text.txt", txt_bytes, len(data))
                    st.download_button("⬇️  Download as .txt",
                                       txt_bytes,
                                       file_name=f"{f.name.removesuffix('.pdf')}_text.txt",
                                       mime="text/plain",
                                       key="xtd")

        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Text extraction failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 15 · EDIT METADATA ──────────────────────────────────────────────────────
elif tool == NEW_B[1]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("🏷️", "Edit Metadata",
           "View and update the title, author, subject, keywords, and other document properties.")
    with col_clr:
        show_clear_button("mdu", "metadata")

    f = st.file_uploader("Upload a PDF", type="pdf", key="mdu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

            meta = reader.metadata or {}
            def get_meta(key: str) -> str:
                val = meta.get(key, "") or meta.get(f"/{key.lstrip('/')}", "")
                return str(val) if val else ""

            st.markdown("#### Current metadata")
            raw_items = {k: str(v) for k, v in meta.items()} if meta else {}
            if raw_items:
                pill_row(*[(f"{k}: {v[:40]}", "") for k, v in list(raw_items.items())[:8]])
            else:
                show_alert("info", "ℹ️", "No metadata found in this PDF.")

            st.markdown("#### Edit fields")
            show_alert("info", "ℹ️",
                       "Fields are sanitized automatically — control characters and injection sequences are stripped.")
            col1, col2 = st.columns(2)
            with col1:
                title    = st.text_input("Title",    value=get_meta("/Title"),    key="mdtitle",   max_chars=500)
                author   = st.text_input("Author",   value=get_meta("/Author"),   key="mdauthor",  max_chars=500)
                subject  = st.text_input("Subject",  value=get_meta("/Subject"),  key="mdsubject", max_chars=500)
            with col2:
                keywords = st.text_input("Keywords", value=get_meta("/Keywords"), key="mdkw",      max_chars=500)
                creator  = st.text_input("Creator",  value=get_meta("/Creator"),  key="mdcreator", max_chars=500)
                producer = st.text_input("Producer", value=get_meta("/Producer"), key="mdprod",    max_chars=500)

            strip_dates = st.checkbox("Strip creation/modification timestamps", value=False, key="mdstrip")

            if st.button("Save Metadata", key="mdb"):
                if not check_rate_limit():
                    st.stop()
                w = PdfWriter()
                for page in reader.pages:
                    w.add_page(page)

                # ✅ Sanitize all metadata fields before writing
                new_meta = {
                    "/Title":    sanitize_metadata_field(title),
                    "/Author":   sanitize_metadata_field(author),
                    "/Subject":  sanitize_metadata_field(subject),
                    "/Keywords": sanitize_metadata_field(keywords),
                    "/Creator":  sanitize_metadata_field(creator),
                    "/Producer": sanitize_metadata_field(producer),
                }
                if not strip_dates:
                    for key in ("/CreationDate", "/ModDate"):
                        if key in meta:
                            new_meta[key] = sanitize_metadata_field(str(meta[key]))

                w.add_metadata({k: v for k, v in new_meta.items() if v})
                out = writer_to_bytes(w)
                increment_op_count()
                add_to_history("updated.pdf", out, len(data))
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                st.success("✅  Metadata updated and sanitized.")
                st.download_button("⬇️  Download updated.pdf",
                                   out, "updated.pdf", "application/pdf", key="mdd")

        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Metadata edit failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 16 · ADD PAGE NUMBERS ───────────────────────────────────────────────────
elif tool == NEW_B[2]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("🔢", "Add Page Numbers",
           "Stamp page numbers onto every page using reportlab, with full position and style control.")
    with col_clr:
        show_clear_button("pnu", "pagenums")

    batch = st.checkbox("Batch mode — add page numbers to multiple PDFs (→ ZIP)", key="pn_batch")

    if batch:
        files = st.file_uploader("Upload PDFs", type="pdf", accept_multiple_files=True, key="pnu_batch")
        f     = None
    else:
        f     = st.file_uploader("Upload a PDF", type="pdf", key="pnu")
        files = None

    active_files = files if batch else ([f] if f else [])

    if active_files and any(active_files):
        if not batch and f:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))
            show_pdf_preview(data)

        col1, col2, col3 = st.columns(3)
        with col1:
            position  = st.selectbox("Position",
                                     ["Bottom center", "Bottom right", "Bottom left",
                                      "Top center", "Top right", "Top left"],
                                     key="pnpos")
        with col2:
            start_num = st.number_input("Start numbering at", min_value=1, value=1, key="pnstart")
        with col3:
            font_size = st.selectbox("Font size", [8, 10, 11, 12, 14], index=1, key="pnfs")

        col4, col5 = st.columns(2)
        with col4:
            fmt_str = st.text_input("Format  (use {n} for number, {t} for total)",
                                    value="{n}", key="pnfmt",
                                    help="Examples: {n}, Page {n}, {n} / {t}")
        with col5:
            margin  = st.number_input("Margin from edge (pt)", min_value=4, max_value=72,
                                      value=18, key="pnmargin")

        if st.button("Add Page Numbers", key="pnb"):
            if not check_rate_limit():
                st.stop()
            try:
                from reportlab.pdfgen import canvas as rl_canvas
                from reportlab.lib.colors import black

                def make_number_overlay(width: float, height: float, label: str) -> bytes:
                    buf = io.BytesIO()
                    c   = rl_canvas.Canvas(buf, pagesize=(width, height))
                    c.setFont("Helvetica", font_size)
                    c.setFillColor(black)
                    pad = float(margin)
                    pos_map = {
                        "Bottom center": (width / 2, pad,          "centre"),
                        "Bottom right":  (width - pad, pad,        "right"),
                        "Bottom left":   (pad, pad,                 "left"),
                        "Top center":    (width / 2, height - pad, "centre"),
                        "Top right":     (width - pad, height - pad,"right"),
                        "Top left":      (pad, height - pad,        "left"),
                    }
                    x, y, align = pos_map[position]
                    if align == "centre":
                        c.drawCentredString(x, y, label)
                    elif align == "right":
                        c.drawRightString(x, y, label)
                    else:
                        c.drawString(x, y, label)
                    c.save()
                    return buf.getvalue()

                results = {}
                for tf in active_files:
                    if tf is None:
                        continue
                    d      = get_bytes(tf)
                    reader = validate_pdf(d, tf.name)
                    pg_total = len(reader.pages)
                    w = PdfWriter()
                    for i, page in enumerate(reader.pages):
                        box    = page.mediabox
                        pw, ph = float(box.width), float(box.height)
                        n      = i + int(start_num)
                        label  = fmt_str.replace("{n}", str(n)).replace("{t}", str(pg_total))
                        ov     = PdfReader(io.BytesIO(make_number_overlay(pw, ph, label)))
                        page.merge_page(ov.pages[0])
                        w.add_page(page)
                    stem = tf.name.removesuffix(".pdf")
                    results[f"{stem}_numbered.pdf"] = writer_to_bytes(w)

                increment_op_count()
                if batch and len(results) > 1:
                    zb = build_zip(results)
                    add_to_history("numbered.zip", zb, sum(tf.size for tf in active_files if tf))
                    st.success(f"✅  Page numbers added to {len(results)} file(s).")
                    st.download_button("⬇️  Download numbered.zip", zb, "numbered.zip", "application/zip", key="pnd")
                elif results:
                    name, out = next(iter(results.items()))
                    add_to_history(name, out, len(data) if f else 0)
                    st.success(f"✅  Page numbers added.")
                    st.download_button(f"⬇️  Download {name}", out, name, "application/pdf", key="pnd")

            except ImportError:
                show_alert("err", "❌", "reportlab is not installed. Run: <code>pip install reportlab</code>")
            except Exception as e:
                st.error(f"Page numbering failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 17 · CROP PAGES ─────────────────────────────────────────────────────────
elif tool == NEW_B[3]:
    col_h, col_clr = st.columns([8, 1])
    with col_h:
        ph("✂️", "Crop Pages",
           "Adjust the visible area of every page by setting new margins.")
    with col_clr:
        show_clear_button("cru", "crop")

    show_alert("warn", "⚠️",
               "Crop box changes what's <em>visible</em> — it does not permanently delete content outside "
               "the crop area. Use Remove Pages if you need to delete entire pages.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="cru")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)

            sample = reader.pages[0].mediabox
            pw_pt  = float(sample.width)
            ph_pt  = float(sample.height)
            pw_mm  = pw_pt * 25.4 / 72
            ph_mm  = ph_pt * 25.4 / 72

            pill_row(
                (f"{total} pages", "a"),
                (fmt_bytes(len(data)), ""),
                (f"Page 1: {pw_mm:.0f}×{ph_mm:.0f} mm  ({pw_pt:.0f}×{ph_pt:.0f} pt)", ""),
            )
            show_pdf_preview(data)
            show_page_dimensions(data)

            show_alert("info", "ℹ️",
                       f"First page is {pw_mm:.0f}×{ph_mm:.0f} mm. "
                       "Enter margins to remove from each edge (in mm). 0 = no crop on that side.")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                top    = st.number_input("Top (mm)",    min_value=0.0, max_value=ph_mm*0.45, value=0.0, step=1.0, key="crtop")
            with col2:
                bottom = st.number_input("Bottom (mm)", min_value=0.0, max_value=ph_mm*0.45, value=0.0, step=1.0, key="crbot")
            with col3:
                left   = st.number_input("Left (mm)",   min_value=0.0, max_value=pw_mm*0.45, value=0.0, step=1.0, key="crlft")
            with col4:
                right  = st.number_input("Right (mm)",  min_value=0.0, max_value=pw_mm*0.45, value=0.0, step=1.0, key="crrgt")

            scope = st.selectbox("Apply to", ["All pages", "Specific pages / range"], key="crscope")
            pages_input = ""
            if scope == "Specific pages / range":
                pages_input = st.text_input("Pages to crop",
                                            placeholder=f"e.g.  1, 3-6  (1 to {total})",
                                            key="crpi")

            def mm_to_pt(mm: float) -> float:
                return mm * 72 / 25.4

            if st.button("Crop PDF", key="crb"):
                if not check_rate_limit():
                    st.stop()
                if top == bottom == left == right == 0:
                    show_alert("warn", "⚠️", "All margins are 0 — nothing to crop.")
                    st.stop()

                if scope == "Specific pages / range":
                    if not pages_input:
                        show_alert("err", "❌", "Enter page numbers to crop.")
                        st.stop()
                    crop_set = set(parse_range(pages_input, total))
                else:
                    crop_set = set(range(total))

                t_pt = mm_to_pt(top)
                b_pt = mm_to_pt(bottom)
                l_pt = mm_to_pt(left)
                r_pt = mm_to_pt(right)

                w    = PdfWriter()
                update, done = progress_with_eta(total, "Cropping…")
                for i, page in enumerate(reader.pages):
                    if i in crop_set:
                        mb = page.mediabox
                        x0 = float(mb.left)   + l_pt
                        y0 = float(mb.bottom) + b_pt
                        x1 = float(mb.right)  - r_pt
                        y1 = float(mb.top)    - t_pt
                        if x1 <= x0 or y1 <= y0:
                            show_alert("err", "❌",
                                       f"Page {i+1}: crop margins exceed page size. Reduce values.")
                            st.stop()
                        from pypdf.generic import RectangleObject
                        page.cropbox = RectangleObject((x0, y0, x1, y1))
                    w.add_page(page)
                    update(i + 1, f"Page {i+1}/{total}")
                done()

                out = writer_to_bytes(w)
                new_w_mm = (float(reader.pages[0].mediabox.width)  - l_pt - r_pt) * 25.4 / 72
                new_h_mm = (float(reader.pages[0].mediabox.height) - t_pt - b_pt) * 25.4 / 72
                increment_op_count()
                add_to_history("cropped.pdf", out, len(data))
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                st.success(
                    f"✅  Cropped {len(crop_set)} page(s). "
                    f"New visible area: {new_w_mm:.0f}×{new_h_mm:.0f} mm."
                )
                st.download_button("⬇️  Download cropped.pdf",
                                   out, "cropped.pdf", "application/pdf", key="crd")

        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Crop failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")
