"""Main Menu box "Stock, Delivery, and Invoices" — spec access_spec/3_stock_delivery_invoices.md.

Screens: UpdateClearanceGR (+ UpdatePOSFfromGR popup), LocalStockRpt -> report "Local Stock of Product"
(✓ = Create DN, S = split via the Shipment Files grid copy_sf_ls), DN / DNParticular (Delivery Note forms),
MultiDNNo -> MultiDN, report ShipmentsDlvrdWOInv, UpdationOfInv; Delivery Note PDFs and two Outlook drafts.

Decisions applied (DECISIONS.md): bug 1 "Location Code" stores the plant name (Access stored the 5th
column = a phone number); bug 2 no false "Error occured when saving the file"; bug 3 the SO is internal —
not auto-filled and no SO warning (the SO line is left out of the warehouse e-mail when no SO is typed);
B4 when every container of a PO line is GR'd (Cleared) the MPC PO line becomes Cleared automatically.
"""
import re
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import func

from extensions import db
from models import SF, CustomerAdd, CustomersPO, Products, ShipmentsStatus, StorageLoc, Transporters
from screens_def import lookups as L
from services import dn_pdf, fmt
from services.screens import ScreenError, eml, form, grid, pdf, report

SS = ShipmentsStatus
LOCKED_BG, LOCKED_FG = "#E7E6E6", "#404040"
ORANGE = "#ED7D31"
STYLES = ["access/stock.css"]
SCRIPTS = ["access/stock.js"]


# ── shared helpers ────────────────────────────────────────────────────

def container(v):
    """Access input mask >LLLL\\ 9999999: 'OOLU4349997' is shown as 'OOLU 4349997'."""
    s = (v or "").strip()
    m = re.fullmatch(r"([A-Za-z]{4})\s?(\d{7})", s)
    return f"{m.group(1).upper()} {m.group(2)}" if m else s


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _uids(params):
    """DN numbers from params: id=<UID>, p=<UID> (prompt) or dns=1,2,3."""
    raw = params.get("dns") or params.get("ids") or params.get("id") or params.get("p") or ""
    return [u for u in (_int(x) for x in re.split(r"[,\s]+", str(raw))) if u is not None]


def open_cus_po(product=None):
    """DN_ActiveCusPO: customer PO lines (of the product) with balance > 0 or no deliveries yet.
    Consumed = Σ SFQty of SF rows referencing the PO line (DeliveredPO + DeliveredPOItem)."""
    used = dict(((po, item), q) for po, item, q in db.session.query(
        SF.DeliveredPO, SF.DeliveredPOItem, func.sum(SF.SFQty)).filter(SF.DeliveredPO.isnot(None))
        .group_by(SF.DeliveredPO, SF.DeliveredPOItem))
    q = CustomersPO.query
    if product is not None:
        q = q.filter(CustomersPO.Product == product)
    out = []
    for c in q.order_by(CustomersPO.CusPONo, CustomersPO.ItemNo):
        consumed = used.get((c.CusPONo, c.ItemNo))
        if consumed is None or c.POQty is None or float(c.POQty) - float(consumed) > 0:
            out.append(c)
    return out


def _po_options(product_from_params):
    def options(params):
        product = None
        if product_from_params:
            uids = _uids(params)
            row = db.session.get(SF, uids[0]) if uids else None
            product = row.Product if row else ""
        return [[f"{c.CusPONo} / {c.ItemNo}", c.ItemNo, c.Product or "", c.Affiliate or ""] for c in open_cus_po(product)]
    return options


def plant_options(params=None):
    return [[a.CustomerPlant, a.Customer or ""] for a in CustomerAdd.query.order_by(CustomerAdd.id)
            if (a.CustomerPlant or "").strip()]


def _find_plant(plant, customer):
    rows = CustomerAdd.query.filter(CustomerAdd.CustomerPlant == plant).order_by(CustomerAdd.id).all()
    return next((a for a in rows if customer and a.Customer == customer), rows[0] if rows else None)


def _plant_after(rec, params, row):
    """Location Code AfterUpdate: copy address and contact of the chosen delivery point into the SF row."""
    a = _find_plant(rec.get("DeliveredToPlant"), rec.get("DeliveredTo"))
    if not a:
        return {}
    return {"updates": {"DeliveredToAdd1": a.CusAdd1, "DeliveredToAdd2": a.CusAdd2,
                        "DeliveredToContactName": a.CusCntName, "DeliveredToContactTel": a.CusCntTel,
                        "DeliveredToContactMob": a.CusCntMob}}


