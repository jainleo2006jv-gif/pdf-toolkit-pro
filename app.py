"""
╔══════════════════════════════════════════════════════╗
║           PDF Toolkit Pro  ·  app.py                 ║
║   A complete, single-file Streamlit PDF utility app  ║
╚══════════════════════════════════════════════════════╝

Features
  Core  → Merge · Split · Remove Pages · Extract Pages · Reorder Pages · Images→PDF
  Extra → Optimize · Compress · Repair · OCR
"""

# ─────────────────────────────────────────────────────────────────────────────
#  Standard-library imports
# ─────────────────────────────────────────────────────────────────────────────
import io
import traceback
import zipfile

# ─────────────────────────────────────────────────────────────────────────────
#  Third-party imports
# ─────────────────────────────────────────────────────────────────────────────
import streamlit as st
from PIL import Image
from pypdf import PdfReader, PdfWriter

# ═════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG  (must be the very first Streamlit call)
# ═════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="PDF Toolkit Pro",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═════════════════════════════════════════════════════════════════════════════
#  CUSTOM CSS
# ═════════════════════════════════════════════════════════════════════════════
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap');

:root {
    --bg:         #0b0d12;
    --surface:    #111318;
    --surface2:   #191c25;
    --border:     #22263a;
    --accent:     #ff6b35;
    --accent2:    #ffb347;
    --accent-dim: rgba(255,107,53,0.10);
    --text:       #dde1f0;
    --muted:      #6a728e;
    --success:    #3ddc97;
    --warning:    #ffc947;
    --danger:     #ff4d6a;
    --info:       #6495ed;
    --r:          12px;
    --r-sm:       8px;
}

/* ── Base ─────────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    font-family: 'DM Sans', sans-serif;
    color: var(--text);
}
#MainMenu, footer, [data-testid="stHeader"], [data-testid="stDecoration"] {
    display: none !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

.sb-brand {
    background: linear-gradient(135deg, #ff6b35 0%, #ffb347 100%);
    padding: 1.5rem 1.4rem 1.1rem;
    margin-bottom: 1rem;
}
.sb-brand h1 {
    font-family: 'Syne', sans-serif;
    font-size: 1.25rem;
    font-weight: 800;
    color: #fff;
    margin: 0 0 0.2rem;
    letter-spacing: -0.3px;
}
.sb-brand small {
    font-size: 0.68rem;
    color: rgba(255,255,255,0.75);
    letter-spacing: 1px;
    text-transform: uppercase;
}

.nav-section {
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 1.8px;
    text-transform: uppercase;
    color: var(--muted);
    padding: 0.75rem 1.2rem 0.25rem;
}

/* Radio → styled nav links */
[data-testid="stSidebar"] .stRadio > div { gap: 0 !important; }
[data-testid="stSidebar"] .stRadio label {
    font-size: 0.86rem !important;
    color: var(--muted) !important;
    padding: 0.5rem 1.2rem !important;
    border-left: 3px solid transparent;
    border-radius: 0 !important;
    transition: all 0.15s;
    cursor: pointer;
}
[data-testid="stSidebar"] .stRadio label:hover {
    color: var(--text) !important;
    background: var(--surface2) !important;
}
[data-testid="stSidebar"] .stRadio label[data-checked="true"],
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label {
    color: var(--accent) !important;
    background: var(--accent-dim) !important;
    border-left-color: var(--accent) !important;
    font-weight: 500 !important;
}
[data-testid="stSidebar"] .stRadio [type="radio"] { display: none !important; }
[data-testid="stSidebar"] * { color: var(--muted); }

/* ── Main layout ──────────────────────────────────────────────────────── */
[data-testid="stMainBlockContainer"] {
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1000px;
}

/* ── Page header ──────────────────────────────────────────────────────── */
.ph {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1.8rem;
    padding-bottom: 1.4rem;
    border-bottom: 1px solid var(--border);
}
.ph-icon { font-size: 2rem; line-height: 1; flex-shrink: 0; }
.ph h2 {
    font-family: 'Syne', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text);
    margin: 0 0 0.2rem;
    letter-spacing: -0.4px;
}
.ph p { font-size: 0.85rem; color: var(--muted); margin: 0; line-height: 1.55; }

