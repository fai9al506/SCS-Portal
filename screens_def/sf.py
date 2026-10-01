"""Main Menu box "Shipment Files" — spec access_spec/2_shipment_files.md.

Screens: SF (Create new S/F), the four "Copy SF" lists (Add S/F Items), UpdatePOSF, SF_BrokerCover
(Docs to Broker) with its two cover-letter reports and Outlook draft, SFFullDetails (locked / editable).
Decisions applied (DECISIONS.md): bug 4 — an S/F number is given only to a line that has none (never
renumbered) and is allocated inside the save, so two users can't get the same number; bug 9 — a line with
no MPC PO and no S/F can't be saved; B5 — Total Inv Amount = Qty × Unit Price (Access calculated column).
"""
from datetime import datetime

from flask import request
from sqlalchemy import func, text

from extensions import db
from models import Brokers, CustomerAdd, CustomersPO, SF, SFBrokerCover, ShipmentsStatus
from screens_def import lookups as L
from services import fmt
from services.screens import ScreenError, eml, form, grid, report

SS = ShipmentsStatus

NOT_IN_LIST = ("The text you entered isn't an item in the list.\n\n"
               "Select an item from the list, or enter text that matches one of the listed items.")

# ── shared look (spec 0.6) ────────────────────────────────────────────
BLUE_HEAD = "#4472C4"
DETAIL_BG = "#DAE3F3"
TITLE = "font:bold italic 16pt 'Times New Roman';color:#fff"
LBL = "font:bold 11pt Calibri;color:#000"
GREY = "#E7E6E6"
RED = "#BA1419"
PACKINGS = ["Container", "Tank", "Other"]


def _lbl(text, x, y, w, h=21, style=LBL):
    return dict(type="label", text=text, x=x, y=y, w=w, h=h, style=style)


# ── row sources ───────────────────────────────────────────────────────

def _sf_total_by_item():
    """SFTotalQty: Σ SFQty per (MPCPONo, MPCPOItemNo) over all SF lines."""
    return {(m, i): float(q or 0) for m, i, q in
            db.session.query(SF.MPCPONo, SF.MPCPOItemNo, func.sum(SF.SFQty)).group_by(SF.MPCPONo, SF.MPCPOItemNo)}


def open_po_lines():
    """SFminusPO: PO lines whose Qty − Σ SFQty (same PO + item) > 0; lines with an ETA first, by ETA."""
    used = _sf_total_by_item()
    rows = SS.query.order_by(SS.ETA.is_(None), SS.ETA, SS.ID).all()
    return [r for r in rows if float(r.Qty or 0) - used.get((r.MPCPONo, r.ItemNo), 0) > 0]


def _po_value(r):
    return f"{r.MPCPONo} #{r.ItemNo}"


def po_pick_options(params=None):
    """MPCPONo combo of the SF form. The value carries the item ("4501291671 #2") so the pick is exact."""
    return [[_po_value(r), r.Supplier or "", r.Product or "", fmt.standard(r.Qty), r.UOM or "", fmt.short_date(r.ETD),
             fmt.short_date(r.ETA), r.POD or "", r.Status or "", f"Item {r.ItemNo}"] for r in open_po_lines()]


def all_po_options(params=None):
    """MPC PO# combo of the Copy SF lists: every PO line (10 columns in Access)."""
    return [[r.MPCPONo or "", r.Supplier or "", r.Product or "", fmt.standard(r.Qty), fmt.short_date(r.ETD),
             fmt.short_date(r.ETA), r.POD or "", r.Status or "", fmt.general(r.UnitPrice), r.ACurr or ""]
            for r in SS.query.order_by(SS.ID) if r.MPCPONo]


def customer_po_numbers(params=None):
    return [r[0] for r in db.session.query(CustomersPO.CusPONo).distinct().order_by(CustomersPO.CusPONo) if r[0]]


def customer_po_with_product(params=None):
    return [[r.CusPONo, r.Product or ""] for r in CustomersPO.query.order_by(CustomersPO.CusPONo, CustomersPO.ItemNo)
            if r.CusPONo]


def customer_plants(params=None):
    return sorted({r[0] for r in db.session.query(CustomerAdd.CustomerPlant) if r[0]})


def status_list(params=None):
    return L.statuses()


# ── S/F number allocation and line rules ──────────────────────────────

def _lock_sf_numbers():
    """Serialise S/F number allocation between users (Postgres advisory lock, released at commit)."""
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(6262)"))


def next_sf_number():
    _lock_sf_numbers()
    return int(db.session.query(func.max(SF.SF)).scalar() or 0) + 1


def _clean_container(v):
    return v.replace(" ", "").upper() if v else v