def _split_po(value, product=None):
    """'4802078204 / 1' -> ('4802078204', 1). A bare PO number takes its first open line (of the product)."""
    v = (value or "").strip()
    if not v:
        return None, None
    m = re.fullmatch(r"(.+?)\s*/\s*(\d+)", v)
    if m:
        return m.group(1).strip(), int(m.group(2))
    lines = [c for c in open_cus_po(product) if c.CusPONo == v] or \
        CustomersPO.query.filter(CustomersPO.CusPONo == v).order_by(CustomersPO.ItemNo).all()
    return v, (lines[0].ItemNo if lines else None)


def _po_after(rec, params, row):
    """PO # AfterUpdate: PO Item # from the chosen PO line (SO is internal — not filled, decision bug 3)."""
    po, item = _split_po(rec.get("DeliveredPO"), rec.get("Product"))
    # Keep "PO / item" in the box until the save, so the chosen item (not the PO's first line) is stored.
    return {"updates": {"DeliveredPO": f"{po} / {item}" if po and item is not None else po, "DeliveredPOItem": item}}


def _dn_before_save(row, typed, params, merged):
    """Store the PO number and its item separately (the list offers 'PO / item')."""
    if "DeliveredPO" not in typed:
        return
    raw = typed["DeliveredPO"]
    po, item = _split_po(raw, merged.get("Product"))
    typed["DeliveredPO"] = po
    old_po = row.DeliveredPO if row is not None else None
    if po is None:
        typed["DeliveredPOItem"] = None
    elif "/" in str(raw) or po != old_po or merged.get("DeliveredPOItem") is None:
        typed["DeliveredPOItem"] = item


DELIVERY_FIELDS = ["DeliveredOn", "DeliveredTo", "DeliveredToPlant", "DeliveredTransporter", "DeliveredPO",
                   "DeliveredPacking", "DeliveredToAdd1", "DeliveredToAdd2", "DeliveredToContactName",
                   "DeliveredToContactTel", "DeliveredToContactMob", "DeliveredPOItem", "DeliveredSO"]


def _reverse(rec, params, row):
    """Reverse Delivery (DN / DNParticular): blank the delivery fields; the line returns to local stock.
    DeliveryRemarks, SAPDNNo and InvNo are kept, as in Access."""
    if row is not None:
        for f in DELIVERY_FIELDS:
            setattr(row, f, None)
    return {"updates": {f: None for f in DELIVERY_FIELDS}, "save": True}


def _reverse_multi(rec, params, row):
    """Reverse Delivery on MultiDN: Access cleared only these six fields of the current row."""
    six = ["DeliveredOn", "DeliveredTo", "DeliveredToPlant", "DeliveredTransporter", "DeliveredPO", "DeliveredPacking"]
    if row is not None:
        for f in six:
            setattr(row, f, None)
    return {"updates": {f: None for f in six}, "save": True}


# ── 1. Updation of Clearance Status (GR) ─────────────────────────────

def sync_po_line(mpcpono, item):
    """B4: the MPC PO line becomes Cleared when all its containers are Cleared (GR done) and the cleared
    quantity covers the PO quantity (same UOM). Canceled containers are ignored."""
    if not mpcpono:
        return
    rows = SF.query.filter(SF.MPCPONo == mpcpono, SF.MPCPOItemNo == item).all()
    rows = [r for r in rows if r.Status != "Canceled"]
    if not rows or any(r.Status != "Cleared" for r in rows):
        return
    for line in SS.query.filter(SS.MPCPONo == mpcpono, SS.ItemNo == item).all():
        if line.Status in ("Cleared", "Canceled"):
            continue
        same_uom = all((r.UOM or "") == (line.UOM or "") for r in rows)
        cleared_qty = sum(float(r.SFQty or 0) for r in rows)
        if same_uom and line.Qty and cleared_qty + 0.001 < float(line.Qty):
            continue                       # more of this PO line is still to be shipped
        line.Status = "Cleared"
        if not line.SFNo:
            line.SFNo = rows[0].SF


