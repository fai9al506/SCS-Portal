from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from extensions import db

bp = Blueprint("po", __name__, url_prefix="/po")


# ── PO List ────────────────────────────────────────────────────────

@bp.route("/")
@login_required
def po_list():
    from models import PurchaseOrder, PurchaseOrderItem, Product

    page = request.args.get("page", 1, type=int)
    per_page = 50
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = PurchaseOrder.query

    if search:
        like = f"%{search}%"
        # Search PO number, supplier name, or product names in items
        from models import Supplier
        query = (
            query
            .outerjoin(Supplier, PurchaseOrder.supplier_id == Supplier.id)
            .outerjoin(PurchaseOrderItem, PurchaseOrder.id == PurchaseOrderItem.po_id)
            .outerjoin(Product, PurchaseOrderItem.product_id == Product.id)
            .filter(or_(
                PurchaseOrder.po_number.ilike(like),
                Supplier.name.ilike(like),
                Product.name.ilike(like),
            ))
            .distinct()
        )

    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter)

    query = query.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Status counts for filter pills
    all_statuses = (
        db.session.query(PurchaseOrder.status, func.count(PurchaseOrder.id))
        .group_by(PurchaseOrder.status)
        .all()
    )
    status_counts = {s: c for s, c in all_statuses}

    # Build display data for each PO
    today = date.today()
    po_data = []
    for po in pagination.items:
        items = po.items
        item_count = len(items)
        products = ", ".join(
            i.product.name for i in items if i.product
        ) or "\u2014"

        total_qty = sum(i.qty or 0 for i in items)

        # Earliest ETD / ETA across items
        etds = [i.etd for i in items if i.etd]
        etas = [i.eta for i in items if i.eta]
        earliest_etd = min(etds) if etds else None
        earliest_eta = min(etas) if etas else None

        # DTA = min ETA - today
        dta = None
        if earliest_eta and po.status in ("Ordered", "Incoming"):
            dta = (earliest_eta - today).days

        # Payment statuses (first item as representative, or aggregate)
        first_pay = items[0].first_payment_status if items else "\u2014"
        second_pay = items[0].second_payment_status if items else "\u2014"

        po_data.append({
            "po": po,
            "item_count": item_count,
            "products": products,
            "total_qty": total_qty,
            "earliest_etd": earliest_etd,
            "earliest_eta": earliest_eta,
            "dta": dta,
            "first_pay": first_pay,
            "second_pay": second_pay,
        })

    return render_template(
        "scs/po_list.html",
        po_data=po_data,
        pagination=pagination,
        search=search,
        status_filter=status_filter,
        status_counts=status_counts,
    )


# ── New PO ─────────────────────────────────────────────────────────

