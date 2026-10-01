"""Main Menu box "Purchase Orders" — spec access_spec/1_purchase_orders.md.

Screens: New PO, Copy PO (New PO form), Updation of ETD/ETA and Pay requests, Add Import Permit,
reports Incoming Shipments / Payments Required / Cleared Shipments / Active Permits, and three Outlook drafts.
Decisions applied (DECISIONS.md): B1 Cleared/Canceled lines left out of Pending Payments, B2 25-75 term,
B3 next item number on "Add new item", bug 5 unit-price symbol follows currency, bug 8 permit list.
"""
from datetime import date, datetime

from sqlalchemy import func, or_

from extensions import db
from models import Permits, Products, ShipmentsStatus
from screens_def import lookups as L
from services import fmt
from services import settings
from services.screens import ScreenError, eml, form, grid, report

# Real values live in the database (Admin > Settings); the code repository is public.
settings.default("po_supplier_cc", "", "Cc: of the 'Send to Supplier' PO e-mail")

SS = ShipmentsStatus

# ── shared rules ──────────────────────────────────────────────────────

# Payment-term split: (1st payment share, 2nd payment share). Access query expression "Required Amount"
# plus 25-75 (decision B2).
SPLITS = {"20-80": (0.2, 0.8), "25-75": (0.25, 0.75), "30-70": (0.3, 0.7), "50-50": (0.5, 0.5), "Advance": (1.0, None)}


def required_amount(rec):
    total = (float(rec.get("Qty") or 0) * float(rec.get("UnitPrice") or 0))
    split = SPLITS.get(rec.get("PayTerm") or "")
    if not split:
        return None
    if rec.get("FirstPayment") == "Required":
        return total * split[0]
    if rec.get("SecondPayment") == "Required":
        return total * split[1] if split[1] is not None else None
    return None


def money(v, cur):
    """Unit price with the line's own currency (Access always showed '$': bug 5)."""
    if v is None:
        return ""
    sym = {"USD": "$", "EUR": "€", "SAR": "SAR "}.get(cur or "", "")
    return f"{sym}{float(v):,.2f}" if v >= 0 else f"({sym}{-float(v):,.2f})"


def active_permits(params=None):
    """ActivePermitsQuery: permits not expired with Remaining = Qty − Σ PO line Qty (Ordered/Incoming/Cleared) > 0."""
    used = dict(db.session.query(SS.PermitNo, func.sum(SS.Qty))
                .filter(SS.Status.in_(["Ordered", "Incoming", "Cleared"])).group_by(SS.PermitNo).all())
    by_status = {}
    for pn, st, q in (db.session.query(SS.PermitNo, SS.Status, func.sum(SS.Qty))
                      .filter(SS.Status.in_(["Ordered", "Incoming", "Cleared"])).group_by(SS.PermitNo, SS.Status)):
        by_status.setdefault(pn, {})[st] = float(q or 0)
    out = []
    for p in Permits.query.order_by(Permits.ProductName, Permits.ID).all():
        remaining = float(p.Qty or 0) - float(used.get(p.PermitNo) or 0)
        if remaining > 0 and (p.ExpiryDate is None or p.ExpiryDate > date.today()):
            st = by_status.get(p.PermitNo, {})
            out.append(dict(p=p, remaining=remaining, ordered=st.get("Ordered"), incoming=st.get("Incoming"),
                            cleared=st.get("Cleared")))
    return out


def active_permit_options(params=None):
    return [[a["p"].PermitNo, a["p"].ProductName or ""] for a in active_permits()]


def sap_name(product):
    p = Products.query.filter_by(ProductName=product).first() if product else None
    return p.SAPName if p else None


def days(a, b):
    return (a - b).days if a and b else None


# ── 1. New PO ─────────────────────────────────────────────────────────

