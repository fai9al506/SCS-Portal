"""Master Data screens — replicas of the 9 Access forms 'Master Data - …' (spec 0, section C),
plus admin-only screens for the lookup lists that Access could only edit in the table itself.

All screens share one engine: the page gets every record of the table, the browser handles
record navigation (like Access), and the record is saved when the user leaves it.
"""
from flask import Blueprint, render_template, request, jsonify, abort, url_for
from flask_login import login_required, current_user
from sqlalchemy import func, inspect as sa_inspect

from extensions import db
from models import (
    Brokers, Customers, CustomerAdd, CustomersPO, CustomerContracts, Packing, Products, ProductGroup,
    ReturningTerminal, SF, SFBrokerCover, ShipmentsStatus, ShippingLines, Suppliers, Transporters,
    Permits, StorageLoc, InternalContacts, Currency, UOM, DeliveryTerms, PaymentTerms, PayTermsCus,
    PortOfDestinations, ClearanceStatus, PermitReq, POIssuedToCompanies, ACCESS_FIELDS,
)
from services.audit import log_action

bp = Blueprint("master", __name__, url_prefix="/master")

# Access standard error messages (shown exactly as Access shows them)
MSG_REQUIRED = "You must enter a value in the '{}' field."
MSG_DUPLICATE = ("The changes you requested to the table were not successful because they would create "
                 "duplicate values in the index, primary key, or relationship. Change the data in the field "
                 "or fields that contain duplicate data, remove the index, or redefine the index to permit "
                 "duplicate entries and try again.")


def f(attr, label, lx, cx, y, lw=112, cw=232, kind="text", maxlen=255, bold=False, tab=None):
    return dict(attr=attr, label=label, lx=lx, cx=cx, y=y, lw=lw, cw=cw, kind=kind,
                maxlen=maxlen, bold=bold, tab=tab)


FORMS = {
    "customers": dict(
        title="Master Data - Customers", model=Customers, key="CusName", width=384, detail_h=140,
        fields=[f("CusName", "Customer Name", 24, 140, 20), f("SAPID", "SAP No.", 24, 140, 53)],
        buttons=(208, 88),
        refs=[(CustomerAdd, "Customer"), (CustomersPO, "Affiliate"), (SF, "IntendedCustomer"),
              (SF, "DeliveredTo"), (SFBrokerCover, "IntendedCustomer"), (CustomerContracts, "CusName")],
    ),
    "brokers": dict(
        title="Master Data - Brokers", model=Brokers, key="BrokerName", width=404, detail_h=348,
        fields=[f("BrokerName", "Short Office Name", 16, 156, 14, lw=136),
                f("BrokerFullName", "Full Office Name", 16, 156, 47, lw=136),
                f("BrokerAdd1", "Address 1", 16, 156, 80, lw=136),
                f("BrokerAdd2", "Address 2", 16, 156, 113, lw=136),
                f("BrokerAdd3Tel", "Tel", 16, 156, 146, lw=136),
                f("BrokerAdd4Mob", "Mob", 16, 156, 179, lw=136),
                f("BrokerRepName", "Contact Name", 16, 156, 212, lw=136),
                f("BrokerEmails", "Contact Emails", 16, 156, 245, lw=136)],
        hint=("* Please seperate them with (;)", 16, 272), buttons=(204, 300),
        refs=[(SF, "Broker")],
    ),
    "transporters": dict(
        title="Master Data - Transporters", model=Transporters, key="TransporterName", width=388, detail_h=152,
        fields=[f("TransporterName", "Transporter Name", 16, 145, 16, lw=125),
                f("emails", "Emails for DNs", 16, 145, 49, lw=125)],
        hint=("* Please seperate them with (;)", 16, 76), buttons=(208, 104),
        refs=[(SF, "DeliveredTransporter")],
    ),
    "returning_terminal": dict(
        title="Master Data - Returning Terminal", model=ReturningTerminal, key="Terminal", width=384, detail_h=116,
        fields=[f("Terminal", "Terminal", 24, 140, 18)], buttons=(208, 60),
        refs=[(SF, "ReturnTerminal")],
    ),
    "products": dict(
        title="Master Data - Products", model=Products, key="ProductName", width=384, detail_h=168,
        fields=[f("ProductName", "Product Name", 24, 140, 18, maxlen=50, tab=0),
                f("ProductGroup", "Product Group", 24, 140, 51, kind="group", tab=1),
                f("SAPName", "SAP Code", 24, 140, 84, tab=4)],
        buttons=(208, 116), button_tab=(2, 3),
        refs=[(CustomersPO, "Product"), (Permits, "ProductName"), (ShipmentsStatus, "Product"), (SF, "Product"),
              (SFBrokerCover, "Product"), (CustomerContracts, "ProductName")],
        # Names used by the FCC and n-Heptane screens — renaming them would break those screens
        protected={"fcc catalyst", "n-heptane"},
    ),
    "packing": dict(
        title="Master Data - Packing", model=Packing, key="PackinMode", width=384, detail_h=116,
        fields=[f("PackinMode", "Packing Mode", 24, 140, 18)], buttons=(208, 56),
        refs=[(CustomersPO, "Packing"), (SF, "DeliveredPacking")],
    ),
    "suppliers": dict(
        title="Master Data - Suppliers", model=Suppliers, key="SupplierName", width=384, detail_h=149,
        fields=[f("SupplierName", "Supplier Name", 24, 140, 18), f("SAPNo", "SAP No.", 24, 140, 51)],
        buttons=(208, 88),
        refs=[(ShipmentsStatus, "Supplier"), (SF, "Supplier")],
    ),
    "customer_address": dict(
        title="Master Data - Customer Address", model=CustomerAdd, key=None, width=407, detail_h=304,
        fields=[f("Customer", "Customer", 12, 160, 20, lw=144, kind="customer"),
                f("CustomerPlant", "Customer Plant Code", 12, 160, 53, lw=144, bold=True),
                f("CusAdd1", "Customer Add1", 12, 160, 86, lw=144),
                f("CusAdd2", "Customer Add2", 12, 160, 119, lw=144),
                f("CusCntName", "Contact Name", 12, 160, 152, lw=144),
                f("CusCntTel", "Tel", 12, 160, 185, lw=144),
                f("CusCntMob", "Mob", 12, 160, 218, lw=144)],
        buttons=(224, 252), refs=[],
    ),
    "shipping_lines": dict(
        title="Master Data - Shipping Lines", model=ShippingLines, key="SLName", width=384, detail_h=116,
        fields=[f("SLName", "Shipping Line", 24, 140, 18)], buttons=(208, 60),
        refs=[(SF, "ShippingLine")],
    ),
}


