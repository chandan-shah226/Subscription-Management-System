"""
Automated Test Suite for Modules 1, 2, and 3
============================================
Comprehensive test suite testing:
- Module 1: Auth, password hashing, JWT, user management, RBAC, password reset, IDOR.
- Module 2: Products, variants, plans, pricing calculations, plan policies.
- Module 3: Quotations, tax calculations, templates, conversions, subscriptions, lifecycle, audit logs.
"""

import os
import sys
import unittest
from datetime import date, timedelta

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import db, User, Product, ProductVariant, SubscriptionPlan, Quotation, Subscription


class SystemTestCase(unittest.TestCase):
    """Test suite using an in-memory SQLite database for isolated test execution."""

    def setUp(self):
        self.app = create_app("testing")
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self, email, password):
        """Helper to log in and return access token and headers."""
        res = self.client.post("/api/auth/login", json={"email": email, "password": password})
        data = res.get_json()
        token = data["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # =========================================================================
    # MODULE 1 TESTS: USER MANAGEMENT & AUTHENTICATION
    # =========================================================================

    def test_customer_registration_and_validation(self):
        """Test customer registration, password complexity, and duplicate prevention."""
        # Weak password (no special char)
        res = self.client.post("/api/auth/register", json={
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "password": "Password123",
            "confirm_password": "Password123"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("special character", res.get_json()["error"])

        # Mismatched passwords
        res = self.client.post("/api/auth/register", json={
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!"
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Passwords do not match", res.get_json()["error"])

        # Valid registration
        res = self.client.post("/api/auth/register", json={
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["role"], "customer")

        # Duplicate email registration prevention
        res_dup = self.client.post("/api/auth/register", json={
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(res_dup.status_code, 400)
        self.assertIn("already exists", res_dup.get_json()["error"])

    def test_authentication_and_jwt_tokens(self):
        """Test login, JWT claims, and rejection of inactive users."""
        # Create user
        user = User(email="test@brightloop.com", first_name="Test", last_name="User", role="customer", is_active=True)
        user.set_password("SecurePass123!")
        db.session.add(user)
        db.session.commit()

        # Wrong password
        res = self.client.post("/api/auth/login", json={"email": "test@brightloop.com", "password": "WrongPassword!"})
        self.assertEqual(res.status_code, 401)

        # Successful login
        res = self.client.post("/api/auth/login", json={"email": "test@brightloop.com", "password": "SecurePass123!"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

        # Access /api/auth/me
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        res_me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.get_json()["data"]["email"], "test@brightloop.com")

        # Deactivated user login rejection
        user.is_active = False
        db.session.commit()
        res_inactive = self.client.post("/api/auth/login", json={"email": "test@brightloop.com", "password": "SecurePass123!"})
        self.assertEqual(res_inactive.status_code, 401)
        self.assertIn("deactivated", res_inactive.get_json()["error"])

    def test_password_reset_flow(self):
        """Test secure password reset token generation and usage."""
        user = User(email="reset@brightloop.com", first_name="Reset", last_name="User", role="customer", is_active=True)
        user.set_password("OriginalPass123!")
        db.session.add(user)
        db.session.commit()

        # Request reset (returns dev token in testing mode)
        res = self.client.post("/api/auth/forgot-password", json={"email": "reset@brightloop.com"})
        self.assertEqual(res.status_code, 200)
        token = res.get_json()["data"].get("dev_reset_token")

        if not token:
            # Look up directly in test DB
            from models.user import PasswordReset
            reset_rec = PasswordReset.query.filter_by(user_id=user.id).first()
            token = reset_rec.token

        # Reset password
        res_reset = self.client.post("/api/auth/reset-password", json={
            "token": token,
            "new_password": "NewSecurePass123!",
            "confirm_password": "NewSecurePass123!"
        })
        self.assertEqual(res_reset.status_code, 200)

        # Login with new password
        res_login = self.client.post("/api/auth/login", json={
            "email": "reset@brightloop.com",
            "password": "NewSecurePass123!"
        })
        self.assertEqual(res_login.status_code, 200)

    def test_admin_staff_rbac_and_idor(self):
        """Test role enforcement, staff creation, and prevention of customer accessing other profiles."""
        admin = User(email="admin@brightloop.com", first_name="Admin", last_name="User", role="admin")
        admin.set_password("AdminPass123!")
        customer1 = User(email="cust1@brightloop.com", first_name="Cust1", last_name="User", role="customer")
        customer1.set_password("CustPass123!")
        customer2 = User(email="cust2@brightloop.com", first_name="Cust2", last_name="User", role="customer")
        customer2.set_password("CustPass123!")
        db.session.add_all([admin, customer1, customer2])
        db.session.commit()

        admin_headers = self._login("admin@brightloop.com", "AdminPass123!")
        cust1_headers = self._login("cust1@brightloop.com", "CustPass123!")

        # Customer trying to list all users -> Forbidden (403)
        res = self.client.get("/api/users", headers=cust1_headers)
        self.assertEqual(res.status_code, 403)

        # Customer 1 trying to access Customer 2's ID -> IDOR blocked (403)
        res_idor = self.client.get(f"/api/users/{customer2.id}", headers=cust1_headers)
        self.assertEqual(res_idor.status_code, 403)

        # Customer 1 accessing own ID -> Allowed (200)
        res_own = self.client.get(f"/api/users/{customer1.id}", headers=cust1_headers)
        self.assertEqual(res_own.status_code, 200)

        # Admin creates staff account
        res_create_staff = self.client.post("/api/users", headers=admin_headers, json={
            "first_name": "New",
            "last_name": "Staff",
            "email": "newstaff@brightloop.com",
            "password": "StaffPassword123!",
            "role": "staff"
        })
        self.assertEqual(res_create_staff.status_code, 201)

    # =========================================================================
    # MODULE 2 TESTS: PRODUCT & PLAN MANAGEMENT
    # =========================================================================

    def test_product_and_variant_management(self):
        """Test product CRUD, validation, variant additions, and price calculation."""
        admin = User(email="admin@brightloop.com", first_name="Admin", last_name="User", role="admin")
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()
        admin_headers = self._login("admin@brightloop.com", "AdminPass123!")

        # Create product with negative price -> rejected
        res_neg = self.client.post("/api/products", headers=admin_headers, json={
            "name": "Cloud Storage",
            "code": "PROD-CLOUD",
            "sales_price": -50,
            "cost_price": 20
        })
        self.assertEqual(res_neg.status_code, 400)

        # Valid product creation
        res = self.client.post("/api/products", headers=admin_headers, json={
            "name": "Cloud Server Hosting",
            "code": "PROD-CLOUD-SRV",
            "sales_price": 1000.00,
            "cost_price": 400.00,
            "tax_rate": 18.00,
            "product_type": "service"
        })
        self.assertEqual(res.status_code, 201)
        p_id = res.get_json()["data"]["id"]

        # Add variant (e.g. Odoo brand adds 560 to base price)
        res_var = self.client.post(f"/api/products/{p_id}/variants", headers=admin_headers, json={
            "variant_name": "Odoo Dedicated CPU",
            "sku": "VAR-ODOO-CPU",
            "additional_price": 560.00
        })
        self.assertEqual(res_var.status_code, 201)
        v_data = res_var.get_json()["data"]
        self.assertEqual(v_data["additional_price"], 560.00)

    def test_subscription_plan_management_and_policies(self):
        """Test plan CRUD, frequency validation, date constraints, and policies."""
        admin = User(email="admin@brightloop.com", first_name="Admin", last_name="User", role="admin")
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()
        admin_headers = self._login("admin@brightloop.com", "AdminPass123!")

        # Invalid frequency
        res_freq = self.client.post("/api/plans", headers=admin_headers, json={
            "name": "Biweekly Plan",
            "code": "PLAN-BIWEEK",
            "billing_frequency": "biweekly"
        })
        self.assertEqual(res_freq.status_code, 400)

        # Invalid date range (end date before start date)
        res_dates = self.client.post("/api/plans", headers=admin_headers, json={
            "name": "Promo Plan",
            "code": "PLAN-PROMO",
            "billing_frequency": "monthly",
            "start_date": "2026-12-31",
            "end_date": "2026-01-01"
        })
        self.assertEqual(res_dates.status_code, 400)
        self.assertIn("End date cannot precede start date", res_dates.get_json()["error"])

        # Valid plan creation
        res = self.client.post("/api/plans", headers=admin_headers, json={
            "name": "Enterprise Annual",
            "code": "PLAN-ENT-ANNUAL",
            "base_price": 12000.00,
            "billing_frequency": "yearly",
            "minimum_quantity": 2,
            "allow_pause": True,
            "allow_renewal": True
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["data"]["minimum_quantity"], 2)

    # =========================================================================
    # MODULE 3 TESTS: QUOTATION & SUBSCRIPTION MANAGEMENT
    # =========================================================================

    def test_quotation_calculations_and_lifecycle(self):
        """Test quotation line item creation, tax and subtotal computation, and status flow."""
        admin = User(email="admin@brightloop.com", first_name="Admin", last_name="User", role="admin")
        admin.set_password("AdminPass123!")
        cust = User(email="cust@brightloop.com", first_name="Customer", last_name="One", role="customer")
        cust.set_password("CustPass123!")
        db.session.add_all([admin, cust])
        db.session.flush()

        from decimal import Decimal
        prod = Product(name="Software License", code="LIC-01", sales_price=Decimal("100.00"), tax_rate=Decimal("18.00"))
        plan = SubscriptionPlan(name="Monthly Plan", code="PLAN-MTH", billing_frequency="monthly", allow_pause=True)
        db.session.add_all([prod, plan])
        db.session.commit()

        admin_headers = self._login("admin@brightloop.com", "AdminPass123!")

        # Create quotation: 2 units of Software License @ $100 = $200. Tax 18% = $36. Total = $236.
        res = self.client.post("/api/quotations", headers=admin_headers, json={
            "customer_id": cust.id,
            "plan_id": plan.id,
            "items": [
                {"product_id": prod.id, "quantity": 2}
            ]
        })
        self.assertEqual(res.status_code, 201)
        q_data = res.get_json()["data"]
        q_id = q_data["id"]

        self.assertEqual(q_data["subtotal"], 200.00)
        self.assertEqual(q_data["tax_amount"], 36.00)
        self.assertEqual(q_data["total_amount"], 236.00)
        self.assertEqual(q_data["status"], "draft")

        # Mark sent
        res_sent = self.client.post(f"/api/quotations/{q_id}/send", headers=admin_headers)
        self.assertEqual(res_sent.status_code, 200)
        self.assertEqual(res_sent.get_json()["data"]["status"], "sent")

        # Confirm quotation
        res_confirm = self.client.post(f"/api/quotations/{q_id}/confirm", headers=admin_headers)
        self.assertEqual(res_confirm.status_code, 200)
        self.assertEqual(res_confirm.get_json()["data"]["status"], "confirmed")

        # Attempt to edit confirmed quotation -> rejected
        res_edit = self.client.put(f"/api/quotations/{q_id}", headers=admin_headers, json={"notes": "Updated note"})
        self.assertEqual(res_edit.status_code, 400)
        self.assertIn("Cannot edit quotation in 'confirmed' status", res_edit.get_json()["error"])

    def test_quotation_conversion_and_subscription_lifecycle(self):
        """Test converting quotation to subscription, pause policy, resume, renew, close, and duplicate prevention."""
        admin = User(email="admin@brightloop.com", first_name="Admin", last_name="User", role="admin")
        admin.set_password("AdminPass123!")
        cust = User(email="cust@brightloop.com", first_name="Customer", last_name="One", role="customer")
        cust.set_password("CustPass123!")
        db.session.add_all([admin, cust])
        db.session.flush()

        from decimal import Decimal
        prod = Product(name="Enterprise Server", code="SRV-ENT", sales_price=Decimal("500.00"), tax_rate=Decimal("18.00"))
        # Plan allows pause and renewal
        plan = SubscriptionPlan(
            name="Cloud Standard",
            code="PLAN-CLOUD-STD",
            billing_frequency="monthly",
            allow_pause=True,
            allow_renewal=True,
            allow_early_close=True
        )
        # Plan that denies pause
        no_pause_plan = SubscriptionPlan(
            name="Strict Plan",
            code="PLAN-STRICT",
            billing_frequency="monthly",
            allow_pause=False,
            allow_renewal=True
        )
        db.session.add_all([prod, plan, no_pause_plan])
        db.session.commit()

        admin_headers = self._login("admin@brightloop.com", "AdminPass123!")

        # Create and confirm quotation
        res_q = self.client.post("/api/quotations", headers=admin_headers, json={
            "customer_id": cust.id,
            "plan_id": plan.id,
            "items": [{"product_id": prod.id, "quantity": 1}]
        })
        q_id = res_q.get_json()["data"]["id"]
        self.client.post(f"/api/quotations/{q_id}/confirm", headers=admin_headers)

        # Convert quotation to subscription
        res_conv = self.client.post(f"/api/subscriptions/convert-quotation/{q_id}", headers=admin_headers)
        self.assertEqual(res_conv.status_code, 201)
        sub_data = res_conv.get_json()["data"]
        sub_id = sub_data["id"]

        self.assertEqual(sub_data["status"], "active")
        self.assertEqual(sub_data["total_amount"], 590.00)  # $500 + 18% tax
        self.assertIn("SUB-", sub_data["subscription_number"])

        # Prevent duplicate conversion of same quotation
        res_dup_conv = self.client.post(f"/api/subscriptions/convert-quotation/{q_id}", headers=admin_headers)
        self.assertEqual(res_dup_conv.status_code, 400)
        self.assertIn("already been converted", res_dup_conv.get_json()["error"])

        # Pause subscription (allowed by plan policy)
        res_pause = self.client.post(f"/api/subscriptions/{sub_id}/pause", headers=admin_headers)
        self.assertEqual(res_pause.status_code, 200)
        self.assertEqual(res_pause.get_json()["data"]["status"], "paused")

        # Resume subscription
        res_resume = self.client.post(f"/api/subscriptions/{sub_id}/resume", headers=admin_headers)
        self.assertEqual(res_resume.status_code, 200)
        self.assertEqual(res_resume.get_json()["data"]["status"], "active")

        # Renew subscription
        res_renew = self.client.post(f"/api/subscriptions/{sub_id}/renew", headers=admin_headers)
        self.assertEqual(res_renew.status_code, 200)
        self.assertEqual(res_renew.get_json()["data"]["status"], "active")

        # Close subscription
        res_close = self.client.post(f"/api/subscriptions/{sub_id}/close", headers=admin_headers)
        self.assertEqual(res_close.status_code, 200)
        self.assertEqual(res_close.get_json()["data"]["status"], "closed")

        # Verify audit logs exist
        res_get = self.client.get(f"/api/subscriptions/{sub_id}", headers=admin_headers)
        logs = res_get.get_json()["data"]["audit_logs"]
        actions = [log["action"] for log in logs]
        self.assertIn("created", actions)
        self.assertIn("paused", actions)
        self.assertIn("resumed", actions)
        self.assertIn("renewed", actions)
        self.assertIn("closed", actions)

        # Test pause rejection on plan with allow_pause = False
        res_strict_q = self.client.post("/api/quotations", headers=admin_headers, json={
            "customer_id": cust.id,
            "plan_id": no_pause_plan.id,
            "items": [{"product_id": prod.id, "quantity": 1}]
        })
        sq_id = res_strict_q.get_json()["data"]["id"]
        self.client.post(f"/api/quotations/{sq_id}/confirm", headers=admin_headers)
        res_strict_sub = self.client.post(f"/api/subscriptions/convert-quotation/{sq_id}", headers=admin_headers)
        strict_sub_id = res_strict_sub.get_json()["data"]["id"]

        # Attempt to pause -> rejected by plan policy
        res_fail_pause = self.client.post(f"/api/subscriptions/{strict_sub_id}/pause", headers=admin_headers)
        self.assertEqual(res_fail_pause.status_code, 400)
        self.assertIn("policy does not permit pausing", res_fail_pause.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
