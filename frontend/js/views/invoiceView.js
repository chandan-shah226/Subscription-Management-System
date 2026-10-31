/**
 * Invoice & Recurring Billing View Component (Module 4)
 * ====================================================
 * Modern, responsive billing module for Brightloop Software:
 * - Summary KPI cards (Total Invoiced, Outstanding, Paid, Overdue)
 * - Filtering (Search by #/Customer, Status tabs, Date range)
 * - Invoice Table with status badges and responsive container
 * - Create Manual Invoice with dynamic line item calculator
 * - View Invoice Details with line item breakdown
 * - Record Payments against outstanding balances
 * - Recurring billing batch generation for due subscriptions
 * - Printable PDF view
 */

const InvoiceView = {
    invoices: [],
    customers: [],
    products: [],
    subscriptions: [],
    stats: {},
    currentInvoice: null,

    render: async () => {
        let invRes, statsRes, prodRes, subRes;
        try {
            [invRes, statsRes, prodRes, subRes] = await Promise.all([
                ApiClient.get('/invoices'),
                ApiClient.get('/invoices/stats'),
                ApiClient.get('/products', { active_only: true }),
                ApiClient.get('/subscriptions')
            ]);
        } catch (e) {
            console.error("Failed to fetch invoice initial data:", e);
            invRes = { success: false, error: e.message };
            statsRes = { success: false };
            prodRes = { success: false };
            subRes = { success: false };
        }

        if (!invRes || !invRes.success) {
            return `
                <div class="view-header">
                    <div>
                        <h2>Invoices & Recurring Billing</h2>
                        <p class="text-muted">Manage invoices, record payments, track receivables, and trigger recurring subscription billing</p>
                    </div>
                </div>
                <div class="card p-4 my-4" style="text-align: center; border: 1px solid #fee2e2; background: #fff; border-radius: 8px; padding: 3rem 1.5rem; margin-top: 1.5rem;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
                    <h3 style="color: #991b1b; margin-bottom: 0.5rem;">Unable to load invoices</h3>
                    <p class="text-muted" style="margin-bottom: 1.5rem;">${invRes?.error || 'A network or server error occurred while retrieving invoice records.'}</p>
                    <button class="btn btn-primary" onclick="Router.handleRouting()">🔄 Retry Loading</button>
                </div>
            `;
        }

        const rawInvoices = invRes.invoices !== undefined ? invRes.invoices : (invRes.data !== undefined ? invRes.data : []);
        InvoiceView.invoices = Array.isArray(rawInvoices) ? rawInvoices : (rawInvoices && Array.isArray(rawInvoices.invoices) ? rawInvoices.invoices : []);
        InvoiceView.stats = (statsRes && statsRes.success && statsRes.stats) ? statsRes.stats : ((statsRes && statsRes.data) || {});
        InvoiceView.products = (prodRes && prodRes.success) ? (prodRes.products || (Array.isArray(prodRes.data) ? prodRes.data : [])) : [];
        InvoiceView.subscriptions = (subRes && subRes.success) ? (subRes.subscriptions || (Array.isArray(subRes.data) ? subRes.data : [])) : [];

        if (AuthManager.isStaff()) {
            try {
                const uRes = await ApiClient.get('/users', { role: 'customer' });
                InvoiceView.customers = uRes.success ? (uRes.users || (Array.isArray(uRes.data) ? uRes.data : [])) : [];
            } catch (ue) {
                console.error("Failed to load customer list:", ue);
                InvoiceView.customers = [];
            }
        }

        const isStaff = AuthManager.isStaff();
        const stats = InvoiceView.stats;

        return `
            <div class="view-header">
                <div>
                    <h2>Invoices & Recurring Billing</h2>
                    <p class="text-muted">Manage invoices, record payments, track receivables, and trigger recurring subscription billing</p>
                </div>
                <div class="view-actions">
                    ${isStaff ? `
                        <button class="btn btn-secondary btn-sm" onclick="InvoiceView.openRecurringModal()">⚡ Run Billing Cycle</button>
                        <button class="btn btn-primary btn-sm" onclick="InvoiceView.openCreateModal()">+ Create Invoice</button>
                    ` : ''}
                </div>
            </div>

            <!-- KPI Metric Cards -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <span class="kpi-title">Total Invoiced</span>
                    <span class="kpi-value">₹${(stats.total_amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                    <span class="kpi-subtext text-muted">${stats.total_count || 0} Total Invoices</span>
                </div>
                <div class="kpi-card kpi-outstanding">
                    <span class="kpi-title">Outstanding Balance</span>
                    <span class="kpi-value text-danger">₹${(stats.total_outstanding || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                    <span class="kpi-subtext text-warning">${stats.confirmed_count || 0} Awaiting Payment</span>
                </div>
                <div class="kpi-card kpi-paid">
                    <span class="kpi-title">Total Collected</span>
                    <span class="kpi-value text-success">₹${(stats.total_collected || stats.paid_amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                    <span class="kpi-subtext text-success">${stats.paid_count || 0} Settled Invoices</span>
                </div>
                <div class="kpi-card kpi-overdue">
                    <span class="kpi-title">Overdue Invoices</span>
                    <span class="kpi-value text-danger">₹${(stats.overdue_amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                    <span class="kpi-subtext text-danger">${stats.overdue_count || 0} Past Due Date</span>
                </div>
            </div>

            <!-- Toolbar & Filters -->
            <div class="toolbar card-body" style="background:#fff; border-radius:8px; margin-bottom:1.5rem; border:1px solid #e2e8f0; padding:1rem 1.25rem;">
                <div class="toolbar-row" style="display:flex; flex-wrap:wrap; gap:0.75rem; align-items:center; width:100%;">
                    <div style="flex: 2; min-width: 240px;">
                        <input type="text" id="inv-search" class="form-control" placeholder="Search by invoice # or customer name..." oninput="InvoiceView.handleFilterChange()">
                    </div>
                    <div style="flex: 1; min-width: 150px;">
                        <select id="inv-status-filter" class="form-control" onchange="InvoiceView.handleFilterChange()">
                            <option value="">All Statuses</option>
                            <option value="Draft">Draft</option>
                            <option value="Confirmed">Confirmed</option>
                            <option value="Paid">Paid</option>
                            <option value="overdue">Overdue</option>
                            <option value="Cancelled">Cancelled</option>
                        </select>
                    </div>
                    <div style="display:flex; gap:0.5rem; align-items:center;">
                        <input type="date" id="inv-start-date" class="form-control" style="width:140px;" title="From date" onchange="InvoiceView.handleFilterChange()">
                        <span class="text-muted">to</span>
                        <input type="date" id="inv-end-date" class="form-control" style="width:140px;" title="To date" onchange="InvoiceView.handleFilterChange()">
                    </div>
                    <div>
                        <button class="btn btn-secondary btn-sm" onclick="InvoiceView.resetFilters()">Reset</button>
                    </div>
                </div>
            </div>

            <!-- Invoices Data Table -->
            <div class="card">
                <div class="card-body" style="padding:0;">
                    <div class="table-responsive" id="invoices-table-container">
                        ${InvoiceView.renderTable(InvoiceView.invoices)}
                    </div>
                </div>
            </div>

            <!-- Modal Container -->
            <div id="invoice-modal-container"></div>
        `;
    },

    renderTable: (invoicesList) => {
        const list = Array.isArray(invoicesList) ? invoicesList : [];
        if (list.length === 0) {
            return `
                <div class="empty-state" style="padding:3rem 1rem; text-align:center;">
                    <div style="font-size:3rem; margin-bottom:0.5rem;">📄</div>
                    <h4 style="margin:0 0 0.5rem 0; color:#475569;">No invoices found</h4>
                    <p class="text-muted" style="margin:0;">There are no invoices matching the selected filters.</p>
                </div>
            `;
        }

        const isStaff = AuthManager.isStaff();

        return `
            <table class="table" style="width:100%; margin-bottom:0;">
                <thead>
                    <tr>
                        <th>Invoice #</th>
                        <th>Customer</th>
                        <th>Subscription</th>
                        <th>Date</th>
                        <th>Due Date</th>
                        <th class="text-right">Total (₹)</th>
                        <th class="text-right">Outstanding (₹)</th>
                        <th class="text-center">Status</th>
                        <th class="text-right">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${list.map(inv => {
                        const statusClass = inv.status.toLowerCase();
                        const isOverdue = inv.is_overdue;
                        const displayStatus = isOverdue ? 'Overdue' : inv.status;
                        const badgeStyle = isOverdue ? 'background:#fee2e2; color:#b91c1c;' :
                            inv.status === 'Paid' ? 'background:#dcfce7; color:#15803d;' :
                            inv.status === 'Confirmed' ? 'background:#e0f2fe; color:#0369a1;' :
                            inv.status === 'Draft' ? 'background:#f1f5f9; color:#475569;' :
                            'background:#fee2e2; color:#991b1b;';

                        return `
                            <tr>
                                <td>
                                    <strong style="color:#714B67; cursor:pointer;" onclick="InvoiceView.openDetailModal(${inv.id})">${inv.invoice_number}</strong>
                                </td>
                                <td>
                                    <div><strong>${inv.customer_name || 'N/A'}</strong></div>
                                    <small class="text-muted">${inv.customer_email || ''}</small>
                                </td>
                                <td>
                                    ${inv.subscription_number ? `<span class="badge" style="background:#f1f5f9; color:#475569;">${inv.subscription_number}</span>` : '<span class="text-muted">—</span>'}
                                </td>
                                <td>${inv.invoice_date || '—'}</td>
                                <td>
                                    <span class="${isOverdue ? 'text-danger' : ''}" style="${isOverdue ? 'font-weight:600;' : ''}">${inv.due_date || '—'}</span>
                                </td>
                                <td class="text-right" style="font-weight:600;">₹${(inv.total_amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
                                <td class="text-right" style="font-weight:600; color:${inv.outstanding_amount > 0 ? '#b91c1c' : '#15803d'};">
                                    ₹${(inv.outstanding_amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}
                                </td>
                                <td class="text-center">
                                    <span class="badge" style="padding:4px 8px; border-radius:9999px; font-weight:600; font-size:11px; ${badgeStyle}">
                                        ${displayStatus.toUpperCase()}
                                    </span>
                                </td>
                                <td class="text-right">
                                    <div class="action-buttons" style="display:flex; gap:0.25rem; justify-content:flex-end;">
                                        <button class="btn btn-secondary btn-sm" onclick="InvoiceView.openDetailModal(${inv.id})" title="View Details">View</button>
                                        <a href="/api/invoices/${inv.id}/print" target="_blank" class="btn btn-secondary btn-sm" title="Printable Layout">Print</a>
                                        ${isStaff && inv.status === 'Draft' ? `
                                            <button class="btn btn-primary btn-sm" onclick="InvoiceView.confirmInvoice(${inv.id})">Confirm</button>
                                        ` : ''}
                                        ${inv.status === 'Confirmed' && inv.outstanding_amount > 0 ? `
                                            <button class="btn btn-primary btn-sm" onclick="InvoiceView.payWithRazorpay(${inv.id})" title="Pay with Razorpay">💳 Pay Online</button>
                                            ${isStaff ? `<button class="btn btn-success btn-sm" onclick="InvoiceView.openPaymentModal(${inv.id})">Manual Pay</button>` : ''}
                                        ` : ''}
                                    </div>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    },

    handleFilterChange: async () => {
        const search = document.getElementById('inv-search')?.value || '';
        const status = document.getElementById('inv-status-filter')?.value || '';
        const startDate = document.getElementById('inv-start-date')?.value || '';
        const endDate = document.getElementById('inv-end-date')?.value || '';

        const params = {};
        if (search) params.search = search;
        if (status) params.status = status;
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;

        const res = await ApiClient.get('/invoices', params);
        if (res.success) {
            const rawInvoices = res.invoices !== undefined ? res.invoices : (res.data !== undefined ? res.data : []);
            InvoiceView.invoices = Array.isArray(rawInvoices) ? rawInvoices : (rawInvoices && Array.isArray(rawInvoices.invoices) ? rawInvoices.invoices : []);
            const container = document.getElementById('invoices-table-container');
            if (container) {
                container.innerHTML = InvoiceView.renderTable(InvoiceView.invoices);
            }
        }
    },

    resetFilters: async () => {
        if (document.getElementById('inv-search')) document.getElementById('inv-search').value = '';
        if (document.getElementById('inv-status-filter')) document.getElementById('inv-status-filter').value = '';
        if (document.getElementById('inv-start-date')) document.getElementById('inv-start-date').value = '';
        if (document.getElementById('inv-end-date')) document.getElementById('inv-end-date').value = '';
        await InvoiceView.handleFilterChange();
    },

    openDetailModal: async (invoiceId) => {
        const res = await ApiClient.get(`/invoices/${invoiceId}`);
        if (!res.success) {
            alert(res.error || 'Unable to load invoice details');
            return;
        }

        const inv = res.invoice || res.data;
        InvoiceView.currentInvoice = inv;
        const isStaff = AuthManager.isStaff();

        const modalHtml = `
            <div class="modal-backdrop" onclick="InvoiceView.closeModal(event)">
                <div class="modal" style="max-width:850px; width:90%; max-height:90vh; overflow-y:auto;" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <div>
                            <h3 style="margin:0; color:#714B67;">Invoice ${inv.invoice_number}</h3>
                            <span class="text-muted" style="font-size:13px;">Created on ${inv.created_at ? inv.created_at.split('T')[0] : 'N/A'}</span>
                        </div>
                        <button class="btn btn-secondary btn-sm" onclick="InvoiceView.closeModal()">✕</button>
                    </div>

                    <div class="modal-body">
                        <!-- Invoice Overview Grid -->
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; margin-bottom:1.5rem; background:#f8fafc; padding:1.25rem; border-radius:8px;">
                            <div>
                                <h4 style="margin:0 0 0.5rem 0; font-size:12px; color:#64748b; text-transform:uppercase;">Customer</h4>
                                <div style="font-size:16px; font-weight:600;">${inv.customer_name}</div>
                                <div class="text-muted">${inv.customer_email}</div>
                                ${inv.customer_phone ? `<div class="text-muted">${inv.customer_phone}</div>` : ''}
                            </div>
                            <div style="text-align:right;">
                                <h4 style="margin:0 0 0.5rem 0; font-size:12px; color:#64748b; text-transform:uppercase;">Billing Info</h4>
                                <div>Status: <strong>${inv.status}</strong></div>
                                <div>Invoice Date: <strong>${inv.invoice_date}</strong></div>
                                <div>Due Date: <strong class="${inv.is_overdue ? 'text-danger' : ''}">${inv.due_date}</strong></div>
                                ${inv.subscription_number ? `<div>Subscription: <span class="badge" style="background:#e0f2fe; color:#0369a1;">${inv.subscription_number}</span></div>` : ''}
                            </div>
                        </div>

                        <!-- Line Items -->
                        <h4 style="margin:0 0 0.75rem 0;">Billed Items</h4>
                        <table class="table" style="margin-bottom:1.5rem;">
                            <thead>
                                <tr>
                                    <th>Description</th>
                                    <th class="text-right">Qty</th>
                                    <th class="text-right">Unit Price (₹)</th>
                                    <th class="text-right">Tax (18%)</th>
                                    <th class="text-right">Total (₹)</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${(inv.items || []).map(item => `
                                    <tr>
                                        <td>
                                            <strong>${item.description}</strong>
                                            ${item.variant_name ? `<div style="font-size:12px; color:#64748b;">Variant: ${item.variant_name}</div>` : ''}
                                        </td>
                                        <td class="text-right">${item.quantity}</td>
                                        <td class="text-right">₹${item.unit_price.toFixed(2)}</td>
                                        <td class="text-right">₹${item.tax_amount.toFixed(2)}</td>
                                        <td class="text-right" style="font-weight:600;">₹${item.total_amount.toFixed(2)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>

                        <!-- Financial Summary Box -->
                        <div style="width:300px; margin-left:auto; margin-bottom:1.5rem; background:#f8fafc; padding:1rem; border-radius:8px;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                                <span>Subtotal:</span>
                                <span>₹${inv.subtotal.toFixed(2)}</span>
                            </div>
                            ${inv.discount_amount > 0 ? `
                                <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem; color:#15803d;">
                                    <span>Discount ${inv.discount_code ? `<span class="badge" style="background:#fef3c7; color:#92400e;">${inv.discount_code}</span>` : ''}:</span>
                                    <span>-₹${inv.discount_amount.toFixed(2)}</span>
                                </div>
                            ` : ''}
                            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                                <span>Taxes:</span>
                                <span>₹${inv.tax_amount.toFixed(2)}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:0.75rem; font-weight:700; font-size:16px; border-top:1px solid #cbd5e1; padding-top:0.5rem; color:#714B67;">
                                <span>Total Amount:</span>
                                <span>₹${inv.total_amount.toFixed(2)}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem; color:#15803d;">
                                <span>Amount Paid:</span>
                                <span>₹${inv.amount_paid.toFixed(2)}</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; font-weight:700; color:${inv.outstanding_amount > 0 ? '#b91c1c' : '#15803d'};">
                                <span>Outstanding:</span>
                                <span>₹${inv.outstanding_amount.toFixed(2)}</span>
                            </div>
                        </div>

                        <!-- Payment History -->
                        <h4 style="margin:0 0 0.75rem 0;">Payment History</h4>
                        ${(inv.payments && inv.payments.length > 0) ? `
                            <table class="table" style="margin-bottom:1.5rem;">
                                <thead>
                                    <tr>
                                        <th>Date</th>
                                        <th>Method</th>
                                        <th>Reference #</th>
                                        <th>Recorded By</th>
                                        <th class="text-right">Amount (₹)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${inv.payments.map(p => `
                                        <tr>
                                            <td>${p.payment_date || '—'}</td>
                                            <td><span class="badge" style="background:#f1f5f9; color:#475569;">${p.payment_method}</span></td>
                                            <td>${p.reference_number || '—'}</td>
                                            <td>${p.created_by || 'System'}</td>
                                            <td class="text-right" style="font-weight:600; color:#15803d;">₹${p.amount.toFixed(2)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        ` : `
                            <p class="text-muted" style="margin-bottom:1.5rem; font-size:13px;">No payments recorded yet for this invoice.</p>
                        `}
                    </div>

                    <div class="modal-footer" style="display:flex; justify-content:space-between;">
                        <a href="/api/invoices/${inv.id}/print" target="_blank" class="btn btn-secondary btn-sm">🖨️ Printable Version</a>
                        <div style="display:flex; gap:0.5rem;">
                            ${isStaff && inv.status === 'Draft' ? `
                                <button class="btn btn-primary" onclick="InvoiceView.confirmInvoice(${inv.id})">Confirm Invoice</button>
                                <button class="btn btn-danger btn-sm" onclick="InvoiceView.cancelInvoice(${inv.id})">Cancel Invoice</button>
                            ` : ''}
                            ${inv.status === 'Confirmed' && inv.outstanding_amount > 0 ? `
                                <button class="btn btn-primary" onclick="InvoiceView.payWithRazorpay(${inv.id})">💳 Pay Online (Razorpay)</button>
                                ${isStaff ? `<button class="btn btn-success" onclick="InvoiceView.openPaymentModal(${inv.id})">Manual Payment</button>` : ''}
                            ` : ''}
                            <button class="btn btn-secondary" onclick="InvoiceView.closeModal()">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('invoice-modal-container').innerHTML = modalHtml;
    },

    confirmInvoice: async (invoiceId) => {
        if (!confirm('Are you sure you want to confirm this invoice? Once confirmed, it will be billed to the customer.')) return;
        const res = await ApiClient.post(`/invoices/${invoiceId}/confirm`);
        if (res.success) {
            alert('Invoice confirmed successfully!');
            InvoiceView.closeModal();
            Router.handleRouting();
        } else {
            alert(res.error || 'Failed to confirm invoice');
        }
    },

    cancelInvoice: async (invoiceId) => {
        const reason = prompt('Please specify a cancellation reason:', 'Client request');
        if (reason === null) return;
        const res = await ApiClient.post(`/invoices/${invoiceId}/cancel`, { reason });
        if (res.success) {
            alert('Invoice cancelled.');
            InvoiceView.closeModal();
            Router.handleRouting();
        } else {
            alert(res.error || 'Failed to cancel invoice');
        }
    },

    openPaymentModal: (invoiceId) => {
        const inv = InvoiceView.currentInvoice && InvoiceView.currentInvoice.id === invoiceId
            ? InvoiceView.currentInvoice
            : InvoiceView.invoices.find(i => i.id === invoiceId);

        if (!inv) return;

        const maxAmount = inv.outstanding_amount || 0;
        const today = new Date().toISOString().split('T')[0];

        const modalHtml = `
            <div class="modal-backdrop" onclick="InvoiceView.closeModal(event)">
                <div class="modal" style="max-width:500px; width:90%;" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3 style="margin:0; color:#714B67;">Record Payment</h3>
                        <button class="btn btn-secondary btn-sm" onclick="InvoiceView.closeModal()">✕</button>
                    </div>
                    <form id="record-payment-form" onsubmit="InvoiceView.submitPayment(event, ${inv.id})">
                        <div class="modal-body">
                            <div style="background:#f8fafc; padding:1rem; border-radius:6px; margin-bottom:1rem;">
                                <div>Invoice: <strong>${inv.invoice_number}</strong></div>
                                <div>Outstanding Balance: <strong class="text-danger">₹${maxAmount.toFixed(2)}</strong></div>
                            </div>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Payment Amount (₹) *</label>
                                <input type="number" step="0.01" id="pay-amount" class="form-control" max="${maxAmount}" min="0.01" value="${maxAmount.toFixed(2)}" required>
                            </div>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Payment Method *</label>
                                <select id="pay-method" class="form-control" required>
                                    <option value="Bank Transfer">Bank Transfer / NEFT / RTGS</option>
                                    <option value="Credit Card">Credit Card</option>
                                    <option value="UPI">UPI</option>
                                    <option value="Cheque">Cheque</option>
                                    <option value="Cash">Cash</option>
                                </select>
                            </div>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Payment Date *</label>
                                <input type="date" id="pay-date" class="form-control" value="${today}" required>
                            </div>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Transaction / Reference #</label>
                                <input type="text" id="pay-reference" class="form-control" placeholder="e.g. TXN-12345678">
                            </div>

                            <div class="form-group">
                                <label>Notes</label>
                                <textarea id="pay-notes" class="form-control" rows="2" placeholder="Optional settlement notes"></textarea>
                            </div>
                        </div>

                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="InvoiceView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-success">Record Payment</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        document.getElementById('invoice-modal-container').innerHTML = modalHtml;
    },

    submitPayment: async (event, invoiceId) => {
        event.preventDefault();
        const amount = parseFloat(document.getElementById('pay-amount').value);
        const method = document.getElementById('pay-method').value;
        const date = document.getElementById('pay-date').value;
        const reference = document.getElementById('pay-reference').value;
        const notes = document.getElementById('pay-notes').value;

        const res = await ApiClient.post(`/invoices/${invoiceId}/payments`, {
            amount: amount,
            payment_method: method,
            payment_date: date,
            reference_number: reference,
            notes: notes
        });

        if (res.success) {
            alert('Payment recorded successfully!');
            InvoiceView.closeModal();
            Router.handleRouting();
        } else {
            alert(res.error || 'Payment recording failed');
        }
    },

    payWithRazorpay: async (invoiceId) => {
        try {
            // 1. Create order on backend server (server-authoritative paise amount)
            const res = await ApiClient.post('/payments/razorpay/create-order', { invoice_id: invoiceId });
            if (!res.success || !res.order) {
                alert(res.error || 'Failed to initialize Razorpay payment order');
                return;
            }

            const order = res.order;

            // 2. Configure official Razorpay checkout options
            const options = {
                key: order.key_id,
                amount: order.amount,
                currency: order.currency || 'INR',
                name: 'Brightloop Software',
                description: `Settlement for Invoice ${order.invoice_number}`,
                order_id: order.order_id,
                prefill: {
                    name: order.customer_name || '',
                    email: order.customer_email || '',
                    contact: order.customer_phone || ''
                },
                theme: {
                    color: '#714B67'
                },
                handler: async function (response) {
                    // 3. Signature verification callback
                    const verifyRes = await ApiClient.post('/payments/razorpay/verify', {
                        razorpay_order_id: response.razorpay_order_id,
                        razorpay_payment_id: response.razorpay_payment_id,
                        razorpay_signature: response.razorpay_signature
                    });

                    if (verifyRes.success) {
                        alert(`Payment of ₹${(order.amount / 100).toFixed(2)} captured successfully!\nTransaction ID: ${response.razorpay_payment_id}`);
                        InvoiceView.closeModal();
                        Router.handleRouting();
                    } else {
                        alert(`Payment signature verification failed: ${verifyRes.error}`);
                    }
                },
                modal: {
                    ondismiss: function () {
                        console.log('Razorpay modal closed');
                    }
                }
            };

            // 3. Open Razorpay Checkout modal
            if (typeof Razorpay === 'undefined') {
                alert(`Razorpay SDK is loading. Test Order ID: ${order.order_id}`);
                return;
            }

            const rzp = new Razorpay(options);
            rzp.on('payment.failed', function (response) {
                alert(`Payment failed: ${response.error.description}`);
            });
            rzp.open();
        } catch (err) {
            console.error('Razorpay checkout error:', err);
            alert(`Razorpay Checkout Error: ${err.message}`);
        }
    },

    openCreateModal: () => {
        const today = new Date().toISOString().split('T')[0];
        const dueDate = new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0];

        const modalHtml = `
            <div class="modal-backdrop" onclick="InvoiceView.closeModal(event)">
                <div class="modal" style="max-width:800px; width:90%; max-height:90vh; overflow-y:auto;" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3 style="margin:0; color:#714B67;">Create New Invoice</h3>
                        <button class="btn btn-secondary btn-sm" onclick="InvoiceView.closeModal()">✕</button>
                    </div>
                    <form id="create-invoice-form" onsubmit="InvoiceView.submitCreateInvoice(event)">
                        <div class="modal-body">
                            <!-- Basic details -->
                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem;">
                                <div class="form-group">
                                    <label>Customer *</label>
                                    <select id="new-inv-customer" class="form-control" required>
                                        <option value="">Select Customer...</option>
                                        ${InvoiceView.customers.map(c => `
                                            <option value="${c.id}">${c.full_name || `${c.first_name} ${c.last_name}`} (${c.email})</option>
                                        `).join('')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Subscription Link (Optional)</label>
                                    <select id="new-inv-sub" class="form-control">
                                        <option value="">None (One-off Invoice)</option>
                                        ${InvoiceView.subscriptions.map(s => `
                                            <option value="${s.id}">${s.subscription_number} — ${s.customer_name || 'Customer'}</option>
                                        `).join('')}
                                    </select>
                                </div>
                            </div>

                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem;">
                                <div class="form-group">
                                    <label>Invoice Date *</label>
                                    <input type="date" id="new-inv-date" class="form-control" value="${today}" required>
                                </div>
                                <div class="form-group">
                                    <label>Due Date *</label>
                                    <input type="date" id="new-inv-due" class="form-control" value="${dueDate}" required>
                                </div>
                            </div>

                            <!-- Line Item Builder -->
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:1.5rem; margin-bottom:0.5rem;">
                                <h4 style="margin:0;">Invoice Items</h4>
                                <button type="button" class="btn btn-secondary btn-sm" onclick="InvoiceView.addLineItemRow()">+ Add Item</button>
                            </div>

                            <table class="table" id="new-inv-items-table" style="margin-bottom:1rem;">
                                <thead>
                                    <tr>
                                        <th>Product / Description</th>
                                        <th style="width:100px;">Qty</th>
                                        <th style="width:130px;">Price (₹)</th>
                                        <th style="width:80px;">Tax %</th>
                                        <th style="width:40px;"></th>
                                    </tr>
                                </thead>
                                <tbody id="new-inv-items-body">
                                    <!-- Dynamic rows -->
                                </tbody>
                            </table>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Promotional / Discount Code (Optional)</label>
                                <input type="text" id="new-inv-discount-code" class="form-control" style="text-transform:uppercase;" placeholder="e.g. SAVE10">
                            </div>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Notes & Terms</label>
                                <textarea id="new-inv-notes" class="form-control" rows="2" placeholder="Payment instructions, bank account details..."></textarea>
                            </div>
                        </div>

                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="InvoiceView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Save as Draft</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        document.getElementById('invoice-modal-container').innerHTML = modalHtml;
        InvoiceView.addLineItemRow();
    },

    addLineItemRow: () => {
        const tbody = document.getElementById('new-inv-items-body');
        if (!tbody) return;

        const rowId = `item-row-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
        const tr = document.createElement('tr');
        tr.id = rowId;
        tr.innerHTML = `
            <td>
                <select class="form-control item-product" style="margin-bottom:4px;" onchange="InvoiceView.handleProductSelect(this, '${rowId}')">
                    <option value="">Custom description...</option>
                    ${InvoiceView.products.map(p => `
                        <option value="${p.id}" data-price="${p.sales_price}" data-tax="${p.tax_rate}">${p.name} (₹${p.sales_price})</option>
                    `).join('')}
                </select>
                <input type="text" class="form-control item-desc" placeholder="Item description" required>
            </td>
            <td>
                <input type="number" class="form-control item-qty" min="1" value="1" required>
            </td>
            <td>
                <input type="number" step="0.01" class="form-control item-price" min="0" value="0.00" required>
            </td>
            <td>
                <input type="number" class="form-control item-tax" value="18" readonly>
            </td>
            <td style="vertical-align:middle; text-align:center;">
                <button type="button" class="btn btn-danger btn-sm" onclick="document.getElementById('${rowId}').remove()" title="Remove line">✕</button>
            </td>
        `;
        tbody.appendChild(tr);
    },

    handleProductSelect: (selectEl, rowId) => {
        const row = document.getElementById(rowId);
        if (!row) return;

        const opt = selectEl.options[selectEl.selectedIndex];
        const descInput = row.querySelector('.item-desc');
        const priceInput = row.querySelector('.item-price');

        if (opt && opt.value) {
            descInput.value = opt.text.split(' (₹')[0];
            priceInput.value = opt.getAttribute('data-price') || '0.00';
        }
    },

    submitCreateInvoice: async (event) => {
        event.preventDefault();
        const customerId = parseInt(document.getElementById('new-inv-customer').value);
        const subId = document.getElementById('new-inv-sub').value ? parseInt(document.getElementById('new-inv-sub').value) : null;
        const invDate = document.getElementById('new-inv-date').value;
        const dueDate = document.getElementById('new-inv-due').value;
        const notes = document.getElementById('new-inv-notes').value;

        const rows = document.querySelectorAll('#new-inv-items-body tr');
        if (rows.length === 0) {
            alert('Please add at least one line item.');
            return;
        }

        const items = [];
        for (const row of rows) {
            const productSelect = row.querySelector('.item-product');
            const desc = row.querySelector('.item-desc').value.trim();
            const qty = parseFloat(row.querySelector('.item-qty').value);
            const price = parseFloat(row.querySelector('.item-price').value);
            const tax = parseFloat(row.querySelector('.item-tax').value || 18);

            if (!desc || isNaN(price)) {
                alert('Please fill out all line item descriptions and valid prices.');
                return;
            }

            items.push({
                product_id: productSelect.value ? parseInt(productSelect.value) : null,
                description: desc,
                quantity: qty,
                unit_price: price,
                tax_rate: tax,
                discount_amount: 0
            });
        }

        const discountCode = document.getElementById('new-inv-discount-code')?.value.trim().toUpperCase() || null;

        const res = await ApiClient.post('/invoices', {
            customer_id: customerId,
            subscription_id: subId,
            invoice_date: invDate,
            due_date: dueDate,
            discount_code: discountCode,
            items: items,
            notes: notes
        });

        if (res.success) {
            alert('Draft invoice created successfully!');
            InvoiceView.closeModal();
            Router.handleRouting();
        } else {
            alert(res.error || 'Failed to create invoice');
        }
    },

    openRecurringModal: () => {
        const today = new Date().toISOString().split('T')[0];
        const modalHtml = `
            <div class="modal-backdrop" onclick="InvoiceView.closeModal(event)">
                <div class="modal" style="max-width:500px; width:90%;" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3 style="margin:0; color:#714B67;">⚡ Recurring Billing Engine</h3>
                        <button class="btn btn-secondary btn-sm" onclick="InvoiceView.closeModal()">✕</button>
                    </div>
                    <form onsubmit="InvoiceView.triggerRecurringBilling(event)">
                        <div class="modal-body">
                            <p class="text-muted" style="margin-top:0;">
                                Scan all active recurring subscriptions and generate invoices for any cycles due on or before the selected date.
                            </p>
                            <div class="form-group">
                                <label>Target Billing Date</label>
                                <input type="date" id="billing-target-date" class="form-control" value="${today}" required>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="InvoiceView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Run Billing Batch</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
        document.getElementById('invoice-modal-container').innerHTML = modalHtml;
    },

    triggerRecurringBilling: async (event) => {
        event.preventDefault();
        const targetDate = document.getElementById('billing-target-date').value;
        const res = await ApiClient.post('/invoices/generate-recurring', { target_date: targetDate });

        if (res.success) {
            alert(`Billing Run Complete:\n• ${res.result.generated_count} invoices generated.\n• ${res.result.skipped_count} subscriptions up to date.`);
            InvoiceView.closeModal();
            Router.handleRouting();
        } else {
            alert(res.error || 'Billing engine error');
        }
    },

    closeModal: (event) => {
        if (event && event.target && !event.target.classList.contains('modal-backdrop')) return;
        const container = document.getElementById('invoice-modal-container');
        if (container) container.innerHTML = '';
    }
};

window.InvoiceView = InvoiceView;
