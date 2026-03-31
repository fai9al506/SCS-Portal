import os
import json
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, jsonify, redirect, url_for, request
from config import Config
from extensions import db, migrate, login_manager, csrf

# Riyadh timezone (UTC+3)
RIYADH_TZ = timezone(timedelta(hours=3))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Fix Railway Postgres URL and use psycopg3 driver
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+psycopg://", 1)
    elif uri.startswith("postgresql://") and "+psycopg" not in uri:
        uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
    if uri != app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        app.config["SQLALCHEMY_DATABASE_URI"] = uri

    # Health check
    @app.route("/health")
    def health():
        return jsonify({"status": "healthy", "app": "scs-portal"}), 200

    # Jinja filters
    @app.template_filter('to_riyadh')
    def to_riyadh_filter(dt):
        if dt is None:
            return ''
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(RIYADH_TZ)

    @app.template_filter('riyadh_fmt')
    def riyadh_fmt_filter(dt, fmt='%d %b %Y, %H:%M'):
        if dt is None:
            return '\u2014'
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(RIYADH_TZ).strftime(fmt)

    @app.template_filter('date_fmt')
    def date_fmt_filter(d, fmt='%d %b %Y'):
        if d is None:
            return '\u2014'
        if isinstance(d, datetime):
            return d.strftime(fmt)
        return d.strftime(fmt)

    @app.template_filter('currency')
    def currency_filter(value, symbol=''):
        if value is None:
            return '\u2014'
        try:
            formatted = "{:,.2f}".format(float(value))
            return f"{symbol} {formatted}".strip() if symbol else formatted
        except (ValueError, TypeError):
            return '\u2014'

    @app.context_processor
    def inject_now():
        return {"now": datetime.utcnow}

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from blueprints.auth import bp as auth_bp
    from blueprints.scs import bp as scs_bp
    from blueprints.manage import bp as manage_bp
    from blueprints.po import bp as po_bp
    from blueprints.delivery import bp as delivery_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(scs_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(po_bp)
    app.register_blueprint(delivery_bp)

    # Root route
    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('scs.dashboard'))
        return redirect(url_for('auth.login'))

    # Auto-create tables and seed data
    with app.app_context():
        # Check if we need to reset the DB (old schema → new schema)
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        needs_reset = (
            ('shipment_files' in existing_tables and 'purchase_orders' not in existing_tables)
            or os.environ.get('RESET_DB') == 'true'
        )
        if needs_reset:
            print("Detected old schema — dropping all tables and recreating...")
            db.drop_all()
            print("Old tables dropped.")

        db.create_all()

        # Seed default admin user
        if User.query.count() == 0:
            admin = User(
                name="Admin",
                email="admin@modernpetro.com",
                role="Admin",
            )
            admin.set_password("MPC@2025!")
            db.session.add(admin)
            db.session.commit()
            print("Created default admin user")

        # Seed currencies
        from models import Currency
        try:
            if Currency.query.count() == 0:
                for code in ['USD', 'SAR', 'EUR', 'GBP', 'CNY', 'INR', 'AED']:
                    db.session.add(Currency(code=code))
                db.session.commit()
                print("Seeded currencies")
        except Exception as e:
            print(f"Seed warning (currencies): {e}")
            db.session.rollback()

        # ── Seed from Access master data JSON ──────────────────────
        _seed_from_access_data()

    return app


