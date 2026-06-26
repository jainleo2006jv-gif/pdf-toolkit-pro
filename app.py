"""
PDF Toolkit Pro — 17 tools: Merge, Split, Remove, Extract, Reorder, Images→PDF,
Optimize, Compress, Repair, Rotate, PDF→Images, Watermark, Protect/Unlock,
Extract Text, Edit Metadata, Add Page Numbers, Crop Pages
"""

import io
import traceback
import zipfile
from collections import Counter
from typing import Optional

import streamlit as st
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError, PdfStreamError
from pypdf.generic import NameObject, NumberObject

# ── Constants ────────────────────────────────────────────────────────────────
MAX_FILE_MB    = 200
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

st.set_page_config(
    page_title="PDF Toolkit",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

:root {
    --bg:       #f8f9fa;
    --white:    #ffffff;
    --border:   #e2e5ea;
    --text:     #1a1d23;
    --muted:    #6b7280;
    --accent:   #2563eb;
    --accent-l: #eff6ff;
    --success:  #16a34a;
    --warning:  #d97706;
    --danger:   #dc2626;
    --r:        8px;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--text) !important;
}

#MainMenu, footer, [data-testid="stHeader"], [data-testid="stDecoration"] {
    display: none !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--white) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

.sb-logo {
    padding: 1.4rem 1.2rem 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0.5rem;
}
.sb-logo h1 {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 0.15rem;
}
.sb-logo span {
    font-size: 0.72rem;
    color: var(--muted);
}

.nav-label {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--muted);
    padding: 0.8rem 1.2rem 0.3rem;
}

[data-testid="stSidebar"] .stRadio > div { gap: 0 !important; }
[data-testid="stSidebar"] .stRadio label {
    font-size: 0.84rem !important;
    color: var(--muted) !important;
    padding: 0.45rem 1.2rem !important;
    border-radius: 0 !important;
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: var(--bg) !important;
    color: var(--text) !important;
}
[data-testid="stSidebar"] .stRadio label[data-checked="true"],
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label {
    background: var(--accent-l) !important;
    color: var(--accent) !important;
    font-weight: 500 !important;
    border-left: 2px solid var(--accent) !important;
}
[data-testid="stSidebar"] .stRadio [type="radio"] { display: none !important; }

/* ── Main ── */
[data-testid="stMainBlockContainer"] {
    padding: 2rem 2.5rem !important;
    max-width: 900px;
}

/* ── Page header ── */
.ph {
    margin-bottom: 1.6rem;
    padding-bottom: 1.2rem;
    border-bottom: 1px solid var(--border);
}
.ph h2 {
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 0.25rem;
}
.ph p { font-size: 0.83rem; color: var(--muted); margin: 0; }

/* ── Card ── */
.card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
.card-title {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.9rem;
}