def _lookup(key, title, model, fields, refs, protected=()):
    """Admin screen for a lookup list (no screen in Access). Same look as the Master Data forms."""
    fl = [f(attr, label, 24, 160, 18 + 33 * i, lw=128) for i, (attr, label) in enumerate(fields)]
    detail_h = 18 + 33 * len(fields) + 50
    FORMS[key] = dict(title=title, model=model, key=fields[0][0], width=420, detail_h=detail_h, fields=fl,
                      buttons=(224, detail_h - 46), refs=refs, protected=set(protected), admin=True)


_lookup("storage_locations", "Storage Locations", StorageLoc,
        [("StorageLocation", "Storage Location"), ("emails", "Emails")], [(SF, "StorageLoc")])
_lookup("internal_contacts", "Internal Contacts (email groups)", InternalContacts,
        [("Group", "Group"), ("Groupemails", "Emails")], [],
        protected={"logistics", "permit", "payreqto", "payreqcc"})
_lookup("currency", "Currency", Currency, [("Currency", "Currency")],
        [(SF, "ACurr"), (ShipmentsStatus, "ACurr"), (CustomersPO, "Curr")])
_lookup("uom", "UOM", UOM, [("UOM", "UOM")], [(SF, "UOM"), (ShipmentsStatus, "UOM"), (CustomersPO, "PerUOM")])
_lookup("delivery_terms", "Delivery Terms", DeliveryTerms, [("DeliveryTerm", "Delivery Term")],
        [(CustomersPO, "DeliveryTerms")])
_lookup("payment_terms", "Payment Terms (Suppliers)", PaymentTerms, [("PaymentTerm", "Payment Term")],
        [(ShipmentsStatus, "PayTerm")])
_lookup("pay_terms_cus", "Payment Terms (Customers)", PayTermsCus, [("PayTermCus", "Payment Term")],
        [(CustomersPO, "PaymentTerms")])
_lookup("ports", "Port of Destinations", PortOfDestinations, [("PortOfDistination", "Port")],
        [(SF, "POD"), (ShipmentsStatus, "POD")])
_lookup("clearance_status", "Clearance Status", ClearanceStatus,
        [("ClearanceStatus", "Clearance Status"), ("SN", "Sort No.")], [(ShipmentsStatus, "ClearanceStatus")])
_lookup("permit_req", "Permit Requirements", PermitReq, [("PermitReq", "Permit Requirement")],
        [(Permits, "PermitRequirement")])
_lookup("po_issued_to", "PO Issued To Companies", POIssuedToCompanies, [("CompanyName", "Company Name")],
        [(CustomersPO, "POIssuedTo")])
_lookup("product_groups", "Product Groups", ProductGroup, [("ProductGroup", "Product Group")], [])
FORMS["clearance_status"]["key"] = None  # Access table has no primary key
FORMS["product_groups"]["key"] = None    # Products store the group ID, so renaming is safe


def window_size(form):
    """Popup window size: border + title bar + form header + detail + record navigation bar."""
    return form["width"] + 2, 31 + 38 + form["detail_h"] + 24 + 2