def _seed_from_access_data():
    """Seed lookup and master data tables from access_masterdata.json."""
    json_path = os.path.join(os.path.dirname(__file__), "access_masterdata.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print("Loaded access_masterdata.json")
    except FileNotFoundError:
        print("access_masterdata.json not found — skipping Access data seed")
        return
    except Exception as e:
        print(f"Error loading access_masterdata.json: {e}")
        return

    lookups = data.get("lookups", {})

    # ── Lookup Tables ──────────────────────────────────────────────

    from models import (
        PackingType, PaymentTermSupplier, PaymentTermCustomer,
        DeliveryTerm, PermitRequirement, UnitOfMeasure,
        ShippingLine, PortOfDestination, ReturnTerminal,
        StorageLocation, Broker, Transporter,
        ProductCategory, Product, Supplier, Customer, CustomerAddress,
    )

    # PackingType
    try:
        if PackingType.query.count() == 0:
            for name in lookups.get("packing_types", []):
                if name and name.strip():
                    db.session.add(PackingType(name=name.strip()))
            db.session.commit()
            print(f"Seeded packing_types ({PackingType.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (packing_types): {e}")
        db.session.rollback()

    # PaymentTermSupplier
    try:
        if PaymentTermSupplier.query.count() == 0:
            for name in lookups.get("payment_terms_supplier", []):
                if name and name.strip():
                    db.session.add(PaymentTermSupplier(name=name.strip()))
            db.session.commit()
            print(f"Seeded payment_terms_supplier ({PaymentTermSupplier.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (payment_terms_supplier): {e}")
        db.session.rollback()

    # PaymentTermCustomer
    try:
        if PaymentTermCustomer.query.count() == 0:
            for name in lookups.get("payment_terms_customer", []):
                if name and name.strip():
                    db.session.add(PaymentTermCustomer(name=name.strip()))
            db.session.commit()
            print(f"Seeded payment_terms_customer ({PaymentTermCustomer.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (payment_terms_customer): {e}")
        db.session.rollback()

    # DeliveryTerm
    try:
        if DeliveryTerm.query.count() == 0:
            for name in lookups.get("delivery_terms", []):
                if name and name.strip():
                    db.session.add(DeliveryTerm(name=name.strip()))
            db.session.commit()
            print(f"Seeded delivery_terms ({DeliveryTerm.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (delivery_terms): {e}")
        db.session.rollback()

    # PermitRequirement
    try:
        if PermitRequirement.query.count() == 0:
            for name in lookups.get("permit_requirements", []):
                if name and name.strip():
                    db.session.add(PermitRequirement(name=name.strip()))
            db.session.commit()
            print(f"Seeded permit_requirements ({PermitRequirement.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (permit_requirements): {e}")
        db.session.rollback()

    # UnitOfMeasure
    try:
        if UnitOfMeasure.query.count() == 0:
            for name in lookups.get("uom", []):
                if name and name.strip():
                    db.session.add(UnitOfMeasure(name=name.strip()))
            db.session.commit()
            print(f"Seeded units_of_measure ({UnitOfMeasure.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (units_of_measure): {e}")
        db.session.rollback()

    # ── Master Data Tables ─────────────────────────────────────────

    # ShippingLine (list of strings)
    try:
        if ShippingLine.query.count() == 0:
            for name in data.get("shipping_lines", []):
                if name and name.strip():
                    db.session.add(ShippingLine(name=name.strip()))
            db.session.commit()
            print(f"Seeded shipping_lines ({ShippingLine.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (shipping_lines): {e}")
        db.session.rollback()

    # PortOfDestination (from lookups)
    try:
        if PortOfDestination.query.count() == 0:
            for name in lookups.get("ports_of_destination", []):
                if name and name.strip():
                    db.session.add(PortOfDestination(name=name.strip()))
            db.session.commit()
            print(f"Seeded ports_of_destination ({PortOfDestination.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (ports_of_destination): {e}")
        db.session.rollback()

    # ReturnTerminal (top-level list of strings)
    try:
        if ReturnTerminal.query.count() == 0:
            for name in data.get("return_terminals", []):
                if name and name.strip():
                    db.session.add(ReturnTerminal(name=name.strip()))
            db.session.commit()
            print(f"Seeded return_terminals ({ReturnTerminal.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (return_terminals): {e}")
        db.session.rollback()

    # StorageLocation (list of dicts: name, emails)
    try:
        if StorageLocation.query.count() == 0:
            for item in data.get("storage_locations", []):
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                db.session.add(StorageLocation(
                    name=name,
                    email=item.get("emails"),
                ))
            db.session.commit()
            print(f"Seeded storage_locations ({StorageLocation.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (storage_locations): {e}")
        db.session.rollback()

    # Broker (list of dicts: name, full_name, address1, tel, emails)
    try:
        if Broker.query.count() == 0:
            for item in data.get("brokers", []):
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                db.session.add(Broker(
                    name=name,
                    full_name=item.get("full_name"),
                    address=item.get("address1"),
                    phone=item.get("tel"),
                    email=item.get("emails"),
                ))
            db.session.commit()
            print(f"Seeded brokers ({Broker.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (brokers): {e}")
        db.session.rollback()

    # Transporter (list of dicts: name, emails)
    try:
        if Transporter.query.count() == 0:
            for item in data.get("transporters", []):
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                db.session.add(Transporter(
                    name=name,
                    email=item.get("emails"),
                ))
            db.session.commit()
            print(f"Seeded transporters ({Transporter.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (transporters): {e}")
        db.session.rollback()

    # ProductCategory (from lookups.product_groups)
    try:
        if ProductCategory.query.count() == 0:
            for name in lookups.get("product_groups", []):
                if name and name.strip():
                    db.session.add(ProductCategory(name=name.strip()))
            db.session.commit()
            print(f"Seeded product_categories ({ProductCategory.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (product_categories): {e}")
        db.session.rollback()

    # Product (list of dicts: name, sap_code, group)
    # group is a string number like "1", "3", etc. — match to ProductCategory by position
    try:
        if Product.query.count() == 0:
            # Build group-name-to-id mapping
            product_groups = lookups.get("product_groups", [])
            group_map = {}  # "1" -> category_id, "2" -> category_id, etc.
            for idx, group_name in enumerate(product_groups, start=1):
                cat = ProductCategory.query.filter_by(name=group_name.strip()).first()
                if cat:
                    group_map[str(idx)] = cat.id

            for item in data.get("products", []):
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                category_id = group_map.get(item.get("group")) if item.get("group") else None
                db.session.add(Product(
                    name=name,
                    sap_code=item.get("sap_code"),
                    category_id=category_id,
                ))
            db.session.commit()
            print(f"Seeded products ({Product.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (products): {e}")
        db.session.rollback()

    # Supplier (list of dicts: name, sap_no)
    try:
        if Supplier.query.count() == 0:
            for item in data.get("suppliers", []):
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                db.session.add(Supplier(
                    name=name,
                    sap_no=item.get("sap_no"),
                ))
            db.session.commit()
            print(f"Seeded suppliers ({Supplier.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (suppliers): {e}")
        db.session.rollback()

    # Customer (list of dicts: name, sap_id)
    try:
        if Customer.query.count() == 0:
            for item in data.get("customers", []):
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                db.session.add(Customer(
                    name=name,
                    sap_id=item.get("sap_id"),
                ))
            db.session.commit()
            print(f"Seeded customers ({Customer.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (customers): {e}")
        db.session.rollback()

    # CustomerAddress (list of dicts: customer, plant, address1, address2, contact_name, contact_tel, contact_mob)
    try:
        if CustomerAddress.query.count() == 0:
            # Build customer name -> id lookup
            customer_lookup = {}
            for c in Customer.query.all():
                customer_lookup[c.name] = c.id

            for item in data.get("customer_addresses", []):
                cust_name = (item.get("customer") or "").strip()
                if not cust_name:
                    continue
                customer_id = customer_lookup.get(cust_name)
                if not customer_id:
                    continue

                # Combine contact_tel and contact_mob
                tel = item.get("contact_tel") or ""
                mob = item.get("contact_mob") or ""
                phone_parts = [p.strip() for p in [tel, mob] if p and p.strip()]
                contact_phone = " / ".join(phone_parts) if phone_parts else None

                db.session.add(CustomerAddress(
                    customer_id=customer_id,
                    plant=item.get("plant"),
                    address_line1=item.get("address1"),
                    address_line2=item.get("address2"),
                    contact_person=item.get("contact_name"),
                    contact_phone=contact_phone,
                ))
            db.session.commit()
            print(f"Seeded customer_addresses ({CustomerAddress.query.count()} rows)")
    except Exception as e:
        print(f"Seed warning (customer_addresses): {e}")
        db.session.rollback()

    print("Access master data seeding complete")


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
