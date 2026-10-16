import os

from flask import Flask, jsonify
from werkzeug.exceptions import BadRequest, MethodNotAllowed, NotFound

from .models import db
from .routes import api


def database_url():
    url = os.environ.get("DATABASE_URL", "sqlite:///clinicfix.db")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    app.register_blueprint(api, url_prefix="/api")

    @app.errorhandler(BadRequest)
    def handle_bad_request(_exception):
        return jsonify({"error": "The request could not be understood."}), 400

    @app.errorhandler(NotFound)
    def handle_not_found(_exception):
        return jsonify({"error": "Route was not found."}), 404

    @app.errorhandler(MethodNotAllowed)
    def handle_method_not_allowed(_exception):
        return jsonify({"error": "Method is not allowed for this route."}), 405

    with app.app_context():
        db.create_all()

    return app