def sf_line_before_save(row, typed, params, merged):
    """Rules shared by every screen that saves an SF line."""
    if "ContainerNo" in typed:
        typed["ContainerNo"] = _clean_container(typed["ContainerNo"])
    po = merged.get("MPCPONo")
    sfno = merged.get("SF")
    if not po and not sfno:
        raise ScreenError("Choose the MPC PO# first.\n\nA shipment file line needs an MPC PO or an S/F number.")
    if "MPCPONo" in typed and po and not SS.query.filter(SS.MPCPONo == po).first():
        raise ScreenError(NOT_IN_LIST)
    # bug 4: give the next number only to a line without one; never renumber an existing S/F
    if not sfno and po:
        typed["SF"] = next_sf_number()


# ── 1. Form SF — "Create new S/F" ─────────────────────────────────────

def _po_pick(rec, params, row):
    """MPCPONo AfterUpdate: copy the chosen PO line into the S/F line (Access VBA)."""
    # The combo value carries the item ("4501291671 #2"), longer than the 10-char field, so read it raw.
    raw = str((request.get_json(silent=True) or {}).get("values", {}).get("MPCPONo") or rec.get("MPCPONo") or "").strip()
    po, _, item = raw.partition("#")
    po, item = po.strip(), item.strip()
    q = SS.query.filter(SS.MPCPONo == po)
    if item:
        q = q.filter(SS.ItemNo == item)
    lines = q.order_by(SS.ID).all()
    if not lines:
        raise ScreenError(NOT_IN_LIST)
    open_ids = {r.ID for r in open_po_lines()}
    line = next((r for r in lines if r.ID in open_ids), lines[0])
    return {"updates": {
        "MPCPONo": line.MPCPONo, "MPCPOItemNo": line.ItemNo, "Supplier": line.Supplier, "Product": line.Product,
        "SFQty": line.Qty, "UOM": line.UOM, "ETD": line.ETD, "ETA": line.ETA, "POD": line.POD,
        "Status": line.Status, "UnitPrice": line.UnitPrice, "ACurr": line.ACurr, "PermitNo": line.PermitNo,
    }}


def _create_sf_no(rec, params, row):
    """Command242 "Create S/F #"."""
    if rec.get("SF"):
        return {"message": "S/F number already maintained", "icon": "info"}
    if not rec.get("MPCPONo"):
        raise ScreenError("Choose the MPC PO# first.\n\nA shipment file line needs an MPC PO or an S/F number.")
    # the number is allocated when the line is saved (safe for two users at once)
    return {"updates": {"MPCPONo": rec.get("MPCPONo")}, "save": True}


def _add_items(rec, params, row):
    """Command250 "Add items": FCC Catalyst lines get the list with Delivery Remarks."""
    if row is None or not row.SF:
        raise ScreenError("Save the S/F line first.")
    fcc = (row.Product or "") == "FCC Catalyst"
    return {"open": {"url": f"/g/{'copy_sf_fcc' if fcc else 'copy_sf_sf'}?SF={row.SF}", "title": "Copy SF",
                     "w": 1014 if fcc else 844, "h": 520}}


def _inv_amount(r):
    if r.get("SFQty") is None and r.get("UnitPrice") is None:
        return None
    return float(r.get("SFQty") or 0) * float(r.get("UnitPrice") or 0)


