"""Sign in / sign out and the password-change page."""
from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import execute, query
from ..helpers import login_required

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user is not None:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = query("SELECT * FROM users WHERE username = ?", (username,), one=True)

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.", "danger")
        elif not user["is_active"]:
            flash("This account has been disabled. Contact the administrator.", "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name'].split()[0]}!", "success")
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):        # only allow internal redirects
                return redirect(nxt)
            return redirect(url_for("dashboard.index"))

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/account", methods=("GET", "POST"))
@login_required
def account():
    """Let any signed-in user change their own password."""
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        row = query("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],), one=True)
        error = None
        if not check_password_hash(row["password_hash"], current):
            error = "Your current password is not correct."
        elif len(new) < 4:
            error = "The new password must be at least 4 characters."
        elif new != confirm:
            error = "The two new passwords do not match."

        if error:
            flash(error, "danger")
        else:
            execute("UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(new), g.user["id"]))
            flash("Password updated.", "success")
            return redirect(url_for("auth.account"))

    return render_template("account.html")
