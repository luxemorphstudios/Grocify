-- Grocify: database schema (SQLite)
-- All dates are stored as TEXT 'YYYY-MM-DD', timestamps as 'YYYY-MM-DD HH:MM:SS'.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS sale_items;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS stock_entries;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS settings;

-- ---------------------------------------------------------------- users
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'staff' CHECK (role IN ('admin', 'staff')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);

-- ----------------------------------------------------------- categories
CREATE TABLE categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

-- ------------------------------------------------------------ suppliers
CREATE TABLE suppliers (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    phone   TEXT,
    email   TEXT,
    address TEXT
);

-- ------------------------------------------------------------- products
CREATE TABLE products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
    supplier_id INTEGER REFERENCES suppliers(id)  ON DELETE SET NULL,
    price       REAL    NOT NULL DEFAULT 0,   -- selling price per unit
    cost_price  REAL    NOT NULL DEFAULT 0,   -- purchase price per unit
    quantity    REAL    NOT NULL DEFAULT 0,   -- stock on hand
    unit        TEXT    NOT NULL DEFAULT 'piece',
    expiry_date TEXT,
    min_stock   REAL    NOT NULL DEFAULT 5,   -- low-stock threshold
    image       TEXT,                         -- file name inside static/uploads/products
    image_credit TEXT,                        -- photographer + licence, when downloaded
    created_at  TEXT    NOT NULL
);

CREATE INDEX idx_products_name     ON products(name);
CREATE INDEX idx_products_category ON products(category_id);

-- ------------------------------------------- stock_entries (stock-in log)
CREATE TABLE stock_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id)  ON DELETE CASCADE,
    supplier_id INTEGER          REFERENCES suppliers(id) ON DELETE SET NULL,
    user_id     INTEGER          REFERENCES users(id)     ON DELETE SET NULL,
    quantity    REAL    NOT NULL,
    cost_price  REAL    NOT NULL DEFAULT 0,
    note        TEXT,
    created_at  TEXT    NOT NULL
);

-- ---------------------------------------------------------------- sales
CREATE TABLE sales (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no     TEXT    NOT NULL UNIQUE,
    user_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
    customer_name  TEXT,
    customer_phone TEXT,
    subtotal       REAL    NOT NULL DEFAULT 0,
    discount       REAL    NOT NULL DEFAULT 0,
    gst_rate       REAL    NOT NULL DEFAULT 0,
    gst_amount     REAL    NOT NULL DEFAULT 0,
    total_amount   REAL    NOT NULL DEFAULT 0,
    payment_mode   TEXT    NOT NULL DEFAULT 'Cash',
    created_at     TEXT    NOT NULL
);

CREATE INDEX idx_sales_created ON sales(created_at);

-- ----------------------------------------------------------- sale_items
-- product_name / unit are copied in so an old bill still prints correctly
-- even if the product is later renamed or deleted.
CREATE TABLE sale_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id      INTEGER NOT NULL REFERENCES sales(id)    ON DELETE CASCADE,
    product_id   INTEGER          REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT    NOT NULL,
    unit         TEXT    NOT NULL DEFAULT 'piece',
    quantity     REAL    NOT NULL,
    price        REAL    NOT NULL,
    line_total   REAL    NOT NULL
);

CREATE INDEX idx_sale_items_sale ON sale_items(sale_id);

-- ------------------------------------------------------------- settings
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO settings (key, value) VALUES
    ('shop_name',       'Grocify Super Market'),
    ('shop_address',    '12 Main Bazaar Road, Pune 411001'),
    ('shop_phone',      '+91 98765 43210'),
    ('currency',        '₹'),
    ('gst_rate',        '5'),
    ('expiry_warn_days','7'),
    -- Hash of the code needed to register an administrator from the sign-in
    -- page. Empty means administrator sign-up is turned off.
    ('admin_code_hash', '');