def _validate_permit(row, typed, params, merged):
    """Access LimitToList on Permit#: an existing line may keep its permit; a new choice must be an active permit."""
    pn = typed.get("PermitNo")
    if pn and (row is None or row.PermitNo != pn):
        if pn not in {o[0] for o in active_permit_options()}:
            raise ScreenError("The text you entered isn't an item in the list.\n\n"
                              "Select an item from the list, or enter text that matches one of the listed items.")



LBL = "font:bold 11pt Calibri;color:#666666"


def _l(text, y):
    return dict(type="label", text=text, x=16, y=y, w=128, h=21, style=LBL)


form(
    "new_po", title="New PO", model=SS, width=368,
    header=dict(h=35, bg="#70AD47"), detail=dict(h=420, bg="#E2F0D9"),
    open_at="new", before_save=_validate_permit,
    required={"UOM": "ShipmentsStatus.UOM", "Status": "ShipmentsStatus.Status"},
    calc=lambda r, p: {"TotalAmount": (float(r.get("Qty") or 0) * float(r.get("UnitPrice") or 0)),
                       "LT": days(r.get("ETA"), r.get("ETD")), "SAPCode": sap_name(r.get("Product")),
                       "UnitPriceShown": money(r.get("UnitPrice"), r.get("ACurr"))},
    controls=[
        dict(sec="header", type="label", text="New PO", x=17, y=0, w=119, h=35,
             style="font:bold italic 20pt 'Times New Roman';color:#F2F2F2"),
        _l("MPC PO#", 8), dict(type="text", field="MPCPONo", x=148, y=8, w=219, h=21, tab=0),
        _l("Supplier", 32), dict(type="combo", field="Supplier", x=148, y=32, w=219, h=21, options=L.suppliers, limit=True, color="#222A35", tab=1),
        _l("Product", 57), dict(type="combo", field="Product", x=148, y=57, w=219, h=20, options=L.products, limit=True, tab=2),
        _l("Qty (kg)", 80), dict(type="text", field="Qty", fmt="standard", x=148, y=80, w=127, h=21, align="right", tab=3),
        dict(type="combo", field="UOM", x=280, y=80, w=88, h=21, options=L.uoms, limit=True, tab=4),
        _l("Unit Price", 105), dict(type="text", field="UnitPrice", fmt="standard", x=148, y=105, w=127, h=21, align="right", tab=5),
        dict(type="combo", field="ACurr", x=280, y=105, w=88, h=21, options=L.currencies, limit=True, tab=6),
        _l("Total Amount", 129), dict(type="calc", name="TotalAmount", fmt="standard", x=148, y=129, w=219, h=20, align="right", bg="#E7E6E6"),
        _l("ETD", 153), dict(type="date", field="ETD", x=148, y=153, w=97, h=21, tab=7),
        _l("ETA", 177), dict(type="date", field="ETA", x=148, y=177, w=97, h=21, tab=8),
        dict(type="label", text="L.T.", x=256, y=176, w=30, h=21, style=LBL),
        dict(type="calc", name="LT", x=287, y=176, w=80, h=20, bg="#E7E6E6"),
        _l("POD", 202), dict(type="combo", field="POD", x=148, y=202, w=219, h=21, options=L.ports, limit=True, tab=9),
        _l("Payment Terms", 226), dict(type="combo", field="PayTerm", x=148, y=226, w=219, h=21, options=L.pay_terms, limit=True, tab=10),
        _l("1st Payment Req.", 250), dict(type="select", field="FirstPayment", x=148, y=250, w=219, h=21, options=L.PAYMENT_STATES, limit=True, tab=11),
        _l("2nd Payment Req.", 275), dict(type="select", field="SecondPayment", x=148, y=275, w=219, h=21, options=L.PAYMENT_STATES, limit=True, tab=12),
        _l("Status", 300), dict(type="combo", field="Status", x=148, y=300, w=219, h=20, options=L.statuses, limit=True, tab=13),
        _l("Permit#", 324), dict(type="combo", field="PermitNo", x=148, y=324, w=219, h=20, options=active_permit_options, limit=False, tab=14),
        dict(type="button", caption="New PO", cls="green", x=16, y=356, w=68, h=27, action={"do": "new"}),
        dict(type="button", caption="Add more items", cls="green", x=92, y=356, w=104, h=27,
             action={"do": "open", "save": True, "url": "/g/copy_po_new?MPCPONo={MPCPONo}", "title": "Copy PO1", "w": 834, "h": 605}),
        dict(type="button", icon="del_record", cls="green", x=284, y=356, w=38, h=27, tip="Delete PO", action={"do": "delete"}),
        dict(type="button", icon="close_form", cls="green", x=328, y=356, w=38, h=27, tip="Close Form", action={"do": "close"}),
        dict(type="button", caption="Send to Supplier", cls="green", x=16, y=388, w=108, h=27,
             action={"do": "eml", "url": "/e/po_supplier?id={_id}", "save": True}),
        dict(type="label", text="SAP Code:", x=152, y=392, w=68, h=21, style="font:11pt Calibri;color:#666666"),
        dict(type="calc", name="SAPCode", x=220, y=392, w=146, h=21, bg="#E7E6E6"),
    ],
)


