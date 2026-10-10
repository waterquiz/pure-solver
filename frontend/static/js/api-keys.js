// API Keys Management Logic

async function loadApiKeys() {
  const tbody = document.getElementById("api-keys-table-body");
  if (!tbody) return;

  try {
    const res = await fetch("/api/v1/api-keys");
    if (!res.ok) return;
    const keys = await res.json();

    tbody.innerHTML = "";
    if (keys.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="px-6 py-8 text-center text-slate-400">
            No API keys found. Click "Generate New API Key" above to create one.
          </td>
        </tr>
      `;
      return;
    }

    keys.forEach((key) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50/80 transition";

      const createdDate = new Date(key.created_at).toLocaleDateString();
      const lastUsed = key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never";

      tr.innerHTML = `
        <td class="px-6 py-4 font-semibold text-slate-900">${key.name}</td>
        <td class="px-6 py-4 font-mono text-blue-700 text-xs font-semibold">${key.masked_key}</td>
        <td class="px-6 py-4"><span class="bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg font-mono text-[11px] border border-slate-200">${key.scopes}</span></td>
        <td class="px-6 py-4 font-mono font-bold text-slate-800">${key.usage_count.toLocaleString()}</td>
        <td class="px-6 py-4 text-slate-500 text-[11px]">${lastUsed}</td>
        <td class="px-6 py-4 text-slate-500 text-[11px]">${createdDate}</td>
        <td class="px-6 py-4">
          <button class="toggle-status-btn px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
            key.is_active ? "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100" : "bg-slate-100 text-slate-500 hover:bg-slate-200 border border-slate-200"
          }" data-id="${key.id}" data-active="${key.is_active}">
            ${key.is_active ? "Active" : "Disabled"}
          </button>
        </td>
        <td class="px-6 py-4 text-right">
          <button class="revoke-key-btn p-1.5 text-slate-400 hover:text-rose-600 rounded-lg transition" title="Revoke and delete" data-id="${key.id}" data-name="${key.name}">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </td>
      `;

      tbody.appendChild(tr);
    });

    // Attach Toggle Status Listeners
    document.querySelectorAll(".toggle-status-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const currentActive = btn.getAttribute("data-active") === "true";
        try {
          const res = await fetch(`/api/v1/api-keys/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !currentActive })
          });
          if (res.ok) {
            showToast(`Key status updated to ${!currentActive ? "Active" : "Disabled"}`, "success");
            loadApiKeys();
          }
        } catch (e) {
          showToast("Error updating key status", "error");
        }
      });
    });

    // Attach Revoke Listeners
    document.querySelectorAll(".revoke-key-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const name = btn.getAttribute("data-name");
        if (!confirm(`Are you sure you want to permanently revoke API key "${name}"? Any active integrations using this key will immediately stop working.`)) return;

        try {
          const res = await fetch(`/api/v1/api-keys/${id}`, { method: "DELETE" });
          if (res.ok) {
            showToast("API key revoked", "success");
            loadApiKeys();
          }
        } catch (e) {
          showToast("Error revoking API key", "error");
        }
      });
    });

  } catch (err) {
    console.error("Error loading API keys:", err);
  }
}

// Modal handling
const createModal = document.getElementById("create-key-modal");
const openModalBtn = document.getElementById("open-create-key-btn");
const closeModalBtn = document.getElementById("close-create-modal-btn");
const cancelModalBtn = document.getElementById("cancel-create-btn");
const createForm = document.getElementById("create-key-form");

const revealModal = document.getElementById("reveal-key-modal");
const revealedInput = document.getElementById("revealed-key-input");
const copyKeyBtn = document.getElementById("copy-revealed-key-btn");
const dismissRevealBtn = document.getElementById("dismiss-reveal-btn");
const curlPreview = document.getElementById("curl-preview-snippet");

if (openModalBtn) {
  openModalBtn.addEventListener("click", () => {
    document.getElementById("key-name").value = "";
    createModal.classList.remove("hidden");
  });
}

function hideCreateModal() {
  if (createModal) createModal.classList.add("hidden");
}

if (closeModalBtn) closeModalBtn.addEventListener("click", hideCreateModal);
if (cancelModalBtn) cancelModalBtn.addEventListener("click", hideCreateModal);

// Form submit: Generate Key
if (createForm) {
  createForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("key-name").value.trim();
    const scopes = [];
    if (document.getElementById("scope-upload").checked) scopes.push("images:upload");
    if (document.getElementById("scope-read").checked) scopes.push("images:read");
    if (document.getElementById("scope-delete").checked) scopes.push("images:delete");

    try {
      const res = await fetch("/api/v1/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, scopes: scopes.join(",") })
      });

      if (!res.ok) {
        showToast("Failed to create API key", "error");
        return;
      }

      const created = await res.json();
      hideCreateModal();

      // Show one-time reveal dialog
      revealedInput.value = created.raw_key;
      if (curlPreview) {
        curlPreview.textContent = `curl -X POST "${window.location.origin}/api/v1/images" \\\n  -H "X-API-Key: ${created.raw_key}" \\\n  -F "file=@image.png"`;
      }
      revealModal.classList.remove("hidden");

      loadApiKeys();
      showToast("API Key created successfully!", "success");
    } catch (err) {
      showToast("Error generating key", "error");
    }
  });
}

// Copy raw key
if (copyKeyBtn) {
  copyKeyBtn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(revealedInput.value);
      showToast("API key copied to clipboard!", "success");
    } catch (e) {
      revealedInput.select();
      document.execCommand("copy");
      showToast("API key copied to clipboard!", "success");
    }
  });
}

if (dismissRevealBtn) {
  dismissRevealBtn.addEventListener("click", () => {
    revealModal.classList.add("hidden");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadApiKeys();
});
