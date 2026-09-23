"""Thin sqlite3 helper layer: one connection per request, plus query helpers."""
import sqlite3
from datetime import datetime

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    """Return the sqlite3 connection for the current request (opening it once)."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    """SELECT helper. Returns a list of sqlite3.Row, or a single Row/None."""
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=(), commit=True):
    """INSERT/UPDATE/DELETE helper. Returns the new row id."""
    db = get_db()
    cur = db.execute(sql, args)
    if commit:
        db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def scalar(sql, args=(), default=0):
    """Return the first column of the first row (handy for COUNT/SUM)."""
    row = query(sql, args, one=True)
    if row is None or row[0] is None:
        return default
    return row[0]


def now():
    """Local timestamp string used for every created_at column."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today():
    return datetime.now().strftime("%Y-%m-%d")


# ----------------------------------------------------------------- settings
def get_settings():
    """All rows of the settings table as a plain dict."""
    return {r["key"]: r["value"] for r in query("SELECT key, value FROM settings")}


def get_setting(key, default=""):
    row = query("SELECT value FROM settings WHERE key = ?", (key,), one=True)
    return row["value"] if row else default


def save_setting(key, value):
    execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


# ------------------------------------------------------------ CLI commands
def init_db():
    """Create all tables (drops existing ones first)."""
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()


def ensure_schema():
    """Add columns that newer versions of Grocify expect.

    Lets an existing grocify.sqlite keep its data when the app is updated,
    instead of forcing everyone to wipe the database.
    """
    db = get_db()
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'products'"
    ).fetchone()
    if not exists:
        return                      # fresh install: init-db will create it

    columns = {r["name"] for r in db.execute("PRAGMA table_info(products)")}
    added = False
    for column, sql_type in (("image", "TEXT"), ("image_credit", "TEXT")):
        if column not in columns:
            db.execute("ALTER TABLE products ADD COLUMN %s %s" % (column, sql_type))
            added = True
    if added:
        db.commit()


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Erase the database and create fresh, empty tables."""
    init_db()
    click.echo("Database initialised (all previous data removed).")


@click.command("seed-db")
@with_appcontext
def seed_db_command():
    """Create fresh tables and fill them with demo data."""
    from .seed import seed

    init_db()
    seed()
    click.echo("Database seeded with demo data.")


@click.command("fetch-images")
@click.option("--force", is_flag=True, help="Also replace photos that are already set.")
@click.option("--only", default=None, help="Just this one product name.")
@click.option("--candidate", default=0, help="Skip this many search hits (to pick another photo).")
@click.option("--terms", default=None,
              help="Search words to use instead of the built-in ones (with --only).")
@with_appcontext
def fetch_images_command(force, only, candidate, terms):
    """Download openly licensed product photos from Wikimedia Commons."""
    import os

    from . import imagefetch

    sql = "SELECT id, name, image FROM products"
    args = []
    if only:
        sql += " WHERE name = ?"
        args.append(only)
    elif not force:
        sql += " WHERE image IS NULL OR image = ''"
    sql += " ORDER BY name COLLATE NOCASE"

    products = query(sql, args)
    if not products:
        click.echo("Nothing to do - every product already has a photo.")
        return

    upload_dir = os.path.join(current_app.static_folder, "uploads", "products")
    found = 0
    for product in products:
        click.echo("  %-30s " % product["name"][:30], nl=False)
        result = imagefetch.fetch_for(
            product["name"],
            terms=[terms] if terms else None,
            candidate=candidate)
        if result is None:
            click.echo("no suitable photo found")
            continue
        jpeg, credit = result
        imagefetch.store(product["id"], jpeg, credit, upload_dir)
        found += 1
        click.echo("ok (%.0f KB)" % (len(jpeg) / 1024))

    total = imagefetch.write_credits(os.path.join(upload_dir, "CREDITS.md"))
    imagefetch.write_manifest(upload_dir)
    click.echo("Downloaded %d of %d. CREDITS.md now lists %d photo(s)."
               % (found, len(products), total))


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)
    app.cli.add_command(fetch_images_command)
