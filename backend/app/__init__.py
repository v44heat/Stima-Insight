"""Flask application factory."""
import logging

from flask import Flask
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from app.config import Config
from app.extensions import db, jwt, migrate
from app.utils.responses import APIError, fail

log = logging.getLogger(__name__)


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    from app import models  # noqa: F401  (register tables)
    from app.routes import (admin, alerts, anomalies, auth, consumption, dashboard, forecast,
                            household, ml, reports, settings)

    for module in (auth, household, consumption, ml, forecast, anomalies, alerts, dashboard,
                   settings, admin, reports):
        app.register_blueprint(module.bp)

    _register_error_handlers(app)
    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(e: APIError):
        return fail(e.message, e.status, e.details)

    @app.errorhandler(HTTPException)
    def handle_http(e: HTTPException):
        msg = {413: "File is too large"}.get(e.code, e.description)
        return fail(msg, e.code)

    @app.errorhandler(Exception)
    def handle_unexpected(e: Exception):
        log.exception("Unhandled error")  # stack trace goes to logs only
        return fail("Internal server error", 500)

    @jwt.unauthorized_loader
    def _missing(reason):
        return fail("Authentication required", 401)

    @jwt.invalid_token_loader
    def _invalid(reason):
        return fail("Invalid token", 401)

    @jwt.expired_token_loader
    def _expired(header, payload):
        return fail("Session expired, please log in again", 401)