def _po_supplier_email(params):
    row = db.session.get(SS, int(params.get("id") or 0))
    if row is None:
        raise ScreenError("Save the PO first.")
    qty = fmt.standard(row.Qty)
    return dict(
        to="", cc=settings.get("po_supplier_cc"),
        subject=f"MPC PO# {row.MPCPONo or ''} - {row.Product or ''} - {qty} {row.UOM or ''}",
        html=(f"Dear Vendor,<P>Please find attached herewith the MPC purchase order no. {row.MPCPONo or ''} for {qty} "
              f"of {row.Product or ''}.<P>Kindly confirm the acknowledgment of order receipt.<P>Regards,<br/>"
              f"Modern Petrochemicals Co."),
    )


eml("po_supplier", build=_po_supplier_email)


# ── 2. Copy PO (New PO form) — add more line items ────────────────────

def _next_item(src, vals, params):
    """B3: the copied line gets the next item number of its PO (Access copied it unchanged)."""
    items = [r[0] for r in db.session.query(SS.ItemNo).filter(SS.MPCPONo == src.MPCPONo)]
    nums = [int(i) for i in items if (i or "").strip().isdigit()]
    vals["ItemNo"] = str(max(nums) + 1 if nums else 1)
    return vals


H = "font:bold 11pt Calibri"
grid(
    "copy_po_new", title="Copy PO1", model=SS, width=1824, win=(834, 605), row_h=24, copy=True,
    alt_bg="#F2F2F2",
    query=lambda p: SS.query.filter(SS.MPCPONo == p.get("MPCPONo", "")).order_by(SS.ID),
    before_copy=_next_item,
    copy_fields=["MPCPONo", "ItemNo", "EntryDate", "Supplier", "Product", "Qty", "UOM", "UnitPrice", "ACurr", "ETD",
                 "ETA", "POD", "PayTerm", "FirstPayment", "SecondPayment", "Status", "PermitNo"],
    required={"UOM": "ShipmentsStatus.UOM", "Status": "ShipmentsStatus.Status"},
    header=dict(h=70, bg="#D6DCE5", col_y=48, label_style=H),
    columns=[
        dict(sec="header", type="label", text="Copy PO", x=4, y=4, w=144, h=34,
             style="font:bold italic 20pt 'Times New Roman';color:#7F7F7F"),
        dict(sec="header", type="button", caption="Add new item", cls="gray", x=180, y=8, w=106, h=27, action={"do": "copy"}),
        dict(sec="header", type="button", caption="Delete Item", cls="gray", x=296, y=8, w=106, h=27, action={"do": "delete"}),
        dict(label="MPC PO No.", type="text", field="MPCPONo", x=4, y=2, w=96, h=20),
        dict(label="Item#", type="text", field="ItemNo", x=105, y=2, w=55, h=20, bold=True, color="#BA1419"),
        dict(label="EntryDate", type="date", field="EntryDate", x=165, y=2, w=96, h=20),
        dict(label="Supplier", type="combo", field="Supplier", x=266, y=2, w=96, h=20, options=L.suppliers, limit=True),
        dict(label="Product", type="combo", field="Product", x=366, y=2, w=96, h=20, options=L.products, limit=True),
        dict(label="Qty", type="text", field="Qty", fmt="standard", x=467, y=2, w=96, h=20, bold=True, color="#BA1419", align="right"),
        dict(label="UOM", type="combo", field="UOM", x=568, y=2, w=45, h=20, options=L.uoms, limit=True),
        dict(label="Unit Price", type="text", field="UnitPrice", fmt="standard", x=618, y=2, w=96, h=20, align="right"),
        dict(label="Currency", type="combo", field="ACurr", x=718, y=2, w=58, h=20, options=L.currencies, limit=True),
        dict(label="Total Amount", type="text", field="TotalAmount", fmt="standard", x=782, y=2, w=96, h=20, locked=True, align="right"),
        dict(label="ETD", type="date", field="ETD", x=882, y=2, w=96, h=20),
        dict(label="ETA", type="date", field="ETA", x=983, y=2, w=96, h=20),
        dict(label="POD", type="combo", field="POD", x=1084, y=2, w=96, h=20, options=L.ports),
        dict(label="PayTerm", type="combo", field="PayTerm", x=1185, y=2, w=96, h=20, options=L.pay_terms),
        dict(label="1stPayment", type="combo", field="FirstPayment", x=1286, y=2, w=96, h=20, options=L.PAYMENT_STATES),
        dict(label="2ndPayment", type="combo", field="SecondPayment", x=1386, y=2, w=96, h=20, options=L.PAYMENT_STATES),
        dict(label="PayType", type="text", field="PayType", x=1487, y=2, w=96, h=20, locked=True),
        dict(label="Status", type="combo", field="Status", x=1588, y=2, w=96, h=20, options=L.statuses),
        dict(label="PermitNo", type="combo", field="PermitNo", x=1689, y=2, w=130, h=20, options=active_permit_options),
    ],
)