L1, C1, L2, C2 = 20, 96, 320, 446
form(
    "sf", title="SF", model=SF, width=660,
    header=dict(h=36, bg=BLUE_HEAD), detail=dict(h=340, bg=DETAIL_BG),
    open_at="new", before_save=sf_line_before_save,
    hooks={"po_pick": _po_pick, "create_sf": _create_sf_no, "add_items": _add_items},
    calc=lambda r, p: {"TotalInvAmount": _inv_amount(r)},
    controls=[
        dict(sec="header", type="label", text="New Shipment File (S/F)", x=8, y=4, w=304, h=32, style=TITLE),
        _lbl("SF", L1, 8, 71),
        dict(type="text", field="SF", x=C1, y=8, w=96, h=21, locked=True, bold=True, align="center",
             tip="Shipment File"),
        dict(type="button", caption="Create S/F #", cls="blue", x=198, y=8, w=108, h=21,
             action={"do": "hook", "name": "create_sf"}),
        _lbl("MPCPONo", L1, 33, 71),
        dict(type="combo", field="MPCPONo", x=C1, y=33, w=176, h=20, options=po_pick_options, after="po_pick",
             color="#222A35", tab=0),
        dict(type="text", field="MPCPOItemNo", x=276, y=33, w=30, h=20, locked=True, unlockable=True, bg=GREY),
        _lbl("Supplier", L1, 57, 71),
        dict(type="combo", field="Supplier", x=C1, y=57, w=210, h=20, options=L.suppliers, limit=True, color="#222A35", tab=1),
        _lbl("Product", L1, 80, 71),
        dict(type="combo", field="Product", x=C1, y=80, w=210, h=20, options=L.products, limit=True, color="#222A35", tab=2),
        _lbl("Qty", L1, 104, 71),
        dict(type="text", field="SFQty", fmt="standard", x=C1, y=104, w=122, h=20, bold=True, color=RED, align="right", tab=3),
        dict(type="combo", field="UOM", x=222, y=104, w=84, h=20, options=L.uoms, limit=True, tab=4),
        _lbl("Packing", L1, 128, 71),
        dict(type="select", field="Packing", x=C1, y=128, w=210, h=20, options=PACKINGS, limit=True, tab=5),
        _lbl("Container#", L1, 152, 75),
        dict(type="text", field="ContainerNo", x=C1, y=152, w=210, h=21, tab=6, tip="4 letters + 7 digits, e.g. FANU1991549",
             style="text-transform:uppercase"),
        _lbl("ETD", L1, 177, 71), dict(type="date", field="ETD", x=C1, y=177, w=210, h=20, tab=7),
        _lbl("ETA", L1, 200, 71), dict(type="date", field="ETA", x=C1, y=200, w=210, h=20, tab=8),
        _lbl("POD", L1, 224, 71), dict(type="combo", field="POD", x=C1, y=224, w=210, h=20, options=L.ports, tab=9),
        _lbl("Status", L1, 248, 71),
        dict(type="combo", field="Status", x=C1, y=248, w=210, h=20, options=status_list, limit=True, tab=10),
        _lbl("Intended Customer", L2, 8, 122),
        dict(type="combo", field="IntendedCustomer", x=C2, y=8, w=210, h=20, options=L.customers, limit=True, color="#222A35", tab=11),
        _lbl("Customer PO#", L2, 32, 122),
        dict(type="combo", field="IntendedCustomerPO", x=C2, y=32, w=210, h=20, options=customer_po_numbers, limit=True, tab=12),
        _lbl("Broker", L2, 56, 122),
        dict(type="combo", field="Broker", x=C2, y=56, w=210, h=20, options=L.brokers, limit=True, color="#222A35", tab=13),
        _lbl("PermitNo", L2, 80, 122), dict(type="text", field="PermitNo", x=C2, y=80, w=210, h=20, tab=14),
        _lbl("Shipping Line", L2, 104, 122),
        dict(type="combo", field="ShippingLine", x=C2, y=104, w=210, h=20, options=L.shipping_lines, limit=True, tab=15),
        _lbl("BOL", L2, 128, 122), dict(type="text", field="BOL", x=C2, y=128, w=210, h=20, tab=16),
        _lbl("Supplier Inv#", L2, 152, 122), dict(type="text", field="SupplierInv", x=C2, y=152, w=210, h=20, tab=17),
        _lbl("Inv Date", L2, 176, 122), dict(type="date", field="SupplierInvDate", x=C2, y=176, w=210, h=20, tab=18),
        _lbl("UnitPrice", L2, 200, 122),
        dict(type="text", field="UnitPrice", x=C2, y=200, w=122, h=20, align="right", tab=19),
        dict(type="combo", field="ACurr", x=572, y=200, w=84, h=20, options=L.currencies, tab=20),
        _lbl("Total Inv Amount", L2, 224, 122),
        dict(type="calc", name="TotalInvAmount", fmt="standard", x=C2, y=224, w=210, h=20, bg=GREY, align="right"),
        _lbl("Remarks", L2, 248, 122), dict(type="text", field="Remarks", x=C2, y=248, w=210, h=20, tab=21),
        dict(type="button", caption="Add New S/F", cls="blue", x=20, y=280, w=88, h=24, action={"do": "new"}),
        dict(type="button", caption="Delete S/F", cls="blue", x=20, y=308, w=88, h=24, action={"do": "delete"}),
        dict(type="button", caption="Add items", cls="blue", x=112, y=280, w=97, h=52,
             action={"do": "hook", "name": "add_items", "save": True}),
        dict(type="button", caption="Update PO/SF", cls="blue", x=556, y=280, w=97, h=24,
             action={"do": "open", "save": True, "url": "/f/update_po_sf?MPCPONo={MPCPONo}&ItemNo={MPCPOItemNo}",
                     "title": "UpdatePOSF", "w": 226, "h": 223}),
        dict(type="button", icon="4d2a44da_envelope", cls="blue", x=556, y=308, w=48, h=24, tip="Docs to Broker",
             action={"do": "open", "save": True, "url": "/f/sf_broker_cover", "title": "SF_BrokerCover", "w": 574, "h": 523}),
        dict(type="button", icon="close_form", cls="blue", x=608, y=308, w=44, h=24, tip="Close Form", action={"do": "close"}),
    ],
)


# ── 2. "Copy SF" family — add lines (containers) to an S/F ────────────

# Fields bound on the Access form (visible + zero-width hidden) = the fields "Add new item" copies.
COPY_FIELDS = ["SF", "MPCPONo", "MPCPOItemNo", "Supplier", "Product", "SFQty", "UOM", "Packing", "ContainerNo",
               "ETD", "ETA", "POD", "Status", "IntendedCustomer", "IntendedCustomerPO", "DocsToBroker", "Broker",
               "PermitNo", "ShippingLine", "BOL", "SupplierInv", "SupplierInvDate", "UnitPrice", "ACurr", "Remarks",
               "ClearanceDate", "StorageLoc", "MPCGRN", "MPCGRDate", "GRRemarks", "DeliveredOn", "DeliveredTo",
               "DeliveredToPlant", "DeliveredToAdd1", "DeliveredToAdd2", "DeliveredToContactName",
               "DeliveredToContactTel", "DeliveredToContactMob", "DeliveredTransporter", "DeliveredPO",
               "DeliveredPacking", "SAPDNNo", "InvNo", "InvDate", "CusGR", "EmptyPickNotified", "EIRNo",
               "ReturnTerminal"]

