#!/usr/bin/env python3
"""Export the executed notebook (markdown + CODE + outputs + plots) to HTML and PDF.

Why not nbconvert: this notebook uses non-standard cell ids ("#VSC-..."), which
fail nbconvert's JSON-schema validation. So we parse the .ipynb directly.

Outputs (in report_export/):
  Model_Efficiency_Comparison.html  - full workbook, code + results + plots
  Model_Efficiency_Comparison.pdf   - full workbook, code + results + plots
"""
from __future__ import annotations

import base64
import html
import json
import re
import tempfile
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

NB = Path("/home/skystarved/dev_workspaces/Model_Efficiency_Comparison.ipynb")
OUT = Path("/home/skystarved/dev_workspaces/report_export")
OUT.mkdir(parents=True, exist_ok=True)

nb = json.loads(NB.read_text())
CELLS = nb.get("cells", [])


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def src_of(cell) -> str:
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else str(s)


def outputs_of(cell):
    """Yield ('text', str) and ('png', bytes) in order."""
    for o in cell.get("outputs", []):
        otype = o.get("output_type")
        if otype == "stream":
            t = o.get("text", "")
            yield ("text", "".join(t) if isinstance(t, list) else str(t))
        elif otype in ("execute_result", "display_data"):
            data = o.get("data", {}) or {}
            if "image/png" in data:
                payload = data["image/png"]
                if isinstance(payload, list):
                    payload = "".join(payload)
                yield ("png", base64.b64decode(payload))
            if "text/plain" in data:
                t = data["text/plain"]
                yield ("text", "".join(t) if isinstance(t, list) else str(t))
        elif otype == "error":
            tb = o.get("traceback") or []
            yield ("text", "\n".join(re.sub(r"\x1b\[[0-9;]*m", "", l) for l in tb))


def ascii_safe(s: str) -> str:
    """Core-font fallback: strip anything outside latin-1."""
    return (
        str(s)
        .replace("\u2014", "-").replace("\u2013", "-")
        .replace("\u2018", "'").replace("\u2019", "'")
        .replace("\u201c", '"').replace("\u201d", '"')
        .replace("\u2192", "->").replace("\u2190", "<-")
        .replace("\u00d7", "x").replace("\u221a", "sqrt")
        .replace("\u2265", ">=").replace("\u2264", "<=")
        .replace("\u2026", "...").replace("\u00b7", ".")
        .encode("latin-1", "replace").decode("latin-1")
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. HTML  (full workbook: markdown + code + outputs + plots)
# ─────────────────────────────────────────────────────────────────────────────
def md_to_html(md: str) -> str:
    """Small markdown subset -> HTML (headings, lists, code fences, tables, inline)."""
    out, in_code, in_table = [], False, False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(raw))
            continue
        if line.startswith("|"):
            if not in_table:
                out.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            out.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if not line.strip():
            out.append("")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{html.escape(m.group(2))}</h{lvl}>")
            continue
        m = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if m:
            out.append(f"<li>{html.escape(m.group(1))}</li>")
            continue
        m = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if m:
            out.append(f"<li>{html.escape(m.group(2))}</li>")
            continue
        out.append(f"<p>{html.escape(line)}</p>")
    if in_table:
        out.append("</table>")
    if in_code:
        out.append("</code></pre>")
    body = "\n".join(out)
    # inline code + bold
    body = re.sub(r"`([^`]+)`", r"<code>\1</code>", body)
    body = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", body)
    return body


CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0 auto;
     max-width:1100px;padding:2rem;line-height:1.55;color:#1a1a1a;background:#fff}