# ── 3. Updation of ETD, ETA and Pay requests ("Shipments Status") ─────

def _eta_after(rec, params, row):
    """ETA AfterUpdate: ETA entered -> Incoming, ETA cleared -> Ordered."""
    return {"updates": {"Status": "Incoming" if rec.get("ETA") else "Ordered"}}


def _updation_query(p):
    eta_null = SS.ETA.is_(None)
    etd_null = SS.ETD.is_(None)
    return (SS.query.filter(SS.Status != "Cleared", SS.Status != "Canceled")
            .order_by(eta_null, SS.ETA, etd_null, SS.ETD, SS.ID))


GREY = "#E7E6E6"
grid(
    "updation_eta", title="Shipments Status", model=SS, width=1548, win=(1521, 809), row_h=28,
    query=_updation_query, allow_delete=True,
    hooks={"eta": _eta_after},
    calc=lambda r, p: {"DTA": days(r.get("ETA"), date.today())},
    header=dict(h=26, bg="#D6DCE5", col_y=4, label_style="font:11pt Calibri"),
    nav_w=1521,
    columns=[
        dict(label="MPC PO No", type="text", field="MPCPONo", x=13, y=4, w=79, h=22, locked=True, bg=GREY),
        dict(label="LI", type="text", field="ItemNo", x=96, y=4, w=25, h=22, locked=True, bg=GREY, align="center"),
        dict(label="Supplier", type="text", field="Supplier", x=125, y=4, w=115, h=22, locked=True, bg=GREY, color="#222A35"),
        dict(label="Product", type="text", field="Product", x=244, y=4, w=160, h=22, locked=True, bg=GREY),
        dict(label="Qty", type="text", field="Qty", fmt="standard", x=408, y=4, w=92, h=22, locked=True, bg=GREY, align="right"),
        dict(label="UP", type="text", field="UnitPrice", fmt="standard", x=504, y=4, w=44, h=22, bg=GREY),
        dict(label="Pay. Terms", type="text", field="PayTerm", x=552, y=4, w=72, h=22, locked=True, bg=GREY),
        dict(label="ETD", type="date", field="ETD", x=628, y=4, w=84, h=22, align="center"),
        dict(label="ETA", type="date", field="ETA", x=716, y=4, w=80, h=22, align="center", after="eta"),
        dict(label="DTA", type="calc", name="DTA", x=800, y=4, w=37, h=22, align="center",
             cond=[{"op": "between", "a": 0, "b": 15, "style": "bold"},
                   {"op": "lt", "a": 0, "style": "bold;color:#BA1419"}]),
        dict(label="POD", type="text", field="POD", x=841, y=4, w=37, h=22, bg=GREY),
        dict(label="S/F#", type="text", field="SFNo", x=882, y=4, w=68, h=22, locked=True, bg=GREY, bold=True, align="center"),
        dict(label="Docs T.No", type="text", field="DocsTrackingNo", x=954, y=4, w=85, h=22),
        dict(label="Clearance Status", type="combo", field="ClearanceStatus", x=1043, y=4, w=138, h=22, options=L.clearance_statuses),
        dict(label="Status", type="combo", field="Status", x=1185, y=4, w=84, h=22, options=L.statuses, limit=True,
             cond=[{"op": "eq", "a": "Ordered", "style": "color:#2F3699"}, {"op": "eq", "a": "Incoming", "style": "color:#BA1419"}]),
        dict(label="1st Payment", type="select", field="FirstPayment", x=1273, y=4, w=84, h=22, options=L.PAYMENT_STATES, limit=True,
             cond=[{"op": "eq", "a": "Required", "style": "bold"}]),
        dict(label="2nd Payment", type="select", field="SecondPayment", x=1361, y=4, w=84, h=22, options=L.PAYMENT_STATES, limit=True,
             cond=[{"op": "eq", "a": "Required", "style": "bold"}]),
        dict(label="Request", type="button", caption="Send e-mail", cls="gray", x=1449, y=4, w=92, h=22,
             action={"do": "eml", "url": "/e/payment_request?id={_id}", "save": True}),
    ],
)

