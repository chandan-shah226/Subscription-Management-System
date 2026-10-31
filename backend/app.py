"""
Application Factory and Entry Point
====================================
Configures and initializes the Flask application with SQLAlchemy,
Flask-JWT-Extended, CORS, route Blueprints, and database seeding.
"""

import os
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from config import config_by_name
from models import (
    db, User, Product, ProductVariant, SubscriptionPlan, PlanProduct,
    Quotation, QuotationItem, Subscription, SubscriptionItem, SubscriptionAuditLog
)
from routes import auth_bp, user_bp, product_bp, plan_bp, quotation_bp, subscription_bp


def seed_initial_data(app):
    """Seeds default administrator, staff, sample products, and plans if absent."""
    with app.app_context():
        db.create_all()

        # Seed Admin User
        admin_email = "admin@brightloop.com"
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                email=admin_email,
                first_name="Admin",
                last_name="Brightloop",
                role="admin",
                is_active=True,
            )
            admin.set_password("Admin@123!")
            db.session.add(admin)

        # Seed Staff User
        staff_email = "staff@brightloop.com"
        if not User.query.filter_by(email=staff_email).first():
            staff = User(
                email=staff_email,
                first_name="Sarah",
                last_name="Staff",
                role="staff",
                is_active=True,
            )
            staff.set_password("Staff@123!")
            db.session.add(staff)

        # Seed Customer User
        customer_email = "customer@brightloop.com"
        if not User.query.filter_by(email=customer_email).first():
            customer = User(
                email=customer_email,
                first_name="John",
                last_name="Doe",
                phone="+1 555-0199",
                role="customer",
                is_active=True,
            )
            customer.set_password("Customer@123!")
            db.session.add(customer)

        # Seed Sample Products
        if not Product.query.first():
            from decimal import Decimal
            p1 = Product(
                name="Cloud Hosting Infrastructure",
                code="PROD-CLOUD-01",
                description="High-availability managed cloud server instances with 99.9% uptime SLA.",
                product_type="service",
                sales_price=Decimal("1200.00"),
                cost_price=Decimal("450.00"),
                tax_rate=Decimal("18.00"),
                is_active=True
            )
            db.session.add(p1)
            db.session.flush()

            v1 = ProductVariant(
                product_id=p1.id,
                variant_name="Enterprise Dedicated CPU (Odoo Brand)",
                sku="CLOUD-CPU-ENT",
                additional_price=Decimal("560.00"),
                is_active=True
            )
            v2 = ProductVariant(
                product_id=p1.id,
                variant_name="Standard Multi-Tenant",
                sku="CLOUD-CPU-STD",
                additional_price=Decimal("0.00"),
                is_active=True
            )
            db.session.add_all([v1, v2])

            p2 = Product(
                name="24/7 Premium Technical Support",
                code="PROD-SUPP-247",
                description="Dedicated technical support team with 15-minute response SLA.",
                product_type="service",
                sales_price=Decimal("350.00"),
                cost_price=Decimal("100.00"),
                tax_rate=Decimal("18.00"),
                is_active=True
            )
            db.session.add(p2)

        # Seed Sample Plans
        if not SubscriptionPlan.query.first():
            from decimal import Decimal
            plan1 = SubscriptionPlan(
                name="SaaS Enterprise Monthly",
                code="PLAN-ENT-MONTHLY",
                description="Comprehensive enterprise subscription with monthly billing and flexible pausing.",
                base_price=Decimal("1500.00"),
                billing_frequency="monthly",
                minimum_quantity=1,
                allow_pause=True,
                allow_renewal=True,
                allow_early_close=True,
                auto_close_on_expiry=False,
                is_active=True
            )
            plan2 = SubscriptionPlan(
                name="SaaS Annual Pro",
                code="PLAN-PRO-YEARLY",
                description="Annual committed subscription plan with discount structure.",
                base_price=Decimal("14000.00"),
                billing_frequency="yearly",
                minimum_quantity=1,
                allow_pause=False,
                allow_renewal=True,
                allow_early_close=False,
                auto_close_on_expiry=True,
                is_active=True
            )
            db.session.add_all([plan1, plan2])

        db.session.commit()


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

    # Initialize extensions with CORS support
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)
    jwt = JWTManager(app)

    # JWT Error handlers for consistent JSON API responses
    @jwt.unauthorized_loader
    def custom_unauthorized_response(callback):
        return jsonify({
            "success": False,
            "error": "Missing Authorization header or invalid token",
            "details": callback
        }), 401

    @jwt.invalid_token_loader
    def custom_invalid_token_response(callback):
        return jsonify({
            "success": False,
            "error": "Signature verification failed or token is malformed",
            "details": callback
        }), 401

    @jwt.expired_token_loader
    def custom_expired_token_response(jwt_header, jwt_payload):
        return jsonify({
            "success": False,
            "error": "Token has expired. Please log in again or refresh your session.",
            "details": {"sub": jwt_payload.get("sub")}
        }), 401

    # Base Health check route
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "message": "Subscription Management System API is active",
            "version": "1.0.0"
        }), 200

    # Database Initialization & Seed Route (for local testing & verification)
    @app.route("/api/init-db", methods=["POST"])
    def init_database_route():
        seed_initial_data(app)
        return jsonify({
            "success": True,
            "message": "Database tables initialized and initial seed records created successfully."
        }), 200

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(plan_bp)
    app.register_blueprint(quotation_bp)
    app.register_blueprint(subscription_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    seed_initial_data(app)
    app.run(host="0.0.0.0", port=5000, debug=True)
