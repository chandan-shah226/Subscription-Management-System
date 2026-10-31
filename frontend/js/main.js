/**
 * Subscription Management System - Main Application Script
 * ========================================================
 * Pure Vanilla JavaScript entry point.
 * Provides a clean architecture for developers to mount module scripts
 * and interact with the backend REST API.
 */

// Configuration constants
const API_BASE_URL = 'http://127.0.0.1:5000/api';

/**
 * Checks connectivity with the Flask backend health endpoint.
 */
async function checkBackendHealth() {
    const statusElement = document.getElementById('api-status');
    if (!statusElement) return;

    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            const data = await response.json();
            statusElement.textContent = `Online (${data.message || 'Ready'})`;
            statusElement.className = 'status-indicator online';
        } else {
            statusElement.textContent = `Offline (HTTP ${response.status})`;
            statusElement.className = 'status-indicator offline';
        }
    } catch (error) {
        statusElement.textContent = 'Offline (Cannot connect to backend)';
        statusElement.className = 'status-indicator offline';
    }
}

/**
 * Main application initialization
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Subscription Management System frontend initialized.');
    
    // Check backend connection on initial load
    checkBackendHealth();

    // -------------------------------------------------------------------------
    // Placeholder for Feature Modules:
    // Independent developers can import or attach modules here:
    // - Auth module (login / registration / token storage)
    // - Products & Plans module
    // - Quotations & Subscriptions module
    // - Invoices & Payments module
    // -------------------------------------------------------------------------
});

