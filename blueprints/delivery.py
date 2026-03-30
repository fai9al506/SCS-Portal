from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from extensions import db

bp = Blueprint("delivery", __name__, url_prefix="/deliveries")


# ── Helpers ───────────────────────────────────────────────────────

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


# ── Delivery List ─────────────────────────────────────────────────

@bp.route("/")
@login_required
def delivery_list():
    from models import DeliveryNote, DeliveryNoteItem, Product

    page = request.args.get("page", 1, type=int)
    per_page = 50
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query = DeliveryNote.query

    if search:
        like = f"%{search}%"
        query = (
            query
            .outerjoin(DeliveryNoteItem, DeliveryNote.id == DeliveryNoteItem.delivery_note_id)
            .filter(or_(
                DeliveryNote.dn_number.ilike(like),
                DeliveryNote.customer_name.ilike(like),
                DeliveryNoteItem.product_name.ilike(like),
                DeliveryNoteItem.container_no.ilike(like),
            ))
            .distinct()
        )

    if status_filter:
        query = query.filter(DeliveryNote.status == status_filter)

    if date_from:
        d = _to_date(date_from)
        if d:
            query = query.filter(DeliveryNote.delivery_date >= d)
    if date_to:
        d = _to_date(date_to)
        if d:
            query = query.filter(DeliveryNote.delivery_date <= d)

    query = query.order_by(DeliveryNote.delivery_date.desc().nullslast(), DeliveryNote.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Status counts for filter pills
    all_statuses = (
        db.session.query(DeliveryNote.status, func.count(DeliveryNote.id))
        .group_by(DeliveryNote.status)
        .all()
    )
    status_counts = {s: c for s, c in all_statuses}

    # Build display data
    dn_data = []
    for dn in pagination.items:
        products = ", ".join(
            i.product_name for i in dn.items if i.product_name
        ) or "\u2014"
        total_qty = sum(i.qty or 0 for i in dn.items)

        dn_data.append({
            "dn": dn,
            "products": products,
            "total_qty": total_qty,
        })

    return render_template(
        "scs/delivery_list.html",
        dn_data=dn_data,
        pagination=pagination,
        search=search,
        status_filter=status_filter,
        status_counts=status_counts,
        date_from=date_from,
        date_to=date_to,
    )


# ── Delivery New ──────────────────────────────────────────────────

@bp.route("/new", methods=["GET", "POST"])
@login_required
def delivery_new():
    from models import (
        DeliveryNote, DeliveryNoteItem, ShipmentContainer, ShipmentFile,
        Customer, CustomerAddress, Transporter, CustomerPO, PackingType,
    )

    if request.method == "POST":
        customer_id = _to_int(request.form.get("customer_id"))
        affiliate_id = _to_int(request.form.get("affiliate_id"))

        # Resolve customer name
        customer_name = None
        if customer_id:
            from models import Customer as Cust
            cust = db.session.get(Cust, customer_id)
            customer_name = cust.name if cust else None

        dn = DeliveryNote(
            dn_number=request.form.get("dn_number", "").strip() or None,
            delivery_date=_to_date(request.form.get("delivery_date")) or date.today(),
            customer_id=customer_id,
            customer_name=customer_name,
            affiliate_id=affiliate_id,
            transporter_id=_to_int(request.form.get("transporter_id")),
            customer_po_id=_to_int(request.form.get("customer_po_id")),
            so_number=request.form.get("so_number", "").strip() or None,
            gp_docs_required=bool(request.form.get("gp_docs_required")),
            packing=request.form.get("packing", "").strip() or None,
            remarks=request.form.get("remarks", "").strip() or None,
            status="Delivered",
            created_by=current_user.id,
        )
        db.session.add(dn)
        db.session.flush()

        # Items — from selected containers
        container_ids = request.form.getlist("item_container_id[]")
        item_qtys = request.form.getlist("item_qty[]")

        total = 0.0
        for idx in range(len(container_ids)):
            cid = _to_int(container_ids[idx])
            if not cid:
                continue

            sc = db.session.get(ShipmentContainer, cid)
            if not sc:
                continue

            qty = _to_float(item_qtys[idx]) if idx < len(item_qtys) else None
            if not qty or qty <= 0:
                continue

            sf = sc.shipment

            item = DeliveryNoteItem(
                delivery_note_id=dn.id,
                shipment_container_id=cid,
                sf_number=sf.sf_number if sf else None,
                product_id=sf.product_id if sf else None,
                product_name=sf.product_name if sf else None,
                container_no=sc.container_no,
                qty=qty,
                uom=sc.uom,
                storage_location_id=sc.storage_location_id,
                packing=sc.packing,
            )
            db.session.add(item)
            total += qty

        dn.total_qty = total
        db.session.commit()
        flash("Delivery Note created successfully.", "success")
        return redirect(url_for("delivery.delivery_detail", dn_id=dn.id))

    # GET — render form
    return render_template(
        "scs/delivery_form.html",
        dn=None,
        customers=Customer.query.filter_by(is_active=True).order_by(Customer.name).all(),
        transporters=Transporter.query.filter_by(is_active=True).order_by(Transporter.name).all(),
        packing_types=PackingType.query.filter_by(is_active=True).order_by(PackingType.name).all(),
    )


# ── Delivery Detail ───────────────────────────────────────────────

@bp.route("/<int:dn_id>")
@login_required
def delivery_detail(dn_id):
    from models import DeliveryNote

    dn = db.session.get(DeliveryNote, dn_id)
    if not dn:
        abort(404)

    return render_template("scs/delivery_detail.html", dn=dn)
