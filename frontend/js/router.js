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
        '/subscriptions': { render: () => SubscriptionView.render(), public: false },
        '/invoices': { render: () => InvoiceView.render(), public: false },
        '/discounts': { render: () => DiscountView.render(), public: false, adminOnly: true },
        '/payments': { render: () => PaymentView.render(), public: false },
        '/finance': { render: () => typeof FinanceView !== 'undefined' ? FinanceView.render() : '<div class="card p-4">Finance Module</div>', public: false, staffOnly: true }
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

        // Admin only guard
        if (route && route.adminOnly && !AuthManager.isAdmin()) {
            window.showToast('Access forbidden: Administrator privileges required.', 'error');
            window.location.hash = '/dashboard';
            return;
        }

        // Staff / Admin guard
        if (route && route.staffOnly && !AuthManager.isStaff()) {
            if (window.showToast) window.showToast('Access forbidden: Administrative role required.', 'error');
            else alert('Access forbidden: Administrative role required.');
            window.location.hash = '/dashboard';
            return;
        }

        // Admin Only guard
        if (route && route.adminOnly && !AuthManager.isAdmin()) {
            if (window.showToast) window.showToast('Access forbidden: Administrator role required.', 'error');
            else alert('Access forbidden: Administrator role required.');
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
            AuthManager.updateNavbar(routePath);
            const content = await (route ? route.render(param) : '<div class="alert alert-danger">Page not found (404)</div>');
            container.innerHTML = content;
        } catch (error) {
            console.error('Routing error:', error);
            container.innerHTML = `
                <div class="card p-4 my-4" style="max-width: 600px; margin: 2rem auto; text-align: center; border: 1px solid #fee2e2; background: #fff; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); padding: 2.5rem 1.5rem;">
                    <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⚠️</div>
                    <h3 style="color: #991b1b; margin-bottom: 0.5rem;">Failed to render view</h3>
                    <p style="color: #64748b; margin-bottom: 1.5rem;">${error.message || 'An unexpected error occurred while loading this view.'}</p>
                    <div>
                        <button class="btn btn-primary" onclick="Router.handleRouting()">🔄 Retry Loading</button>
                    </div>
                </div>
            `;
        } finally {
            AuthManager.updateNavbar(routePath);
        }
    }
}

window.Router = Router;
