"""
Application Factory and Entry Point
====================================
Configures and initializes the Flask application with SQLAlchemy,
Flask-JWT-Extended, CORS, route Blueprints, and database seeding.
Includes all Modules:
- Module 1: Authentication & User Management
- Module 2: Products & Subscription Plans
- Module 3: Quotations & Active Subscriptions
- Module 4: Invoices & Recurring Billing
"""

import os
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS

# Load .env file from project root (parent of backend/) so Razorpay keys are available
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass

from config import config_by_name
from models import (
    db, User, Product, ProductVariant, SubscriptionPlan, PlanProduct,
    Quotation, QuotationItem, Subscription, SubscriptionItem, SubscriptionAuditLog,
    Invoice, InvoiceItem, Payment, Discount
)
from routes import (
    auth_bp, user_bp, product_bp, plan_bp, quotation_bp, subscription_bp,
    invoice_bp, payment_bp, discount_bp, finance_bp
)


def seed_initial_data(app):
    """Seeds default administrator, staff, sample products, plans, and invoices if absent."""
    with app.app_context():
        db.create_all()

        # Seed Admin User
        admin_email = "admin@brightloop.com"
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                first_name="Admin",
                last_name="Brightloop",
                role="admin",
                is_active=True,
            )
            admin.set_password("Admin@123!")
            db.session.add(admin)
            db.session.flush()

        # Seed Staff User
        staff_email = "staff@brightloop.com"
        staff = User.query.filter_by(email=staff_email).first()
        if not staff:
            staff = User(
                email=staff_email,
                first_name="Sarah",
                last_name="Staff",
                role="staff",
                is_active=True,
            )
            staff.set_password("Staff@123!")
            db.session.add(staff)
            db.session.flush()

        # Seed Customer User
        customer_email = "customer@brightloop.com"
        customer = User.query.filter_by(email=customer_email).first()
        if not customer:
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
            db.session.flush()

        # Seed Sample Products
        p1 = Product.query.filter_by(code="PROD-CLOUD-01").first()
        if not p1:
            p1 = Product(
                name="Cloud Hosting Infrastructure",
                code="PROD-CLOUD-01",
                description="High-availability managed cloud server instances with 99.9% uptime SLA.",
                product_type="service",
                sales_price=Decimal("1200.00"),
                cost_price=Decimal("450.00"),
                is_active=True,
            )
            db.session.add(p1)
            db.session.flush()

        plan1 = SubscriptionPlan.query.filter_by(code="PLAN-CLOUD-BASIC").first()
        if not plan1:
            plan1 = SubscriptionPlan(
                name="Standard Cloud Tier",
                code="PLAN-CLOUD-BASIC",
                description="General-purpose compute instance with standard memory.",
                base_price=Decimal("1200.00"),
                billing_frequency="monthly",
                minimum_quantity=1,
                allow_pause=True,
                allow_renewal=True,
                allow_early_close=True,
                auto_close_on_expiry=False,
                is_active=True
            )
            db.session.add(plan1)

        plan2 = SubscriptionPlan.query.filter_by(code="PLAN-PRO-YEARLY").first()
        if not plan2:
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
            db.session.add(plan2)

        db.session.commit()

        # Seed Sample Subscription if none exists
        sub = Subscription.query.filter_by(subscription_number="SUB-2026-0001").first()
        if not sub and customer and plan1:
            sub = Subscription(
                subscription_number="SUB-2026-0001",
                customer_id=customer.id,
                plan_id=plan1.id,
                status="active",
                billing_frequency="monthly",
                start_date=date.today() - timedelta(days=60),
                next_billing_date=date.today(),
                auto_renew=True,
                subtotal=Decimal("1760.00"),
                tax_amount=Decimal("316.80"),
                total_amount=Decimal("2076.80"),
                notes="Initial production active subscription."
            )
            db.session.add(sub)
            db.session.flush()

            if p1:
                item1 = SubscriptionItem(
                    subscription_id=sub.id,
                    product_id=p1.id,
                    quantity=1,
                    unit_price=Decimal("1760.00"),
                    tax_rate=Decimal("18.00"),
                    tax_amount=Decimal("316.80"),
                    total_price=Decimal("2076.80")
                )
                db.session.add(item1)

            audit = SubscriptionAuditLog(
                subscription_id=sub.id,
                action="subscription_created",
                performed_by_id=customer.id,
                details="Initial sample subscription provisioned."
            )
            db.session.add(audit)
            db.session.commit()

        # Seed Sample Invoices (Module 4) if none exist
        if not Invoice.query.first() and customer:
            today = date.today()

            # 1. Paid Invoice
            inv1 = Invoice(
                invoice_number="INV-2026-0001",
                customer_id=customer.id,
                subscription_id=sub.id if sub else None,
                billing_period_start=today - timedelta(days=60),
                billing_period_end=today - timedelta(days=30),
                invoice_date=today - timedelta(days=30),
                due_date=today - timedelta(days=15),
                subtotal=Decimal("1760.00"),
                discount_amount=Decimal("0.00"),
                tax_amount=Decimal("316.80"),
                total_amount=Decimal("2076.80"),
                amount_paid=Decimal("2076.80"),
                outstanding_amount=Decimal("0.00"),
                status="Paid",
                notes="Monthly billing cycle invoice. Fully settled via Bank Transfer."
            )
            db.session.add(inv1)
            db.session.flush()

            if p1:
                db.session.add(InvoiceItem(
                    invoice_id=inv1.id,
                    product_id=p1.id,
                    description="Cloud Hosting Infrastructure (Enterprise CPU)",
                    quantity=Decimal("1.00"),
                    unit_price=Decimal("1760.00"),
                    discount_amount=Decimal("0.00"),
                    tax_rate=Decimal("18.00"),
                    tax_amount=Decimal("316.80"),
                    total_amount=Decimal("2076.80")
                ))

            db.session.add(Payment(
                invoice_id=inv1.id,
                amount=Decimal("2076.80"),
                payment_method="Bank Transfer",
                payment_date=today - timedelta(days=20),
                reference_number="NEFT-BL-20260901",
                notes="Settlement received in full",
                created_by_id=admin.id if admin else None
            ))

            # 2. Confirmed Overdue Invoice with partial payment
            inv2 = Invoice(
                invoice_number="INV-2026-0002",
                customer_id=customer.id,
                subscription_id=sub.id if sub else None,
                billing_period_start=today - timedelta(days=30),
                billing_period_end=today,
                invoice_date=today - timedelta(days=20),
                due_date=today - timedelta(days=5),  # Overdue
                subtotal=Decimal("2110.00"),
                discount_amount=Decimal("0.00"),
                tax_amount=Decimal("379.80"),
                total_amount=Decimal("2489.80"),
                amount_paid=Decimal("1000.00"),
                outstanding_amount=Decimal("1489.80"),
                status="Confirmed",
                notes="Current billing cycle. Partial payment received, balance overdue."
            )
            db.session.add(inv2)
            db.session.flush()

            if p1:
                db.session.add(InvoiceItem(
                    invoice_id=inv2.id,
                    product_id=p1.id,
                    description="Cloud Hosting Infrastructure",
                    quantity=Decimal("1.00"),
                    unit_price=Decimal("1760.00"),
                    discount_amount=Decimal("0.00"),
                    tax_rate=Decimal("18.00"),
                    tax_amount=Decimal("316.80"),
                    total_amount=Decimal("2076.80")
                ))
            if p2:
                db.session.add(InvoiceItem(
                    invoice_id=inv2.id,
                    product_id=p2.id,
                    description="24/7 Premium Technical Support",
                    quantity=Decimal("1.00"),
                    unit_price=Decimal("350.00"),
                    discount_amount=Decimal("0.00"),
                    tax_rate=Decimal("18.00"),
                    tax_amount=Decimal("63.00"),
                    total_amount=Decimal("413.00")
                ))

            db.session.add(Payment(
                invoice_id=inv2.id,
                amount=Decimal("1000.00"),
                payment_method="UPI",
                payment_date=today - timedelta(days=10),
                reference_number="UPI-REF-998811",
                notes="Partial payment via UPI",
                created_by_id=admin.id if admin else None
            ))

            # 3. Draft Invoice
            inv3 = Invoice(
                invoice_number="INV-2026-0003",
                customer_id=customer.id,
                subscription_id=None,
                billing_period_start=None,
                billing_period_end=None,
                invoice_date=today,
                due_date=today + timedelta(days=15),
                subtotal=Decimal("700.00"),
                discount_amount=Decimal("0.00"),
                tax_amount=Decimal("126.00"),
                total_amount=Decimal("826.00"),
                amount_paid=Decimal("0.00"),
                outstanding_amount=Decimal("826.00"),
                status="Draft",
                notes="Draft onboarding consultation invoice."
            )
            db.session.add(inv3)
            db.session.flush()

            if p2:
                db.session.add(InvoiceItem(
                    invoice_id=inv3.id,
                    product_id=p2.id,
                    description="24/7 Premium Technical Support (2 hours custom setup)",
                    quantity=Decimal("2.00"),
                    unit_price=Decimal("350.00"),
                    discount_amount=Decimal("0.00"),
                    tax_rate=Decimal("18.00"),
                    tax_amount=Decimal("126.00"),
                    total_amount=Decimal("826.00")
                ))

            db.session.commit()

        # Seed Sample Discounts (Module 5) if none exist
        if not Discount.query.first():
            today = date.today()
            d1 = Discount(
                code="SAVE10",
                description="10% off on all recurring subscriptions and services",
                discount_type="percentage",
                value=Decimal("10.00"),
                min_purchase=Decimal("500.00"),
                min_quantity=1,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=365),
                usage_limit=100,
                times_used=0,
                scope="all",
                is_active=True
            )
            d2 = Discount(
                code="SUB20",
                description="20% off on subscription billing",
                discount_type="percentage",
                value=Decimal("20.00"),
                min_purchase=Decimal("1000.00"),
                min_quantity=1,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=365),
                usage_limit=50,
                times_used=0,
                scope="subscription",
                is_active=True
            )
            d3 = Discount(
                code="FLAT500",
                description="Flat ₹500 off on large purchases",
                discount_type="fixed",
                value=Decimal("500.00"),
                min_purchase=Decimal("2000.00"),
                min_quantity=1,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=365),
                usage_limit=20,
                times_used=0,
                scope="all",
                is_active=True
            )
            db.session.add_all([d1, d2, d3])
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
            "success": True,
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
    app.register_blueprint(invoice_bp)
    app.register_blueprint(discount_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(finance_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    seed_initial_data(app)
    port = int(os.environ.get("PORT", 5000))
    print(f"Brightloop Backend Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=True)