/* ── Pills ── */
.pr { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.6rem 0; }
.pill {
    font-size: 0.75rem; font-weight: 500;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--muted);
}
.pill.a { background: var(--accent-l); border-color: #bfdbfe; color: var(--accent); }
.pill.s { background: #f0fdf4; border-color: #bbf7d0; color: var(--success); }
.pill.w { background: #fffbeb; border-color: #fde68a; color: var(--warning); }
.pill.d { background: #fef2f2; border-color: #fecaca; color: var(--danger); }

/* ── Alerts ── */
.al {
    display: flex; gap: 0.6rem; align-items: flex-start;
    padding: 0.7rem 0.9rem;
    border-radius: var(--r);
    font-size: 0.82rem; line-height: 1.5; margin: 0.7rem 0;
}
.al-i { font-size: 0.9rem; flex-shrink: 0; margin-top: 0.05rem; }
.al.info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; }
.al.warn { background: #fffbeb; border: 1px solid #fde68a; color: var(--warning); }
.al.err  { background: #fef2f2; border: 1px solid #fecaca; color: var(--danger); }
.al.ok   { background: #f0fdf4; border: 1px solid #bbf7d0; color: var(--success); }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: var(--white) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: var(--r) !important;
}
[data-testid="stFileUploader"]:hover { border-color: var(--accent) !important; }
[data-testid="stFileUploader"] label { color: var(--muted) !important; font-size: 0.82rem !important; }

/* ── Inputs ── */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.84rem !important;
}
.stTextInput input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px #dbeafe !important; outline: none !important; }
.stTextInput label, .stSelectbox label, .stNumberInput label, .stSlider label {
    color: var(--text) !important; font-size: 0.8rem !important; font-weight: 500 !important;
}

/* ── Buttons ── */
.stButton > button {
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
}
.stButton > button:hover { opacity: 0.88 !important; }

[data-testid="stDownloadButton"] > button {
    background: var(--white) !important;
    color: var(--accent) !important;
    border: 1px solid #bfdbfe !important;
    border-radius: var(--r) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.83rem !important;
    box-shadow: none !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: var(--accent-l) !important;
    transform: none !important;
}

/* ── Progress ── */
[data-testid="stProgressBar"] > div > div {
    background: var(--accent) !important;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1.2rem 0 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }

/* ── Text area ── */
.stTextArea textarea {
    background: var(--white) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r) !important;
    color: var(--text) !important;
    font-family: 'Courier New', monospace !important;
    font-size: 0.78rem !important;
}

/* ── Streamlit alerts ── */
[data-testid="stAlert"] { border-radius: var(--r) !important; font-size: 0.82rem !important; }

/* ── Checkbox ── */
.stCheckbox label { color: var(--text) !important; font-size: 0.83rem !important; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
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


def show_alert(kind: str, icon: str, html: str) -> None:
    st.markdown(
        f'<div class="al {kind}"><span class="al-i">{icon}</span><span>{html}</span></div>',
        unsafe_allow_html=True,
    )


def ph(icon: str, title: str, desc: str) -> None:
    st.markdown(
        f'<div class="ph"><h2>{icon} {title}</h2><p>{desc}</p></div>',
        unsafe_allow_html=True,
    )


def card_start(label: str = "") -> None:
    if "_card_label" not in st.session_state:
        st.session_state["_card_label"] = ""
    st.session_state["_card_label"] = label
    st.session_state["_card_items"] = []


def card_end() -> None:
    label = st.session_state.get("_card_label", "")
    title_html = f'<p class="card-title">{label}</p>' if label else ""
    st.markdown(f'<div class="card">{title_html}</div>', unsafe_allow_html=True)


def pill_row(*pills) -> None:
    inner = "".join(
        f'<span class="pill {cls}">{lbl}</span>' for lbl, cls in pills
    )
    st.markdown(f'<div class="pr">{inner}</div>', unsafe_allow_html=True)


# ── PDF helpers ───────────────────────────────────────────────────────────────

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
            return {"pages": 0, "encrypted": True, "error": None}
        return {"pages": len(reader.pages), "encrypted": False, "error": None}
    except (PdfReadError, PdfStreamError) as e:
        return {"pages": 0, "encrypted": False, "error": str(e)}
    except Exception as e:
        return {"pages": 0, "encrypted": False, "error": f"Unexpected error: {e}"}


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
    """Like validate_pdf but accepts an optional password for encrypted PDFs."""
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


# ═════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

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
    st.markdown('<div class="nav-label">Core Tools</div>', unsafe_allow_html=True)
    core_tool = st.radio("core_nav", CORE, label_visibility="collapsed", key="core_nav")
    st.markdown('<div class="nav-label" style="margin-top:0.4rem">Extras</div>',
                unsafe_allow_html=True)
    extra_tool = st.radio("extra_nav", EXTRA, label_visibility="collapsed", key="extra_nav")
    st.markdown('<div class="nav-label" style="margin-top:0.4rem">Transform</div>',
                unsafe_allow_html=True)
    new_a_tool = st.radio("new_a_nav", NEW_A, label_visibility="collapsed", key="new_a_nav")
    st.markdown('<div class="nav-label" style="margin-top:0.4rem">Content</div>',
                unsafe_allow_html=True)
    new_b_tool = st.radio("new_b_nav", NEW_B, label_visibility="collapsed", key="new_b_nav")

# Determine the active tool; last-clicked radio wins via session state
if "active_nav" not in st.session_state:
    st.session_state["active_nav"] = CORE[0]

_prev_core  = st.session_state.get("_prev_core",  CORE[0])
_prev_extra = st.session_state.get("_prev_extra", EXTRA[0])
_prev_new_a = st.session_state.get("_prev_new_a", NEW_A[0])
_prev_new_b = st.session_state.get("_prev_new_b", NEW_B[0])

if core_tool != _prev_core:
    st.session_state["active_nav"] = core_tool
elif extra_tool != _prev_extra:
    st.session_state["active_nav"] = extra_tool
elif new_a_tool != _prev_new_a:
    st.session_state["active_nav"] = new_a_tool
elif new_b_tool != _prev_new_b:
    st.session_state["active_nav"] = new_b_tool

st.session_state["_prev_core"]  = core_tool
st.session_state["_prev_extra"] = extra_tool
st.session_state["_prev_new_a"] = new_a_tool
st.session_state["_prev_new_b"] = new_b_tool
tool = st.session_state["active_nav"]


# ═════════════════════════════════════════════════════════════════════════════
#  TOOL PANELS
# ═════════════════════════════════════════════════════════════════════════════

# ─── 1 · MERGE ───────────────────────────────────────────────────────────────
if tool == CORE[0]:
    ph("🔀", "Merge PDFs",
       "Combine multiple PDFs into one document, in upload order.")

    files = st.file_uploader("Upload PDFs (select two or more)",
                             type="pdf", accept_multiple_files=True, key="mu")
    if files:
        pill_row((f"{len(files)} file(s) selected", "a"))

        card_start("Files to merge")
        total_pages = 0
        bad_files   = []
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

        if bad_files:
            show_alert("warn", "⚠️", f"Fix the issues above before merging: {', '.join(bad_files)}")
        elif len(files) < 2:
            show_alert("warn", "⚠️", "Upload at least 2 PDFs.")
        elif st.button("Merge PDFs", key="mb"):
            try:
                w    = PdfWriter()
                prog = st.progress(0, text="Merging…")
                for idx, f in enumerate(files):
                    reader = validate_pdf(get_bytes(f), f.name)
                    for pg in reader.pages:
                        w.add_page(pg)
                    prog.progress((idx + 1) / len(files),
                                  text=f"Merging {idx+1}/{len(files)}: {f.name}")
                prog.empty()
                out = writer_to_bytes(w)
                st.success(f"✅  Merged {len(files)} files → {len(w.pages)} pages ({fmt_bytes(len(out))}).")
                st.download_button("⬇️  Download merged.pdf",
                                   out, "merged.pdf", "application/pdf", key="md")
            except ValueError as e:
                show_alert("err", "❌", str(e))
            except Exception as e:
                st.error(f"Merge failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload two or more PDFs above to get started.")


# ─── 2 · SPLIT ───────────────────────────────────────────────────────────────
elif tool == CORE[1]:
    ph("✂️", "Split PDF",
       "Split into individual pages or fixed-size chunks, delivered as a ZIP.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="su")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

            col1, col2 = st.columns(2)
            with col1:
                mode = st.selectbox("Split mode",
                                    ["Every page (individual files)", "Fixed chunk size"],
                                    key="sm")
            with col2:
                chunk_size = None
                if mode == "Fixed chunk size":
                    chunk_size = st.number_input("Pages per chunk",
                                                 min_value=1, max_value=total,
                                                 value=min(5, total), key="sc")

            if st.button("Split PDF", key="sb"):
                pages_dict: dict = {}
                prog = st.progress(0, text="Splitting…")
                if mode == "Every page (individual files)":
                    for i in range(total):
                        pages_dict[f"page_{i+1:04d}.pdf"] = copy_pages(reader, [i])
                        prog.progress((i + 1) / total, text=f"Page {i+1}/{total}")
                elif chunk_size is not None:
                    cs    = int(chunk_size)
                    parts = list(range(0, total, cs))
                    for part_idx, start in enumerate(parts):
                        end = min(start + cs, total)
                        key = f"part_{part_idx+1:03d}_pages_{start+1}-{end}.pdf"
                        pages_dict[key] = copy_pages(reader, list(range(start, end)))
                        prog.progress((part_idx + 1) / len(parts),
                                      text=f"Chunk {part_idx+1}/{len(parts)}")
                prog.empty()
                zb = build_zip(pages_dict)
                st.success(f"✅  {len(pages_dict)} file(s) created ({fmt_bytes(len(zb))}).")
                st.download_button(f"⬇️  Download split_pages.zip",
                                   zb, "split_pages.zip", "application/zip", key="sd")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Split failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 3 · REMOVE PAGES ────────────────────────────────────────────────────────
elif tool == CORE[2]:
    ph("🗑️", "Remove Pages",
       "Delete specific pages by number or range.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="rpu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

            pages_input = st.text_input("Pages to remove",
                                        placeholder=f"e.g.  2, 5, 7-10  (1 to {total})",
                                        key="rpi")
            show_alert("info", "ℹ️",
                       f"Comma-separated page numbers or ranges. Valid: 1–{total}.")

            if pages_input and st.button("Remove Pages", key="rpb"):
                to_remove = set(parse_range(pages_input, total))
                keep      = [i for i in range(total) if i not in to_remove]
                if not keep:
                    show_alert("err", "❌", "Cannot remove all pages.")
                else:
                    with st.spinner("Removing pages…"):
                        out = copy_pages(reader, keep)
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
    ph("📑", "Extract Pages",
       "Pull a subset of pages into a new PDF.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="eu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

            pages_input = st.text_input("Pages to extract",
                                        placeholder=f"e.g.  1, 3-6, 9  (1 to {total})",
                                        key="epi")
            show_alert("info", "ℹ️",
                       f"Comma-separated page numbers or ranges. Valid: 1–{total}.")

            if pages_input and st.button("Extract Pages", key="eb"):
                indices = parse_range(pages_input, total)
                with st.spinner("Extracting…"):
                    out = copy_pages(reader, indices)
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
    ph("↕️", "Reorder Pages",
       "Rearrange pages into any order.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="rou")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"))

            example = ", ".join(str(i) for i in range(total, 0, -1))
            order_input = st.text_input(
                f"New page order — enter all {total} page number(s) once each",
                placeholder=f"Reversed example: {example}",
                key="roi",
            )
            show_alert("info", "ℹ️",
                       f"Enter all {total} page numbers separated by commas in your desired order.")

            if order_input and st.button("Reorder Pages", key="rob"):
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
                            out = copy_pages(reader, [n - 1 for n in nums])
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
    ph("🖼️", "Images → PDF",
       "Convert JPG, PNG, TIFF, WebP or BMP images into a single PDF.")

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
                pil_images.append(img)
                with cols[idx % n_cols]:
                    st.image(img, use_container_width=True,
                             caption=f"{idx+1}. {img_file.name[:16]}")
            except Exception as exc:
                bad.append(f"{img_file.name} ({exc})")
        card_end()

        if bad:
            show_alert("warn", "⚠️", f"Could not open: {'; '.join(bad)}")

        if pil_images and st.button("Convert to PDF", key="i2b"):
            try:
                prog = st.progress(0, text="Processing images…")
                if fit == "A4 portrait (white background)":
                    W, H    = 2480, 3508
                    fitted  = []
                    for i, img in enumerate(pil_images):
                        rgb = img.convert("RGB")
                        rgb.thumbnail((W, H), Image.LANCZOS)
                        canvas = Image.new("RGB", (W, H), (255, 255, 255))
                        canvas.paste(rgb, ((W - rgb.width) // 2, (H - rgb.height) // 2))
                        fitted.append(canvas)
                        prog.progress((i + 1) / len(pil_images),
                                      text=f"Fitting image {i+1}/{len(pil_images)}")
                    pil_images = fitted

                final = []
                for i, img in enumerate(pil_images):
                    b = io.BytesIO()
                    img.convert("RGB").save(b, "JPEG", quality=quality)
                    b.seek(0)
                    final.append(Image.open(b))
                    prog.progress((i + 1) / len(pil_images),
                                  text=f"Encoding image {i+1}/{len(pil_images)}")

                prog.progress(1.0, text="Building PDF…")
                out = images_to_pdf(final)
                prog.empty()
                st.success(f"✅  {len(final)}-page PDF created ({fmt_bytes(len(out))}).")
                st.download_button("⬇️  Download images.pdf",
                                   out, "images.pdf", "application/pdf", key="i2d")
            except Exception as e:
                st.error(f"Conversion failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload one or more images above to get started.")


# ─── 7 · OPTIMIZE ────────────────────────────────────────────────────────────
elif tool == EXTRA[0]:
    ph("⚡", "Optimize PDF",
       "Deduplicate objects and compress internal streams to shrink file size.")
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

            compress_streams = st.checkbox("Compress content streams (recommended)", value=True, key="ocs")

            if st.button("Optimize", key="opb"):
                w    = PdfWriter()
                prog = st.progress(0, text="Optimizing…")
                for i, page in enumerate(reader.pages):
                    w.add_page(page)
                    if compress_streams:
                        w.pages[-1].compress_content_streams()
                    prog.progress((i + 1) / total, text=f"Page {i+1}/{total}")
                w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
                prog.progress(1.0, text="Finalizing…")
                out = writer_to_bytes(w)
                prog.empty()
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
    ph("🗜️", "Compress PDF",
       "Re-compress internal streams to reduce file size.")
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

            if st.button("Compress", key="cpb"):
                w    = PdfWriter()
                prog = st.progress(0, text="Compressing…")
                for i, page in enumerate(reader.pages):
                    w.add_page(page)
                    w.pages[-1].compress_content_streams()
                    prog.progress((i + 1) / total, text=f"Page {i+1}/{total}")
                w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
                prog.progress(1.0, text="Finalizing…")
                out = writer_to_bytes(w)
                prog.empty()
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
                try:
                    reader  = PdfReader(io.BytesIO(data), strict=False)
                    w       = PdfWriter()
                    skipped = 0
                    total_r = len(reader.pages)
                    prog    = st.progress(0, text="Repairing…")
                    for i, page in enumerate(reader.pages):
                        try:
                            w.add_page(page)
                        except Exception as page_err:
                            skipped += 1
                            st.warning(f"Page {i+1} skipped: {page_err}")
                        prog.progress((i + 1) / total_r, text=f"Page {i+1}/{total_r}")
                    prog.empty()

                    if len(w.pages) == 0:
                        show_alert("err", "❌",
                                   "No pages could be recovered. The file may be too severely damaged.")
                    else:
                        out = writer_to_bytes(w)
                        st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                        if skipped:
                            show_alert("warn", "⚠️",
                                       f"{skipped} page(s) were unrecoverable and skipped.")
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
    ph("🔄", "Rotate Pages",
       "Rotate all pages or a specific range by 90°, 180°, or 270°.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="rotu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

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
            if scope == "Specific pages / range":
                pages_input = st.text_input("Pages to rotate",
                                            placeholder=f"e.g.  1, 3-6  (1 to {total})",
                                            key="rotpi")
                show_alert("info", "ℹ️", f"Comma-separated page numbers or ranges. Valid: 1–{total}.")

            if st.button("Rotate PDF", key="rotb"):
                angle_map = {
                    "90° clockwise": 90,
                    "180°": 180,
                    "90° counter-clockwise": 270,
                }
                deg = angle_map[angle]

                if scope == "Specific pages / range":
                    if not pages_input:
                        show_alert("err", "❌", "Enter page numbers to rotate.")
                        st.stop()
                    rotate_set = set(parse_range(pages_input, total))
                else:
                    rotate_set = set(range(total))

                w    = PdfWriter()
                prog = st.progress(0, text="Rotating…")
                for i, page in enumerate(reader.pages):
                    w.add_page(page)
                    if i in rotate_set:
                        w.pages[-1].rotate(deg)
                    prog.progress((i + 1) / total, text=f"Page {i+1}/{total}")
                prog.empty()
                out = writer_to_bytes(w)
                st.success(f"✅  Rotated {len(rotate_set)} page(s) by {angle}.")
                st.download_button("⬇️  Download rotated.pdf",
                                   out, "rotated.pdf", "application/pdf", key="rotd")
        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Rotation failed: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 11 · PDF → IMAGES ───────────────────────────────────────────────────────
elif tool == NEW_A[1]:
    ph("📸", "PDF → Images",
       "Export every page (or a range) as PNG or JPEG images, delivered as a ZIP.")
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
                    indices   = parse_range(pages_input, total)
                    first_p   = indices[0] + 1
                    last_p    = indices[-1] + 1
                else:
                    indices = list(range(total))
                    first_p, last_p = 1, total

                prog = st.progress(0, text="Rasterising pages…")
                images = convert_from_bytes(
                    data,
                    dpi=dpi,
                    first_page=first_p,
                    last_page=last_p,
                    fmt=fmt.lower(),
                )
                # If specific (non-contiguous) range requested, filter further
                if scope == "Specific range":
                    needed_offsets = {i - (first_p - 1) for i in indices}
                    images = [img for k, img in enumerate(images) if k in needed_offsets]

                files_dict = {}
                ext = "jpg" if fmt == "JPEG" else "png"
                for k, img in enumerate(images):
                    page_num = indices[k] + 1
                    b = io.BytesIO()
                    save_kw = {"quality": 92} if fmt == "JPEG" else {}
                    img.save(b, format=fmt, **save_kw)
                    files_dict[f"page_{page_num:04d}.{ext}"] = b.getvalue()
                    prog.progress((k + 1) / len(images), text=f"Page {page_num}/{total}")

                prog.empty()
                zb = build_zip(files_dict)
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
    ph("💧", "Watermark PDF",
       "Stamp a text watermark diagonally across every page.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="wmu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

            col1, col2 = st.columns(2)
            with col1:
                wm_text  = st.text_input("Watermark text", value="CONFIDENTIAL", key="wmt")
            with col2:
                wm_opacity = st.slider("Opacity", 5, 60, 20, key="wmo",
                                       help="Lower = more transparent")

            col3, col4 = st.columns(2)
            with col3:
                wm_color = st.selectbox("Color",
                                        ["Gray", "Red", "Blue", "Black"],
                                        key="wmc")
            with col4:
                wm_size = st.selectbox("Font size", [24, 36, 48, 60, 72], index=2, key="wms")

            if wm_text.strip() and st.button("Apply Watermark", key="wmb"):
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
                    r, g, b = color_map[wm_color]
                    alpha   = wm_opacity / 100.0

                    def make_watermark_page(width: float, height: float) -> bytes:
                        buf = io.BytesIO()
                        c   = rl_canvas.Canvas(buf, pagesize=(width, height))
                        c.saveState()
                        c.setFont("Helvetica-Bold", wm_size)
                        c.setFillColor(Color(r, g, b, alpha=alpha))
                        c.translate(width / 2, height / 2)
                        c.rotate(45)
                        c.drawCentredString(0, 0, wm_text)
                        c.restoreState()
                        c.save()
                        return buf.getvalue()

                    w    = PdfWriter()
                    prog = st.progress(0, text="Applying watermark…")
                    for i, page in enumerate(reader.pages):
                        box     = page.mediabox
                        pw, ph  = float(box.width), float(box.height)
                        wm_pdf  = PdfReader(io.BytesIO(make_watermark_page(pw, ph)))
                        page.merge_page(wm_pdf.pages[0])
                        w.add_page(page)
                        prog.progress((i + 1) / total, text=f"Page {i+1}/{total}")

                    prog.empty()
                    out = writer_to_bytes(w)
                    st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                    st.success(f"✅  Watermark applied to {total} page(s).")
                    st.download_button("⬇️  Download watermarked.pdf",
                                       out, "watermarked.pdf", "application/pdf", key="wmd")

                except ImportError:
                    show_alert("err", "❌",
                               "reportlab is not installed. Run: <code>pip install reportlab</code>")
                except Exception as e:
                    st.error(f"Watermark failed: {e}\n\n{traceback.format_exc()}")
            elif not wm_text.strip():
                show_alert("warn", "⚠️", "Enter watermark text above.")

        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Error: {e}\n\n{traceback.format_exc()}")
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

                col1, col2 = st.columns(2)
                with col1:
                    user_pw  = st.text_input("User password (required to open)", type="password", key="ppuw")
                with col2:
                    owner_pw = st.text_input("Owner password (optional, for permissions)",
                                             type="password", key="ppow",
                                             help="Leave blank to use the same as user password.")

                if user_pw and st.button("Add Password", key="ppb"):
                    try:
                        w = PdfWriter()
                        for page in reader.pages:
                            w.add_page(page)
                        eff_owner = owner_pw if owner_pw else user_pw
                        w.encrypt(user_password=user_pw, owner_password=eff_owner)
                        out = writer_to_bytes(w)
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
                   "Only remove passwords from files you own or have permission to unlock.")
        f = st.file_uploader("Upload a password-protected PDF", type="pdf", key="upu")
        if f:
            try:
                data = get_bytes(f)
                check_file_size(data, f.name)
                pill_row((fmt_bytes(len(data)), ""))

                pw = st.text_input("Current password", type="password", key="upw")

                if pw and st.button("Remove Password", key="upb"):
                    try:
                        reader = validate_pdf_with_password(data, f.name, pw)
                        total  = len(reader.pages)
                        w = PdfWriter()
                        for page in reader.pages:
                            w.add_page(page)
                        out = writer_to_bytes(w)
                        st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                        st.success(f"✅  Password removed — {total} page(s) unlocked.")
                        st.download_button("⬇️  Download unlocked.pdf",
                                           out, "unlocked.pdf", "application/pdf", key="upd")
                    except ValueError as e:
                        show_alert("err", "❌", str(e))
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
    ph("📝", "Extract Text",
       "Pull all readable text out of a PDF — by page or as a single document.")

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
                if scope == "Specific range":
                    if not pages_input:
                        show_alert("err", "❌", "Enter page numbers to extract.")
                        st.stop()
                    indices = parse_range(pages_input, total)
                else:
                    indices = list(range(total))

                prog  = st.progress(0, text="Extracting text…")
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
                    prog.progress((k + 1) / len(indices), text=f"Page {i+1}/{total}")
                prog.empty()

                separator = "\n\n" if layout == "Single document" else "\n\n"
                full_text = separator.join(parts)
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
                    st.text_area("Extracted text", full_text, height=320, key="xtout")
                    txt_bytes = full_text.encode("utf-8")
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
    ph("🏷️", "Edit Metadata",
       "View and update the title, author, subject, keywords, and other document properties.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="mdu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

            # Read existing metadata
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
            col1, col2 = st.columns(2)
            with col1:
                title    = st.text_input("Title",    value=get_meta("/Title"),    key="mdtitle")
                author   = st.text_input("Author",   value=get_meta("/Author"),   key="mdauthor")
                subject  = st.text_input("Subject",  value=get_meta("/Subject"),  key="mdsubject")
            with col2:
                keywords = st.text_input("Keywords", value=get_meta("/Keywords"), key="mdkw")
                creator  = st.text_input("Creator",  value=get_meta("/Creator"),  key="mdcreator")
                producer = st.text_input("Producer", value=get_meta("/Producer"), key="mdprod")

            strip_dates = st.checkbox("Strip creation/modification timestamps", value=False, key="mdstrip")

            if st.button("Save Metadata", key="mdb"):
                w = PdfWriter()
                for page in reader.pages:
                    w.add_page(page)

                new_meta = {
                    "/Title":    title,
                    "/Author":   author,
                    "/Subject":  subject,
                    "/Keywords": keywords,
                    "/Creator":  creator,
                    "/Producer": producer,
                }
                if not strip_dates:
                    for key in ("/CreationDate", "/ModDate"):
                        if key in meta:
                            new_meta[key] = str(meta[key])

                w.add_metadata({k: v for k, v in new_meta.items() if v})
                out = writer_to_bytes(w)
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                st.success("✅  Metadata updated.")
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
    ph("🔢", "Add Page Numbers",
       "Stamp page numbers onto every page using reportlab, with full position and style control.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="pnu")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)
            pill_row((f"{total} pages", "a"), (fmt_bytes(len(data)), ""))

            col1, col2, col3 = st.columns(3)
            with col1:
                position = st.selectbox("Position",
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
                margin = st.number_input("Margin from edge (pt)", min_value=4, max_value=72,
                                         value=18, key="pnmargin")

            if st.button("Add Page Numbers", key="pnb"):
                try:
                    from reportlab.pdfgen import canvas as rl_canvas
                    from reportlab.lib.colors import black

                    def make_number_overlay(width: float, height: float,
                                            label: str) -> bytes:
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

                    w    = PdfWriter()
                    prog = st.progress(0, text="Stamping page numbers…")
                    for i, page in enumerate(reader.pages):
                        box    = page.mediabox
                        pw, ph = float(box.width), float(box.height)
                        n      = i + int(start_num)
                        label  = fmt_str.replace("{n}", str(n)).replace("{t}", str(total))
                        overlay_pdf = PdfReader(io.BytesIO(make_number_overlay(pw, ph, label)))
                        page.merge_page(overlay_pdf.pages[0])
                        w.add_page(page)
                        prog.progress((i + 1) / total, text=f"Page {i+1}/{total}")

                    prog.empty()
                    out = writer_to_bytes(w)
                    st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                    st.success(f"✅  Page numbers added to {total} page(s).")
                    st.download_button("⬇️  Download numbered.pdf",
                                       out, "numbered.pdf", "application/pdf", key="pnd")

                except ImportError:
                    show_alert("err", "❌",
                               "reportlab is not installed. Run: <code>pip install reportlab</code>")
                except Exception as e:
                    st.error(f"Page numbering failed: {e}\n\n{traceback.format_exc()}")

        except ValueError as e:
            show_alert("err", "❌", str(e))
        except Exception as e:
            st.error(f"Error: {e}\n\n{traceback.format_exc()}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 17 · CROP PAGES ─────────────────────────────────────────────────────────
elif tool == NEW_B[3]:
    ph("✂️", "Crop Pages",
       "Adjust the visible area of every page by setting new margins. "
       "Uses the PDF crop box — the original content is preserved and recoverable.")

    show_alert("warn", "⚠️",
               "Crop box changes what's <em>visible</em> — it does not permanently delete content outside "
               "the crop area. Use Remove Pages if you need to delete entire pages.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="cru")
    if f:
        try:
            data   = get_bytes(f)
            reader = validate_pdf(data, f.name)
            total  = len(reader.pages)

            # Sample first page dimensions for reference
            sample  = reader.pages[0].mediabox
            pw_pt   = float(sample.width)
            ph_pt   = float(sample.height)
            pw_mm   = pw_pt * 25.4 / 72
            ph_mm   = ph_pt * 25.4 / 72

            pill_row(
                (f"{total} pages", "a"),
                (fmt_bytes(len(data)), ""),
                (f"Page 1: {pw_mm:.0f}×{ph_mm:.0f} mm  ({pw_pt:.0f}×{ph_pt:.0f} pt)", ""),
            )
            show_alert("info", "ℹ️",
                       f"First page is {pw_mm:.0f}×{ph_mm:.0f} mm. "
                       "Enter margins to remove from each edge (in mm). "
                       "0 = no crop on that side.")

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
                prog = st.progress(0, text="Cropping…")
                for i, page in enumerate(reader.pages):
                    if i in crop_set:
                        mb   = page.mediabox
                        x0   = float(mb.left)   + l_pt
                        y0   = float(mb.bottom) + b_pt
                        x1   = float(mb.right)  - r_pt
                        y1   = float(mb.top)    - t_pt
                        if x1 <= x0 or y1 <= y0:
                            show_alert("err", "❌",
                                       f"Page {i+1}: crop margins exceed page size. Reduce values.")
                            st.stop()
                        from pypdf.generic import RectangleObject
                        page.cropbox = RectangleObject((x0, y0, x1, y1))
                    w.add_page(page)
                    prog.progress((i + 1) / total, text=f"Page {i+1}/{total}")

                prog.empty()
                out = writer_to_bytes(w)
                new_w_mm = (float(reader.pages[0].mediabox.width) - l_pt - r_pt) * 25.4 / 72
                new_h_mm = (float(reader.pages[0].mediabox.height) - t_pt - b_pt) * 25.4 / 72
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
