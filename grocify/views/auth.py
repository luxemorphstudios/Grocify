"""Sign in / sign out and the password-change page."""
from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import execute, now, query
from ..helpers import login_required, validate_password, validate_username

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


@bp.route("/register", methods=("GET", "POST"))
def register():
    """Anyone can create an account from the sign-in page."""
    if g.user is not None:
        return redirect(url_for("dashboard.index"))

    form = {"name": "", "username": "", "role": "staff"}

    if request.method == "POST":
        form = {
            "name": request.form.get("name", "").strip(),
            "username": request.form.get("username", "").strip().lower(),
            "role": request.form.get("role", "staff"),
        }
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = None
        if not form["name"]:
            error = "Please enter your full name."
        elif form["role"] not in ("admin", "staff"):
            error = "Please choose a valid role."
        else:
            error = (validate_username(form["username"])
                     or validate_password(password, confirm))
            if error is None and query("SELECT 1 FROM users WHERE username = ?",
                                       (form["username"],), one=True):
                error = "That username is already taken. Please pick another."

        if error:
            flash(error, "danger")
        else:
            execute(
                """INSERT INTO users (name, username, password_hash, role,
                                      is_active, created_at)
                   VALUES (?,?,?,?,1,?)""",
                (form["name"], form["username"], generate_password_hash(password),
                 form["role"], now()),
            )
            flash("Account created. You can sign in now.", "success")
            return redirect(url_for("auth.login"))

    return render_template("register.html", form=form)


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
        if not check_password_hash(row["password_hash"], current):
            error = "Your current password is not correct."
        else:
            error = validate_password(new, confirm)

        if error:
            flash(error, "danger")
        else:
            execute("UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(new), g.user["id"]))
            flash("Password updated.", "success")
            return redirect(url_for("auth.account"))

    return render_template("account.html")
