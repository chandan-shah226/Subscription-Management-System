/**
 * Discount Management View Component (Module 5)
 * =============================================
 * Admin-managed discount engine with:
 * - Summary KPI cards (Total Rules, Active, Expired, Exhausted, Total Redemptions)
 * - Filtering (Search, Discount Type, Status, Scope)
 * - Interactive rule table with badges and toggle controls
 * - Modal for Creating and Editing discount rules with multi-condition thresholds
 * - Product scope picker
 */

const DiscountView = {
    discounts: [],
    stats: {},
    products: [],
    pagination: {},
    currentDiscount: null,

    render: async () => {
        let discRes, statsRes, prodRes;
        try {
            [discRes, statsRes, prodRes] = await Promise.all([
                ApiClient.get('/discounts'),
                ApiClient.get('/discounts/stats'),
                ApiClient.get('/products', { active_only: true })
            ]);
        } catch (e) {
            console.error("Failed to fetch discounts initial data:", e);
            discRes = { success: false, error: e.message };
            statsRes = { success: false };
            prodRes = { success: false };
        }

        if (!discRes || !discRes.success) {
            return `
                <div class="view-header">
                    <div>
                        <h2>Discounts & Promotional Rules</h2>
                        <p class="text-muted">Manage promotional codes, percentage and fixed discounts, minimum thresholds, and scope policies</p>
                    </div>
                </div>
                <div class="card p-4 my-4" style="text-align: center; border: 1px solid #fee2e2; background: #fff; border-radius: 8px; padding: 3rem 1.5rem; margin-top: 1.5rem;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
                    <h3 style="color: #991b1b; margin-bottom: 0.5rem;">Unable to load discounts</h3>
                    <p class="text-muted" style="margin-bottom: 1.5rem;">${discRes?.error || 'A network or server error occurred while retrieving discount rules.'}</p>
                    <button class="btn btn-primary" onclick="Router.handleRouting()">🔄 Retry Loading</button>
                </div>
            `;
        }

        const rawDiscounts = discRes.discounts !== undefined ? discRes.discounts : (discRes.data !== undefined ? discRes.data : []);
        DiscountView.discounts = Array.isArray(rawDiscounts) ? rawDiscounts : [];
        DiscountView.pagination = discRes.pagination || {};
        DiscountView.stats = (statsRes && statsRes.success && statsRes.stats) ? statsRes.stats : ((statsRes && statsRes.data) || {});
        DiscountView.products = (prodRes && prodRes.success) ? (prodRes.products || (Array.isArray(prodRes.data) ? prodRes.data : [])) : [];

        const stats = DiscountView.stats;
        const isAdmin = AuthManager.isAdmin();

        return `
            <div class="view-header">
                <div>
                    <h2>Discounts & Promotional Rules</h2>
                    <p class="text-muted">Manage promotional codes, percentage and fixed discounts, minimum thresholds, and scope policies</p>
                </div>
                <div class="view-actions">
                    ${isAdmin ? `
                        <button class="btn btn-primary btn-sm" onclick="DiscountView.openCreateModal()">+ Create Discount Rule</button>
                    ` : ''}
                </div>
            </div>

            <!-- KPI Metric Cards -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <span class="kpi-title">Total Rules</span>
                    <span class="kpi-value">${stats.total_discounts || 0}</span>
                    <span class="kpi-subtext text-muted">Configured Discount Rules</span>
                </div>
                <div class="kpi-card kpi-paid">
                    <span class="kpi-title">Active Rules</span>
                    <span class="kpi-value text-success">${stats.active_discounts || 0}</span>
                    <span class="kpi-subtext text-success">Available for Checkout</span>
                </div>
                <div class="kpi-card kpi-overdue">
                    <span class="kpi-title">Expired Rules</span>
                    <span class="kpi-value text-danger">${stats.expired_discounts || 0}</span>
                    <span class="kpi-subtext text-muted">Past Validity Window</span>
                </div>
                <div class="kpi-card kpi-outstanding">
                    <span class="kpi-title">Exhausted</span>
                    <span class="kpi-value text-warning">${stats.exhausted_discounts || 0}</span>
                    <span class="kpi-subtext text-muted">Usage Limit Reached</span>
                </div>
                <div class="kpi-card">
                    <span class="kpi-title">Total Redemptions</span>
                    <span class="kpi-value" style="color:#714B67;">${stats.total_redemptions || 0}</span>
                    <span class="kpi-subtext text-muted">Times Applied to Invoices</span>
                </div>
            </div>

            <!-- Toolbar & Search Filters -->
            <div class="toolbar card-body" style="background:#fff; border-radius:8px; margin-bottom:1.5rem; border:1px solid #e2e8f0; padding:1rem 1.25rem;">
                <div class="toolbar-row" style="display:flex; flex-wrap:wrap; gap:0.75rem; align-items:center; width:100%;">
                    <div style="flex: 2; min-width: 220px;">
                        <input type="text" id="disc-search" class="form-control" placeholder="Search by code or description..." oninput="DiscountView.handleFilterChange()">
                    </div>
                    <div style="flex: 1; min-width: 140px;">
                        <select id="disc-type-filter" class="form-control" onchange="DiscountView.handleFilterChange()">
                            <option value="">All Types</option>
                            <option value="percentage">Percentage (%)</option>
                            <option value="fixed">Fixed Amount (₹)</option>
                        </select>
                    </div>
                    <div style="flex: 1; min-width: 140px;">
                        <select id="disc-status-filter" class="form-control" onchange="DiscountView.handleFilterChange()">
                            <option value="">All Statuses</option>
                            <option value="active">Active</option>
                            <option value="expired">Expired</option>
                            <option value="exhausted">Exhausted</option>
                            <option value="inactive">Inactive</option>
                        </select>
                    </div>
                    <div style="flex: 1; min-width: 150px;">
                        <select id="disc-scope-filter" class="form-control" onchange="DiscountView.handleFilterChange()">
                            <option value="">All Scopes</option>
                            <option value="all">Global (All Items)</option>
                            <option value="subscription">Subscription Only</option>
                            <option value="product">Specific Products</option>
                        </select>
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="DiscountView.resetFilters()">Reset</button>
                </div>
            </div>

            <!-- Discounts Table Container -->
            <div id="discounts-table-container">
                ${DiscountView.renderTable(DiscountView.discounts)}
            </div>

            <!-- Modal Container -->
            <div id="discount-modal-container"></div>
        `;
    },

    renderTable: (discounts) => {
        const list = Array.isArray(discounts) ? discounts : [];
        if (list.length === 0) {
            return `
                <div class="empty-state card" style="padding:3rem; text-align:center; background:#fff; border-radius:8px; border:1px solid #e2e8f0;">
                    <div style="font-size:42px; margin-bottom:0.75rem;">🏷️</div>
                    <h3 style="color:#714B67; margin-bottom:0.5rem;">No Discount Rules Found</h3>
                    <p class="text-muted">Create promotional discounts with percentage or fixed deductions to reward subscribers.</p>
                </div>
            `;
        }

        return `
            <div class="table-responsive card" style="background:#fff; border-radius:8px; border:1px solid #e2e8f0; overflow:hidden;">
                <table class="table" style="width:100%; margin:0; border-collapse:collapse;">
                    <thead>
                        <tr style="background:#f8fafc; border-bottom:1px solid #e2e8f0;">
                            <th style="padding:12px 16px; text-align:left;">Code</th>
                            <th style="padding:12px 16px; text-align:left;">Description</th>
                            <th style="padding:12px 16px; text-align:left;">Discount</th>
                            <th style="padding:12px 16px; text-align:left;">Scope</th>
                            <th style="padding:12px 16px; text-align:left;">Thresholds</th>
                            <th style="padding:12px 16px; text-align:left;">Validity & Usage</th>
                            <th style="padding:12px 16px; text-align:center;">Status</th>
                            <th style="padding:12px 16px; text-align:right;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${list.map(d => {
                            let statusBadge = '<span class="badge" style="background:#dcfce7; color:#15803d;">ACTIVE</span>';
                            if (!d.is_active) {
                                statusBadge = '<span class="badge" style="background:#f1f5f9; color:#475569;">INACTIVE</span>';
                            } else if (d.is_expired) {
                                statusBadge = '<span class="badge" style="background:#fee2e2; color:#b91c1c;">EXPIRED</span>';
                            } else if (d.is_exhausted) {
                                statusBadge = '<span class="badge" style="background:#fef3c7; color:#92400e;">EXHAUSTED</span>';
                            }

                            const valDisplay = d.discount_type === 'percentage'
                                ? `<strong style="color:#714B67;">${d.value}%</strong> off`
                                : `<strong style="color:#15803d;">₹${d.value.toFixed(2)}</strong> flat`;

                            const scopeLabel = d.scope === 'subscription'
                                ? '<span class="badge" style="background:#e0f2fe; color:#0369a1;">Subscription</span>'
                                : d.scope === 'product'
                                ? `<span class="badge" style="background:#fef3c7; color:#92400e;">Products (${(d.products || []).length})</span>`
                                : '<span class="badge" style="background:#f1f5f9; color:#475569;">Global</span>';

                            return `
                                <tr style="border-bottom:1px solid #f1f5f9;">
                                    <td style="padding:12px 16px;">
                                        <span class="badge" style="background:#f3e8ff; color:#6b21a8; font-weight:700; font-size:12px; letter-spacing:0.5px;">
                                            ${d.code}
                                        </span>
                                    </td>
                                    <td style="padding:12px 16px; max-width:220px;">
                                        <div style="font-weight:500;">${d.description || '—'}</div>
                                    </td>
                                    <td style="padding:12px 16px;">${valDisplay}</td>
                                    <td style="padding:12px 16px;">${scopeLabel}</td>
                                    <td style="padding:12px 16px; font-size:12px; color:#64748b;">
                                        <div>Min: <strong>₹${(d.min_purchase || 0).toFixed(2)}</strong></div>
                                        <div>Qty: <strong>${d.min_quantity || 1}</strong></div>
                                    </td>
                                    <td style="padding:12px 16px; font-size:12px;">
                                        <div>Used: <strong>${d.times_used}</strong> / ${d.usage_limit || '∞'}</div>
                                        <div class="text-muted">${d.start_date || '—'} to ${d.end_date || 'Ongoing'}</div>
                                    </td>
                                    <td style="padding:12px 16px; text-align:center;">
                                        ${statusBadge}
                                    </td>
                                    <td style="padding:12px 16px; text-align:right;">
                                        <div style="display:flex; gap:0.25rem; justify-content:flex-end;">
                                            <button class="btn btn-secondary btn-sm" onclick="DiscountView.openEditModal(${d.id})">Edit</button>
                                            <button class="btn ${d.is_active ? 'btn-danger' : 'btn-success'} btn-sm" onclick="DiscountView.toggleDiscount(${d.id})">
                                                ${d.is_active ? 'Deactivate' : 'Activate'}
                                            </button>
                                        </div>
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
        const search = document.getElementById('disc-search')?.value || '';
        const discType = document.getElementById('disc-type-filter')?.value || '';
        const status = document.getElementById('disc-status-filter')?.value || '';
        const scope = document.getElementById('disc-scope-filter')?.value || '';

        const params = {};
        if (search) params.search = search;
        if (discType) params.discount_type = discType;
        if (status) params.status = status;
        if (scope) params.scope = scope;

        const res = await ApiClient.get('/discounts', params);
        if (res.success) {
            const rawDiscounts = res.discounts !== undefined ? res.discounts : (res.data !== undefined ? res.data : []);
            DiscountView.discounts = Array.isArray(rawDiscounts) ? rawDiscounts : [];
            const container = document.getElementById('discounts-table-container');
            if (container) {
                container.innerHTML = DiscountView.renderTable(DiscountView.discounts);
            }
        }
    },

    resetFilters: async () => {
        if (document.getElementById('disc-search')) document.getElementById('disc-search').value = '';
        if (document.getElementById('disc-type-filter')) document.getElementById('disc-type-filter').value = '';
        if (document.getElementById('disc-status-filter')) document.getElementById('disc-status-filter').value = '';
        if (document.getElementById('disc-scope-filter')) document.getElementById('disc-scope-filter').value = '';
        await DiscountView.handleFilterChange();
    },

    openCreateModal: () => {
        DiscountView.currentDiscount = null;
        DiscountView.renderFormModal('Create Discount Rule');
    },

    openEditModal: async (discountId) => {
        const res = await ApiClient.get(`/discounts/${discountId}`);
        if (!res.success) {
            alert(res.error || 'Failed to fetch discount details');
            return;
        }
        DiscountView.currentDiscount = res.discount;
        DiscountView.renderFormModal(`Edit Discount Rule (${res.discount.code})`, res.discount);
    },

    renderFormModal: (title, discount = null) => {
        const isEdit = !!discount;
        const products = DiscountView.products;
        const attachedProdIds = (discount && discount.products) ? discount.products.map(p => p.id) : [];

        const modalHtml = `
            <div class="modal-backdrop" onclick="DiscountView.closeModal(event)">
                <div class="modal" style="max-width:650px; width:90%; max-height:90vh; overflow-y:auto;" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3 style="margin:0; color:#714B67;">${title}</h3>
                        <button class="btn btn-secondary btn-sm" onclick="DiscountView.closeModal()">✕</button>
                    </div>

                    <form id="discount-form" onsubmit="DiscountView.saveDiscount(event, ${isEdit ? discount.id : 'null'})">
                        <div class="modal-body">
                            <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1rem;">
                                <div class="form-group">
                                    <label>Discount Code *</label>
                                    <input type="text" id="df-code" class="form-control" style="text-transform:uppercase; font-weight:700;" placeholder="e.g. SUMMER25" value="${isEdit ? discount.code : ''}" required ${isEdit ? 'readonly' : ''}>
                                    <small class="text-muted">Unique identifier for checkout.</small>
                                </div>
                                <div class="form-group">
                                    <label>Discount Type *</label>
                                    <select id="df-type" class="form-control" onchange="DiscountView.updateValueLabel()" required>
                                        <option value="percentage" ${isEdit && discount.discount_type === 'percentage' ? 'selected' : ''}>Percentage (%)</option>
                                        <option value="fixed" ${isEdit && discount.discount_type === 'fixed' ? 'selected' : ''}>Fixed Amount (₹)</option>
                                    </select>
                                </div>
                            </div>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Description</label>
                                <input type="text" id="df-desc" class="form-control" placeholder="Promotional campaign description..." value="${isEdit ? (discount.description || '') : ''}">
                            </div>

                            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; margin-bottom:1rem;">
                                <div class="form-group">
                                    <label id="df-val-label">Value (% or ₹) *</label>
                                    <input type="number" step="0.01" min="0.01" id="df-value" class="form-control" value="${isEdit ? discount.value : ''}" required>
                                </div>
                                <div class="form-group">
                                    <label>Min Purchase (₹)</label>
                                    <input type="number" step="0.01" min="0" id="df-min-purchase" class="form-control" value="${isEdit ? discount.min_purchase : '0.00'}">
                                </div>
                                <div class="form-group">
                                    <label>Min Quantity</label>
                                    <input type="number" min="1" id="df-min-qty" class="form-control" value="${isEdit ? discount.min_quantity : '1'}">
                                </div>
                            </div>

                            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:1rem; margin-bottom:1rem;">
                                <div class="form-group">
                                    <label>Start Date</label>
                                    <input type="date" id="df-start-date" class="form-control" value="${isEdit ? (discount.start_date || '') : ''}">
                                </div>
                                <div class="form-group">
                                    <label>End Date</label>
                                    <input type="date" id="df-end-date" class="form-control" value="${isEdit ? (discount.end_date || '') : ''}">
                                </div>
                                <div class="form-group">
                                    <label>Usage Limit</label>
                                    <input type="number" min="1" id="df-usage-limit" class="form-control" placeholder="Optional max uses" value="${isEdit ? (discount.usage_limit || '') : ''}">
                                </div>
                            </div>

                            <div class="form-group" style="margin-bottom:1rem;">
                                <label>Rule Scope *</label>
                                <select id="df-scope" class="form-control" onchange="DiscountView.toggleProductSelector()" required>
                                    <option value="all" ${isEdit && discount.scope === 'all' ? 'selected' : ''}>Global (Applies to all products & invoices)</option>
                                    <option value="subscription" ${isEdit && discount.scope === 'subscription' ? 'selected' : ''}>Subscription Billing Only</option>
                                    <option value="product" ${isEdit && discount.scope === 'product' ? 'selected' : ''}>Specific Products Only</option>
                                </select>
                            </div>

                            <!-- Specific Product Checkboxes -->
                            <div id="product-selector-container" style="display:${isEdit && discount.scope === 'product' ? 'block' : 'none'}; background:#f8fafc; padding:1rem; border-radius:6px; margin-bottom:1rem; border:1px solid #e2e8f0; max-height:160px; overflow-y:auto;">
                                <label style="font-weight:600; margin-bottom:0.5rem; display:block;">Select Eligible Products:</label>
                                ${products.map(p => `
                                    <div style="margin-bottom:4px;">
                                        <label style="font-weight:normal; font-size:13px; display:flex; align-items:center; gap:6px;">
                                            <input type="checkbox" name="product_ids" value="${p.id}" ${attachedProdIds.includes(p.id) ? 'checked' : ''}>
                                            ${p.name} (${p.code}) — ₹${p.sales_price}
                                        </label>
                                    </div>
                                `).join('')}
                            </div>
                        </div>

                        <div class="modal-footer" style="display:flex; justify-content:flex-end; gap:0.5rem;">
                            <button type="button" class="btn btn-secondary" onclick="DiscountView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">${isEdit ? 'Update Rule' : 'Save Rule'}</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        document.getElementById('discount-modal-container').innerHTML = modalHtml;
    },

    updateValueLabel: () => {
        const type = document.getElementById('df-type')?.value;
        const label = document.getElementById('df-val-label');
        if (label) {
            label.textContent = type === 'percentage' ? 'Percentage (e.g. 15%) *' : 'Fixed Amount (₹) *';
        }
    },

    toggleProductSelector: () => {
        const scope = document.getElementById('df-scope')?.value;
        const container = document.getElementById('product-selector-container');
        if (container) {
            container.style.display = scope === 'product' ? 'block' : 'none';
        }
    },

    saveDiscount: async (event, discountId) => {
        event.preventDefault();
        const code = document.getElementById('df-code').value.trim().toUpperCase();
        const discountType = document.getElementById('df-type').value;
        const description = document.getElementById('df-desc').value.trim();
        const value = parseFloat(document.getElementById('df-value').value);
        const minPurchase = parseFloat(document.getElementById('df-min-purchase').value) || 0;
        const minQuantity = parseInt(document.getElementById('df-min-qty').value) || 1;
        const startDate = document.getElementById('df-start-date').value || null;
        const endDate = document.getElementById('df-end-date').value || null;
        const usageLimit = document.getElementById('df-usage-limit').value ? parseInt(document.getElementById('df-usage-limit').value) : null;
        const scope = document.getElementById('df-scope').value;

        const productIds = [];
        if (scope === 'product') {
            document.querySelectorAll('input[name="product_ids"]:checked').forEach(cb => {
                productIds.push(parseInt(cb.value));
            });
            if (productIds.length === 0) {
                alert('Please select at least one eligible product for product-scoped discount.');
                return;
            }
        }

        const payload = {
            code,
            discount_type: discountType,
            description,
            value,
            min_purchase: minPurchase,
            min_quantity: minQuantity,
            start_date: startDate,
            end_date: endDate,
            usage_limit: usageLimit,
            scope,
            product_ids: productIds
        };

        const res = discountId
            ? await ApiClient.put(`/discounts/${discountId}`, payload)
            : await ApiClient.post('/discounts', payload);

        if (res.success) {
            alert(res.message || 'Discount rule saved successfully!');
            DiscountView.closeModal();
            Router.handleRouting();
        } else {
            alert(res.error || 'Failed to save discount rule');
        }
    },

    toggleDiscount: async (discountId) => {
        const res = await ApiClient.post(`/discounts/${discountId}/toggle`);
        if (res.success) {
            DiscountView.handleFilterChange();
        } else {
            alert(res.error || 'Failed to toggle discount state');
        }
    },

    closeModal: (event) => {
        if (!event || event.target.classList.contains('modal-backdrop')) {
            const container = document.getElementById('discount-modal-container');
            if (container) container.innerHTML = '';
        }
    }
};

window.DiscountView = DiscountView;
