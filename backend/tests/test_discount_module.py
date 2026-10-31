"""
Test Suite for Module 5: Discount Management
============================================
Comprehensive test coverage for:
1. Percentage vs Fixed discount calculations and capping.
2. Minimum purchase amount and quantity thresholds.
3. Date window validity (start_date, end_date).
4. Atomic usage limits and redemption logging.
5. Scoped discounts (all, subscription, product).
6. Automatic discount selection and application on subscription billing.
7. Historical invoice immutability.
8. Admin RBAC protection (Customer forbidden, Admin authorized).
9. Discount preview API endpoint.
"""

import sys
import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from flask_jwt_extended import create_access_token

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from models import (
    db, User, Discount, DiscountProduct, DiscountRedemption,
    Invoice, InvoiceItem, Subscription, SubscriptionPlan, Product
)
from services.discount_service import (
    create_discount, update_discount, toggle_discount_status,
    select_best_discount, record_discount_redemption, revert_discount_redemption
)
from services.invoice_service import generate_subscription_invoices, confirm_invoice, cancel_invoice


class DiscountModuleTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        # Create Admin
        self.admin = User(
            email="admin_disc@test.com",
            first_name="Admin",
            last_name="Disc",
            role="admin"
        )
        self.admin.set_password("AdminPass@123")
        db.session.add(self.admin)

        # Create Customer
        self.customer = User(
            email="customer_disc@test.com",
            first_name="Cust",
            last_name="Disc",
            role="customer"
        )
        self.customer.set_password("CustPass@123")
        db.session.add(self.customer)
        db.session.commit()

        self.admin_token = create_access_token(
            identity=str(self.admin.id),
            additional_claims={"role": self.admin.role, "email": self.admin.email}
        )
        self.customer_token = create_access_token(
            identity=str(self.customer.id),
            additional_claims={"role": self.customer.role, "email": self.customer.email}
        )
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.customer_headers = {"Authorization": f"Bearer {self.customer_token}"}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_percentage_and_fixed_discount_calculations(self):
        """Verifies percentage and fixed calculations, rounding, and capping."""
        disc_pct = Discount(
            code="PERCENT20",
            discount_type="percentage",
            value=Decimal("20.00"),
            is_active=True
        )
        disc_fix = Discount(
            code="FLAT150",
            discount_type="fixed",
            value=Decimal("150.00"),
            is_active=True
        )
        db.session.add_all([disc_pct, disc_fix])
        db.session.commit()

        # 20% on 1000 = 200
        self.assertEqual(disc_pct.calculate_discount_amount(Decimal("1000.00")), Decimal("200.00"))
        # Fixed 150 on 1000 = 150
        self.assertEqual(disc_fix.calculate_discount_amount(Decimal("1000.00")), Decimal("150.00"))
        # Fixed 150 on 100 capped at 100
        self.assertEqual(disc_fix.calculate_discount_amount(Decimal("100.00")), Decimal("100.00"))

    def test_minimum_purchase_and_quantity_thresholds(self):
        """Verifies discount is rejected when below minimum purchase or quantity."""
        disc = Discount(
            code="MINPURCH500",
            discount_type="percentage",
            value=Decimal("10.00"),
            min_purchase=Decimal("500.00"),
            min_quantity=2,
            is_active=True
        )
        db.session.add(disc)
        db.session.commit()

        # Subtotal too low (400 < 500)
        eligible, reason = disc.is_eligible(subtotal=Decimal("400.00"), quantity=2)
        self.assertFalse(eligible)
        self.assertIn("Minimum purchase", reason)

        # Quantity too low (1 < 2)
        eligible, reason = disc.is_eligible(subtotal=Decimal("600.00"), quantity=1)
        self.assertFalse(eligible)
        self.assertIn("Minimum quantity", reason)

        # Both satisfied
        eligible, reason = disc.is_eligible(subtotal=Decimal("600.00"), quantity=2)
        self.assertTrue(eligible)

    def test_validity_date_window(self):
        """Verifies start_date and end_date validity enforcement."""
        today = date.today()
        future_disc = Discount(
            code="FUTURE",
            discount_type="percentage",
            value=Decimal("10.00"),
            start_date=today + timedelta(days=5),
            is_active=True
        )
        expired_disc = Discount(
            code="EXPIRED",
            discount_type="percentage",
            value=Decimal("10.00"),
            end_date=today - timedelta(days=1),
            is_active=True
        )
        valid_disc = Discount(
            code="ACTIVE_NOW",
            discount_type="percentage",
            value=Decimal("10.00"),
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
            is_active=True
        )
        db.session.add_all([future_disc, expired_disc, valid_disc])
        db.session.commit()

        self.assertFalse(future_disc.is_eligible(Decimal("100.00"))[0])
        self.assertFalse(expired_disc.is_eligible(Decimal("100.00"))[0])
        self.assertTrue(valid_disc.is_eligible(Decimal("100.00"))[0])

    def test_usage_limit_and_redemption_tracking(self):
        """Verifies max usage limit stops application once reached."""
        disc = Discount(
            code="ONETIME",
            discount_type="fixed",
            value=Decimal("50.00"),
            usage_limit=1,
            times_used=0,
            is_active=True
        )
        db.session.add(disc)
        db.session.commit()

        # First redemption succeeds
        red = record_discount_redemption(disc.id, invoice_id=1, customer_id=self.customer.id, amount=Decimal("50.00"))
        self.assertIsNotNone(red)
        self.assertEqual(disc.times_used, 1)
        self.assertTrue(disc.is_exhausted)

        # Second redemption fails
        with self.assertRaises(ValueError):
            record_discount_redemption(disc.id, invoice_id=2, customer_id=self.customer.id, amount=Decimal("50.00"))

        # Revert first redemption
        revert_discount_redemption(invoice_id=1)
        self.assertEqual(disc.times_used, 0)
        self.assertFalse(disc.is_exhausted)

    def test_scoped_discounts_product_and_subscription(self):
        """Verifies product-scoped vs subscription-scoped discounts."""
        prod1 = Product(name="Prod 1", code="P1", sales_price=Decimal("100.00"), cost_price=Decimal("50.00"))
        prod2 = Product(name="Prod 2", code="P2", sales_price=Decimal("200.00"), cost_price=Decimal("100.00"))
        db.session.add_all([prod1, prod2])
        db.session.flush()

        disc_prod = Discount(code="PROD1ONLY", discount_type="percentage", value=Decimal("15.00"), scope="product", is_active=True)
        db.session.add(disc_prod)
        db.session.flush()
        db.session.add(DiscountProduct(discount_id=disc_prod.id, product_id=prod1.id))
        db.session.commit()

        # Product 1 is eligible
        self.assertTrue(disc_prod.is_eligible(Decimal("100.00"), product_ids=[prod1.id])[0])
        # Product 2 alone is NOT eligible
        self.assertFalse(disc_prod.is_eligible(Decimal("200.00"), product_ids=[prod2.id])[0])

    def test_automatic_discount_selection_for_subscription(self):
        """Verifies select_best_discount picks the highest savings discount."""
        d_small = Discount(code="SAVE5", discount_type="percentage", value=Decimal("5.00"), is_active=True)
        d_large = Discount(code="SAVE25", discount_type="percentage", value=Decimal("25.00"), is_active=True)
        db.session.add_all([d_small, d_large])
        db.session.commit()

        best, amount = select_best_discount(Decimal("1000.00"), is_subscription=True)
        self.assertEqual(best.code, "SAVE25")
        self.assertEqual(amount, Decimal("250.00"))

    def test_recurring_billing_applies_best_discount(self):
        """Verifies that recurring invoice generation automatically binds the best discount."""
        disc = Discount(code="AUTOSUB10", discount_type="percentage", value=Decimal("10.00"), scope="subscription", is_active=True)
        plan = SubscriptionPlan(name="Plan Test", code="PLAN-T1", base_price=Decimal("1000.00"), billing_frequency="monthly")
        db.session.add_all([disc, plan])
        db.session.flush()

        today = date.today()
        sub = Subscription(
            subscription_number="SUB-DISC-01",
            customer_id=self.customer.id,
            plan_id=plan.id,
            status="active",
            billing_frequency="monthly",
            start_date=today - timedelta(days=30),
            next_billing_date=today,
            subtotal=Decimal("1000.00"),
            tax_amount=Decimal("180.00"),
            total_amount=Decimal("1180.00")
        )
        db.session.add(sub)
        db.session.commit()

        res = generate_subscription_invoices(target_date=today)
        self.assertEqual(res["generated_count"], 1)

        inv = Invoice.query.filter_by(subscription_id=sub.id).first()
        self.assertIsNotNone(inv)
        self.assertEqual(inv.discount_code, "AUTOSUB10")
        self.assertEqual(inv.discount_amount, Decimal("100.00"))

    def test_historical_invoice_immutability(self):
        """Verifies confirming an invoice freezes discount and deactivating rule later does not alter invoice."""
        disc = Discount(code="FROZEN10", discount_type="percentage", value=Decimal("10.00"), is_active=True)
        db.session.add(disc)
        db.session.flush()

        inv = Invoice(
            invoice_number="INV-FROZEN-01",
            customer_id=self.customer.id,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=15),
            subtotal=Decimal("1000.00"),
            discount_id=disc.id,
            discount_code="FROZEN10",
            discount_amount=Decimal("100.00"),
            tax_amount=Decimal("162.00"),
            total_amount=Decimal("1062.00"),
            amount_paid=Decimal("0.00"),
            outstanding_amount=Decimal("1062.00"),
            status="Draft"
        )
        db.session.add(inv)
        db.session.flush()
        db.session.add(InvoiceItem(invoice_id=inv.id, description="Item", quantity=1, unit_price=1000, total_amount=1062))
        db.session.commit()

        # Confirm invoice
        confirm_invoice(inv.id)
        self.assertEqual(disc.times_used, 1)

        # Deactivate discount rule
        disc.is_active = False
        db.session.commit()

        # Verify historical invoice remains completely unaltered
        reloaded = db.session.get(Invoice, inv.id)
        self.assertEqual(reloaded.discount_amount, Decimal("100.00"))
        self.assertEqual(reloaded.total_amount, Decimal("1062.00"))

    def test_admin_rbac_protection(self):
        """Verifies customer cannot create/edit discounts; Admin can."""
        # Customer tries to create discount -> 403 Forbidden
        res = self.client.post("/api/discounts", json={"code": "HACK", "value": 50}, headers=self.customer_headers)
        self.assertEqual(res.status_code, 403)

        # Admin creates discount -> 201 Created
        res = self.client.post("/api/discounts", json={
            "code": "PROMO2026",
            "discount_type": "percentage",
            "value": 15,
            "min_purchase": 200
        }, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["discount"]["code"], "PROMO2026")

    def test_discount_preview_endpoint(self):
        """Verifies /api/discounts/preview evaluates eligibility for customer cart."""
        disc = Discount(code="CART15", discount_type="percentage", value=Decimal("15.00"), min_purchase=Decimal("500.00"), is_active=True)
        db.session.add(disc)
        db.session.commit()

        # Preview with code meeting minimum purchase
        res = self.client.post("/api/discounts/preview", json={
            "code": "CART15",
            "subtotal": 1000.00,
            "quantity": 1
        }, headers=self.customer_headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["eligible"])
        self.assertEqual(data["discount_amount"], 150.00)


if __name__ == "__main__":
    unittest.main()
