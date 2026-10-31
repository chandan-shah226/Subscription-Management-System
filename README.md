# Subscription Management System

A centralized ERP-style platform for managing products, subscription plans, customer subscriptions, recurring billing, invoices, payments, and financial reporting.

---

## About the Project

The Subscription Management System is developed for **Brightloop Software** as part of a hackathon challenge.

The objective is to automate the complete subscription business lifecycle through a single platform, reducing manual work and improving billing accuracy, payment tracking, and financial visibility.

This repository contains the complete end-to-end implementation of **Modules 1, 2, and 3**:
- **Module 1: User Management & Authentication**
- **Module 2: Product & Plan Management**
- **Module 3: Quotation & Subscription Management**

---

## Technology Stack

- **Backend:** Python 3.10+, Flask 3.x
- **Database & ORM:** SQLite (local), SQLAlchemy (`Flask-SQLAlchemy 3.x`)
- **Authentication & Security:** JWT (`Flask-JWT-Extended 4.x`), Werkzeug password hashing (`pbkdf2:sha256`)
- **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3 (No external JS frameworks)
- **API Architecture:** RESTful JSON APIs with CORS support and standardized envelopes
- **Testing:** Python `unittest` suite

---

## Project Structure

```text
Subscription-Management-System/
│
├── frontend/
│   ├── index.html                  # Single-page application entry point
│   ├── css/
│   │   └── style.css               # SaaS design system, responsive styles, modals & toasts
│   └── js/
│       ├── api.js                  # Centralized HTTP client with JWT header injection & error handling
│       ├── auth.js                 # Authentication state store, session persistence & navbar updater
│       ├── router.js               # Client-side hash SPA router with RBAC route guards
│       ├── main.js                 # Frontend bootstrapper & global toast notifications
│       └── views/
│           ├── authView.js         # Login, Registration, Forgot Password & Reset Password
│           ├── dashboardView.js    # Operational metrics, stats cards & quick actions
│           ├── userView.js         # User listing, Staff account creation & activation toggling
│           ├── productPlanView.js  # Product CRUD, brand variants & Subscription plans
│           ├── quotationView.js    # Multi-item quotation builder, templates & conversion
│           └── subscriptionView.js # Subscriptions, lifecycle actions & audit log timeline
│
├── backend/
│   ├── app.py                      # Application factory (create_app), extension & blueprint wiring
│   ├── config.py                   # Environment configs (Development, Testing, Production)
│   ├── models/
│   │   ├── __init__.py             # SQLAlchemy instance and model exports
│   │   ├── user.py                 # User, PasswordReset, and UserPermission models
│   │   ├── product.py              # Product and ProductVariant models
│   │   ├── plan.py                 # SubscriptionPlan and PlanProduct models
│   │   ├── quotation.py            # Quotation and QuotationItem models
│   │   └── subscription.py         # Subscription, SubscriptionItem, and SubscriptionAuditLog models
│   ├── routes/
│   │   ├── __init__.py             # Blueprint exports
│   │   ├── auth_routes.py          # /api/auth endpoints
│   │   ├── user_routes.py          # /api/users endpoints
│   │   ├── product_routes.py       # /api/products endpoints
│   │   ├── plan_routes.py          # /api/plans endpoints
│   │   ├── quotation_routes.py     # /api/quotations endpoints
│   │   └── subscription_routes.py  # /api/subscriptions endpoints
│   ├── services/
│   │   ├── __init__.py             # Service exports
│   │   ├── auth_service.py         # Password validation, hashing, JWT issuance & reset logic
│   │   ├── user_service.py         # Staff creation, user management & escalation prevention
│   │   ├── product_service.py      # Product/variant CRUD, price modifiers & availability
│   │   ├── plan_service.py         # Plan policies, frequencies & date window constraints
│   │   ├── quotation_service.py    # Line pricing, tax calculations, templates & status transitions
│   │   └── subscription_service.py # Lifecycle state machine, policy enforcement & audit logs
│   ├── middleware/
│   │   ├── __init__.py             # Middleware exports
│   │   └── auth.py                 # RBAC decorators, permission guards & JSON response helpers
│   ├── tests/
│   │   └── test_modules.py         # Automated test suite for Modules 1, 2, and 3
│   └── requirements.txt            # Python dependencies
│
├── instance/
│   └── .gitkeep                    # SQLite storage directory (database excluded from Git)
│
├── .gitignore                      # Git ignore rules for Python, virtual environments, IDEs, DBs
└── README.md                       # Complete documentation & API reference
```

---

## Seed Accounts (Ready for Testing)

When the backend runs, initial seed records are automatically provisioned:

