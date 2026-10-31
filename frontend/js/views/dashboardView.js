/**
 * Dashboard View Component
 * ========================
 * Overview screen displaying metrics for active subscriptions, products, quotes, and quick actions.
 */

const DashboardView = {
    render: async () => {
        const user = AuthManager.getUser();
        if (!user) return '';

        // Fetch counts concurrently
        const [subsRes, quotesRes, prodsRes] = await Promise.all([
            ApiClient.get('/subscriptions'),
            ApiClient.get('/quotations'),
            ApiClient.get('/products')
        ]);

        const subs = subsRes.success ? subsRes.data : [];
        const quotes = quotesRes.success ? quotesRes.data : [];
        const prods = prodsRes.success ? prodsRes.data : [];

        const activeSubsCount = subs.filter(s => s.status === 'active').length;
        const pausedSubsCount = subs.filter(s => s.status === 'paused').length;
        const draftQuotesCount = quotes.filter(q => q.status === 'draft' || q.status === 'sent').length;
        const confirmedQuotesCount = quotes.filter(q => q.status === 'confirmed').length;

        return `
            <div class="dashboard-header">
                <div>
                    <h2>Welcome back, ${user.first_name || 'User'}!</h2>
                    <p class="text-muted">Subscription Management System — Modules 1, 2 & 3 Dashboard</p>
                </div>
                <div class="quick-actions">
                    <a href="#/quotations" class="btn btn-primary" onclick="setTimeout(() => QuotationView.openCreateModal(), 100)">+ New Quotation</a>
                    <a href="#/products" class="btn btn-secondary">Catalog</a>
                </div>
            </div>

            <!-- Stats Metric Grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon icon-blue">🔄</div>
                    <div class="stat-details">
                        <span class="stat-value">${activeSubsCount}</span>
                        <span class="stat-label">Active Subscriptions</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon icon-orange">⏸️</div>
                    <div class="stat-details">
                        <span class="stat-value">${pausedSubsCount}</span>
                        <span class="stat-label">Paused Subscriptions</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon icon-green">📝</div>
                    <div class="stat-details">
                        <span class="stat-value">${draftQuotesCount}</span>
                        <span class="stat-label">Pending / Draft Quotations</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon icon-purple">📦</div>
                    <div class="stat-details">
                        <span class="stat-value">${prods.length}</span>
                        <span class="stat-label">Available Products</span>
                    </div>
                </div>
            </div>

            <!-- Recent Subscriptions and Quotations Tables -->
            <div class="dashboard-sections-grid">
                <div class="card">
                    <div class="card-header">
                        <h3>Recent Subscriptions</h3>
                        <a href="#/subscriptions" class="text-sm">View All &rarr;</a>
                    </div>
                    <div class="card-body">
                        ${subs.length === 0 ? '<p class="empty-state">No subscriptions found.</p>' : `
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Number</th>
                                        <th>Customer</th>
                                        <th>Status</th>
                                        <th>Next Billing</th>
                                        <th>Amount</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${subs.slice(0, 5).map(s => `
                                        <tr>
                                            <td><strong>${s.subscription_number}</strong></td>
                                            <td>${s.customer_name || 'Customer'}</td>
                                            <td><span class="status-pill status-${s.status}">${s.status.toUpperCase()}</span></td>
                                            <td>${s.next_billing_date || 'N/A'}</td>
                                            <td>$${s.total_amount.toFixed(2)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `}
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <h3>Recent Quotations</h3>
                        <a href="#/quotations" class="text-sm">View All &rarr;</a>
                    </div>
                    <div class="card-body">
                        ${quotes.length === 0 ? '<p class="empty-state">No quotations found.</p>' : `
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Number</th>
                                        <th>Customer</th>
                                        <th>Status</th>
                                        <th>Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${quotes.slice(0, 5).map(q => `
                                        <tr>
                                            <td><strong>${q.quotation_number}</strong></td>
                                            <td>${q.customer_name || 'Customer'}</td>
                                            <td><span class="status-pill status-${q.status}">${q.status.toUpperCase()}</span></td>
                                            <td>$${q.total_amount.toFixed(2)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `}
                    </div>
                </div>
            </div>
        `;
    }
};

window.DashboardView = DashboardView;