COPY_HEAD = dict(h=74, bg="#D6DCE5", col_y=52, label_style="font:bold 11pt Calibri;color:#7F7F7F")


def _copy_header():
    return [
        dict(sec="header", type="label", text="Copy SF", x=4, y=4, w=144, h=34,
             style="font:bold italic 20pt 'Times New Roman';color:#7F7F7F"),
        dict(sec="header", type="button", caption="Add new item", cls="gray", x=180, y=8, w=106, h=27, action={"do": "copy"}),
        dict(sec="header", type="button", caption="Delete Item", cls="gray", x=296, y=8, w=106, h=27, action={"do": "delete"}),
    ]


def _copy_columns(full=True, fcc=False):
    cols = [
        dict(label="UID", type="text", field="UID", x=2, y=2, w=70, h=20, locked=True, color="#404040"),
        dict(label="SF", type="text", field="SF", x=76, y=2, w=68, h=20),
        dict(label="Container #", type="text", field="ContainerNo", x=148, y=2, w=100, h=20, bold=True, color=RED,
             style="text-transform:uppercase"),
        dict(label="Qty", type="text", field="SFQty", fmt="standard", x=252, y=2, w=88, h=20, bold=True, color=RED, align="right"),
        dict(label="UOM", type="combo", field="UOM", x=344, y=2, w=40, h=20, options=L.uoms, limit=True),
    ]
    if full:
        cols += [
            dict(label="MPC PO#", type="combo", field="MPCPONo", x=388, y=2, w=104, h=20, options=all_po_options, limit=True),
            dict(label="Item", type="text", field="MPCPOItemNo", x=496, y=2, w=32, h=20),
            dict(label="Product", type="combo", field="Product", x=532, y=2, w=135, h=20, options=L.products),
        ]
    if fcc:
        cols.append(dict(label="Delivery Remarks", type="text", field="DeliveryRemarks", x=671, y=2, w=330, h=20))
    return cols


def _sf_param(name):
    def q(p):
        try:
            n = int(str(p.get(name, "")).strip())
        except ValueError:
            return SF.query.filter(db.false())
        return SF.query.filter(SF.SF == n).order_by(SF.UID)
    return q


def _ls_query(p):
    """Copy SF (for LS): the stock line's S/F + container (Access filter on the report row)."""
    src = db.session.get(SF, int(p.get("UID") or 0)) if str(p.get("UID", "")).isdigit() else None
    if src is None:
        return SF.query.filter(db.false())
    return SF.query.filter(SF.SF == src.SF, SF.ContainerNo == src.ContainerNo).order_by(SF.UID)


_copy_common = dict(model=SF, row_h=24, copy=True, before_save=sf_line_before_save, scripts=["access/sf.js"])

grid("copy_sf", title="Copy SF", width=680, win=(903, 520), query=_sf_param("p"), header=COPY_HEAD,
     copy_fields=COPY_FIELDS, columns=_copy_header() + _copy_columns(), **_copy_common)
grid("copy_sf_sf", title="Copy SF", width=680, win=(844, 520), query=_sf_param("SF"), header=COPY_HEAD,
     copy_fields=COPY_FIELDS, columns=_copy_header() + _copy_columns(), **_copy_common)
grid("copy_sf_fcc", title="Copy SF", width=1010, win=(1014, 520), query=_sf_param("SF"), header=COPY_HEAD,
     copy_fields=COPY_FIELDS + ["DeliveryRemarks"], columns=_copy_header() + _copy_columns(fcc=True), **_copy_common)
grid("copy_sf_ls", title="Copy SF", width=576, win=(576, 420), query=_ls_query, header=COPY_HEAD,
     copy_fields=COPY_FIELDS, footer=dict(h=40, bg="#D6DCE5"),
     columns=_copy_header() + _copy_columns(full=False) + [
         dict(sec="footer", type="button", caption="Go back to the stock report", cls="gray", x=396, y=4, w=172, h=27,
              action={"do": "js", "fn": "sfBackToStock"}),
     ], **_copy_common)


# ── 5. UpdatePOSF — write the S/F number and status onto the PO line ──

