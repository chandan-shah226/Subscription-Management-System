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
    Quotation, QuotationItem, Subscription, SubscriptionItem, SubscriptionAuditLog,
    Invoice, InvoiceItem, Payment, Discount
)
from routes import (
    auth_bp, user_bp, product_bp, plan_bp, quotation_bp, subscription_bp,
    invoice_bp, payment_bp, discount_bp, finance_bp
)


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
            db.session.flush()

        # Seed Sample Discounts
        if not Discount.query.first():
            from decimal import Decimal
            from datetime import date, timedelta
            d1 = Discount(
                name="Welcome New Customer (10% Off)",
                code="WELCOME10",
                discount_type="percentage",
                value=Decimal("10.00"),
                min_amount=Decimal("100.00"),
                start_date=date.today() - timedelta(days=30),
                end_date=date.today() + timedelta(days=365),
                max_uses=100,
                used_count=3,
                scope="subscription",
                is_active=True
            )
            d2 = Discount(
                name="Volume Discount (5+ Seats)",
                code="VOLUME5",
                discount_type="fixed",
                value=Decimal("200.00"),
                min_quantity=5,
                start_date=date.today() - timedelta(days=10),
                end_date=date.today() + timedelta(days=180),
                max_uses=50,
                used_count=1,
                scope="subscription",
                is_active=True
            )
            d3 = Discount(
                name="Annual Early Bird Commit (15% Off)",
                code="ANNUAL15",
                discount_type="percentage",
                value=Decimal("15.00"),
                min_amount=Decimal("1000.00"),
                start_date=date.today() - timedelta(days=60),
                end_date=date.today() + timedelta(days=300),
                max_uses=30,
                used_count=5,
                scope="subscription",
                is_active=True
            )
            db.session.add_all([d1, d2, d3])

        # Seed Sample Subscription if absent
        cust_user = User.query.filter_by(email="customer@brightloop.com").first()
        plan_monthly = SubscriptionPlan.query.filter_by(code="PLAN-ENT-MONTHLY").first()
        prod1 = Product.query.first()
        if cust_user and plan_monthly and prod1 and not Subscription.query.first():
            from decimal import Decimal
            from datetime import date, timedelta
            today = date.today()
            sub1 = Subscription(
                subscription_number="SUB-2026-0001",
                customer_id=cust_user.id,
                plan_id=plan_monthly.id,
                status="active",
                billing_frequency="monthly",
                start_date=today - timedelta(days=60),
                next_billing_date=today + timedelta(days=30),
                subtotal=Decimal("1500.00"),
                tax_amount=Decimal("270.00"),
                total_amount=Decimal("1770.00"),
                amount=Decimal("1770.00"),
                plan_name=plan_monthly.name,
                product_name=prod1.name,
                renews_on=today + timedelta(days=30)
            )
            db.session.add(sub1)
            db.session.flush()

            # Add line item
            si1 = SubscriptionItem(
                subscription_id=sub1.id,
                product_id=prod1.id,
                quantity=1,
                unit_price=Decimal("1500.00"),
                tax_rate=Decimal("18.00"),
                total_price=Decimal("1770.00")
            )
            db.session.add(si1)

            # Seed an invoice that is paid
            inv1 = Invoice(
                invoice_number="INV-2026-0001",
                subscription_id=sub1.id,
                customer_id=cust_user.id,
                invoice_date=today - timedelta(days=60),
                due_date=today - timedelta(days=45),
                status="paid",
                subtotal=Decimal("1500.00"),
                tax_amount=Decimal("270.00"),
                discount_amount=Decimal("0.00"),
                total_amount=Decimal("1770.00"),
                amount=Decimal("1770.00"),
                notes="Initial monthly billing for SaaS Enterprise"
            )
            db.session.add(inv1)
            db.session.flush()

            inv_item1 = InvoiceItem(
                invoice_id=inv1.id,
                product_id=prod1.id,
                description=prod1.name,
                quantity=1,
                unit_price=Decimal("1500.00"),
                tax_rate=Decimal("18.00"),
                total_price=Decimal("1770.00")
            )
            db.session.add(inv_item1)

            # Seed payment for inv1
            pay1 = Payment(
                payment_reference="PAY-2026-0001",
                invoice_id=inv1.id,
                customer_id=cust_user.id,
                amount=Decimal("1770.00"),
                method="card",
                status="successful",
                paid_on=today - timedelta(days=59),
                note="Card payment processed successfully"
            )
            db.session.add(pay1)

            # Seed a current confirmed invoice
            inv2 = Invoice(
                invoice_number="INV-2026-0002",
                subscription_id=sub1.id,
                customer_id=cust_user.id,
                invoice_date=today - timedelta(days=30),
                due_date=today + timedelta(days=5),
                status="confirmed",
                subtotal=Decimal("1500.00"),
                tax_amount=Decimal("270.00"),
                discount_amount=Decimal("150.00"),
                total_amount=Decimal("1620.00"),
                amount=Decimal("1620.00"),
                discount_code="WELCOME10",
                notes="Recurring monthly invoice with WELCOME10 coupon"
            )
            db.session.add(inv2)
            db.session.flush()

            inv_item2 = InvoiceItem(
                invoice_id=inv2.id,
                product_id=prod1.id,
                description=prod1.name,
                quantity=1,
                unit_price=Decimal("1500.00"),
                tax_rate=Decimal("18.00"),
                total_price=Decimal("1770.00")
            )
            db.session.add(inv_item2)

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
    app.register_blueprint(invoice_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(discount_bp)
    app.register_blueprint(finance_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    seed_initial_data(app)
    port = int(os.environ.get("PORT", 5001))
    print(f"🚀 Brightloop Backend Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=True)
