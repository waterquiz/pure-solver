// User Management Client Logic

async function loadUsers() {
  const tbody = document.getElementById("users-table-body");
  if (!tbody) return;

  try {
    const res = await fetch("/api/v1/users");
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="6" class="px-6 py-8 text-center text-rose-500 font-semibold">Access denied or error loading users.</td></tr>`;
      return;
    }
    const users = await res.json();

    tbody.innerHTML = "";
    users.forEach((u) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50/80 transition";

      const created = new Date(u.created_at).toLocaleDateString();

      tr.innerHTML = `
        <td class="px-6 py-4 font-semibold text-slate-900 flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold text-xs uppercase">
            ${u.username.charAt(0)}
          </div>
          <span>${u.username}</span>
        </td>
        <td class="px-6 py-4 text-slate-600">${u.email}</td>
        <td class="px-6 py-4">
          <span class="px-2.5 py-0.5 rounded-lg text-[10px] font-bold ${
            u.is_admin ? "bg-purple-50 text-purple-700 border border-purple-200" : "bg-slate-100 text-slate-600 border border-slate-200"
          }">
            ${u.is_admin ? "ADMIN" : "OPERATOR"}
          </span>
        </td>
        <td class="px-6 py-4">
          <button class="toggle-user-status-btn px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
            u.is_active ? "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100" : "bg-slate-100 text-slate-500 hover:bg-slate-200 border border-slate-200"
          }" data-id="${u.id}" data-active="${u.is_active}">
            ${u.is_active ? "Active" : "Disabled"}
          </button>
        </td>
        <td class="px-6 py-4 text-slate-500 text-[11px]">${created}</td>
        <td class="px-6 py-4 text-right">
          <button class="delete-user-btn p-1.5 text-slate-400 hover:text-rose-600 rounded-lg transition" title="Delete account" data-id="${u.id}" data-username="${u.username}">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </td>
      `;

      tbody.appendChild(tr);
    });

    // Attach Toggle Status Listeners
    document.querySelectorAll(".toggle-user-status-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const currentActive = btn.getAttribute("data-active") === "true";
        try {
          const res = await fetch(`/api/v1/users/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !currentActive })
          });
          if (res.ok) {
            showToast(`User status updated to ${!currentActive ? "Active" : "Disabled"}`, "success");
            loadUsers();
          } else {
            const err = await res.json();
            showToast(err.detail || "Error updating user status", "error");
          }
        } catch (e) {
          showToast("Network error updating status", "error");
        }
      });
    });

    // Attach Delete Listeners
    document.querySelectorAll(".delete-user-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const username = btn.getAttribute("data-username");
        if (!confirm(`Are you sure you want to permanently delete user "${username}"?`)) return;

        try {
          const res = await fetch(`/api/v1/users/${id}`, { method: "DELETE" });
          if (res.ok) {
            showToast(`User "${username}" deleted`, "success");
            loadUsers();
          } else {
            const err = await res.json();
            showToast(err.detail || "Error deleting user", "error");
          }
        } catch (e) {
          showToast("Network error deleting user", "error");
        }
      });
    });

  } catch (err) {
    console.error("Error loading users:", err);
  }
}

// Modal handling
const userModal = document.getElementById("create-user-modal");
const openUserModalBtn = document.getElementById("open-create-user-btn");
const closeUserModalBtn = document.getElementById("close-user-modal-btn");
const cancelUserModalBtn = document.getElementById("cancel-user-modal-btn");
const createUserForm = document.getElementById("create-user-form");

if (openUserModalBtn) {
  openUserModalBtn.addEventListener("click", () => {
    createUserForm.reset();
    userModal.classList.remove("hidden");
  });
}

function hideUserModal() {
  if (userModal) userModal.classList.add("hidden");
}

if (closeUserModalBtn) closeUserModalBtn.addEventListener("click", hideUserModal);
if (cancelUserModalBtn) cancelUserModalBtn.addEventListener("click", hideUserModal);

if (createUserForm) {
  createUserForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("new-username").value.trim();
    const email = document.getElementById("new-email").value.trim();
    const password = document.getElementById("new-password").value;
    const is_admin = document.getElementById("new-is-admin").checked;

    try {
      const res = await fetch("/api/v1/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password, is_admin })
      });

      if (!res.ok) {
        const err = await res.json();
        showToast(err.detail || "Failed to create user", "error");
        return;
      }

      hideUserModal();
      loadUsers();
      showToast(`User "${username}" created successfully`, "success");
    } catch (err) {
      showToast("Network error creating user", "error");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadUsers();
});