form(
    "update_po_sf", title="UpdatePOSF", model=SS, width=224, detail=dict(h=164, bg="#FFFFFF"),
    open_at="first", allow_add=False, allow_delete=False,
    query=lambda p: SS.query.filter(SS.MPCPONo == p.get("MPCPONo", ""), SS.ItemNo == p.get("ItemNo", "")).order_by(SS.ID),
    required={"Status": "ShipmentsStatus.Status"},
    controls=[
        _lbl("MPC PO No", 12, 16, 96, style="font:11pt Calibri"),
        dict(type="text", field="MPCPONo", x=112, y=16, w=100, h=21, locked=True),
        _lbl("Item No", 12, 41, 96, style="font:11pt Calibri"),
        dict(type="text", field="ItemNo", x=112, y=41, w=100, h=21, locked=True),
        _lbl("Status", 12, 66, 96),
        dict(type="combo", field="Status", x=112, y=66, w=100, h=21, options=status_list, limit=True, bold=True, color=RED, tab=0),
        _lbl("SFNo", 12, 91, 96),
        dict(type="text", field="SFNo", x=112, y=91, w=100, h=21, bold=True, color=RED, tab=1),
        dict(type="button", icon="close_form", cls="gray", x=168, y=120, w=38, h=32, tip="Close Form", action={"do": "close"}),
    ],
)


# ── 3. SF_BrokerCover — "Docs to Broker" ──────────────────────────────

def sf_groups():
    """Query "SF Total Qty": one row per S/F (and grouped fields) for lines not yet cleared, newest first."""
    keys = [SF.SF, SF.Product, SF.UOM, SF.ETD, SF.ETA, SF.POD, SF.DocsToBroker, SF.Broker, SF.ShippingLine, SF.BOL,
            SF.SupplierInv, SF.SupplierInvDate, SF.ClearanceDate, SF.IntendedCustomer, SF.IntendedCustomerPO, SF.PermitNo]
    rows = (db.session.query(*keys, func.sum(SF.SFQty).label("qty"), func.count(SF.ContainerNo).label("fcl"))
            .filter(SF.ClearanceDate.is_(None)).group_by(*keys).order_by(SF.SF.desc()).all())
    return [r for r in rows if r.SF]


def sf_no_options(params=None):
    seen, out = set(), []
    for r in sf_groups():
        if r.SF not in seen:
            seen.add(r.SF)
            out.append([str(r.SF), r.Product or "", f"{fmt.standard(r.qty)} {r.UOM or ''}", f"{r.fcl} FCL"])
    return out


def _cover_fill(sfno):
    """SFNo AfterUpdate: copy the S/F totals and the broker's details (snapshot)."""
    g = next((r for r in sf_groups() if r.SF == sfno), None)
    if g is None:
        raise ScreenError(NOT_IN_LIST)
    vals = {"Product": g.Product, "SFQty": g.qty, "NoFCL": g.fcl, "UOM": g.UOM, "ETD": g.ETD, "ETA": g.ETA,
            "POD": g.POD, "DocsToBroker": datetime.now().replace(microsecond=0), "Broker": g.Broker,
            "ShippingLine": g.ShippingLine, "BOL": g.BOL, "SupplierInv": g.SupplierInv,
            "IntendedCustomer": g.IntendedCustomer, "PermitNo": g.PermitNo}
    try:
        vals["IntendedCustomerPO"] = int(str(g.IntendedCustomerPO).strip()) if g.IntendedCustomerPO else None
    except ValueError:
        vals["IntendedCustomerPO"] = None
    b = Brokers.query.filter_by(BrokerName=g.Broker).first() if g.Broker else None
    for f in ("BrokerFullName", "BrokerAdd1", "BrokerAdd2", "BrokerAdd3Tel", "BrokerAdd4Mob", "BrokerRepName", "BrokerEmails"):
        vals[f] = getattr(b, f) if b else None
    return vals


def _cover_pick(rec, params, row):
    if rec.get("SFNo") in (None, ""):
        return {}
    return {"updates": _cover_fill(int(rec["SFNo"]))}


def _cover_before_save(row, typed, params, merged):
    if not merged.get("SFNo"):
        raise ScreenError("You must enter a value in the 'SF_BrokerCover.SFNo' field.")
    if "SFNo" in typed and (row is None or row.SFNo != typed["SFNo"]):
        if str(typed["SFNo"]) not in {o[0] for o in sf_no_options()}:
            raise ScreenError(NOT_IN_LIST)
        fill = _cover_fill(typed["SFNo"])
        if typed.get("PermitNo"):          # PermitNo stays editable after the pick
            fill.pop("PermitNo")
        typed.update(fill)


CL = 20     # left labels
CV = 146    # left values
_hidden = "display:none"
_count_rows = [("BOL", "BOL", 36), ("Invoice", "Inv", 64), ("Cert. of Origin", "COO", 92),
               ("Cert. of Analysis", "COA", 120), ("Packing List", "PL", 148), ("Insurance", "Insurance", 176)]

