"""Printed Delivery Note (Access reports "Delivery Note", "Delivery Note Particular", "Multi Delivery Note").

A4 portrait, one page per SF row (DN number = SF.UID). Layout follows spec 3 §7 and the sample
db_DN/Delivery Notes Set.pdf. Access positions are in px (96 dpi) from the report's left edge.
"""
import os

from fpdf import FPDF

from services import fmt

PX = 25.4 / 96            # mm per Access px
LEFT, TOP = 7.0, 6.0      # page margins (mm), as in the sample PDF
ICONS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "access", "icons")
GREY = (231, 230, 230)    # #E7E6E6
FOOTER = ("P.O. Box 2728, Riyadh 11461 • Kingdom of Saudi Arabia • Tel.: +966.11.243.9114 "
          "• e-mail: mlogistic@alfaisaliah.com")


def _t(v):
    """Text for the PDF core fonts (Windows-1252); characters outside it become '?'."""
    if v is None:
        return ""
    return str(v).encode("cp1252", "replace").decode("cp1252")


def _x(px):
    return LEFT + px * PX


class _DN(FPDF):
    def footer(self):
        self.set_draw_color(160, 160, 160)
        self.line(_x(11), 297 - 14, _x(733), 297 - 14)
        self.set_xy(_x(11), 297 - 12)
        self.set_font("helvetica", "B", 7)
        self.cell(722 * PX, 4, _t(FOOTER), align="C")


def _cell(pdf, x, y, w, h, text="", style="", size=9, align="L", fill=False, border=0):
    pdf.set_xy(_x(x), TOP + y * PX)
    pdf.set_font("helvetica", style, size)
    pdf.cell(w * PX, h * PX, _t(text), border=border, align=align, fill=fill)


def _page(pdf, r):
    """One Delivery Note page for SF row `r` (a models.SF object)."""
    pdf.add_page()
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.2)
    pdf.set_fill_color(*GREY)
    # Page header: MPC logo (left), Al Faisaliah Group logo (right)
    pdf.image(os.path.join(ICONS, "dn_mpc_logo.jpg"), x=_x(8), y=TOP + 4 * PX, h=80 * PX)
    pdf.image(os.path.join(ICONS, "dn_afg_logo.jpg"), x=_x(648), y=TOP + 4 * PX, h=88 * PX)
    y0 = 113                                   # detail section starts under the page header
    _cell(pdf, 560, y0 + 20, 174, 34, "Delivery Note", "B", 16, "R")
    # "To:" / "Information:" bars
    _cell(pdf, 13, y0 + 60, 365, 25, " To:", "B", 10, fill=True, border=1)
    _cell(pdf, 382, y0 + 60, 354, 25, " Information:", "B", 10, fill=True, border=1)
    rows = [89, 116, 142, 166, 190, 214]
    block_top, block_bottom = y0 + 85, y0 + 238
    pdf.rect(_x(13), TOP + block_top * PX, 365 * PX, (block_bottom - block_top) * PX)
    pdf.rect(_x(382), TOP + block_top * PX, 354 * PX, (block_bottom - block_top) * PX)
    left = [(r.DeliveredTo, "B"), (r.DeliveredToAdd1, ""), (r.DeliveredToAdd2, ""), (r.DeliveredToContactName, "")]
    for (val, st), ry in zip(left, rows[:4]):
        _cell(pdf, 35, y0 + ry, 342, 21, val, st, 10 if st else 9)
    _cell(pdf, 35, y0 + rows[4], 55, 21, "Tel:", "", 9)
    _cell(pdf, 90, y0 + rows[4], 288, 21, r.DeliveredToContactTel, "", 9)
    _cell(pdf, 35, y0 + rows[5], 55, 21, "Mobile:", "", 9)
    _cell(pdf, 90, y0 + rows[5], 288, 21, r.DeliveredToContactMob, "", 9)
    info = [("Delivery Note No.:", r.UID, "B"), ("Delivery Date:", fmt.short_date(r.DeliveredOn), ""),
            ("Transporter:", r.DeliveredTransporter, ""), ("Truck / Plate No.:", "", ""),
            ("Driver Name:", "", ""), ("MPC Ref. No.:", r.SF, "")]
    for (label, val, st), ry in zip(info, rows):
        _cell(pdf, 412, y0 + ry, 131, 21, label, "", 9)
        _cell(pdf, 547, y0 + ry, 188, 21, val, st, 10 if st else 9)
    # Delivery From
    _cell(pdf, 13, y0 + 244, 140, 25, " Delivery From:  ", "B", 10, fill=True, border=1)
    _cell(pdf, 153, y0 + 244, 583, 25, "  Modern Petrochemicals Company Ltd. (MPC)", "B", 10, border=1)
    # Details table
    _cell(pdf, 13, y0 + 280, 723, 25, " Delivery Note Details", "B", 10, fill=True, border=1)
    cols = [(13, 49, "item"), (62, 500, "Description"), (562, 65, "UOM"), (627, 109, "Quantity")]
    for x, w, h in cols:
        _cell(pdf, x, y0 + 310, w, 20, h, "B", 9, "C", border=1)
    body_top, body_bottom = y0 + 330, y0 + 781
    for x, w, _ in cols:
        pdf.rect(_x(x), TOP + body_top * PX, w * PX, (body_bottom - body_top) * PX)
    _cell(pdf, 13, y0 + 334, 49, 19, "010", "", 9, "C")
    _cell(pdf, 66, y0 + 334, 491, 19, r.Product, "", 9)
    _cell(pdf, 562, y0 + 334, 65, 19, r.UOM, "", 9, "C")
    _cell(pdf, 627, y0 + 334, 106, 19, fmt.standard(r.SFQty), "", 9, "R")
    _cell(pdf, 66, y0 + 357, 491, 19, r.DeliveredPacking, "", 9)
    _cell(pdf, 66, y0 + 380, 491, 19, r.ContainerNo, "", 9)
    po_item = "" if r.DeliveredPOItem is None else r.DeliveredPOItem
    _cell(pdf, 66, y0 + 403, 491, 19, f"Purchase Order Number: {r.DeliveredPO or ''}, PO Item # {po_item}", "", 9)
    if r.DeliveryRemarks:
        pdf.set_xy(_x(66), TOP + (y0 + 429) * PX)
        pdf.set_font("helvetica", "", 9)
        pdf.multi_cell(480 * PX, 19 * PX, _t(r.DeliveryRemarks))
    # Received By box
    sig_top = y0 + 800
    pdf.rect(_x(13), TOP + sig_top * PX, 723 * PX, 105 * PX)
    _cell(pdf, 41, sig_top + 4, 120, 20, "Received By", "B", 9)
    for dy, a, b in ((30, "Name", "Stamp"), (73, "Signature", "Date")):
        _cell(pdf, 41, sig_top + dy, 120, 20, a, "", 9)
        _cell(pdf, 162, sig_top + dy, 240, 20, ":  ____________________________", "", 9)
        _cell(pdf, 445, sig_top + dy, 82, 20, b, "", 9, "R")
        _cell(pdf, 531, sig_top + dy, 20, 20, ":", "", 9)


def build(rows):
    """PDF bytes with one Delivery Note page per SF row, in the given order."""
    pdf = _DN(orientation="P", unit="mm", format="A4")
    pdf.core_fonts_encoding = "cp1252"     # the Access DN footer uses bullets (•)
    pdf.set_auto_page_break(False)
    pdf.set_title("Delivery Note")
    pdf.set_author("Modern Petrochemicals Co.")
    for r in rows:
        _page(pdf, r)
    if not rows:
        pdf.add_page()
    return bytes(pdf.output())