def _gr_after_save(row, params, is_new):
    if row.Status == "Cleared":
        sync_po_line(row.MPCPONo, row.MPCPOItemNo)


def _sf_no(params):
    return _int(params.get("p") or params.get("SF"))


RED = "color:#BA1419"
GRL = dict(locked=True, bg="#D0CECE", color=LOCKED_FG)
grid(
    "update_clearance_gr", title="UpdateClearanceGR", model=SF, width=1702, win=(1720, 796), row_h=27,
    allow_delete=False, nav_w=1720,
    query=lambda p: SF.query.filter(SF.SF == _sf_no(p)).order_by(SF.UID),
    after_save=_gr_after_save,
    header=dict(h=27, bg="#D6DCE5", col_y=4, label_style="font-weight:bold;justify-content:center"),
    footer=dict(h=68, bg="#ffffff"),
    styles=STYLES, scripts=SCRIPTS,
    columns=[
        dict(label="S/F#", type="text", field="SF", x=7, y=4, w=65, h=21, **GRL),
        dict(label="Container#", type="text", field="ContainerNo", x=76, y=4, w=101, h=21, **GRL),
        dict(label="Product", type="text", field="Product", x=181, y=4, w=96, h=21, **GRL),
        dict(label="SFQtyQty", type="text", field="SFQty", fmt="standard", x=281, y=4, w=96, h=21, align="right", **GRL),
        dict(label="UOM", type="text", field="UOM", x=381, y=4, w=47, h=21, **GRL),
        dict(label="Storage Location", head_style=RED, type="combo", field="StorageLoc", x=432, y=4, w=107, h=21,
             options=L.storage_locations, limit=True),
        dict(label="C'l Status", head_style=RED, type="combo", field="Status", x=543, y=4, w=96, h=21,
             options=L.statuses, limit=True, color="#BA1419"),
        dict(label="C'l Date", head_style=RED, type="date", field="ClearanceDate", x=643, y=4, w=96, h=21),
        dict(label="MPC PO#", type="text", field="MPCPONo", x=743, y=4, w=96, h=21, **GRL),
        dict(label="Item", type="text", field="MPCPOItemNo", x=843, y=4, w=33, h=21, **GRL),
        dict(label="MPC GR#", head_style=RED, type="text", field="MPCGRN", x=880, y=4, w=102, h=21),
        dict(label="MPC GR Date", head_style=RED, type="date", field="MPCGRDate", x=986, y=4, w=108, h=21),
        dict(label="Supplier Inv#", type="text", field="SupplierInv", x=1098, y=4, w=140, h=21, **GRL),
        dict(label="BOL#", type="text", field="BOL", x=1242, y=4, w=140, h=21, **GRL),
        dict(label="Remarks", type="text", field="GRRemarks", x=1386, y=4, w=164, h=21),
        dict(label="UID", type="text", field="UID", x=1554, y=4, w=80, h=21, locked=True),
        dict(sec="footer", type="button", caption="Complete the Updation of the PO Status", cls="orange round",
             x=12, y=4, w=268, h=60,
             action={"do": "open", "save": True, "url": "/f/update_po_sf_from_gr?MPCPONo={MPCPONo}&ItemNo={MPCPOItemNo}",
                     "title": "UpdatePOSFfromGR", "w": 241, "h": 245}),
    ],
)

form(
    "update_po_sf_from_gr", title="UpdatePOSFfromGR", model=SS, width=224,
    detail=dict(h=164, bg="#ffffff"), allow_add=False, allow_delete=False, open_at="first",
    query=lambda p: SS.query.filter(SS.MPCPONo == p.get("MPCPONo", ""), SS.ItemNo == p.get("ItemNo", "")).order_by(SS.ID),
    required={"Status": "ShipmentsStatus.Status"},
    controls=[
        dict(type="label", text="MPC PO No", x=12, y=16, w=96, h=21),
        dict(type="text", field="MPCPONo", x=112, y=16, w=96, h=21, locked=True, color=LOCKED_FG),
        dict(type="label", text="Item No", x=12, y=41, w=96, h=21),
        dict(type="text", field="ItemNo", x=112, y=41, w=96, h=21, locked=True, color=LOCKED_FG),
        dict(type="label", text="SF No", x=12, y=66, w=96, h=21),
        dict(type="text", field="SFNo", x=112, y=66, w=96, h=21, locked=True, color=LOCKED_FG),
        dict(type="label", text="Status", x=12, y=91, w=96, h=21, bold=True),
        dict(type="combo", field="Status", x=112, y=91, w=96, h=21, options=L.statuses, limit=True, bold=True, color="#BA1419"),
        dict(type="button", icon="close_form", cls="flat", x=168, y=120, w=38, h=32, tip="Close Form", action={"do": "close"}),
    ],
)


