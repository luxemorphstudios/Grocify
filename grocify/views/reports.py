"""Sales reports with charts, plus CSV export."""
import csv
import io
from datetime import date

from flask import Blueprint, Response, render_template, request

from ..db import query, scalar
from ..helpers import admin_required, nice_date

bp = Blueprint("reports", __name__)


def _period():
    """Read the start/end filter, defaulting to the current month."""
    first = date.today().replace(day=1).strftime("%Y-%m-%d")
    start = request.args.get("start", "").strip() or first
    end = request.args.get("end", "").strip() or date.today().strftime("%Y-%m-%d")
    if start > end:
        start, end = end, start
    return start, end


@bp.route("/reports")
@admin_required
def index():
    start, end = _period()
    args = (start, end)
    where = "WHERE date(s.created_at) BETWEEN date(?) AND date(?)"

    summary = {
        "revenue": scalar("SELECT SUM(total_amount) FROM sales s " + where, args),
        "bills": scalar("SELECT COUNT(*) FROM sales s " + where, args),
        "discount": scalar("SELECT SUM(discount) FROM sales s " + where, args),
        "gst": scalar("SELECT SUM(gst_amount) FROM sales s " + where, args),
        "units": scalar(
            "SELECT SUM(si.quantity) FROM sale_items si JOIN sales s ON s.id = si.sale_id "
            + where, args),
    }
    summary["average"] = (summary["revenue"] / summary["bills"]) if summary["bills"] else 0

    daily = query(
        """SELECT date(s.created_at) AS day, SUM(s.total_amount) AS total,
                  COUNT(*) AS bills
             FROM sales s """ + where + """
         GROUP BY date(s.created_at) ORDER BY day""", args)

    top_products = query(
        """SELECT si.product_name, si.unit,
                  SUM(si.quantity)   AS sold,
                  SUM(si.line_total) AS revenue
             FROM sale_items si JOIN sales s ON s.id = si.sale_id """ + where + """
         GROUP BY si.product_name, si.unit
         ORDER BY revenue DESC LIMIT 10""", args)

    by_category = query(
        """SELECT IFNULL(c.name, 'Uncategorised') AS category,
                  SUM(si.line_total) AS revenue
             FROM sale_items si
             JOIN sales s      ON s.id = si.sale_id
        LEFT JOIN products p   ON p.id = si.product_id
        LEFT JOIN categories c ON c.id = p.category_id """ + where + """
         GROUP BY category ORDER BY revenue DESC""", args)

    by_payment = query(
        """SELECT s.payment_mode, COUNT(*) AS bills, SUM(s.total_amount) AS revenue
             FROM sales s """ + where + """
         GROUP BY s.payment_mode ORDER BY revenue DESC""", args)

    by_staff = query(
        """SELECT IFNULL(u.name, 'Deleted user') AS cashier,
                  COUNT(*) AS bills, SUM(s.total_amount) AS revenue
             FROM sales s LEFT JOIN users u ON u.id = s.user_id """ + where + """
         GROUP BY cashier ORDER BY revenue DESC""", args)

    charts = {
        "daily_labels": [nice_date(r["day"], "%d %b") for r in daily],
        "daily_values": [round(r["total"] or 0, 2) for r in daily],
        "category_labels": [r["category"] for r in by_category],
        "category_values": [round(r["revenue"] or 0, 2) for r in by_category],
        "payment_labels": [r["payment_mode"] for r in by_payment],
        "payment_values": [round(r["revenue"] or 0, 2) for r in by_payment],
    }

    return render_template(
        "reports.html",
        start=start, end=end,
        summary=summary,
        daily=daily,
        top_products=top_products,
        by_category=by_category,
        by_payment=by_payment,
        by_staff=by_staff,
        charts=charts,
    )


@bp.route("/reports/export.csv")
@admin_required
def export_csv():
    """Download every bill line in the selected period as a CSV file."""
    start, end = _period()
    rows = query(
        """SELECT s.invoice_no, s.created_at, IFNULL(u.name, '-') AS cashier,
                  IFNULL(s.customer_name, '-') AS customer, s.payment_mode,
                  si.product_name, si.quantity, si.unit, si.price, si.line_total,
                  s.discount, s.gst_amount, s.total_amount
             FROM sales s
             JOIN sale_items si ON si.sale_id = s.id
        LEFT JOIN users u       ON u.id = s.user_id
            WHERE date(s.created_at) BETWEEN date(?) AND date(?)
         ORDER BY s.id, si.id""",
        (start, end),
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Invoice", "Date", "Cashier", "Customer", "Payment",
                     "Product", "Quantity", "Unit", "Rate", "Line total",
                     "Bill discount", "Bill GST", "Bill total"])
    for r in rows:
        writer.writerow([r[k] for k in r.keys()])

    filename = "grocify-sales-%s-to-%s.csv" % (start, end)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )
