"""
Application Factory and Entry Point
====================================
Configures and initializes the Flask application with SQLAlchemy,
Flask-JWT-Extended, and CORS support.

Developers can register their individual feature blueprints inside create_app().
"""

import os
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from config import config_by_name
from models import db


def create_app(config_name=None):
    """
    Application factory pattern to configure and instantiate the Flask app.
    
    :param config_name: Environment configuration name ('development', 'testing', 'production')
    :return: Configured Flask application instance
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Initialize extensions
    CORS(app)
    db.init_app(app)
    jwt = JWTManager(app)

    # Base / Health check route to verify backend connectivity
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "message": "Subscription Management System API is active",
            "version": "0.1.0"
        }), 200

    # -------------------------------------------------------------------------
    # Blueprint Registration Placeholder:
    # Multiple developers can register their feature blueprints here.
    # Example:
    #   from routes.auth_routes import auth_bp
    #   app.register_blueprint(auth_bp, url_prefix="/api/auth")
    # -------------------------------------------------------------------------

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)