# ── 2. Local Stock of Single Product ─────────────────────────────────

# Unbound dialogs (LocalStockRpt, MultiDNNo): the engine needs a model; nothing is ever saved to it.
form(
    "local_stock_rpt", title="LocalStockRpt", model=Products, width=272, detail=dict(h=76, bg="#ffffff"),
    nav=False, allow_delete=False, styles=STYLES, scripts=SCRIPTS,
    controls=[
        dict(type="label", text="Product Name", x=12, y=12, w=93, h=21, style="font:bold 11pt 'Times New Roman'"),
        dict(type="combo", name="Combo4", x=108, y=12, w=144, h=21, options=L.products, color="#222A35"),
        dict(type="button", caption="Open Report", cls="gray", x=168, y=44, w=85, h=21,
             action={"do": "js", "fn": "openLocalStock"}),
    ],
)


def _local_stock(params):
    product = params.get("product") or params.get("p") or ""
    rows = (SF.query.filter(SF.Product == product, SF.Status.in_(["Incoming", "Cleared"]), SF.DeliveredOn.is_(None))
            .order_by(SF.Status, SF.ETA, SF.Supplier, SF.ContainerNo, SF.UID).all())
    groups = []
    for status in sorted({r.Status for r in rows}):
        g = [r for r in rows if r.Status == status]
        groups.append(dict(status=status, rows=g, total=sum(float(r.SFQty or 0) for r in g)))
    return {"product": product, "groups": groups, "grand": sum(float(r.SFQty or 0) for r in rows),
            "container": container}


report("rpt_local_stock", title="Local Stock of Product", template="reports/stock_local.html", data=_local_stock)


# ── 3. Delivery Note forms (DN from the stock report, DNParticular from the menu) ──

LBL = "font:11pt Calibri"
LK = dict(locked=True, bg=LOCKED_BG, color=LOCKED_FG)
GREYBOX = dict(bg=LOCKED_BG, color=LOCKED_FG)


