/**
 * Quotation Management View Component (Module 3)
 * ==============================================
 * Manages quotations, reusable templates, live line-item pricing & taxes,
 * lifecycle status transitions, and quotation-to-subscription conversion.
 */

const QuotationView = {
    quotations: [],
    products: [],
    plans: [],
    customers: [],
    lineItems: [],

    render: async () => {
        const [qRes, pRes, planRes] = await Promise.all([
            ApiClient.get('/quotations'),
            ApiClient.get('/products', { active_only: true }),
            ApiClient.get('/plans', { available_only: true })
        ]);

        QuotationView.quotations = qRes.success ? qRes.data : [];
        QuotationView.products = pRes.success ? pRes.data : [];
        QuotationView.plans = planRes.success ? planRes.data : [];

        // If staff/admin, fetch customers for quotation creation
        if (AuthManager.isStaff()) {
            const uRes = await ApiClient.get('/users', { role: 'customer' });
            QuotationView.customers = uRes.success ? uRes.data : [];
        }

        return `
            <div class="view-header">
                <div>
                    <h2>Quotations & Proposals</h2>
                    <p class="text-muted">Draft, price estimates, apply taxes, and convert accepted quotes into recurring subscriptions</p>
                </div>
                <div class="header-action-group">
                    <button class="btn btn-outline" onclick="QuotationView.openTemplatesModal()">Reusable Templates</button>
                    <button class="btn btn-primary" onclick="QuotationView.openCreateModal()">+ Create Quotation</button>
                </div>
            </div>

            <!-- Filter Toolbar -->
            <div class="toolbar">
                <input type="text" id="quote-search" class="form-control toolbar-search" placeholder="Search quotation number or customer..." oninput="QuotationView.filterQuotes()">
                <select id="quote-status-filter" class="form-control toolbar-select" onchange="QuotationView.filterQuotes()">
                    <option value="">All Statuses</option>
                    <option value="draft">Draft</option>
                    <option value="sent">Sent</option>
                    <option value="confirmed">Confirmed</option>
                    <option value="rejected">Rejected</option>
                    <option value="expired">Expired</option>
                </select>
            </div>

            <!-- Quotations Table -->
            <div class="card">
                <div class="card-body">
                    <div id="quotes-table-container">
                        ${QuotationView.renderTable(QuotationView.quotations)}
                    </div>
                </div>
            </div>

            <!-- Modal Container -->
            <div id="quotation-modal-container"></div>
        `;
    },

    renderTable: (quoteList) => {
        if (quoteList.length === 0) {
            return `<p class="empty-state">No quotations found matching your criteria.</p>`;
        }

        return `
            <table class="table">
                <thead>
                    <tr>
                        <th>Quotation #</th>
                        <th>Customer</th>
                        <th>Plan</th>
                        <th>Status</th>
                        <th>Valid Until</th>
                        <th>Subtotal</th>
                        <th>Tax</th>
                        <th>Total</th>
                        <th>Subscription</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${quoteList.map(q => `
                        <tr>
                            <td><strong>${q.quotation_number}</strong></td>
                            <td>${q.customer_name || 'Customer'}</td>
                            <td>${q.plan_name ? `<span class="badge badge-info">${q.plan_name}</span>` : '<span class="text-muted">—</span>'}</td>
                            <td><span class="status-pill status-${q.status}">${q.status.toUpperCase()}</span></td>
                            <td>${q.valid_until || 'N/A'}</td>
                            <td>$${q.subtotal.toFixed(2)}</td>
                            <td>$${q.tax_amount.toFixed(2)}</td>
                            <td><strong>$${q.total_amount.toFixed(2)}</strong></td>
                            <td>
                                ${q.has_converted_subscription ? `
                                    <span class="badge badge-success">${q.subscription_number}</span>
                                ` : '<span class="text-muted">Not Converted</span>'}
                            </td>
                            <td>
                                <button class="btn btn-sm btn-secondary" onclick="QuotationView.openDetailsModal(${q.id})">Details &rarr;</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    filterQuotes: () => {
        const search = (document.getElementById('quote-search').value || '').toLowerCase();
        const status = document.getElementById('quote-status-filter').value;

        const filtered = QuotationView.quotations.filter(q => {
            const matchesSearch = q.quotation_number.toLowerCase().includes(search) || 
                                  (q.customer_name && q.customer_name.toLowerCase().includes(search));
            const matchesStatus = !status || q.status === status;
            return matchesSearch && matchesStatus;
        });

        document.getElementById('quotes-table-container').innerHTML = QuotationView.renderTable(filtered);
    },

    // --- CREATE QUOTATION WITH LIVE LINE CALCULATIONS ---

    openCreateModal: (templateData = null) => {
        QuotationView.lineItems = [];
        const isStaff = AuthManager.isStaff();
        const currentUserId = AuthManager.getUser().id;

        const container = document.getElementById('quotation-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="QuotationView.closeModal(event)">
                <div class="modal-dialog modal-xl" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>${templateData ? 'Create from Template' : 'Create New Quotation'}</h3>
                        <button class="modal-close" onclick="QuotationView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="QuotationView.submitCreateQuotation(event)">
                        <div class="modal-body">
                            <!-- Header fields -->
                            <div class="form-row">
                                ${isStaff ? `
                                    <div class="form-group">
                                        <label>Customer *</label>
                                        <select id="quote-customer" class="form-control" required>
                                            <option value="">Select Customer...</option>
                                            ${QuotationView.customers.map(c => `
                                                <option value="${c.id}">${c.full_name} (${c.email})</option>
                                            `).join('')}
                                        </select>
                                    </div>
                                ` : `
                                    <input type="hidden" id="quote-customer" value="${currentUserId}">
                                `}
                                <div class="form-group">
                                    <label>Associated Subscription Plan</label>
                                    <select id="quote-plan" class="form-control" onchange="QuotationView.onPlanSelected()">
                                        <option value="">No Plan / Ad-hoc</option>
                                        ${QuotationView.plans.map(p => `
                                            <option value="${p.id}">${p.name} ($${p.base_price}/mo - Min Qty: ${p.minimum_quantity})</option>
                                        `).join('')}
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Valid Until *</label>
                                    <input type="date" id="quote-valid-until" class="form-control" required>
                                </div>
                            </div>

                            <!-- Line items builder -->
                            <div class="line-items-section mt-3">
                                <div class="d-flex justify-between align-center mb-2">
                                    <h4>Product Line Items</h4>
                                    <button type="button" class="btn btn-sm btn-primary" onclick="QuotationView.addLineItem()">+ Add Line Item</button>
                                </div>
                                <div class="table-responsive">
                                    <table class="table line-items-table">
                                        <thead>
                                            <tr>
                                                <th style="width: 28%">Product *</th>
                                                <th style="width: 25%">Variant (Optional)</th>
                                                <th style="width: 10%">Quantity *</th>
                                                <th style="width: 14%">Unit Price ($)</th>
                                                <th style="width: 10%">Tax Rate (%)</th>
                                                <th style="width: 13%">Line Total</th>
                                                <th style="width: 5%"></th>
                                            </tr>
                                        </thead>
                                        <tbody id="line-items-tbody">
                                            <!-- Dynamically added rows -->
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <!-- Live Calculation Summary Card -->
                            <div class="quote-totals-box mt-3">
                                <div class="totals-row">
                                    <span>Subtotal:</span>
                                    <strong id="live-subtotal">$0.00</strong>
                                </div>
                                <div class="totals-row">
                                    <span>Tax Amount:</span>
                                    <strong id="live-tax">$0.00</strong>
                                </div>
                                <div class="totals-row total-highlight">
                                    <span>Grand Total:</span>
                                    <strong id="live-grand-total">$0.00</strong>
                                </div>
                            </div>

                            <!-- Notes & Terms -->
                            <div class="form-row mt-3">
                                <div class="form-group">
                                    <label>Notes / Memo</label>
                                    <textarea id="quote-notes" class="form-control" rows="2" placeholder="Internal or customer notes..."></textarea>
                                </div>
                                <div class="form-group">
                                    <label>Terms & Conditions</label>
                                    <textarea id="quote-terms" class="form-control" rows="2" placeholder="Standard payment and subscription terms..."></textarea>
                                </div>
                            </div>

                            <!-- Template Option -->
                            <div class="mt-2">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="quote-is-template"> Also save this quotation as a reusable template
                                </label>
                                <div id="template-name-group" class="form-group mt-2 d-none">
                                    <label>Template Name</label>
                                    <input type="text" id="quote-template-name" class="form-control" placeholder="e.g. Standard Cloud Starter Template">
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="QuotationView.closeModal()">Cancel</button>
                            <button type="submit" id="save-quote-btn" class="btn btn-primary">Create Draft Quotation</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        // Default valid until date: today + 30 days
        const defaultDate = new Date();
        defaultDate.setDate(defaultDate.getDate() + 30);
        document.getElementById('quote-valid-until').value = defaultDate.toISOString().split('T')[0];

        // Toggle template name input
        document.getElementById('quote-is-template').addEventListener('change', (e) => {
            const nameGroup = document.getElementById('template-name-group');
            if (e.target.checked) nameGroup.classList.remove('d-none');
            else nameGroup.classList.add('d-none');
        });

        // Add initial row or copy from template
        if (templateData && templateData.items && templateData.items.length > 0) {
            templateData.items.forEach(item => {
                QuotationView.addLineItem(item);
            });
            if (templateData.plan_id) {
                document.getElementById('quote-plan').value = templateData.plan_id;
            }
        } else {
            QuotationView.addLineItem();
        }
    },

    addLineItem: (prefill = null) => {
        const tbody = document.getElementById('line-items-tbody');
        if (!tbody) return;

        const rowIndex = QuotationView.lineItems.length;
        const itemId = `row-${Date.now()}-${rowIndex}`;

        const row = document.createElement('tr');
        row.id = itemId;
        row.innerHTML = `
            <td>
                <select class="form-control item-product" onchange="QuotationView.onProductChange('${itemId}')" required>
                    <option value="">Select Product...</option>
                    ${QuotationView.products.map(p => `
                        <option value="${p.id}" ${prefill && prefill.product_id === p.id ? 'selected' : ''}>
                            ${p.name} ($${p.sales_price.toFixed(2)})
                        </option>
                    `).join('')}
                </select>
            </td>
            <td>
                <select class="form-control item-variant" onchange="QuotationView.onVariantChange('${itemId}')">
                    <option value="">Base Product</option>
                </select>
            </td>
            <td>
                <input type="number" min="1" class="form-control item-quantity" value="${prefill ? prefill.quantity : 1}" oninput="QuotationView.recalculateTotals()" required>
            </td>
            <td>
                <input type="number" step="0.01" min="0" class="form-control item-unit-price" value="${prefill ? prefill.unit_price : '0.00'}" oninput="QuotationView.recalculateTotals()" required>
            </td>
            <td>
                <input type="number" step="0.01" min="0" class="form-control item-tax-rate" value="${prefill ? prefill.tax_rate : '18.00'}" oninput="QuotationView.recalculateTotals()" required>
            </td>
            <td>
                <strong class="item-line-total text-success">$0.00</strong>
            </td>
            <td>
                <button type="button" class="btn btn-sm btn-danger btn-icon" onclick="QuotationView.removeLineItem('${itemId}')">&times;</button>
            </td>
        `;

        tbody.appendChild(row);
        QuotationView.lineItems.push(itemId);

        // Populate variants for prefill or default
        if (prefill) {
            QuotationView.onProductChange(itemId, prefill.variant_id);
        } else if (QuotationView.products.length > 0) {
            row.querySelector('.item-product').value = QuotationView.products[0].id;
            QuotationView.onProductChange(itemId);
        }
    },

    removeLineItem: (itemId) => {
        const row = document.getElementById(itemId);
        if (row) row.remove();
        QuotationView.lineItems = QuotationView.lineItems.filter(id => id !== itemId);
        QuotationView.recalculateTotals();
    },

    onProductChange: (itemId, selectVariantId = null) => {
        const row = document.getElementById(itemId);
        if (!row) return;

        const prodId = parseInt(row.querySelector('.item-product').value, 10);
        const prod = QuotationView.products.find(p => p.id === prodId);
        const variantSelect = row.querySelector('.item-variant');

        if (!prod) {
            variantSelect.innerHTML = '<option value="">Base Product</option>';
            row.querySelector('.item-unit-price').value = '0.00';
            QuotationView.recalculateTotals();
            return;
        }

        // Set base unit price and tax
        row.querySelector('.item-unit-price').value = prod.sales_price.toFixed(2);
        row.querySelector('.item-tax-rate').value = prod.tax_rate.toFixed(2);

        // Populate variants
        let variantOptions = '<option value="">Base Product</option>';
        if (prod.variants && prod.variants.length > 0) {
            prod.variants.filter(v => v.is_active).forEach(v => {
                const selected = selectVariantId === v.id ? 'selected' : '';
                variantOptions += `<option value="${v.id}" data-add="${v.additional_price}" ${selected}>${v.variant_name} (+$${v.additional_price.toFixed(2)})</option>`;
            });
        }
        variantSelect.innerHTML = variantOptions;

        QuotationView.onVariantChange(itemId);
    },

    onVariantChange: (itemId) => {
        const row = document.getElementById(itemId);
        if (!row) return;

        const prodId = parseInt(row.querySelector('.item-product').value, 10);
        const prod = QuotationView.products.find(p => p.id === prodId);
        if (!prod) return;

        const variantSelect = row.querySelector('.item-variant');
        const selectedOpt = variantSelect.options[variantSelect.selectedIndex];
        const addPrice = selectedOpt && selectedOpt.dataset.add ? parseFloat(selectedOpt.dataset.add) : 0;

        const effectivePrice = prod.sales_price + addPrice;
        row.querySelector('.item-unit-price').value = effectivePrice.toFixed(2);

        QuotationView.recalculateTotals();
    },

    recalculateTotals: () => {
        let subtotal = 0;
        let totalTax = 0;

        QuotationView.lineItems.forEach(itemId => {
            const row = document.getElementById(itemId);
            if (!row) return;

            const qty = parseInt(row.querySelector('.item-quantity').value || 1, 10);
            const unitPrice = parseFloat(row.querySelector('.item-unit-price').value || 0);
            const taxRate = parseFloat(row.querySelector('.item-tax-rate').value || 0);

            const lineBase = qty * unitPrice;
            const lineTax = (lineBase * taxRate) / 100;
            const lineTotal = lineBase + lineTax;

            subtotal += lineBase;
            totalTax += lineTax;

            const lineTotalEl = row.querySelector('.item-line-total');
            if (lineTotalEl) lineTotalEl.textContent = `$${lineTotal.toFixed(2)}`;
        });

        const grandTotal = subtotal + totalTax;

        const subtotalEl = document.getElementById('live-subtotal');
        const taxEl = document.getElementById('live-tax');
        const grandEl = document.getElementById('live-grand-total');

        if (subtotalEl) subtotalEl.textContent = `$${subtotal.toFixed(2)}`;
        if (taxEl) taxEl.textContent = `$${totalTax.toFixed(2)}`;
        if (grandEl) grandEl.textContent = `$${grandTotal.toFixed(2)}`;
    },

    submitCreateQuotation: async (event) => {
        event.preventDefault();

        const customerSelect = document.getElementById('quote-customer');
        const customerId = parseInt(customerSelect.value, 10);
        const planId = document.getElementById('quote-plan').value ? parseInt(document.getElementById('quote-plan').value, 10) : null;
        const validUntil = document.getElementById('quote-valid-until').value;
        const notes = document.getElementById('quote-notes').value.trim();
        const terms = document.getElementById('quote-terms').value.trim();
        const isTemplate = document.getElementById('quote-is-template').checked;
        const templateName = document.getElementById('quote-template-name').value.trim();

        if (!customerId) {
            window.showToast('Please select a customer.', 'error');
            return;
        }

        const items = [];
        for (const itemId of QuotationView.lineItems) {
            const row = document.getElementById(itemId);
            if (!row) continue;
            const pId = parseInt(row.querySelector('.item-product').value, 10);
            const vId = row.querySelector('.item-variant').value ? parseInt(row.querySelector('.item-variant').value, 10) : null;
            const qty = parseInt(row.querySelector('.item-quantity').value, 10);
            const up = parseFloat(row.querySelector('.item-unit-price').value);
            const tr = parseFloat(row.querySelector('.item-tax-rate').value);

            if (!pId) continue;
            items.push({
                product_id: pId,
                variant_id: vId,
                quantity: qty,
                unit_price: up,
                tax_rate: tr
            });
        }

        if (items.length === 0) {
            window.showToast('At least one product line item is required.', 'error');
            return;
        }

        const payload = {
            customer_id: customerId,
            plan_id: planId,
            valid_until: validUntil,
            notes,
            terms_conditions: terms,
            is_template: isTemplate,
            template_name: templateName,
            items
        };

        const saveBtn = document.getElementById('save-quote-btn');
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        const res = await ApiClient.post('/quotations', payload);
        saveBtn.disabled = false;
        saveBtn.textContent = 'Create Draft Quotation';

        if (res.success) {
            window.showToast('Quotation created successfully!', 'success');
            QuotationView.closeModal();
            QuotationView.refresh();
        } else {
            window.showToast(res.error || 'Failed to create quotation.', 'error');
        }
    },

    // --- QUOTATION DETAILS & STATUS ACTIONS ---

    openDetailsModal: async (quotationId) => {
        const res = await ApiClient.get(`/quotations/${quotationId}`);
        if (!res.success) {
            window.showToast(res.error || 'Failed to load quotation details.', 'error');
            return;
        }

        const q = res.data;
        const isStaff = AuthManager.isStaff();

        const container = document.getElementById('quotation-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="QuotationView.closeModal(event)">
                <div class="modal-dialog modal-lg" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <div>
                            <h3>${q.quotation_number}</h3>
                            <span class="status-pill status-${q.status}">${q.status.toUpperCase()}</span>
                        </div>
                        <button class="modal-close" onclick="QuotationView.closeModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <!-- Details Grid -->
                        <div class="details-grid mb-3">
                            <div><strong>Customer:</strong> ${q.customer_name} (${q.customer_email || ''})</div>
                            <div><strong>Plan:</strong> ${q.plan_name || 'None / Ad-hoc'}</div>
                            <div><strong>Validity:</strong> Valid until ${q.valid_until} ${q.is_expired ? '<span class="text-danger">(EXPIRED)</span>' : ''}</div>
                            <div><strong>Created:</strong> ${q.created_at ? q.created_at.split('T')[0] : 'N/A'}</div>
                        </div>

                        <!-- Line items snapshot -->
                        <h4>Quotation Line Items</h4>
                        <table class="table mb-3">
                            <thead>
                                <tr>
                                    <th>Product</th>
                                    <th>Variant</th>
                                    <th>Qty</th>
                                    <th>Unit Price</th>
                                    <th>Tax Rate</th>
                                    <th>Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${q.items.map(it => `
                                    <tr>
                                        <td><strong>${it.product_name}</strong></td>
                                        <td>${it.variant_name ? `${it.variant_name} (${it.sku})` : '—'}</td>
                                        <td>${it.quantity}</td>
                                        <td>$${it.unit_price.toFixed(2)}</td>
                                        <td>${it.tax_rate}% ($${it.tax_amount.toFixed(2)})</td>
                                        <td><strong>$${it.total_price.toFixed(2)}</strong></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>

                        <!-- Totals Breakdown -->
                        <div class="quote-totals-box">
                            <div class="totals-row">
                                <span>Subtotal:</span>
                                <strong>$${q.subtotal.toFixed(2)}</strong>
                            </div>
                            <div class="totals-row">
                                <span>Tax Amount:</span>
                                <strong>$${q.tax_amount.toFixed(2)}</strong>
                            </div>
                            <div class="totals-row total-highlight">
                                <span>Total Amount:</span>
                                <strong>$${q.total_amount.toFixed(2)}</strong>
                            </div>
                        </div>

                        ${q.has_converted_subscription ? `
                            <div class="alert alert-success mt-3">
                                <strong>Converted:</strong> Active subscription exists for this quote: <code>${q.subscription_number}</code>
                            </div>
                        ` : ''}
                    </div>

                    <!-- Action Controls -->
                    <div class="modal-footer justify-between">
                        <div>
                            <button type="button" class="btn btn-outline btn-sm" onclick="QuotationView.promptSaveTemplate(${q.id})">Save as Template</button>
                        </div>
                        <div class="d-flex gap-2">
                            ${q.status === 'draft' && isStaff ? `
                                <button type="button" class="btn btn-secondary" onclick="QuotationView.sendQuote(${q.id})">Send to Customer</button>
                            ` : ''}

                            ${(q.status === 'draft' || q.status === 'sent') ? `
                                <button type="button" class="btn btn-success" onclick="QuotationView.confirmQuote(${q.id})">Confirm Quotation</button>
                                <button type="button" class="btn btn-danger" onclick="QuotationView.rejectQuote(${q.id})">Reject</button>
                            ` : ''}

                            ${q.status === 'confirmed' && !q.has_converted_subscription ? `
                                <button type="button" class="btn btn-primary" onclick="QuotationView.convertToSubscription(${q.id})">
                                    Convert to Subscription &rarr;
                                </button>
                            ` : ''}

                            <button type="button" class="btn btn-secondary" onclick="QuotationView.closeModal()">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    sendQuote: async (quoteId) => {
        const res = await ApiClient.post(`/quotations/${quoteId}/send`);
        if (res.success) {
            window.showToast('Quotation marked as sent.', 'success');
            QuotationView.openDetailsModal(quoteId);
            QuotationView.refresh();
        } else {
            window.showToast(res.error || 'Failed to send quotation.', 'error');
        }
    },

    confirmQuote: async (quoteId) => {
        const res = await ApiClient.post(`/quotations/${quoteId}/confirm`);
        if (res.success) {
            window.showToast('Quotation confirmed successfully!', 'success');
            QuotationView.openDetailsModal(quoteId);
            QuotationView.refresh();
        } else {
            window.showToast(res.error || 'Failed to confirm quotation.', 'error');
        }
    },

    rejectQuote: async (quoteId) => {
        if (!confirm('Are you sure you want to reject this quotation?')) return;
        const res = await ApiClient.post(`/quotations/${quoteId}/reject`);
        if (res.success) {
            window.showToast('Quotation rejected.', 'info');
            QuotationView.openDetailsModal(quoteId);
            QuotationView.refresh();
        } else {
            window.showToast(res.error || 'Failed to reject quotation.', 'error');
        }
    },

    convertToSubscription: async (quoteId) => {
        if (!confirm('Convert this confirmed quotation into an active recurring subscription? Line items and agreed pricing snapshots will be locked.')) return;

        const res = await ApiClient.post(`/subscriptions/convert-quotation/${quoteId}`);
        if (res.success) {
            window.showToast('Quotation converted to Subscription successfully!', 'success');
            QuotationView.closeModal();
            window.Router.navigate('/subscriptions');
        } else {
            window.showToast(res.error || 'Failed to convert quotation.', 'error');
        }
    },

    promptSaveTemplate: async (quoteId) => {
        const templateName = prompt('Enter a name for this reusable quotation template:');
        if (!templateName) return;

        const res = await ApiClient.post(`/quotations/${quoteId}/save-as-template`, { template_name: templateName });
        if (res.success) {
            window.showToast('Template saved successfully!', 'success');
        } else {
            window.showToast(res.error || 'Failed to save template.', 'error');
        }
    },

    // --- REUSABLE TEMPLATES MODAL ---

    openTemplatesModal: async () => {
        const res = await ApiClient.get('/quotations/templates');
        const templates = res.success ? res.data : [];

        const container = document.getElementById('quotation-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="QuotationView.closeModal(event)">
                <div class="modal-dialog modal-lg" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Reusable Quotation Templates</h3>
                        <button class="modal-close" onclick="QuotationView.closeModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        ${templates.length === 0 ? '<p class="empty-state">No templates created yet. You can save any quotation as a template.</p>' : `
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Template Name</th>
                                        <th>Base Plan</th>
                                        <th>Items</th>
                                        <th>Estimated Amount</th>
                                        <th>Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${templates.map(t => `
                                        <tr>
                                            <td><strong>${t.template_name || t.quotation_number}</strong></td>
                                            <td>${t.plan_name || 'Standard'}</td>
                                            <td>${t.items ? t.items.length : 0} item(s)</td>
                                            <td><strong>$${t.total_amount.toFixed(2)}</strong></td>
                                            <td>
                                                <button class="btn btn-sm btn-primary" onclick="QuotationView.useTemplate(${t.id})">Use Template</button>
                                            </td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="QuotationView.closeModal()">Close</button>
                    </div>
                </div>
            </div>
        `;
    },

    useTemplate: async (templateId) => {
        const res = await ApiClient.get(`/quotations/${templateId}`);
        if (res.success) {
            QuotationView.closeModal();
            QuotationView.openCreateModal(res.data);
        }
    },

    closeModal: () => {
        const container = document.getElementById('quotation-modal-container');
        if (container) container.innerHTML = '';
    },

    refresh: async () => {
        const res = await ApiClient.get('/quotations');
        QuotationView.quotations = res.success ? res.data : [];
        const tableContainer = document.getElementById('quotes-table-container');
        if (tableContainer) tableContainer.innerHTML = QuotationView.renderTable(QuotationView.quotations);
    }
};

window.QuotationView = QuotationView;

