/**
 * Client-Side View Router
 * =======================
 * Hash-based Single Page Application router with authentication guards.
 */

class Router {
    static routes = {
        '/login': { render: () => AuthView.renderLogin(), public: true },
        '/register': { render: () => AuthView.renderRegister(), public: true },
        '/forgot-password': { render: () => AuthView.renderForgotPassword(), public: true },
        '/reset-password': { render: (param) => AuthView.renderResetPassword(param), public: true },
        '/dashboard': { render: () => DashboardView.render(), public: false },
        '/users': { render: () => UserView.render(), public: false, staffOnly: true },
        '/products': { render: () => ProductPlanView.render(), public: false },
        '/plans': { render: () => {
            const res = ProductPlanView.render();
            setTimeout(() => ProductPlanView.switchTab('plans'), 50);
            return res;
        }, public: false },
        '/quotations': { render: () => QuotationView.render(), public: false },
        '/subscriptions': { render: () => SubscriptionView.render(), public: false }
    };

    static init() {
        window.addEventListener('hashchange', () => this.handleRouting());
        window.addEventListener('load', () => this.handleRouting());
        this.handleRouting();
    }

    static navigate(path) {
        window.location.hash = path;
    }

    static async handleRouting() {
        const hash = window.location.hash.slice(1) || '';
        let [routePath, queryString] = hash.split('?');
        if (!routePath || routePath === '/') {
            routePath = AuthManager.isAuthenticated() ? '/dashboard' : '/login';
        }

        const route = this.routes[routePath];
        const container = document.getElementById('view-container');
        if (!container) return;

        // Authentication guards
        if (!route || !route.public) {
            if (!AuthManager.isAuthenticated()) {
                window.location.hash = '/login';
                return;
            }
        }

        // Staff / Admin guard
        if (route && route.staffOnly && !AuthManager.isStaff()) {
            window.showToast('Access forbidden: Administrative role required.', 'error');
            window.location.hash = '/dashboard';
            return;
        }

        // Redirect logged in user from auth pages to dashboard
        if (route && route.public && AuthManager.isAuthenticated() && (routePath === '/login' || routePath === '/register')) {
            window.location.hash = '/dashboard';
            return;
        }

        // Parse query params if any
        let param = null;
        if (queryString) {
            const urlParams = new URLSearchParams(queryString);
            param = urlParams.get('token') || queryString;
        }

        // Render view
        container.innerHTML = '<div class="loading-spinner-box"><div class="spinner"></div><p>Loading view...</p></div>';

        try {
            const content = await (route ? route.render(param) : '<div class="alert alert-danger">Page not found (404)</div>');
            container.innerHTML = content;
            AuthManager.updateNavbar();
        } catch (error) {
            console.error('Routing error:', error);
            container.innerHTML = `<div class="alert alert-danger">Failed to render view: ${error.message}</div>`;
        }
    }
}

window.Router = Router;

