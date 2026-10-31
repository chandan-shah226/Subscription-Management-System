/**
 * Product & Plan Management View Component (Module 2)
 * ===================================================
 * Complete interface for Products, Variants with pricing modifiers,
 * Subscription Plans, Frequencies, and Lifecycle Policies.
 */

const ProductPlanView = {
    products: [],
    plans: [],
    currentTab: 'products',

    render: async () => {
        const [prodRes, planRes] = await Promise.all([
            ApiClient.get('/products'),
            ApiClient.get('/plans')
        ]);

        ProductPlanView.products = prodRes.success ? prodRes.data : [];
        ProductPlanView.plans = planRes.success ? planRes.data : [];

        return `
            <div class="view-header">
                <div>
                    <h2>Products & Subscription Plans</h2>
                    <p class="text-muted">Manage product catalog, brand variants, recurring billing plans, and policies</p>
                </div>
                <div>
                    ${AuthManager.isStaff() ? `
                        <button class="btn btn-primary" onclick="ProductPlanView.openCreateItemModal()">
                            ${ProductPlanView.currentTab === 'products' ? '+ Add Product' : '+ Add Subscription Plan'}
                        </button>
                    ` : ''}
                </div>
            </div>

            <!-- Tab Switcher -->
            <div class="tabs-container">
                <button class="tab-btn ${ProductPlanView.currentTab === 'products' ? 'active' : ''}" onclick="ProductPlanView.switchTab('products')">
                    Products & Variants (${ProductPlanView.products.length})
                </button>
                <button class="tab-btn ${ProductPlanView.currentTab === 'plans' ? 'active' : ''}" onclick="ProductPlanView.switchTab('plans')">
                    Subscription Plans (${ProductPlanView.plans.length})
                </button>
            </div>

            <!-- Tab Content Container -->
            <div id="tab-content" class="card">
                <div class="card-body">
                    ${ProductPlanView.currentTab === 'products' ? ProductPlanView.renderProductsTable() : ProductPlanView.renderPlansTable()}
                </div>
            </div>

            <!-- Dynamic Modal Container -->
            <div id="catalog-modal-container"></div>
        `;
    },

    switchTab: (tabName) => {
        ProductPlanView.currentTab = tabName;
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        if (event && event.target) event.target.classList.add('active');
        
        const container = document.getElementById('tab-content');
        if (container) {
            container.querySelector('.card-body').innerHTML = 
                tabName === 'products' ? ProductPlanView.renderProductsTable() : ProductPlanView.renderPlansTable();
        }
        
        // Update header button text
        const addBtn = document.querySelector('.view-header button');
        if (addBtn) {
            addBtn.textContent = tabName === 'products' ? '+ Add Product' : '+ Add Subscription Plan';
        }
    },

    // --- PRODUCTS TABLE & OPERATIONS ---

    renderProductsTable: () => {
        if (ProductPlanView.products.length === 0) {
            return `<p class="empty-state">No products registered yet. Click "+ Add Product" to create one.</p>`;
        }

        return `
            <table class="table">
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Sales Price</th>
                        <th>Tax Rate</th>
                        <th>Variants</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${ProductPlanView.products.map(p => `
                        <tr>
                            <td><code>${p.code}</code></td>
                            <td>
                                <strong>${p.name}</strong>
                                ${p.description ? `<div class="text-sm text-muted">${p.description}</div>` : ''}
                            </td>
                            <td><span class="badge ${p.product_type === 'service' ? 'badge-primary' : 'badge-secondary'}">${p.product_type}</span></td>
                            <td><strong>$${p.sales_price.toFixed(2)}</strong></td>
                            <td>${p.tax_rate}%</td>
                            <td>
                                <button class="btn btn-sm btn-outline" onclick="ProductPlanView.openVariantsModal(${p.id})">
                                    ${p.variants.length} Variant(s) &rarr;
                                </button>
                            </td>
                            <td>
                                <span class="status-pill status-${p.is_active ? 'active' : 'closed'}">
                                    ${p.is_active ? 'Active' : 'Inactive'}
                                </span>
                            </td>
                            <td>
                                ${AuthManager.isStaff() ? `
                                    <button class="btn btn-sm btn-secondary" onclick="ProductPlanView.openEditProductModal(${p.id})">Edit</button>
                                    <button class="btn btn-sm ${p.is_active ? 'btn-danger' : 'btn-success'}" onclick="ProductPlanView.toggleProductActive(${p.id})">
                                        ${p.is_active ? 'Deactivate' : 'Activate'}
                                    </button>
                                ` : '—'}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    openCreateProductModal: () => {
        const container = document.getElementById('catalog-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="ProductPlanView.closeModal(event)">
                <div class="modal-dialog" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Add New Product</h3>
                        <button class="modal-close" onclick="ProductPlanView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="ProductPlanView.submitProduct(event)">
                        <div class="modal-body">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Product Name *</label>
                                    <input type="text" id="prod-name" class="form-control" required placeholder="e.g. Cloud Server Hosting">
                                </div>
                                <div class="form-group">
                                    <label>Product Code *</label>
                                    <input type="text" id="prod-code" class="form-control" required placeholder="e.g. PROD-CLOUD-01">
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Product Type *</label>
                                    <select id="prod-type" class="form-control">
                                        <option value="service" selected>Service</option>
                                        <option value="physical">Physical Product</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Sales Price ($) *</label>
                                    <input type="number" step="0.01" min="0" id="prod-sales-price" class="form-control" required placeholder="1000.00">
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Cost Price ($)</label>
                                    <input type="number" step="0.01" min="0" id="prod-cost-price" class="form-control" value="0.00">
                                </div>
                                <div class="form-group">
                                    <label>Tax Rate (%) *</label>
                                    <input type="number" step="0.01" min="0" id="prod-tax-rate" class="form-control" value="18.00">
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Description</label>
                                <textarea id="prod-desc" class="form-control" rows="2" placeholder="Product details..."></textarea>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="ProductPlanView.closeModal()">Cancel</button>
                            <button type="submit" id="save-prod-btn" class="btn btn-primary">Save Product</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    openEditProductModal: (productId) => {
        const prod = ProductPlanView.products.find(p => p.id === productId);
        if (!prod) return;

        const container = document.getElementById('catalog-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="ProductPlanView.closeModal(event)">
                <div class="modal-dialog" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Edit Product: ${prod.name}</h3>
                        <button class="modal-close" onclick="ProductPlanView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="ProductPlanView.submitEditProduct(event, ${prod.id})">
                        <div class="modal-body">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Product Name *</label>
                                    <input type="text" id="edit-prod-name" class="form-control" required value="${prod.name}">
                                </div>
                                <div class="form-group">
                                    <label>Product Code *</label>
                                    <input type="text" id="edit-prod-code" class="form-control" required value="${prod.code}">
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Product Type *</label>
                                    <select id="edit-prod-type" class="form-control">
                                        <option value="service" ${prod.product_type === 'service' ? 'selected' : ''}>Service</option>
                                        <option value="physical" ${prod.product_type === 'physical' ? 'selected' : ''}>Physical Product</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Sales Price ($) *</label>
                                    <input type="number" step="0.01" min="0" id="edit-prod-sales-price" class="form-control" required value="${prod.sales_price}">
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Cost Price ($)</label>
                                    <input type="number" step="0.01" min="0" id="edit-prod-cost-price" class="form-control" value="${prod.cost_price}">
                                </div>
                                <div class="form-group">
                                    <label>Tax Rate (%) *</label>
                                    <input type="number" step="0.01" min="0" id="edit-prod-tax-rate" class="form-control" value="${prod.tax_rate}">
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Description</label>
                                <textarea id="edit-prod-desc" class="form-control" rows="2">${prod.description || ''}</textarea>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="ProductPlanView.closeModal()">Cancel</button>
                            <button type="submit" id="update-prod-btn" class="btn btn-primary">Update Product</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    submitProduct: async (event) => {
        event.preventDefault();
        const payload = {
            name: document.getElementById('prod-name').value.trim(),
            code: document.getElementById('prod-code').value.trim(),
            product_type: document.getElementById('prod-type').value,
            sales_price: parseFloat(document.getElementById('prod-sales-price').value),
            cost_price: parseFloat(document.getElementById('prod-cost-price').value || 0),
            tax_rate: parseFloat(document.getElementById('prod-tax-rate').value || 18),
            description: document.getElementById('prod-desc').value.trim()
        };

        const res = await ApiClient.post('/products', payload);
        if (res.success) {
            window.showToast('Product created successfully!', 'success');
            ProductPlanView.closeModal();
            ProductPlanView.refresh();
        } else {
            window.showToast(res.error || 'Failed to create product.', 'error');
        }
    },

    submitEditProduct: async (event, productId) => {
        event.preventDefault();
        const payload = {
            name: document.getElementById('edit-prod-name').value.trim(),
            code: document.getElementById('edit-prod-code').value.trim(),
            product_type: document.getElementById('edit-prod-type').value,
            sales_price: parseFloat(document.getElementById('edit-prod-sales-price').value),
            cost_price: parseFloat(document.getElementById('edit-prod-cost-price').value || 0),
            tax_rate: parseFloat(document.getElementById('edit-prod-tax-rate').value || 18),
            description: document.getElementById('edit-prod-desc').value.trim()
        };

        const res = await ApiClient.put(`/products/${productId}`, payload);
        if (res.success) {
            window.showToast('Product updated successfully!', 'success');
            ProductPlanView.closeModal();
            ProductPlanView.refresh();
        } else {
            window.showToast(res.error || 'Failed to update product.', 'error');
        }
    },

    toggleProductActive: async (productId) => {
        const res = await ApiClient.put(`/products/${productId}/toggle-active`);
        if (res.success) {
            window.showToast('Product status updated.', 'success');
            ProductPlanView.refresh();
        } else {
            window.showToast(res.error || 'Failed to update status.', 'error');
        }
    },

    // --- PRODUCT VARIANTS MANAGEMENT ---

    openVariantsModal: (productId) => {
        const prod = ProductPlanView.products.find(p => p.id === productId);
        if (!prod) return;

        const container = document.getElementById('catalog-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="ProductPlanView.closeModal(event)">
                <div class="modal-dialog modal-lg" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Variants for: ${prod.name} (Base Price: $${prod.sales_price.toFixed(2)})</h3>
                        <button class="modal-close" onclick="ProductPlanView.closeModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <!-- Variant List -->
                        <h4>Existing Variants</h4>
                        ${prod.variants.length === 0 ? '<p class="empty-state">No variants configured for this product.</p>' : `
                            <table class="table mb-4">
                                <thead>
                                    <tr>
                                        <th>Variant Name</th>
                                        <th>SKU</th>
                                        <th>Additional Price</th>
                                        <th>Effective Final Price</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${prod.variants.map(v => `
                                        <tr>
                                            <td><strong>${v.variant_name}</strong></td>
                                            <td><code>${v.sku}</code></td>
                                            <td>+$${v.additional_price.toFixed(2)}</td>
                                            <td><strong class="text-success">$${(prod.sales_price + v.additional_price).toFixed(2)}</strong></td>
                                            <td><span class="status-pill status-${v.is_active ? 'active' : 'closed'}">${v.is_active ? 'Active' : 'Inactive'}</span></td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        `}

                        <!-- Add Variant Form -->
                        ${AuthManager.isStaff() ? `
                            <div class="card p-3 mt-3 bg-light">
                                <h4>Add New Variant (e.g. Odoo Brand +$560)</h4>
                                <form onsubmit="ProductPlanView.submitVariant(event, ${prod.id}, ${prod.sales_price})">
                                    <div class="form-row">
                                        <div class="form-group">
                                            <label>Variant Name *</label>
                                            <input type="text" id="var-name" class="form-control" required placeholder="e.g. Odoo Brand Dedicated CPU">
                                        </div>
                                        <div class="form-group">
                                            <label>SKU *</label>
                                            <input type="text" id="var-sku" class="form-control" required placeholder="e.g. ODOO-CPU-560">
                                        </div>
                                        <div class="form-group">
                                            <label>Additional Price ($) *</label>
                                            <input type="number" step="0.01" min="0" id="var-price" class="form-control" required placeholder="560.00" oninput="ProductPlanView.calcVariantTotal(${prod.sales_price})">
                                        </div>
                                    </div>
                                    <div class="text-sm mb-2 text-muted">
                                        Calculated Total Price: <span id="var-total-preview" class="font-bold text-success">$${prod.sales_price.toFixed(2)}</span>
                                    </div>
                                    <button type="submit" class="btn btn-primary btn-sm">+ Add Variant</button>
                                </form>
                            </div>
                        ` : ''}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="ProductPlanView.closeModal()">Close</button>
                    </div>
                </div>
            </div>
        `;
    },

    calcVariantTotal: (basePrice) => {
        const add = parseFloat(document.getElementById('var-price').value || 0);
        const total = basePrice + add;
        const preview = document.getElementById('var-total-preview');
        if (preview) preview.textContent = `$${total.toFixed(2)}`;
    },

    submitVariant: async (event, productId) => {
        event.preventDefault();
        const payload = {
            variant_name: document.getElementById('var-name').value.trim(),
            sku: document.getElementById('var-sku').value.trim(),
            additional_price: parseFloat(document.getElementById('var-price').value || 0)
        };

        const res = await ApiClient.post(`/products/${productId}/variants`, payload);
        if (res.success) {
            window.showToast('Variant added successfully!', 'success');
            await ProductPlanView.refresh();
            ProductPlanView.openVariantsModal(productId);
        } else {
            window.showToast(res.error || 'Failed to add variant.', 'error');
        }
    },

    // --- PLANS TABLE & OPERATIONS ---

    renderPlansTable: () => {
        if (ProductPlanView.plans.length === 0) {
            return `<p class="empty-state">No subscription plans registered yet. Click "+ Add Subscription Plan" to create one.</p>`;
        }

        return `
            <table class="table">
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Plan Name</th>
                        <th>Frequency</th>
                        <th>Base Price</th>
                        <th>Min Qty</th>
                        <th>Dates Window</th>
                        <th>Policies</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${ProductPlanView.plans.map(p => `
                        <tr>
                            <td><code>${p.code}</code></td>
                            <td>
                                <strong>${p.name}</strong>
                                ${p.description ? `<div class="text-sm text-muted">${p.description}</div>` : ''}
                            </td>
                            <td><span class="badge badge-info">${p.billing_frequency.toUpperCase()}</span></td>
                            <td><strong>$${p.base_price.toFixed(2)}</strong></td>
                            <td>${p.minimum_quantity}</td>
                            <td>
                                <span class="text-sm">
                                    ${p.start_date ? p.start_date : 'Immediate'} &rarr; ${p.end_date ? p.end_date : 'Ongoing'}
                                </span>
                            </td>
                            <td>
                                <div class="policy-tags">
                                    <span class="tag ${p.allow_pause ? 'tag-green' : 'tag-gray'}">Pause: ${p.allow_pause ? 'Yes' : 'No'}</span>
                                    <span class="tag ${p.allow_renewal ? 'tag-green' : 'tag-gray'}">Renew: ${p.allow_renewal ? 'Yes' : 'No'}</span>
                                    <span class="tag ${p.allow_early_close ? 'tag-green' : 'tag-gray'}">Early-Close: ${p.allow_early_close ? 'Yes' : 'No'}</span>
                                </div>
                            </td>
                            <td>
                                <span class="status-pill status-${p.is_available ? 'active' : 'closed'}">
                                    ${p.is_available ? 'Available' : 'Unavailable'}
                                </span>
                            </td>
                            <td>
                                ${AuthManager.isStaff() ? `
                                    <button class="btn btn-sm btn-secondary" onclick="ProductPlanView.openEditPlanModal(${p.id})">Edit</button>
                                    <button class="btn btn-sm ${p.is_active ? 'btn-danger' : 'btn-success'}" onclick="ProductPlanView.togglePlanActive(${p.id})">
                                        ${p.is_active ? 'Deactivate' : 'Activate'}
                                    </button>
                                ` : '—'}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    openCreatePlanModal: () => {
        const container = document.getElementById('catalog-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="ProductPlanView.closeModal(event)">
                <div class="modal-dialog modal-lg" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Create Subscription Plan</h3>
                        <button class="modal-close" onclick="ProductPlanView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="ProductPlanView.submitPlan(event)">
                        <div class="modal-body">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Plan Name *</label>
                                    <input type="text" id="plan-name" class="form-control" required placeholder="e.g. Enterprise Monthly Subscription">
                                </div>
                                <div class="form-group">
                                    <label>Plan Code *</label>
                                    <input type="text" id="plan-code" class="form-control" required placeholder="e.g. PLAN-ENT-MTH">
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Billing Frequency *</label>
                                    <select id="plan-freq" class="form-control">
                                        <option value="daily">Daily</option>
                                        <option value="weekly">Weekly</option>
                                        <option value="monthly" selected>Monthly</option>
                                        <option value="yearly">Yearly</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Base Price ($) *</label>
                                    <input type="number" step="0.01" min="0" id="plan-price" class="form-control" required placeholder="1500.00">
                                </div>
                                <div class="form-group">
                                    <label>Minimum Quantity *</label>
                                    <input type="number" min="1" id="plan-min-qty" class="form-control" required value="1">
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Availability Start Date</label>
                                    <input type="date" id="plan-start-date" class="form-control">
                                </div>
                                <div class="form-group">
                                    <label>Availability End Date</label>
                                    <input type="date" id="plan-end-date" class="form-control">
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Description</label>
                                <textarea id="plan-desc" class="form-control" rows="2" placeholder="Plan details and commitments..."></textarea>
                            </div>
                            <div class="policy-checkboxes-group">
                                <h4>Plan Policies</h4>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="plan-allow-pause" checked> Allow customer to pause active subscription
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="plan-allow-renewal" checked> Allow automatic or manual subscription renewal
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="plan-allow-early-close" checked> Allow early cancellation/closure before plan end date
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="plan-auto-close"> Automatically close subscription on availability expiration
                                </label>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="ProductPlanView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Create Plan</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    openEditPlanModal: (planId) => {
        const plan = ProductPlanView.plans.find(p => p.id === planId);
        if (!plan) return;

        const container = document.getElementById('catalog-modal-container');
        container.innerHTML = `
            <div class="modal-backdrop" onclick="ProductPlanView.closeModal(event)">
                <div class="modal-dialog modal-lg" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Edit Plan: ${plan.name}</h3>
                        <button class="modal-close" onclick="ProductPlanView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="ProductPlanView.submitEditPlan(event, ${plan.id})">
                        <div class="modal-body">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Plan Name *</label>
                                    <input type="text" id="edit-plan-name" class="form-control" required value="${plan.name}">
                                </div>
                                <div class="form-group">
                                    <label>Plan Code *</label>
                                    <input type="text" id="edit-plan-code" class="form-control" required value="${plan.code}">
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Billing Frequency *</label>
                                    <select id="edit-plan-freq" class="form-control">
                                        <option value="daily" ${plan.billing_frequency === 'daily' ? 'selected' : ''}>Daily</option>
                                        <option value="weekly" ${plan.billing_frequency === 'weekly' ? 'selected' : ''}>Weekly</option>
                                        <option value="monthly" ${plan.billing_frequency === 'monthly' ? 'selected' : ''}>Monthly</option>
                                        <option value="yearly" ${plan.billing_frequency === 'yearly' ? 'selected' : ''}>Yearly</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Base Price ($) *</label>
                                    <input type="number" step="0.01" min="0" id="edit-plan-price" class="form-control" required value="${plan.base_price}">
                                </div>
                                <div class="form-group">
                                    <label>Minimum Quantity *</label>
                                    <input type="number" min="1" id="edit-plan-min-qty" class="form-control" required value="${plan.minimum_quantity}">
                                </div>
                            </div>
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Availability Start Date</label>
                                    <input type="date" id="edit-plan-start-date" class="form-control" value="${plan.start_date || ''}">
                                </div>
                                <div class="form-group">
                                    <label>Availability End Date</label>
                                    <input type="date" id="edit-plan-end-date" class="form-control" value="${plan.end_date || ''}">
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Description</label>
                                <textarea id="edit-plan-desc" class="form-control" rows="2">${plan.description || ''}</textarea>
                            </div>
                            <div class="policy-checkboxes-group">
                                <h4>Plan Policies</h4>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="edit-plan-allow-pause" ${plan.allow_pause ? 'checked' : ''}> Allow customer to pause active subscription
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="edit-plan-allow-renewal" ${plan.allow_renewal ? 'checked' : ''}> Allow automatic or manual subscription renewal
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="edit-plan-allow-early-close" ${plan.allow_early_close ? 'checked' : ''}> Allow early cancellation/closure before plan end date
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="edit-plan-auto-close" ${plan.auto_close_on_expiry ? 'checked' : ''}> Automatically close subscription on availability expiration
                                </label>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="ProductPlanView.closeModal()">Cancel</button>
                            <button type="submit" class="btn btn-primary">Update Plan</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    submitPlan: async (event) => {
        event.preventDefault();
        const payload = {
            name: document.getElementById('plan-name').value.trim(),
            code: document.getElementById('plan-code').value.trim(),
            billing_frequency: document.getElementById('plan-freq').value,
            base_price: parseFloat(document.getElementById('plan-price').value),
            minimum_quantity: parseInt(document.getElementById('plan-min-qty').value, 10),
            start_date: document.getElementById('plan-start-date').value || null,
            end_date: document.getElementById('plan-end-date').value || null,
            description: document.getElementById('plan-desc').value.trim(),
            allow_pause: document.getElementById('plan-allow-pause').checked,
            allow_renewal: document.getElementById('plan-allow-renewal').checked,
            allow_early_close: document.getElementById('plan-allow-early-close').checked,
            auto_close_on_expiry: document.getElementById('plan-auto-close').checked
        };

        const res = await ApiClient.post('/plans', payload);
        if (res.success) {
            window.showToast('Subscription plan created successfully!', 'success');
            ProductPlanView.closeModal();
            ProductPlanView.refresh();
        } else {
            window.showToast(res.error || 'Failed to create plan.', 'error');
        }
    },

    submitEditPlan: async (event, planId) => {
        event.preventDefault();
        const payload = {
            name: document.getElementById('edit-plan-name').value.trim(),
            code: document.getElementById('edit-plan-code').value.trim(),
            billing_frequency: document.getElementById('edit-plan-freq').value,
            base_price: parseFloat(document.getElementById('edit-plan-price').value),
            minimum_quantity: parseInt(document.getElementById('edit-plan-min-qty').value, 10),
            start_date: document.getElementById('edit-plan-start-date').value || null,
            end_date: document.getElementById('edit-plan-end-date').value || null,
            description: document.getElementById('edit-plan-desc').value.trim(),
            allow_pause: document.getElementById('edit-plan-allow-pause').checked,
            allow_renewal: document.getElementById('edit-plan-allow-renewal').checked,
            allow_early_close: document.getElementById('edit-plan-allow-early-close').checked,
            auto_close_on_expiry: document.getElementById('edit-plan-auto-close').checked
        };

        const res = await ApiClient.put(`/plans/${planId}`, payload);
        if (res.success) {
            window.showToast('Plan updated successfully!', 'success');
            ProductPlanView.closeModal();
            ProductPlanView.refresh();
        } else {
            window.showToast(res.error || 'Failed to update plan.', 'error');
        }
    },

    togglePlanActive: async (planId) => {
        const res = await ApiClient.put(`/plans/${planId}/toggle-active`);
        if (res.success) {
            window.showToast('Plan status updated.', 'success');
            ProductPlanView.refresh();
        } else {
            window.showToast(res.error || 'Failed to update plan status.', 'error');
        }
    },

    openCreateItemModal: () => {
        if (ProductPlanView.currentTab === 'products') {
            ProductPlanView.openCreateProductModal();
        } else {
            ProductPlanView.openCreatePlanModal();
        }
    },

    closeModal: () => {
        const container = document.getElementById('catalog-modal-container');
        if (container) container.innerHTML = '';
    },

    refresh: async () => {
        const [prodRes, planRes] = await Promise.all([
            ApiClient.get('/products'),
            ApiClient.get('/plans')
        ]);
        ProductPlanView.products = prodRes.success ? prodRes.data : [];
        ProductPlanView.plans = planRes.success ? planRes.data : [];

        const container = document.getElementById('tab-content');
        if (container) {
            container.querySelector('.card-body').innerHTML = 
                ProductPlanView.currentTab === 'products' ? ProductPlanView.renderProductsTable() : ProductPlanView.renderPlansTable();
        }
    }
};

window.ProductPlanView = ProductPlanView;

