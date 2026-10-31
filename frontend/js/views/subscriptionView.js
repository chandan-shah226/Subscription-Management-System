/**
 * Subscription Management View Component (Module 3)
 * ==================================================
 * Handles recurring subscription monitoring, status badges, lifecycle transitions
 * (Pause, Resume, Renew, Close), policy checks, and audit log history.
 */

const SubscriptionView = {
    subscriptions: [],
    products: [],
    plans: [],
    customers: [],

    render: async () => {
        const [subRes, pRes, planRes] = await Promise.all([
            ApiClient.get('/subscriptions'),
            ApiClient.get('/products', { active_only: true }),
            ApiClient.get('/plans', { available_only: true })
        ]);

        SubscriptionView.subscriptions = subRes.success ? subRes.data : [];
        SubscriptionView.products = pRes.success ? pRes.data : [];
        SubscriptionView.plans = planRes.success ? planRes.data : [];

        if (AuthManager.isStaff()) {
            const uRes = await ApiClient.get('/users', { role: 'customer' });
            SubscriptionView.customers = uRes.success ? uRes.data : [];
        }

        return `
            <div class="view-header">
                <div>
                    <h2>Recurring Subscriptions</h2>
                    <p class="text-muted">Monitor active services, manage lifecycle actions (Pause/Resume/Renew/Close), and view audit history</p>
                </div>
                ${AuthManager.isStaff() ? `
                    <button class="btn btn-primary" onclick="SubscriptionView.openDirectCreateModal()">+ Direct Subscription</button>
                ` : ''}
            </div>

            <!-- Filters -->
            <div class="toolbar">
                <input type="text" id="sub-search" class="form-control toolbar-search" placeholder="Search subscription number or customer..." oninput="SubscriptionView.filterSubs()">
                <select id="sub-status-filter" class="form-control toolbar-select" onchange="SubscriptionView.filterSubs()">
                    <option value="">All Statuses</option>
                    <option value="active">Active</option>
                    <option value="paused">Paused</option>
                    <option value="closed">Closed</option>
                    <option value="expired">Expired</option>
                </select>
            </div>

            <!-- Subscriptions Table -->
            <div class="card">
                <div class="card-body">
                    <div id="subs-table-container">
                        ${SubscriptionView.renderTable(SubscriptionView.subscriptions)}
                    </div>
                </div>
            </div>

            <!-- Modal Container -->
            <div id="subscription-modal-container"></div>
        `;
    },

    renderTable: (subList) => {
        if (subList.length === 0) {
            return `<p class="empty-state">No subscriptions found matching your criteria.</p>`;
        }

        return `
            <table class="table">
                <thead>
                    <tr>
                        <th>Subscription #</th>
                        <th>Customer</th>
                        <th>Plan</th>
                        <th>Frequency</th>
                        <th>Status</th>
                        <th>Next Billing</th>
                        <th>Recurring Total</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${subList.map(s => `
                        <tr>
                            <td><strong>${s.subscription_number}</strong></td>
                            <td>${s.customer_name || 'Customer'}</td>
                            <td><span class="badge badge-info">${s.plan_name || 'Plan'}</span></td>
                            <td>${s.billing_frequency.toUpperCase()}</td>
                            <td><span class="status-pill status-${s.status}">${s.status.toUpperCase()}</span></td>
                            <td>${s.next_billing_date || 'N/A'}</td>
                            <td><strong>$${s.total_amount.toFixed(2)}</strong></td>
                            <td>
                                <button class="btn btn-sm btn-secondary" onclick="SubscriptionView.openDetailsModal(${s.id})">Manage &rarr;</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    filterSubs: () => {
        const search = (document.getElementById('sub-search').value || '').toLowerCase();
        const status = document.getElementById('sub-status-filter').value;

        const filtered = SubscriptionView.subscriptions.filter(s => {
            const matchesSearch = s.subscription_number.toLowerCase().includes(search) ||
                                  (s.customer_name && s.customer_name.toLowerCase().includes(search));
            const matchesStatus = !status || s.status === status;
            return matchesSearch && matchesStatus;
        });

        document.getElementById('subs-table-container').innerHTML = SubscriptionView.renderTable(filtered);
    },

    // --- SUBSCRIPTION DETAILS, LIFECYCLE & AUDIT LOGS ---

    openDetailsModal: async (subscriptionId) => {
        const res = await ApiClient.get(`/subscriptions/${subscriptionId}`);
        if (!res.success) {
            window.showToast(res.error || 'Failed to load subscription details.', 'error');
            return;
        }

        const s = res.data;
        const container = document.getElementById('subscription-modal-container');

        container.innerHTML = `
            <div class="modal-backdrop" onclick="SubscriptionView.closeModal(event)">
                <div class="modal-dialog modal-xl" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <div>
                            <h3>Subscription: ${s.subscription_number}</h3>
                            <span class="status-pill status-${s.status}">${s.status.toUpperCase()}</span>
                        </div>
                        <button class="modal-close" onclick="SubscriptionView.closeModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <!-- Key Metadata Grid -->
                        <div class="details-grid mb-3">
                            <div><strong>Customer:</strong> ${s.customer_name} (${s.customer_email})</div>
                            <div><strong>Plan:</strong> ${s.plan_name}</div>
                            <div><strong>Billing Frequency:</strong> ${s.billing_frequency.toUpperCase()}</div>
                            <div><strong>Next Billing Date:</strong> ${s.next_billing_date}</div>
                            <div><strong>Start Date:</strong> ${s.start_date}</div>
                            <div><strong>End Date:</strong> ${s.end_date || 'Continuous / No Expiry'}</div>
                            <div><strong>Pause Policy:</strong> ${s.allow_pause ? 'Allowed' : 'Disabled by Plan'}</div>
                            <div><strong>Renewal Policy:</strong> ${s.allow_renewal ? 'Allowed' : 'Disabled by Plan'}</div>
                        </div>

                        <!-- Agreed Line Items Snapshot -->
                        <h4>Agreed Snapshot Products & Pricing</h4>
                        <table class="table mb-4">
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Variant</th>
                                    <th>Quantity</th>
                                    <th>Agreed Unit Price</th>
                                    <th>Tax</th>
                                    <th>Line Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${s.items.map(it => `
                                    <tr>
                                        <td><strong>${it.product_name}</strong></td>
                                        <td>${it.variant_name ? `${it.variant_name} (${it.sku})` : '—'}</td>
                                        <td>${it.quantity}</td>
                                        <td>$${it.unit_price.toFixed(2)}</td>
                                        <td>$${it.tax_amount.toFixed(2)} (${it.tax_rate}%)</td>
                                        <td><strong>$${it.total_price.toFixed(2)}</strong></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>

                        <!-- Totals Banner -->
                        <div class="quote-totals-box mb-4">
                            <div class="totals-row">
                                <span>Subtotal:</span>
                                <strong>$${s.subtotal.toFixed(2)}</strong>
                            </div>
                            <div class="totals-row">
                                <span>Tax:</span>
                                <strong>$${s.tax_amount.toFixed(2)}</strong>
                            </div>
                            <div class="totals-row total-highlight">
                                <span>Recurring Billing Total:</span>
                                <strong>$${s.total_amount.toFixed(2)}</strong>
                            </div>
                        </div>

                        <!-- Lifecycle Action Controls Bar -->
                        <div class="lifecycle-controls-panel mb-4">
                            <h4>Subscription Lifecycle Controls</h4>
                            <div class="d-flex gap-2 flex-wrap mt-2">
                                ${s.status === 'active' ? `
                                    <button class="btn btn-outline" onclick="SubscriptionView.generateInvoiceForSub(${s.id})">
                                        ⚡ Generate Invoice
                                    </button>
                                    <button class="btn btn-warning" onclick="SubscriptionView.pauseSub(${s.id})" ${!s.allow_pause ? 'disabled title="Plan policy forbids pause"' : ''}>
                                        ⏸️ Pause Subscription
                                    </button>
                                ` : ''}

                                ${s.status === 'paused' ? `
                                    <button class="btn btn-success" onclick="SubscriptionView.resumeSub(${s.id})">
                                        ▶️ Resume Subscription
                                    </button>
                                ` : ''}

                                ${(s.status === 'active' || s.status === 'expired') ? `
                                    <button class="btn btn-primary" onclick="SubscriptionView.renewSub(${s.id})" ${!s.allow_renewal ? 'disabled title="Plan policy forbids renewal"' : ''}>
                                        🔄 Renew & Advance Schedule
                                    </button>
                                ` : ''}

                                ${s.status !== 'closed' ? `
                                    <button class="btn btn-danger" onclick="SubscriptionView.closeSub(${s.id})">
                                        🛑 Close / Terminate
                                    </button>
                                ` : '<span class="badge badge-secondary">Subscription is Closed</span>'}
                            </div>
                        </div>

                        <!-- Audit Log Timeline -->
                        <h4>Audit Trail & Lifecycle History</h4>
                        <div class="audit-timeline mt-2">
                            ${s.audit_logs && s.audit_logs.length > 0 ? s.audit_logs.map(log => `
                                <div class="timeline-item">
                                    <div class="timeline-dot dot-${log.action}"></div>
                                    <div class="timeline-content">
                                        <div class="d-flex justify-between">
                                            <strong>${log.action.toUpperCase()}</strong>
                                            <span class="text-xs text-muted">${log.timestamp ? log.timestamp.replace('T', ' ').slice(0, 19) : ''}</span>
                                        </div>
                                        <p class="text-sm mt-1">${log.details || 'Lifecycle mutation recorded.'}</p>
                                        <span class="text-xs text-muted">Performed by: ${log.performed_by_name || 'System User'}</span>
                                    </div>
                                </div>
                            `).join('') : '<p class="text-muted text-sm">No audit entries yet.</p>'}
                        </div>
                    </div>

                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="SubscriptionView.closeModal()">Close</button>
                    </div>
                </div>
            </div>
        `;
    },

    generateInvoiceForSub: async (subId) => {
        const res = await ApiClient.post(`/invoices/generate/${subId}`, {});
        if (res.success) {
            window.showToast(`Invoice ${res.data.invoice_number} created successfully!`, 'success');
            SubscriptionView.closeModal();
            window.Router.navigate('/invoices');
        } else {
            window.showToast(res.error || 'Failed to generate invoice', 'error');
        }
    },

    pauseSub: async (subId) => {
        if (!confirm('Pause this subscription? Recurring invoices and automated actions will be held until resumed.')) return;
        const res = await ApiClient.post(`/subscriptions/${subId}/pause`);
        if (res.success) {
            window.showToast('Subscription paused successfully.', 'warning');
            SubscriptionView.openDetailsModal(subId);
            SubscriptionView.refresh();
        } else {
            window.showToast(res.error || 'Failed to pause subscription.', 'error');
        }
    },

    resumeSub: async (subId) => {
        const res = await ApiClient.post(`/subscriptions/${subId}/resume`);
        if (res.success) {
            window.showToast('Subscription resumed and now active!', 'success');
            SubscriptionView.openDetailsModal(subId);
            SubscriptionView.refresh();
        } else {
            window.showToast(res.error || 'Failed to resume subscription.', 'error');
        }
    },

    renewSub: async (subId) => {
        if (!confirm('Renew this subscription? Next billing date will advance according to the frequency schedule.')) return;
        const res = await ApiClient.post(`/subscriptions/${subId}/renew`);
        if (res.success) {
            window.showToast('Subscription renewed successfully!', 'success');
            SubscriptionView.openDetailsModal(subId);
            SubscriptionView.refresh();
        } else {
            window.showToast(res.error || 'Failed to renew subscription.', 'error');
        }
    },

    closeSub: async (subId) => {
        if (!confirm('WARNING: Are you sure you want to permanently close/terminate this subscription? This cannot be undone.')) return;
        const res = await ApiClient.post(`/subscriptions/${subId}/close`);
        if (res.success) {
            window.showToast('Subscription closed and terminated.', 'info');
            SubscriptionView.openDetailsModal(subId);
            SubscriptionView.refresh();
        } else {
            window.showToast(res.error || 'Failed to close subscription.', 'error');
        }
    },

    // --- DIRECT SUBSCRIPTION CREATION MODAL ---

    openDirectCreateModal: () => {
        const container = document.getElementById('subscription-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="SubscriptionView.closeModal(event)">
                <div class="modal-dialog modal-lg" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Create Direct Subscription</h3>
                        <button class="modal-close" onclick="SubscriptionView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="SubscriptionView.submitDirectSubscription(event)">
                        <div class="modal-body">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Customer *</label>
                                    <select id="dir-sub-customer" class="form-control" required>
                                        <option value="">Select Customer...</option>
                                        ${SubscriptionView.customers.map(c => `
                                            <option value="${c.id}">${c.full_name} (${c.email})</option>
                                        `).join('')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Subscription Plan *</label>
                                    <select id="dir-sub-plan" class="form-control" required>
                                        <option value="">Select Plan...</option>
                                        ${SubscriptionView.plans.map(p => `
                                            <option value="${p.id}">${p.name} ($${p.base_price} / ${p.billing_frequency})</option>
                                        `).join('')}
                                    </select>
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Initial Product Item *</label>
                                    <select id="dir-sub-product" class="form-control" required>
                                        ${SubscriptionView.products.map(p => `
                                            <option value="${p.id}">${p.name} ($${p.sales_price})</option>
                                        `).join('')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Quantity *</label>
                                    <input type="number" min="1" id="dir-sub-qty" class="form-control" value="1" required>
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Notes</label>
                                <textarea id="dir-sub-notes" class="form-control" rows="2" placeholder="Optional subscription notes..."></textarea>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="SubscriptionView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Create & Activate</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    submitDirectSubscription: async (event) => {
        event.preventDefault();
        const customerId = parseInt(document.getElementById('dir-sub-customer').value, 10);
        const planId = parseInt(document.getElementById('dir-sub-plan').value, 10);
        const productId = parseInt(document.getElementById('dir-sub-product').value, 10);
        const qty = parseInt(document.getElementById('dir-sub-qty').value, 10);
        const notes = document.getElementById('dir-sub-notes').value.trim();

        const payload = {
            customer_id: customerId,
            plan_id: planId,
            notes,
            items: [{ product_id: productId, quantity: qty }]
        };

        const res = await ApiClient.post('/subscriptions', payload);
        if (res.success) {
            window.showToast('Direct subscription created and activated successfully!', 'success');
            SubscriptionView.closeModal();
            SubscriptionView.refresh();
        } else {
            window.showToast(res.error || 'Failed to create subscription.', 'error');
        }
    },

    closeModal: () => {
        const container = document.getElementById('subscription-modal-container');
        if (container) container.innerHTML = '';
    },

    refresh: async () => {
        const res = await ApiClient.get('/subscriptions');
        SubscriptionView.subscriptions = res.success ? res.data : [];
        const tableContainer = document.getElementById('subs-table-container');
        if (tableContainer) tableContainer.innerHTML = SubscriptionView.renderTable(SubscriptionView.subscriptions);
    }
};

window.SubscriptionView = SubscriptionView;

