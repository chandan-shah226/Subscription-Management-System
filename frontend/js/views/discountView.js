/**
 * Discount Management View Component (Module 5)
 * ==============================================
 * Admin-only interface for creating and monitoring promotional coupons,
 * seat-volume price breaks, validity dates, and redemption limits.
 */

const DiscountView = {
    discounts: [],
    products: [],

    render: async () => {
        if (!AuthManager.isAdmin()) {
            return `<div class="alert alert-danger">Access forbidden: Administrator privileges required to manage discount rules.</div>`;
        }

        const [discRes, prodRes] = await Promise.all([
            ApiClient.get('/discounts'),
            ApiClient.get('/products', { active_only: true })
        ]);

        DiscountView.discounts = discRes.success ? discRes.data : [];
        DiscountView.products = prodRes.success ? prodRes.data : [];

        return `
            <div class="view-header">
                <div>
                    <h2>Discount Rules & Coupons</h2>
                    <p class="text-muted">Configure seat-volume discounts, percentage/fixed promo coupons, date validity, and usage limits</p>
                </div>
                <div>
                    <button class="btn btn-primary" onclick="DiscountView.openCreateModal()">+ Create Discount Rule</button>
                </div>
            </div>

            <!-- Discount Rules Table Card -->
            <div class="card">
                <div class="card-body">
                    ${DiscountView.renderTable(DiscountView.discounts)}
                </div>
            </div>

            <!-- Modal Container -->
            <div id="discount-modal-container"></div>
        `;
    },

    renderTable: (discounts) => {
        if (!discounts || discounts.length === 0) {
            return `<p class="empty-state">No discount rules registered yet. Click "+ Create Discount Rule" to set one up.</p>`;
        }

        return `
            <table class="table">
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Name</th>
                        <th>Benefit</th>
                        <th>Conditions</th>
                        <th>Validity Period</th>
                        <th>Usage / Limit</th>
                        <th>Scope</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${discounts.map(d => {
                        const statusClass = d.status_label === 'Active' ? 'status-active'
                            : d.status_label === 'Expired' ? 'status-closed'
                            : 'status-draft';

                        return `
                            <tr>
                                <td><span class="badge badge-info font-bold">${d.code}</span></td>
                                <td><strong>${d.name}</strong></td>
                                <td>
                                    <strong class="text-success">
                                        ${d.discount_type === 'percentage' ? `${d.value}% Off` : `$${d.value.toFixed(2)} Off`}
                                    </strong>
                                </td>
                                <td>
                                    <small>
                                        ${d.min_quantity ? `Min ${d.min_quantity} seats<br>` : ''}
                                        ${d.min_amount ? `Min spend $${d.min_amount.toFixed(2)}` : ''}
                                        ${!d.min_quantity && !d.min_amount ? 'No minimum' : ''}
                                    </small>
                                </td>
                                <td>
                                    <small class="text-muted">
                                        ${d.start_date || 'Anytime'} &rarr; ${d.end_date || 'Ongoing'}
                                    </small>
                                </td>
                                <td>
                                    <strong>${d.used_count}</strong> / ${d.max_uses ? d.max_uses : '∞'} uses
                                </td>
                                <td><span class="badge badge-primary">${d.scope.toUpperCase()}</span></td>
                                <td>
                                    <span class="status-pill ${statusClass}">${d.status_label.toUpperCase()}</span>
                                </td>
                                <td>
                                    <button class="btn btn-sm ${d.is_active ? 'btn-danger' : 'btn-success'}" 
                                            onclick="DiscountView.toggleDiscount(${d.id})">
                                        ${d.is_active ? 'Deactivate' : 'Activate'}
                                    </button>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        `;
    },

    toggleDiscount: async (discountId) => {
        const res = await ApiClient.post(`/discounts/${discountId}/toggle`, {});
        if (res.success) {
            window.showToast(res.message || 'Status updated', 'success');
            const content = await DiscountView.render();
            const container = document.getElementById('view-container');
            if (container) container.innerHTML = content;
        } else {
            window.showToast(res.error || 'Failed to update discount', 'error');
        }
    },

    openCreateModal: () => {
        const container = document.getElementById('discount-modal-container');
        if (!container) return;

        const products = DiscountView.products;

        container.innerHTML = `
            <div class="modal-overlay" onclick="DiscountView.closeModal(event)">
                <div class="modal-card modal-md" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Create New Discount Rule</h3>
                        <button class="modal-close" onclick="DiscountView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="DiscountView.handleCreateSubmit(event)">
                        <div class="modal-body">
                            <div class="form-row">
                                <div class="form-group">
                                    <label for="disc-name">Rule / Promotion Name *</label>
                                    <input type="text" id="disc-name" class="form-control" required placeholder="e.g. Volume Tier Discount">
                                </div>
                                <div class="form-group">
                                    <label for="disc-code">Coupon / Promo Code *</label>
                                    <input type="text" id="disc-code" class="form-control" required placeholder="e.g. VOLUME10, SEATS5" style="text-transform:uppercase;">
                                </div>
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label for="disc-type">Discount Type *</label>
                                    <select id="disc-type" class="form-control" required>
                                        <option value="percentage">Percentage Off (%)</option>
                                        <option value="fixed">Fixed Amount Off ($)</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label for="disc-value">Discount Value *</label>
                                    <input type="number" id="disc-value" class="form-control" step="0.01" min="0.01" required placeholder="e.g. 15 for 15% or 50.00">
                                </div>
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label for="disc-min-qty">Minimum Quantity / Seats</label>
                                    <input type="number" id="disc-min-qty" class="form-control" min="1" placeholder="e.g. 5 seats">
                                    <small class="form-hint">Only triggers if order has at least this many units.</small>
                                </div>
                                <div class="form-group">
                                    <label for="disc-min-amt">Minimum Purchase Spend ($)</label>
                                    <input type="number" id="disc-min-amt" class="form-control" step="0.01" min="0" placeholder="e.g. 500.00">
                                </div>
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label for="disc-start-date">Valid From Date</label>
                                    <input type="date" id="disc-start-date" class="form-control">
                                </div>
                                <div class="form-group">
                                    <label for="disc-end-date">Valid Until Date</label>
                                    <input type="date" id="disc-end-date" class="form-control">
                                </div>
                            </div>

                            <div class="form-row">
                                <div class="form-group">
                                    <label for="disc-max-uses">Max Usage Redemptions</label>
                                    <input type="number" id="disc-max-uses" class="form-control" min="1" placeholder="Leave blank for unlimited">
                                </div>
                                <div class="form-group">
                                    <label for="disc-scope">Discount Scope</label>
                                    <select id="disc-scope" class="form-control" onchange="DiscountView.onScopeChange()">
                                        <option value="subscription">Whole Subscription / Order</option>
                                        <option value="product">Specific Product Line</option>
                                    </select>
                                </div>
                            </div>

                            <div class="form-group d-none" id="product-select-group">
                                <label for="disc-prod-id">Target Product</label>
                                <select id="disc-prod-id" class="form-control">
                                    <option value="">-- Select Product --</option>
                                    ${products.map(p => `<option value="${p.id}">${p.name} (${p.code})</option>`).join('')}
                                </select>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="DiscountView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Create Discount Rule</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    onScopeChange: () => {
        const scope = document.getElementById('disc-scope').value;
        const group = document.getElementById('product-select-group');
        if (group) {
            group.className = scope === 'product' ? 'form-group' : 'form-group d-none';
        }
    },

    handleCreateSubmit: async (event) => {
        event.preventDefault();
        const data = {
            name: document.getElementById('disc-name').value.trim(),
            code: document.getElementById('disc-code').value.trim().toUpperCase(),
            discount_type: document.getElementById('disc-type').value,
            value: parseFloat(document.getElementById('disc-value').value),
            min_quantity: document.getElementById('disc-min-qty').value || null,
            min_amount: document.getElementById('disc-min-amt').value || null,
            start_date: document.getElementById('disc-start-date').value || null,
            end_date: document.getElementById('disc-end-date').value || null,
            max_uses: document.getElementById('disc-max-uses').value || null,
            scope: document.getElementById('disc-scope').value,
            product_id: document.getElementById('disc-prod-id')?.value || null
        };

        const res = await ApiClient.post('/discounts', data);
        if (res.success) {
            window.showToast(`Discount rule '${data.code}' created successfully!`, 'success');
            DiscountView.closeModal();
            const content = await DiscountView.render();
            const container = document.getElementById('view-container');
            if (container) container.innerHTML = content;
        } else {
            window.showToast(res.error || 'Failed to create discount', 'error');
        }
    },

    closeModal: (event) => {
        if (event && event.target && !event.target.classList.contains('modal-overlay')) return;
        const container = document.getElementById('discount-modal-container');
        if (container) container.innerHTML = '';
    }
};

window.DiscountView = DiscountView;