def _dn_controls(top, particular):
    """Spec §6.2. DN buttons sit 16 px higher than DNParticular's."""
    def row(label, y, **c):
        return [dict(type="label", text=label, x=8, y=y, w=159, h=20, style=LBL), dict(x=172, y=y, w=197, h=20, **c)]

    num = dict() if particular else dict(align="center", bold=True)
    c = [
        dict(sec="header", type="label", text="Delivery Note", x=8, y=4, w=304, h=32,
             style="font:bold italic 16pt Calibri;color:#fff"),
        dict(type="label", text="Delivery Note#", x=8, y=8, w=98, h=20, style=LBL),
        dict(type="text", field="UID", x=108, y=8, w=92, h=20, **LK, **num),
        dict(type="label", text="S/F#", x=212, y=8, w=34, h=20, style=LBL),
        dict(type="text", field="SF", x=248, y=8, w=120, h=20, **LK, **num),
    ]
    c += row("Product Name:", 36, type="text", field="Product", **LK)
    c += row("Qty:", 61, type="text", field="SFQty", fmt="standard", locked=True, bg=LOCKED_BG, color="#BA1419")
    c += row("UOM:", 86, type="text", field="UOM", **LK)
    c += row("Container #:", 110, type="text", field="ContainerNo", **LK)
    c += row("Storage Location:", 135, type="text", field="StorageLoc", **LK)
    c += row("Delivery Date:", 160, type="date", field="DeliveredOn", align="center", tab=0)
    c += row("Affliate Name:", 185, type="combo", field="DeliveredTo", options=L.customers, color="#222A35", tab=1)
    c += row("Location Code:", 210, type="combo", field="DeliveredToPlant", options=plant_options, color="#222A35",
             after="plant", tab=2)
    c += row("Location Address:", 234, type="text", field="DeliveredToAdd1", **GREYBOX)
    c += row("Location Address 2:", 259, type="text", field="DeliveredToAdd2", **GREYBOX)
    c += row("Contact Person:", 284, type="text", field="DeliveredToContactName", **GREYBOX)
    c += row("Tel #", 309, type="text", field="DeliveredToContactTel", **GREYBOX)
    c += row("Mob #", 334, type="text", field="DeliveredToContactMob", **GREYBOX)
    c += row("Transporter:", 358, type="combo", field="DeliveredTransporter", options=L.transporters, color="#222A35", tab=3)
    c += row("PO #", 383, type="combo", field="DeliveredPO", options=_po_options(True), color="#222A35", after="po", tab=4,
             tip="CusPONo / Item  —  Product | Affiliate")
    c += row("PO Item #", 408, type="text", field="DeliveredPOItem", **LK)
    c += row("SO #", 434, type="text", field="DeliveredSO", **GREYBOX)
    c += row("Packing", 458, type="combo", field="DeliveredPacking", options=L.packing, color="#222A35", tab=5)
    c += row("Delivery Remarks", 483, type="text", field="DeliveryRemarks", tab=6)
    c += [
        dict(type="button", caption="Print to PDF", cls="orange", x=8, y=top, w=124, h=25,
             action={"do": "js", "fn": "dnPrint", "pdf": "dn_pdf"}),
        dict(type="button", caption="Reverse Delivery", cls="orange white", x=264, y=top, w=104, h=25,
             action={"do": "hook", "name": "reverse"}),
        dict(type="button", caption="Send e-mail (WH)", cls="orange", x=8, y=top + 32, w=124, h=25,
             action={"do": "js", "fn": "dnEmail", "kind": "dn_warehouse"}),
        dict(type="button", caption="Send e-mail (direct)", cls="orange", x=244, y=top + 32, w=124, h=25,
             action={"do": "js", "fn": "dnEmail", "kind": "dn_transporter"}),
        dict(type="check", name="CheckGP", x=244, y=top + 64, w=14, h=14),
        dict(type="label", text="GP docs req.", x=262, y=top + 61, w=90, h=20, style="font:11pt Calibri;color:#7F7F7F"),
    ]
    return c


for _key, _particular, _top in (("dn", False, 504), ("dn_particular", True, 520)):
    form(
        _key, title="Create Delivery Note", model=SF, width=376,
        header=dict(h=36, bg=ORANGE), detail=dict(h=_top + 96, bg="#FBE4D6"),
        allow_add=False, allow_delete=False, open_at="first",
        query=lambda p: SF.query.filter(SF.UID.in_(_uids(p) or [-1])).order_by(SF.UID),
        before_save=_dn_before_save, hooks={"plant": _plant_after, "po": _po_after, "reverse": _reverse},
        styles=STYLES, scripts=SCRIPTS, prompt="Enter the DN number:" if _particular else None,
        controls=_dn_controls(_top, _particular),
    )


# ── 4. Deliver multi-items ────────────────────────────────────────────

form(
    "multi_dn_no", title="MultiDNNo", model=Products, width=254, detail=dict(h=304, bg="#ffffff"),
    nav=False, allow_delete=False, styles=STYLES, scripts=SCRIPTS,
    controls=[c for i in range(10) for c in (
        dict(type="label", text=f"Delivery Note# {i + 1}", x=16, y=12 + 25 * i, w=115, h=21, bold=True),
        dict(type="text", name=f"DN{i + 1}", x=135, y=12 + 25 * i, w=96, h=21, color=LOCKED_FG),
    )] + [dict(type="button", caption="Create Delivery Note(s)", cls="gray", x=80, y=272, w=152, h=25,
               action={"do": "js", "fn": "openMultiDN"})],
)

