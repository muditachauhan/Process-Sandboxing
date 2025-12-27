# utils/pdf_exporter.py
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import datetime
import os

def export_report_pdf(output_pdf_path, metadata: dict, log_text: str, chart_img_path: str = None):
    """
    Creates a simple PDF containing metadata, a log text block, and an optional chart image.
    metadata: dict with keys like 'pid','cmd','started','priority','affinity'
    log_text: full text
    chart_img_path: optional PNG path (saved by matplotlib)
    """
    os.makedirs(os.path.dirname(output_pdf_path) or ".", exist_ok=True)
    c = canvas.Canvas(output_pdf_path, pagesize=letter)
    width, height = letter
    x_margin = 40
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x_margin, y, "Sandbox Session Report")
    y -= 24
    c.setFont("Helvetica", 9)
    c.drawString(x_margin, y, f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 18

    # metadata table-like
    for k, v in metadata.items():
        c.drawString(x_margin, y, f"{k}: {v}")
        y -= 14
    y -= 6

    # insert chart image if present
    if chart_img_path and os.path.exists(chart_img_path):
        try:
            img = ImageReader(chart_img_path)
            iw, ih = img.getSize()
            aspect = ih / float(iw)
            img_w = width - 2 * x_margin
            img_h = img_w * aspect
            if img_h > (y - 120):
                img_h = y - 120
                img_w = img_h / aspect
            c.drawImage(img, x_margin, y - img_h, width=img_w, height=img_h)
            y -= img_h + 12
        except Exception:
            pass

    # logs - wrap text
    c.setFont("Courier", 8)
    # ensure there's space
    lines = log_text.splitlines()
    # fit as many lines as possible on remaining page
    max_lines = int((y - 40) / 10)
    start_line = max(0, len(lines) - max_lines)
    display_lines = lines[start_line:]
    for line in display_lines:
        if y < 50:
            c.showPage()
            y = height - 40
            c.setFont("Courier", 8)
        c.drawString(x_margin, y, line[:100])
        y -= 10
    c.save()
    return output_pdf_path