h1{font-size:1.9rem;border-bottom:3px solid #2f7ed8;padding-bottom:.4rem}
h2{font-size:1.4rem;color:#1f5fa8;margin-top:2.2rem;border-bottom:1px solid #dde3ea;
   padding-bottom:.25rem}
h3{font-size:1.15rem;color:#2c3e50;margin-top:1.6rem}
table{border-collapse:collapse;margin:.8rem 0;font-size:.85rem}
td,th{border:1px solid #d7dde5;padding:.3rem .55rem}
tr:nth-child(even){background:#f7f9fc}
pre{background:#f5f7fa;border:1px solid #e1e6ed;border-radius:6px;padding:.75rem;
    overflow-x:auto;font-size:.8rem;line-height:1.35}
pre code{background:none;padding:0}
code{background:#eef1f5;padding:.1em .3em;border-radius:4px;font-size:.88em}
.cell{margin:1.4rem 0;border-left:3px solid #e3e8ef;padding-left:1rem}
.cell.code{border-left-color:#2f7ed8}
.cell.md{border-left-color:#9aa5b1}
.label{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;
       color:#7b8794;margin-bottom:.3rem;font-weight:600}
.out{background:#fbfcfd;border:1px solid #e8edf3;border-radius:6px;padding:.6rem;
     font-size:.78rem;white-space:pre-wrap;word-break:break-word;max-height:520px;
     overflow:auto}
img{max-width:100%;border:1px solid #dde3ea;border-radius:6px;margin:.6rem 0;
    background:#fff}
.toc{background:#f7f9fc;border:1px solid #e1e6ed;border-radius:8px;padding:1rem 1.4rem}
.toc a{color:#1f5fa8;text-decoration:none}
.toc a:hover{text-decoration:underline}
"""

html_parts = [
    "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
    "<meta name='viewport' content='width=device-width,initial-scale=1'>",
    "<title>LLM Efficiency &amp; Provider Value - Workbook</title>",
    f"<style>{CSS}</style></head><body>",
    "<h1>LLM Efficiency &amp; Provider-Value Analysis</h1>",
    "<p><em>Full workbook export - markdown, code, results and plots. "
    "Generated 2026-10-24.</em></p>",
]

# table of contents from markdown headings
toc = []
for i, c in enumerate(CELLS):
    if c.get("cell_type") == "markdown":
        for line in src_of(c).splitlines():
            m = re.match(r"^(#{1,3})\s+(.*)$", line.strip())
            if m:
                toc.append((len(m.group(1)), m.group(2), f"cell-{i}"))
if toc:
    html_parts.append("<div class='toc'><strong>Contents</strong><ul>")
    for lvl, text, anchor in toc:
        pad = "&nbsp;" * (lvl - 1) * 4
        html_parts.append(f"<li>{pad}<a href='#{anchor}'>{html.escape(text)}</a></li>")
    html_parts.append("</ul></div>")

n_code = n_img = 0
for i, cell in enumerate(CELLS):
    ctype = cell.get("cell_type")
    src = src_of(cell)
    if ctype == "markdown":
        if not src.strip():
            continue
        html_parts.append(f"<div class='cell md' id='cell-{i}'>{md_to_html(src)}</div>")
    elif ctype == "code":
        if not src.strip() and not cell.get("outputs"):
            continue
        n_code += 1
        ec = cell.get("execution_count")
        label = f"In [{ec}]" if ec is not None else "In [ ]"
        html_parts.append(f"<div class='cell code' id='cell-{i}'>")
        html_parts.append(f"<div class='label'>{label}</div>")
        html_parts.append(f"<pre><code>{html.escape(src)}</code></pre>")
        for kind, payload in outputs_of(cell):
            if kind == "text":
                if payload.strip():
                    html_parts.append(f"<div class='label'>Out</div>")
                    html_parts.append(f"<pre class='out'>{html.escape(payload)}</pre>")
            else:
                n_img += 1
                b64 = base64.b64encode(payload).decode()
                html_parts.append(
                    f"<img src='data:image/png;base64,{b64}' alt='plot {n_img}'>"
                )
        html_parts.append("</div>")

html_parts.append("</body></html>")
html_path = OUT / "Model_Efficiency_Comparison.html"
html_path.write_text("\n".join(html_parts), encoding="utf-8")
print(f"HTML  -> {html_path}  ({n_code} code cells, {n_img} plots)")


# ─────────────────────────────────────────────────────────────────────────────
# 2. PDF  (full workbook: markdown + code + outputs + plots)
# ─────────────────────────────────────────────────────────────────────────────
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
F_REG = FONT_DIR / "DejaVuSans.ttf"
F_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"
F_ITAL = FONT_DIR / "DejaVuSans-Oblique.ttf"
F_MONO = FONT_DIR / "DejaVuSansMono.ttf"
F_MONO_B = FONT_DIR / "DejaVuSansMono-Bold.ttf"
HAVE_TTF = all(p.exists() for p in (F_REG, F_BOLD, F_MONO))

BODY = "Body"
MONO = "Mono"


class WorkbookPDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font(BODY, "", 8)
        self.set_text_color(130, 138, 148)
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="C")


pdf = WorkbookPDF(format="A4")
pdf.set_margins(15, 15, 15)
pdf.set_auto_page_break(auto=True, margin=16)
pdf.alias_nb_pages()

if HAVE_TTF:
    pdf.add_font(BODY, "", str(F_REG))
    pdf.add_font(BODY, "B", str(F_BOLD))
    if F_ITAL.exists():
        pdf.add_font(BODY, "I", str(F_ITAL))
    pdf.add_font(MONO, "", str(F_MONO))
    if F_MONO_B.exists():
        pdf.add_font(MONO, "B", str(F_MONO_B))
    sanitize = lambda s: str(s)
else:  # pragma: no cover - fallback
    BODY, MONO = "Helvetica", "Courier"
    sanitize = ascii_safe


def block(text, font=BODY, size=9, style="", fill=False, lh=None,
          color=(26, 26, 26), indent=0.0):
    """Render a wrapped text block that never raises on odd characters."""
    if text is None:
        return
    text = sanitize(text)
    if not text.strip():
        pdf.ln(size * 0.35)
        return
    pdf.set_font(font, style, size)
    pdf.set_text_color(*color)
    if fill:
        pdf.set_fill_color(245, 247, 250)
    pdf.set_x(pdf.l_margin + indent)
    try:
        pdf.multi_cell(pdf.epw - indent, lh or size * 0.52, text,
                       fill=fill, wrapmode="CHAR")
    except Exception:
        # last-resort: strip to printable ascii and retry once
        try:
            pdf.set_x(pdf.l_margin + indent)
            pdf.multi_cell(pdf.epw - indent, lh or size * 0.52,
                           ascii_safe(text), fill=fill, wrapmode="CHAR")
        except Exception:
            pass


def code_block(src: str, size=7.2, lh=3.5, color=(38, 42, 50), bg=(246, 248, 251)):
    """Render source code line-by-line so leading indentation survives.

    fpdf2's multi_cell trims leading spaces, which destroys Python indentation.
    Instead we draw each line with an explicit x offset for its indent, and use
    a light background band behind the whole block.
    """
    lines = src.rstrip("\n").split("\n")
    if not lines:
        return
    pad = 1.6
    # Measure the real advance width of one space in the mono font at this size.
    pdf.set_font(MONO, "", size)
    space_w = pdf.get_string_width(" ") or size * 0.6
    for raw in lines:
        if pdf.get_y() > pdf.h - pdf.b_margin - 8:
            pdf.add_page()
        # expand tabs to 4 spaces, then count leading spaces
        expanded = raw.expandtabs(4)
        stripped = expanded.lstrip(" ")
        n_lead = len(expanded) - len(stripped)
        x = pdf.l_margin + pad + n_lead * space_w
        avail = pdf.w - pdf.r_margin - pad - x
        if avail < 12:  # extremely deep indent: clamp to keep text on page
            x = pdf.l_margin + pad + 8 * space_w
            avail = pdf.w - pdf.r_margin - pad - x
        pdf.set_font(MONO, "", size)
        pdf.set_text_color(*color)
        pdf.set_fill_color(*bg)
        pdf.set_x(x)
        try:
            pdf.multi_cell(avail, lh, sanitize(stripped) if stripped else " ",
                           fill=True, wrapmode="CHAR")
        except Exception:
            try:
                pdf.set_x(x)
                pdf.multi_cell(avail, lh, ascii_safe(stripped) or " ",
                               fill=True, wrapmode="CHAR")
            except Exception:
                pass


def heading(text, level=2):
    sizes = {1: 17, 2: 13.5, 3: 11.5, 4: 10.5}
    size = sizes.get(level, 10)
    if pdf.get_y() > pdf.h - 45:
        pdf.add_page()
    pdf.ln(2.5 if level <= 2 else 1.5)
    block(text, size=size, style="B", color=(20, 60, 110) if level <= 2 else (44, 62, 80),
          lh=size * 0.62)
    if level <= 2:
        y = pdf.get_y() + 1
        pdf.set_draw_color(210, 218, 228)
        pdf.set_line_width(0.4)
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(2)


def add_plot(payload: bytes, caption: str):
    global n_img
    n_img += 1
    tmp = Path(tempfile.gettempdir()) / f"_nbplot_{n_img}.png"
    tmp.write_bytes(payload)
    try:
        from PIL import Image
        with Image.open(tmp) as im:
            iw, ih = im.size
    except Exception:
        iw, ih = 1600, 900
    max_w = pdf.epw
    max_h = pdf.h - pdf.t_margin - pdf.b_margin - 18
    scale = min(max_w / iw, max_h / ih)
    dw, dh = iw * scale, ih * scale
    if pdf.get_y() + dh + 8 > pdf.h - pdf.b_margin:
        pdf.add_page()
    block(caption, size=8, style="I", color=(110, 118, 128), lh=4)
    try:
        pdf.image(str(tmp), w=dw, h=dh)
    except Exception as e:  # pragma: no cover
        block(f"[plot omitted: {e}]", size=8, style="I")
    pdf.ln(3)
    tmp.unlink(missing_ok=True)


def render_markdown(md: str):
    in_code = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            code_block(raw, size=7.5, lh=3.6)
            continue
        if not line.strip():
            pdf.ln(1.6)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            heading(m.group(2), level=min(len(m.group(1)), 4))
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            block("  |  ".join(cells), font=MONO, size=7, lh=3.4)
            continue
        m = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if m:
            block("- " + m.group(1), size=9, indent=3, lh=4.6)
            continue
        m = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if m:
            block(f"{m.group(1)}. {m.group(2)}", size=9, indent=3, lh=4.6)
            continue
        block(line, size=9, lh=4.7)


# ── cover ──
pdf.add_page()
pdf.ln(40)
block("LLM Efficiency & Provider-Value Analysis", size=22, style="B",
      color=(20, 60, 110), lh=11)
pdf.ln(3)
block("Full workbook export - markdown, code, results and plots", size=11,
      color=(90, 100, 112), lh=6)
pdf.ln(2)
block("Generated 2026-10-24", size=9, color=(130, 138, 148), lh=5)
pdf.ln(10)
block(f"Notebook: {NB.name}", size=9, color=(90, 100, 112), lh=5)
block(f"Cells: {len(CELLS)}", size=9, color=(90, 100, 112), lh=5)

# ── body ──
n_code = n_img = 0
for i, cell in enumerate(CELLS):
    ctype = cell.get("cell_type")
    src = src_of(cell)
    if ctype == "markdown":
        if not src.strip():
            continue
        render_markdown(src)
    elif ctype == "code":
        if not src.strip() and not cell.get("outputs"):
            continue
        n_code += 1
        if pdf.get_y() > pdf.h - 55:
            pdf.add_page()
        ec = cell.get("execution_count")
        block(f"In [{ec}]" if ec is not None else "In [ ]", size=7.5, style="B",
              color=(120, 128, 140), lh=4)
        code_block(src, size=7.2, lh=3.5)
        pdf.ln(1.2)
        for kind, payload in outputs_of(cell):
            if kind == "text":
                if payload.strip():
                    block("Out", size=7.5, style="B", color=(120, 128, 140), lh=4)
                    block(payload.rstrip(), font=MONO, size=7, lh=3.4,
                          color=(40, 44, 52))
                    pdf.ln(1.2)
            else:
                add_plot(payload, f"Figure {n_img + 1} - cell {i}")

pdf_path = OUT / "Model_Efficiency_Comparison.pdf"
pdf.output(str(pdf_path))
print(f"PDF   -> {pdf_path}  ({pdf.page} pages, {n_code} code cells, {n_img} plots)")
