"""Main Menu box "Commission, Service, and Detention Invoices" — spec 4_customer_po_and_invoices.md, section B.

FCC Catalyst (Grace → Petro Rabigh): MPC invoices Grace a sales commission (USD per kg) and handling charges
(SAR per container). n-Heptane ISO-tanks: tank rental (detention) invoice per tank per day after free days,
plus the empty-tank return to the shipping line. Everything is tracked on SF rows (no invoice table).

Decisions: B6 — a shipment (S/F + Grace invoice) is "pending" when ALL its containers are delivered and its
invoice is not submitted; B7 — rates, bank details, PA# and Grace e-mail recipients are admin settings;
bug 7 — wrong captions fixed; bug 10 — tank chargeable days never below 0; bug 6 — commission value keeps decimals.
"""
from datetime import datetime

from sqlalchemy import func

from extensions import db
from models import SF
from screens_def import lookups as L
from services import fmt, settings
from services.screens import ScreenError, eml, grid, report

# ── settings (decision B7) ────────────────────────────────────────────
settings.default("fcc_commission_rate", 0.1263, "FCC Catalyst sales commission estimate, USD per kg delivered")
settings.default("fcc_handling_rate", 9300, "FCC Catalyst handling charges, SAR per container")
settings.default("fcc_handling_breakdown",
                 "Pull out from Jeddah Port: 600; Transportation to Rabigh: 1,800; Off-Loading: 2,300; "
                 "Empty Container Return to Shipping Line: 800; Delivery to Petro-Rabigh Refinery: 600; "
                 "Warehousing Cost: 3,200",
                 "Handling cost per container shown on the invoice description (lines separated by ;)")
settings.default("bank_usd", "", 'MPC USD bank account for FCC commission invoices (lines separated by ;)')
settings.default("bank_sar", "", 'MPC SAR bank account for FCC handling invoices (lines separated by ;)')
settings.default("fcc_pa_no", "", 'Grace FCC purchase agreement number (FCC invoice e-mail subjects)')
settings.default("grace_email_to", "", 'To: of the FCC commission/handling invoice e-mails')
settings.default("grace_email_cc", "", 'Cc: of the FCC commission/handling invoice e-mails')
settings.default("tank_rate_per_day", 55, "n-Heptane ISO-tank rental, USD per tank per day")
settings.default("tank_free_days", 10, "n-Heptane ISO-tank free days before rental is charged")

ERR = "An error was occurred, please check if there is info missing."


def _lines(key):
    return [x.strip() for x in settings.get(key).split(";") if x.strip()]


def is_fcc():
    return func.lower(SF.Product) == "fcc catalyst"


def is_heptane():
    return func.lower(SF.Product) == "n-heptane"


def _group_rows(sf_no, supplier_inv):
    q = SF.query.filter(is_fcc(), SF.SF == sf_no)
    q = q.filter(SF.SupplierInv == supplier_inv) if supplier_inv is not None else q.filter(SF.SupplierInv.is_(None))
    return q.all()


def _pending_reps(flag):
    """B6: one representative SF row (lowest unsubmitted UID) per FCC shipment (S/F + Grace invoice)
    whose containers are ALL delivered and whose invoice (flag) is not submitted on every row."""
    groups = {}
    for r in SF.query.filter(is_fcc()).order_by(SF.SF, SF.UID).all():
        groups.setdefault((r.SF, r.SupplierInv), []).append(r)
    reps = []
    for rows in groups.values():
        open_rows = [r for r in rows if not getattr(r, flag)]
        if open_rows and all(r.DeliveredOn is not None for r in rows):
            reps.append(open_rows[0].UID)
    return reps


# ── shared grid styles ────────────────────────────────────────────────
GREY = "#E7E6E6"
MAG = "#EA36DD"
PINK = "background:#DFA7A5;color:#000"
YELLOW = "background:#FFE699;color:#000"
HEAD = "font:bold 11pt Calibri;color:#fff;justify-content:center;text-align:center"
DESC = "display:none;font-size:8pt;white-space:pre;background:#fff;border:1px solid #a6a6a6"


def _ro(label, field, x, w, **kw):
    """Locked grey column (Access locked text box)."""
    return dict(label=label, type="text", field=field, x=x, y=4, w=w, h=22, locked=True, bg=GREY, **kw)


def _calc_col(label, name, x, w, **kw):
    return dict(label=label, type="calc", name=name, x=x, y=4, w=w, h=22, bg=GREY, **kw)


def _show_desc_button(x, h):
    return dict(sec="header", type="button", caption="Show Invoice(s) Description", cls="blue", x=x, y=8, w=184, h=20,
                action={"do": "js", "fn": "invShowDesc", "h": h})