ML = dict(locked=True, bg=LOCKED_BG, color=LOCKED_FG)
grid(
    "multi_dn", title="Create Delivery Note", model=SF, width=1535, win=(1119, 820), row_h=32,
    allow_delete=False, nav_w=1119, row_bg="#FBE4D6", alt_bg="#FBE4D6",
    query=lambda p: SF.query.filter(SF.UID.in_(_uids(p) or [-1])).order_by(SF.UID),
    before_save=_dn_before_save, hooks={"plant": _plant_after, "po": _po_after, "reverse": _reverse_multi},
    header=dict(h=59, bg=ORANGE, col_y=36, label_style="color:#fff;justify-content:center"),
    footer=dict(h=95, bg="#FBE4D6"),
    styles=STYLES, scripts=SCRIPTS,
    columns=[
        dict(sec="header", type="label", text="Delivery Note", x=4, y=0, w=304, h=32,
             style="font:bold italic 16pt Calibri;color:#fff"),
        dict(label="DN#", type="text", field="UID", x=4, y=8, w=57, h=21, align="center", **ML),
        dict(label="S/F#", type="text", field="SF", x=65, y=8, w=51, h=21, align="center", **ML),
        dict(label="Product Name", type="text", field="Product", x=120, y=8, w=114, h=21, **ML),
        dict(label="Qty", type="text", field="SFQty", fmt="standard", x=238, y=8, w=69, h=21, locked=True,
             bg=LOCKED_BG, bold=True, color="#BA1419", align="right"),
        dict(label="UOM", type="text", field="UOM", x=311, y=8, w=40, h=21, **ML),
        dict(label="Container #", type="text", field="ContainerNo", x=355, y=8, w=96, h=21, **ML),
        dict(label="Storage Loc.", type="text", field="StorageLoc", x=455, y=8, w=84, h=21, **ML),
        dict(label="Dlvr Date", type="date", field="DeliveredOn", x=543, y=8, w=80, h=21),
        dict(label="Affliate Name", type="combo", field="DeliveredTo", x=627, y=8, w=120, h=21, options=L.customers, limit=True),
        dict(label="Location Code", type="combo", field="DeliveredToPlant", x=751, y=8, w=120, h=21, options=plant_options,
             after="plant"),
        dict(label="Transporter", type="combo", field="DeliveredTransporter", x=875, y=8, w=124, h=21,
             options=L.transporters, limit=True),
        dict(label="PO #", type="combo", field="DeliveredPO", x=1003, y=8, w=112, h=21, options=_po_options(False),
             after="po", tip="CusPONo / Item  —  Product | Affiliate"),
        dict(label="PO Item #", type="text", field="DeliveredPOItem", x=1119, y=8, w=64, h=21, **ML),
        dict(label="SO #", type="text", field="DeliveredSO", x=1187, y=8, w=70, h=21, bg=LOCKED_BG),
        dict(label="Packing", type="combo", field="DeliveredPacking", x=1261, y=8, w=89, h=21, options=L.packing),
        dict(label="Delivery Remarks", type="text", field="DeliveryRemarks", x=1354, y=8, w=159, h=21),
        # zero-width boxes that carry the address copied from the Location Code (as in Access)
        *[dict(type="text", field=f, x=1517, y=8, w=1, h=21, style="display:none")
          for f in ("DeliveredToAdd1", "DeliveredToAdd2", "DeliveredToContactName", "DeliveredToContactTel",
                    "DeliveredToContactMob")],
        dict(sec="footer", type="label", text="Total Quantity:", x=156, y=8, w=97, h=20, bold=True),
        dict(sec="footer", type="text", name="SumQty", x=257, y=8, w=96, h=20, locked=True, bold=True,
             bg=LOCKED_BG, color="#BA1419", align="right"),
        dict(sec="footer", type="button", caption="Print to PDF", cls="orange", x=384, y=8, w=128, h=25,
             action={"do": "js", "fn": "multiPrint"}),
        dict(sec="footer", type="button", caption="Reverse Delivery", cls="orange white", x=384, y=40, w=108, h=25,
             action={"do": "hook", "name": "reverse"}),
        dict(sec="footer", type="button", caption="Send e-mail to WH", cls="orange", x=540, y=8, w=128, h=25,
             action={"do": "js", "fn": "multiEmail", "kind": "dn_warehouse"}),
        dict(sec="footer", type="button", caption="Send e-mail to TP.", cls="orange", x=540, y=40, w=128, h=25,
             action={"do": "js", "fn": "multiEmail", "kind": "dn_transporter"}),
        dict(sec="footer", type="check", name="CheckMP", x=692, y=14, w=14, h=14),
        dict(sec="footer", type="label", text="Multi products", x=710, y=10, w=100, h=20),
        dict(sec="footer", type="check", name="CheckGP", x=692, y=46, w=14, h=14),
        dict(sec="footer", type="label", text="GP docs req.", x=710, y=42, w=100, h=20),
        dict(sec="footer", type="label", name="Label510", x=844, y=12, w=164, h=73, html=True,
             text="Please enter the SOs numbers manually\nto reflect in the email text:", style="display:none;white-space:normal"),
        dict(sec="footer", type="memo", name="MSOn", x=1012, y=12, w=192, h=73, style="display:none"),
    ],
)


