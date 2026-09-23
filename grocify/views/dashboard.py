"""Home dashboard: summary cards, alerts and the 7-day sales chart."""
from flask import Blueprint, render_template

from ..db import get_setting, query, scalar, today
from ..helpers import date_range, login_required, nice_date

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    warn_days = int(float(get_setting("expiry_warn_days", "7") or 7))

    total_products = scalar("SELECT COUNT(*) FROM products")
    stock_value = scalar("SELECT SUM(quantity * price) FROM products")
    todays_total = scalar(
        "SELECT SUM(total_amount) FROM sales WHERE date(created_at) = ?", (today(),)
    )
    todays_bills = scalar(
        "SELECT COUNT(*) FROM sales WHERE date(created_at) = ?", (today(),)
    )

    low_stock = query(
        """SELECT p.*, c.name AS category
             FROM products p LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.quantity <= p.min_stock
            ORDER BY (p.quantity - p.min_stock) ASC, p.name
            LIMIT 8"""
    )
    low_stock_count = scalar("SELECT COUNT(*) FROM products WHERE quantity <= min_stock")

    expiring = query(
        """SELECT p.*, c.name AS category
             FROM products p LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.expiry_date IS NOT NULL AND p.expiry_date <> ''
              AND date(p.expiry_date) <= date('now', ?)
            ORDER BY p.expiry_date ASC
            LIMIT 8""",
        (f"+{warn_days} day",),
    )
    expiring_count = scalar(
        """SELECT COUNT(*) FROM products
            WHERE expiry_date IS NOT NULL AND expiry_date <> ''
              AND date(expiry_date) <= date('now', ?)""",
        (f"+{warn_days} day",),
    )

    recent_sales = query(
        """SELECT s.*, u.name AS cashier
             FROM sales s LEFT JOIN users u ON u.id = s.user_id
            ORDER BY s.id DESC LIMIT 6"""
    )

    # --- 7-day sales chart -------------------------------------------------
    days = date_range(7)
    rows = {
        r["d"]: r["total"]
        for r in query(
            """SELECT date(created_at) AS d, SUM(total_amount) AS total
                 FROM sales
                WHERE date(created_at) >= date('now', '-6 day')
                GROUP BY date(created_at)"""
        )
    }
    chart = {
        "labels": [nice_date(d, "%d %b") for d in days],
        "totals": [round(rows.get(d, 0) or 0, 2) for d in days],
    }

    # --- top sellers (last 30 days) ---------------------------------------
    top_products = query(
        """SELECT si.product_name,
                  SUM(si.quantity)   AS sold,
                  SUM(si.line_total) AS revenue
             FROM sale_items si JOIN sales s ON s.id = si.sale_id
            WHERE date(s.created_at) >= date('now', '-30 day')
            GROUP BY si.product_name
            ORDER BY revenue DESC
            LIMIT 5"""
    )

    return render_template(
        "dashboard.html",
        total_products=total_products,
        stock_value=stock_value,
        todays_total=todays_total,
        todays_bills=todays_bills,
        low_stock=low_stock,
        low_stock_count=low_stock_count,
        expiring=expiring,
        expiring_count=expiring_count,
        warn_days=warn_days,
        recent_sales=recent_sales,
        chart=chart,
        top_products=top_products,
    )
