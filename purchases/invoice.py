"""Render a PurchaseOrder to a printable PDF (purchase order / invoice)."""
import io

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

BRAND = colors.HexColor("#4f46e5")
LIGHT = colors.HexColor("#f1f5f9")
MUTED = colors.HexColor("#64748b")


def _money(value):
    sym = getattr(settings, "CURRENCY_SYMBOL", "")
    return f"{sym}{value:,.2f}"


def build_purchase_pdf(order) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm,
        title=f"Purchase Order {order.po_number}",
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=styles["Normal"], fontSize=9, leading=13)
    muted = ParagraphStyle("m", parent=normal, textColor=MUTED)
    right = ParagraphStyle("r", parent=normal, alignment=TA_RIGHT)
    h_company = ParagraphStyle("hc", parent=normal, fontSize=15, leading=18,
                               textColor=BRAND, fontName="Helvetica-Bold")
    h_title = ParagraphStyle("ht", parent=normal, fontSize=20, leading=22,
                             alignment=TA_RIGHT, fontName="Helvetica-Bold")
    label = ParagraphStyle("lbl", parent=muted, fontSize=7.5,
                           fontName="Helvetica-Bold")

    el = []

    # --- Header: company (left) + document title (right) ------------------
    company = getattr(settings, "COMPANY_NAME", "Inventory Management")
    company_block = [
        Paragraph(company, h_company),
        Paragraph(getattr(settings, "COMPANY_ADDRESS", ""), muted),
        Paragraph(getattr(settings, "COMPANY_EMAIL", ""), muted),
        Paragraph(getattr(settings, "COMPANY_PHONE", ""), muted),
    ]
    tax = getattr(settings, "COMPANY_TAX_ID", "")
    if tax:
        company_block.append(Paragraph(f"Tax ID: {tax}", muted))
    title_block = [Paragraph("PURCHASE ORDER", h_title),
                   Paragraph(f"# {order.po_number}", right)]
    el.append(Table([[company_block, title_block]],
                    colWidths=[doc.width * 0.55, doc.width * 0.45]))
    el.append(Spacer(1, 14))

    # --- Supplier + meta --------------------------------------------------
    s = order.supplier
    supplier_lines = [Paragraph("SUPPLIER", label), Paragraph(s.name, normal)]
    if s.contact_person:
        supplier_lines.append(Paragraph(s.contact_person, muted))
    if s.address:
        supplier_lines.append(Paragraph(s.address.replace("\n", "<br/>"), muted))
    contact = " · ".join(x for x in [s.email, s.phone] if x)
    if contact:
        supplier_lines.append(Paragraph(contact, muted))
    if s.gst_number:
        supplier_lines.append(Paragraph(f"GST/VAT: {s.gst_number}", muted))

    meta = [
        ["Order Date", order.order_date.strftime("%d %b %Y")],
        ["Expected", order.expected_date.strftime("%d %b %Y") if order.expected_date else "—"],
        ["Status", order.get_status_display()],
        ["Created By", order.created_by.get_full_name() or order.created_by.username if order.created_by else "—"],
    ]
    meta_tbl = Table([[Paragraph(k, label), Paragraph(str(v), right)] for k, v in meta],
                     colWidths=[doc.width * 0.22, doc.width * 0.23])
    meta_tbl.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    el.append(Table([[supplier_lines, meta_tbl]],
                    colWidths=[doc.width * 0.55, doc.width * 0.45]))
    el.append(Spacer(1, 16))

    # --- Line items -------------------------------------------------------
    data = [["#", "Product", "Qty", "Unit Price", "Subtotal"]]
    for i, item in enumerate(order.items.select_related("product"), start=1):
        data.append([
            str(i), item.product.name, str(item.quantity),
            _money(item.unit_price), _money(item.subtotal),
        ])
    data.append(["", "", "", "Total", _money(order.total_amount)])

    items = Table(data, colWidths=[
        doc.width * 0.07, doc.width * 0.43, doc.width * 0.12,
        doc.width * 0.19, doc.width * 0.19,
    ], repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT]),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, MUTED),
        ("FONTNAME", (3, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    el.append(items)

    if order.notes:
        el.append(Spacer(1, 14))
        el.append(Paragraph("NOTES", label))
        el.append(Paragraph(order.notes.replace("\n", "<br/>"), muted))

    el.append(Spacer(1, 24))
    el.append(Paragraph(
        "This is a system-generated purchase order and is valid without signature.",
        ParagraphStyle("f", parent=muted, fontSize=7.5, alignment=1)))

    doc.build(el)
    return buffer.getvalue()