form(
    "sf_broker_cover", title="SF_BrokerCover", model=SFBrokerCover, width=572,
    header=dict(h=36, bg=BLUE_HEAD), detail=dict(h=428, bg=DETAIL_BG),
    open_at="new", before_save=_cover_before_save, hooks={"sfno": _cover_pick},
    scripts=["access/sf.js"],
    controls=[
        dict(sec="header", type="label", text="Shipment Notify and Documents send to Broker", x=8, y=4, w=520, h=32, style=TITLE),
        _lbl("SFNo", CL, 8, 120),
        dict(type="combo", field="SFNo", x=CV, y=8, w=96, h=21, options=sf_no_options, bold=True, align="center",
             after="sfno", tab=0),
        _lbl("Product", CL, 36, 120),
        dict(type="text", field="Product", x=CV, y=36, w=144, h=21, locked=True, bg=GREY),
        _lbl("Qty", CL, 64, 120),
        dict(type="text", field="SFQty", fmt="standard", x=CV, y=64, w=98, h=21, locked=True, bg=GREY, bold=True,
             color=RED, align="right"),
        dict(type="text", field="UOM", x=246, y=64, w=44, h=21, locked=True, bg=GREY),
        _lbl("FCL", CL, 88, 120), dict(type="text", field="NoFCL", fmt="int", x=CV, y=88, w=144, h=21, locked=True, bg=GREY),
        _lbl("ETD", CL, 116, 120), dict(type="date", field="ETD", x=CV, y=116, w=144, h=21, locked=True, bg=GREY),
        _lbl("ETA", CL, 140, 120), dict(type="date", field="ETA", x=CV, y=140, w=144, h=21, locked=True, bg=GREY),
        _lbl("POD", CL, 164, 120), dict(type="text", field="POD", x=CV, y=164, w=144, h=21, locked=True, bg=GREY),
        _lbl("Docs to Broker", CL, 188, 120),
        dict(type="date", field="DocsToBroker", x=CV, y=188, w=144, h=21, locked=True, bg=GREY),
        _lbl("Broker", CL, 212, 120), dict(type="text", field="Broker", x=CV, y=212, w=144, h=21, locked=True, bg=GREY),
        _lbl("PermitNo", CL, 236, 120), dict(type="text", field="PermitNo", x=CV, y=236, w=144, h=21, bg=GREY, tab=1),
        _lbl("Shipping Line", CL, 260, 120),
        dict(type="text", field="ShippingLine", x=CV, y=260, w=144, h=21, locked=True, bg=GREY),
        _lbl("BOL", CL, 284, 120), dict(type="text", field="BOL", x=CV, y=284, w=144, h=21, locked=True, bg=GREY),
        _lbl("Supplier Inv#", CL, 308, 120),
        dict(type="text", field="SupplierInv", x=CV, y=308, w=144, h=21, locked=True, bg=GREY),
        _lbl("Int. Customer", CL, 332, 120),
        dict(type="text", field="IntendedCustomer", x=CV, y=332, w=144, h=21, locked=True, bg=GREY),
        _lbl("Int. Customer PO#", CL, 356, 124),
        dict(type="text", field="IntendedCustomerPO", fmt="int", x=CV, y=356, w=144, h=21, locked=True, bg=GREY),
        # hidden snapshot fields (Visible = No in Access)
        *[dict(type="text", field=f, x=0, y=0, w=1, h=1, locked=True, style=_hidden)
          for f in ("BrokerEmails", "BrokerFullName", "BrokerAdd1", "BrokerAdd2", "BrokerRepName", "BrokerAdd4Mob",
                    "BrokerAdd3Tel")],
        # document count grid
        _lbl("# Originals", 424, 8, 80, style="font:bold 11pt Calibri;text-decoration:underline"),
        _lbl("# Copies", 508, 8, 64, style="font:bold 11pt Calibri;text-decoration:underline"),
        *[c for label, key, y in _count_rows for c in (
            _lbl(label, 332, y, 110),
            dict(type="text", field=f"NoofOrg{key}", fmt="int", x=444, y=y, w=28, h=20, align="center", tab=2),
            dict(type="text", field=f"NoofCopy{key}", fmt="int", x=524, y=y, w=28, h=20, align="center", tab=2),
        )],
        # option groups (unbound; radios are added by sf.js) + DHL tracking number
        dict(type="box", x=332, y=212, w=224, h=52, style="border:1px solid #A6A6A6"),
        _lbl("Show customer PO details?", 340, 214, 210, h=20, style="font:11pt Calibri"),
        dict(type="box", x=332, y=272, w=224, h=56, style="border:1px solid #A6A6A6"),
        _lbl("Send the docs thru DHL?", 340, 274, 210, h=20, style="font:11pt Calibri"),
        dict(type="text", field="CourierNo", x=444, y=300, w=104, h=21, tab=3),
        dict(type="button", caption="Print the Cover Letter", cls="blue", x=20, y=392, w=144, h=27,
             action={"do": "js", "fn": "sfBrokerPrint"}),
        dict(type="button", caption="Send Email", cls="blue", x=172, y=392, w=96, h=27,
             action={"do": "js", "fn": "sfBrokerEmail"}),
        dict(type="button", icon="close_form", cls="blue", x=524, y=344, w=38, h=32, tip="Close Form", action={"do": "close"}),
    ],
)


