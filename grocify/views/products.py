"""Products, categories and stock-in (purchase) entries."""
from flask import (Blueprint, abort, flash, g, jsonify, redirect,
                   render_template, request, url_for)

from ..db import execute, get_db, get_setting, now, query, scalar
from ..helpers import UNITS, admin_required, login_required, parse_float
from ..uploads import delete_image, save_image

bp = Blueprint("products", __name__)


# ============================================================== PRODUCTS ===
@bp.route("/products")
@login_required
def index():
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category", "")
    status = request.args.get("status", "all")
    sort = request.args.get("sort", "name")

    warn_days = int(float(get_setting("expiry_warn_days", "7") or 7))

    sql = """SELECT p.*, c.name AS category, s.name AS supplier
               FROM products p
          LEFT JOIN categories c ON c.id = p.category_id
          LEFT JOIN suppliers  s ON s.id = p.supplier_id
              WHERE 1 = 1"""
    args = []

    if q:
        sql += " AND p.name LIKE ?"
        args.append("%" + q + "%")
    if category_id:
        sql += " AND p.category_id = ?"
        args.append(category_id)
    if status == "low":
        sql += " AND p.quantity <= p.min_stock AND p.quantity > 0"
    elif status == "out":
        sql += " AND p.quantity <= 0"
    elif status == "expiring":
        sql += (" AND p.expiry_date IS NOT NULL AND p.expiry_date <> ''"
                " AND date(p.expiry_date) <= date('now', ?)")
        args.append("+%d day" % warn_days)
    elif status == "expired":
        sql += (" AND p.expiry_date IS NOT NULL AND p.expiry_date <> ''"
                " AND date(p.expiry_date) < date('now')")

    order = {
        "name": "p.name COLLATE NOCASE ASC",
        "price": "p.price DESC",
        "stock": "p.quantity ASC",
        "expiry": "p.expiry_date IS NULL, p.expiry_date ASC",
        "newest": "p.id DESC",
    }.get(sort, "p.name COLLATE NOCASE ASC")
    sql += " ORDER BY " + order

    items = query(sql, args)
    categories = query("SELECT * FROM categories ORDER BY name")

    return render_template(
        "products/list.html",
        items=items,
        categories=categories,
        q=q,
        category_id=category_id,
        status=status,
        sort=sort,
        warn_days=warn_days,
        total_value=sum((r["quantity"] or 0) * (r["price"] or 0) for r in items),
    )


def _product_form_data():
    """Read and validate the add/edit product form. Returns (data, error)."""
    data = {
        "name": request.form.get("name", "").strip(),
        "category_id": request.form.get("category_id") or None,
        "supplier_id": request.form.get("supplier_id") or None,
        "price": parse_float(request.form.get("price")),
        "cost_price": parse_float(request.form.get("cost_price")),
        "quantity": parse_float(request.form.get("quantity")),
        "unit": request.form.get("unit", "piece"),
        "expiry_date": request.form.get("expiry_date", "").strip() or None,
        "min_stock": parse_float(request.form.get("min_stock"), 5),
    }
    error = None
    if not data["name"]:
        error = "Product name is required."
    elif data["price"] < 0 or data["quantity"] < 0:
        error = "Price and quantity cannot be negative."
    elif data["unit"] not in UNITS:
        error = "Please choose a valid unit."
    return data, error


