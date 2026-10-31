/**
 * User Management View Component (Module 1)
 * =========================================
 * Allows Administrators and Staff to view, manage, and provision users with RBAC.
 */

const UserView = {
    users: [],

    render: async () => {
        if (!AuthManager.isAdmin() && !AuthManager.isStaff()) {
            return `<div class="alert alert-danger">Access forbidden: Administrative permissions required.</div>`;
        }

        const res = await ApiClient.get('/users');
        UserView.users = res.success ? res.data : [];

        return `
            <div class="view-header">
                <div>
                    <h2>User & Account Management</h2>
                    <p class="text-muted">Manage staff accounts, customer access, and role permissions</p>
                </div>
                ${AuthManager.isAdmin() ? `
                    <button class="btn btn-primary" onclick="UserView.openCreateStaffModal()">+ Create Staff Account</button>
                ` : ''}
            </div>

            <!-- Filters & Search Toolbar -->
            <div class="toolbar">
                <input type="text" id="user-search" class="form-control toolbar-search" placeholder="Search by name or email..." oninput="UserView.filterUsers()">
                <select id="user-role-filter" class="form-control toolbar-select" onchange="UserView.filterUsers()">
                    <option value="">All Roles</option>
                    <option value="admin">Administrator</option>
                    <option value="staff">Staff</option>
                    <option value="customer">Customer</option>
                </select>
            </div>

            <!-- User Table -->
            <div class="card">
                <div class="card-body">
                    <div id="users-table-container">
                        ${UserView.renderTable(UserView.users)}
                    </div>
                </div>
            </div>

            <!-- Create Staff Modal Container -->
            <div id="user-modal-container"></div>
        `;
    },

    renderTable: (userList) => {
        if (userList.length === 0) {
            return `<p class="empty-state">No users match the search criteria.</p>`;
        }

        const currentUserId = AuthManager.getUser().id;

        return `
            <table class="table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${userList.map(u => `
                        <tr>
                            <td><strong>${u.full_name}</strong></td>
                            <td>${u.email}</td>
                            <td>
                                <span class="badge ${u.role === 'admin' ? 'role-admin' : u.role === 'staff' ? 'role-staff' : 'role-customer'}">
                                    ${u.role.toUpperCase()}
                                </span>
                            </td>
                            <td>
                                <span class="status-pill status-${u.is_active ? 'active' : 'closed'}">
                                    ${u.is_active ? 'Active' : 'Deactivated'}
                                </span>
                            </td>
                            <td>${u.created_at ? u.created_at.split('T')[0] : 'N/A'}</td>
                            <td>
                                ${u.id !== currentUserId && (AuthManager.isAdmin() || (AuthManager.isStaff() && u.role === 'customer')) ? `
                                    <button class="btn btn-sm ${u.is_active ? 'btn-danger' : 'btn-success'}" onclick="UserView.toggleActive(${u.id}, '${u.full_name}')">
                                        ${u.is_active ? 'Deactivate' : 'Activate'}
                                    </button>
                                ` : '<span class="text-muted text-sm">—</span>'}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    },

    filterUsers: () => {
        const search = (document.getElementById('user-search').value || '').toLowerCase();
        const role = document.getElementById('user-role-filter').value;

        const filtered = UserView.users.filter(u => {
            const matchesSearch = u.full_name.toLowerCase().includes(search) || u.email.toLowerCase().includes(search);
            const matchesRole = !role || u.role === role;
            return matchesSearch && matchesRole;
        });

        document.getElementById('users-table-container').innerHTML = UserView.renderTable(filtered);
    },

    toggleActive: async (userId, userName) => {
        if (!confirm(`Are you sure you want to change the active status for ${userName}?`)) return;

        const res = await ApiClient.put(`/users/${userId}/toggle-active`);
        if (res.success) {
            window.showToast('User status updated successfully.', 'success');
            // Refresh table
            const refreshed = await ApiClient.get('/users');
            if (refreshed.success) {
                UserView.users = refreshed.data;
                UserView.filterUsers();
            }
        } else {
            window.showToast(res.error || 'Failed to update user status.', 'error');
        }
    },

    openCreateStaffModal: () => {
        const modalContainer = document.getElementById('user-modal-container');
        modalContainer.innerHTML = `
            <div class="modal-backdrop" onclick="UserView.closeModal(event)">
                <div class="modal-dialog" onclick="event.stopPropagation()">
                    <div class="modal-header">
                        <h3>Create Staff Account</h3>
                        <button class="modal-close" onclick="UserView.closeModal()">&times;</button>
                    </div>
                    <form onsubmit="UserView.submitCreateStaff(event)">
                        <div class="modal-body">
                            <div class="form-row">
                                <div class="form-group">
                                    <label>First Name *</label>
                                    <input type="text" id="staff-first-name" class="form-control" required placeholder="Staff first name">
                                </div>
                                <div class="form-group">
                                    <label>Last Name *</label>
                                    <input type="text" id="staff-last-name" class="form-control" required placeholder="Staff last name">
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Email Address *</label>
                                <input type="email" id="staff-email" class="form-control" required placeholder="staff.member@brightloop.com">
                            </div>
                            <div class="form-group">
                                <label>Phone (Optional)</label>
                                <input type="tel" id="staff-phone" class="form-control" placeholder="+1 555-0150">
                            </div>
                            <div class="form-group">
                                <label>Role *</label>
                                <select id="staff-role" class="form-control">
                                    <option value="staff" selected>Staff Member</option>
                                    <option value="customer">Customer</option>
                                </select>
                                <small class="form-hint">Staff accounts can manage products, quotations, and subscriptions.</small>
                            </div>
                            <div class="form-group">
                                <label>Initial Password *</label>
                                <input type="password" id="staff-password" class="form-control" required placeholder="At least 9 characters">
                                <small class="form-hint">Must contain uppercase, lowercase, and special character.</small>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="UserView.closeModal()">Cancel</button>
                            <button type="submit" id="create-staff-btn" class="btn btn-primary">Create Account</button>
                        </div>
                    </form>
                </div>
            </div>
        `;
    },

    closeModal: () => {
        const modalContainer = document.getElementById('user-modal-container');
        if (modalContainer) modalContainer.innerHTML = '';
    },

    submitCreateStaff: async (event) => {
        event.preventDefault();
        const firstName = document.getElementById('staff-first-name').value.trim();
        const lastName = document.getElementById('staff-last-name').value.trim();
        const email = document.getElementById('staff-email').value.trim();
        const phone = document.getElementById('staff-phone').value.trim();
        const role = document.getElementById('staff-role').value;
        const password = document.getElementById('staff-password').value;
        const btn = document.getElementById('create-staff-btn');

        btn.disabled = true;
        btn.textContent = 'Creating...';

        const res = await ApiClient.post('/users', {
            first_name: firstName,
            last_name: lastName,
            email,
            phone,
            role,
            password
        });

        btn.disabled = false;
        btn.textContent = 'Create Account';

        if (res.success) {
            window.showToast('Staff account created successfully!', 'success');
            UserView.closeModal();
            // Refresh table
            const refreshed = await ApiClient.get('/users');
            if (refreshed.success) {
                UserView.users = refreshed.data;
                UserView.filterUsers();
            }
        } else {
            window.showToast(res.error || 'Failed to create staff account.', 'error');
        }
    }
};

window.UserView = UserView;

