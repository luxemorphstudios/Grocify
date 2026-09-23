"""Demo data so the project can be shown without typing anything in first."""
import random
from collections import defaultdict
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

from .db import get_db, now

USERS = [
    ("Karan Sharma",  "admin",  "admin123", "admin"),
    ("Priya Nair",    "priya",  "staff123", "staff"),
    ("Rahul Verma",   "rahul",  "staff123", "staff"),
]

CATEGORIES = [
    ("Dairy",            "Milk, curd, butter, cheese and paneer"),
    ("Vegetables",       "Fresh daily vegetables"),
    ("Fruits",           "Seasonal fresh fruit"),
    ("Snacks",           "Biscuits, chips and namkeen"),
    ("Beverages",        "Tea, coffee, juices and soft drinks"),
    ("Grains & Pulses",  "Rice, atta, dals and flours"),
    ("Personal Care",    "Soap, shampoo and toothpaste"),
    ("Household",        "Cleaning and kitchen supplies"),
]

SUPPLIERS = [
    ("Amul Distributors",      "+91 98220 11223", "orders@amuldist.example",
     "Plot 14, MIDC, Pune"),
    ("Green Valley Farms",     "+91 97654 88221", "hello@greenvalley.example",
     "Market Yard, Pune"),
    ("Sunrise Wholesale",      "+91 90210 45567", "sales@sunrisewhole.example",
     "Shop 3, Gultekdi, Pune"),
    ("Daily Needs Traders",    "+91 93700 99010", "contact@dailyneeds.example",
     "Camp Road, Pune"),
]

# name, category, price, cost, qty, unit, days-to-expiry (None = no expiry), min_stock
PRODUCTS = [
    ("Amul Gold Milk 1L",        "Dairy",       68,  60,  40, "packet",   4,  10),
    ("Amul Butter 500g",         "Dairy",      265, 240,  12, "packet",  60,   5),
    ("Fresh Paneer 200g",        "Dairy",       89,  75,   6, "packet",   3,   8),
    ("Curd Cup 400g",            "Dairy",       45,  38,  18, "packet",   5,  10),
    ("Cheese Slices 200g",       "Dairy",      145, 128,   4, "packet",  25,   6),
    ("Tomato",                   "Vegetables",  38,  28,  25, "kg",       5,   8),
    ("Onion",                    "Vegetables",  32,  24,  60, "kg",      20,  15),
    ("Potato",                   "Vegetables",  28,  20,  75, "kg",      25,  15),
    ("Spinach Bunch",            "Vegetables",  20,  14,   9, "piece",    2,  10),
    ("Green Chilli",             "Vegetables",  60,  45,   3, "kg",       6,   4),
    ("Banana",                   "Fruits",      54,  42,  14, "dozen",    4,   6),
    ("Apple Shimla",             "Fruits",     168, 140,  18, "kg",      12,   8),
    ("Orange",                   "Fruits",      92,  74,  11, "kg",       8,   6),
    ("Parle-G Biscuit 250g",     "Snacks",      30,  25,  85, "packet", 180,  20),
    ("Lays Classic 52g",         "Snacks",      20,  16,  48, "packet",  90,  20),
    ("Haldiram Bhujia 200g",     "Snacks",      55,  46,   7, "packet", 120,  10),
    ("Marie Gold 300g",          "Snacks",      45,  38,  32, "packet", 150,  12),
    ("Tata Tea Gold 500g",       "Beverages",  275, 245,  16, "packet", 300,   6),
    ("Nescafe Classic 100g",     "Beverages",  330, 300,   9, "bottle", 360,   5),
    ("Real Mixed Fruit 1L",      "Beverages",  120, 102,   5, "bottle",  30,   8),
    ("Coca Cola 750ml",          "Beverages",   40,  33,  36, "bottle",  75,  12),
    ("India Gate Basmati 5kg",   "Grains & Pulses", 620, 560,  8, "packet", 400, 4),
    ("Aashirvaad Atta 5kg",      "Grains & Pulses", 285, 255, 14, "packet", 150, 6),
    ("Toor Dal 1kg",             "Grains & Pulses", 165, 142, 22, "kg",     240, 8),
    ("Sugar 1kg",                "Grains & Pulses",  46,  40, 40, "kg",     300, 10),
    ("Sunflower Oil 1L",         "Grains & Pulses", 142, 126, 19, "bottle", 210, 8),
    ("Dove Soap 100g",           "Personal Care",    62,  52, 26, "piece",  400, 10),
    ("Colgate Strong Teeth 200g","Personal Care",   118, 100, 13, "piece",  450, 6),
    ("Clinic Plus Shampoo 340ml","Personal Care",   210, 185,  4, "bottle", 380, 6),
    ("Surf Excel 1kg",           "Household",       145, 128, 17, "packet", 500, 6),
    ("Vim Dishwash Bar",         "Household",        20,  15, 55, "piece",  365, 20),
    ("Harpic 500ml",             "Household",       102,  88,  3, "bottle", 420, 5),
    ("Garbage Bags (30 pcs)",    "Household",        99,  82, 12, "packet", None, 5),
    ("Steel Scrubber",           "Household",        25,  18,  0, "piece",  None, 8),
]