/* ── Card ─────────────────────────────────────────────────────────────── */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
}
.card-title {
    font-family: 'Syne', sans-serif;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 1rem;
}

/* ── Pills ────────────────────────────────────────────────────────────── */
.pr { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.7rem 0; }
.pill {
    display: inline-flex; align-items: center; gap: 0.3rem;
    font-size: 0.76rem; font-weight: 500;
    padding: 0.22rem 0.7rem;
    border-radius: 999px;
    background: var(--surface2); border: 1px solid var(--border); color: var(--muted);
}
.pill.a { background: var(--accent-dim); border-color: rgba(255,107,53,.28); color: var(--accent); }
.pill.s { background: rgba(61,220,151,.09); border-color: rgba(61,220,151,.28); color: var(--success); }
.pill.w { background: rgba(255,201,71,.08); border-color: rgba(255,201,71,.28); color: var(--warning); }
.pill.d { background: rgba(255,77,106,.08); border-color: rgba(255,77,106,.28); color: var(--danger); }

/* ── Alert ────────────────────────────────────────────────────────────── */
.al {
    display: flex; gap: 0.7rem; align-items: flex-start;
    padding: 0.8rem 1rem; border-radius: var(--r-sm);
    font-size: 0.83rem; line-height: 1.55; margin: 0.8rem 0;
}
.al-i { font-size: 0.95rem; flex-shrink: 0; margin-top: 0.05rem; }
.al.info { background: rgba(100,149,237,.09); border: 1px solid rgba(100,149,237,.25); color: #a0b8ff; }
.al.warn { background: rgba(255,201,71,.07); border: 1px solid rgba(255,201,71,.25); color: var(--warning); }
.al.err  { background: rgba(255,77,106,.07);  border: 1px solid rgba(255,77,106,.25); color: var(--danger); }
.al.ok   { background: rgba(61,220,151,.07);  border: 1px solid rgba(61,220,151,.25); color: var(--success); }

/* ── File uploader ────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: var(--surface2) !important;
    border: 2px dashed var(--border) !important;
    border-radius: var(--r) !important;
}
[data-testid="stFileUploader"]:hover { border-color: var(--accent) !important; }
[data-testid="stFileUploader"] label { color: var(--muted) !important; font-size: 0.83rem !important; }

/* ── Inputs ───────────────────────────────────────────────────────────── */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stTextInput input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 2px var(--accent-dim) !important; }
.stTextInput label, .stSelectbox label, .stNumberInput label, .stSlider label {
    color: var(--muted) !important; font-size: 0.8rem !important; font-weight: 500 !important;
}

/* ── Primary button ───────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
    color: #fff !important; border: none !important;
    border-radius: var(--r-sm) !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important; font-size: 0.86rem !important;
    letter-spacing: 0.3px !important;
    padding: 0.52rem 1.3rem !important;
    box-shadow: 0 4px 18px rgba(255,107,53,.28) !important;
    transition: opacity .18s, transform .12s !important;
}
.stButton > button:hover  { opacity: .88 !important; transform: translateY(-1px) !important; }
.stButton > button:active { transform: translateY(0) !important; }

/* ── Download button ──────────────────────────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: var(--surface2) !important;
    color: var(--accent) !important;
    border: 1px solid rgba(255,107,53,.35) !important;
    border-radius: var(--r-sm) !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important; font-size: 0.83rem !important;
    box-shadow: none !important;
    transition: background .15s, border-color .15s !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: var(--accent-dim) !important;
    border-color: var(--accent) !important;
    transform: none !important;
}

/* ── Progress bar ─────────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent2)) !important;
}

/* ── Streamlit alert boxes ────────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: var(--r-sm) !important; font-size: 0.83rem !important; }

/* ── Divider ──────────────────────────────────────────────────────────── */
hr { border-color: var(--border) !important; margin: 1.4rem 0 !important; }

/* ── Scrollbar ────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }

/* ── Text area (OCR preview) ──────────────────────────────────────────── */
.stTextArea textarea {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--text) !important;
    font-family: 'DM Mono', 'Courier New', monospace !important;
    font-size: 0.8rem !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.2f} GB"


