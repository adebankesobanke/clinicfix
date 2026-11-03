import os

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from werkzeug.exceptions import BadRequest, MethodNotAllowed, NotFound

from .models import db
from .routes import api

migrate = Migrate()


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
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "dev-only-change-me"),
        JWT_ACCESS_TOKEN_EXPIRES=900,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    JWTManager(app)

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

    return app