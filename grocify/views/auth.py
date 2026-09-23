"""Sign in / sign out and the password-change page."""
from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import execute, get_setting, now, query, scalar
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


def _admin_signup_error(code):
    """Decide whether an administrator may be created from the public form.

    Three cases:
    1. No administrator exists yet (a freshly created database) - allow it, or
       nobody could ever make the first one.
    2. An administrator exists but no code has been set - administrator
       sign-up is off, so refuse and say where to turn it on.
    3. A code is set - it must match. The stored value is a hash, exactly like
       a password, so the real code is nowhere in the database or the code.
    """
    if scalar("SELECT COUNT(*) FROM users WHERE role = 'admin'") == 0:
        return None

    stored = get_setting("admin_code_hash", "")
    if not stored:
        return ("Administrator sign-up is turned off. Ask an administrator to "
                "set an administrator code in Settings, or to create the "
                "account for you from the Staff accounts page.")
    if not code:
        return "Please enter the administrator code."
    if not check_password_hash(stored, code):
        return "That administrator code is not correct."
    return None


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
            if error is None and form["role"] == "admin":
                error = _admin_signup_error(request.form.get("admin_code", ""))

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

    return render_template(
        "register.html", form=form,
        # Tells the page whether to explain that a code will be needed.
        admin_code_required=scalar(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'") > 0,
    )


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