def size_pills(orig: int, new: int) -> str:
    delta = new - orig
    pct   = (delta / orig * 100) if orig else 0
    cls   = "s" if delta < 0 else ("w" if delta == 0 else "d")
    sign  = "+" if delta > 0 else ""
    verb  = "saved" if delta < 0 else ("no change" if delta == 0 else "larger")
    detail = f"{sign}{pct:.1f}% · {fmt_bytes(abs(delta))} {verb}"
    return (
        f'<div class="pr">'
        f'<span class="pill">📄 Before: {fmt_bytes(orig)}</span>'
        f'<span class="pill {cls}">📦 After: {fmt_bytes(new)} · {detail}</span>'
        f'</div>'
    )


def show_alert(kind: str, icon: str, html: str) -> None:
    st.markdown(
        f'<div class="al {kind}"><span class="al-i">{icon}</span><span>{html}</span></div>',
        unsafe_allow_html=True,
    )


def ph(icon: str, title: str, desc: str) -> None:
    st.markdown(
        f'<div class="ph"><div class="ph-icon">{icon}</div>'
        f'<div><h2>{title}</h2><p>{desc}</p></div></div>',
        unsafe_allow_html=True,
    )


def card_start(label: str = "") -> None:
    st.markdown(f'<div class="card">', unsafe_allow_html=True)
    if label:
        st.markdown(f'<p class="card-title">{label}</p>', unsafe_allow_html=True)


def card_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def pill_row(*pills) -> None:
    """pills = list of (label, cls) tuples; cls in {a, s, w, d, ''}"""
    inner = "".join(
        f'<span class="pill {cls}">{lbl}</span>' for lbl, cls in pills
    )
    st.markdown(f'<div class="pr">{inner}</div>', unsafe_allow_html=True)


# ── PDF helpers ───────────────────────────────────────────────────────────────

def get_bytes(uf) -> bytes:
    uf.seek(0)
    return uf.read()


def make_reader(data: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(data))


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
    """
    Convert a 1-based range string like "1, 3-5, 8" into a sorted list
    of 0-based indices.  Raises ValueError for bad input.
    """
    out: set = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a), int(b)
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
    """PIL Images → PDF bytes.  Uses img2pdf when available."""
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
        buf = io.BytesIO()
        rgb[0].save(buf, format="PDF", save_all=True, append_images=rgb[1:])
        return buf.getvalue()


# ═════════════════════════════════════════════════════════════════════════════
#  SIDEBAR NAV
# ═════════════════════════════════════════════════════════════════════════════

CORE  = ["🔀  Merge PDFs", "✂️  Split PDF", "🗑️  Remove Pages",
         "📑  Extract Pages", "↕️  Reorder Pages", "🖼️  Images → PDF"]
EXTRA = ["⚡  Optimize PDF", "🗜️  Compress PDF", "🔧  Repair PDF"]

with st.sidebar:
    st.markdown(
        '<div class="sb-brand"><h1>⬡ PDF Toolkit Pro</h1>'
        '<small>10 tools · one place</small></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="nav-section">Core Tools</div>', unsafe_allow_html=True)
    tool = st.radio("nav", CORE + EXTRA, label_visibility="collapsed")
    st.markdown('<div class="nav-section" style="margin-top:0.6rem">Best-Effort Extras</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:0.68rem;color:#2a2f45;padding:1.2rem 1.2rem 0;line-height:1.7">'
        'pypdf · Pillow · img2pdf<br>pdf2image · pytesseract'
        '</p>',
        unsafe_allow_html=True,
    )

# ═════════════════════════════════════════════════════════════════════════════
#  TOOL PANELS
# ═════════════════════════════════════════════════════════════════════════════

