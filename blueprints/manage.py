from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from extensions import db

bp = Blueprint("manage", __name__, url_prefix="/manage")


def manager_required(f):
    """Require Admin or Manager role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role not in ("Admin", "Manager"):
            flash("Access denied.", "error")
            return redirect(url_for("scs.dashboard"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Require Admin role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != "Admin":
            flash("Access denied.", "error")
            return redirect(url_for("scs.dashboard"))
        return f(*args, **kwargs)
    return decorated


# ── Lookup type registry ───────────────────────────────────────────
# Maps URL slug -> (model_name, display_name, field_list)
# field_list defines the form fields for each lookup type.

LOOKUP_TYPES = {
    "brokers": ("Broker", "Broker", [
        ("name", "Name", "text", True),
        ("full_name", "Full Name", "text", False),
        ("email", "Email", "text", False),
        ("phone", "Phone", "text", False),
    ]),
    "transporters": ("Transporter", "Transporter", [
        ("name", "Name", "text", True),
        ("email", "Email", "text", False),
        ("phone", "Phone", "text", False),
    ]),
    "storage_locations": ("StorageLocation", "Storage Location", [
        ("name", "Name", "text", True),
        ("email", "Email", "text", False),
    ]),
    "shipping_lines": ("ShippingLine", "Shipping Line", [
        ("name", "Name", "text", True),
    ]),
    "ports": ("PortOfDestination", "Port of Destination", [
        ("name", "Name", "text", True),
    ]),
    "return_terminals": ("ReturnTerminal", "Return Terminal", [
        ("name", "Name", "text", True),
    ]),
    "product_categories": ("ProductCategory", "Product Category", [
        ("name", "Name", "text", True),
    ]),
    "currencies": ("Currency", "Currency", [
        ("code", "Code", "text", True),
        ("name", "Name", "text", False),
    ]),
    "packing_types": ("PackingType", "Packing Type", [
        ("name", "Name", "text", True),
    ]),
    "payment_terms_supplier": ("PaymentTermSupplier", "Payment Terms (Supplier)", [
        ("name", "Name", "text", True),
    ]),
    "payment_terms_customer": ("PaymentTermCustomer", "Payment Terms (Customer)", [
        ("name", "Name", "text", True),
    ]),
    "delivery_terms": ("DeliveryTerm", "Delivery Term", [
        ("name", "Name", "text", True),
    ]),
    "permit_requirements": ("PermitRequirement", "Permit Requirement", [
        ("name", "Name", "text", True),
    ]),
    "uom": ("UnitOfMeasure", "Unit of Measure", [
        ("name", "Name", "text", True),
    ]),
}


def _get_lookup_model(type_slug):
    """Return the SQLAlchemy model class for a lookup type slug."""
    import models as m
    info = LOOKUP_TYPES.get(type_slug)
    if not info:
        return None, None
    model_cls = getattr(m, info[0], None)
    return model_cls, info


# ── Products ────────────────────────────────────────────────────────

@bp.route("/products")
@login_required
@manager_required
def products():
    from models import Product
    search = request.args.get("q", "").strip()
    query = Product.query
    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            Product.name.ilike(like),
            Product.sap_code.ilike(like),
        ))
    items = query.order_by(Product.name).all()
    return render_template("manage/products.html", products=items, search=search)


@bp.route("/products/new", methods=["GET", "POST"])
@login_required
@manager_required
def product_new():
    from models import Product, ProductCategory
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sap_code = request.form.get("sap_code", "").strip() or None
        category_id = request.form.get("category_id", type=int) or None

        if not name:
            flash("Product name is required.", "error")
            categories = ProductCategory.query.order_by(ProductCategory.name).all()
            return render_template("manage/product_form.html", product=None, categories=categories)

        product = Product(name=name, sap_code=sap_code, category_id=category_id)
        db.session.add(product)
        db.session.commit()
        flash(f"Product '{name}' created.", "success")
        return redirect(url_for("manage.products"))

    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    return render_template("manage/product_form.html", product=None, categories=categories)


@bp.route("/products/<int:id>/edit", methods=["GET", "POST"])
@login_required
@manager_required
def product_edit(id):
    from models import Product, ProductCategory
    product = Product.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sap_code = request.form.get("sap_code", "").strip() or None
        category_id = request.form.get("category_id", type=int) or None

        if not name:
            flash("Product name is required.", "error")
            categories = ProductCategory.query.order_by(ProductCategory.name).all()
            return render_template("manage/product_form.html", product=product, categories=categories)

        product.name = name
        product.sap_code = sap_code
        product.category_id = category_id
        db.session.commit()
        flash(f"Product '{name}' updated.", "success")
        return redirect(url_for("manage.products"))

    categories = ProductCategory.query.order_by(ProductCategory.name).all()
    return render_template("manage/product_form.html", product=product, categories=categories)


@bp.route("/products/<int:id>/delete", methods=["POST"])
@login_required
@manager_required
def product_delete(id):
    from models import Product
    product = Product.query.get_or_404(id)
    product.is_active = False
    db.session.commit()
    flash(f"Product '{product.name}' deactivated.", "success")
    return redirect(url_for("manage.products"))


# ── Suppliers ───────────────────────────────────────────────────────

@bp.route("/suppliers")
@login_required
@manager_required
def suppliers():
    from models import Supplier
    search = request.args.get("q", "").strip()
    query = Supplier.query
    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            Supplier.name.ilike(like),
            Supplier.sap_no.ilike(like),
            Supplier.email.ilike(like),
        ))
    items = query.order_by(Supplier.name).all()
    return render_template("manage/suppliers.html", suppliers=items, search=search)


@bp.route("/suppliers/new", methods=["GET", "POST"])
@login_required
@manager_required
def supplier_new():
    from models import Supplier
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sap_no = request.form.get("sap_no", "").strip() or None
        address = request.form.get("address", "").strip() or None
        phone = request.form.get("phone", "").strip() or None
        email = request.form.get("email", "").strip() or None
        contact_person = request.form.get("contact_person", "").strip() or None

        if not name:
            flash("Supplier name is required.", "error")
            return render_template("manage/supplier_form.html", supplier=None)

        supplier = Supplier(name=name, sap_no=sap_no, address=address,
                            phone=phone, email=email, contact_person=contact_person)
        db.session.add(supplier)
        db.session.commit()
        flash(f"Supplier '{name}' created.", "success")
        return redirect(url_for("manage.suppliers"))

    return render_template("manage/supplier_form.html", supplier=None)


@bp.route("/suppliers/<int:id>/edit", methods=["GET", "POST"])
@login_required
@manager_required
def supplier_edit(id):
    from models import Supplier
    supplier = Supplier.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sap_no = request.form.get("sap_no", "").strip() or None
        address = request.form.get("address", "").strip() or None
        phone = request.form.get("phone", "").strip() or None
        email = request.form.get("email", "").strip() or None
        contact_person = request.form.get("contact_person", "").strip() or None

        if not name:
            flash("Supplier name is required.", "error")
            return render_template("manage/supplier_form.html", supplier=supplier)

        supplier.name = name
        supplier.sap_no = sap_no
        supplier.address = address
        supplier.phone = phone
        supplier.email = email
        supplier.contact_person = contact_person
        db.session.commit()
        flash(f"Supplier '{name}' updated.", "success")
        return redirect(url_for("manage.suppliers"))

    return render_template("manage/supplier_form.html", supplier=supplier)


@bp.route("/suppliers/<int:id>/delete", methods=["POST"])
@login_required
@manager_required
def supplier_delete(id):
    from models import Supplier
    supplier = Supplier.query.get_or_404(id)
    try:
        supplier.is_active = False
        db.session.commit()
        flash(f"Supplier '{supplier.name}' deactivated.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not deactivate supplier.", "error")
    return redirect(url_for("manage.suppliers"))


# ── Customers ───────────────────────────────────────────────────────

@bp.route("/customers")
@login_required
@manager_required
def customers():
    from models import Customer
    search = request.args.get("q", "").strip()
    query = Customer.query
    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            Customer.name.ilike(like),
            Customer.sap_id.ilike(like),
        ))
    items = query.order_by(Customer.name).all()
    return render_template("manage/customers.html", customers=items, search=search)


@bp.route("/customers/new", methods=["GET", "POST"])
@login_required
@manager_required
def customer_new():
    from models import Customer
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sap_id = request.form.get("sap_id", "").strip() or None

        if not name:
            flash("Customer name is required.", "error")
            return render_template("manage/customer_form.html", customer=None)

        customer = Customer(name=name, sap_id=sap_id)
        db.session.add(customer)
        db.session.commit()
        flash(f"Customer '{name}' created.", "success")
        return redirect(url_for("manage.customer_edit", id=customer.id))

    return render_template("manage/customer_form.html", customer=None)


@bp.route("/customers/<int:id>/edit", methods=["GET", "POST"])
@login_required
@manager_required
def customer_edit(id):
    from models import Customer
    customer = Customer.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sap_id = request.form.get("sap_id", "").strip() or None

        if not name:
            flash("Customer name is required.", "error")
            return render_template("manage/customer_form.html", customer=customer)

        customer.name = name
        customer.sap_id = sap_id
        db.session.commit()
        flash(f"Customer '{name}' updated.", "success")
        return render_template("manage/customer_form.html", customer=customer)

    return render_template("manage/customer_form.html", customer=customer)


@bp.route("/customers/<int:id>/delete", methods=["POST"])
@login_required
@manager_required
def customer_delete(id):
    from models import Customer
    customer = Customer.query.get_or_404(id)
    try:
        customer.is_active = False
        db.session.commit()
        flash(f"Customer '{customer.name}' deactivated.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not deactivate customer.", "error")
    return redirect(url_for("manage.customers"))


# ── Customer Addresses ──────────────────────────────────────────────

@bp.route("/customers/<int:cid>/addresses/new", methods=["POST"])
@login_required
@manager_required
def customer_address_new(cid):
    from models import Customer, CustomerAddress
    customer = Customer.query.get_or_404(cid)

    addr = CustomerAddress(
        customer_id=cid,
        plant=request.form.get("plant", "").strip() or None,
        address_line1=request.form.get("address_line1", "").strip() or None,
        address_line2=request.form.get("address_line2", "").strip() or None,
        city=request.form.get("city", "").strip() or None,
        contact_person=request.form.get("contact_person", "").strip() or None,
        contact_phone=request.form.get("contact_phone", "").strip() or None,
        contact_email=request.form.get("contact_email", "").strip() or None,
    )
    db.session.add(addr)
    db.session.commit()
    flash("Address added.", "success")
    return redirect(url_for("manage.customer_edit", id=cid))


@bp.route("/customers/<int:cid>/addresses/<int:aid>/edit", methods=["POST"])
@login_required
@manager_required
def customer_address_edit(cid, aid):
    from models import CustomerAddress
    addr = CustomerAddress.query.get_or_404(aid)
    if addr.customer_id != cid:
        flash("Address not found.", "error")
        return redirect(url_for("manage.customer_edit", id=cid))

    addr.plant = request.form.get("plant", "").strip() or None
    addr.address_line1 = request.form.get("address_line1", "").strip() or None
    addr.address_line2 = request.form.get("address_line2", "").strip() or None
    addr.city = request.form.get("city", "").strip() or None
    addr.contact_person = request.form.get("contact_person", "").strip() or None
    addr.contact_phone = request.form.get("contact_phone", "").strip() or None
    addr.contact_email = request.form.get("contact_email", "").strip() or None
    db.session.commit()
    flash("Address updated.", "success")
    return redirect(url_for("manage.customer_edit", id=cid))


@bp.route("/customers/<int:cid>/addresses/<int:aid>/delete", methods=["POST"])
@login_required
@manager_required
def customer_address_delete(cid, aid):
    from models import CustomerAddress
    addr = CustomerAddress.query.get_or_404(aid)
    if addr.customer_id != cid:
        flash("Address not found.", "error")
        return redirect(url_for("manage.customer_edit", id=cid))

    try:
        db.session.delete(addr)
        db.session.commit()
        flash("Address deleted.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Cannot delete this address — it is referenced by other records.", "error")
    return redirect(url_for("manage.customer_edit", id=cid))


# ── Lookups ─────────────────────────────────────────────────────────

@bp.route("/lookups")
@login_required
@manager_required
def lookups():
    from models import (Broker, Transporter, StorageLocation,
                        ShippingLine, PortOfDestination, ReturnTerminal,
                        ProductCategory, Currency, PackingType,
                        PaymentTermSupplier, PaymentTermCustomer,
                        DeliveryTerm, PermitRequirement, UnitOfMeasure)
    return render_template("manage/lookups.html",
        brokers=Broker.query.order_by(Broker.name).all(),
        transporters=Transporter.query.order_by(Transporter.name).all(),
        storage_locations=StorageLocation.query.order_by(StorageLocation.name).all(),
        shipping_lines=ShippingLine.query.order_by(ShippingLine.name).all(),
        ports=PortOfDestination.query.order_by(PortOfDestination.name).all(),
        return_terminals=ReturnTerminal.query.order_by(ReturnTerminal.name).all(),
        product_categories=ProductCategory.query.order_by(ProductCategory.name).all(),
        currencies=Currency.query.order_by(Currency.code).all(),
        packing_types=PackingType.query.order_by(PackingType.name).all(),
        payment_terms_supplier=PaymentTermSupplier.query.order_by(PaymentTermSupplier.name).all(),
        payment_terms_customer=PaymentTermCustomer.query.order_by(PaymentTermCustomer.name).all(),
        delivery_terms=DeliveryTerm.query.order_by(DeliveryTerm.name).all(),
        permit_requirements=PermitRequirement.query.order_by(PermitRequirement.name).all(),
        uom=UnitOfMeasure.query.order_by(UnitOfMeasure.name).all(),
        lookup_types=LOOKUP_TYPES,
    )


@bp.route("/lookups/<type_slug>/add", methods=["POST"])
@login_required
@manager_required
def lookup_add(type_slug):
    model_cls, info = _get_lookup_model(type_slug)
    if not model_cls:
        flash("Unknown lookup type.", "error")
        return redirect(url_for("manage.lookups"))

    _, display_name, fields = info
    kwargs = {}
    for field_name, label, field_type, required in fields:
        val = request.form.get(field_name, "").strip()
        if required and not val:
            flash(f"{label} is required.", "error")
            return redirect(url_for("manage.lookups"))
        kwargs[field_name] = val or None

    try:
        item = model_cls(**kwargs)
        db.session.add(item)
        db.session.commit()
        flash(f"{display_name} added.", "success")
    except IntegrityError:
        db.session.rollback()
        flash(f"A {display_name.lower()} with that name already exists.", "error")

    return redirect(url_for("manage.lookups"))


@bp.route("/lookups/<type_slug>/<int:id>/toggle", methods=["POST"])
@login_required
@manager_required
def lookup_toggle(type_slug, id):
    model_cls, info = _get_lookup_model(type_slug)
    if not model_cls:
        flash("Unknown lookup type.", "error")
        return redirect(url_for("manage.lookups"))

    item = model_cls.query.get_or_404(id)
    item.is_active = not item.is_active
    db.session.commit()
    status = "activated" if item.is_active else "deactivated"
    flash(f"{info[1]} '{getattr(item, 'name', getattr(item, 'code', ''))}' {status}.", "success")
    return redirect(url_for("manage.lookups"))


@bp.route("/lookups/<type_slug>/<int:id>/delete", methods=["POST"])
@login_required
@manager_required
def lookup_delete(type_slug, id):
    model_cls, info = _get_lookup_model(type_slug)
    if not model_cls:
        flash("Unknown lookup type.", "error")
        return redirect(url_for("manage.lookups"))

    item = model_cls.query.get_or_404(id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash(f"{info[1]} deleted.", "success")
    except IntegrityError:
        db.session.rollback()
        flash(f"Cannot delete — this {info[1].lower()} is referenced by other records. Try deactivating instead.", "error")

    return redirect(url_for("manage.lookups"))


# ── Users ───────────────────────────────────────────────────────────

@bp.route("/users")
@login_required
@admin_required
def users():
    from models import User
    all_users = User.query.order_by(User.name).all()
    return render_template("manage/users.html", users=all_users)


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def user_new():
    if request.method == "POST":
        from models import User
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "Logistics")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("manage/user_form.html")

        if User.query.filter_by(email=email).first():
            flash("A user with this email already exists.", "error")
            return render_template("manage/user_form.html")

        user = User(name=name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f"User '{name}' created.", "success")
        return redirect(url_for("manage.users"))

    return render_template("manage/user_form.html")


# ── Audit Log ───────────────────────────────────────────────────────

@bp.route("/audit-log")
@login_required
@manager_required
def audit_log():
    from models import AuditLog
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(200).all()
    return render_template("manage/audit_log.html", logs=logs)
