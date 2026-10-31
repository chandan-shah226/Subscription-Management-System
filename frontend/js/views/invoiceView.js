/**
 * Invoice & Billing Management View Component (Module 4)
 * ======================================================
 * Manages automated recurring billing generation, invoice status lifecycles,
 * professional tax invoice print layout, and payment dispatch.
 */

const InvoiceView = {
    invoices: [],
    subscriptions: [],
    currentFilter: '',
    searchQuery: '',

    render: async () => {
        const isCustomer = AuthManager.isCustomer();
        const [invRes, subsRes] = await Promise.all([
            ApiClient.get('/invoices'),
            ApiClient.get('/subscriptions', { status: 'active' })
        ]);

        InvoiceView.invoices = invRes.success ? invRes.data : [];
        InvoiceView.subscriptions = subsRes.success ? subsRes.data : [];

        return `
            <div class="view-header">
                <div>
                    <h2>${isCustomer ? 'My Invoices & Receipts' : 'Invoices & Billing Management'}</h2>
                    <p class="text-muted">
                        ${isCustomer
                            ? 'Review your billing history, download tax invoices, and settle outstanding balances online'
                            : 'Automated recurring billing, tax calculations, invoice confirmation, printing, and payment reconciliation'}
                    </p>
                </div>
                <div class="header-action-group">
                    ${!isCustomer ? `
                        <button class="btn btn-outline" onclick="InvoiceView.runBillingDayCron()">⚡ Run Billing Day Batch</button>
                        <button class="btn btn-primary" onclick="InvoiceView.openGenerateModal()">+ Generate From Subscription</button>
                    ` : ''}
                </div>
            </div>

            <!-- Overdue Notice Banner if any invoices overdue -->
            ${InvoiceView.renderOverdueBanner()}

            <!-- Filter Toolbar -->
            <div class="toolbar">
                <input type="text" id="inv-search" class="form-control toolbar-search" 
                       placeholder="Search invoice number, customer, or notes..." 
                       oninput="InvoiceView.filterInvoices()">
                <select id="inv-status-filter" class="form-control toolbar-select" onchange="InvoiceView.filterInvoices()">
                    <option value="">All Statuses</option>
                    <option value="draft">Draft</option>
                    <option value="confirmed">Confirmed (Unpaid)</option>
                    <option value="paid">Paid</option>
                    <option value="overdue">Overdue</option>
                    <option value="cancelled">Cancelled</option>
                </select>
            </div>

            <!-- Invoices Table Card -->
            <div class="card">
                <div class="card-body">
                    <div id="invoices-table-container">
                        ${InvoiceView.renderTable(InvoiceView.invoices)}
                    </div>
                </div>
            </div>

            <!-- Dynamic Modal Container -->
            <div id="invoice-modal-container"></div>
        `;
    },

    renderOverdueBanner: () => {
        const overdue = InvoiceView.invoices.filter(i => i.is_overdue && i.status !== 'paid');
        if (overdue.length === 0) return '';
        const totalOverdue = overdue.reduce((sum, i) => sum + (i.outstanding_balance || i.total_amount), 0);
        return `
            <div class="alert alert-danger" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
                <div>
                    <strong>⚠️ Overdue Receivables Alert:</strong> ${overdue.length} invoice(s) are currently past due date totaling <strong>$${totalOverdue.toFixed(2)}</strong>.
                </div>
                <button class="btn btn-sm btn-danger" onclick="InvoiceView.quickFilterStatus('overdue')">View Overdue</button>
            </div>
        `;
    },

    renderTable: (invList) => {
        if (!invList || invList.length === 0) {
            return `<p class="empty-state">No invoices found matching your criteria.</p>`;
        }

        const isCustomer = AuthManager.isCustomer();

        return `
            <table class="table">
                <thead>
                    <tr>
                        <th>Invoice #</th>
                        ${!isCustomer ? '<th>Customer</th>' : ''}
                        <th>Subscription</th>
                        <th>Invoice Date</th>
                        <th>Due Date</th>
                        <th>Total</th>
                        <th>Balance Due</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${invList.map(inv => {
                        const statusClass = inv.status === 'paid' ? 'status-active'
                            : inv.status === 'overdue' ? 'status-closed'
                            : inv.status === 'confirmed' ? 'status-paused'
                            : 'status-draft';

                        return `
                            <tr>
                                <td><strong>${inv.invoice_number}</strong></td>
                                ${!isCustomer ? `<td>${inv.customer_name || 'Customer'}<br><small class="text-muted">${inv.customer_email || ''}</small></td>` : ''}
                                <td>${inv.subscription_number ? `<span class="badge badge-info">${inv.subscription_number}</span>` : '<span class="text-muted">—</span>'}</td>
                                <td>${inv.invoice_date || 'N/A'}</td>
                                <td>
                                    <span class="${inv.is_overdue && inv.status !== 'paid' ? 'text-danger font-bold' : ''}">
                                        ${inv.due_date || 'N/A'} ${inv.is_overdue && inv.status !== 'paid' ? '⚠️' : ''}
                                    </span>
                                </td>
                                <td><strong>$${inv.total_amount.toFixed(2)}</strong></td>
                                <td>
                                    ${inv.outstanding_balance > 0 
                                        ? `<strong class="text-danger">$${inv.outstanding_balance.toFixed(2)}</strong>` 
                                        : '<span class="text-success">$0.00</span>'}
                                </td>
                                <td>
                                    <span class="status-pill ${statusClass}">${(inv.status || 'draft').toUpperCase()}</span>
                                </td>
                                <td>
                                    <div class="action-buttons-cell">
                                        <button class="btn btn-sm btn-secondary" onclick="InvoiceView.openDetailModal(${inv.id})">View / Print</button>
                                        ${!isCustomer && inv.status === 'draft' ? `
                                            <button class="btn btn-sm btn-success" onclick="InvoiceView.confirmInvoice(${inv.id})">Confirm</button>
                                        ` : ''}
                                        ${inv.status !== 'paid' && inv.status !== 'cancelled' ? `
                                            <button class="btn btn-sm btn-primary" onclick="InvoiceView.openPayModal(${inv.id})">
                                                ${isCustomer ? 'Pay Online' : 'Record Pay'}
                                            </button>
                                        ` : ''}
                                        ${!isCustomer && inv.status !== 'cancelled' && inv.status !== 'paid' ? `
                                            <button class="btn btn-sm btn-danger" onclick="InvoiceView.cancelInvoice(${inv.id})">Cancel</button>
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

    filterInvoices: () => {
        const query = (document.getElementById('inv-search')?.value || '').toLowerCase();
        const status = (document.getElementById('inv-status-filter')?.value || '').toLowerCase();

        const filtered = InvoiceView.invoices.filter(inv => {
            const matchesQuery = !query ||
                (inv.invoice_number && inv.invoice_number.toLowerCase().includes(query)) ||
                (inv.customer_name && inv.customer_name.toLowerCase().includes(query)) ||
                (inv.customer_email && inv.customer_email.toLowerCase().includes(query)) ||
                (inv.subscription_number && inv.subscription_number.toLowerCase().includes(query));

            const matchesStatus = !status || (inv.status && inv.status.toLowerCase() === status);
            return matchesQuery && matchesStatus;
        });

        const container = document.getElementById('invoices-table-container');
        if (container) {
            container.innerHTML = InvoiceView.renderTable(filtered);
        }
    },

    quickFilterStatus: (status) => {
        const select = document.getElementById('inv-status-filter');
        if (select) {
            select.value = status;
            InvoiceView.filterInvoices();
        }
    },

    // --- Actions ---

    runBillingDayCron: async () => {
        if (!confirm('Run Billing Day batch generation now? This will scan all active subscriptions due today and automatically create invoices without duplicates.')) return;
        const res = await ApiClient.post('/invoices/generate-batch', {});
        if (res.success) {
            window.showToast(res.message || 'Billing day batch completed', 'success');
            await InvoiceView.refreshData();
        } else {
            window.showToast(res.error || 'Failed to run billing day batch', 'error');
        }
    },

    confirmInvoice: async (invoiceId) => {
        const res = await ApiClient.post(`/invoices/${invoiceId}/confirm`, {});
        if (res.success) {
            window.showToast('Invoice confirmed successfully', 'success');
            await InvoiceView.refreshData();
        } else {
            window.showToast(res.error || 'Failed to confirm invoice', 'error');
        }
    },

    cancelInvoice: async (invoiceId) => {
        if (!confirm('Are you sure you want to cancel this invoice?')) return;
        const res = await ApiClient.post(`/invoices/${invoiceId}/cancel`, {});
        if (res.success) {
            window.showToast('Invoice cancelled', 'info');
            await InvoiceView.refreshData();
        } else {
            window.showToast(res.error || 'Failed to cancel invoice', 'error');
        }
    },

    refreshData: async () => {
        const res = await ApiClient.get('/invoices');
        if (res.success) {
            InvoiceView.invoices = res.data;
            const container = document.getElementById('invoices-table-container');
            if (container) {
                container.innerHTML = InvoiceView.renderTable(InvoiceView.invoices);
            }
        }
    },

    // --- Modal 1: Printable Tax Invoice ---

    openDetailModal: async (invoiceId) => {
        const res = await ApiClient.get(`/invoices/${invoiceId}`);
        if (!res.success || !res.data) {
            window.showToast('Failed to load invoice details', 'error');
            return;
        }

        const inv = res.data;
        const container = document.getElementById('invoice-modal-container');
        if (!container) return;

        const isPaid = inv.status === 'paid';
        const isOverdue = inv.is_overdue && !isPaid;

        container.innerHTML = `
            <div class="modal-overlay" onclick="InvoiceView.closeModal(event)">
                <div class="modal-card printable-invoice-card" onclick="event.stopPropagation()">
                    <div class="modal-header no-print">
                        <h3>Tax Invoice — ${inv.invoice_number}</h3>
                        <div class="modal-header-actions">
                            <button class="btn btn-outline btn-sm" onclick="window.print()">🖨️ Print / Save PDF</button>
                            <button class="modal-close" onclick="InvoiceView.closeModal()">&times;</button>
                        </div>
                    </div>

                    <!-- Printable Invoice Layout -->
                    <div class="printable-invoice-body" id="print-area">
                        <!-- Invoice Header -->
                        <div class="invoice-header-grid">
                            <div>
                                <h1 class="invoice-brand-title">Brightloop <span>Software</span></h1>
                                <p class="text-sm text-muted">Subscription & Cloud Systems Inc.<br>contact@brightloop.com • +1 (800) 555-0199</p>
                            </div>
                            <div class="invoice-meta-right">
                                <h2 class="invoice-title">INVOICE</h2>
                                <div class="invoice-meta-row"><strong>Invoice #:</strong> ${inv.invoice_number}</div>
                                <div class="invoice-meta-row"><strong>Invoice Date:</strong> ${inv.invoice_date}</div>
                                <div class="invoice-meta-row"><strong>Payment Due:</strong> ${inv.due_date}</div>
                                <div class="invoice-meta-row">
                                    <strong>Status:</strong> 
                                    <span class="status-pill ${isPaid ? 'status-active' : isOverdue ? 'status-closed' : 'status-paused'}">
                                        ${inv.status.toUpperCase()}
                                    </span>
                                </div>
                            </div>
                        </div>

                        <hr class="invoice-divider">

                        <!-- Bill To & Subscription References -->
                        <div class="invoice-parties-grid">
                            <div class="bill-to-box">
                                <span class="section-subtitle">BILL TO</span>
                                <h3 class="customer-name">${inv.customer_name || 'Valued Customer'}</h3>
                                <p class="customer-email">${inv.customer_email || ''}</p>
                            </div>
                            <div class="subscription-ref-box">
                                <span class="section-subtitle">SUBSCRIPTION REFERENCE</span>
                                <p><strong>Subscription #:</strong> ${inv.subscription_number || 'Direct Order'}</p>
                                ${inv.discount_code ? `<p><strong>Applied Coupon:</strong> <span class="badge badge-success">${inv.discount_code}</span></p>` : ''}
                            </div>
                        </div>

                        <!-- Itemized Table -->
                        <table class="invoice-items-table">
                            <thead>
                                <tr>
                                    <th>Description</th>
                                    <th class="text-center">Qty</th>
                                    <th class="text-right">Unit Price</th>
                                    <th class="text-right">Tax Rate</th>
                                    <th class="text-right">Amount</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${(inv.items && inv.items.length > 0 ? inv.items : [{ description: 'Subscription Service', quantity: 1, unit_price: inv.subtotal, tax_rate: 18, total_price: inv.total_amount }]).map(it => `
                                    <tr>
                                        <td>
                                            <strong>${it.description || it.product_name || 'Service Item'}</strong>
                                            ${it.variant_name ? `<br><small class="text-muted">Variant: ${it.variant_name}</small>` : ''}
                                        </td>
                                        <td class="text-center">${it.quantity}</td>
                                        <td class="text-right">$${it.unit_price.toFixed(2)}</td>
                                        <td class="text-right">${it.tax_rate}%</td>
                                        <td class="text-right font-bold">$${it.total_price.toFixed(2)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>

                        <!-- Totals Summary Grid -->
                        <div class="invoice-totals-grid">
                            <div class="invoice-notes-area">
                                <strong>Notes & Payment Terms:</strong>
                                <p class="text-sm text-muted">${inv.notes || 'Payment terms: Due within 15 days from issue date. Electronic bank wire and credit card payments accepted.'}</p>
                                ${inv.payments && inv.payments.length > 0 ? `
                                    <div class="payment-receipt-summary">
                                        <span class="text-xs font-bold text-success">✓ PAYMENT TRANSACTIONS RECORDED:</span>
                                        ${inv.payments.map(p => `
                                            <div class="text-xs text-muted">
                                                ${p.payment_reference} — $${p.amount.toFixed(2)} via ${(p.method || '').toUpperCase()} on ${p.paid_on}
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                            </div>
                            <div class="invoice-calculation-box">
                                <div class="calc-row"><span>Subtotal:</span> <span>$${inv.subtotal.toFixed(2)}</span></div>
                                ${inv.discount_amount > 0 ? `
                                    <div class="calc-row text-success"><span>Discount (${inv.discount_code || 'Promo'}):</span> <span>-$${inv.discount_amount.toFixed(2)}</span></div>
                                ` : ''}
                                <div class="calc-row"><span>Taxes (Auto 18%):</span> <span>+$${inv.tax_amount.toFixed(2)}</span></div>
                                <div class="calc-row total-highlight"><span>Total Due:</span> <span>$${inv.total_amount.toFixed(2)}</span></div>
                                <div class="calc-row text-muted"><span>Paid to Date:</span> <span>-$${inv.paid_amount.toFixed(2)}</span></div>
                                <div class="calc-row balance-row ${inv.outstanding_balance > 0 ? 'text-danger font-bold' : 'text-success'}">
                                    <span>Remaining Balance:</span> <span>$${inv.outstanding_balance.toFixed(2)}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="modal-footer no-print">
                        ${!isPaid && inv.status !== 'cancelled' ? `
                            <button class="btn btn-primary" onclick="InvoiceView.closeModal(); InvoiceView.openPayModal(${inv.id})">
                                ${AuthManager.isCustomer() ? '💳 Pay Invoice Online' : '💳 Record Customer Payment'}
                            </button>
                        ` : ''}
                        <button class="btn btn-secondary" onclick="InvoiceView.closeModal()">Close</button>
                    </div>
                </div>
            </div>
        `;
    },

    // --- Modal 2: Generate Invoice from Active Subscription ---

    openGenerateModal: () => {
        const container = document.getElementById('invoice-modal-container');
        if (!container) return;

        const subs = InvoiceView.subscriptions;

        container.innerHTML = `
            <div class="modal-overlay" onclick="InvoiceView.closeModal(event)">
                <div class="modal-card modal-md" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Generate Invoice From Subscription</h3>
                        <button class="modal-close" onclick="InvoiceView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="InvoiceView.handleGenerateSubmit(event)">
                        <div class="modal-body">
                            <div class="form-group">
                                <label for="gen-sub-id">Select Active Subscription *</label>
                                <select id="gen-sub-id" class="form-control" required>
                                    <option value="">-- Choose Subscription --</option>
                                    ${subs.map(s => `
                                        <option value="${s.id}">
                                            ${s.subscription_number} — ${s.customer_name || 'Customer'} ($${s.total_amount.toFixed(2)} / ${s.billing_frequency})
                                        </option>
                                    `).join('')}
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="gen-due-days">Payment Due Terms (Days)</label>
                                <input type="number" id="gen-due-days" class="form-control" value="15" min="1" max="90" required>
                            </div>
                            <div class="form-group">
                                <label for="gen-discount-code">Promotional Discount Code (Optional)</label>
                                <input type="text" id="gen-discount-code" class="form-control" placeholder="e.g. WELCOME10, VOLUME5">
                                <small class="form-hint">Admin discount rules apply automatically if valid.</small>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="InvoiceView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Generate Invoice</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    handleGenerateSubmit: async (event) => {
        event.preventDefault();
        const subId = document.getElementById('gen-sub-id').value;
        const dueDays = parseInt(document.getElementById('gen-due-days').value) || 15;
        const discountCode = (document.getElementById('gen-discount-code').value || '').trim();

        const res = await ApiClient.post(`/invoices/generate/${subId}`, {
            due_days: dueDays,
            discount_code: discountCode || null
        });

        if (res.success) {
            window.showToast(`Invoice ${res.data.invoice_number} created successfully!`, 'success');
            InvoiceView.closeModal();
            await InvoiceView.refreshData();
        } else {
            window.showToast(res.error || 'Failed to generate invoice', 'error');
        }
    },

    // --- Modal 3: Pay Invoice (Online / Record) ---

    openPayModal: async (invoiceId) => {
        const inv = InvoiceView.invoices.find(i => i.id === invoiceId);
        if (!inv) return;

        const container = document.getElementById('invoice-modal-container');
        if (!container) return;

        const isCustomer = AuthManager.isCustomer();
        const amountDue = inv.outstanding_balance > 0 ? inv.outstanding_balance : inv.total_amount;

        container.innerHTML = `
            <div class="modal-overlay" onclick="InvoiceView.closeModal(event)">
                <div class="modal-card modal-md" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>${isCustomer ? 'Pay Invoice Online' : 'Record Payment for Invoice'}</h3>
                        <button class="modal-close" onclick="InvoiceView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="InvoiceView.handlePaySubmit(event, ${inv.id})">
                        <div class="modal-body">
                            <div class="invoice-pay-summary-box">
                                <div><strong>Invoice:</strong> ${inv.invoice_number}</div>
                                <div><strong>Customer:</strong> ${inv.customer_name || 'Customer'}</div>
                                <div><strong>Total Amount:</strong> $${inv.total_amount.toFixed(2)}</div>
                                <div><strong>Remaining Balance:</strong> <strong class="text-danger">$${amountDue.toFixed(2)}</strong></div>
                            </div>

                            <div class="form-group" style="margin-top:1rem;">
                                <label for="pay-amount">Payment Amount ($) *</label>
                                <input type="number" id="pay-amount" class="form-control" step="0.01" min="0.01" max="${amountDue}" value="${amountDue.toFixed(2)}" required>
                            </div>

                            <div class="form-group">
                                <label for="pay-method">Payment Method *</label>
                                <select id="pay-method" class="form-control" required>
                                    <option value="card">Credit / Debit Card</option>
                                    <option value="bank_transfer">Bank Wire Transfer</option>
                                    <option value="upi">UPI / Instant Online</option>
                                    ${!isCustomer ? '<option value="cash">Cash / Cheque</option>' : ''}
                                </select>
                            </div>

                            ${isCustomer ? `
                                <div class="form-group">
                                    <label for="mock-card-num">Card Number (Mock Sandbox Checkout)</label>
                                    <input type="text" id="mock-card-num" class="form-control" placeholder="4242 •••• •••• 4242" value="4242 •••• •••• 4242">
                                </div>
                            ` : ''}

                            <div class="form-group">
                                <label for="pay-note">Transaction Reference / Note</label>
                                <input type="text" id="pay-note" class="form-control" placeholder="e.g. Ref #TXN-90214 / Online settlement">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="InvoiceView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">${isCustomer ? 'Confirm & Pay Now' : 'Save Payment Record'}</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    handlePaySubmit: async (event, invoiceId) => {
        event.preventDefault();
        const amount = parseFloat(document.getElementById('pay-amount').value);
        const method = document.getElementById('pay-method').value;
        const note = (document.getElementById('pay-note').value || '').trim();

        const res = await ApiClient.post('/payments', {
            invoice_id: invoiceId,
            amount: amount,
            method: method,
            note: note || `Online payment settled via ${method.toUpperCase()}`
        });

        if (res.success) {
            window.showToast(`Payment successful! Reference: ${res.data.payment_reference}`, 'success');
            InvoiceView.closeModal();
            await InvoiceView.refreshData();
        } else {
            window.showToast(res.error || 'Failed to record payment', 'error');
        }
    },

    closeModal: (event) => {
        if (event && event.target && !event.target.classList.contains('modal-overlay')) return;
        const container = document.getElementById('invoice-modal-container');
        if (container) container.innerHTML = '';
    }
};

window.InvoiceView = InvoiceView;
