/**
 * Unified API Client for Subscription Management System
 * =====================================================
 * Handles HTTP requests, JWT header attachment, response parsing,
 * error handling, and redirection on unauthenticated requests.
 */

// Dynamically detect API host: prefer port 5001 (macOS AirPlay avoids 5000) or current host
let API_BASE_URL = window.API_BASE_URL ||
    (window.location.port === '5001' || window.location.port === '5000'
        ? `${window.location.origin}/api`
        : 'http://127.0.0.1:5001/api');

class ApiClient {
    /**
     * Retrieves the stored JWT access token.
     */
    static getToken() {
        return localStorage.getItem('access_token');
    }

    /**
     * Stores authentication tokens.
     */
    static setTokens(accessToken, refreshToken) {
        localStorage.setItem('access_token', accessToken);
        if (refreshToken) {
            localStorage.setItem('refresh_token', refreshToken);
        }
    }

    /**
     * Clears authentication tokens and user session.
     */
    static clearAuth() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_profile');
    }

    /**
     * Core fetch wrapper with JSON serialization and authorization headers.
     */
    static async request(endpoint, options = {}) {
        const url = `${API_BASE_URL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        const token = this.getToken();
        if (token && !headers['Authorization']) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const config = {
            ...options,
            headers
        };

        try {
            let response;
            try {
                response = await fetch(url, config);
            } catch (firstErr) {
                // Try candidate fallback endpoints (5001, 5000, localhost)
                const candidateBases = [
                    'http://127.0.0.1:5001/api',
                    'http://localhost:5001/api',
                    'http://127.0.0.1:5000/api',
                    'http://localhost:5000/api'
                ];
                let connected = false;
                for (const altBase of candidateBases) {
                    if (altBase === API_BASE_URL) continue;
                    try {
                        response = await fetch(`${altBase}${endpoint}`, config);
                        API_BASE_URL = altBase;
                        connected = true;
                        break;
                    } catch (e) {}
                }
                if (!connected) throw firstErr;
            }

            const data = await response.json().catch(() => ({}));

            if (response.status === 401) {
                // If unauthorized and trying to access protected route, clear session and redirect to login
                if (!endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
                    this.clearAuth();
                    if (window.Router) {
                        window.Router.navigate('/login');
                    }
                }
                return {
                    success: false,
                    error: data.error || 'Session expired or unauthorized. Please log in again.',
                    status: response.status
                };
            }

            if (!response.ok) {
                return {
                    success: false,
                    error: data.error || `Request failed with HTTP status ${response.status}`,
                    details: data.details || null,
                    status: response.status
                };
            }

            return {
                success: true,
                data: data.data !== undefined ? data.data : data,
                message: data.message || '',
                status: response.status
            };

        } catch (err) {
            console.error('API Network Error:', err);
            return {
                success: false,
                error: 'Cannot connect to backend server. Ensure Flask is running on http://127.0.0.1:5000',
                status: 0
            };
        }
    }

    // Convenience HTTP methods
    static get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    }

    static post(endpoint, body = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }

    static put(endpoint, body = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    }

    static delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
}

// Attach to window for global access across vanilla JS modules
window.ApiClient = ApiClient;
