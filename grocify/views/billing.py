"""Billing counter (POS), saved bills and the printable invoice."""
import json
from datetime import datetime

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, url_for)

from ..db import get_db, get_setting, now, query, scalar, today
from ..helpers import (PAYMENT_MODES, admin_required, login_required,
                       parse_float)

bp = Blueprint("billing", __name__)


def _next_invoice_no(db):
    """INV-20260923-0007 style number, restarting every day."""
    stamp = datetime.now().strftime("%Y%m%d")
    row = db.execute(
        "SELECT COUNT(*) AS n FROM sales WHERE invoice_no LIKE ?",
        ("INV-" + stamp + "-%",),
    ).fetchone()
    return "INV-%s-%04d" % (stamp, (row["n"] or 0) + 1)


# ============================================================== COUNTER ===
@bp.route("/billing")
@login_required
def counter():
    return render_template(
        "billing/counter.html",
        categories=query("SELECT name FROM categories ORDER BY name"),
        gst_rate=float(get_setting("gst_rate", "0") or 0),
        todays_total=scalar(
            "SELECT SUM(total_amount) FROM sales WHERE date(created_at) = ?", (today(),)
        ),
        todays_bills=scalar(
            "SELECT COUNT(*) FROM sales WHERE date(created_at) = ?", (today(),)
        ),
    )


@bp.route("/billing/checkout", methods=("POST",))
@login_required
def checkout():
    """Validate the cart, save the sale and reduce stock - all or nothing."""
    try:
        cart = json.loads(request.form.get("items") or "[]")
    except ValueError:
        cart = []

    if not cart:
        flash("The cart is empty - add at least one product.", "warning")
        return redirect(url_for("billing.counter"))

    discount = max(parse_float(request.form.get("discount")), 0)
    gst_rate = max(parse_float(request.form.get("gst_rate")), 0)
    payment_mode = request.form.get("payment_mode", "Cash")
    if payment_mode not in PAYMENT_MODES:
        payment_mode = "Cash"

    db = get_db()
    lines, subtotal = [], 0.0

    # Prices and stock always come from the database, never from the browser.
    for entry in cart:
        product = db.execute(
            "SELECT * FROM products WHERE id = ?", (entry.get("id"),)
        ).fetchone()
        if product is None:
            flash("One of the products is no longer available. Cart cleared.", "danger")
            return redirect(url_for("billing.counter"))

        quantity = parse_float(entry.get("qty"))
        if quantity <= 0:
            continue
        if quantity > (product["quantity"] or 0):
            flash("Only %g %s of %s left in stock." %
                  (product["quantity"], product["unit"], product["name"]), "danger")
            return redirect(url_for("billing.counter"))

        line_total = round(quantity * product["price"], 2)
        subtotal += line_total
        lines.append((product, quantity, line_total))

    if not lines:
        flash("The cart is empty - add at least one product.", "warning")
        return redirect(url_for("billing.counter"))

    subtotal = round(subtotal, 2)
    discount = min(discount, subtotal)
    taxable = subtotal - discount
    gst_amount = round(taxable * gst_rate / 100, 2)
    total = round(taxable + gst_amount, 2)

    try:
        sale_id = db.execute(
            """INSERT INTO sales (invoice_no, user_id, customer_name, customer_phone,
                                  subtotal, discount, gst_rate, gst_amount,
                                  total_amount, payment_mode, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (_next_invoice_no(db), g.user["id"],
             request.form.get("customer_name", "").strip() or None,
             request.form.get("customer_phone", "").strip() or None,
             subtotal, discount, gst_rate, gst_amount, total, payment_mode, now()),
        ).lastrowid

        for product, quantity, line_total in lines:
            db.execute(
                """INSERT INTO sale_items (sale_id, product_id, product_name, unit,
                                           quantity, price, line_total)
                   VALUES (?,?,?,?,?,?,?)""",
                (sale_id, product["id"], product["name"], product["unit"],
                 quantity, product["price"], line_total),
            )
            db.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?",
                       (quantity, product["id"]))
        db.commit()
    except Exception:
        db.rollback()
        flash("The bill could not be saved. Please try again.", "danger")
        return redirect(url_for("billing.counter"))

    flash("Bill saved successfully.", "success")
    return redirect(url_for("billing.invoice", sale_id=sale_id))


# ================================================================ BILLS ===
@bp.route("/bills")
@login_required
def bills():
    q = request.args.get("q", "").strip()
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()

    sql = """SELECT s.*, u.name AS cashier,
                    (SELECT COUNT(*) FROM sale_items si WHERE si.sale_id = s.id) AS item_count
               FROM sales s LEFT JOIN users u ON u.id = s.user_id
              WHERE 1 = 1"""
    args = []
    if q:
        sql += " AND (s.invoice_no LIKE ? OR s.customer_name LIKE ? OR s.customer_phone LIKE ?)"
        args += ["%" + q + "%"] * 3
    if start:
        sql += " AND date(s.created_at) >= date(?)"
        args.append(start)
    if end:
        sql += " AND date(s.created_at) <= date(?)"
        args.append(end)
    sql += " ORDER BY s.id DESC LIMIT 300"

    rows = query(sql, args)
    return render_template(
        "billing/bills.html",
        bills=rows,
        q=q, start=start, end=end,
        grand_total=sum(r["total_amount"] or 0 for r in rows),
    )


@bp.route("/bills/<int:sale_id>")
@login_required
def invoice(sale_id):
    sale = query(
        """SELECT s.*, u.name AS cashier
             FROM sales s LEFT JOIN users u ON u.id = s.user_id
            WHERE s.id = ?""",
        (sale_id,), one=True,
    )
    if sale is None:
        abort(404)
    items = query("SELECT * FROM sale_items WHERE sale_id = ? ORDER BY id", (sale_id,))
    return render_template("billing/invoice.html", sale=sale, items=items)


@bp.route("/bills/<int:sale_id>/delete", methods=("POST",))
@admin_required
def delete_bill(sale_id):
    """Cancel a bill and put the stock back (useful for demo / mistakes)."""
    db = get_db()
    sale = db.execute("SELECT invoice_no FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if sale is None:
        abort(404)

    for item in db.execute("SELECT product_id, quantity FROM sale_items WHERE sale_id = ?",
                           (sale_id,)).fetchall():
        if item["product_id"]:
            db.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?",
                       (item["quantity"], item["product_id"]))
    db.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    db.commit()

    flash("Bill " + sale["invoice_no"] + " cancelled and stock restored.", "info")
    return redirect(url_for("billing.bills"))