# ── B1. FCC Commission Invoices (Pending) ─────────────────────────────

def _commission_calc(r, p):
    rows = [x for x in _group_rows(r.get("SF"), r.get("SupplierInv")) if not x.CommissionInvSubmitted]
    qty = sum(float(x.SFQty or 0) for x in rows)
    rate = settings.get("fcc_commission_rate", float)
    last = max((x.DeliveredOn for x in rows if x.DeliveredOn), default=None)
    desc = "\n".join([f"Grace Invoice# {r.get('SupplierInv') or ''}", "", "MPC (USD) Bank Account Details:", *_lines("bank_usd")])
    return {"Qty": qty, "LastDlv": last, "EstCom": rate * qty, "Desc": desc,
            "Containers": f"{len(rows)} of {len(rows)} delivered"}


grid(
    "fcc_commission_inv", title="FCC Catalyst Commission Invoices", model=SF, width=800, win=(872, 603), row_h=32,
    query=lambda p: SF.query.filter(SF.UID.in_(_pending_reps("CommissionInvSubmitted"))).order_by(SF.SF, SF.UID),
    allow_edit=False, allow_delete=False, calc=_commission_calc, scripts=["access/inv.js"],
    header=dict(h=67, bg="#4472C4", col_y=44, label_style=HEAD),
    footer=dict(h=26, bg="#8FAADC"), alt_bg="#DAE3F3", row_bg="#DAE3F3",
    columns=[
        dict(sec="header", type="label", text="FCC Catalyst Commission Invoices", x=4, y=4, w=340, h=32,
             style="font:bold italic 16pt 'Times New Roman';color:#fff"),
        _show_desc_button(388, 150),
        _ro("MPC S/F#", "SF", 4, 76, align="center"),
        _ro("Product", "Product", 84, 96, color="#222A35"),
        _calc_col("Quantity", "Qty", 186, 84, fmt="standard", align="right"),
        _ro("Grace Inv #", "SupplierInv", 275, 88, bold=True),
        _ro("Inv Date", "SupplierInvDate", 368, 92, align="center"),
        _ro("Grace SO#", "Remarks", 464, 84),
        _calc_col("Delivery Date", "LastDlv", 553, 95, align="center"),
        _calc_col("Est. Com. Value (USD)", "EstCom", 653, 139, fmt="standard", align="right", bold=True),
        dict(type="label", text="Invoice Description:", x=4, y=34, w=128, h=24, style="display:none;color:#3B3838"),
        dict(type="memo", name="Desc", x=136, y=34, w=360, h=107, locked=True, style=DESC),
        dict(type="button", caption="Update the Invoice Number/Submission", cls="blue", x=528, y=34, w=259, h=27,
             style="display:none",
             action={"do": "open", "url": "/g/fcc_commission_inv_update?SupplierInv={SupplierInv}",
                     "title": "FCC Catalyst Commission Invoices", "w": 1180, "h": 640, "close_self": True}),
        dict(sec="footer", type="label", text="Total Estimated Commission Value:", x=380, y=4, w=268, h=20,
             style="font:bold 11pt Calibri;color:#3B3838;justify-content:flex-end"),
        dict(sec="footer", type="calc", name="TotalCom", x=653, y=2, w=139, h=21, bg=GREY, bold=True, align="right"),
    ],
)


# ── B2. FCC Commission invoice update ─────────────────────────────────

grid(
    "fcc_commission_inv_update", title="FCC Catalyst Commission Invoices", model=SF, width=1145, win=(1180, 640),
    row_h=28, allow_delete=False,
    query=lambda p: (SF.query.filter(is_fcc(), SF.SupplierInv == p.get("SupplierInv", ""), SF.DeliveredOn.isnot(None))
                     .order_by(SF.UID)),
    header=dict(h=71, bg="#4472C4", col_y=48, label_style=HEAD), nav_w=1180,
    columns=[
        dict(sec="header", type="label", text="FCC Catalyst Commission Invoices", x=4, y=4, w=340, h=32,
             style="font:bold italic 16pt 'Times New Roman';color:#fff"),
        dict(sec="header", type="button", caption="Send the Invoice by e-mail", cls="blue", x=896, y=12, w=180, h=24,
             action={"do": "eml", "save": True, "url": "/e/fcc_commission_email?SupplierInv={SupplierInv}&SF={SF}"}),
        _ro("MPC S/F#", "SF", 4, 76, align="center"),
        _ro("Product", "Product", 84, 96),
        _ro("Quantity", "SFQty", 186, 84, fmt="standard", align="right"),
        _ro("Grace Inv #", "SupplierInv", 275, 88, bold=True),
        _ro("Inv Date", "SupplierInvDate", 368, 92, align="center"),
        _ro("Grace SO#", "Remarks", 464, 84),
        _ro("Delivery Date", "DeliveredOn", 553, 95, align="center"),
        _ro("Petro Rabigh PO#", "DeliveredPO", 653, 111),
        _ro("PO Item#", "DeliveredPOItem", 769, 64, align="center"),
        dict(label="Com. Inv Value", type="text", field="CommissionActualInvValue", fmt="standard", x=839, y=4, w=112,
             h=22, color=MAG, align="right", head_style=PINK),
        dict(label="Com. Actual Inv#", type="text", field="CommissionActualInv", x=956, y=4, w=112, h=22, color=MAG,
             head_style=PINK),
        dict(label="Submitted", type="check", field="CommissionInvSubmitted", x=1100, y=8, w=14, h=14, hx=1072, hw=70,
             head_style=PINK),
    ],
)


