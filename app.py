import os
import click
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
    from blueprints.menu import bp as menu_bp
    from blueprints.master import bp as master_bp
    from blueprints.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(master_bp)
    app.register_blueprint(admin_bp)

    # Root route
    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('menu.main_menu'))
        return redirect(url_for('auth.login'))

    @app.cli.command("import-access")
    @click.argument("export_path")
    def import_access_command(export_path):
        """Load an Access export (.json.gz from tools/export_access.py) into the SCS tables."""
        from services.access_import import load_export, import_access_data
        with open(export_path, "rb") as f:
            counts = import_access_data(load_export(f))
        for table, n in counts.items():
            print(f"{table}: {n}")

    # Auto-create tables
    with app.app_context():
        _drop_redesign_tables()
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

        # gunicorn --preload forks the workers after this: drop the startup connections so each
        # worker opens its own (a shared SSL connection fails with "bad record mac").
        db.session.remove()
        db.engine.dispose()

    return app


# Tables of the earlier redesign (before the Access replica). Users and audit_log are kept.
REDESIGN_TABLES = [
    "product_categories", "currencies", "shipping_lines", "ports_of_destination", "return_terminals",
    "packing_types", "payment_terms_supplier", "payment_terms_customer", "delivery_terms",
    "permit_requirements", "units_of_measure", "products", "suppliers", "customers",
    "customer_addresses", "brokers", "transporters", "storage_locations", "permits",
    "purchase_orders", "purchase_order_items", "shipment_files", "shipment_containers",
    "customer_pos", "customer_po_items", "delivery_notes", "delivery_note_items",
    "container_returns", "commission_tracking", "shipment_payment_tracking", "broker_covers",
    "customer_contracts",
]


def _drop_redesign_tables():
    """One-time switch from the redesign schema to the Access-replica schema."""
    from sqlalchemy import inspect, text
    existing = set(inspect(db.engine).get_table_names())
    if "purchase_orders" not in existing:
        return
    print("Redesign schema found — dropping its tables (users and audit_log kept)...")
    cascade = " CASCADE" if db.engine.dialect.name == "postgresql" else ""
    with db.engine.begin() as conn:
        for name in REDESIGN_TABLES:
            if name in existing:
                conn.execute(text(f'DROP TABLE "{name}"{cascade}'))
    print("Redesign tables dropped.")


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
