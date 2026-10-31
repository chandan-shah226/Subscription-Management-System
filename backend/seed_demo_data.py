"""
Demo Data Seeder — Brightloop Software
=======================================
Adds realistic demo data across all 6 modules so the application
looks properly populated. Run once from inside the backend/ folder:

    python seed_demo_data.py

Safe to re-run — skips records that already exist.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'), override=False)

from datetime import date, timedelta
from decimal import Decimal
from app import create_app
from models import (
    db, User, Product, ProductVariant, SubscriptionPlan, PlanProduct,
    Subscription, SubscriptionItem, Invoice, InvoiceItem, Discount,
    DiscountRedemption, Payment
)

app = create_app('development')

def upsert_user(email, first, last, role, password):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, first_name=first, last_name=last, role=role, is_active=True)
        u.set_password(password)
        db.session.add(u)
        db.session.flush()
        print(f"  ✅ User created: {email} [{role}]")
    else:
        print(f"  ⏭️  User exists:  {email}")
    return u

def upsert_product(code, name, desc, price, tax):
    p = Product.query.filter_by(code=code).first()
    if not p:
        p = Product(code=code, name=name, description=desc,
                    sales_price=Decimal(str(price)), tax_rate=Decimal(str(tax)),
                    product_type="service", is_active=True)
        db.session.add(p)
        db.session.flush()
        print(f"  ✅ Product created: {code}")
    else:
        print(f"  ⏭️  Product exists:  {code}")
    return p

def upsert_plan(code, name, price, freq):
    pl = SubscriptionPlan.query.filter_by(code=code).first()
    if not pl:
        pl = SubscriptionPlan(code=code, name=name,
                              base_price=Decimal(str(price)),
                              billing_frequency=freq, is_active=True)
        db.session.add(pl)
        db.session.flush()
        print(f"  ✅ Plan created: {code}")
    else:
        print(f"  ⏭️  Plan exists:  {code}")
    return pl

def upsert_discount(code, desc, dtype, value, scope, limit, start_delta, end_delta, times_used=0):
    d = Discount.query.filter_by(code=code).first()
    if not d:
        today = date.today()
        d = Discount(
            code=code, description=desc, discount_type=dtype,
            value=Decimal(str(value)), scope=scope,
            min_purchase=Decimal("0.00"), min_quantity=1,
            usage_limit=limit, times_used=times_used,
            is_active=True,
            start_date=today + timedelta(days=start_delta),
            end_date=today + timedelta(days=end_delta)
        )
        db.session.add(d)
        db.session.flush()
        print(f"  ✅ Discount created: {code}")
    else:
        print(f"  ⏭️  Discount exists:  {code}")
    return d

with app.app_context():
    db.create_all()

    print("\n━━━ USERS ━━━")
    admin = upsert_user("admin@brightloop.com",  "Arjun",   "Mehta",     "admin",    "Admin@123!")
    staff = upsert_user("staff@brightloop.com",  "Priya",   "Sharma",    "staff",    "Staff@123!")
    c1    = upsert_user("rajesh.kumar@techcorp.in",  "Rajesh",  "Kumar",  "customer", "Customer@123!")
    c2    = upsert_user("anita.singh@globalhr.com",  "Anita",   "Singh",  "customer", "Customer@123!")
    c3    = upsert_user("vikram.patel@financeio.in", "Vikram",  "Patel",  "customer", "Customer@123!")
    c4    = upsert_user("sneha.joshi@ecomhub.com",   "Sneha",   "Joshi",  "customer", "Customer@123!")
    db.session.commit()

    print("\n━━━ PRODUCTS ━━━")
    p1 = upsert_product("PROD-CLOUD-01", "Cloud Hosting Infrastructure",
                        "99.9% uptime SLA cloud servers with auto-scaling, CDN, and daily backups.",
                        1200, 18)
    p2 = upsert_product("PROD-SUPP-247", "24/7 Premium Technical Support",
                        "Round-the-clock dedicated support with <2hr SLA response guarantee.",
                        350, 18)
    p3 = upsert_product("PROD-ERP-ENT", "ERP Enterprise Suite",
                        "Full-featured ERP with HR, Payroll, Inventory, Finance, and CRM modules.",
                        4500, 18)
    p4 = upsert_product("PROD-CRM-PRO", "CRM Pro Platform",
                        "AI-driven customer management: leads, pipeline, automation, and analytics.",
                        1800, 18)
    p5 = upsert_product("PROD-ANALYTICS", "Business Intelligence & Analytics",
                        "Real-time dashboards, custom reports, and data warehouse integrations.",
                        900, 18)
    p6 = upsert_product("PROD-BACKUP", "Secure Cloud Backup & DR",
                        "Encrypted automated backups with geo-redundancy and one-click restore.",
                        450, 18)
    db.session.commit()

    print("\n━━━ SUBSCRIPTION PLANS ━━━")
    pl1 = upsert_plan("PLAN-ENT-MONTHLY",  "SaaS Enterprise Monthly",  1500, "monthly")
    pl2 = upsert_plan("PLAN-PRO-YEARLY",   "SaaS Annual Pro",         14000, "yearly")
    pl3 = upsert_plan("PLAN-STARTER-MON",  "Starter Monthly",           799, "monthly")
    pl4 = upsert_plan("PLAN-GROWTH-MON",   "Growth Monthly",           2499, "monthly")
    db.session.commit()

    print("\n━━━ DISCOUNTS ━━━")
    d_save10   = upsert_discount("SAVE10",    "10% Off All Invoices — Loyalty Reward",          "percentage", 10,  "all",          200, -30, 60,  47)
    d_sub20    = upsert_discount("SUB20",     "20% Off Subscription Renewal — Early Bird",      "percentage", 20,  "subscription", 100, -15, 45,  23)
    d_flat500  = upsert_discount("FLAT500",   "Flat ₹500 Off on Orders Above ₹2000",            "fixed",      500, "all",          50,  -60, 30,  11)
    d_newcust  = upsert_discount("WELCOME15", "15% New Customer Welcome Discount",              "percentage", 15,  "all",          300, -90, 90,  89)
    d_q4sale   = upsert_discount("Q4SALE25",  "Q4 Sale — 25% Off Cloud Products",               "percentage", 25,  "product",      150, -5,  30,   5)
    d_expired  = upsert_discount("DIWALI10",  "Diwali Special 10% — Expired",                  "percentage", 10,  "all",          500, -120, -1,  412)
    db.session.commit()

    # Mark expired discount inactive
    d_expired_obj = Discount.query.filter_by(code="DIWALI10").first()
    if d_expired_obj and d_expired_obj.is_active:
        d_expired_obj.is_active = False
        db.session.commit()

    print("\n━━━ SUBSCRIPTIONS ━━━")
    today = date.today()

    def make_subscription(num, customer, plan, status, start_delta_days, products_and_qty):
        sub = Subscription.query.filter_by(subscription_number=num).first()
        if sub:
            print(f"  ⏭️  Subscription exists: {num}")
            return sub
        start = today - timedelta(days=start_delta_days)
        sub = Subscription(
            subscription_number=num,
            customer_id=customer.id,
            plan_id=plan.id,
            status=status,
            billing_frequency="monthly",
            start_date=start,
            next_billing_date=today + timedelta(days=30),
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00")
        )
        db.session.add(sub)
        db.session.flush()
        total = Decimal("0.00")
        for prod, qty in products_and_qty:
            unit = prod.sales_price
            tax  = (unit * Decimal(str(qty)) * prod.tax_rate / 100).quantize(Decimal("0.01"))
            line_total = unit * qty + tax
            total += line_total
            item = SubscriptionItem(
                subscription_id=sub.id,
                product_id=prod.id,
                quantity=qty,
                unit_price=unit,
                tax_rate=prod.tax_rate,
                tax_amount=tax,
                total_price=line_total
            )
            db.session.add(item)
        sub.total_amount = total
        db.session.commit()
        print(f"  ✅ Subscription created: {num} [{status}]")
        return sub

    sub1 = make_subscription("SUB-2026-0001", c1, pl1, "active",  60, [(p1,1),(p2,1)])
    sub2 = make_subscription("SUB-2026-0002", c2, pl2, "active",  90, [(p3,1)])
    sub3 = make_subscription("SUB-2026-0003", c3, pl3, "active",  30, [(p4,1),(p5,1)])
    sub4 = make_subscription("SUB-2026-0004", c4, pl4, "active",  45, [(p1,1),(p2,1),(p6,1)])
    sub5 = make_subscription("SUB-2026-0005", c1, pl3, "paused",  120, [(p5,1)])
    db.session.commit()

    print("\n━━━ INVOICES & PAYMENTS ━━━")

    def make_invoice(num, customer, subscription, inv_date_delta, due_delta, items_data,
                     disc_code=None, disc_obj=None, status="Paid",
                     pay_method=None, pay_source="manual", pay_ref=None, rzp_id=None):
        existing = Invoice.query.filter_by(invoice_number=num).first()
        if existing:
            print(f"  ⏭️  Invoice exists: {num}")
            return existing

        inv_date = today - timedelta(days=inv_date_delta)
        due_date = inv_date + timedelta(days=due_delta)

        subtotal = Decimal("0.00")
        tax_total = Decimal("0.00")
        inv_items = []
        for desc, qty, unit_price, tax_rate in items_data:
            qty_d = Decimal(str(qty))
            up_d  = Decimal(str(unit_price))
            tr_d  = Decimal(str(tax_rate))
            line_subtotal = qty_d * up_d
            tax_amt = (line_subtotal * tr_d / 100).quantize(Decimal("0.01"))
            subtotal  += line_subtotal
            tax_total += tax_amt
            inv_items.append((desc, qty_d, up_d, tr_d, tax_amt, line_subtotal + tax_amt))

        disc_amount = Decimal("0.00")
        disc_id = None
        if disc_obj:
            disc_id = disc_obj.id
            if disc_obj.discount_type == "percentage":
                disc_amount = (subtotal * disc_obj.value / 100).quantize(Decimal("0.01"))
            else:
                disc_amount = min(disc_obj.value, subtotal)

        total = (subtotal - disc_amount + tax_total).quantize(Decimal("0.01"))
        if total < Decimal("0.00"):
            total = Decimal("0.00")

        amount_paid = total if status == "Paid" else (
            Decimal("0.00") if status in ("Draft", "Cancelled") else Decimal("0.00")
        )
        outstanding = total - amount_paid

        inv = Invoice(
            invoice_number=num,
            customer_id=customer.id,
            subscription_id=subscription.id if subscription else None,
            billing_period_start=inv_date,
            billing_period_end=due_date,
            invoice_date=inv_date,
            due_date=due_date,
            subtotal=subtotal,
            discount_id=disc_id,
            discount_code=disc_code,
            discount_amount=disc_amount,
            tax_amount=tax_total,
            total_amount=total,
            amount_paid=amount_paid,
            outstanding_amount=outstanding,
            status=status,
            notes=f"Generated for subscription {subscription.subscription_number}" if subscription else "Manual invoice"
        )
        db.session.add(inv)
        db.session.flush()

        for desc, qty, up, tr, tax_amt, line_total in inv_items:
            ii = InvoiceItem(
                invoice_id=inv.id,
                description=desc,
                quantity=qty,
                unit_price=up,
                discount_amount=Decimal("0.00"),
                tax_rate=tr,
                tax_amount=tax_amt,
                total_amount=line_total
            )
            db.session.add(ii)

        if status == "Paid" and pay_method:
            pay = Payment(
                invoice_id=inv.id,
                amount=total,
                currency="INR",
                payment_method=pay_method,
                payment_source=pay_source,
                status="captured",
                payment_date=inv_date + timedelta(days=3),
                reference_number=pay_ref,
                razorpay_payment_id=rzp_id,
                notes=f"Payment for {num}",
                created_by_id=staff.id if pay_source == "manual" else None
            )
            db.session.add(pay)

        if disc_obj and status in ("Paid", "Confirmed"):
            redemption = DiscountRedemption(
                discount_id=disc_obj.id,
                invoice_id=inv.id,
                customer_id=customer.id,
                amount_applied=disc_amount
            )
            db.session.add(redemption)
            disc_obj.times_used = (disc_obj.times_used or 0) + 1

        db.session.commit()
        print(f"  ✅ Invoice created: {num} [{status}] ₹{total}")
        return inv

    # ── Rajesh Kumar (c1) — SUB-2026-0001 ───────────────────────────────────
    make_invoice("INV-2026-0001", c1, sub1,
                 inv_date_delta=60, due_delta=15,
                 items_data=[
                     ("Cloud Hosting Infrastructure — Monthly", 1, 1200, 18),
                     ("24/7 Premium Technical Support — Monthly", 1, 350, 18),
                 ],
                 disc_code="SAVE10", disc_obj=d_save10, status="Paid",
                 pay_method="Bank Transfer", pay_source="manual", pay_ref="NEFT-BL-0001")

    make_invoice("INV-2026-0002", c1, sub1,
                 inv_date_delta=30, due_delta=15,
                 items_data=[
                     ("Cloud Hosting Infrastructure — Monthly", 1, 1200, 18),
                     ("24/7 Premium Technical Support — Monthly", 1, 350, 18),
                 ],
                 disc_code=None, disc_obj=None, status="Paid",
                 pay_method="UPI", pay_source="manual", pay_ref="UPI-BL-0002")

    make_invoice("INV-2026-0003", c1, sub1,
                 inv_date_delta=0, due_delta=15,
                 items_data=[
                     ("Cloud Hosting Infrastructure — Monthly", 1, 1200, 18),
                     ("24/7 Premium Technical Support — Monthly", 1, 350, 18),
                 ],
                 disc_code="SAVE10", disc_obj=d_save10, status="Confirmed",
                 pay_method=None)

    # ── Anita Singh (c2) — SUB-2026-0002 ─────────────────────────────────────
    make_invoice("INV-2026-0004", c2, sub2,
                 inv_date_delta=90, due_delta=30,
                 items_data=[
                     ("ERP Enterprise Suite — Annual Subscription", 1, 4500, 18),
                 ],
                 disc_code="WELCOME15", disc_obj=d_newcust, status="Paid",
                 pay_method="Bank Transfer", pay_source="manual", pay_ref="NEFT-BL-0004")

    make_invoice("INV-2026-0005", c2, sub2,
                 inv_date_delta=60, due_delta=30,
                 items_data=[
                     ("ERP Enterprise Suite — Annual Subscription", 1, 4500, 18),
                 ],
                 disc_code="SUB20", disc_obj=d_sub20, status="Paid",
                 pay_method="Razorpay", pay_source="razorpay",
                 pay_ref="order_BL_sub20_0005",
                 rzp_id="pay_BL_razorpay_0005")

    make_invoice("INV-2026-0006", c2, sub2,
                 inv_date_delta=5, due_delta=25,
                 items_data=[
                     ("ERP Enterprise Suite — Annual Subscription", 1, 4500, 18),
                 ],
                 disc_code=None, disc_obj=None, status="Confirmed",
                 pay_method=None)

    # ── Vikram Patel (c3) — SUB-2026-0003 ────────────────────────────────────
    make_invoice("INV-2026-0007", c3, sub3,
                 inv_date_delta=30, due_delta=15,
                 items_data=[
                     ("CRM Pro Platform — Monthly", 1, 1800, 18),
                     ("Business Intelligence & Analytics — Monthly", 1, 900, 18),
                 ],
                 disc_code="FLAT500", disc_obj=d_flat500, status="Paid",
                 pay_method="Credit Card", pay_source="manual", pay_ref="CC-BL-0007")

    make_invoice("INV-2026-0008", c3, sub3,
                 inv_date_delta=3, due_delta=15,
                 items_data=[
                     ("CRM Pro Platform — Monthly", 1, 1800, 18),
                     ("Business Intelligence & Analytics — Monthly", 1, 900, 18),
                 ],
                 disc_code=None, disc_obj=None, status="Draft",
                 pay_method=None)

    # ── Sneha Joshi (c4) — SUB-2026-0004 ─────────────────────────────────────
    make_invoice("INV-2026-0009", c4, sub4,
                 inv_date_delta=45, due_delta=15,
                 items_data=[
                     ("Cloud Hosting Infrastructure — Monthly", 1, 1200, 18),
                     ("24/7 Premium Technical Support — Monthly", 1, 350, 18),
                     ("Secure Cloud Backup & DR — Monthly", 1, 450, 18),
                 ],
                 disc_code="SAVE10", disc_obj=d_save10, status="Paid",
                 pay_method="Bank Transfer", pay_source="manual", pay_ref="NEFT-BL-0009")

    make_invoice("INV-2026-0010", c4, sub4,
                 inv_date_delta=15, due_delta=15,
                 items_data=[
                     ("Cloud Hosting Infrastructure — Monthly", 1, 1200, 18),
                     ("24/7 Premium Technical Support — Monthly", 1, 350, 18),
                     ("Secure Cloud Backup & DR — Monthly", 1, 450, 18),
                 ],
                 disc_code="SAVE10", disc_obj=d_save10, status="Paid",
                 pay_method="Razorpay", pay_source="razorpay",
                 pay_ref="order_BL_sneha_0010",
                 rzp_id="pay_BL_razorpay_0010")

    make_invoice("INV-2026-0011", c4, sub4,
                 inv_date_delta=2, due_delta=15,
                 items_data=[
                     ("Cloud Hosting Infrastructure — Monthly", 1, 1200, 18),
                     ("24/7 Premium Technical Support — Monthly", 1, 350, 18),
                     ("Secure Cloud Backup & DR — Monthly", 1, 450, 18),
                 ],
                 disc_code=None, disc_obj=None, status="Draft",
                 pay_method=None)

    # Overdue invoice (due date in the past, Confirmed & not paid)
    past_inv = Invoice.query.filter_by(invoice_number="INV-2026-OVERDUE01").first()
    if not past_inv:
        ov = Invoice(
            invoice_number="INV-2026-OVERDUE01",
            customer_id=c3.id,
            subscription_id=sub3.id,
            invoice_date=today - timedelta(days=45),
            due_date=today - timedelta(days=15),
            subtotal=Decimal("2700.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("486.00"),
            total_amount=Decimal("3186.00"),
            amount_paid=Decimal("0.00"),
            outstanding_amount=Decimal("3186.00"),
            status="Confirmed",
            notes="Overdue — follow-up required."
        )
        db.session.add(ov)
        db.session.flush()
        ii_ov = InvoiceItem(
            invoice_id=ov.id,
            description="CRM Pro Platform — Monthly (Oct billing — overdue)",
            quantity=Decimal("1"), unit_price=Decimal("1800"),
            discount_amount=Decimal("0"), tax_rate=Decimal("18"),
            tax_amount=Decimal("324"), total_amount=Decimal("2124")
        )
        ii_ov2 = InvoiceItem(
            invoice_id=ov.id,
            description="Business Intelligence & Analytics — Monthly (Oct — overdue)",
            quantity=Decimal("1"), unit_price=Decimal("900"),
            discount_amount=Decimal("0"), tax_rate=Decimal("18"),
            tax_amount=Decimal("162"), total_amount=Decimal("1062")
        )
        db.session.add_all([ii_ov, ii_ov2])
        db.session.commit()
        print(f"  ✅ Invoice created: INV-2026-OVERDUE01 [Confirmed/Overdue] ₹3186.00")
    else:
        print(f"  ⏭️  Invoice exists:  INV-2026-OVERDUE01")

    print("\n━━━ FINAL SUMMARY ━━━")
    print(f"  Users:         {User.query.count()}")
    print(f"  Products:      {Product.query.count()}")
    print(f"  Plans:         {SubscriptionPlan.query.count()}")
    print(f"  Subscriptions: {Subscription.query.count()}")
    print(f"  Invoices:      {Invoice.query.count()}")
    print(f"  Discounts:     {Discount.query.count()}")
    print(f"  Payments:      {Payment.query.count()}")
    print(f"  Redemptions:   {DiscountRedemption.query.count()}")
    print("\n✅ Demo data seeding complete!\n")
    print("  Login credentials:")
    print("    Admin  → admin@brightloop.com  / Admin@123!")
    print("    Staff  → staff@brightloop.com  / Staff@123!")
    print("    Cust1  → rajesh.kumar@techcorp.in  / Customer@123!")
    print("    Cust2  → anita.singh@globalhr.com  / Customer@123!")
    print("    Cust3  → vikram.patel@financeio.in / Customer@123!")
    print("    Cust4  → sneha.joshi@ecomhub.com   / Customer@123!")
