from flask import Blueprint, render_template, request, abort
from flask_login import login_required
from sqlalchemy import func, or_
from extensions import db

bp = Blueprint("scs", __name__)


# ── Dashboard ──────────────────────────────────────────────────────

@bp.route("/dashboard")
@login_required
def dashboard():
    from models import ShipmentFile

    # Status counts
    raw_counts = dict(
        db.session.query(ShipmentFile.status, func.count(ShipmentFile.id))
        .group_by(ShipmentFile.status)
        .all()
    )
    raw_counts["total"] = sum(raw_counts.values())

    # Recent shipments (last 15)
    recent = (
        ShipmentFile.query
        .order_by(ShipmentFile.entry_date.desc().nullslast(), ShipmentFile.id.desc())
        .limit(15)
        .all()
    )

    return render_template("scs/dashboard.html", counts=raw_counts, recent=recent)


# ── Shipment Files ─────────────────────────────────────────────────

@bp.route("/shipments")
@login_required
def shipments():
    from models import ShipmentFile

    page = request.args.get("page", 1, type=int)
    per_page = 50
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = ShipmentFile.query

    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            ShipmentFile.sf_number.ilike(like),
            ShipmentFile.supplier_name.ilike(like),
            ShipmentFile.product_name.ilike(like),
            ShipmentFile.po_ref.ilike(like),
            ShipmentFile.container_no.ilike(like),
        ))

    if status_filter:
        query = query.filter(ShipmentFile.status == status_filter)

    query = query.order_by(ShipmentFile.entry_date.desc().nullslast(), ShipmentFile.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Status counts for filter pills
    all_statuses = (
        db.session.query(ShipmentFile.status, func.count(ShipmentFile.id))
        .group_by(ShipmentFile.status)
        .all()
    )
    status_counts = {s: c for s, c in all_statuses}

    return render_template(
        "scs/shipments.html",
        shipments=pagination.items,
        pagination=pagination,
        search=search,
        status_filter=status_filter,
        status_counts=status_counts,
    )


# ── Shipment Detail ────────────────────────────────────────────────

@bp.route("/shipments/<int:sid>")
@login_required
def shipment_detail(sid):
    from models import ShipmentFile
    sf = db.session.get(ShipmentFile, sid)
    if not sf:
        abort(404)
    return render_template("scs/shipment_detail.html", sf=sf)


# ── Customer POs ───────────────────────────────────────────────────

@bp.route("/customer-pos")
@login_required
def customer_pos():
    from models import CustomerPO

    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    query = CustomerPO.query

    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            CustomerPO.po_no.ilike(like),
            CustomerPO.customer_name.ilike(like),
            CustomerPO.product_name.ilike(like),
        ))

    if status == "open":
        query = query.filter(CustomerPO.is_closed == False)
    elif status == "closed":
        query = query.filter(CustomerPO.is_closed == True)

    query = query.order_by(CustomerPO.po_date.desc().nullslast(), CustomerPO.id.desc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    return render_template(
        "scs/customer_pos.html",
        pos=pagination.items,
        pagination=pagination,
        search=search,
        status=status,
    )


# ── Payment Tracking ──────────────────────────────────────────────

@bp.route("/payments")
@login_required
def payments():
    from models import ShipmentFile, ShipmentPaymentTracking

    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()

    query = (
        db.session.query(ShipmentPaymentTracking)
        .join(ShipmentFile, ShipmentPaymentTracking.shipment_id == ShipmentFile.id)
    )

    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            ShipmentFile.sf_number.ilike(like),
            ShipmentFile.supplier_name.ilike(like),
            ShipmentPaymentTracking.lc_no.ilike(like),
        ))

    query = query.order_by(ShipmentPaymentTracking.id.desc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    return render_template(
        "scs/payments.html",
        payments=pagination.items,
        pagination=pagination,
        search=search,
    )


# ── Permits ────────────────────────────────────────────────────────

@bp.route("/permits")
@login_required
def permits():
    from models import Permit

    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()

    query = Permit.query

    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            Permit.permit_no.ilike(like),
            Permit.product_name.ilike(like),
            Permit.hs_code.ilike(like),
        ))

    query = query.order_by(Permit.expiry_date.desc().nullslast(), Permit.id.desc())
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    return render_template(
        "scs/permits.html",
        permits=pagination.items,
        pagination=pagination,
        search=search,
    )