def _cover_row(params):
    row = db.session.get(SFBrokerCover, int(params.get("id") or 0)) if str(params.get("id", "")).isdigit() else None
    if row is None:
        raise ScreenError("Save the record first.")
    return {"r": row, "today": datetime.now().date()}


report("rpt_broker_cover", title="SF_BrokerCover", template="reports/sf_broker_cover.html", portrait=True,
       data=lambda p: dict(_cover_row(p), with_cus_po=False))
report("rpt_broker_cover_cuspo", title="SF_BrokerCover_wCusPO", template="reports/sf_broker_cover.html", portrait=True,
       data=lambda p: dict(_cover_row(p), with_cus_po=True))


def _broker_email(params):
    err = "An error was occurred, please check if there is info missing."
    row = db.session.get(SFBrokerCover, int(params.get("id") or 0)) if str(params.get("id", "")).isdigit() else None
    if row is None:
        raise ScreenError(err)
    b = Brokers.query.filter_by(BrokerName=row.Broker).first() if row.Broker else None
    cc = L.group_emails("Logistics")
    if not cc:
        raise ScreenError(err)
    show_po = params.get("cuspo") == "2"
    dhl = params.get("dhl") == "2"
    cus_po = "" if row.IntendedCustomerPO is None else fmt.general(row.IntendedCustomerPO)
    subject = f"S/F# {row.SFNo} - {row.Product or ''} - {fmt.general(row.NoFCL)} FCL, BOL# {row.BOL or ''}"
    if show_po:
        subject += f" - {row.IntendedCustomer or ''} PO# {cus_po}"
    em = "&emsp;&emsp;"
    html = (f"Dear {(b.BrokerRepName if b else '') or ''},<br/><br/>"
            "Please find attached herewith a copy of the Shipping Documents for customs clearance.<br/><br/>"
            + (f"Originals has be couriered by DHL, tracking no. {row.CourierNo or ''}." if dhl
               else "Kindly arrange to collect the originals from our office.") + "<br/><br/>"
            + (f"{em}<b>{row.IntendedCustomer or ''}</b><b> PO# </b>{cus_po}<br/>" if show_po else "")
            + f"{em}<b>Shipment File No.: </b>{row.SFNo}<br/>"
            f"{em}<b>Bill of Lading: </b>{row.BOL or ''}<br/>"
            f"{em}<b>Product: </b>{row.Product or ''}<br/>"
            f"{em}<b>Quantity: </b>{fmt.standard(row.SFQty)} {row.UOM or ''}<br/><br/>"
            "Please keep us updated on the customs clearance process within this subject email.<br/><br/>"
            "Best regards,<br/>Logistic In-charge<br/>Modern Petrochemicals Co.<br/>Tel: 11-2439112")
    return dict(to=(b.BrokerEmails if b else "") or "", cc=cc, subject=subject, html=html)


eml("broker_docs", build=_broker_email)


# ── 7. SFFullDetails (locked / editable) ──────────────────────────────

FA_L, FA_V, FB_L, FB_V, FC_L, FC_V = 8, 116, 302, 446, 632, 776
ROWS_Y = [8, 33, 58, 83, 108, 132, 157, 182, 207, 232, 257, 282, 307, 332, 357, 382, 407, 432, 457]
PURPLE = "#8066A0"