PHRASES = {"20-80": ("20%", "80%"), "25-75": ("25%", "75%"), "30-70": ("30%", "70%"), "50-50": ("50%", "50%")}


def _payment_request_email(params):
    row = db.session.get(SS, int(params.get("id") or 0))
    if row is None:
        raise ScreenError("The record was deleted by another user.")
    term = row.PayTerm or ""
    first = row.FirstPayment == "Required"
    second = not first and row.SecondPayment == "Required"
    phrase = ""
    if first or second:
        if term in PHRASES:
            phrase = f"Please arrange to transfer {PHRASES[term][0 if first else 1]} payment amount"
        elif term == "Advance":
            phrase = "Please arrange to transfer TOTAL payment amount"
        elif term in ("LC 90 Days", "LC 60 Days"):
            phrase = "Please arrange for the LC document"
    amount = required_amount({"Qty": row.Qty, "UnitPrice": row.UnitPrice, "PayTerm": term,
                              "FirstPayment": row.FirstPayment, "SecondPayment": row.SecondPayment})
    amount_line = "" if term.startswith("LC ") else f"The required amount is {row.ACurr or ''} {fmt.standard(amount)}<P>"
    return dict(
        to=L.group_emails("PayReqTo"), cc=L.group_emails("PayReqCc"),
        subject=f"Payment Request - PO# {row.MPCPONo or ''}",
        html=f"Dear Accounting Officer, <P>{phrase} of PO# {row.MPCPONo or ''} Item# {row.ItemNo or ''}.<P>{amount_line}Kind regards,",
    )


