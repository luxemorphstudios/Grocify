"""Shared helpers: access-control decorators, template filters, small utilities."""
from datetime import date, datetime, timedelta
from functools import wraps

from flask import flash, g, redirect, request, session, url_for

from .db import query


# --------------------------------------------------------------- session
def load_logged_in_user():
    """Runs before every request; puts the current user on ``g.user``."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    g.user = query(
        "SELECT id, name, username, role FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
        one=True,
    )
    if g.user is None:          # account was deleted or disabled mid-session
        session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(**kwargs):
        if g.user is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if g.user["role"] != "admin":
            flash("That page is for administrators only.", "danger")
            return redirect(url_for("dashboard.index"))
        return view(**kwargs)

    return wrapped


# ------------------------------------------------------- template filters
def money(value, symbol=None):
    """Format a number the Indian way: 1234567.5 -> 12,34,567.50"""
    from .db import get_setting

    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0.0
    if symbol is None:
        symbol = get_setting("currency", "₹")

    sign = "-" if value < 0 else ""
    whole, dec = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return f"{sign}{symbol}{whole}.{dec}"


def qty(value):
    """Drop the decimals on whole quantities: 3.0 -> '3', 2.5 -> '2.5'"""
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        return "0"
    return str(int(value)) if value == int(value) else f"{value:g}"


def nice_date(value, fmt="%d %b %Y"):
    """Accepts 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' and prints it readably."""
    if not value:
        return "—"
    if isinstance(value, (datetime, date)):
        return value.strftime(fmt)
    text = str(value)
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).strftime(fmt)
        except ValueError:
            continue
    return text


def nice_datetime(value):
    return nice_date(value, "%d %b %Y, %I:%M %p")


# ------------------------------------------------------------- utilities
def parse_float(value, default=0.0):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default


def parse_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError, AttributeError):
        return default


def days_until(date_text):
    """Days from today until 'YYYY-MM-DD' (negative when already past)."""
    if not date_text:
        return None
    try:
        target = datetime.strptime(str(date_text)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return (target - date.today()).days


def date_range(days=7):
    """List of the last ``days`` dates as 'YYYY-MM-DD', oldest first."""
    end = date.today()
    return [(end - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]


PASSWORD_MIN_LENGTH = 8


def validate_password(password, confirm=None):
    """Check a new password against the rules. Returns an error, or None.

    The rules are deliberately checked here on the server. The sign-up form
    also checks them in the browser, but that is only for quick feedback - a
    user can edit the page, so the server has to decide.
    """
    if len(password or "") < PASSWORD_MIN_LENGTH:
        return ("The password must be at least %d characters long."
                % PASSWORD_MIN_LENGTH)
    if not any(not ch.isalnum() and not ch.isspace() for ch in password):
        return ("The password must include at least one special character, "
                "for example ! @ # $ % or &.")
    if confirm is not None and password != confirm:
        return "The two passwords do not match."
    return None


def validate_username(username):
    """Usernames are lower case, 3-20 characters, letters/digits/dot/underscore."""
    name = username or ""
    if not 3 <= len(name) <= 20:
        return "The username must be between 3 and 20 characters."
    if not all(ch.isalnum() or ch in "._" for ch in name):
        return ("The username can only contain letters, numbers, dots and "
                "underscores.")
    return None


def hue(text):
    """A stable 0-359 hue for a name, used to colour its fallback thumbnail.

    The same formula exists in pos.js so a product looks identical on the
    billing screen and in the product table.
    """
    total = 0
    for ch in str(text or ""):
        total = (total * 31 + ord(ch)) % 360
    return total


UNITS = ["piece", "kg", "gram", "litre", "ml", "packet", "box", "dozen", "bottle"]

PAYMENT_MODES = ["Cash", "UPI", "Card"]


def register_filters(app):
    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["qty"] = qty
    app.jinja_env.filters["nice_date"] = nice_date
    app.jinja_env.filters["nice_datetime"] = nice_datetime
    app.jinja_env.globals["days_until"] = days_until
    app.jinja_env.globals["hue"] = hue
    app.jinja_env.globals["UNITS"] = UNITS
    app.jinja_env.globals["PAYMENT_MODES"] = PAYMENT_MODES