@bp.route("/products/new", methods=("GET", "POST"))
@admin_required
def create():
    if request.method == "POST":
        data, error = _product_form_data()
        image = None
        if not error:
            # Only touch the uploaded file once the rest of the form is valid.
            image, error = save_image(request.files.get("image"))

        if error:
            flash(error, "danger")
            product = data
        else:
            execute(
                """INSERT INTO products
                   (name, category_id, supplier_id, price, cost_price,
                    quantity, unit, expiry_date, min_stock, image, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (data["name"], data["category_id"], data["supplier_id"],
                 data["price"], data["cost_price"], data["quantity"],
                 data["unit"], data["expiry_date"], data["min_stock"], image, now()),
            )
            flash(data["name"] + " added to the catalogue.", "success")
            return redirect(url_for("products.index"))
    else:
        product = {"unit": "piece", "min_stock": 5, "quantity": 0}

    return render_template(
        "products/form.html",
        product=product,
        categories=query("SELECT * FROM categories ORDER BY name"),
        suppliers=query("SELECT * FROM suppliers ORDER BY name"),
        mode="new",
    )


@bp.route("/products/<int:pid>/edit", methods=("GET", "POST"))
@admin_required
def edit(pid):
    row = query("SELECT * FROM products WHERE id = ?", (pid,), one=True)
    if row is None:
        abort(404)
    product = dict(row)

    if request.method == "POST":
        data, error = _product_form_data()
        image = product["image"]

        if not error:
            uploaded, error = save_image(request.files.get("image"), old_name=image)
            if uploaded:
                image = uploaded
            elif request.form.get("remove_image"):
                delete_image(image)
                image = None

        if error:
            flash(error, "danger")
            product.update(data)
        else:
            execute(
                """UPDATE products SET name=?, category_id=?, supplier_id=?, price=?,
                          cost_price=?, quantity=?, unit=?, expiry_date=?, min_stock=?,
                          image=?
                    WHERE id=?""",
                (data["name"], data["category_id"], data["supplier_id"],
                 data["price"], data["cost_price"], data["quantity"],
                 data["unit"], data["expiry_date"], data["min_stock"], image, pid),
            )
            flash(data["name"] + " updated.", "success")
            return redirect(url_for("products.index"))

    return render_template(
        "products/form.html",
        product=product,
        categories=query("SELECT * FROM categories ORDER BY name"),
        suppliers=query("SELECT * FROM suppliers ORDER BY name"),
        mode="edit",
    )


@bp.route("/products/<int:pid>/delete", methods=("POST",))
@admin_required
def delete(pid):
    product = query("SELECT name, image FROM products WHERE id = ?", (pid,), one=True)
    if product is None:
        abort(404)
    delete_image(product["image"])
    execute("DELETE FROM products WHERE id = ?", (pid,))
    flash(product["name"] + " deleted. Past bills are not affected.", "info")
    return redirect(url_for("products.index"))


# ============================================================== STOCK IN ===
@bp.route("/stock", methods=("GET", "POST"))
@admin_required
def stock():
    """Record new stock arriving from a supplier; adds to product quantity."""
    if request.method == "POST":
        product_id = request.form.get("product_id")
        quantity = parse_float(request.form.get("quantity"))
        cost_price = parse_float(request.form.get("cost_price"))
        supplier_id = request.form.get("supplier_id") or None
        expiry_date = request.form.get("expiry_date", "").strip() or None
        note = request.form.get("note", "").strip()

        product = query("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
        if product is None:
            flash("Please choose a product.", "danger")
        elif quantity <= 0:
            flash("Quantity must be greater than zero.", "danger")
        else:
            db = get_db()
            db.execute(
                """INSERT INTO stock_entries
                   (product_id, supplier_id, user_id, quantity, cost_price, note, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (product["id"], supplier_id, g.user["id"], quantity, cost_price,
                 note, now()),
            )
            db.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?",
                       (quantity, product["id"]))
            if cost_price > 0:
                db.execute("UPDATE products SET cost_price = ? WHERE id = ?",
                           (cost_price, product["id"]))
            if supplier_id:
                db.execute("UPDATE products SET supplier_id = ? WHERE id = ?",
                           (supplier_id, product["id"]))
            if expiry_date:
                db.execute("UPDATE products SET expiry_date = ? WHERE id = ?",
                           (expiry_date, product["id"]))
            db.commit()
            flash("Added %g %s to %s." % (quantity, product["unit"], product["name"]),
                  "success")
            return redirect(url_for("products.stock"))

    entries = query(
        """SELECT e.*, p.name AS product, p.unit, s.name AS supplier, u.name AS added_by
             FROM stock_entries e
             JOIN products  p ON p.id = e.product_id
        LEFT JOIN suppliers s ON s.id = e.supplier_id
        LEFT JOIN users     u ON u.id = e.user_id
         ORDER BY e.id DESC LIMIT 100"""
    )
    return render_template(
        "products/stock.html",
        entries=entries,
        products=query("SELECT id, name, unit, quantity, cost_price "
                       "FROM products ORDER BY name COLLATE NOCASE"),
        suppliers=query("SELECT * FROM suppliers ORDER BY name"),
    )


# ============================================================ CATEGORIES ===
@bp.route("/categories", methods=("GET", "POST"))
@admin_required
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Category name is required.", "danger")
        elif query("SELECT 1 FROM categories WHERE name = ? COLLATE NOCASE",
                   (name,), one=True):
            flash("A category named " + name + " already exists.", "warning")
        else:
            execute("INSERT INTO categories (name, description) VALUES (?,?)",
                    (name, description))
            flash("Category " + name + " added.", "success")
        return redirect(url_for("products.categories"))

    items = query(
        """SELECT c.*,
                  (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id)
                      AS product_count,
                  (SELECT IFNULL(SUM(p.quantity * p.price), 0) FROM products p
                    WHERE p.category_id = c.id) AS stock_value
             FROM categories c
         ORDER BY c.name COLLATE NOCASE"""
    )
    return render_template("products/categories.html", items=items)


@bp.route("/categories/<int:cid>/edit", methods=("POST",))
@admin_required
def edit_category(cid):
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Category name is required.", "danger")
    else:
        execute("UPDATE categories SET name = ?, description = ? WHERE id = ?",
                (name, description, cid))
        flash("Category updated.", "success")
    return redirect(url_for("products.categories"))


@bp.route("/categories/<int:cid>/delete", methods=("POST",))
@admin_required
def delete_category(cid):
    used = scalar("SELECT COUNT(*) FROM products WHERE category_id = ?", (cid,))
    if used:
        flash("This category still has %d product(s). Move or delete them first."
              % used, "warning")
    else:
        execute("DELETE FROM categories WHERE id = ?", (cid,))
        flash("Category deleted.", "info")
    return redirect(url_for("products.categories"))


# =================================================================== API ===
@bp.route("/api/products")
@login_required
def api_products():
    """Product list used by the billing screen (client-side search)."""
    rows = query(
        """SELECT p.id, p.name, p.price, p.quantity, p.unit, p.expiry_date, p.image,
                  IFNULL(c.name, 'Uncategorised') AS category
             FROM products p LEFT JOIN categories c ON c.id = p.category_id
         ORDER BY p.name COLLATE NOCASE"""
    )
    return jsonify([dict(r) for r in rows])