eml("payment_request", build=_payment_request_email)


# ── 4. Add Import Permit ──────────────────────────────────────────────

PL = "font:bold 11pt Calibri"


def _permit_before_save(row, typed, params, merged):
    """Duty Percent: '5' means 5% (Access needed 0.05 or 5%)."""
    d = typed.get("DutyPercent")
    if d is not None and d > 1:
        typed["DutyPercent"] = d / 100


form(
    "add_permit", title="Add New PermitAdd NewPermit", model=Permits, width=340, before_save=_permit_before_save,
    header=dict(h=36, bg="#AFABAB"), detail=dict(h=284, bg="#E7E6E6"),
    required={"PermitNo": "Permits.PermitNo"},
    controls=[
        dict(sec="header", type="label", text="Add New Permit", x=8, y=4, w=180, h=28,
             style="font:bold italic 16pt 'Times New Roman';color:#fff"),
        dict(sec="header", type="button", caption="See All Active Permits", cls="gray", x=188, y=8, w=148, h=20, tip="Open Report",
             action={"do": "open", "save": True, "url": "/r/rpt_active_permits", "title": "Active Permits", "w": 1180, "h": 820, "close_self": True}),
        dict(type="label", text="ID", x=12, y=8, w=132, h=21, style=PL),
        dict(type="text", field="ID", x=148, y=8, w=188, h=21, locked=True, bg="#F2F2F2"),
        dict(type="label", text="Permit No", x=12, y=32, w=132, h=21, style=PL),
        dict(type="text", field="PermitNo", x=148, y=32, w=188, h=21, tab=0),
        dict(type="label", text="Product Name", x=12, y=57, w=132, h=21, style=PL),
        dict(type="combo", field="ProductName", x=148, y=57, w=188, h=21, options=L.products, limit=True, tab=1),
        dict(type="label", text="HS Code", x=12, y=82, w=132, h=21, style=PL),
        dict(type="text", field="HSCode", x=148, y=82, w=188, h=21, tab=2),
        dict(type="label", text="Name in Customs", x=12, y=107, w=132, h=21, style=PL),
        dict(type="text", field="NameinCustoms", x=148, y=107, w=188, h=21, tab=3),
        dict(type="label", text="PermitRequirement", x=12, y=132, w=132, h=21, style=PL),
        dict(type="combo", field="PermitRequirement", x=148, y=132, w=188, h=21, options=L.permit_reqs, limit=True, tab=4),
        dict(type="label", text="Duty Percent", x=12, y=156, w=132, h=21, style=PL),
        dict(type="text", field="DutyPercent", fmt="percent", x=148, y=156, w=188, h=21, tab=5,
             tip="Type 5% (or 0.05) for 5 percent"),
        dict(type="label", text="Permit Quantity", x=12, y=181, w=132, h=21, style=PL),
        dict(type="text", field="Qty", fmt="standard", x=148, y=181, w=188, h=21, align="right", tab=6),
        dict(type="label", text="Expiry Date", x=12, y=206, w=132, h=21, style=PL),
        dict(type="date", field="ExpiryDate", x=148, y=206, w=188, h=21, tab=7),
        dict(type="button", caption="New", cls="gray", x=12, y=244, w=52, h=27, action={"do": "new"}),
        dict(type="button", caption="Delete", cls="gray", x=68, y=244, w=52, h=27, action={"do": "delete"}),
        dict(type="button", icon="master_FindBtn", cls="gray", x=144, y=244, w=36, h=27, tip="Find Record", action={"do": "find"}),
        dict(type="button", icon="4d2a44da_envelope", cls="gray", x=184, y=244, w=36, h=27, tip="Email permit request",
             action={"do": "eml", "url": "/e/permit_request?id={_id}", "save": True,
                     "check": "An error was occurred, please check if there is info missing."}),
        dict(type="button", caption="Save and Exit", cls="gray", x=244, y=244, w=92, h=27, tip="Close Form", action={"do": "close"}),
    ],
)