def _grace_email(subject, kind, params):
    inv, sf_no = (params.get("SupplierInv") or "").strip(), (params.get("SF") or "").strip()
    if not inv and not sf_no:
        raise ScreenError(ERR)
    ind = "&emsp;&emsp;"
    return dict(
        to=settings.get("grace_email_to"), cc=settings.get("grace_email_cc"), subject=subject,
        html=(f"Greetings,<br/><br/>Please find attached {kind} invoice for the following shipment details.<br/><br/>"
              f"{ind}<b>Grace Invoice# </b>{inv}<br/>{ind}<b>MPC S/F# </b>{sf_no}<br/><br/>"
              f"Best regards,<br/>Modern Petrochemicals Co."),
    )


eml("fcc_commission_email", build=lambda p: _grace_email(
    f"FCC PA# {settings.get('fcc_pa_no')} - Sales Commission Invoices", "commission", p))
eml("fcc_service_email", build=lambda p: _grace_email(
    f"FCC PA# {settings.get('fcc_pa_no')} - Handling Charges Invoice (S/F# {(p.get('SF') or '').strip()})", "handling", p))


# ── B3. FCC Commission Invoices Report (All) ──────────────────────────

def _fcc_report(params):
    rows = SF.query.filter(is_fcc()).all()
    out = []
    for submitted in (False, True):                    # Access sorts submitted descending: pending first
        part = [r for r in rows if bool(r.CommissionInvSubmitted) == submitted]
        if not part:
            continue
        invs = []
        for inv in sorted({r.SupplierInv or "" for r in part}):
            rr = sorted([r for r in part if (r.SupplierInv or "") == inv],
                        key=lambda r: (r.DeliveredOn is not None, r.DeliveredOn or datetime.min.date(), r.UID))
            invs.append(dict(inv=inv, rows=rr))
        out.append(dict(submitted=submitted, invs=invs))
    return {"groups": out, "now": datetime.now()}


report("rpt_fcc_commission", title="FCC Commission Report", template="reports/inv_fcc_commission.html",
       data=_fcc_report, portrait=True)


# ── B4. FCC Handling (service) Invoices (Pending) ─────────────────────

def _service_calc(r, p):
    rows = [x for x in _group_rows(r.get("SF"), r.get("SupplierInv")) if not x.ServiceInvSubmitted]
    n = sum(1 for x in rows if x.ContainerNo)
    rate = settings.get("fcc_handling_rate", float)
    last = max((x.DeliveredOn for x in rows if x.DeliveredOn), default=None)
    desc = "\n".join([f"Grace Invoice# {r.get('SupplierInv') or ''}", f"MPC S/F# {r.get('SF') or ''}", "",
                      "Handling Cost Per Container:", *_lines("fcc_handling_breakdown"), f"(Total: {rate:,.0f})", "",
                      "MPC (SAR) Bank Account Details:", *_lines("bank_sar")])
    return {"Containers": n, "LastDlv": last, "Rate": rate, "Total": n * rate, "Desc": desc}


