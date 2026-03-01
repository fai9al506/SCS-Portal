from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import or_
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


# ── Lookups ─────────────────────────────────────────────────────────

@bp.route("/lookups")
@login_required
@manager_required
def lookups():
    from models import (Broker, Transporter, StorageLocation,
                        ShippingLine, PortOfDestination, ReturnTerminal,
                        ProductCategory, Currency)
    return render_template("manage/lookups.html",
        brokers=Broker.query.order_by(Broker.name).all(),
        transporters=Transporter.query.order_by(Transporter.name).all(),
        storage_locations=StorageLocation.query.order_by(StorageLocation.name).all(),
        shipping_lines=ShippingLine.query.order_by(ShippingLine.name).all(),
        ports=PortOfDestination.query.order_by(PortOfDestination.name).all(),
        return_terminals=ReturnTerminal.query.order_by(ReturnTerminal.name).all(),
        product_categories=ProductCategory.query.order_by(ProductCategory.name).all(),
        currencies=Currency.query.order_by(Currency.code).all(),
    )


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