@bp.route("/new", methods=["GET", "POST"])
@login_required
def po_new():
    from models import (
        PurchaseOrder, PurchaseOrderItem, Supplier, PaymentTermSupplier,
        Product, UnitOfMeasure, Currency, PortOfDestination, Permit,
    )

    if request.method == "POST":
        po = PurchaseOrder(
            po_number=request.form.get("po_number", "").strip() or None,
            supplier_id=request.form.get("supplier_id", type=int) or None,
            payment_terms_id=request.form.get("payment_terms_id", type=int) or None,
            status=request.form.get("status", "Ordered"),
            notes=request.form.get("notes", "").strip() or None,
            created_by=current_user.id,
        )
        db.session.add(po)
        db.session.flush()  # get po.id

        # Line items
        product_ids = request.form.getlist("product_id[]")
        qtys = request.form.getlist("qty[]")
        uoms = request.form.getlist("uom[]")
        unit_prices = request.form.getlist("unit_price[]")
        currencies = request.form.getlist("currency[]")
        etds = request.form.getlist("etd[]")
        etas = request.form.getlist("eta[]")
        pod_ids = request.form.getlist("pod_id[]")
        permit_ids = request.form.getlist("permit_id[]")
        sap_codes = request.form.getlist("sap_code[]")
        statuses = request.form.getlist("item_status[]")
        first_pays = request.form.getlist("first_payment[]")
        second_pays = request.form.getlist("second_payment[]")

        for idx in range(len(product_ids)):
            qty_val = _to_float(qtys[idx]) if idx < len(qtys) else None
            price_val = _to_float(unit_prices[idx]) if idx < len(unit_prices) else None
            total = (qty_val or 0) * (price_val or 0) if (qty_val and price_val) else None

            item = PurchaseOrderItem(
                po_id=po.id,
                item_no=idx + 1,
                product_id=_to_int(product_ids[idx]),
                qty=qty_val,
                uom=uoms[idx] if idx < len(uoms) else None,
                unit_price=price_val,
                currency=currencies[idx] if idx < len(currencies) else None,
                total_amount=total,
                etd=_to_date(etds[idx]) if idx < len(etds) else None,
                eta=_to_date(etas[idx]) if idx < len(etas) else None,
                port_of_destination_id=_to_int(pod_ids[idx]) if idx < len(pod_ids) else None,
                permit_id=_to_int(permit_ids[idx]) if idx < len(permit_ids) else None,
                sap_code=sap_codes[idx].strip() if idx < len(sap_codes) else None,
                status=statuses[idx] if idx < len(statuses) else "Ordered",
                first_payment_status=first_pays[idx] if idx < len(first_pays) else "Pending",
                second_payment_status=second_pays[idx] if idx < len(second_pays) else "Pending",
            )
            db.session.add(item)

        db.session.commit()
        flash("Purchase Order created successfully.", "success")
        return redirect(url_for("po.po_list"))

    # GET — render empty form
    return render_template(
        "scs/po_form.html",
        po=None,
        suppliers=Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all(),
        payment_terms=PaymentTermSupplier.query.filter_by(is_active=True).order_by(PaymentTermSupplier.name).all(),
        products=Product.query.filter_by(is_active=True).order_by(Product.name).all(),
        uoms=UnitOfMeasure.query.filter_by(is_active=True).order_by(UnitOfMeasure.name).all(),
        currencies=Currency.query.filter_by(is_active=True).order_by(Currency.code).all(),
        pods=PortOfDestination.query.filter_by(is_active=True).order_by(PortOfDestination.name).all(),
        permits=Permit.query.filter_by(is_active=True).order_by(Permit.permit_no).all(),
    )


# ── PO Detail ──────────────────────────────────────────────────────

@bp.route("/<int:po_id>")
@login_required
def po_detail(po_id):
    from models import PurchaseOrder

    po = db.session.get(PurchaseOrder, po_id)
    if not po:
        abort(404)

    today = date.today()
    items_data = []
    for item in po.items:
        dta = None
        if item.eta and po.status in ("Ordered", "Incoming"):
            dta = (item.eta - today).days
        items_data.append({"item": item, "dta": dta})

    return render_template("scs/po_detail.html", po=po, items_data=items_data)


# ── Edit PO ────────────────────────────────────────────────────────

