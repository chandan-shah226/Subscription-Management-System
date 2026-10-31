/**
 * Dashboard View Component
 * ========================
 * Executive overview screen for Admin/Staff and Self-Service Hub for Customers.
 */

const DashboardView = {
    render: async () => {
        const user = AuthManager.getUser();
        if (!user) return '';

        const isCustomer = AuthManager.isCustomer();

        // Fetch metrics concurrently
        const [subsRes, quotesRes, invRes, payRes] = await Promise.all([
            ApiClient.get('/subscriptions'),
            ApiClient.get('/quotations'),
            ApiClient.get('/invoices'),
            ApiClient.get('/payments')
        ]);

        const subs = subsRes.success ? subsRes.data : [];
        const quotes = quotesRes.success ? quotesRes.data : [];
        const invoices = invRes.success ? invRes.data : [];
        const payments = payRes.success ? payRes.data : [];

        const activeSubsCount = subs.filter(s => s.status === 'active').length;
        const totalRevenue = payments.reduce((sum, p) => sum + p.amount, 0);
        const unpaidInvoices = invoices.filter(i => i.status !== 'paid' && i.status !== 'cancelled');
        const outstandingDue = unpaidInvoices.reduce((sum, i) => sum + (i.outstanding_balance || i.total_amount), 0);
        const overdueCount = unpaidInvoices.filter(i => i.is_overdue).length;

        return `
            <div class="dashboard-header">
                <div>
                    <h2>Welcome, ${user.first_name || 'User'}!</h2>
                    <p class="text-muted">
                        ${isCustomer 
                            ? 'Brightloop Customer Self-Service Portal — Manage your subscriptions and invoices in one place' 
                            : 'Brightloop Operations & Billing Executive Hub'}
                    </p>
                </div>
                <div class="quick-actions">
                    ${isCustomer ? `
                        <a href="#/products" class="btn btn-primary">Browse Catalog & Plans</a>
                        <a href="#/invoices" class="btn btn-secondary">My Invoices</a>
                    ` : `
                        <a href="#/quotations" class="btn btn-primary" onclick="setTimeout(() => QuotationView.openCreateModal(), 100)">+ New Quotation</a>
                        <a href="#/invoices" class="btn btn-secondary">Invoicing & Billing</a>
                        <a href="#/finance" class="btn btn-outline">Executive Finance Hub</a>
                    `}
                </div>
            </div>

            <!-- Overdue Warning Banner if customer has unpaid invoices -->
            ${isCustomer && overdueCount > 0 ? `
                <div class="alert alert-danger" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
                    <div><strong>⚠️ Payment Due:</strong> You have ${overdueCount} invoice(s) awaiting payment totaling <strong>$${outstandingDue.toFixed(2)}</strong>.</div>
                    <a href="#/invoices" class="btn btn-sm btn-danger">Pay Now Online</a>
                </div>
            ` : ''}

            <!-- Stats Metric Grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon icon-blue">🔄</div>
                    <div class="stat-details">
                        <span class="stat-value">${activeSubsCount}</span>
                        <span class="stat-label">${isCustomer ? 'My Active Subscriptions' : 'Active Subscriptions'}</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon icon-green">💵</div>
                    <div class="stat-details">
                        <span class="stat-value">$${totalRevenue.toFixed(2)}</span>
                        <span class="stat-label">${isCustomer ? 'Total Paid to Date' : 'Total Revenue Collected'}</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon icon-orange">⏳</div>
                    <div class="stat-details">
                        <span class="stat-value">$${outstandingDue.toFixed(2)}</span>
                        <span class="stat-label">${isCustomer ? 'Current Balance Due' : 'Outstanding Receivables'}</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon ${overdueCount > 0 ? 'icon-red' : 'icon-purple'}">
                        ${overdueCount > 0 ? '🚨' : '📝'}
                    </div>
                    <div class="stat-details">
                        <span class="stat-value ${overdueCount > 0 ? 'text-danger' : ''}">${overdueCount > 0 ? overdueCount : quotes.length}</span>
                        <span class="stat-label">${overdueCount > 0 ? 'Overdue Invoices' : isCustomer ? 'My Quotations' : 'Quotations Drafted'}</span>
                    </div>
                </div>
            </div>

            <!-- Recent Subscriptions and Invoices Tables -->
            <div class="dashboard-sections-grid">
                <!-- Recent Subscriptions -->
                <div class="card">
                    <div class="card-header">
                        <h3>${isCustomer ? 'My Subscriptions' : 'Recent Subscriptions'}</h3>
                        <a href="#/subscriptions" class="text-sm">View All &rarr;</a>
                    </div>
                    <div class="card-body">
                        ${subs.length === 0 ? '<p class="empty-state">No subscriptions found.</p>' : `
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Number</th>
                                        ${!isCustomer ? '<th>Customer</th>' : ''}
                                        <th>Status</th>
                                        <th>Next Billing</th>
                                        <th>Amount</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${subs.slice(0, 5).map(s => `
                                        <tr>
                                            <td><strong>${s.subscription_number}</strong></td>
                                            ${!isCustomer ? `<td>${s.customer_name || 'Customer'}</td>` : ''}
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

                <!-- Recent Invoices -->
                <div class="card">
                    <div class="card-header">
                        <h3>${isCustomer ? 'My Recent Invoices' : 'Recent Invoices'}</h3>
                        <a href="#/invoices" class="text-sm">View All &rarr;</a>
                    </div>
                    <div class="card-body">
                        ${invoices.length === 0 ? '<p class="empty-state">No invoices found.</p>' : `
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Invoice #</th>
                                        ${!isCustomer ? '<th>Customer</th>' : ''}
                                        <th>Due Date</th>
                                        <th>Total</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${invoices.slice(0, 5).map(inv => `
                                        <tr>
                                            <td><strong>${inv.invoice_number}</strong></td>
                                            ${!isCustomer ? `<td>${inv.customer_name || 'Customer'}</td>` : ''}
                                            <td>${inv.due_date}</td>
                                            <td><strong>$${inv.total_amount.toFixed(2)}</strong></td>
                                            <td><span class="status-pill ${inv.status === 'paid' ? 'status-active' : inv.is_overdue ? 'status-closed' : 'status-paused'}">${(inv.status || 'draft').toUpperCase()}</span></td>
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
