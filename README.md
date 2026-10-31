# Subscription Management System

A centralized ERP-style platform for managing products, subscription plans, customer subscriptions, recurring billing, invoices, payments, and financial reporting.

## About the Project

The Subscription Management System is being developed for **Brightloop Software** as part of a hackathon challenge.

The objective is to automate the complete subscription business lifecycle through a single platform, reducing manual work and improving billing accuracy, payment tracking, and financial visibility.

The system will support businesses that offer monthly, yearly, weekly, or daily subscription-based products and services.

## Key Features

### 1. User Management

- User registration and login.
- Role-based access control.
- Admin, Staff, and Customer roles.
- Password reset functionality.

### 2. Product & Plan Management

- Create and manage products.
- Configure product types, selling prices, and cost prices.
- Manage product variants.
- Create subscription plans.
- Configure daily, weekly, monthly, and yearly billing cycles.
- Manage plan availability, renewal, pause, and closure.

### 3. Quotation & Subscription Management

- Create and manage quotations.
- Reusable quotation templates.
- Convert quotations into subscriptions.
- Track subscription lifecycle and status.
- Manage subscription products, quantities, prices, and payment terms.

### 4. Invoice & Billing Management

- Automatic recurring invoice generation.
- Automatic tax calculations.
- Invoice confirmation and cancellation.
- Invoice printing and sending.
- Prevention of duplicate billing.

### 5. Discount Management

- Fixed and percentage-based discounts.
- Minimum purchase and quantity conditions.
- Discount validity dates.
- Usage limits.
- Automatic discount application.

### 6. Payment Management

- Record customer payments.
- Track payment methods, amounts, and dates.
- Link payments to invoices.
- Track paid, partially paid, and outstanding invoices.

### 7. Finance & Reporting Dashboard

- Active subscription overview.
- Revenue tracking.
- Outstanding payment tracking.
- Overdue invoice monitoring.
- Financial summaries and filters.

## Technology Stack

### Backend

- **Programming Language:** Python
- **Framework:** Flask
- **Database:** SQL Database (PostgreSQL preferred)
- **ORM:** SQLAlchemy
- **Communication:** REST APIs

### Frontend

- Frontend framework and libraries: To be finalized by the frontend development team.
- API integration through REST APIs.

## Application Workflow

```text
Customer Registration
        |
        v
Product & Plan Selection
        |
        v
Quotation Creation
        |
        v
Subscription Confirmation
        |
        v
Subscription Activation
        |
        v
Automatic Invoice Generation
        |
        v
Payment Recording
        |
        v
Financial Dashboard & Reports
```

## Project Structure

The project directory structure will be finalized as development progresses.

```text
subscription-management-system/
│
├── backend/
│   └── (Flask application)
│
├── frontend/
│   └── (Frontend application)
│
├── README.md
└── .gitignore
```

## Project Status

**Current Stage:** Initial Development

Planned development priorities:

- [ ] Database architecture and configuration
- [ ] Authentication and role management
- [ ] Product and plan management
- [ ] Quotation and subscription management
- [ ] Recurring billing and invoice generation
- [ ] Discount management
- [ ] Payment tracking
- [ ] Finance dashboard and reporting
- [ ] Frontend and backend integration
- [ ] Testing and performance optimization

## Development Goal

Build a reliable, scalable, and user-friendly subscription management platform that automates business operations and provides accurate financial information.

---

**Built as part of the Subscription Management System Hackathon Challenge.**
