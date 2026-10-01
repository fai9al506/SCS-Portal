"""Main Menu box "Customers PO's" — spec access_spec/4_customer_po_and_invoices.md, section A.

Screens: Add new Customer PO (AddNewCusPO), Add PO Items (AddPOItems), Customers PO Report dialog (CusPORpt)
+ reports CusPOBalance / CusPOBalanceActive, Inquiry of Single PO (DeliveryReportofSinglePO), Delivery Schedule
dialog + report.

Balance rule (Access query CustomersPOConsumed): Delivered Qty = Σ SF.SFQty of the SF rows whose
(DeliveredPO, DeliveredPOItem) = (CusPONo, ItemNo); Balance Qty = POQty − Delivered Qty; active = Balance > 0.
Decisions: B3 spirit — "Add new item" clones the PO header from item 1 and takes the next item number;
bug 11 — the Customers PO Report dialog stays open after "You have to enter product!".
"""
from datetime import datetime

from sqlalchemy import false, func

from extensions import db
from models import Customers, CustomersPO, Products, SF
from screens_def import lookups as L
from services import fmt
from services.screens import form, grid, report

CP = CustomersPO


# ── shared rules ──────────────────────────────────────────────────────

def delivered_map(po_nos=None):
    """{(CusPONo, ItemNo): Σ SFQty} of SF rows delivered against a customer PO item."""
    q = (db.session.query(SF.DeliveredPO, SF.DeliveredPOItem, func.sum(SF.SFQty))
         .filter(SF.DeliveredPO.isnot(None)).group_by(SF.DeliveredPO, SF.DeliveredPOItem))
    if po_nos is not None:
        q = q.filter(SF.DeliveredPO.in_(list(po_nos)))
    return {(po, item): float(s or 0) for po, item, s in q.all()}


def balances(q):
    """Customer PO lines of query q with (row, delivered or None, balance)."""
    rows = q.all()
    dm = delivered_map({r.CusPONo for r in rows})
    out = []
    for r in rows:
        dlv = dm.get((r.CusPONo, r.ItemNo))
        out.append((r, dlv, float(r.POQty or 0) - (dlv or 0)))
    return out


def unit_price_text(r):
    """Access: =[Curr] & " " & Format([UnitPrice],"Standard") & " /" & [PerUOM]."""
    return f"{(r.Curr + ' ') if r.Curr else ''}{fmt.standard(r.UnitPrice or 0)} /{r.PerUOM or ''}"


def cus_sap(name):
    c = Customers.query.filter_by(CusName=name).first() if name else None
    return c.SAPID if c else None


def prod_sap(name):
    p = Products.query.filter_by(ProductName=name).first() if name else None
    return p.SAPName if p else None


def contract_nos(p=None):
    from models import CustomerContracts
    return [r[0] for r in db.session.query(CustomerContracts.CusContractNo).order_by(CustomerContracts.CusContractNo)]


def _values(r):
    q, up, vat = float(r.get("POQty") or 0), float(r.get("UnitPrice") or 0), r.get("VAT")
    po_value = up * q
    vat_value = po_value * float(vat) if vat is not None else None
    return {"POValue": po_value, "VATValue": vat_value,
            "POValueWVAT": po_value + vat_value if vat_value is not None else None}


def _vat_before_save(row, typed, params, merged):
    """VAT %: '15' means 15% (Access needed 0.15 or 15%)."""
    v = typed.get("VAT")
    if v is not None and v > 1:
        typed["VAT"] = v / 100


# ── A1. Add new Customer PO (form AddNewCusPO, caption "CustomersPO") ──

LBL = "font:bold 11pt Calibri;color:#000"
GREY = "#E7E6E6"


def _l(text, y):
    return dict(type="label", text=text, x=20, y=y, w=111, h=21, style=LBL)


def _row(text, y, **ctl):
    return [_l(text, y), dict(x=136, y=y, w=190, h=21, color="#404040", **ctl)]


