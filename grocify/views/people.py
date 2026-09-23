"""Suppliers, staff accounts and shop settings - all administrator-only."""
from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, url_for)
from werkzeug.security import generate_password_hash

from ..db import execute, get_setting, now, query, save_setting, scalar
from ..helpers import admin_required, parse_float, validate_password, validate_username

bp = Blueprint("people", __name__)


# ============================================================= SUPPLIERS ===
@bp.route("/suppliers", methods=("GET", "POST"))
@admin_required
def suppliers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Supplier name is required.", "danger")
        else:
            execute(
                "INSERT INTO suppliers (name, phone, email, address) VALUES (?,?,?,?)",
                (name,
                 request.form.get("phone", "").strip(),
                 request.form.get("email", "").strip(),
                 request.form.get("address", "").strip()),
            )
            flash("Supplier " + name + " added.", "success")
        return redirect(url_for("people.suppliers"))

    items = query(
        """SELECT s.*,
                  (SELECT COUNT(*) FROM products p WHERE p.supplier_id = s.id)
                      AS product_count,
                  (SELECT IFNULL(SUM(e.quantity * e.cost_price), 0)
                     FROM stock_entries e WHERE e.supplier_id = s.id) AS purchased
             FROM suppliers s
         ORDER BY s.name COLLATE NOCASE"""
    )
    return render_template("people/suppliers.html", items=items)


@bp.route("/suppliers/<int:sid>/edit", methods=("POST",))
@admin_required
def edit_supplier(sid):
    name = request.form.get("name", "").strip()
    if not name:
        flash("Supplier name is required.", "danger")
    else:
        execute(
            "UPDATE suppliers SET name=?, phone=?, email=?, address=? WHERE id=?",
            (name,
             request.form.get("phone", "").strip(),
             request.form.get("email", "").strip(),
             request.form.get("address", "").strip(),
             sid),
        )
        flash("Supplier updated.", "success")
    return redirect(url_for("people.suppliers"))


@bp.route("/suppliers/<int:sid>/delete", methods=("POST",))
@admin_required
def delete_supplier(sid):
    execute("DELETE FROM suppliers WHERE id = ?", (sid,))
    flash("Supplier deleted. Their products stay in the catalogue.", "info")
    return redirect(url_for("people.suppliers"))


# ================================================================ USERS ===
@bp.route("/users", methods=("GET", "POST"))
@admin_required
def users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "staff")

        error = None
        if not name or not username:
            error = "Name and username are both required."
        elif role not in ("admin", "staff"):
            error = "Please choose a valid role."
        else:
            error = validate_username(username) or validate_password(password)
            if error is None and query("SELECT 1 FROM users WHERE username = ?",
                                       (username,), one=True):
                error = "That username is already taken."

        if error:
            flash(error, "danger")
        else:
            execute(
                """INSERT INTO users (name, username, password_hash, role, is_active, created_at)
                   VALUES (?,?,?,?,1,?)""",
                (name, username, generate_password_hash(password), role, now()),
            )
            flash("Account created for " + name + ".", "success")
        return redirect(url_for("people.users"))

    items = query(
        """SELECT u.*,
                  (SELECT COUNT(*) FROM sales s WHERE s.user_id = u.id) AS bill_count
             FROM users u ORDER BY u.role, u.name COLLATE NOCASE"""
    )
    return render_template("people/users.html", items=items)


@bp.route("/users/<int:uid>/edit", methods=("POST",))
@admin_required
def edit_user(uid):
    user = query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if user is None:
        abort(404)

    name = request.form.get("name", "").strip()
    role = request.form.get("role", user["role"])
    password = request.form.get("password", "")

    if not name:
        flash("Name is required.", "danger")
        return redirect(url_for("people.users"))
    if role not in ("admin", "staff"):
        role = user["role"]

    # Never let the last administrator demote themselves out of the system.
    if user["role"] == "admin" and role != "admin":
        admins = scalar("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1")
        if admins <= 1:
            flash("This is the only administrator account - keep it as admin.", "warning")
            return redirect(url_for("people.users"))

    execute("UPDATE users SET name = ?, role = ? WHERE id = ?", (name, role, uid))
    if password:
        problem = validate_password(password)
        if problem:
            flash(problem + " The password was not changed.", "warning")
        else:
            execute("UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(password), uid))
    flash("Account updated.", "success")
    return redirect(url_for("people.users"))


@bp.route("/users/<int:uid>/toggle", methods=("POST",))
@admin_required
def toggle_user(uid):
    user = query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if user is None:
        abort(404)
    if user["id"] == g.user["id"]:
        flash("You cannot disable your own account.", "warning")
        return redirect(url_for("people.users"))
    if user["is_active"] and user["role"] == "admin":
        admins = scalar("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1")
        if admins <= 1:
            flash("At least one administrator must stay active.", "warning")
            return redirect(url_for("people.users"))

    execute("UPDATE users SET is_active = ? WHERE id = ?",
            (0 if user["is_active"] else 1, uid))
    flash(("Account disabled." if user["is_active"] else "Account enabled."), "info")
    return redirect(url_for("people.users"))


@bp.route("/users/<int:uid>/delete", methods=("POST",))
@admin_required
def delete_user(uid):
    user = query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    if user is None:
        abort(404)
    if user["id"] == g.user["id"]:
        flash("You cannot delete your own account.", "warning")
    elif user["role"] == "admin" and scalar(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'") <= 1:
        flash("At least one administrator account must remain.", "warning")
    else:
        execute("DELETE FROM users WHERE id = ?", (uid,))
        flash("Account deleted. Their past bills are kept.", "info")
    return redirect(url_for("people.users"))


# ============================================================= SETTINGS ===
@bp.route("/settings", methods=("GET", "POST"))
@admin_required
def settings():
    if request.method == "POST":
        for key in ("shop_name", "shop_address", "shop_phone", "currency"):
            save_setting(key, request.form.get(key, "").strip())
        save_setting("gst_rate", max(parse_float(request.form.get("gst_rate")), 0))
        save_setting("expiry_warn_days",
                     int(max(parse_float(request.form.get("expiry_warn_days"), 7), 1)))

        # The administrator code is a credential, so it is hashed and can only
        # be replaced or cleared - never read back.
        if request.form.get("clear_admin_code"):
            save_setting("admin_code_hash", "")
            flash("Administrator sign-up turned off.", "info")
        else:
            new_code = request.form.get("admin_code", "")
            if new_code:
                problem = validate_password(new_code, what="administrator code")
                if problem:
                    flash(problem + " The code was not changed.", "warning")
                else:
                    save_setting("admin_code_hash", generate_password_hash(new_code))
                    flash("Administrator code updated.", "success")

        flash("Settings saved.", "success")
        return redirect(url_for("people.settings"))

    return render_template(
        "people/settings.html",
        admin_code_set=bool(get_setting("admin_code_hash", "")),
        admin_count=scalar("SELECT COUNT(*) FROM users WHERE role = 'admin'"),
    )