# ── 5. Delivery Note PDFs and e-mails ─────────────────────────────────

def _rows(params):
    """Copies of the SF rows to print (ContainerNo shown with the Access input mask)."""
    uids = _uids(params)
    rows = SF.query.filter(SF.UID.in_(uids or [-1])).order_by(SF.UID).all()
    if not rows:
        raise ScreenError("An error was occurred, please check if there is info missing.")
    cols = [pr.key for pr in db.inspect(SF).column_attrs]
    out = []
    for r in rows:
        c = SimpleNamespace(**{k: getattr(r, k) for k in cols})
        c.ContainerNo = container(c.ContainerNo)
        out.append(c)
    return out


def _dn_pdf(params):
    rows = _rows(params)
    return f"Delivery Note# {rows[0].UID}.pdf", dn_pdf.build(rows)


def _multi_pdf(params):
    return "Delivery Notes Set.pdf", dn_pdf.build(_rows(params))


pdf("dn_pdf", build=_dn_pdf)
pdf("multi_dn_pdf", build=_multi_pdf)


def _emails(table_col, key_col, value):
    if not value:
        return ""
    row = db.session.query(table_col).filter(key_col == value).first()
    return (row[0] or "") if row else ""


def _dn_email(params, transporter):
    """Single DN (param id) or MultiDN (params dns + cur = the row with focus). Access took every single
    value (product, affiliate, date, UOM, location, transporter) from the current row."""
    multi = bool(params.get("dns"))
    rows = _rows(params)
    cur = next((r for r in rows if str(r.UID) == str(params.get("cur"))), rows[-1])
    mp = multi and params.get("mp") == "1" and not transporter
    product = "Multi-products" if mp else (cur.Product or "")
    qty = sum(float(r.SFQty or 0) for r in rows) if multi else cur.SFQty
    qty_label = "Total Qty" if multi else "Quantity"
    date = fmt.short_date(cur.DeliveredOn)
    subject = f"DN - {product} - {cur.DeliveredTo or ''} on {date}"
    wh_emails = _emails(StorageLoc.emails, StorageLoc.StorageLocation, cur.StorageLoc)
    logistics = L.group_emails("Logistics")
    ind = "&emsp;&emsp;"
    lines = (f"{ind}<b>Product: </b>{product}<br/>{ind}<b>Affiliate: </b>{cur.DeliveredTo or ''}<br/>"
             f"{ind}<b>{qty_label}: </b>{fmt.standard(qty)} {cur.UOM or ''}<br/>{ind}<b>Date: </b>{date}<br/>")
    intro = "Please find attached herewith Material Delivery Notification as per below details.<br/><br/>"
    if multi:
        name = "Delivery Notes Set.pdf"
    else:
        name = f"{'Delivery Note' if transporter else 'DN'}# {cur.UID}.pdf"
    attachment = [(name, dn_pdf.build(rows), "application/pdf")]
    if not transporter:
        so = (params.get("mso") or "").strip() if mp else ("" if cur.DeliveredSO is None else str(cur.DeliveredSO))
        so_line = f"{ind}<b>SO# </b>{so}<br/>" if so else ""
        html = (f"Dear {cur.StorageLoc or ''} team,<br/><br/>{intro}{lines}{so_line}<br/>"
                f"Please create SAP DN and arrange the delivery according to the attached details.<br/><br/>"
                f"Best regards,<br/>Sales Department<br/>Modern Petrochemicals Co.")
        return dict(to=wh_emails, cc=logistics, subject=subject, html=html, attachments=attachment)
    gp = ("Please share the driver and truck details for gate-pass preparation in prior time.<br/><br/>"
          if params.get("gp") == "1" else "")
    html = (f"To: {cur.DeliveredTransporter or ''}<br/><br/>{intro}{lines}<br/>{gp}"
            f"Note: Please send us immediately after delivery our delivery note duly signed/stamped by customer. "
            f"Original delivery note should be attached to your invoice. Without original delivery note your invoice "
            f"will be on hold until we receive it.<br/><br/>Best regards,<br/>Logistics Department<br/>Modern Petrochemicals Co.")
    tp_emails = _emails(Transporters.emails, Transporters.TransporterName, cur.DeliveredTransporter)
    cc = "; ".join(x for x in (logistics, wh_emails) if x)
    return dict(to=tp_emails, cc=cc, subject=subject, html=html, attachments=attachment)


