from urllib.parse import urlparse
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User

bp = Blueprint("auth", __name__)


def _is_safe_url(target):
    """Validate that redirect target is a safe, relative URL."""
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("scs.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get("next")
            if not _is_safe_url(next_page):
                next_page = None
            return redirect(next_page or url_for("scs.dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