form(
    "add_new_cus_po", title="CustomersPO", model=CP, width=340, win=(346, 735),
    header=dict(h=36, bg="#4472C4"), detail=dict(h=636, bg="#DAE3F3"),
    open_at="last", before_save=_vat_before_save,
    query=lambda p: CP.query.order_by(CP.ID),
    required={"CusPONo": "CustomersPO.CusPONo", "PODate": "CustomersPO.PODate"},
    calc=lambda r, p: dict(_values(r), CusSAP=cus_sap(r.get("Affiliate")), ProdSAP=prod_sap(r.get("Product"))),
    controls=[
        dict(sec="header", type="label", text="New Customer PO", x=8, y=4, w=304, h=32,
             style="font:bold italic 16pt 'Times New Roman';color:#fff"),
        _l("PO #", 8), dict(type="text", field="CusPONo", x=136, y=8, w=144, h=21, tab=0),
        dict(type="text", field="ItemNo", x=285, y=8, w=41, h=21, locked=True, bg=GREY, align="center"),
        *_row("PO Issued To", 34, type="combo", field="POIssuedTo", options=L.po_issued_to, limit=True, tab=1),
        *_row("Product", 60, type="combo", field="Product", options=L.products, limit=True, tab=2),
        *_row("PO Date", 86, type="date", field="PODate", tab=3),
        *_row("Affiliate", 112, type="combo", field="Affiliate", options=L.customers, limit=True, tab=4),
        _l("SAP Code", 138), dict(type="calc", name="CusSAP", x=136, y=138, w=190, h=21, bg=GREY, color="#22B14C"),
        _l("PO Qty (KG)", 164), dict(type="text", field="POQty", fmt="standard", x=136, y=164, w=190, h=21,
                                     bold=True, color="#BA1419", align="right", tab=5),
        *_row("Delivery Terms", 190, type="combo", field="DeliveryTerms", options=L.delivery_terms, limit=True, tab=6),
        *_row("Payment Terms", 216, type="combo", field="PaymentTerms", options=L.pay_terms_cus, limit=True, tab=7),
        _l("Unit Price (/KG)", 242), dict(type="text", field="UnitPrice", fmt="standard", x=136, y=242, w=95, h=21,
                                          align="right", tab=8),
        dict(type="combo", field="Curr", x=235, y=242, w=91, h=21, options=L.currencies, limit=True, tab=9),
        *_row("UOM", 268, type="combo", field="PerUOM", options=L.uoms, limit=True, tab=10),
        *_row("VAT %", 294, type="text", field="VAT", fmt="percent", tab=11, tip="Type 15% (or 15) for 15 percent"),
        _l("VAT Value", 320), dict(type="calc", name="VATValue", fmt="standard", x=136, y=320, w=190, h=21, bg=GREY, align="right"),
        _l("PO Value", 346), dict(type="calc", name="POValue", fmt="standard", x=136, y=346, w=190, h=21, bg=GREY, align="right"),
        _l("PO Value Inc VAT", 372), dict(type="calc", name="POValueWVAT", fmt="standard", x=136, y=372, w=190, h=21,
                                          bg=GREY, align="right"),
        *_row("Packing", 398, type="combo", field="Packing", options=L.packing, limit=True, tab=12),
        *_row("Delivery Date", 424, type="date", field="DeliveryDate", tab=13),
        *_row("SO #", 450, type="text", field="SONo", tab=14),
        *_row("Contract #", 476, type="combo", field="ContractNo", options=contract_nos, limit=True, tab=15),
        *_row("Remarks", 502, type="text", field="Remarks", tab=16),
        dict(type="button", caption="Add more items", cls="blue", x=20, y=536, w=196, h=27, tab=17,
             action={"do": "open", "save": True, "url": "/g/add_po_items?CusPONo={CusPONo}", "title": "AddPOItems",
                     "w": 1119, "h": 820, "close_self": True}),
        dict(type="button", icon="close_form", cls="blue", x=286, y=536, w=38, h=27, tip="Close Form", tab=18,
             action={"do": "close"}),
        dict(type="button", caption="Add New PO", cls="blue", x=20, y=568, w=88, h=27, tab=19, action={"do": "new"}),
        dict(type="button", caption="Delete PO item", cls="blue", x=112, y=568, w=104, h=27, tab=20, action={"do": "delete"}),
        dict(type="button", icon="master_FindBtn", cls="blue", x=286, y=568, w=38, h=27, tip="Find Record", tab=21,
             action={"do": "find"}),
        dict(type="label", text="SAP Code:", x=96, y=604, w=66, h=21, style="font:11pt Calibri;color:#666666"),
        dict(type="calc", name="ProdSAP", x=164, y=604, w=160, h=21, bg=GREY),
    ],
)


