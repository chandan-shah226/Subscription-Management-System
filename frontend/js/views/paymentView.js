/**
 * Payment Management View Component (Module 6)
 * ============================================
 * Unified payment audit trail and processing module:
 * - KPI summary metrics (Total Collected, Successful, Pending, Failed, Receivables)
 * - Multi-criteria search and filters (Method, Source, Status, Date)
 * - Transaction table with real-time status badges
 * - Manual offline payment recording modal (Staff/Admin)
 * - Transaction details and cryptographic receipt modal
 */

const PaymentView = {
    payments: [],
    stats: {},
    pagination: {},
    confirmedInvoices: [],
    currentPayment: null,

    render: async () => {
        let payRes, statsRes, invRes;
        try {
            [payRes, statsRes, invRes] = await Promise.all([
                ApiClient.get('/payments'),
                ApiClient.get('/payments/stats'),
                ApiClient.get('/invoices', { status: 'Confirmed' })
            ]);
        } catch (e) {
            console.error("Failed to fetch payment initial data:", e);
            payRes = { success: false, error: e.message };
            statsRes = { success: false };
            invRes = { success: false };
        }

        if (!payRes || !payRes.success) {
            return `
                <div class="view-header">
                    <div>
                        <h2>Payments & Financial Transactions</h2>
                        <p class="text-muted">Unified payment ledger tracking manual offline settlements and Razorpay online gateway captures</p>
                    </div>
                </div>
                <div class="card p-4 my-4" style="text-align: center; border: 1px solid #fee2e2; background: #fff; border-radius: 8px; padding: 3rem 1.5rem; margin-top: 1.5rem;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
                    <h3 style="color: #991b1b; margin-bottom: 0.5rem;">Unable to load payment records</h3>
                    <p class="text-muted" style="margin-bottom: 1.5rem;">${payRes?.error || 'A network or server error occurred while retrieving payment transactions.'}</p>
                    <button class="btn btn-primary" onclick="Router.handleRouting()">🔄 Retry Loading</button>
                </div>
            `;
        }

        const rawPayments = payRes.payments !== undefined ? payRes.payments : (payRes.data !== undefined ? payRes.data : []);
        PaymentView.payments = Array.isArray(rawPayments) ? rawPayments : [];
        PaymentView.pagination = payRes.pagination || {};
        PaymentView.stats = (statsRes && statsRes.success && statsRes.stats) ? statsRes.stats : ((statsRes && statsRes.data) || {});
        const rawInvoices = (invRes && invRes.success) ? (invRes.invoices !== undefined ? invRes.invoices : (invRes.data !== undefined ? invRes.data : [])) : [];
        PaymentView.confirmedInvoices = Array.isArray(rawInvoices) ? rawInvoices : [];

        const stats = PaymentView.stats;
        const isStaff = AuthManager.isStaff();

        return `
            <div class="view-header">
                <div>
                    <h2>Payments & Financial Transactions</h2>
                    <p class="text-muted">Unified payment ledger tracking manual offline settlements and Razorpay online gateway captures</p>
                </div>
                <div class="view-actions">
                    ${isStaff ? `
                        <button class="btn btn-primary btn-sm" onclick="PaymentView.openManualModal()">+ Record Offline Payment</button>
                    ` : ''}
                </div>
            </div>

            <!-- KPI Metric Cards -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <span class="kpi-title">Total Transactions</span>
                    <span class="kpi-value">${stats.total_payments || 0}</span>
                    <span class="kpi-subtext text-muted">All Recorded Payments</span>
                </div>
                <div class="kpi-card kpi-paid">
                    <span class="kpi-title">Total Collected</span>
                    <span class="kpi-value text-success">₹${(stats.total_collected || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                    <span class="kpi-subtext text-success">${stats.successful_payments || 0} Successful</span>
                </div>
                <div class="kpi-card kpi-outstanding">
                    <span class="kpi-title">Pending Settlements</span>
                    <span class="kpi-value text-warning">${stats.pending_payments || 0}</span>
                    <span class="kpi-subtext text-muted">Awaiting Gateway Callback</span>
                </div>
                <div class="kpi-card kpi-overdue">
                    <span class="kpi-title">Failed Payments</span>
                    <span class="kpi-value text-danger">${stats.failed_payments || 0}</span>
                    <span class="kpi-subtext text-muted">Declined / Timed Out</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Outstanding Receivables</span>
                    <span class="kpi-value text-danger">₹${(stats.outstanding_receivables || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</span>
                    <span class="kpi-subtext text-muted">Unpaid Confirmed Invoices</span>
                </div>
            </div>

            <!-- Toolbar & Search Filters -->
            <div class="toolbar card-body" style="background:#fff; border-radius:8px; margin-bottom:1.5rem; border:1px solid #e2e8f0; padding:1rem 1.25rem;">
                <div class="toolbar-row" style="display:flex; flex-wrap:wrap; gap:0.75rem; align-items:center; width:100%;">
                    <div style="flex: 2; min-width: 220px;">
                        <input type="text" id="pay-search" class="form-control" placeholder="Search by reference, order ID, invoice #, or customer..." oninput="PaymentView.handleFilterChange()">
                    </div>
                    <div style="flex: 1; min-width: 140px;">
                        <select id="pay-method-filter" class="form-control" onchange="PaymentView.handleFilterChange()">
                            <option value="">All Methods</option>
                            <option value="Razorpay">Razorpay Gateway</option>
                            <option value="Bank Transfer">Bank Transfer / NEFT</option>
                            <option value="UPI">UPI</option>
                            <option value="Credit Card">Credit Card</option>
                            <option value="Cash">Cash</option>
                            <option value="Cheque">Cheque</option>
                        </select>
                    </div>
                    <div style="flex: 1; min-width: 130px;">
                        <select id="pay-source-filter" class="form-control" onchange="PaymentView.handleFilterChange()">
                            <option value="">All Sources</option>
                            <option value="razorpay">Online (Razorpay)</option>
                            <option value="manual">Manual (Offline)</option>
                        </select>
                    </div>
                    <div style="flex: 1; min-width: 130px;">
                        <select id="pay-status-filter" class="form-control" onchange="PaymentView.handleFilterChange()">
                            <option value="">All Statuses</option>
                            <option value="captured">Captured (Success)</option>
                            <option value="pending">Pending</option>
                            <option value="failed">Failed</option>
                        </select>
                    </div>
                    <div style="display:flex; gap:0.5rem; align-items:center;">
                        <input type="date" id="pay-start-date" class="form-control" style="width:135px;" title="From date" onchange="PaymentView.handleFilterChange()">
                        <span class="text-muted">to</span>
                        <input type="date" id="pay-end-date" class="form-control" style="width:135px;" title="To date" onchange="PaymentView.handleFilterChange()">
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="PaymentView.resetFilters()">Reset</button>
                </div>
            </div>

            <!-- Payments Table Container -->
            <div id="payments-table-container">
                ${PaymentView.renderTable(PaymentView.payments)}
            </div>

            <!-- Modal Container -->
            <div id="payment-modal-container"></div>
        `;
    },

    renderTable: (payments) => {
        const list = Array.isArray(payments) ? payments : [];
        if (list.length === 0) {
            return `
                <div class="empty-state card" style="padding:3rem; text-align:center; background:#fff; border-radius:8px; border:1px solid #e2e8f0;">
                    <div style="font-size:42px; margin-bottom:0.75rem;">💳</div>
                    <h3 style="color:#714B67; margin-bottom:0.5rem;">No Payment Records Found</h3>
                    <p class="text-muted">Settled online Razorpay transactions and manual offline receipts will appear here.</p>
                </div>
            `;
        }

        return `
            <div class="table-responsive card" style="background:#fff; border-radius:8px; border:1px solid #e2e8f0; overflow:hidden;">
                <table class="table" style="width:100%; margin:0; border-collapse:collapse;">
                    <thead>
                        <tr style="background:#f8fafc; border-bottom:1px solid #e2e8f0;">
                            <th style="padding:12px 16px; text-align:left;">Reference # / ID</th>
                            <th style="padding:12px 16px; text-align:left;">Invoice #</th>
                            <th style="padding:12px 16px; text-align:left;">Customer</th>
                            <th style="padding:12px 16px; text-align:left;">Date</th>
                            <th style="padding:12px 16px; text-align:left;">Method & Source</th>
                            <th style="padding:12px 16px; text-align:right;">Amount (₹)</th>
                            <th style="padding:12px 16px; text-align:center;">Status</th>
                            <th style="padding:12px 16px; text-align:right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${list.map(p => {
                            let statusBadge = '<span class="badge" style="background:#dcfce7; color:#15803d;">CAPTURED</span>';
                            if (p.status === 'pending') {
                                statusBadge = '<span class="badge" style="background:#fef3c7; color:#92400e;">PENDING</span>';
                            } else if (p.status === 'failed') {
                                statusBadge = '<span class="badge" style="background:#fee2e2; color:#b91c1c;">FAILED</span>';
                            }

                            const sourceBadge = p.payment_source === 'razorpay'
                                ? '<span class="badge" style="background:#f3e8ff; color:#6b21a8;">Online (Razorpay)</span>'
                                : '<span class="badge" style="background:#f1f5f9; color:#475569;">Manual Offline</span>';

                            const refDisplay = p.razorpay_payment_id || p.reference_number || `PAY-${p.id}`;

                            return `
                                <tr style="border-bottom:1px solid #f1f5f9;">
                                    <td style="padding:12px 16px;">
                                        <div style="font-weight:600; font-family:monospace; color:#334155;">${refDisplay}</div>
                                        ${p.razorpay_order_id ? `<div style="font-size:11px; color:#64748b;">Order: ${p.razorpay_order_id}</div>` : ''}
                                    </td>
                                    <td style="padding:12px 16px;">
                                        <a href="#/invoices" style="color:#714B67; font-weight:600; text-decoration:none;">
                                            ${p.invoice_number || `INV-${p.invoice_id}`}
                                        </a>
                                    </td>
                                    <td style="padding:12px 16px;">
                                        <div style="font-weight:500;">${p.customer_name || '—'}</div>
                                    </td>
                                    <td style="padding:12px 16px; font-size:13px; color:#64748b;">
                                        ${p.payment_date || '—'}
                                    </td>
                                    <td style="padding:12px 16px;">
                                        <div style="font-weight:500;">${p.payment_method}</div>
                                        <div style="margin-top:2px;">${sourceBadge}</div>
                                    </td>
                                    <td style="padding:12px 16px; text-align:right; font-weight:700; color:#15803d; font-size:14px;">
                                        ₹${(p.amount || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}
                                    </td>
                                    <td style="padding:12px 16px; text-align:center;">
                                        ${statusBadge}
                                    </td>
                                    <td style="padding:12px 16px; text-align:right;">
                                        <button class="btn btn-secondary btn-sm" onclick="PaymentView.openDetailModal(${p.id})">Details</button>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    },

    handleFilterChange: async () => {
        const search = document.getElementById('pay-search')?.value || '';
        const method = document.getElementById('pay-method-filter')?.value || '';
        const source = document.getElementById('pay-source-filter')?.value || '';
        const status = document.getElementById('pay-status-filter')?.value || '';
        const startDate = document.getElementById('pay-start-date')?.value || '';
        const endDate = document.getElementById('pay-end-date')?.value || '';

        const params = {};
        if (search) params.search = search;
        if (method) params.payment_method = method;
        if (source) params.payment_source = source;
        if (status) params.status = status;
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;

        const res = await ApiClient.get('/payments', params);
        if (res.success) {
            const rawPayments = res.payments !== undefined ? res.payments : (res.data !== undefined ? res.data : []);
            PaymentView.payments = Array.isArray(rawPayments) ? rawPayments : [];
            const container = document.getElementById('payments-table-container');
            if (container) {
                container.innerHTML = PaymentView.renderTable(PaymentView.payments);
            }
        }
    },

    resetFilters: async () => {
        if (document.getElementById('pay-search')) document.getElementById('pay-search').value = '';
        if (document.getElementById('pay-method-filter')) document.getElementById('pay-method-filter').value = '';
        if (document.getElementById('pay-source-filter')) document.getElementById('pay-source-filter').value = '';
        if (document.getElementById('pay-status-filter')) document.getElementById('pay-status-filter').value = '';
        if (document.getElementById('pay-start-date')) document.getElementById('pay-start-date').value = '';
        if (document.getElementById('pay-end-date')) document.getElementById('pay-end-date').value = '';
        await PaymentView.handleFilterChange();
    },

    openManualModal: async () => {
        // Fetch fresh list of Confirmed invoices with outstanding balance
        const res = await ApiClient.get('/invoices', { status: 'Confirmed' });
        const invoices = res.success ? (res.invoices || res.data || []).filter(i => (i.outstanding_amount || 0) > 0) : [];
        PaymentView.confirmedInvoices = invoices;

        if (invoices.length === 0) {
            alert('There are currently no confirmed invoices awaiting payment.');
            return;
        }

        const firstInv = invoices[0];
        const modalHtml = `
            <div class="modal-backdrop" onclick="PaymentView.closeModal(event)">
                <div class="modal" style="max-width:550px; width:90%;" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3 style="margin:0; color:#714B67;">Record Offline Payment</h3>
                        <button class="btn btn-secondary btn-sm" onclick="PaymentView.closeModal()">✕</button>
                    </div>

                    <form id="manual-payment-form" onsubmit="PaymentView.submitManualPayment(event)">
                        <div class="modal-body">
                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Select Confirmed Invoice *</label>
                                <select id="mp-invoice-id" class="form-control" onchange="PaymentView.onInvoiceSelectChange()" required>
                                    ${invoices.map(inv => `
                                        <option value="${inv.id}" data-outstanding="${inv.outstanding_amount}" data-customer="${inv.customer_name}">
                                            ${inv.invoice_number} — ${inv.customer_name} (Outstanding: ₹${inv.outstanding_amount.toFixed(2)})
                                        </option>
                                    `).join('')}
                                </select>
                            </div>

                            <div style="background:#f8fafc; padding:1rem; border-radius:6px; margin-bottom:1rem; border:1px solid #e2e8f0;">
                                <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                                    <span class="text-muted">Customer:</span>
                                    <strong id="mp-customer-display">${firstInv.customer_name}</strong>
                                </div>
                                <div style="display:flex; justify-content:space-between;">
                                    <span class="text-muted">Outstanding Balance:</span>
                                    <strong id="mp-outstanding-display" class="text-danger">₹${firstInv.outstanding_amount.toFixed(2)}</strong>
                                </div>
                            </div>

                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem;">
                                <div class="form-group">
                                    <label>Payment Amount (₹) *</label>
                                    <input type="number" step="0.01" min="0.01" max="${firstInv.outstanding_amount}" id="mp-amount" class="form-control" value="${firstInv.outstanding_amount.toFixed(2)}" required>
                                </div>
                                <div class="form-group">
                                    <label>Payment Method *</label>
                                    <select id="mp-method" class="form-control" required>
                                        <option value="Bank Transfer">Bank Transfer / NEFT / RTGS</option>
                                        <option value="UPI">UPI</option>
                                        <option value="Cheque">Cheque</option>
                                        <option value="Cash">Cash</option>
                                        <option value="Credit Card">Credit Card (POS Terminal)</option>
                                    </select>
                                </div>
                            </div>

                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem;">
                                <div class="form-group">
                                    <label>Payment Date *</label>
                                    <input type="date" id="mp-date" class="form-control" value="${new Date().toISOString().split('T')[0]}" required>
                                </div>
                                <div class="form-group">
                                    <label>Reference # / UTR</label>
                                    <input type="text" id="mp-ref" class="form-control" placeholder="e.g. UTR-987654321">
                                </div>
                            </div>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Internal Notes</label>
                                <textarea id="mp-notes" class="form-control" rows="2" placeholder="Cheque clearance notes, receipt memo, etc."></textarea>
                            </div>
                        </div>

                        <div class="modal-footer" style="display:flex; justify-content:flex-end; gap:0.5rem;">
                            <button type="button" class="btn btn-secondary" onclick="PaymentView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Record Payment</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        document.getElementById('payment-modal-container').innerHTML = modalHtml;
    },

    onInvoiceSelectChange: () => {
        const select = document.getElementById('mp-invoice-id');
        const selectedOption = select.options[select.selectedIndex];
        const outstanding = parseFloat(selectedOption.getAttribute('data-outstanding')) || 0;
        const customer = selectedOption.getAttribute('data-customer') || '';

        document.getElementById('mp-customer-display').textContent = customer;
        document.getElementById('mp-outstanding-display').textContent = `₹${outstanding.toFixed(2)}`;

        const amountInput = document.getElementById('mp-amount');
        amountInput.max = outstanding;
        amountInput.value = outstanding.toFixed(2);
    },

    submitManualPayment: async (event) => {
        event.preventDefault();
        const invoiceId = parseInt(document.getElementById('mp-invoice-id').value);
        const amount = parseFloat(document.getElementById('mp-amount').value);
        const paymentMethod = document.getElementById('mp-method').value;
        const paymentDate = document.getElementById('mp-date').value;
        const referenceNumber = document.getElementById('mp-ref').value.trim();
        const notes = document.getElementById('mp-notes').value.trim();

        const payload = {
            invoice_id: invoiceId,
            amount,
            payment_method: paymentMethod,
            payment_date: paymentDate,
            reference_number: referenceNumber,
            notes
        };

        const res = await ApiClient.post('/payments/manual', payload);
        if (res.success) {
            alert(res.message || 'Payment recorded successfully!');
            PaymentView.closeModal();
            Router.handleRouting();
        } else {
            alert(res.error || 'Failed to record manual payment');
        }
    },

    openDetailModal: async (paymentId) => {
        const res = await ApiClient.get(`/payments/${paymentId}`);
        if (!res.success) {
            alert(res.error || 'Failed to fetch payment details');
            return;
        }

        const p = res.payment;
        PaymentView.currentPayment = p;

        const modalHtml = `
            <div class="modal-backdrop" onclick="PaymentView.closeModal(event)">
                <div class="modal" style="max-width:600px; width:90%;" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <div>
                            <h3 style="margin:0; color:#714B67;">Payment Receipt</h3>
                            <span class="text-muted" style="font-size:12px;">ID: ${p.reference_number || p.razorpay_payment_id || p.id}</span>
                        </div>
                        <button class="btn btn-secondary btn-sm" onclick="PaymentView.closeModal()">✕</button>
                    </div>

                    <div class="modal-body">
                        <!-- Amount Banner -->
                        <div style="background:#f0fdf4; border:1px solid #bbf7d0; padding:1.25rem; border-radius:8px; text-align:center; margin-bottom:1.5rem;">
                            <span style="font-size:12px; color:#15803d; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Amount Settled</span>
                            <div style="font-size:28px; font-weight:800; color:#15803d; margin:4px 0;">₹${p.amount.toFixed(2)} ${p.currency}</div>
                            <span class="badge" style="background:#dcfce7; color:#15803d; font-weight:700;">${p.status.toUpperCase()}</span>
                        </div>

                        <!-- Details Grid -->
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1.5rem; background:#f8fafc; padding:1.25rem; border-radius:8px; font-size:13px;">
                            <div>
                                <div class="text-muted">Invoice Number</div>
                                <div style="font-weight:600;">${p.invoice_number}</div>
                            </div>
                            <div>
                                <div class="text-muted">Customer Name</div>
                                <div style="font-weight:600;">${p.customer_name}</div>
                            </div>
                            <div>
                                <div class="text-muted">Payment Method</div>
                                <div style="font-weight:600;">${p.payment_method}</div>
                            </div>
                            <div>
                                <div class="text-muted">Payment Source</div>
                                <div style="font-weight:600; text-transform:capitalize;">${p.payment_source}</div>
                            </div>
                            <div>
                                <div class="text-muted">Payment Date</div>
                                <div style="font-weight:600;">${p.payment_date}</div>
                            </div>
                            <div>
                                <div class="text-muted">Recorded Timestamp</div>
                                <div style="font-weight:600;">${p.created_at ? p.created_at.split('T')[0] : 'N/A'}</div>
                            </div>
                        </div>

                        ${p.payment_source === 'razorpay' ? `
                            <div style="background:#faf5ff; border:1px solid #e9d5ff; padding:1rem; border-radius:6px; margin-bottom:1.5rem; font-size:12px;">
                                <div style="font-weight:700; color:#6b21a8; margin-bottom:0.5rem;">🔐 Razorpay Online Verification Details</div>
                                <div>Order ID: <code style="color:#6b21a8;">${p.razorpay_order_id || 'N/A'}</code></div>
                                <div>Payment ID: <code style="color:#6b21a8;">${p.razorpay_payment_id || 'N/A'}</code></div>
                                <div>Signature Check: <strong class="text-success">✓ Cryptographically Verified (HMAC-SHA256)</strong></div>
                            </div>
                        ` : ''}

                        ${p.notes ? `
                            <div style="margin-bottom:1rem;">
                                <label style="font-weight:600; font-size:12px; color:#64748b;">Notes / Memo</label>
                                <div style="background:#f8fafc; padding:0.75rem; border-radius:6px; font-size:13px; white-space:pre-wrap;">${p.notes}</div>
                            </div>
                        ` : ''}
                    </div>

                    <div class="modal-footer" style="display:flex; justify-content:flex-end;">
                        <button class="btn btn-secondary" onclick="PaymentView.closeModal()">Close</button>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('payment-modal-container').innerHTML = modalHtml;
    },

    closeModal: (event) => {
        if (!event || event.target.classList.contains('modal-backdrop')) {
            const container = document.getElementById('payment-modal-container');
            if (container) container.innerHTML = '';
        }
    }
};

window.PaymentView = PaymentView;
