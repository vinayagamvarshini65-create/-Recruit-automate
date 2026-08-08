"""
documents.py
Merges candidate data into a text template and renders it as a formatted PDF.
Uses reportlab (no external binary dependencies like LibreOffice needed).
"""
import os
import re
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

DOCS_DIR = os.path.join(os.path.dirname(__file__), "data", "documents")
os.makedirs(DOCS_DIR, exist_ok=True)

MERGE_FIELD_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def merge_fields(text, candidate):
    """Replace {{field}} placeholders with candidate values."""
    context = {
        "name": candidate.get("name", ""),
        "email": candidate.get("email", ""),
        "role": candidate.get("role", ""),
        "department": candidate.get("department", ""),
        "salary": candidate.get("salary", ""),
        "joining_date": candidate.get("joining_date", ""),
        "today": datetime.now().strftime("%B %d, %Y"),
    }

    def repl(match):
        key = match.group(1)
        return str(context.get(key, match.group(0)))

    return MERGE_FIELD_RE.sub(repl, text)


def missing_fields(text, candidate):
    """Return list of merge fields referenced that have no value for this candidate."""
    context = {
        "name": candidate.get("name"),
        "email": candidate.get("email"),
        "role": candidate.get("role"),
        "department": candidate.get("department"),
        "salary": candidate.get("salary"),
        "joining_date": candidate.get("joining_date"),
    }
    missing = []
    for field in MERGE_FIELD_RE.findall(text):
        if field == "today":
            continue
        if not context.get(field):
            missing.append(field)
    return sorted(set(missing))


def generate_pdf(candidate, template_body, doc_title="Offer Letter"):
    """
    Renders merged template text into a formatted PDF.
    Returns the absolute file path of the generated PDF.
    """
    merged_text = merge_fields(template_body, candidate)

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate["name"])
    filename = f"{candidate['id']}_{safe_name}_{doc_title.replace(' ', '_')}.pdf"
    filepath = os.path.join(DOCS_DIR, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=letter,
        leftMargin=1 * inch, rightMargin=1 * inch,
        topMargin=1 * inch, bottomMargin=1 * inch,
    )
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=11, leading=16, alignment=TA_LEFT,
        spaceAfter=10,
    )
    title_style = ParagraphStyle(
        "DocTitle", parent=styles["Title"], fontSize=16, spaceAfter=20,
    )

    story = [Paragraph(doc_title.upper(), title_style)]

    # Each blank-line-separated block becomes its own paragraph so line breaks render correctly
    for block in merged_text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        safe_block = block.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_block = safe_block.replace("\n", "<br/>")
        story.append(Paragraph(safe_block, body_style))
        story.append(Spacer(1, 6))

    doc.build(story)
    return filepath