eml("dn_warehouse", build=lambda p: _dn_email(p, transporter=False))
eml("dn_transporter", build=lambda p: _dn_email(p, transporter=True))


# ── 6. Shipments Delivered without Invoice ────────────────────────────

def _dlvrd_wo_inv(params):
    rows = (SF.query.filter(SF.Product != "FCC Catalyst", SF.DeliveredOn.isnot(None), SF.InvNo.is_(None))
            .order_by(SF.Product, SF.DeliveredPO, SF.UID).all())
    products = []
    for prod in sorted({r.Product for r in rows}):
        pr = [r for r in rows if r.Product == prod]
        pos = []
        for po in sorted({r.DeliveredPO or "" for r in pr}):
            lines = [r for r in pr if (r.DeliveredPO or "") == po]
            pos.append(dict(po=po, to=lines[0].DeliveredTo or "", rows=lines,
                            total=sum(float(r.SFQty or 0) for r in lines)))
        products.append(dict(product=prod, pos=pos))
    return {"products": products, "now": datetime.now(), "container": container}


report("rpt_dlvrd_wo_inv", title="ShipmentsDlvrdWOInv", template="reports/stock_dlvrd_wo_inv.html",
       data=_dlvrd_wo_inv, portrait=True)


# ── 7. Updation of Delivery/Invoice ───────────────────────────────────

def _cus_po_list(params=None):
    return [[c.CusPONo, c.Product or ""] for c in CustomersPO.query.order_by(CustomersPO.CusPONo)]


MAG, RD = "color:#EA35DD", "color:#ED1C24"
UL = dict(locked=True)
grid(
    "updation_of_inv", title="Updation of Invoices", model=SF, width=1299, win=(1316, 595), row_h=24,
    allow_delete=False, nav_w=1316,
    query=lambda p: SF.query.filter(SF.SF == _sf_no(p)).order_by(SF.UID),
    header=dict(h=26, bg="#D6DCE5", col_y=4,
                label_style="font:bold 11pt 'Times New Roman';justify-content:center"),
    columns=[
        dict(label="SF", type="text", field="SF", x=4, y=2, w=62, h=20, align="center", **UL),
        dict(label="Container #", type="text", field="ContainerNo", x=70, y=2, w=103, h=20, **UL),
        dict(label="Product", type="text", field="Product", x=178, y=2, w=135, h=20, **UL),
        dict(label="Qty", type="text", field="SFQty", fmt="standard", x=318, y=2, w=83, h=20, align="right", **UL),
        dict(label="Delivery Date", head_style=MAG, type="date", field="DeliveredOn", x=406, y=2, w=96, h=20, color="#EA35DD"),
        dict(label="Delivered PO#", head_style=MAG, type="combo", field="DeliveredPO", x=507, y=2, w=102, h=20,
             options=_cus_po_list),
        dict(label="Item#", head_style=MAG, type="text", field="DeliveredPOItem", x=614, y=2, w=43, h=20),
        dict(label="Affiliate", head_style=MAG, type="combo", field="DeliveredTo", x=662, y=2, w=131, h=20,
             options=L.customers, limit=True),
        dict(label="SAP DN No", head_style=RD, type="text", field="SAPDNNo", x=798, y=2, w=96, h=20, color="#ED1C24"),
        dict(label="Invoice #", head_style=RD, type="text", field="InvNo", x=899, y=2, w=102, h=20, color="#ED1C24"),
        dict(label="Invoice Date", head_style=RD, type="date", field="InvDate", x=1006, y=2, w=96, h=20, color="#ED1C24"),
        dict(label="Customer GR#", type="text", field="CusGR", x=1107, y=2, w=102, h=20),
        dict(label="UID", type="text", field="UID", x=1214, y=2, w=82, h=20, align="center", locked=True),
    ],
)