@bp.route("/<int:po_id>/edit", methods=["GET", "POST"])
@login_required
def po_edit(po_id):
    from models import (
        PurchaseOrder, PurchaseOrderItem, Supplier, PaymentTermSupplier,
        Product, UnitOfMeasure, Currency, PortOfDestination, Permit,
    )

    po = db.session.get(PurchaseOrder, po_id)
    if not po:
        abort(404)

    if request.method == "POST":
        po.po_number = request.form.get("po_number", "").strip() or None
        po.supplier_id = request.form.get("supplier_id", type=int) or None
        po.payment_terms_id = request.form.get("payment_terms_id", type=int) or None
        po.status = request.form.get("status", po.status)
        po.notes = request.form.get("notes", "").strip() or None

        # Delete old items and recreate
        PurchaseOrderItem.query.filter_by(po_id=po.id).delete()
        db.session.flush()

        product_ids = request.form.getlist("product_id[]")
        qtys = request.form.getlist("qty[]")
        uoms = request.form.getlist("uom[]")
        unit_prices = request.form.getlist("unit_price[]")
        currencies = request.form.getlist("currency[]")
        etds = request.form.getlist("etd[]")
        etas = request.form.getlist("eta[]")
        pod_ids = request.form.getlist("pod_id[]")
        permit_ids = request.form.getlist("permit_id[]")
        sap_codes = request.form.getlist("sap_code[]")
        statuses = request.form.getlist("item_status[]")
        first_pays = request.form.getlist("first_payment[]")
        second_pays = request.form.getlist("second_payment[]")

        for idx in range(len(product_ids)):
            qty_val = _to_float(qtys[idx]) if idx < len(qtys) else None
            price_val = _to_float(unit_prices[idx]) if idx < len(unit_prices) else None
            total = (qty_val or 0) * (price_val or 0) if (qty_val and price_val) else None

            item = PurchaseOrderItem(
                po_id=po.id,
                item_no=idx + 1,
                product_id=_to_int(product_ids[idx]),
                qty=qty_val,
                uom=uoms[idx] if idx < len(uoms) else None,
                unit_price=price_val,
                currency=currencies[idx] if idx < len(currencies) else None,
                total_amount=total,
                etd=_to_date(etds[idx]) if idx < len(etds) else None,
                eta=_to_date(etas[idx]) if idx < len(etas) else None,
                port_of_destination_id=_to_int(pod_ids[idx]) if idx < len(pod_ids) else None,
                permit_id=_to_int(permit_ids[idx]) if idx < len(permit_ids) else None,
                sap_code=sap_codes[idx].strip() if idx < len(sap_codes) else None,
                status=statuses[idx] if idx < len(statuses) else "Ordered",
                first_payment_status=first_pays[idx] if idx < len(first_pays) else "Pending",
                second_payment_status=second_pays[idx] if idx < len(second_pays) else "Pending",
            )
            db.session.add(item)

        db.session.commit()
        flash("Purchase Order updated successfully.", "success")
        return redirect(url_for("po.po_detail", po_id=po.id))

    # GET — render form pre-filled
    return render_template(
        "scs/po_form.html",
        po=po,
        suppliers=Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all(),
        payment_terms=PaymentTermSupplier.query.filter_by(is_active=True).order_by(PaymentTermSupplier.name).all(),
        products=Product.query.filter_by(is_active=True).order_by(Product.name).all(),
        uoms=UnitOfMeasure.query.filter_by(is_active=True).order_by(UnitOfMeasure.name).all(),
        currencies=Currency.query.filter_by(is_active=True).order_by(Currency.code).all(),
        pods=PortOfDestination.query.filter_by(is_active=True).order_by(PortOfDestination.name).all(),
        permits=Permit.query.filter_by(is_active=True).order_by(Permit.permit_no).all(),
    )


# ── Update PO Status ──────────────────────────────────────────────

@bp.route("/<int:po_id>/status", methods=["POST"])
@login_required
def po_update_status(po_id):
    from models import PurchaseOrder

    po = db.session.get(PurchaseOrder, po_id)
    if not po:
        abort(404)

    new_status = request.form.get("status", "").strip()
    if new_status in ("Ordered", "Incoming", "Cleared", "Canceled"):
        po.status = new_status
        db.session.commit()
        flash(f"PO status updated to {new_status}.", "success")
    else:
        flash("Invalid status.", "error")

    return redirect(url_for("po.po_detail", po_id=po.id))


# ── Helpers ────────────────────────────────────────────────────────

def _to_float(val):
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


def _to_int(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None


def _to_date(val):
    from datetime import date as dt_date
    try:
        if val:
            return dt_date.fromisoformat(val)
    except (ValueError, TypeError):
        pass
    return None
