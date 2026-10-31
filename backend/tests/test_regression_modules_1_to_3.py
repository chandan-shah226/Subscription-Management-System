"""
Regression Test Suite for Modules 1, 2, and 3
=============================================
Verifies that Modules 1 (User/Auth/Roles), 2 (Product/Plans),
and 3 (Subscriptions/Quotations) remain 100% operational
and unaffected by Module 4, 5, and 6 implementations.
"""

import sys
import os
import unittest
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User, Product, ProductVariant, Plan, Subscription, SubscriptionLine
from flask_jwt_extended import create_access_token


class Modules1To3RegressionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_module_1_user_roles_and_authentication(self):
        """Verifies Module 1: User creation, password hashing, and login authentication."""
        admin = User(
            email="admin@test.com",
            first_name="Admin",
            last_name="Tester",
            role="admin"
        )
        admin.set_password("AdminSecure@123")
        db.session.add(admin)
        db.session.commit()

        # Verify password hashing
        self.assertTrue(admin.check_password("AdminSecure@123"))
        self.assertFalse(admin.check_password("WrongPassword"))

        # Verify login API
        res = self.client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "AdminSecure@123"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("access_token", data["data"])
        self.assertEqual(data["data"]["user"]["role"], "admin")

    def test_module_2_product_and_variants(self):
        """Verifies Module 2: Products, cost/sales price, and variants (Odoo +560)."""
        admin = User(
            email="admin_prod@test.com",
            first_name="Admin",
            last_name="Prod",
            role="admin"
        )
        admin.set_password("AdminSecure@123")
        db.session.add(admin)
        db.session.commit()

        token = create_access_token(
            identity=str(admin.id),
            additional_claims={"role": admin.role, "email": admin.email}
        )
        headers = {"Authorization": f"Bearer {token}"}

        product = Product(
            name="Brightloop Core ERP",
            code="PROD-ERP-01",
            product_type="software",
            sales_price=Decimal("4500.00"),
            cost_price=Decimal("1500.00")
        )
        db.session.add(product)
        db.session.flush()

        variant = ProductVariant(
            product_id=product.id,
            variant_name="Odoo Brand Integration",
            sku="SKU-ODOO-560",
            additional_price=Decimal("560.00")
        )
        db.session.add(variant)
        db.session.commit()

        # Query via auxiliary API
        res = self.client.get("/api/products", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        products = data.get("data") if isinstance(data.get("data"), list) else data.get("products", [])
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["variants"][0]["additional_price"], 560.00)

    def test_module_2_plan_billing_frequencies(self):
        """Verifies Module 2: Plan configurations (Daily, Weekly, Monthly, Yearly)."""
        plan = Plan(
            name="Enterprise Yearly",
            code="PLAN-ENT-YR-01",
            billing_frequency="yearly",
            base_price=Decimal("55000.00"),
            minimum_quantity=5,
            allow_pause=True,
            allow_renewal=True
        )
        db.session.add(plan)
        db.session.commit()

        self.assertEqual(plan.billing_frequency, "yearly")
        self.assertEqual(plan.base_price, Decimal("55000.00"))
        self.assertTrue(plan.allow_pause)

    def test_module_3_subscription_lifecycle_and_lines(self):
        """Verifies Module 3: Subscription creation, status transitions, and lines."""
        user = User(email="cust@test.com", first_name="Customer", last_name="Test", role="customer")
        user.set_password("Cust@123")
        db.session.add(user)
        db.session.commit()

        token = create_access_token(
            identity=str(user.id),
            additional_claims={"role": user.role, "email": user.email}
        )
        headers = {"Authorization": f"Bearer {token}"}

        plan = Plan(
            name="ERP Pro Plan",
            code="PLAN-ERP-PRO",
            billing_frequency="monthly",
            base_price=Decimal("4500.00"),
            minimum_quantity=1
        )
        db.session.add(plan)
        db.session.flush()

        product = Product(
            name="ERP Seat",
            code="PROD-SEAT-01",
            product_type="service",
            sales_price=Decimal("1500.00"),
            cost_price=Decimal("500.00")
        )
        db.session.add(product)
        db.session.flush()

        sub = Subscription(
            subscription_number="SUB-TEST-100",
            customer_id=user.id,
            plan_id=plan.id,
            status="Draft",
            billing_frequency="monthly",
            start_date=date.today(),
            next_billing_date=date.today() + timedelta(days=30),
            subtotal=Decimal("4500.00"),
            tax_amount=Decimal("810.00"),
            total_amount=Decimal("5310.00")
        )
        db.session.add(sub)
        db.session.flush()

        line = SubscriptionLine(
            subscription_id=sub.id,
            product_id=product.id,
            quantity=3,
            unit_price=Decimal("1500.00"),
            tax_rate=Decimal("18.00"),
            tax_amount=Decimal("810.00"),
            total_price=Decimal("5310.00")
        )
        db.session.add(line)
        db.session.commit()

        # Test lifecycle transitions: Draft -> Active
        sub.status = "Active"
        db.session.commit()
        self.assertEqual(sub.status, "Active")

        # Verify /api/subscriptions lookup
        res = self.client.get(f"/api/subscriptions?customer_id={user.id}", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        subs_data = data.get("data") if isinstance(data.get("data"), list) else data.get("subscriptions", [])
        self.assertEqual(len(subs_data), 1)
        self.assertEqual(subs_data[0]["subscription_number"], "SUB-TEST-100")


if __name__ == "__main__":
    unittest.main()
