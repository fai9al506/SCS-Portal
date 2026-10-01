"""Admin: users, loading data from Access, and the lookup lists Access had no screens for."""
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from extensions import db
from models import User, ACCESS_FIELDS
from services.audit import log_action

bp = Blueprint("admin", __name__, url_prefix="/admin")

# Only "Admin" changes what a user can do for now; view-only and other limits come later.
ROLES = ["Admin", "Logistics", "Sales", "Finance", "Manager", "Viewer"]


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "Admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.route("/")
@admin_required
def index():
    from blueprints.master import FORMS, window_size
    lists = []
    for key, form in FORMS.items():
        if form.get("admin"):
            w, h = window_size(form)
            lists.append(dict(key=key, title=form["title"], url=url_for("master.form", key=key), w=w, h=h))
    counts = {m.__access_table__: m.query.count() for m in ACCESS_FIELDS}
    return render_template("admin/index.html", users=User.query.order_by(User.name).all(), roles=ROLES,
                           lists=lists, counts=counts)


@bp.route("/users/save", methods=["POST"])
@admin_required
def save_user():
    user_id = request.form.get("id")
    user = User.query.get(int(user_id)) if user_id else User()
    user.name = request.form.get("name", "").strip()
    user.email = request.form.get("email", "").strip().lower()
    user.role = request.form.get("role") if request.form.get("role") in ROLES else "Logistics"
    user.is_active = request.form.get("is_active") == "on"
    password = request.form.get("password", "")
    if not user.name or not user.email:
        flash("Name and email are required.", "error")
        return redirect(url_for("admin.index"))
    if not user_id and not password:
        flash("A password is required for a new user.", "error")
        return redirect(url_for("admin.index"))
    if User.query.filter(User.email == user.email, User.id != (user.id or 0)).first():
        flash("Another user already has this email.", "error")
        return redirect(url_for("admin.index"))
    if password:
        user.set_password(password)
    if not user_id:
        db.session.add(user)
    db.session.commit()
    log_action(current_user.id, "User", "update_user" if user_id else "create_user", "User", user.id,
               after={"name": user.name, "email": user.email, "role": user.role, "active": user.is_active})
    flash(f"Saved {user.name}.", "success")
    return redirect(url_for("admin.index"))


@bp.route("/import", methods=["POST"])
@admin_required
def import_access():
    from services.access_import import load_export, import_access_data
    upload = request.files.get("export")
    if not upload or not upload.filename:
        flash("Choose the export file first.", "error")
        return redirect(url_for("admin.index"))
    if request.form.get("confirm") != "REPLACE":
        flash("Type REPLACE to confirm. All SCS data in the portal will be replaced.", "error")
        return redirect(url_for("admin.index"))
    try:
        data = load_export(upload.stream)
        counts = import_access_data(data)
    except Exception as e:
        db.session.rollback()
        flash(f"Import failed, nothing was changed: {e}", "error")
        return redirect(url_for("admin.index"))
    log_action(current_user.id, "User", "import_access", "Database", None,
               after={"source": data.get("source"), "exported_at": data.get("exported_at"), "counts": counts})
    flash(f"Imported {sum(counts.values())} records from {data.get('source')} "
          f"(exported {data.get('exported_at', '')[:16].replace('T', ' ')}).", "success")
    return redirect(url_for("admin.index"))
