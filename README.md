# Subscription Management System

A centralized ERP-style platform for managing products, subscription plans, customer subscriptions, recurring billing, invoices, payments, and financial reporting.

---

## About the Project

The Subscription Management System is being developed for **Brightloop Software** as part of a hackathon challenge.

The objective is to automate the complete subscription business lifecycle through a single platform, reducing manual work and improving billing accuracy, payment tracking, and financial visibility.

The system supports businesses offering recurring subscription models (daily, weekly, monthly, and yearly).

---

## Technology Stack

- **Backend:** Python 3.x, Flask
- **Database & ORM:** SQLite, SQLAlchemy (`Flask-SQLAlchemy`)
- **Authentication:** JWT (`Flask-JWT-Extended`)
- **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3
- **API Architecture:** RESTful JSON APIs with CORS support

---

## Project Structure

```text
Subscription-Management-System/
│
├── frontend/
│   ├── index.html          # Main HTML entry point
│   ├── css/
│   │   └── style.css       # Core styling & design system
│   └── js/
│       └── main.js         # Frontend application logic & API client
│
├── backend/
│   ├── app.py              # Application factory & server entry point
│   ├── config.py           # Configuration settings (Dev, Test, Prod)
│   ├── models/
│   │   └── __init__.py     # SQLAlchemy models & schema definitions
│   ├── routes/
│   │   └── __init__.py     # API routes and Flask blueprints
│   ├── services/
│   │   └── __init__.py     # Business logic, workflows & calculations
│   ├── middleware/
│   │   └── __init__.py     # Authentication guards & custom middleware
│   └── requirements.txt    # Python package dependencies
│
├── instance/
│   └── .gitkeep            # Local instance folder (SQLite database storage)
│
├── .gitignore              # Git ignore rules for Python, virtual environments, IDEs, DBs
└── README.md               # Project documentation & guidelines
```

---

## Directory & File Descriptions

### Backend (`/backend`)
- **`app.py`**: Initializes the Flask application using the application factory pattern (`create_app()`), registers extensions (SQLAlchemy, JWT, CORS), and exposes a `/api/health` connectivity check.
- **`config.py`**: Houses configuration classes for development, testing, and production environments, including SQLite database path and JWT expiration settings.
- **`models/`**: Houses SQLAlchemy database models (e.g., users, products, plans, quotations, invoices, payments). Models can be written in separate files and imported into `__init__.py`.
- **`routes/`**: Contains Flask Blueprints for each domain module. Developers can create route files (e.g., `auth_routes.py`, `product_routes.py`) and register them in `app.py`.
- **`services/`**: Encapsulates core business logic, billing calculations, and workflow engines away from route controllers to keep code modular and testable.
- **`middleware/`**: Contains custom decorators, role-based authorization guards, error handlers, and request hooks.
- **`requirements.txt`**: Pinned dependencies including Flask, Flask-SQLAlchemy, Flask-JWT-Extended, Flask-Cors, and python-dotenv.

### Database Storage (`/instance`)
- Contains runtime data such as local SQLite database files (`*.db`), which are excluded from Git via `.gitignore`. The `.gitkeep` file ensures the folder exists across checkouts.

### Frontend (`/frontend`)
- **`index.html`**: Clean semantic HTML5 layout with placeholders for future feature views and a backend status indicator.
- **`css/style.css`**: Pure CSS with responsive layout rules and CSS variables for consistent colors and spacing.
- **`js/main.js`**: Vanilla JavaScript handling DOM readiness, health check verification with the backend API, and placeholders for feature modules.

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ installed
- Modern web browser

### 2. Backend Setup
1. Open a terminal and navigate to the project directory:
   ```bash
   cd Subscription-Management-System/backend
   ```
2. Create and activate a virtual environment:
   - **Windows:**
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - **macOS / Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the development server:
   ```bash
   python app.py
   ```
   The API will be available at `http://127.0.0.1:5000/api/health`.

### 3. Frontend Setup
Open `frontend/index.html` in your browser, or serve it using a simple HTTP server:
```bash
# From the project root or frontend directory:
python -m http.server 8000 --directory frontend
```
Navigate to `http://localhost:8000` to view the frontend interface and verify backend connectivity.

---

## Guidelines for Independent Development

To allow multiple developers to work concurrently without merge conflicts:
1. **Models**: Add entity models in separate files inside `backend/models/` (e.g., `user.py`, `invoice.py`) and import them into `models/__init__.py`.
2. **Routes & APIs**: Create dedicated Flask Blueprints in `backend/routes/` for each feature domain and register them in `backend/app.py`.
3. **Business Logic**: Place complex calculations (such as billing cycles and tax computations) in `backend/services/`.
4. **Security & Permissions**: Put authorization checks and custom decorators in `backend/middleware/`.
5. **Database**: Do not commit SQLite database files (`*.db`). Database migrations and schema creation will be managed via SQLAlchemy models.