def _pk(model):
    """Attribute name of the primary key (e.g. 'id', 'UID', 'ID')."""
    mapper = sa_inspect(model)
    return mapper.get_property_by_column(mapper.primary_key[0]).key


def _record(model, row, form):
    out = {"_id": getattr(row, _pk(model))}
    for fld in form["fields"]:
        v = getattr(row, fld["attr"])
        out[fld["attr"]] = "" if v is None else str(v) if not isinstance(v, (int, float)) else v
    return out


def _rows(form):
    model = form["model"]
    q = model.query
    if form["key"]:
        q = q.order_by(func.lower(getattr(model, form["key"])))
    else:
        q = q.order_by(getattr(model, _pk(model)))
    return [_record(model, r, form) for r in q.all()]


def _get_form(key):
    form = FORMS.get(key) or abort(404)
    if form.get("admin") and current_user.role != "Admin":
        abort(403)
    return form


def _ref_count(form, value):
    return sum(m.query.filter(getattr(m, a) == value).count() for m, a in form["refs"])


@bp.route("/<key>")
@login_required
def form(key):
    form = _get_form(key)
    options = {}
    kinds = {fld["kind"] for fld in form["fields"]}
    if "group" in kinds:
        # Access combo: shows the group name, stores the group ID as text
        options["group"] = [[str(g.ID), g.ProductGroup] for g in ProductGroup.query.order_by(ProductGroup.ProductGroup)]
    if "customer" in kinds:
        options["customer"] = [c.CusName for c in Customers.query.order_by(Customers.id)]
    js_cfg = dict(fields=[{"attr": fl["attr"], "kind": fl["kind"]} for fl in form["fields"]], rows=_rows(form),
                  options=options, saveUrl=url_for("master.save", key=key), deleteUrl=url_for("master.delete", key=key))
    return render_template("access/master_form.html", form=form, options=options, js_cfg=js_cfg)


@bp.route("/<key>/save", methods=["POST"])
@login_required
def save(key):
    form = _get_form(key)
    model = form["model"]
    data = request.get_json() or {}
    values = {fld["attr"]: (data.get(fld["attr"]) or "").strip() for fld in form["fields"]}
    for fld in form["fields"]:
        if fld["attr"] == "SN":
            values["SN"] = int(values["SN"]) if values["SN"].lstrip("-").isdigit() else 0
        elif values[fld["attr"]] == "":
            values[fld["attr"]] = None

    row = model.query.get(data["_id"]) if data.get("_id") else None
    keyattr = form["key"]
    old_key = getattr(row, keyattr) if (row and keyattr) else None

    if keyattr:
        new_key = values[keyattr]
        if not new_key:
            access_name = next(n for n, a in ACCESS_FIELDS[model].items() if a == keyattr)
            return jsonify(error=MSG_REQUIRED.format(f"{model.__access_table__}.{access_name}")), 400
        dup = model.query.filter(func.lower(getattr(model, keyattr)) == new_key.lower())
        if row:
            dup = dup.filter(getattr(model, _pk(model)) != getattr(row, _pk(model)))
        if dup.first():
            return jsonify(error=MSG_DUPLICATE), 400
        if old_key and old_key != new_key and old_key.lower() in form.get("protected", set()):
            return jsonify(error=f"'{old_key}' is used by fixed rules in the system and can't be renamed."), 400

    before = _record(model, row, form) if row else None
    if row is None:
        row = model()
        db.session.add(row)
    for attr, v in values.items():
        setattr(row, attr, v)

    # Access joins on names, so a rename used to cut old records off. Carry the new name to them.
    renamed = 0
    if keyattr and old_key and old_key != values[keyattr]:
        for m, a in form["refs"]:
            renamed += m.query.filter(getattr(m, a) == old_key).update({a: values[keyattr]}, synchronize_session=False)

    db.session.commit()
    after = _record(model, row, form)
    log_action(current_user.id, "User", "update" if before else "create", model.__access_table__,
               after["_id"], before=before, after=dict(after, renamed_in_records=renamed) if renamed else after)
    return jsonify(record=after, rows=_rows(form))


@bp.route("/<key>/delete", methods=["POST"])
@login_required
def delete(key):
    form = _get_form(key)
    model = form["model"]
    row = model.query.get((request.get_json() or {}).get("_id")) or abort(404)
    if form["key"]:
        used = _ref_count(form, getattr(row, form["key"]))
        if used:
            return jsonify(error=f"This record can't be deleted because {used} other record(s) use it."), 400
        if (getattr(row, form["key"]) or "").lower() in form.get("protected", set()):
            return jsonify(error="This record is used by fixed rules in the system and can't be deleted."), 400
    if model is ProductGroup and Products.query.filter(Products.ProductGroup == str(row.ID)).count():
        return jsonify(error="This record can't be deleted because products use it."), 400
    before = _record(model, row, form)
    db.session.delete(row)
    db.session.commit()
    log_action(current_user.id, "User", "delete", model.__access_table__, before["_id"], before=before)
    return jsonify(rows=_rows(form))
