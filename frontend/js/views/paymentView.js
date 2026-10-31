/**
 * Payment Management View Component (Module 6)
 * =============================================
 * Handles payment recording across various channels (Credit Card, Wire, Cash, UPI),
 * tracking settled vs outstanding invoices, and overdue receivable chasing.
 */

const PaymentView = {
    payments: [],
    invoices: [],
    currentTab: 'transactions', // 'transactions' | 'receivables'

    render: async () => {
        const [payRes, invRes] = await Promise.all([
            ApiClient.get('/payments'),
            ApiClient.get('/invoices')
        ]);

        PaymentView.payments = payRes.success ? payRes.data : [];
        PaymentView.invoices = invRes.success ? invRes.data : [];

        const totalCollected = PaymentView.payments.reduce((sum, p) => sum + p.amount, 0);
        const outstandingInvoices = PaymentView.invoices.filter(i => i.status !== 'paid' && i.status !== 'cancelled');
        const totalOutstanding = outstandingInvoices.reduce((sum, i) => sum + (i.outstanding_balance || i.total_amount), 0);
        const overdueInvoices = outstandingInvoices.filter(i => i.is_overdue);

        return `
            <div class="view-header">
                <div>
                    <h2>Payment & Receivables Management</h2>
                    <p class="text-muted">Record incoming client payments, reconcile bank statements, and chase overdue revenue</p>
                </div>
                <div>
                    <button class="btn btn-primary" onclick="PaymentView.openRecordPaymentModal()">+ Record Payment</button>
                </div>
            </div>

            <!-- KPI Metric Cards -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon icon-green">💵</div>
                    <div class="stat-details">
                        <span class="stat-value">$${totalCollected.toFixed(2)}</span>
                        <span class="stat-label">Total Revenue Collected</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon icon-blue">🧾</div>
                    <div class="stat-details">
                        <span class="stat-value">${PaymentView.payments.length}</span>
                        <span class="stat-label">Successful Transactions</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon icon-orange">⏳</div>
                    <div class="stat-details">
                        <span class="stat-value">$${totalOutstanding.toFixed(2)}</span>
                        <span class="stat-label">Total Outstanding Due (${outstandingInvoices.length} invoices)</span>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon icon-red">⚠️</div>
                    <div class="stat-details">
                        <span class="stat-value text-danger">${overdueInvoices.length}</span>
                        <span class="stat-label">Overdue Invoices to Chase</span>
                    </div>
                </div>
            </div>

            <!-- Tab Switcher -->
            <div class="tabs-container">
                <button class="tab-btn ${PaymentView.currentTab === 'transactions' ? 'active' : ''}" onclick="PaymentView.switchTab('transactions')">
                    Payment Transactions (${PaymentView.payments.length})
                </button>
                <button class="tab-btn ${PaymentView.currentTab === 'receivables' ? 'active' : ''}" onclick="PaymentView.switchTab('receivables')">
                    Outstanding Receivables & Chasing (${outstandingInvoices.length})
                </button>
            </div>

            <!-- Tab Content -->
            <div id="payment-tab-content" class="card">
                <div class="card-body">
                    ${PaymentView.currentTab === 'transactions' ? PaymentView.renderTransactionsTable() : PaymentView.renderReceivablesTable()}
                </div>
            </div>

            <!-- Modal Container -->
            <div id="payment-modal-container"></div>
        `;
    },

    switchTab: (tabName) => {
        PaymentView.currentTab = tabName;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        if (event && event.target) event.target.classList.add('active');

        const container = document.getElementById('payment-tab-content');
        if (container) {
            container.querySelector('.card-body').innerHTML =
                tabName === 'transactions' ? PaymentView.renderTransactionsTable() : PaymentView.renderReceivablesTable();
        }
    },

    renderTransactionsTable: () => {
        const payments = PaymentView.payments;
        if (payments.length === 0) {
            return `<p class="empty-state">No payment transactions recorded yet. Click "+ Record Payment" to log an incoming payment.</p>`;
        }

        return `
            <div class="toolbar" style="margin-bottom:1rem;">
                <input type="text" id="pay-search" class="form-control toolbar-search" placeholder="Search reference, customer, or note..." oninput="PaymentView.filterPayments()">
            </div>
            <div id="pay-table-wrapper">
                <table class="table">
                    <thead>
                        <tr>
                            <th>Reference #</th>
                            <th>Invoice #</th>
                            <th>Customer</th>
                            <th>Method</th>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Status</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${payments.map(p => `
                            <tr>
                                <td><strong>${p.payment_reference}</strong></td>
                                <td><a href="#/invoices" class="font-bold">${p.invoice_number || 'Invoice'}</a></td>
                                <td>${p.customer_name || 'Customer'}<br><small class="text-muted">${p.customer_email || ''}</small></td>
                                <td>
                                    <span class="badge ${p.method === 'card' ? 'badge-info' : p.method === 'bank_transfer' ? 'badge-primary' : 'badge-success'}">
                                        ${(p.method || 'card').replace('_', ' ').toUpperCase()}
                                    </span>
                                </td>
                                <td>${p.paid_on || 'N/A'}</td>
                                <td><strong class="text-success">$${p.amount.toFixed(2)}</strong></td>
                                <td><span class="status-pill status-active">${p.status.toUpperCase()}</span></td>
                                <td><small class="text-muted">${p.note || '—'}</small></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    },

    renderReceivablesTable: () => {
        const outstanding = PaymentView.invoices.filter(i => i.status !== 'paid' && i.status !== 'cancelled');
        if (outstanding.length === 0) {
            return `<div class="empty-state text-success">🎉 All invoices are fully settled! No outstanding receivables.</div>`;
        }

        return `
            <p class="text-muted" style="margin-bottom:1rem;">
                The following invoices have outstanding unpaid balances. Use "Chase Overdue" to dispatch a reminder or "Record Payment" when money arrives.
            </p>
            <table class="table">
                <thead>
                    <tr>
                        <th>Invoice #</th>
                        <th>Customer</th>
                        <th>Due Date</th>
                        <th>Days Overdue</th>
                        <th>Total Invoiced</th>
                        <th>Remaining Owed</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${outstanding.map(inv => {
                        const today = new Date().toISOString().split('T')[0];
                        const isOverdue = inv.due_date < today;
                        let daysOverdue = 0;
                        if (isOverdue && inv.due_date) {
                            const diff = Math.floor((new Date(today) - new Date(inv.due_date)) / (1000 * 60 * 60 * 24));
                            daysOverdue = Math.max(0, diff);
                        }

                        return `
                            <tr class="${isOverdue ? 'overdue-row-highlight' : ''}">
                                <td><strong>${inv.invoice_number}</strong></td>
                                <td>${inv.customer_name || 'Customer'}<br><small class="text-muted">${inv.customer_email || ''}</small></td>
                                <td>${inv.due_date}</td>
                                <td>
                                    ${isOverdue 
                                        ? `<span class="badge badge-danger">⚠️ ${daysOverdue} days overdue</span>` 
                                        : '<span class="text-muted">Current</span>'}
                                </td>
                                <td>$${inv.total_amount.toFixed(2)}</td>
                                <td><strong class="text-danger">$${(inv.outstanding_balance || inv.total_amount).toFixed(2)}</strong></td>
                                <td><span class="status-pill ${isOverdue ? 'status-closed' : 'status-paused'}">${(inv.status || 'confirmed').toUpperCase()}</span></td>
                                <td>
                                    <div class="action-buttons-cell">
                                        <button class="btn btn-sm btn-primary" onclick="PaymentView.openRecordPaymentModal(${inv.id})">Record Payment</button>
                                        <button class="btn btn-sm btn-outline" onclick="PaymentView.chaseInvoice('${inv.invoice_number}', '${inv.customer_name}')">📧 Chase Overdue</button>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    },

    chaseInvoice: (invNumber, customerName) => {
        window.showToast(`Automated payment reminder dispatched to ${customerName} for ${invNumber}`, 'info');
    },

    filterPayments: () => {
        const query = (document.getElementById('pay-search')?.value || '').toLowerCase();
        const filtered = PaymentView.payments.filter(p => {
            return !query ||
                (p.payment_reference && p.payment_reference.toLowerCase().includes(query)) ||
                (p.customer_name && p.customer_name.toLowerCase().includes(query)) ||
                (p.invoice_number && p.invoice_number.toLowerCase().includes(query)) ||
                (p.note && p.note.toLowerCase().includes(query));
        });

        const wrapper = document.getElementById('pay-table-wrapper');
        if (wrapper) {
            wrapper.innerHTML = `
                <table class="table">
                    <thead>
                        <tr>
                            <th>Reference #</th>
                            <th>Invoice #</th>
                            <th>Customer</th>
                            <th>Method</th>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Status</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${filtered.map(p => `
                            <tr>
                                <td><strong>${p.payment_reference}</strong></td>
                                <td><a href="#/invoices" class="font-bold">${p.invoice_number || 'Invoice'}</a></td>
                                <td>${p.customer_name || 'Customer'}</td>
                                <td><span class="badge badge-info">${(p.method || 'card').toUpperCase()}</span></td>
                                <td>${p.paid_on || 'N/A'}</td>
                                <td><strong class="text-success">$${p.amount.toFixed(2)}</strong></td>
                                <td><span class="status-pill status-active">${p.status.toUpperCase()}</span></td>
                                <td><small class="text-muted">${p.note || '—'}</small></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    },

    // --- Record Payment Modal ---

    openRecordPaymentModal: (presetInvoiceId = null) => {
        const container = document.getElementById('payment-modal-container');
        if (!container) return;

        const unpaidInvoices = PaymentView.invoices.filter(i => i.status !== 'paid' && i.status !== 'cancelled');

        container.innerHTML = `
            <div class="modal-overlay" onclick="PaymentView.closeModal(event)">
                <div class="modal-card modal-md" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Record Incoming Payment</h3>
                        <button class="modal-close" onclick="PaymentView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="PaymentView.handlePaymentSubmit(event)">
                        <div class="modal-body">
                            <div class="form-group">
                                <label for="rec-inv-id">Select Target Invoice *</label>
                                <select id="rec-inv-id" class="form-control" required onchange="PaymentView.onInvoiceSelect()">
                                    <option value="">-- Choose Invoice --</option>
                                    ${unpaidInvoices.map(inv => `
                                        <option value="${inv.id}" data-due="${inv.outstanding_balance || inv.total_amount}" ${presetInvoiceId === inv.id ? 'selected' : ''}>
                                            ${inv.invoice_number} — ${inv.customer_name || 'Customer'} (Due: $${(inv.outstanding_balance || inv.total_amount).toFixed(2)})
                                        </option>
                                    `).join('')}
                                </select>
                            </div>

                            <div class="form-group">
                                <label for="rec-amount">Amount Received ($) *</label>
                                <input type="number" id="rec-amount" class="form-control" step="0.01" min="0.01" required placeholder="0.00">
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label for="rec-method">Payment Method *</label>
                                    <select id="rec-method" class="form-control" required>
                                        <option value="card">Credit Card (Stripe/POS)</option>
                                        <option value="bank_transfer">Direct Bank Wire / ACH</option>
                                        <option value="upi">UPI / Online Gateway</option>
                                        <option value="cash">Cash / Cheque</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="rec-date">Payment Date *</label>
                                    <input type="date" id="rec-date" class="form-control" value="${new Date().toISOString().split('T')[0]}" required>
                                </div>
                            </div>

                            <div class="form-group">
                                <label for="rec-note">Bank Reference / Memo Note</label>
                                <input type="text" id="rec-note" class="form-control" placeholder="e.g. Bank statement line #98124 / Wire cleared">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="PaymentView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Save Payment</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        if (presetInvoiceId) {
            PaymentView.onInvoiceSelect();
        }
    },

    onInvoiceSelect: () => {
        const select = document.getElementById('rec-inv-id');
        const selectedOpt = select.options[select.selectedIndex];
        if (selectedOpt && selectedOpt.dataset.due) {
            document.getElementById('rec-amount').value = parseFloat(selectedOpt.dataset.due).toFixed(2);
        }
    },

    handlePaymentSubmit: async (event) => {
        event.preventDefault();
        const invoiceId = parseInt(document.getElementById('rec-inv-id').value);
        const amount = parseFloat(document.getElementById('rec-amount').value);
        const method = document.getElementById('rec-method').value;
        const paidOn = document.getElementById('rec-date').value;
        const note = (document.getElementById('rec-note').value || '').trim();

        const res = await ApiClient.post('/payments', {
            invoice_id: invoiceId,
            amount: amount,
            method: method,
            paid_on: paidOn,
            note: note
        });

        if (res.success) {
            window.showToast(`Payment ${res.data.payment_reference} recorded successfully!`, 'success');
            PaymentView.closeModal();
            const content = await PaymentView.render();
            const container = document.getElementById('view-container');
            if (container) container.innerHTML = content;
        } else {
            window.showToast(res.error || 'Failed to record payment', 'error');
        }
    },

    closeModal: (event) => {
        if (event && event.target && !event.target.classList.contains('modal-overlay')) return;
        const container = document.getElementById('payment-modal-container');
        if (container) container.innerHTML = '';
    }
};

window.PaymentView = PaymentView;
