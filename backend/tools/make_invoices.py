"""Generate the demo invoice PDF suite (PLAN.md §8.2).

Digital invoices use fpdf2; the scanned one is drawn with PIL (rotated,
noisy) and saved as an image-only PDF so it genuinely has no text layer.
Layout is intentionally parseable by the fallback extractor, but the primary
path is the LLM — these are just bytes either way.

Usage:  python tools/make_invoices.py  (writes ../../testdata/*.pdf)
"""
from __future__ import annotations

import os
import random
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fpdf import FPDF

OUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "testdata"))


class InvoicePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, self.vendor, ln=1)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, f"{self.address}", ln=1)
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 8, "INVOICE", ln=1)
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Thank you for your business - {self.vendor}", align="C")


def _latin1(s: str) -> str:
    # fpdf2 core fonts are latin-1; swap typographic dashes for ASCII
    return s.replace("\u2014", "-").replace("\u2013", "-")


def make_invoice(filename: str, *, vendor: str, address: str,
                 invoice_number: str | None, invoice_date: date | None,
                 po_number: str | None, lines: list[tuple[str, float, float]],
                 tax: float, note: str = "") -> str:
    """lines: (description, qty, unit_price); amount = qty*unit_price."""
    vendor, address, note = _latin1(vendor), _latin1(address), _latin1(note)
    lines = [(_latin1(d), q, u) for d, q, u in lines]
    pdf = InvoicePDF(format="Letter")
    pdf.vendor, pdf.address = vendor, address
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)

    def row(label: str, value: str):
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(40, 6, label)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, value, ln=1)

    row("Invoice Number:", invoice_number or "Not provided")
    row("Invoice Date:", invoice_date.isoformat() if invoice_date else "Not provided")
    row("Vendor:", vendor)
    if po_number:
        row("PO Number:", po_number)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(95, 7, "Description", border=1)
    pdf.cell(25, 7, "Qty", border=1)
    pdf.cell(35, 7, "Unit Price", border=1)
    pdf.cell(35, 7, "Amount", border=1, ln=1)
    subtotal = 0.0
    for desc, qty, unit in lines:
        amount = round(qty * unit, 2)
        subtotal += amount
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 7, desc, border=1)
        pdf.cell(25, 7, f"{qty:g}", border=1)
        pdf.cell(35, 7, f"${unit:,.2f}", border=1)
        pdf.cell(35, 7, f"${amount:,.2f}", border=1, ln=1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(155, 7, "Subtotal", border=1)
    pdf.cell(35, 7, f"${subtotal:,.2f}", border=1, ln=1)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(155, 7, "Tax", border=1)
    pdf.cell(35, 7, f"${tax:,.2f}", border=1, ln=1)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(155, 8, "Total Due", border=1)
    pdf.cell(35, 8, f"${subtotal + tax:,.2f}", border=1, ln=1)
    if note:
        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, note)

    path = os.path.join(OUT_DIR, filename)
    pdf.output(path)
    return path


