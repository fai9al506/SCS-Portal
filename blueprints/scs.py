from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from extensions import db

bp = Blueprint("scs", __name__)


# ── Helpers (same as po.py) ───────────────────────────────────────

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


# ── Dashboard ──────────────────────────────────────────────────────

@bp.route("/dashboard")
@login_required
def dashboard():
    from models import ShipmentFile, ShipmentContainer, CustomerPO, PurchaseOrder

    today = date.today()

    # Summary counts
    incoming_shipments = ShipmentFile.query.filter(ShipmentFile.status == "Incoming").count()

    pending_clearance = (
        db.session.query(func.count(ShipmentContainer.id))
        .join(ShipmentFile, ShipmentContainer.shipment_id == ShipmentFile.id)
        .filter(
            ShipmentContainer.clearance_status == "Incoming",
            ShipmentFile.status != "Cleared",
        )
        .scalar()
    ) or 0

    open_customer_pos = CustomerPO.query.filter(CustomerPO.is_closed == False).count()

    active_pos = PurchaseOrder.query.filter(
        PurchaseOrder.status.in_(["Ordered", "Incoming"])
    ).count()

    # Arriving Soon — top 10 incoming shipments by ETA
    arriving_soon = (
        ShipmentFile.query
        .filter(ShipmentFile.status == "Incoming", ShipmentFile.eta.isnot(None))
        .order_by(ShipmentFile.eta.asc())
        .limit(10)
        .all()
    )
    arriving_data = []
    for sf in arriving_soon:
        dta = (sf.eta - today).days if sf.eta else None
        container_count = len(sf.containers) if sf.containers else 0
        arriving_data.append({
            "sf": sf,
            "dta": dta,
            "container_count": container_count,
        })

    # Recent POs (last 10)
    recent_pos = (
        PurchaseOrder.query
        .order_by(PurchaseOrder.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "scs/dashboard.html",
        incoming_shipments=incoming_shipments,
        pending_clearance=pending_clearance,
        open_customer_pos=open_customer_pos,
        active_pos=active_pos,
        arriving_data=arriving_data,
        recent_pos=recent_pos,
        today=today,
    )


# ── Shipment Files — List ──────────────────────────────────────────

@bp.route("/shipments")
@login_required
def shipments():
    from models import ShipmentFile, ShipmentContainer, PurchaseOrder

    page = request.args.get("page", 1, type=int)
    per_page = 50
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = ShipmentFile.query

    if search:
        like = f"%{search}%"
        query = (
            query
            .outerjoin(PurchaseOrder, ShipmentFile.po_id == PurchaseOrder.id)
            .outerjoin(ShipmentContainer, ShipmentFile.id == ShipmentContainer.shipment_id)
            .filter(or_(
                ShipmentFile.sf_number.ilike(like),
                ShipmentFile.supplier_name.ilike(like),
                ShipmentFile.product_name.ilike(like),
                PurchaseOrder.po_number.ilike(like),
                ShipmentContainer.container_no.ilike(like),
            ))
            .distinct()
        )

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

    # Build display data
    today = date.today()
    sf_data = []
    for sf in pagination.items:
        container_count = len(sf.containers)
        total_qty = sum(c.qty or 0 for c in sf.containers) if sf.containers else None
        po_number = sf.purchase_order.po_number if sf.purchase_order else None

        # DTA = ETA - today
        dta = None
        if sf.eta and sf.status in ("Incoming", "Ordered"):
            dta = (sf.eta - today).days

        sf_data.append({
            "sf": sf,
            "container_count": container_count,
            "total_qty": total_qty,
            "po_number": po_number,
            "dta": dta,
        })

    return render_template(
        "scs/shipments.html",
        sf_data=sf_data,
        pagination=pagination,
        search=search,
        status_filter=status_filter,
        status_counts=status_counts,
    )


# ── Shipment Files — Detail ───────────────────────────────────────

@bp.route("/shipments/<int:sid>")
@login_required
def shipment_detail(sid):
    from models import ShipmentFile, StorageLocation

    sf = db.session.get(ShipmentFile, sid)
    if not sf:
        abort(404)

    today = date.today()
    dta = None
    if sf.eta and sf.status in ("Incoming", "Ordered"):
        dta = (sf.eta - today).days

    storage_locations = StorageLocation.query.filter_by(is_active=True).order_by(StorageLocation.name).all()

    return render_template(
        "scs/shipment_detail.html",
        sf=sf,
        dta=dta,
        storage_locations=storage_locations,
    )


# ── Shipment Files — New ──────────────────────────────────────────

@bp.route("/shipments/new", methods=["GET", "POST"])
@login_required
def shipment_new():
    from models import (
        ShipmentFile, ShipmentContainer, PurchaseOrder,
        Supplier, Product, Customer, Broker, Permit,
        ShippingLine, PortOfDestination, UnitOfMeasure, PackingType,
        Currency,
    )

    if request.method == "POST":
        sf = ShipmentFile(
            sf_number=request.form.get("sf_number", "").strip() or None,
            po_id=_to_int(request.form.get("po_id")),
            po_item_no=_to_int(request.form.get("po_item_no")),
            supplier_id=_to_int(request.form.get("supplier_id")),
            supplier_name=request.form.get("supplier_name", "").strip() or None,
            product_id=_to_int(request.form.get("product_id")),
            product_name=request.form.get("product_name", "").strip() or None,
            bol_no=request.form.get("bol_no", "").strip() or None,
            bol_date=_to_date(request.form.get("bol_date")),
            shipping_line_id=_to_int(request.form.get("shipping_line_id")),
            etd=_to_date(request.form.get("etd")),
            eta=_to_date(request.form.get("eta")),
            actual_arrival=_to_date(request.form.get("actual_arrival")),
            port_of_destination_id=_to_int(request.form.get("port_of_destination_id")),
            port_of_destination_name=request.form.get("port_of_destination_name", "").strip() or None,
            status=request.form.get("status", "Incoming"),
            intended_customer_id=_to_int(request.form.get("intended_customer_id")),
            broker_id=_to_int(request.form.get("broker_id")),
            permit_id=_to_int(request.form.get("permit_id")),
            supplier_inv_no=request.form.get("supplier_inv_no", "").strip() or None,
            supplier_inv_date=_to_date(request.form.get("supplier_inv_date")),
            unit_price=_to_float(request.form.get("unit_price")),
            currency=request.form.get("currency", "").strip() or None,
            total_inv_amount=_to_float(request.form.get("total_inv_amount")),
            packing=request.form.get("packing", "").strip() or None,
            remarks=request.form.get("remarks", "").strip() or None,
            entry_date=_to_date(request.form.get("entry_date")) or date.today(),
            notes=request.form.get("notes", "").strip() or None,
            created_by=current_user.id,
        )
        db.session.add(sf)
        db.session.flush()

        # Containers
        container_nos = request.form.getlist("container_no[]")
        container_qtys = request.form.getlist("container_qty[]")
        container_uoms = request.form.getlist("container_uom[]")
        container_packings = request.form.getlist("container_packing[]")
        container_seals = request.form.getlist("container_seal[]")

        for idx in range(len(container_nos)):
            cno = container_nos[idx].strip() if idx < len(container_nos) else ""
            if not cno:
                continue
            container = ShipmentContainer(
                shipment_id=sf.id,
                container_no=cno,
                qty=_to_float(container_qtys[idx]) if idx < len(container_qtys) else None,
                uom=container_uoms[idx].strip() if idx < len(container_uoms) else None,
                packing=container_packings[idx].strip() if idx < len(container_packings) else None,
                seal_no=container_seals[idx].strip() if idx < len(container_seals) else None,
                clearance_status="Incoming",
            )
            db.session.add(container)

        db.session.commit()
        flash("Shipment File created successfully.", "success")
        return redirect(url_for("scs.shipment_detail", sid=sf.id))

    # GET — render form
    pos = PurchaseOrder.query.order_by(PurchaseOrder.po_number).all()
    return render_template(
        "scs/sf_form.html",
        sf=None,
        pos=pos,
        suppliers=Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all(),
        products=Product.query.filter_by(is_active=True).order_by(Product.name).all(),
        customers=Customer.query.filter_by(is_active=True).order_by(Customer.name).all(),
        brokers=Broker.query.filter_by(is_active=True).order_by(Broker.name).all(),
        permits=Permit.query.filter_by(is_active=True).order_by(Permit.permit_no).all(),
        shipping_lines=ShippingLine.query.filter_by(is_active=True).order_by(ShippingLine.name).all(),
        pods=PortOfDestination.query.filter_by(is_active=True).order_by(PortOfDestination.name).all(),
        uoms=UnitOfMeasure.query.filter_by(is_active=True).order_by(UnitOfMeasure.name).all(),
        packing_types=PackingType.query.filter_by(is_active=True).order_by(PackingType.name).all(),
        currencies=Currency.query.filter_by(is_active=True).order_by(Currency.code).all(),
    )


# ── Shipment Files — Edit ─────────────────────────────────────────

@bp.route("/shipments/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def shipment_edit(sid):
    from models import (
        ShipmentFile, ShipmentContainer, PurchaseOrder,
        Supplier, Product, Customer, Broker, Permit,
        ShippingLine, PortOfDestination, UnitOfMeasure, PackingType,
        Currency,
    )

    sf = db.session.get(ShipmentFile, sid)
    if not sf:
        abort(404)

    if request.method == "POST":
        sf.sf_number = request.form.get("sf_number", "").strip() or None
        sf.po_id = _to_int(request.form.get("po_id"))
        sf.po_item_no = _to_int(request.form.get("po_item_no"))
        sf.supplier_id = _to_int(request.form.get("supplier_id"))
        sf.supplier_name = request.form.get("supplier_name", "").strip() or None
        sf.product_id = _to_int(request.form.get("product_id"))
        sf.product_name = request.form.get("product_name", "").strip() or None
        sf.bol_no = request.form.get("bol_no", "").strip() or None
        sf.bol_date = _to_date(request.form.get("bol_date"))
        sf.shipping_line_id = _to_int(request.form.get("shipping_line_id"))
        sf.etd = _to_date(request.form.get("etd"))
        sf.eta = _to_date(request.form.get("eta"))
        sf.actual_arrival = _to_date(request.form.get("actual_arrival"))
        sf.port_of_destination_id = _to_int(request.form.get("port_of_destination_id"))
        sf.port_of_destination_name = request.form.get("port_of_destination_name", "").strip() or None
        sf.status = request.form.get("status", sf.status)
        sf.intended_customer_id = _to_int(request.form.get("intended_customer_id"))
        sf.broker_id = _to_int(request.form.get("broker_id"))
        sf.permit_id = _to_int(request.form.get("permit_id"))
        sf.supplier_inv_no = request.form.get("supplier_inv_no", "").strip() or None
        sf.supplier_inv_date = _to_date(request.form.get("supplier_inv_date"))
        sf.unit_price = _to_float(request.form.get("unit_price"))
        sf.currency = request.form.get("currency", "").strip() or None
        sf.total_inv_amount = _to_float(request.form.get("total_inv_amount"))
        sf.packing = request.form.get("packing", "").strip() or None
        sf.remarks = request.form.get("remarks", "").strip() or None
        sf.entry_date = _to_date(request.form.get("entry_date"))
        sf.notes = request.form.get("notes", "").strip() or None

        # Delete old containers and recreate
        ShipmentContainer.query.filter_by(shipment_id=sf.id).delete()
        db.session.flush()

        container_nos = request.form.getlist("container_no[]")
        container_qtys = request.form.getlist("container_qty[]")
        container_uoms = request.form.getlist("container_uom[]")
        container_packings = request.form.getlist("container_packing[]")
        container_seals = request.form.getlist("container_seal[]")

        for idx in range(len(container_nos)):
            cno = container_nos[idx].strip() if idx < len(container_nos) else ""
            if not cno:
                continue
            container = ShipmentContainer(
                shipment_id=sf.id,
                container_no=cno,
                qty=_to_float(container_qtys[idx]) if idx < len(container_qtys) else None,
                uom=container_uoms[idx].strip() if idx < len(container_uoms) else None,
                packing=container_packings[idx].strip() if idx < len(container_packings) else None,
                seal_no=container_seals[idx].strip() if idx < len(container_seals) else None,
                clearance_status="Incoming",
            )
            db.session.add(container)

        db.session.commit()
        flash("Shipment File updated successfully.", "success")
        return redirect(url_for("scs.shipment_detail", sid=sf.id))

    # GET — render form pre-filled
    pos = PurchaseOrder.query.order_by(PurchaseOrder.po_number).all()
    return render_template(
        "scs/sf_form.html",
        sf=sf,
        pos=pos,
        suppliers=Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all(),
        products=Product.query.filter_by(is_active=True).order_by(Product.name).all(),
        customers=Customer.query.filter_by(is_active=True).order_by(Customer.name).all(),
        brokers=Broker.query.filter_by(is_active=True).order_by(Broker.name).all(),
        permits=Permit.query.filter_by(is_active=True).order_by(Permit.permit_no).all(),
        shipping_lines=ShippingLine.query.filter_by(is_active=True).order_by(ShippingLine.name).all(),
        pods=PortOfDestination.query.filter_by(is_active=True).order_by(PortOfDestination.name).all(),
        uoms=UnitOfMeasure.query.filter_by(is_active=True).order_by(UnitOfMeasure.name).all(),
        packing_types=PackingType.query.filter_by(is_active=True).order_by(PackingType.name).all(),
        currencies=Currency.query.filter_by(is_active=True).order_by(Currency.code).all(),
    )


# ── Shipment Files — Update Clearance ─────────────────────────────

@bp.route("/shipments/<int:sid>/clearance", methods=["POST"])
@login_required
def shipment_clearance(sid):
    from models import ShipmentFile, ShipmentContainer, StorageLocation

    sf = db.session.get(ShipmentFile, sid)
    if not sf:
        abort(404)

    container_ids = request.form.getlist("container_id[]")
    clearance_statuses = request.form.getlist("clearance_status[]")
    clearance_dates = request.form.getlist("clearance_date[]")
    storage_ids = request.form.getlist("storage_location_id[]")
    gr_nos = request.form.getlist("gr_no[]")
    gr_dates = request.form.getlist("gr_date[]")

    updated = 0
    for idx in range(len(container_ids)):
        cid = _to_int(container_ids[idx])
        if not cid:
            continue

        container = db.session.get(ShipmentContainer, cid)
        if not container or container.shipment_id != sf.id:
            continue

        container.clearance_status = clearance_statuses[idx] if idx < len(clearance_statuses) else container.clearance_status
        container.clearance_date = _to_date(clearance_dates[idx]) if idx < len(clearance_dates) else container.clearance_date
        container.storage_location_id = _to_int(storage_ids[idx]) if idx < len(storage_ids) else container.storage_location_id
        container.gr_no = gr_nos[idx].strip() if idx < len(gr_nos) and gr_nos[idx].strip() else container.gr_no
        container.gr_date = _to_date(gr_dates[idx]) if idx < len(gr_dates) else container.gr_date

        # Auto-fill storage location name
        if container.storage_location_id:
            sl = db.session.get(StorageLocation, container.storage_location_id)
            container.storage_location_name = sl.name if sl else None

        updated += 1

    # Auto-update SF status if all containers cleared
    all_cleared = all(c.clearance_status == "Cleared" for c in sf.containers) if sf.containers else False
    if all_cleared and sf.status != "Cleared":
        sf.status = "Cleared"

    db.session.commit()
    flash(f"Updated clearance for {updated} container(s).", "success")
    return redirect(url_for("scs.shipment_detail", sid=sf.id))


# ── Shipment Files — Status Update ────────────────────────────────

@bp.route("/shipments/<int:sid>/status", methods=["POST"])
@login_required
def shipment_update_status(sid):
    from models import ShipmentFile

    sf = db.session.get(ShipmentFile, sid)
    if not sf:
        abort(404)

    new_status = request.form.get("status", "").strip()
    if new_status in ("Ordered", "Incoming", "Cleared", "Canceled"):
        sf.status = new_status
        db.session.commit()
        flash(f"Shipment status updated to {new_status}.", "success")
    else:
        flash("Invalid status.", "error")

    return redirect(url_for("scs.shipment_detail", sid=sf.id))


# ── Customer POs — List ───────────────────────────────────────────

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


# ── Customer PO — New ─────────────────────────────────────────────

@bp.route("/customer-pos/new", methods=["GET", "POST"])
@login_required
def customer_po_new():
    from models import (
        CustomerPO, CustomerPOItem, Customer, CustomerAddress,
        Product, UnitOfMeasure, Currency, DeliveryTerm, PaymentTermCustomer,
        PackingType,
    )

    if request.method == "POST":
        customer_id = _to_int(request.form.get("customer_id"))
        customer_name = None
        if customer_id:
            cust = db.session.get(Customer, customer_id)
            customer_name = cust.name if cust else None

        cpo = CustomerPO(
            po_no=request.form.get("po_no", "").strip() or None,
            customer_id=customer_id,
            customer_name=customer_name,
            po_date=_to_date(request.form.get("po_date")),
            po_issued_to=request.form.get("po_issued_to", "").strip() or None,
            delivery_terms_id=_to_int(request.form.get("delivery_terms_id")),
            payment_terms_id=_to_int(request.form.get("payment_terms_id")),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(cpo)
        db.session.flush()

        # Line items
        product_ids = request.form.getlist("product_id[]")
        affiliate_ids = request.form.getlist("affiliate_id[]")
        qtys = request.form.getlist("qty[]")
        uoms = request.form.getlist("uom[]")
        unit_prices = request.form.getlist("unit_price[]")
        currencies = request.form.getlist("currency[]")
        vat_pcts = request.form.getlist("vat_percent[]")
        packings = request.form.getlist("packing[]")
        delivery_dates = request.form.getlist("delivery_date[]")
        so_numbers = request.form.getlist("so_number[]")
        contract_nos = request.form.getlist("contract_no[]")
        item_remarks = request.form.getlist("item_remarks[]")

        for idx in range(len(product_ids)):
            pid = _to_int(product_ids[idx])
            prod_name = None
            if pid:
                prod = db.session.get(Product, pid)
                prod_name = prod.name if prod else None

            qty_val = _to_float(qtys[idx]) if idx < len(qtys) else None
            price_val = _to_float(unit_prices[idx]) if idx < len(unit_prices) else None
            vat_pct = _to_float(vat_pcts[idx]) if idx < len(vat_pcts) else 0
            vat_pct = vat_pct or 0

            total_val = (qty_val or 0) * (price_val or 0) if (qty_val and price_val) else None
            vat_val = (total_val or 0) * vat_pct / 100 if total_val else 0
            total_inc_vat = (total_val or 0) + vat_val if total_val else None

            item = CustomerPOItem(
                customer_po_id=cpo.id,
                item_no=idx + 1,
                product_id=pid,
                product_name=prod_name,
                affiliate_id=_to_int(affiliate_ids[idx]) if idx < len(affiliate_ids) else None,
                qty=qty_val,
                uom=uoms[idx] if idx < len(uoms) else None,
                unit_price=price_val,
                currency=currencies[idx] if idx < len(currencies) else None,
                vat_percent=vat_pct,
                vat_value=vat_val,
                total_value=total_val,
                total_value_inc_vat=total_inc_vat,
                packing=packings[idx] if idx < len(packings) else None,
                delivery_date=_to_date(delivery_dates[idx]) if idx < len(delivery_dates) else None,
                so_number=so_numbers[idx].strip() if idx < len(so_numbers) else None,
                contract_no=contract_nos[idx].strip() if idx < len(contract_nos) else None,
                remarks=item_remarks[idx].strip() if idx < len(item_remarks) else None,
            )
            db.session.add(item)

        db.session.commit()
        flash("Customer PO created successfully.", "success")
        return redirect(url_for("scs.customer_po_detail", cpo_id=cpo.id))

    # GET — build dropdown data
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    customer_addresses = {}
    for c in customers:
        customer_addresses[c.id] = [
            {"id": a.id, "label": a.plant or a.address_line1 or f"Address #{a.id}"}
            for a in c.addresses
        ]

    return render_template(
        "scs/customer_po_form.html",
        cpo=None,
        customers=customers,
        customer_addresses=customer_addresses,
        products=Product.query.filter_by(is_active=True).order_by(Product.name).all(),
        uoms=UnitOfMeasure.query.filter_by(is_active=True).order_by(UnitOfMeasure.name).all(),
        currencies=Currency.query.filter_by(is_active=True).order_by(Currency.code).all(),
        delivery_terms=DeliveryTerm.query.filter_by(is_active=True).order_by(DeliveryTerm.name).all(),
        payment_terms=PaymentTermCustomer.query.filter_by(is_active=True).order_by(PaymentTermCustomer.name).all(),
        packing_types=PackingType.query.filter_by(is_active=True).order_by(PackingType.name).all(),
    )


# ── Customer PO — Detail ──────────────────────────────────────────

@bp.route("/customer-pos/<int:cpo_id>")
@login_required
def customer_po_detail(cpo_id):
    from models import CustomerPO, DeliveryNoteItem, DeliveryNote

    cpo = db.session.get(CustomerPO, cpo_id)
    if not cpo:
        abort(404)

    items_data = []
    for item in cpo.items:
        delivered_qty = (
            db.session.query(func.coalesce(func.sum(DeliveryNoteItem.qty), 0))
            .join(DeliveryNote, DeliveryNoteItem.delivery_note_id == DeliveryNote.id)
            .filter(DeliveryNote.customer_po_id == cpo.id)
            .filter(DeliveryNoteItem.product_id == item.product_id)
            .scalar()
        ) or 0

        balance = (item.qty or 0) - delivered_qty
        pct_delivered = (delivered_qty / item.qty * 100) if item.qty and item.qty > 0 else 0

        items_data.append({
            "item": item,
            "delivered_qty": delivered_qty,
            "balance_qty": balance,
            "pct_delivered": min(pct_delivered, 100),
        })

    return render_template("scs/customer_po_detail.html", cpo=cpo, items_data=items_data)


# ── Customer PO — Edit ────────────────────────────────────────────

@bp.route("/customer-pos/<int:cpo_id>/edit", methods=["GET", "POST"])
@login_required
def customer_po_edit(cpo_id):
    from models import (
        CustomerPO, CustomerPOItem, Customer, CustomerAddress,
        Product, UnitOfMeasure, Currency, DeliveryTerm, PaymentTermCustomer,
        PackingType,
    )

    cpo = db.session.get(CustomerPO, cpo_id)
    if not cpo:
        abort(404)

    if request.method == "POST":
        customer_id = _to_int(request.form.get("customer_id"))
        customer_name = None
        if customer_id:
            cust = db.session.get(Customer, customer_id)
            customer_name = cust.name if cust else None

        cpo.po_no = request.form.get("po_no", "").strip() or None
        cpo.customer_id = customer_id
        cpo.customer_name = customer_name
        cpo.po_date = _to_date(request.form.get("po_date"))
        cpo.po_issued_to = request.form.get("po_issued_to", "").strip() or None
        cpo.delivery_terms_id = _to_int(request.form.get("delivery_terms_id"))
        cpo.payment_terms_id = _to_int(request.form.get("payment_terms_id"))
        cpo.is_closed = request.form.get("is_closed") == "1"
        cpo.notes = request.form.get("notes", "").strip() or None

        CustomerPOItem.query.filter_by(customer_po_id=cpo.id).delete()
        db.session.flush()

        product_ids = request.form.getlist("product_id[]")
        affiliate_ids = request.form.getlist("affiliate_id[]")
        qtys = request.form.getlist("qty[]")
        uoms = request.form.getlist("uom[]")
        unit_prices = request.form.getlist("unit_price[]")
        currencies = request.form.getlist("currency[]")
        vat_pcts = request.form.getlist("vat_percent[]")
        packings = request.form.getlist("packing[]")
        delivery_dates = request.form.getlist("delivery_date[]")
        so_numbers = request.form.getlist("so_number[]")
        contract_nos = request.form.getlist("contract_no[]")
        item_remarks = request.form.getlist("item_remarks[]")

        for idx in range(len(product_ids)):
            pid = _to_int(product_ids[idx])
            prod_name = None
            if pid:
                prod = db.session.get(Product, pid)
                prod_name = prod.name if prod else None

            qty_val = _to_float(qtys[idx]) if idx < len(qtys) else None
            price_val = _to_float(unit_prices[idx]) if idx < len(unit_prices) else None
            vat_pct = _to_float(vat_pcts[idx]) if idx < len(vat_pcts) else 0
            vat_pct = vat_pct or 0

            total_val = (qty_val or 0) * (price_val or 0) if (qty_val and price_val) else None
            vat_val = (total_val or 0) * vat_pct / 100 if total_val else 0
            total_inc_vat = (total_val or 0) + vat_val if total_val else None

            item = CustomerPOItem(
                customer_po_id=cpo.id,
                item_no=idx + 1,
                product_id=pid,
                product_name=prod_name,
                affiliate_id=_to_int(affiliate_ids[idx]) if idx < len(affiliate_ids) else None,
                qty=qty_val,
                uom=uoms[idx] if idx < len(uoms) else None,
                unit_price=price_val,
                currency=currencies[idx] if idx < len(currencies) else None,
                vat_percent=vat_pct,
                vat_value=vat_val,
                total_value=total_val,
                total_value_inc_vat=total_inc_vat,
                packing=packings[idx] if idx < len(packings) else None,
                delivery_date=_to_date(delivery_dates[idx]) if idx < len(delivery_dates) else None,
                so_number=so_numbers[idx].strip() if idx < len(so_numbers) else None,
                contract_no=contract_nos[idx].strip() if idx < len(contract_nos) else None,
                remarks=item_remarks[idx].strip() if idx < len(item_remarks) else None,
            )
            db.session.add(item)

        db.session.commit()
        flash("Customer PO updated successfully.", "success")
        return redirect(url_for("scs.customer_po_detail", cpo_id=cpo.id))

    # GET — build dropdown data
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    customer_addresses = {}
    for c in customers:
        customer_addresses[c.id] = [
            {"id": a.id, "label": a.plant or a.address_line1 or f"Address #{a.id}"}
            for a in c.addresses
        ]

    return render_template(
        "scs/customer_po_form.html",
        cpo=cpo,
        customers=customers,
        customer_addresses=customer_addresses,
        products=Product.query.filter_by(is_active=True).order_by(Product.name).all(),
        uoms=UnitOfMeasure.query.filter_by(is_active=True).order_by(UnitOfMeasure.name).all(),
        currencies=Currency.query.filter_by(is_active=True).order_by(Currency.code).all(),
        delivery_terms=DeliveryTerm.query.filter_by(is_active=True).order_by(DeliveryTerm.name).all(),
        payment_terms=PaymentTermCustomer.query.filter_by(is_active=True).order_by(PaymentTermCustomer.name).all(),
        packing_types=PackingType.query.filter_by(is_active=True).order_by(PackingType.name).all(),
    )


# ── Payment Tracking ─────────────────────────────────────────────

@bp.route("/payments")
@login_required
def payments():
    from models import PurchaseOrder, PurchaseOrderItem, Supplier, Product

    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    pay_filter = request.args.get("pay_status", "").strip()

    query = (
        db.session.query(PurchaseOrderItem)
        .join(PurchaseOrder, PurchaseOrderItem.po_id == PurchaseOrder.id)
        .outerjoin(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .outerjoin(Product, PurchaseOrderItem.product_id == Product.id)
    )

    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            PurchaseOrder.po_number.ilike(like),
            Supplier.name.ilike(like),
            Product.name.ilike(like),
        ))

    if pay_filter == "required":
        query = query.filter(or_(
            PurchaseOrderItem.first_payment_status == "Required",
            PurchaseOrderItem.second_payment_status == "Required",
        ))
    elif pay_filter == "done":
        query = query.filter(
            PurchaseOrderItem.first_payment_status == "Done",
            PurchaseOrderItem.second_payment_status == "Done",
        )

    query = query.order_by(PurchaseOrder.created_at.desc(), PurchaseOrderItem.item_no)
    pagination = query.paginate(page=page, per_page=50, error_out=False)

    return render_template(
        "scs/payments.html",
        items=pagination.items,
        pagination=pagination,
        search=search,
        pay_filter=pay_filter,
    )


# ── Permits ──────────────────────────────────────────────────────

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

    today = date.today()
    permits_data = []
    for p in pagination.items:
        remaining = (p.qty or 0) - (p.qty_used or 0)
        pct_used = ((p.qty_used or 0) / p.qty * 100) if p.qty and p.qty > 0 else 0
        pct_used = min(pct_used, 100)

        days_to_expiry = (p.expiry_date - today).days if p.expiry_date else None

        permits_data.append({
            "permit": p,
            "remaining": remaining,
            "pct_used": pct_used,
            "days_to_expiry": days_to_expiry,
        })

    return render_template(
        "scs/permits.html",
        permits_data=permits_data,
        pagination=pagination,
        search=search,
    )


# ── Permit — New ──────────────────────────────────────────────────

@bp.route("/permits/new", methods=["GET", "POST"])
@login_required
def permit_new():
    from models import Permit, Product, PermitRequirement

    if request.method == "POST":
        pid = _to_int(request.form.get("product_id"))
        prod_name = None
        if pid:
            prod = db.session.get(Product, pid)
            prod_name = prod.name if prod else None

        permit = Permit(
            permit_no=request.form.get("permit_no", "").strip() or None,
            product_id=pid,
            product_name=prod_name,
            hs_code=request.form.get("hs_code", "").strip() or None,
            name_in_customs=request.form.get("name_in_customs", "").strip() or None,
            permit_requirement_id=_to_int(request.form.get("permit_requirement_id")),
            duty_percent=_to_float(request.form.get("duty_percent")),
            qty=_to_float(request.form.get("qty")),
            qty_used=0,
            expiry_date=_to_date(request.form.get("expiry_date")),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(permit)
        db.session.commit()
        flash("Permit created successfully.", "success")
        return redirect(url_for("scs.permits"))

    return render_template(
        "scs/permit_form.html",
        permit=None,
        products=Product.query.filter_by(is_active=True).order_by(Product.name).all(),
        permit_requirements=PermitRequirement.query.filter_by(is_active=True).order_by(PermitRequirement.name).all(),
    )


# ── Permit — Edit ─────────────────────────────────────────────────

@bp.route("/permits/<int:permit_id>/edit", methods=["GET", "POST"])
@login_required
def permit_edit(permit_id):
    from models import Permit, Product, PermitRequirement

    permit = db.session.get(Permit, permit_id)
    if not permit:
        abort(404)

    if request.method == "POST":
        pid = _to_int(request.form.get("product_id"))
        prod_name = None
        if pid:
            prod = db.session.get(Product, pid)
            prod_name = prod.name if prod else None

        permit.permit_no = request.form.get("permit_no", "").strip() or None
        permit.product_id = pid
        permit.product_name = prod_name
        permit.hs_code = request.form.get("hs_code", "").strip() or None
        permit.name_in_customs = request.form.get("name_in_customs", "").strip() or None
        permit.permit_requirement_id = _to_int(request.form.get("permit_requirement_id"))
        permit.duty_percent = _to_float(request.form.get("duty_percent"))
        permit.qty = _to_float(request.form.get("qty"))
        permit.expiry_date = _to_date(request.form.get("expiry_date"))
        permit.notes = request.form.get("notes", "").strip() or None

        db.session.commit()
        flash("Permit updated successfully.", "success")
        return redirect(url_for("scs.permits"))

    return render_template(
        "scs/permit_form.html",
        permit=permit,
        products=Product.query.filter_by(is_active=True).order_by(Product.name).all(),
        permit_requirements=PermitRequirement.query.filter_by(is_active=True).order_by(PermitRequirement.name).all(),
    )


# ── API: PO Info for JS Auto-fill ─────────────────────────────────

@bp.route("/api/po/<int:po_id>")
@login_required
def api_po_info(po_id):
    """Return PO data as JSON for JS auto-fill in SF form."""
    from models import PurchaseOrder

    po = db.session.get(PurchaseOrder, po_id)
    if not po:
        return jsonify({}), 404

    items = []
    for item in po.items:
        items.append({
            "item_no": item.item_no,
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else None,
            "qty": item.qty,
            "uom": item.uom,
        })

    return jsonify({
        "po_number": po.po_number,
        "supplier_id": po.supplier_id,
        "supplier_name": po.supplier.name if po.supplier else None,
        "items": items,
    })


# ── API: Customer Affiliates for JS ───────────────────────────────

@bp.route("/api/customer/<int:customer_id>/affiliates")
@login_required
def api_customer_affiliates(customer_id):
    """Return customer affiliates (addresses) as JSON."""
    from models import Customer

    customer = db.session.get(Customer, customer_id)
    if not customer:
        return jsonify([]), 404

    affiliates = []
    for addr in customer.addresses:
        affiliates.append({
            "id": addr.id,
            "plant": addr.plant or "",
            "address_line1": addr.address_line1 or "",
            "address_line2": addr.address_line2 or "",
            "city": addr.city or "",
            "contact_person": addr.contact_person or "",
            "contact_phone": addr.contact_phone or "",
        })

    return jsonify(affiliates)


# ── API: Available Stock for Deliveries ────────────────────────────

@bp.route("/api/available-stock")
@login_required
def api_available_stock():
    """Return cleared containers with remaining qty for delivery creation."""
    from models import ShipmentContainer, ShipmentFile, DeliveryNoteItem

    customer_id = request.args.get("customer_id", type=int)

    query = (
        db.session.query(ShipmentContainer)
        .join(ShipmentFile, ShipmentContainer.shipment_id == ShipmentFile.id)
        .filter(ShipmentContainer.clearance_status == "Cleared")
    )

    if customer_id:
        query = query.filter(ShipmentFile.intended_customer_id == customer_id)

    containers = query.order_by(ShipmentFile.sf_number, ShipmentContainer.container_no).all()

    stock = []
    for c in containers:
        # Calculate delivered qty for this container
        delivered = db.session.query(func.coalesce(func.sum(DeliveryNoteItem.qty), 0)).filter(
            DeliveryNoteItem.shipment_container_id == c.id
        ).scalar()
        available = (c.qty or 0) - (delivered or 0)
        if available <= 0:
            continue

        stock.append({
            "container_id": c.id,
            "sf_number": c.shipment.sf_number if c.shipment else "",
            "container_no": c.container_no or "",
            "product_id": c.shipment.product_id if c.shipment else None,
            "product_name": c.shipment.product_name if c.shipment else "",
            "available_qty": round(available, 3),
            "uom": c.uom or "",
            "storage_location_id": c.storage_location_id,
            "storage_location": c.storage_location_name or (c.storage_location.name if c.storage_location else ""),
        })

    return jsonify(stock)
