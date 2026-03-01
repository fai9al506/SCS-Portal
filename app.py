import os
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(scs_bp)
    app.register_blueprint(manage_bp)

    # Root route
    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('scs.dashboard'))
        return redirect(url_for('auth.login'))

    # Auto-create tables and seed data
    with app.app_context():
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

        # Seed lookup data
        from models import Currency, ShippingLine, PortOfDestination, ReturnTerminal
        try:
            if Currency.query.count() == 0:
                for code in ['USD', 'SAR', 'EUR', 'GBP', 'CNY', 'INR', 'AED']:
                    db.session.add(Currency(code=code))
                db.session.commit()
                print("Seeded currencies")
        except Exception as e:
            print(f"Seed warning (currencies): {e}")
            db.session.rollback()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
