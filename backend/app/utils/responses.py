"""Consistent JSON responses and a custom API exception."""
from flask import jsonify


class APIError(Exception):
    def __init__(self, message: str, status: int = 400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


def ok(data=None, status: int = 200, **extra):
    body = {"success": True, "data": data}
    body.update(extra)
    return jsonify(body), status


def fail(message: str, status: int = 400, details=None):
    body = {"success": False, "error": {"message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status
