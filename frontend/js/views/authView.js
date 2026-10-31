/**
 * Authentication View Components
 * ==============================
 * Handles Login, Registration, Forgot Password, and Reset Password views.
 */

const AuthView = {
    renderLogin: () => {
        return `
            <div class="auth-card">
                <h2>Welcome Back</h2>
                <p class="auth-subtitle">Log in to manage your subscriptions and quotes</p>
                <div id="auth-alert" class="alert d-none"></div>
                <form id="login-form" onsubmit="AuthView.handleLogin(event)">
                    <div class="form-group">
                        <label for="login-email">Email Address</label>
                        <input type="email" id="login-email" class="form-control" required placeholder="name@company.com" autocomplete="username">
                    </div>
                    <div class="form-group">
                        <label for="login-password">Password</label>
                        <input type="password" id="login-password" class="form-control" required placeholder="••••••••" autocomplete="current-password">
                    </div>
                    <div class="auth-options">
                        <a href="#/forgot-password" class="text-sm">Forgot Password?</a>
                    </div>
                    <button type="submit" id="login-btn" class="btn btn-primary btn-block">Log In</button>
                </form>
                <div class="auth-footer">
                    <span>Don't have an account?</span>
                    <a href="#/register">Create Customer Account</a>
                </div>
                <div class="demo-credentials-box">
                    <strong>Demo Accounts:</strong>
                    <div>Admin: <code>admin@brightloop.com</code> / <code>Admin@123!</code></div>
                    <div>Staff: <code>staff@brightloop.com</code> / <code>Staff@123!</code></div>
                    <div>Customer: <code>customer@brightloop.com</code> / <code>Customer@123!</code></div>
                </div>
            </div>
        `;
    },

    handleLogin: async (event) => {
        event.preventDefault();
        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;
        const btn = document.getElementById('login-btn');
        const alertBox = document.getElementById('auth-alert');

        btn.disabled = true;
        btn.textContent = 'Authenticating...';
        alertBox.className = 'alert d-none';

        const result = await AuthManager.login(email, password);
        btn.disabled = false;
        btn.textContent = 'Log In';

        if (result.success) {
            window.showToast('Login successful! Welcome back.', 'success');
            window.Router.navigate('/dashboard');
        } else {
            alertBox.className = 'alert alert-danger';
            alertBox.textContent = result.error || 'Authentication failed. Please check credentials.';
        }
    },

    renderRegister: () => {
        return `
            <div class="auth-card">
                <h2>Create Account</h2>
                <p class="auth-subtitle">Register for customer access to quotes & subscriptions</p>
                <div id="auth-alert" class="alert d-none"></div>
                <form id="register-form" onsubmit="AuthView.handleRegister(event)">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="reg-first-name">First Name *</label>
                            <input type="text" id="reg-first-name" class="form-control" required placeholder="John">
                        </div>
                        <div class="form-group">
                            <label for="reg-last-name">Last Name *</label>
                            <input type="text" id="reg-last-name" class="form-control" required placeholder="Doe">
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="reg-email">Email Address *</label>
                        <input type="email" id="reg-email" class="form-control" required placeholder="john.doe@example.com">
                    </div>
                    <div class="form-group">
                        <label for="reg-phone">Phone Number (Optional)</label>
                        <input type="tel" id="reg-phone" class="form-control" placeholder="+1 555-0100">
                    </div>
                    <div class="form-group">
                        <label for="reg-password">Password *</label>
                        <input type="password" id="reg-password" class="form-control" required placeholder="At least 9 characters">
                        <small class="form-hint">Must be >8 characters with uppercase, lowercase, and special characters.</small>
                    </div>
                    <div class="form-group">
                        <label for="reg-confirm-password">Confirm Password *</label>
                        <input type="password" id="reg-confirm-password" class="form-control" required placeholder="Repeat password">
                    </div>
                    <button type="submit" id="register-btn" class="btn btn-primary btn-block">Register Account</button>
                </form>
                <div class="auth-footer">
                    <span>Already have an account?</span>
                    <a href="#/login">Log In</a>
                </div>
            </div>
        `;
    },

    handleRegister: async (event) => {
        event.preventDefault();
        const firstName = document.getElementById('reg-first-name').value.trim();
        const lastName = document.getElementById('reg-last-name').value.trim();
        const email = document.getElementById('reg-email').value.trim();
        const phone = document.getElementById('reg-phone').value.trim();
        const password = document.getElementById('reg-password').value;
        const confirmPassword = document.getElementById('reg-confirm-password').value;
        const btn = document.getElementById('register-btn');
        const alertBox = document.getElementById('auth-alert');

        if (password !== confirmPassword) {
            alertBox.className = 'alert alert-danger';
            alertBox.textContent = 'Passwords do not match.';
            return;
        }

        btn.disabled = true;
        btn.textContent = 'Registering...';
        alertBox.className = 'alert d-none';

        const res = await AuthManager.register({
            first_name: firstName,
            last_name: lastName,
            email,
            phone,
            password,
            confirm_password: confirmPassword
        });

        btn.disabled = false;
        btn.textContent = 'Register Account';

        if (res.success) {
            window.showToast('Registration successful! Please log in.', 'success');
            window.Router.navigate('/login');
        } else {
            alertBox.className = 'alert alert-danger';
            alertBox.textContent = res.error || 'Registration failed.';
        }
    },

    renderForgotPassword: () => {
        return `
            <div class="auth-card">
                <h2>Reset Password</h2>
                <p class="auth-subtitle">Enter your registered email to receive a password reset token</p>
                <div id="auth-alert" class="alert d-none"></div>
                <form id="forgot-form" onsubmit="AuthView.handleForgotPassword(event)">
                    <div class="form-group">
                        <label for="forgot-email">Email Address</label>
                        <input type="email" id="forgot-email" class="form-control" required placeholder="name@company.com">
                    </div>
                    <button type="submit" id="forgot-btn" class="btn btn-primary btn-block">Request Reset Token</button>
                </form>
                <div id="dev-token-display" class="mt-3 d-none"></div>
                <div class="auth-footer">
                    <span>Remember your password?</span>
                    <a href="#/login">Back to Login</a>
                </div>
            </div>
        `;
    },

    handleForgotPassword: async (event) => {
        event.preventDefault();
        const email = document.getElementById('forgot-email').value.trim();
        const btn = document.getElementById('forgot-btn');
        const alertBox = document.getElementById('auth-alert');
        const tokenDisplay = document.getElementById('dev-token-display');

        btn.disabled = true;
        btn.textContent = 'Requesting...';

        const res = await ApiClient.post('/auth/forgot-password', { email });
        btn.disabled = false;
        btn.textContent = 'Request Reset Token';

        alertBox.className = 'alert alert-info';
        alertBox.textContent = res.message || 'If your email is registered, you will receive password reset instructions.';

        if (res.data && res.data.dev_reset_token) {
            tokenDisplay.className = 'alert alert-warning mt-3';
            tokenDisplay.innerHTML = `
                <strong>[Dev Testing Mode] Reset Token:</strong><br>
                <code>${res.data.dev_reset_token}</code><br>
                <a href="#/reset-password?token=${encodeURIComponent(res.data.dev_reset_token)}" class="btn btn-sm btn-primary mt-2">Proceed to Reset Password</a>
            `;
        }
    },

    renderResetPassword: (tokenFromUrl = '') => {
        return `
            <div class="auth-card">
                <h2>Set New Password</h2>
                <p class="auth-subtitle">Enter the reset token and your new password</p>
                <div id="auth-alert" class="alert d-none"></div>
                <form id="reset-form" onsubmit="AuthView.handleResetPassword(event)">
                    <div class="form-group">
                        <label for="reset-token">Reset Token</label>
                        <input type="text" id="reset-token" class="form-control" required value="${tokenFromUrl}" placeholder="Paste token here">
                    </div>
                    <div class="form-group">
                        <label for="reset-new-password">New Password</label>
                        <input type="password" id="reset-new-password" class="form-control" required placeholder="At least 9 characters">
                        <small class="form-hint">Must be >8 characters with uppercase, lowercase, and special characters.</small>
                    </div>
                    <div class="form-group">
                        <label for="reset-confirm-password">Confirm New Password</label>
                        <input type="password" id="reset-confirm-password" class="form-control" required placeholder="Repeat password">
                    </div>
                    <button type="submit" id="reset-btn" class="btn btn-primary btn-block">Update Password</button>
                </form>
                <div class="auth-footer">
                    <a href="#/login">Back to Login</a>
                </div>
            </div>
        `;
    },

    handleResetPassword: async (event) => {
        event.preventDefault();
        const token = document.getElementById('reset-token').value.trim();
        const newPassword = document.getElementById('reset-new-password').value;
        const confirmPassword = document.getElementById('reset-confirm-password').value;
        const btn = document.getElementById('reset-btn');
        const alertBox = document.getElementById('auth-alert');

        if (newPassword !== confirmPassword) {
            alertBox.className = 'alert alert-danger';
            alertBox.textContent = 'Passwords do not match.';
            return;
        }

        btn.disabled = true;
        btn.textContent = 'Updating...';

        const res = await ApiClient.post('/auth/reset-password', {
            token,
            new_password: newPassword,
            confirm_password: confirmPassword
        });

        btn.disabled = false;
        btn.textContent = 'Update Password';

        if (res.success) {
            window.showToast('Password reset successfully! Please log in.', 'success');
            window.Router.navigate('/login');
        } else {
            alertBox.className = 'alert alert-danger';
            alertBox.textContent = res.error || 'Failed to reset password.';
        }
    }
};

window.AuthView = AuthView;