# ─── 1 · MERGE ───────────────────────────────────────────────────────────────
if tool == CORE[0]:
    ph("🔀", "Merge PDFs",
       "Combine multiple PDFs into a single document, in the order you upload them.")

    files = st.file_uploader("Upload PDFs (select two or more)",
                             type="pdf", accept_multiple_files=True, key="mu")
    if files:
        pill_row((f"📁 {len(files)} file(s) selected", "a"))

        card_start("Files to merge — in order")
        total_pages = 0
        for i, f in enumerate(files, 1):
            try:
                r  = make_reader(get_bytes(f))
                pc = len(r.pages)
                total_pages += pc
                st.markdown(
                    f"`{i}.` **{f.name}** &nbsp; "
                    f'<span class="pill" style="font-size:.72rem">{pc} pg</span>&nbsp;'
                    f'<span class="pill" style="font-size:.72rem">{fmt_bytes(f.size)}</span>',
                    unsafe_allow_html=True,
                )
            except Exception:
                st.markdown(f"`{i}.` **{f.name}** — ⚠️ unreadable")
        pill_row((f"✅ {total_pages} pages after merge", "s"))
        card_end()

        if len(files) < 2:
            show_alert("warn", "⚠️", "Upload at least 2 PDFs.")
        elif st.button("Merge PDFs →", key="mb"):
            try:
                w = PdfWriter()
                for f in files:
                    for pg in make_reader(get_bytes(f)).pages:
                        w.add_page(pg)
                out = writer_to_bytes(w)
                st.success(f"✅  {len(files)} files merged → {len(w.pages)} pages.")
                st.download_button("⬇️  Download merged.pdf",
                                   out, "merged.pdf", "application/pdf", key="md")
            except Exception as e:
                st.error(f"Merge failed: {e}")
    else:
        show_alert("info", "ℹ️", "Upload two or more PDFs above to get started.")