grid(
    "fcc_service_inv", title="FCC Catalyst Service Invoices", model=SF, width=870, win=(1072, 591), row_h=33,
    query=lambda p: SF.query.filter(SF.UID.in_(_pending_reps("ServiceInvSubmitted"))).order_by(SF.SF, SF.UID),
    allow_edit=False, allow_delete=False, calc=_service_calc, scripts=["access/inv.js"],
    header=dict(h=67, bg="#4472C4", col_y=44, label_style=HEAD), alt_bg="#DAE3F3", row_bg="#DAE3F3",
    columns=[
        dict(sec="header", type="label", text="FCC Catalyst Service Invoices", x=4, y=4, w=340, h=32,
             style="font:bold italic 16pt 'Times New Roman';color:#fff"),
        _show_desc_button(388, 280),
        _ro("MPC S/F#", "SF", 4, 76, align="center"),
        _ro("Product", "Product", 84, 96, color="#222A35"),
        _calc_col("No. of Containers", "Containers", 186, 111, bold=True, align="center"),
        _ro("Grace Inv #", "SupplierInv", 302, 88),
        _ro("Inv Date", "SupplierInvDate", 395, 92, align="center"),
        _ro("Grace SO#", "Remarks", 492, 84),
        _calc_col("Delivery Date", "LastDlv", 580, 95, align="center"),
        _calc_col("Rate/FCL", "Rate", 680, 64, fmt="standard", align="right"),
        _calc_col("Total Value (SAR)", "Total", 750, 109, fmt="standard", align="right", bold=True),
        dict(type="label", text="Invoice Description:", x=4, y=35, w=128, h=24, style="display:none;color:#595959"),
        dict(type="memo", name="Desc", x=136, y=35, w=360, h=237, locked=True, style=DESC),
        dict(type="button", caption="Update the Invoice Number/Submission", cls="blue", x=544, y=35, w=259, h=27,
             style="display:none",
             action={"do": "open", "url": "/g/fcc_service_inv_update?SF={SF}", "title": "FCC Catalyst Service Invoices",
                     "w": 1180, "h": 640, "close_self": True}),
    ],
)


# ── B5. FCC Handling invoice update ───────────────────────────────────

def _int_param(p, k):
    try:
        return int(float(p.get(k) or 0))
    except ValueError:
        return 0


grid(
    "fcc_service_inv_update", title="FCC Catalyst Service Invoices", model=SF, width=1149, win=(1180, 640),
    row_h=28, allow_delete=False,
    query=lambda p: SF.query.filter(is_fcc(), SF.SF == _int_param(p, "SF")).order_by(SF.ContainerNo, SF.UID),
    header=dict(h=87, bg="#4472C4", col_y=64, label_style=HEAD), nav_w=1180,
    columns=[
        dict(sec="header", type="label", text="FCC Catalyst Service Invoices", x=4, y=4, w=340, h=32,
             style="font:bold italic 16pt 'Times New Roman';color:#fff"),
        dict(sec="header", type="label",
             text="Note: Please do not submit unless all S/F containers are delivered, otherwise hold until completion.",
             x=396, y=8, w=624, h=24, style="color:#D8D8D8;justify-content:flex-end"),
        dict(sec="header", type="button", caption="Send the Invoice by e-mail", cls="blue", x=840, y=34, w=180, h=24,
             action={"do": "eml", "save": True, "url": "/e/fcc_service_email?SupplierInv={SupplierInv}&SF={SF}"}),
        _ro("UID", "UID", 4, 60, align="center"),
        _ro("MPC S/F#", "SF", 68, 63, align="center"),
        _ro("Product", "Product", 136, 96),
        _ro("Container#", "ContainerNo", 238, 101),
        _ro("Grace Inv #", "SupplierInv", 344, 88, bold=True),
        _ro("Inv Date", "SupplierInvDate", 437, 92, align="center"),
        _ro("Grace SO#", "Remarks", 534, 84),
        _ro("Delivery Date", "DeliveredOn", 623, 95, align="center"),
        _ro("Petro Rabigh PO#", "DeliveredPO", 723, 111),
        _ro("PO Item#", "DeliveredPOItem", 839, 64, align="center"),
        dict(label="Service Inv#", type="text", field="ServiceInv", x=908, y=4, w=115, h=22, color=MAG, head_style=PINK),
        dict(label="Submitted", type="check", field="ServiceInvSubmitted", x=1056, y=8, w=14, h=14, hx=1028, hw=70,
             head_style=PINK),
    ],
)


# ── B6. n-Heptane ISO-Tank Rental Invoices ────────────────────────────

def _tank_days(r):
    """Total days = delivery − arrival + 1; chargeable = total − free days, never below 0 (bug 10)."""
    dlv, arr = r.get("DeliveredOn"), r.get("DateofArrivaltoPort")
    if not dlv or not arr:
        return None, None, None
    total = (dlv - arr).days + 1
    charge = max(0, total - settings.get("tank_free_days", int))
    return total, charge, charge * settings.get("tank_rate_per_day", float)