def _full_controls(locked):
    def v(field, x, row, kind="text", **kw):
        c = dict(type=kind, field=field, x=x, y=ROWS_Y[row], w=182, h=21, bold=True, tab=kw.pop("tab", None), **kw)
        if locked and not c.get("locked"):
            c.update(locked=True, unlockable=True)
        return c

    def lab(text, x, row, w):
        return _lbl(text, x, ROWS_Y[row], w)

    A = [("UID", "UID", "text", dict(locked=True, align="center")),
         ("S/F#", "SF", "text", dict(locked=True, align="center")),
         ("MPC PO#", "MPCPONo", "combo", dict(options=all_po_options, limit=True)),
         ("MPC PO Item#", "MPCPOItemNo", "text", {}),
         ("Supplier Name", "Supplier", "combo", dict(options=L.suppliers, limit=True, color="#222A35")),
         ("Product", "Product", "combo", dict(options=L.products, limit=True)),
         ("Quantity", "SFQty", "text", dict(fmt="standard", align="center")),
         ("UOM", "UOM", "combo", dict(options=L.uoms, limit=True)),
         ("Packing", "Packing", "select", dict(options=PACKINGS, limit=True)),
         ("Container#", "ContainerNo", "text", dict(align="center", style="text-transform:uppercase")),
         ("ETD", "ETD", "date", dict(align="center")),
         ("ETA", "ETA", "date", dict(align="center")),
         ("POD", "POD", "combo", dict(options=L.ports, limit=True)),
         ("Status", "Status", "combo", dict(options=status_list, limit=True)),
         ("Int. Customer", "IntendedCustomer", "combo", dict(options=L.customers, limit=True)),
         ("Int. PO#", "IntendedCustomerPO", "combo", dict(options=customer_po_numbers, limit=True)),
         ("Docs to Broker", "DocsToBroker", "date", {}),
         ("Broker Name", "Broker", "combo", dict(options=L.brokers, limit=True)),
         ("Permit#", "PermitNo", "text", {})]
    B = [("Shipping Line", "ShippingLine", "combo", dict(options=L.shipping_lines, limit=True)),
         ("BOL#", "BOL", "text", {}),
         ("Supplier Inv#", "SupplierInv", "text", {}),
         ("Supplier Inv Date", "SupplierInvDate", "date", dict(align="center")),
         ("Unit Price", "UnitPrice", "text", {}),
         ("Currency", "ACurr", "combo", dict(options=L.currencies, limit=True)),
         ("Remarks", "Remarks", "text", {}),
         ("Bayan#", "BayanNo", "text", {}),
         ("Clearance Date", "ClearanceDate", "date", dict(align="center")),
         ("Storage Locaction", "StorageLoc", "combo", dict(options=L.storage_locations, limit=True)),
         ("MPC GR#", "MPCGRN", "text", {}),
         ("MPC GR Date", "MPCGRDate", "date", dict(align="center")),
         ("GR Remarks", "GRRemarks", "text", {}),
         ("Delivered On", "DeliveredOn", "date", dict(color=RED, align="center")),
         ("Delivered To", "DeliveredTo", "combo", dict(options=L.customers, limit=True, color=RED)),
         ("Delivered Plant", "DeliveredToPlant", "combo", dict(options=customer_plants, color=RED)),
         ("Delivered PO#", "DeliveredPO", "combo", dict(options=customer_po_with_product, limit=True, color=RED)),
         ("Delivered PO Item#", "DeliveredPOItem", "text", dict(color=RED)),
         ("Delivered SO#", "DeliveredSO", "text", dict(color=RED))]
    C = [("SAP DN#", "SAPDNNo", "text", {}),
         ("MPC Inv#", "InvNo", "text", {}),
         ("MPC Inv Date", "InvDate", "date", dict(align="center")),
         ("Detention Inv#", "DetentionInv", "text", {}),
         ("Submitting", "DetentionInvSubmitted", "check", {}),
         ("Comm'n Inv Value", "CommissionActualInvValue", "text", dict(fmt="standard")),
         ("Comm'n Inv#", "CommissionActualInv", "text", {}),
         ("Submitting", "CommissionInvSubmitted", "check", {}),
         ("Service Inv#", "ServiceInv", "text", {}),
         ("Submitting", "ServiceInvSubmitted", "check", {}),
         ("Customer GR#", "CusGR", "text", {}),
         ("Date of Arrival at Port", "DateofArrivaltoPort", "date", {}),
         ("Empty Pick Notified", "EmptyPickNotified", "date", dict(color=PURPLE, align="center")),
         ("Empty Pick Date", "EmptyPickDate", "date", dict(color=PURPLE)),
         ("Empty Return Date", "EmptyReturnDate", "date", dict(color=PURPLE)),
         ("EIR#", "EIRNo", "text", {}),
         ("Returning Terminal", "ReturnTerminal", "combo", dict(options=L.return_terminals, limit=True)),
         ("Return Complete", "ReturnIsDone", "check", {})]
    out = []
    tab = 0
    for cols, lx, vx, lw in ((A, FA_L, FA_V, 104), (B, FB_L, FB_V, 140), (C, FC_L, FC_V, 140)):
        for i, (label, field, kind, kw) in enumerate(cols):
            out.append(lab(label, lx, i, lw))
            kw = dict(kw)
            if kind == "check":
                c = dict(type="check", field=field, x=vx, y=ROWS_Y[i] + 3, w=16, h=16, tab=tab)
                if locked:
                    c.update(locked=True, unlockable=True)
            else:
                c = v(field, vx, i, kind, tab=None if kw.get("locked") else tab, **kw)
            out.append(c)
            tab += 1
    return out


def _full(locked):
    ctl = [dict(sec="header", type="label", text="Shipment File Full Details", x=8, y=4, w=420, h=32, style=TITLE)]
    ctl += _full_controls(locked)
    if locked:
        ctl.append(dict(type="button", caption="Edit", cls="blue", x=768, y=488, w=96, h=38, action={"do": "unlock"}))
    ctl += [
        dict(type="button", icon="master_FindBtn", cls="blue", x=871, y=488, w=38, h=38, tip="Find Record", action={"do": "find"}),
        dict(type="button", icon="close_form", cls="blue", x=916, y=488, w=38, h=38, tip="Close Form", action={"do": "close"}),
    ]
    return ctl


_full_common = dict(model=SF, width=968, header=dict(h=36, bg=BLUE_HEAD), detail=dict(h=540, bg=DETAIL_BG),
                    open_at="last", before_save=sf_line_before_save)
form("sf_full_details_locked", title="SF", locked_mode=True, controls=_full(True), **_full_common)
form("sf_full_details", title="SF", controls=_full(False), **_full_common)
