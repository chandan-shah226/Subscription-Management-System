/**
 * Main Application Script (Frontend Entry Point)
 * ==============================================
 * Bootstraps the Vanilla JavaScript Single Page Application.
 * Initializes authentication, client-side routing, and global toast notifications.
 */

/**
 * Toast Notification System
 * @param {string} message - Message text
 * @param {'success'|'error'|'warning'|'info'} type - Toast theme
 * @param {number} duration - Milliseconds before auto-dismiss
 */
window.showToast = (message, type = 'info', duration = 3500) => {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 400);
    }, duration);
};

/**
 * Verifies backend connectivity and updates status badge.
 */
async function checkBackendConnectivity() {
    const statusEl = document.getElementById('api-status');
    if (!statusEl) return;

    try {
        const res = await ApiClient.get('/health');
        if (res && (res.status === 200 || res.success || res.status === 'healthy' || res.data?.status === 'healthy')) {
            statusEl.textContent = 'Backend Online (v1.0.0)';
            statusEl.className = 'status-indicator online';
        } else {
            statusEl.textContent = 'Backend Offline';
            statusEl.className = 'status-indicator offline';
        }
    } catch (e) {
        statusEl.textContent = 'Backend Offline';
        statusEl.className = 'status-indicator offline';
    }
}

/**
 * Application Initialization
 */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Subscription Management System frontend starting up...');

    // 1. Initialize auth state
    AuthManager.init();

    // 2. Check backend connectivity
    await checkBackendConnectivity();

    // 3. If token present, fetch fresh user profile
    if (ApiClient.getToken()) {
        await AuthManager.fetchCurrentUser();
    } else {
        AuthManager.updateNavbar();
    }

    // 4. Initialize client-side router
    Router.init();
});