def make_scanned_invoice(filename: str, *, vendor: str, invoice_number: str,
                         invoice_date: date, po_number: str,
                         lines: list[tuple[str, float, float]], tax: float) -> str:
    """Render an invoice to an image, rotate + add noise, save as image-only PDF."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    W, H = 1700, 2200
    img = Image.new("L", (W, H), 250)
    d = ImageDraw.Draw(img)
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    font = None
    bold = None
    for p in font_paths:
        try:
            font = ImageFont.truetype(p, 34)
            bold = ImageFont.truetype(p, 36)
            break
        except Exception:
            continue
    if font is None:
        font = bold = ImageFont.load_default()

    y = 120
    d.text((100, y), vendor, font=bold, fill=20); y += 60
    d.text((100, y), "1180 Commerce Park Drive · Wilmington, DE", font=font, fill=60); y += 50
    d.text((100, y), "INVOICE", font=bold, fill=20); y += 70

    d.text((100, y), "Invoice Number:", font=font, fill=20)
    d.text((600, y), invoice_number, font=bold, fill=20); y += 48
    d.text((100, y), "Invoice Date:", font=font, fill=20)
    d.text((600, y), invoice_date.isoformat(), font=bold, fill=20); y += 48
    d.text((100, y), "Vendor:", font=font, fill=20)
    d.text((600, y), vendor, font=bold, fill=20); y += 48
    d.text((100, y), "PO Number:", font=font, fill=20)
    d.text((600, y), po_number, font=bold, fill=20); y += 80

    d.line((100, y, W - 100, y), fill=120, width=2); y += 20
    subtotal = 0.0
    for desc, qty, unit in lines:
        amount = round(qty * unit, 2)
        subtotal += amount
        d.text((100, y), desc, font=font, fill=20)
        d.text((1050, y), f"{qty:g}", font=font, fill=20)
        d.text((1200, y), f"${unit:,.2f}", font=font, fill=20)
        d.text((1450, y), f"${amount:,.2f}", font=font, fill=20)
        y += 52
    d.line((100, y, W - 100, y), fill=120, width=2); y += 20
    d.text((100, y), "Subtotal", font=bold, fill=20)
    d.text((1450, y), f"${subtotal:,.2f}", font=bold, fill=20); y += 52
    d.text((100, y), "Tax", font=font, fill=20)
    d.text((1450, y), f"${tax:,.2f}", font=font, fill=20); y += 52
    d.text((100, y), "Total Due", font=bold, fill=20)
    d.text((1450, y), f"${subtotal + tax:,.2f}", font=bold, fill=20)

    img = img.rotate(-1.3, expand=False, fillcolor=250, resample=Image.BICUBIC)
    px = img.load()
    rng = random.Random(42)
    for _ in range(22000):  # scanner grain
        x, yy = rng.randrange(W), rng.randrange(H)
        cur = px[x, yy]
        px[x, yy] = max(0, min(255, cur + rng.randint(-38, 38)))
    img = img.filter(ImageFilter.GaussianBlur(0.6))

    path = os.path.join(OUT_DIR, filename)
    img.save(path, "PDF", resolution=150)
    return path


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    made = []

    made.append(make_invoice(
        "inv_happy_acme.pdf",
        vendor="Acme Industrial Supply", address="2200 Foundry Rd · Cleveland, OH",
        invoice_number="ACME-2026-0417", invoice_date=date(2026, 9, 12),
        po_number="PO-2026-101",
        lines=[("Industrial fasteners, grade 8 (box of 500)", 60, 85.00),
               ("Safety equipment kit — warehouse", 30, 230.00)],
        tax=0.0, note="Tax exempt — resale certificate on file."))

    made.append(make_invoice(
        "inv_duplicate_acme.pdf",
        vendor="Acme Industrial Supply", address="2200 Foundry Rd · Cleveland, OH",
        invoice_number="ACME-2026-0417", invoice_date=date(2026, 9, 12),
        po_number="PO-2026-101",
        lines=[("Industrial fasteners, grade 8 (box of 500)", 60, 85.00),
               ("Safety equipment kit — warehouse", 30, 230.00),
               ("Rush processing fee", 1, 400.00)],
        tax=0.0, note="Reissued — includes rush processing fee."))

    made.append(make_invoice(
        "inv_split_a.pdf",
        vendor="Northwind Logistics", address="75 Harbor Way · Newark, NJ",
        invoice_number="NW-2026-0851A", invoice_date=date(2026, 9, 10),
        po_number="PO-2026-114",
        lines=[("Freight services — September leg", 1, 4800.00)],
        tax=0.0))

    made.append(make_invoice(
        "inv_split_b.pdf",
        vendor="Northwind Logistics", address="75 Harbor Way · Newark, NJ",
        invoice_number="NW-2026-0851B", invoice_date=date(2026, 9, 18),
        po_number="PO-2026-114",
        lines=[("Freight services — October leg", 1, 4800.00)],
        tax=0.0))

    made.append(make_invoice(
        "inv_breach_globex.pdf",
        vendor="Globex Facilities Group", address="400 Plaza Level · Houston, TX",
        invoice_number="GFX-77320", invoice_date=date(2026, 9, 14),
        po_number="PO-2026-118",
        lines=[("Office lighting retrofit", 40, 175.00),
               ("Installation labour", 8, 150.00),
               ("Disposal fee — old fixtures", 1, 328.00)],
        tax=0.0, note="Disposal of removed fixtures billed at cost."))

    made.append(make_scanned_invoice(
        "inv_scanned_foxtrot.pdf",
        vendor="Foxtrot Media Labs", invoice_number="FML-2213",
        invoice_date=date(2026, 9, 8), po_number="PO-2026-121",
        lines=[("Q3 campaign analytics retainer", 3, 1800.00)],
        tax=0.0))

    made.append(make_invoice(
        "inv_missing_initech.pdf",
        vendor="Initech Systems", address="4100 Tech Center Dr · Austin, TX",
        invoice_number=None, invoice_date=date(2026, 9, 15),
        po_number=None,
        lines=[("Server rack migration — labour", 45, 150.00)],
        tax=0.0, note="Reference PO to follow — billing per agreed statement of work."))

    made.append(make_invoice(
        "inv_linemismatch_hooli.pdf",
        vendor="Hooli Cloud Services", address="1 Cloud Campus · Mountain View, CA",
        invoice_number="HCL-99117", invoice_date=date(2026, 9, 16),
        po_number="PO-2026-127",
        lines=[("Cloud hosting — dedicated nodes", 100, 50.40),
               ("Premium support plan", 1, 2460.00)],
        tax=0.0, note="Q4 rate card applied to hosting nodes."))

    for p in made:
        print(f"wrote {p} ({os.path.getsize(p):,} bytes)")


if __name__ == "__main__":
    main()