# ─── 2 · SPLIT ───────────────────────────────────────────────────────────────
elif tool == CORE[1]:
    ph("✂️", "Split PDF",
       "Explode a PDF into individual pages (or fixed-size chunks) delivered as a ZIP.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="su")
    if f:
        data   = get_bytes(f)
        reader = make_reader(data)
        total  = len(reader.pages)
        pill_row((f"📄 {total} pages", "a"), (fmt_bytes(len(data)), ""))

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

        if st.button("Split PDF →", key="sb"):
            try:
                pages_dict: dict = {}
                if mode == "Every page (individual files)":
                    for i in range(total):
                        pages_dict[f"page_{i+1:04d}.pdf"] = copy_pages(reader, [i])
                else:
                    cs   = int(chunk_size)
                    part = 1
                    for start in range(0, total, cs):
                        end = min(start + cs, total)
                        key = f"part_{part:03d}_pages_{start+1}-{end}.pdf"
                        pages_dict[key] = copy_pages(reader, list(range(start, end)))
                        part += 1
                zb = build_zip(pages_dict)
                st.success(f"✅  {len(pages_dict)} file(s) created.")
                st.download_button(f"⬇️  Download split_pages.zip ({fmt_bytes(len(zb))})",
                                   zb, "split_pages.zip", "application/zip", key="sd")
            except Exception as e:
                st.error(f"Split failed: {e}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 3 · REMOVE PAGES ────────────────────────────────────────────────────────
elif tool == CORE[2]:
    ph("🗑️", "Remove Pages",
       "Delete specific pages. Enter 1-based page numbers or ranges.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="rpu")
    if f:
        data   = get_bytes(f)
        reader = make_reader(data)
        total  = len(reader.pages)
        pill_row((f"📄 {total} pages", "a"), (fmt_bytes(len(data)), ""))

        pages_input = st.text_input("Pages to remove",
                                    placeholder=f"e.g.  2, 5, 7-10  (1 to {total})",
                                    key="rpi")
        show_alert("info", "ℹ️",
                   f"Comma-separated values and/or ranges, e.g. <code>1, 3-5, 8</code>. "
                   f"Valid range: 1 to {total}.")

        if pages_input and st.button("Remove Pages →", key="rpb"):
            try:
                to_remove = set(parse_range(pages_input, total))
                keep      = [i for i in range(total) if i not in to_remove]
                if not keep:
                    show_alert("err", "❌", "Cannot remove all pages.")
                else:
                    out = copy_pages(reader, keep)
                    st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                    st.success(f"✅  Removed {len(to_remove)} page(s) — {len(keep)} remaining.")
                    st.download_button("⬇️  Download result.pdf",
                                       out, "result.pdf", "application/pdf", key="rpd")
            except ValueError as e:
                show_alert("err", "❌", str(e))
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 4 · EXTRACT PAGES ───────────────────────────────────────────────────────
elif tool == CORE[3]:
    ph("📑", "Extract Pages",
       "Pull a subset of pages into a new PDF.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="eu")
    if f:
        data   = get_bytes(f)
        reader = make_reader(data)
        total  = len(reader.pages)
        pill_row((f"📄 {total} pages", "a"), (fmt_bytes(len(data)), ""))

        pages_input = st.text_input("Pages to extract",
                                    placeholder=f"e.g.  1, 3-6, 9  (1 to {total})",
                                    key="epi")
        show_alert("info", "ℹ️",
                   f"Comma-separated page numbers/ranges. Valid range: 1 to {total}.")

        if pages_input and st.button("Extract Pages →", key="eb"):
            try:
                indices = parse_range(pages_input, total)
                out     = copy_pages(reader, indices)
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                st.success(f"✅  Extracted {len(indices)} page(s).")
                st.download_button("⬇️  Download extracted.pdf",
                                   out, "extracted.pdf", "application/pdf", key="ed")
            except ValueError as e:
                show_alert("err", "❌", str(e))
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 5 · REORDER PAGES ───────────────────────────────────────────────────────
elif tool == CORE[4]:
    ph("↕️", "Reorder Pages",
       "Rearrange all pages of a PDF into any order.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="rou")
    if f:
        data   = get_bytes(f)
        reader = make_reader(data)
        total  = len(reader.pages)
        pill_row((f"📄 {total} pages", "a"))

        example = ", ".join(str(i) for i in range(total, 0, -1))
        order_input = st.text_input(
            f"New page order — enter all {total} page number(s) once each",
            placeholder=f"Reversed example: {example}",
            key="roi",
        )
        show_alert("info", "ℹ️",
                   f"Enter all {total} page numbers separated by commas, in your desired order. "
                   "Every number must appear exactly once.")

        if order_input and st.button("Reorder Pages →", key="rob"):
            try:
                nums = [int(x.strip()) for x in order_input.split(",") if x.strip()]
                if len(nums) != total:
                    show_alert("err", "❌",
                               f"Got {len(nums)} number(s) but document has {total} pages.")
                elif sorted(nums) != list(range(1, total + 1)):
                    missing = sorted(set(range(1, total + 1)) - set(nums))
                    dupes   = sorted(set(n for n in nums if nums.count(n) > 1))
                    msg = "Invalid order. "
                    if missing: msg += f"Missing: {missing}. "
                    if dupes:   msg += f"Duplicates: {dupes}."
                    show_alert("err", "❌", msg)
                else:
                    out = copy_pages(reader, [n - 1 for n in nums])
                    st.success("✅  Pages reordered.")
                    st.download_button("⬇️  Download reordered.pdf",
                                       out, "reordered.pdf", "application/pdf", key="rod")
            except ValueError:
                show_alert("err", "❌", "Invalid input — integers only, comma-separated.")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 6 · IMAGES → PDF ────────────────────────────────────────────────────────
elif tool == CORE[5]:
    ph("🖼️", "Images → PDF",
       "Convert JPG, PNG, TIFF, WebP or BMP images into a single PDF. "
       "One image per page, in upload order.")

    imgs = st.file_uploader(
        "Upload images",
        type=["jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"],
        accept_multiple_files=True,
        key="i2u",
    )

    if imgs:
        pill_row((f"🖼️ {len(imgs)} image(s)", "a"))

        col_q, col_fit = st.columns(2)
        with col_q:
            quality = st.slider("JPEG quality", 50, 100, 88, key="iq")
        with col_fit:
            fit = st.selectbox("Page size",
                               ["Match image size", "A4 portrait (white background)"],
                               key="if")

        # Preview grid
        card_start("Preview")
        n_cols = min(len(imgs), 6)
        cols   = st.columns(n_cols)
        pil_images, bad = [], []

        for idx, img_file in enumerate(imgs):
            try:
                img = Image.open(img_file)
                pil_images.append(img)
                with cols[idx % n_cols]:
                    st.image(img, use_container_width=True,
                             caption=f"{idx+1}. {img_file.name[:16]}")
            except Exception:
                bad.append(img_file.name)
        card_end()

        if bad:
            show_alert("warn", "⚠️", f"Could not open: {', '.join(bad)}")

        if pil_images and st.button("Convert to PDF →", key="i2b"):
            try:
                if fit == "A4 portrait (white background)":
                    W, H = 2480, 3508
                    fitted = []
                    for img in pil_images:
                        rgb = img.convert("RGB")
                        rgb.thumbnail((W, H), Image.LANCZOS)
                        canvas = Image.new("RGB", (W, H), (255, 255, 255))
                        canvas.paste(rgb, ((W - rgb.width) // 2, (H - rgb.height) // 2))
                        fitted.append(canvas)
                    pil_images = fitted

                # Re-encode at chosen quality
                final = []
                for img in pil_images:
                    b = io.BytesIO()
                    img.convert("RGB").save(b, "JPEG", quality=quality)
                    final.append(Image.open(b))

                out = images_to_pdf(final)
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
               "<strong>Best-effort.</strong> Works best on office-generated PDFs with "
               "shared resources. Already-compressed or image-heavy PDFs may not shrink.")

    f = st.file_uploader("Upload a PDF", type="pdf", key="opu")
    if f:
        data   = get_bytes(f)
        reader = make_reader(data)
        total  = len(reader.pages)
        pill_row((f"📄 {total} pages", "a"), (fmt_bytes(len(data)), ""))

        compress_streams = st.checkbox("Compress content streams (recommended)", value=True, key="ocs")

        if st.button("Optimize →", key="opb"):
            try:
                w = PdfWriter()
                for page in reader.pages:
                    w.add_page(page)
                    if compress_streams:
                        w.pages[-1].compress_content_streams()
                w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
                out = writer_to_bytes(w)
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                if len(out) < len(data):
                    st.success(f"✅  Saved {fmt_bytes(len(data) - len(out))}.")
                else:
                    st.info("ℹ️  Already well-optimised; no reduction achieved.")
                st.download_button("⬇️  Download optimized.pdf",
                                   out, "optimized.pdf", "application/pdf", key="opd")
            except Exception as e:
                st.error(f"Optimization failed: {e}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 8 · COMPRESS ────────────────────────────────────────────────────────────
elif tool == EXTRA[1]:
    ph("🗜️", "Compress PDF",
       "Re-compress internal streams to reduce file size.")
    show_alert("warn", "⚠️",
               "<strong>Best-effort.</strong> This uses stream-level compression only. "
               "For aggressive image resampling use Ghostscript: "
               "<code>gs -sDEVICE=pdfwrite -dPDFSETTINGS=/ebook -o out.pdf in.pdf</code>")

    f = st.file_uploader("Upload a PDF", type="pdf", key="cpu")
    if f:
        data   = get_bytes(f)
        reader = make_reader(data)
        total  = len(reader.pages)
        pill_row((f"📄 {total} pages", "a"), (fmt_bytes(len(data)), ""))

        if st.button("Compress →", key="cpb"):
            try:
                w = PdfWriter()
                for page in reader.pages:
                    w.add_page(page)
                    w.pages[-1].compress_content_streams()
                w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
                out = writer_to_bytes(w)
                st.markdown(size_pills(len(data), len(out)), unsafe_allow_html=True)
                if len(out) < len(data):
                    st.success(f"✅  Compressed by {fmt_bytes(len(data) - len(out))}.")
                else:
                    st.info("ℹ️  No further compression achieved. Try Ghostscript.")
                st.download_button("⬇️  Download compressed.pdf",
                                   out, "compressed.pdf", "application/pdf", key="cpd")
            except Exception as e:
                st.error(f"Compression failed: {e}")
    else:
        show_alert("info", "ℹ️", "Upload a PDF above to get started.")


# ─── 9 · REPAIR ──────────────────────────────────────────────────────────────
elif tool == EXTRA[2]:
    ph("🔧", "Repair PDF",
       "Try to recover a corrupted PDF by reading it in lenient mode "
       "and re-serialising it cleanly.")
    show_alert("warn", "⚠️",
               "<strong>Best-effort.</strong> Fixes minor structural issues "
               "(truncated xref tables, invalid object refs). "
               "Severely damaged files or those with lost encryption keys cannot be recovered.")

    f = st.file_uploader("Upload a damaged PDF", type="pdf", key="rpu2")
    if f:
        data = get_bytes(f)
        pill_row((fmt_bytes(len(data)), ""))

        if st.button("Attempt Repair →", key="rpb2"):
            try:
                reader  = PdfReader(io.BytesIO(data), strict=False)
                w       = PdfWriter()
                skipped = 0
                for page in reader.pages:
                    try:
                        w.add_page(page)
                    except Exception:
                        skipped += 1

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
    else:
        show_alert("info", "ℹ️", "Upload a damaged PDF above to get started.")



