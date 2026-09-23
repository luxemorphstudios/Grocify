"""Grocify - Grocery Store Management System (Flask + SQLite)."""
import os

from flask import Flask, g, render_template

from . import db
from .helpers import load_logged_in_user, register_filters

__version__ = "1.0.0"


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        # For a college project a fixed key is fine. In production, read it
        # from an environment variable instead.
        SECRET_KEY=os.environ.get("GROCIFY_SECRET_KEY", "grocify-dev-secret-key"),
        DATABASE=os.path.join(app.instance_path, "grocify.sqlite"),
        # Hard ceiling on any upload; product images are capped lower
        # (2 MB) inside grocify/uploads.py so we can show a friendly message.
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    )

    if test_config is None:
        app.config.from_pyfile("config.py", silent=True)
    else:
        app.config.from_mapping(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    register_filters(app)

    # Keep an older database file usable after an update.
    with app.app_context():
        try:
            db.ensure_schema()
        except Exception:          # database not created yet
            pass

    app.before_request(load_logged_in_user)

    # ------------------------------------------------------- blueprints
    from .views import auth, billing, dashboard, people, products, reports

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(billing.bp)
    app.register_blueprint(people.bp)
    app.register_blueprint(reports.bp)
    app.add_url_rule("/", endpoint="index")

    # -------------------------------------------------- shared template ctx
    @app.context_processor
    def inject_globals():
        shop = {}
        try:
            shop = db.get_settings()
        except Exception:          # database not created yet
            pass
        return {"shop": shop, "app_version": __version__}

    # ------------------------------------------------------ error pages
    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404,
                               message="We couldn't find that page."), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                               message="You don't have access to that page."), 403

    @app.errorhandler(413)
    def too_large(e):
        return render_template("error.html", code=413,
                               message="That file is too big to upload."), 413

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", code=500,
                               message="Something went wrong on our side."), 500

    return app