def seed():
    """Fill freshly created tables with users, catalogue and 30 days of sales."""
    random.seed(7)
    db = get_db()
    stamp = now()

    for name, username, password, role in USERS:
        db.execute(
            """INSERT INTO users (name, username, password_hash, role, is_active, created_at)
               VALUES (?,?,?,?,1,?)""",
            (name, username, generate_password_hash(password), role, stamp),
        )

    category_ids = {}
    for name, description in CATEGORIES:
        cur = db.execute("INSERT INTO categories (name, description) VALUES (?,?)",
                         (name, description))
        category_ids[name] = cur.lastrowid

    supplier_ids = []
    for name, phone, email, address in SUPPLIERS:
        cur = db.execute(
            "INSERT INTO suppliers (name, phone, email, address) VALUES (?,?,?,?)",
            (name, phone, email, address))
        supplier_ids.append(cur.lastrowid)

    products = []
    for i, (name, category, price, cost, qty, unit, expiry_days, min_stock) in \
            enumerate(PRODUCTS):
        expiry = None
        if expiry_days is not None:
            expiry = (date.today() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
        supplier_id = supplier_ids[i % len(supplier_ids)]
        # Stock a healthy shelf for everything except the handful of items that
        # are deliberately left low so the alerts have something to show.
        if qty > 6:
            qty = qty * 3
        cur = db.execute(
            """INSERT INTO products (name, category_id, supplier_id, price, cost_price,
                                     quantity, unit, expiry_date, min_stock, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (name, category_ids[category], supplier_id, price, cost,
             qty, unit, expiry, min_stock, stamp),
        )
        products.append({"id": cur.lastrowid, "name": name, "price": price,
                         "unit": unit, "qty": qty, "supplier_id": supplier_id,
                         "cost": cost})

    # One stock-in entry per product so the purchase log is not empty.
    for p in products:
        if p["qty"] > 0:
            db.execute(
                """INSERT INTO stock_entries (product_id, supplier_id, user_id, quantity,
                                              cost_price, note, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (p["id"], p["supplier_id"], 1, p["qty"], p["cost"],
                 "Opening stock", stamp),
            )

    _seed_sales(db, products)
    _restore_photos(db)
    db.commit()


def _restore_photos(db):
    """Put previously downloaded product photos back after a reset.

    Seeding drops every table, but the picture files are still on disk, so the
    manifest written by ``fetch-images`` tells us which file belongs to which
    product name.
    """
    import json
    import os

    from flask import current_app

    upload_dir = os.path.join(current_app.static_folder, "uploads", "products")
    path = os.path.join(upload_dir, "manifest.json")
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    for name, entry in data.items():
        filename = entry.get("image")
        if filename and os.path.exists(os.path.join(upload_dir, filename)):
            db.execute("UPDATE products SET image = ?, image_credit = ? WHERE name = ?",
                       (filename, entry.get("credit"), name))


def _seed_sales(db, products):
    """Create believable bills across the last 30 days and reduce stock for them."""
    customers = [
        ("Sneha Patil", "9822011223"), ("Arjun Desai", "9765588221"),
        ("Meera Joshi", "9021045567"), ("Vikram Rao", "9370099010"),
        (None, None), (None, None), ("Fatima Shaikh", "9881234567"),
    ]
    payment_modes = ["Cash", "Cash", "Cash", "UPI", "UPI", "Card"]
    counters = defaultdict(int)
    stock = {p["id"]: p["qty"] for p in products}
    sellable = [p for p in products if p["qty"] > 0]

    for day_offset in range(29, -1, -1):
        day = date.today() - timedelta(days=day_offset)
        for _ in range(random.randint(2, 7)):
            moment = datetime(day.year, day.month, day.day,
                              random.randint(9, 20), random.randint(0, 59),
                              random.randint(0, 59))
            basket = random.sample(sellable, random.randint(1, 5))
            lines, subtotal = [], 0.0

            for product in basket:
                quantity = random.choice([1, 1, 1, 2, 2, 3, 5])
                if stock[product["id"]] - quantity < 1:
                    continue
                stock[product["id"]] -= quantity
                line_total = round(quantity * product["price"], 2)
                subtotal += line_total
                lines.append((product, quantity, line_total))

            if not lines:
                continue

            subtotal = round(subtotal, 2)
            discount = round(random.choice([0, 0, 0, 10, 20, 25]), 2)
            discount = min(discount, subtotal)
            gst_rate = 5.0
            gst_amount = round((subtotal - discount) * gst_rate / 100, 2)
            total = round(subtotal - discount + gst_amount, 2)

            key = day.strftime("%Y%m%d")
            counters[key] += 1
            invoice_no = "INV-%s-%04d" % (key, counters[key])
            customer_name, customer_phone = random.choice(customers)

            sale_id = db.execute(
                """INSERT INTO sales (invoice_no, user_id, customer_name, customer_phone,
                                      subtotal, discount, gst_rate, gst_amount,
                                      total_amount, payment_mode, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (invoice_no, random.choice([1, 2, 2, 3, 3]), customer_name,
                 customer_phone, subtotal, discount, gst_rate, gst_amount, total,
                 random.choice(payment_modes),
                 moment.strftime("%Y-%m-%d %H:%M:%S")),
            ).lastrowid

            for product, quantity, line_total in lines:
                db.execute(
                    """INSERT INTO sale_items (sale_id, product_id, product_name, unit,
                                               quantity, price, line_total)
                       VALUES (?,?,?,?,?,?,?)""",
                    (sale_id, product["id"], product["name"], product["unit"],
                     quantity, product["price"], line_total),
                )

    for product_id, remaining in stock.items():
        db.execute("UPDATE products SET quantity = ? WHERE id = ?",
                   (remaining, product_id))