def _tank_calc(r, p):
    total, charge, amount = _tank_days(r)
    rate = settings.get("tank_rate_per_day", float)
    free = settings.get("tank_free_days", int)
    desc = "\n".join([
        "ISO-Tank Rental Charges", "",
        f"Tank# {r.get('ContainerNo') or ''}", f"MPC S/F# {r.get('SF') or ''}", f"Bayan# {r.get('BayanNo') or ''}",
        f"Date of Arrival to Port: {fmt.short_date(r.get('DateofArrivaltoPort'))}",
        f"Date of Delivery: {fmt.short_date(r.get('DeliveredOn'))}",
        f"Total Days: {'' if total is None else total}",
        f"Chargeable Days ({free}-free days): {'' if charge is None else charge}",
        f"Rate per day: {fmt.general(rate)} USD/Tank/Day", "",
        f"Total Rate: {fmt.standard(amount) if amount is not None else ''} USD"])
    return {"TotalDays": total, "ChargeableDays": charge, "RentalUSD": amount, "Desc": desc}


grid(
    "tank_rental_charges", title="n-Heptane Tank Rental Invoice and Tank Returning to SL", model=SF, width=1436,
    win=(1451, 796), row_h=35, allow_delete=False, calc=_tank_calc, scripts=["access/inv.js"],
    query=lambda p: (SF.query.filter(is_heptane(), SF.DeliveredOn.isnot(None),
                                     (SF.DetentionInvSubmitted.is_(False)) | (SF.ReturnIsDone.is_(False)))
                     .order_by(SF.UID)),
    header=dict(h=62, bg="#4472C4", col_y=40, label_style=HEAD), alt_bg="#DAE3F3", row_bg="#DAE3F3", nav_w=1451,
    columns=[
        dict(sec="header", type="label", text="n-Heptane Tank Rental Invoice and Tank Returning to SL", x=4, y=4,
             w=372, h=32, style="font:bold italic 11pt 'Times New Roman';color:#fff"),
        _show_desc_button(380, 200),
        _ro("MPC S/F#", "SF", 4, 61, align="center"),
        _ro("D/N#", "UID", 69, 73, align="center"),
        _ro("Product", "Product", 146, 96),
        _ro("Qty", "SFQty", 246, 71, fmt="standard", align="right"),
        _ro("Tank #", "ContainerNo", 321, 97),
        _ro("Delivery Date", "DeliveredOn", 422, 91, align="center"),
        _ro("PO#", "DeliveredPO", 517, 97),
        _ro("Item#", "DeliveredPOItem", 618, 40, align="center"),
        dict(label="Bayan#", type="text", field="BayanNo", x=662, y=4, w=85, h=22, color=MAG, head_style=PINK),
        dict(label="Arrival to POD", type="date", field="DateofArrivaltoPort", x=751, y=4, w=90, h=22, color=MAG,
             align="center", head_style=PINK),
        dict(label="Detention Invoice", type="text", field="DetentionInv", x=845, y=4, w=115, h=22, color=MAG,
             head_style=PINK),
        dict(label="DI Submitted", type="check", field="DetentionInvSubmitted", x=999, y=10, w=14, h=14, hx=964, hw=88,
             head_style=PINK),
        dict(label="Empty Return Date", type="date", field="EmptyReturnDate", x=1056, y=4, w=121, h=22, align="center",
             head_style=YELLOW),
        dict(label="EIR No", type="text", field="EIRNo", x=1181, y=4, w=74, h=22, head_style=YELLOW),
        dict(label="Return Terminal", type="combo", field="ReturnTerminal", x=1259, y=4, w=104, h=22,
             options=L.return_terminals, head_style=YELLOW),
        dict(label="Returned", type="check", field="ReturnIsDone", x=1392, y=10, w=14, h=14, hx=1367, hw=65,
             head_style=YELLOW),
        dict(type="label", text="Invoice Description:", x=4, y=37, w=128, h=24, style="display:none;color:#595959"),
        dict(type="memo", name="Desc", x=136, y=37, w=360, h=160, locked=True, style=DESC),
    ],
)


# ── B7. Tanks Not-Returned to SL Report ───────────────────────────────

def _tanks_not_returned(params):
    rows = (SF.query.filter((is_heptane()) | (is_fcc()), SF.ReturnIsDone.is_(False))
            .order_by(SF.SF, SF.DeliveredOn.is_(None), SF.DeliveredOn).all())
    groups = []
    for prod in sorted({r.Product or "" for r in rows}, key=str.lower):
        groups.append(dict(product=prod, rows=[r for r in rows if (r.Product or "") == prod]))
    return {"groups": groups, "now": datetime.now()}


report("rpt_tanks_not_returned", title="Not-Returned Tanks Report", template="reports/inv_tanks_not_returned.html",
       data=_tanks_not_returned)