def _permit_email(params):
    p = db.session.get(Permits, int(params.get("id") or 0))
    if p is None:
        raise ScreenError("An error was occurred, please check if there is info missing.")
    ind = "&emsp;&emsp;"
    return dict(
        to=L.group_emails("Permit"), cc=L.group_emails("Logistics"),
        subject=f"Import Permit Request - {p.ProductName or ''}",
        html=(f"Dear Ali,<br/><br/>Please apply for an import permit of below details.<br/><br/>"
              f"{ind}<b>Product: </b>{p.ProductName or ''}<br/>"
              f"{ind}<b>HS Code: </b>{p.HSCode or ''}<br/>"
              f"{ind}<b>Quantity: </b>{fmt.standard(p.Qty)}<br/>"
              f"{ind}<b>Permit Requirement: </b>{p.PermitRequirement or ''}<br/>"
              f"{ind}<b>Duty Percent: </b>{fmt.percent(p.DutyPercent)}<br/><br/>"
              f"Best regards,<br/>Logistics Department<br/>Modern Petrochemicals Co."),
    )


eml("permit_request", build=_permit_email)


# ── Reports ───────────────────────────────────────────────────────────

def _incoming(params):
    rows = SS.query.filter(SS.Status == "Incoming").order_by(SS.ETA.is_(None), SS.ETA).all()
    today = date.today()
    return {"rows": rows, "dta": lambda r: days(r.ETA, today), "now": datetime.now()}


report("rpt_incoming", title="Incoming Shipments Report", template="reports/po_incoming.html", data=_incoming)


def _payments(params):
    # B1: lines already Cleared (or Canceled) are left out — nobody follows up their payment.
    rows = (SS.query.filter(or_(SS.FirstPayment == "Required", SS.SecondPayment == "Required"))
            .filter(SS.Status.notin_(["Cleared", "Canceled"]))
            .order_by(SS.ETA.is_(None), SS.ETA, SS.MPCPONo, SS.ItemNo).all())
    groups = []
    for pay_type in ("Balance", "Advance"):           # PayType descending
        lines = [r for r in rows if r.PayType == pay_type]
        if not lines:
            continue
        curs = []
        for cur in sorted({r.ACurr or "" for r in lines}):
            cl = [r for r in lines if (r.ACurr or "") == cur]
            amounts = [_req(r) for r in cl]
            curs.append(dict(cur=cur, rows=list(zip(cl, amounts)), total=sum(a for a in amounts if a)))
        groups.append(dict(pay_type=pay_type, curs=curs))
    grand = {}
    for r in rows:
        a = _req(r)
        grand[r.ACurr or ""] = grand.get(r.ACurr or "", 0) + (a or 0)
    return {"groups": groups, "grand": sorted(grand.items()), "now": datetime.now()}


def _req(r):
    return required_amount({"Qty": r.Qty, "UnitPrice": r.UnitPrice, "PayTerm": r.PayTerm,
                            "FirstPayment": r.FirstPayment, "SecondPayment": r.SecondPayment})


report("rpt_payments", title="Payments Required", template="reports/po_payments.html", data=_payments)


def _cleared(params):
    rows = (SS.query.filter(SS.Status == "Cleared")
            .order_by(SS.SFNo.desc().nulls_last(), SS.ETA.is_(None), SS.ETA, SS.ETD.is_(None), SS.ETD, SS.ID).all())
    return {"rows": rows, "now": datetime.now()}


report("rpt_cleared", title="ClearedShipmentsReport", template="reports/po_cleared.html", data=_cleared)


def _active_permits(params):
    return {"rows": active_permits(), "now": datetime.now()}


report("rpt_active_permits", title="Active Permits", template="reports/po_active_permits.html", data=_active_permits)