| Role | Email | Password | Permissions & Scope |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@brightloop.com` | `Admin@123!` | Full access to users, products, plans, quotes, subscriptions |
| **Staff Member** | `staff@brightloop.com` | `Staff@123!` | Manages products, plans, customer quotes, and subscriptions |
| **Customer** | `customer@brightloop.com` | `Customer@123!` | Self-service: views personal quotes & subscriptions |

---

## REST API Reference

### 1. Authentication (`/api/auth`)
- `POST /api/auth/register`: Customer self-registration (validates password strength: >8 chars, upper, lower, special char).
- `POST /api/auth/login`: Authenticates credentials; returns Access and Refresh JWT tokens.
- `GET /api/auth/me`: Retrieves current authenticated user profile and permissions (`Bearer` token required).
- `POST /api/auth/forgot-password`: Requests time-limited, single-use password reset token (returns dev token in DEBUG mode).
- `POST /api/auth/reset-password`: Sets new password using verified reset token.

### 2. User Management (`/api/users`)
- `GET /api/users`: Lists users with role and search filters (Admin/Staff only).
- `GET /api/users/<id>`: Retrieves single user profile (Enforces IDOR: customers can only view their own profile).
- `POST /api/users`: Creates staff accounts (Admin only; staff cannot create admin accounts).
- `PUT /api/users/<id>`: Updates user profile/roles (Role escalation prevented).
- `PUT /api/users/<id>/toggle-active`: Activates or deactivates user account.

### 3. Products & Variants (`/api/products`)
- `GET /api/products`: Lists products with variants and tax rates (`active_only` filter supported).
- `GET /api/products/<id>`: Gets single product with variants.
- `POST /api/products`: Creates product (Admin/Staff only; validates non-negative prices, unique codes).
- `PUT /api/products/<id>`: Updates product without altering historical snapshots.
- `PUT /api/products/<id>/toggle-active`: Deactivates/activates product.
- `POST /api/products/<id>/variants`: Adds variant with SKU and additional price modifier (e.g. Odoo brand +$560.00).
- `PUT /api/products/variants/<var_id>`: Updates variant details.

### 4. Subscription Plans (`/api/plans`)
- `GET /api/plans`: Lists subscription plans (`available_only` checks active status and date window).
- `GET /api/plans/<id>`: Retrieves plan with policy rules.
- `POST /api/plans`: Creates plan with billing frequency (`daily`, `weekly`, `monthly`, `yearly`), minimum quantity (>= 1), date window, and lifecycle policies (`allow_pause`, `allow_renewal`, `allow_early_close`, `auto_close_on_expiry`).
- `PUT /api/plans/<id>`: Updates plan rules.
- `PUT /api/plans/<id>/toggle-active`: Toggles plan active status.

### 5. Quotations (`/api/quotations`)
- `GET /api/quotations`: Lists quotations (Customers view only their own; staff/admin view all).
- `GET /api/quotations/templates`: Lists reusable quotation templates.
- `GET /api/quotations/<id>`: Retrieves quotation details with snapshot line items.
- `POST /api/quotations`: Creates quotation with live line-item pricing, tax rate calculation, subtotal, and grand total.
- `PUT /api/quotations/<id>`: Updates draft quotation (Editing confirmed, rejected, or expired quotes is blocked).
- `POST /api/quotations/<id>/send`: Transitions status to `sent`.
- `POST /api/quotations/<id>/confirm`: Confirms/accepts quotation.
- `POST /api/quotations/<id>/reject`: Rejects quotation.
- `POST /api/quotations/<id>/save-as-template`: Saves quotation as reusable template.

### 6. Subscriptions (`/api/subscriptions`)
- `GET /api/subscriptions`: Lists subscriptions (Filtered by role).
- `GET /api/subscriptions/<id>`: Retrieves subscription with snapshot line items and full audit trail.
- `POST /api/subscriptions/convert-quotation/<quotation_id>`: Converts confirmed quotation to active recurring subscription (Blocks duplicate conversions; snapshots agreed prices).
- `POST /api/subscriptions`: Creates direct subscription.
- `POST /api/subscriptions/<id>/pause`: Pauses subscription (Enforces `allow_pause` plan policy).
- `POST /api/subscriptions/<id>/resume`: Resumes paused subscription.
- `POST /api/subscriptions/<id>/renew`: Renews subscription and advances next billing schedule (Enforces `allow_renewal` plan policy).
- `POST /api/subscriptions/<id>/close`: Terminates subscription and records closing timestamp.

---

## Running the Application

### 1. Start the Flask Backend Server
```bash
cd backend
python app.py
```
The backend initializes the local SQLite database and runs at `http://127.0.0.1:5000`.

### 2. Open the Frontend
Open `frontend/index.html` in any web browser, or serve it using Python's static HTTP server:
```bash
python -m http.server 8000 --directory frontend
```
Navigate to `http://localhost:8000` to interact with the system.

### 3. Run the Automated Test Suite
```bash
python -m unittest backend/tests/test_modules.py
```
All 8 automated tests verify RBAC, password security, product calculations, plan constraints, quotation lifecycle, quotation-to-subscription conversion, pause/resume policy checks, and audit logging.
