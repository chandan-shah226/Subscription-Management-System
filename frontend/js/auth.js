/**
 * Authentication and Session State Manager
 * ========================================
 * Manages user credentials, role detection, session persistence, and logout.
 */

class AuthManager {
    static currentUser = null;

    /**
     * Initializes authentication state from localStorage.
     */
    static init() {
        const cachedUser = localStorage.getItem('user_profile');
        if (cachedUser) {
            try {
                this.currentUser = JSON.parse(cachedUser);
            } catch (e) {
                this.currentUser = null;
            }
        }
    }

    static isAuthenticated() {
        return !!ApiClient.getToken() && !!this.currentUser;
    }

    static getUser() {
        return this.currentUser;
    }

    static getRole() {
        return this.currentUser ? this.currentUser.role : 'guest';
    }

    static isAdmin() {
        return this.getRole() === 'admin';
    }

    static isStaff() {
        return this.getRole() === 'staff' || this.isAdmin();
    }

    static isCustomer() {
        return this.getRole() === 'customer';
    }

    /**
     * Authenticates user via backend and persists session.
     */
    static async login(email, password) {
        const response = await ApiClient.post('/auth/login', { email, password });
        if (response.success && response.data) {
            ApiClient.setTokens(response.data.access_token, response.data.refresh_token);
            this.currentUser = response.data.user;
            localStorage.setItem('user_profile', JSON.stringify(this.currentUser));
            this.updateNavbar();
            return { success: true, user: this.currentUser };
        }
        return { success: false, error: response.error };
    }

    /**
     * Customer registration.
     */
    static async register(formData) {
        return await ApiClient.post('/auth/register', formData);
    }

    /**
     * Refreshes the current user profile from /auth/me.
     */
    static async fetchCurrentUser() {
        if (!ApiClient.getToken()) return null;
        const res = await ApiClient.get('/auth/me');
        if (res.success && res.data) {
            this.currentUser = res.data;
            localStorage.setItem('user_profile', JSON.stringify(this.currentUser));
            this.updateNavbar();
            return this.currentUser;
        } else {
            this.logout();
            return null;
        }
    }

    /**
     * Terminates the current session and redirects to login.
     */
    static logout() {
        ApiClient.clearAuth();
        this.currentUser = null;
        this.updateNavbar();
        if (window.Router) {
            window.Router.navigate('/login');
        }
    }

    /**
     * Dynamically updates the top navigation bar according to the active role.
     */
    static updateNavbar(overrideRoute = null) {
        const navContainer = document.getElementById('app-navigation');
        const userMenu = document.getElementById('user-menu');
        if (!navContainer || !userMenu) return;

        if (!this.isAuthenticated()) {
            navContainer.innerHTML = `
                <a href="#/login" class="nav-link" data-route="/login">Login</a>
                <a href="#/register" class="nav-link" data-route="/register">Register</a>
            `;
            userMenu.innerHTML = `
                <span class="badge guest-badge">Guest</span>
            `;
            return;
        }

        const user = this.currentUser;
        let navLinks = `
            <a href="#/dashboard" class="nav-link" data-route="/dashboard">Dashboard</a>
            <a href="#/products" class="nav-link" data-route="/products">Products & Plans</a>
            <a href="#/quotations" class="nav-link" data-route="/quotations">Quotations</a>
            <a href="#/subscriptions" class="nav-link" data-route="/subscriptions">Subscriptions</a>
            <a href="#/invoices" class="nav-link" data-route="/invoices">Invoices</a>
        `;

        if (this.isAdmin()) {
            navLinks += `<a href="#/discounts" class="nav-link" data-route="/discounts">Discounts</a>`;
        }

        navLinks += `<a href="#/payments" class="nav-link" data-route="/payments">Payments</a>`;

        if (this.isAdmin() || this.isStaff()) {
            navLinks += `<a href="#/finance" class="nav-link" data-route="/finance">Finance Hub</a>`;
            navLinks += `<a href="#/users" class="nav-link" data-route="/users">Users</a>`;
        }
            navLinks += `<a href="#/users" class="nav-link" data-route="/users">Users</a>`;
        }

        navContainer.innerHTML = navLinks;

        const roleColor = user.role === 'admin' ? 'role-admin' : user.role === 'staff' ? 'role-staff' : 'role-customer';
        userMenu.innerHTML = `
            <div class="user-profile-badge">
                <span class="user-name">${user.full_name || user.email}</span>
                <span class="badge ${roleColor}">${user.role.toUpperCase()}</span>
            </div>
            <button id="logout-btn" class="btn btn-secondary btn-sm" onclick="AuthManager.logout()">Logout</button>
        `;

        // Highlight active link accurately
        const currentHash = window.location.hash.slice(1) || '/dashboard';
        const rawRoute = overrideRoute || currentHash;
        const currentRoute = rawRoute.split('?')[0];

        navContainer.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
        const activeLink = navContainer.querySelector(`[data-route="${currentRoute}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
    }
}

// Attach to window
window.AuthManager = AuthManager;