# ── A2. Add PO Items (continuous form AddPOItems) ─────────────────────

HEADER_FIELDS = ["CusPONo", "POIssuedTo", "Product", "PODate", "Affiliate", "DeliveryTerms", "PaymentTerms", "Curr",
                 "UnitPrice", "PerUOM", "VAT", "Packing", "SONo", "ContractNo", "Remarks"]


def _clone_item(src, vals, params):
    """'Add new item': header copied from item 1 of the PO, next item number, qty/date from the selected line."""
    first = CP.query.filter(CP.CusPONo == src.CusPONo).order_by(CP.ItemNo, CP.ID).first() or src
    for f in HEADER_FIELDS:
        vals[f] = getattr(first, f)
    top = db.session.query(func.max(CP.ItemNo)).filter(CP.CusPONo == src.CusPONo).scalar() or 0
    vals["ItemNo"] = int(top) + 1
    vals["Closed"] = False
    return vals


TH = "font:bold 11pt 'Times New Roman';text-align:center;justify-content:center"
grid(
    "add_po_items", title="AddPOItems", model=CP, width=763, win=(1119, 820), row_h=28, copy=True,
    query=lambda p: CP.query.filter(CP.CusPONo == p.get("CusPONo", "")).order_by(CP.ID),
    before_copy=_clone_item, before_save=_vat_before_save,
    copy_fields=["CusPONo", "ItemNo", "Product", "POQty", "DeliveryDate", "Remarks"],
    required={"CusPONo": "CustomersPO.CusPONo", "PODate": "CustomersPO.PODate"},
    header=dict(h=70, bg="#D6DCE5", col_y=48, label_style=TH),
    columns=[
        dict(sec="header", type="label", text="Add PO Items", x=4, y=4, w=220, h=36,
             style="font:bold 20pt 'Times New Roman'"),
        dict(sec="header", type="button", caption="Add new item", cls="blue", x=240, y=8, w=110, h=27, action={"do": "copy"},
             tip="Adds the next item of this PO (header copied from item 1)"),
        dict(sec="header", type="button", caption="Delete Item", cls="blue", x=360, y=8, w=100, h=27, action={"do": "delete"}),
        dict(label="PO No", type="text", field="CusPONo", x=12, y=3, w=96, h=21, color="#404040", align="center"),
        dict(label="Product", type="combo", field="Product", x=112, y=3, w=96, h=21, options=L.products, limit=True,
             color="#222A35", align="center"),
        dict(label="Item No", type="text", field="ItemNo", x=212, y=3, w=59, h=21, bold=True, color="#BA1419", align="center"),
        dict(label="PO Item Qty", type="text", field="POQty", fmt="standard", x=275, y=3, w=105, h=21, bold=True,
             color="#BA1419", align="center"),
        dict(label="Delivery Date", type="date", field="DeliveryDate", x=384, y=3, w=97, h=21, bold=True,
             color="#BA1419", align="center"),
        dict(label="Remarks", type="text", field="Remarks", x=485, y=3, w=208, h=21, color="#404040",
             head_style="justify-content:flex-start"),
    ],
)


# ── A3. Customers PO Report dialog (CusPORpt) + A4 reports ────────────

DLG = "font:bold 11pt 'Times New Roman';justify-content:flex-end"
form(
    "cus_po_rpt", title="CusPORpt", model=CP, width=308, win=(324, 185), nav=False,
    detail=dict(h=145, bg="#FFFFFF"), query=lambda p: CP.query.filter(false()),
    allow_delete=False, scripts=["access/cpo.js"],
    calc=lambda r, p: {"ActiveOnly": True},
    controls=[
        dict(type="label", text="Product", x=12, y=12, w=80, h=21, style=DLG),
        dict(type="label", text="*", x=94, y=12, w=10, h=21, style="color:#ED1C24;font:bold 11pt Calibri"),
        dict(type="combo", name="Product", x=108, y=12, w=180, h=21, options=L.products, color="#222A35"),
        dict(type="label", text="Customer", x=26, y=44, w=66, h=21, style=DLG),
        dict(type="combo", name="Customer", x=108, y=44, w=180, h=20,
             options=lambda p: [r[0] for r in db.session.query(Customers.CusName).order_by(Customers.id)]),
        dict(type="check", name="ActiveOnly", x=108, y=78, w=14, h=14),
        dict(type="label", text="Active only", x=125, y=74, w=90, h=21, style="font:11pt Calibri"),
        dict(type="button", caption="Open Report", cls="gray", x=168, y=112, w=100, h=24,
             action={"do": "js", "fn": "cusPoRptOpen"}),
    ],
)


def _cus_po_balance(params, active):
    product, customer = (params.get("product") or "").strip(), (params.get("customer") or "").strip()
    q = CP.query
    if product:
        q = q.filter(CP.Product == product)
    if customer:
        q = q.filter(CP.Affiliate == customer)
    rows = balances(q.order_by(CP.PODate, CP.Affiliate, CP.CusPONo, CP.ItemNo))
    if active and (product or customer):
        rows = [x for x in rows if x[2] > 0]
    title_product = rows[0][0].Product if rows else product
    return {"rows": rows, "title_product": title_product or "", "now": datetime.now(), "price": unit_price_text}


report("rpt_cus_po_balance", title="CusPOBalance", template="reports/cpo_balance.html",
       data=lambda p: _cus_po_balance(p, False))
report("rpt_cus_po_balance_active", title="CusPOBalanceActive", template="reports/cpo_balance.html",
       data=lambda p: _cus_po_balance(p, True))


# ── A5/A6. Inquiry of Single PO (DeliveryReportofSinglePO) ────────────

def _single_po(params):
    po = (params.get("p") or "").strip()
    items = CP.query.filter(CP.CusPONo == po).order_by(CP.ItemNo, CP.ID).all()
    lines = []
    for it in items:
        sfs = (SF.query.filter(SF.DeliveredPO == it.CusPONo, SF.DeliveredPOItem == it.ItemNo)
               .order_by(SF.DeliveredOn.is_(None), SF.DeliveredOn, SF.UID).all())
        if sfs:
            lines += [(it, s) for s in sfs]
        else:
            lines.append((it, None))
    dm = delivered_map({po})
    blocks = {}
    for it in items:
        k = (it.Affiliate or "", it.Product or "", it.SONo or "", it.PerUOM or "")
        b = blocks.setdefault(k, dict(customer=k[0], product=k[1], so=k[2], uom=k[3], n_items=0, qty=0.0, delivered=0.0))
        b["n_items"] += 1
        b["qty"] += float(it.POQty or 0)
        b["delivered"] += dm.get((it.CusPONo, it.ItemNo), 0.0)
    contract = next((i.ContractNo for i in items if i.ContractNo), None)
    return {"po": po if items else "", "contract": contract, "lines": lines, "blocks": list(blocks.values()),
            "now": datetime.now()}


report("rpt_single_po", title="DeliveryReportofSinglePO", template="reports/cpo_single_po.html", data=_single_po)


# ── A7/A8. Delivery Schedule ──────────────────────────────────────────

form(
    "delivery_schedule", title="DeliverySchedule", model=CP, width=292, win=(308, 132), nav=False,
    detail=dict(h=92, bg="#FFFFFF"), query=lambda p: CP.query.filter(false()),
    allow_delete=False, scripts=["access/cpo.js"],
    controls=[
        dict(type="label", text="Product", x=12, y=12, w=80, h=21, style=DLG),
        dict(type="combo", name="Product", x=108, y=12, w=170, h=21, options=L.products, color="#222A35"),
        dict(type="button", caption="Open Report", cls="gray", x=168, y=56, w=100, h=24,
             action={"do": "js", "fn": "deliveryScheduleOpen"}),
    ],
)


def _delivery_schedule(params):
    product = (params.get("product") or "").strip()
    q = CP.query
    if product:
        q = q.filter(CP.Product == product)
    rows = [x for x in balances(q) if x[2] > 0]
    rows.sort(key=lambda x: ((x[0].Product or "").lower(), x[0].DeliveryDate is not None,
                             x[0].DeliveryDate or datetime.min.date()))
    groups = []
    for r in rows:
        if not groups or groups[-1]["product"] != (r[0].Product or ""):
            groups.append(dict(product=r[0].Product or "", rows=[], total=0.0))
        groups[-1]["rows"].append(r)
        groups[-1]["total"] += float(r[0].POQty or 0)
    return {"groups": groups, "now": datetime.now(), "price": unit_price_text}


report("rpt_delivery_schedule", title="Delivery Schedule", template="reports/cpo_delivery_schedule.html",
       data=_delivery_schedule)
