// Authentication, Sidebar, Toast, and WebSocket Manager

let ws = null;
let reconnectAttempts = 0;
const maxReconnectDelay = 15000;
let wsHeartbeatTimer = null;

// Toast notification helper
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = "toast";

  let bgClass = "bg-slate-800 border border-slate-700";
  let icon = "fa-circle-info text-blue-400";
  if (type === "success") {
    bgClass = "bg-emerald-900/90 border border-emerald-500/50 text-white";
    icon = "fa-circle-check text-emerald-400";
  } else if (type === "error") {
    bgClass = "bg-rose-900/90 border border-rose-500/50 text-white";
    icon = "fa-triangle-exclamation text-rose-400";
  } else if (type === "warning") {
    bgClass = "bg-amber-900/90 border border-amber-500/50 text-white";
    icon = "fa-triangle-exclamation text-amber-400";
  }

  toast.className = `toast ${bgClass}`;
  toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Check current user profile
async function checkAuth() {
  const isLoginPage = window.location.pathname === "/login";
  try {
    const res = await fetch("/api/v1/auth/me");
    if (!res.ok) {
      if (!isLoginPage) window.location.href = "/login";
      return null;
    }
    const user = await res.json();

    // Update UI elements with user data
    const nameEl = document.getElementById("user-display-name");
    const avatarEl = document.getElementById("user-avatar");
    const roleEl = document.getElementById("user-role-badge");
    const adminLink = document.getElementById("admin-users-link");

    if (nameEl) nameEl.textContent = user.username;
    if (avatarEl) avatarEl.textContent = user.username.charAt(0).toUpperCase();
    if (roleEl) roleEl.textContent = user.is_admin ? "Administrator" : "Operator";
    if (adminLink && user.is_admin) {
      adminLink.classList.remove("hidden");
    }

    return user;
  } catch (err) {
    if (!isLoginPage) window.location.href = "/login";
    return null;
  }
}

// WebSocket Connection Manager with Exponential Backoff
function setupWebSocket() {
  const token = localStorage.getItem("auth_token");
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/dashboard${token ? `?token=${token}` : ""}`;

  const statusBadge = document.getElementById("ws-status-badge");
  const statusDot = document.getElementById("ws-indicator-dot");
  const statusText = document.getElementById("ws-status-text");

  function updateStatus(state) {
    if (!statusDot || !statusText) return;
    if (state === "connected") {
      statusDot.className = "w-2.5 h-2.5 rounded-full bg-emerald-400 pulse-green";
      statusText.textContent = "Connected";
      statusText.className = "font-medium text-emerald-400";
    } else if (state === "reconnecting") {
      statusDot.className = "w-2.5 h-2.5 rounded-full bg-amber-400 pulse-yellow";
      statusText.textContent = "Reconnecting...";
      statusText.className = "font-medium text-amber-400";
    } else {
      statusDot.className = "w-2.5 h-2.5 rounded-full bg-rose-500";
      statusText.textContent = "Disconnected";
      statusText.className = "font-medium text-rose-400";
    }
  }

  updateStatus("reconnecting");
  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    reconnectAttempts = 0;
    updateStatus("connected");
    // Start heartbeat
    clearInterval(wsHeartbeatTimer);
    wsHeartbeatTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 25000);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "pong") return;
      window.dispatchEvent(new CustomEvent("ws_event", { detail: data }));
    } catch (e) {
      console.error("Failed to parse websocket message", e);
    }
  };

  ws.onclose = () => {
    clearInterval(wsHeartbeatTimer);
    updateStatus("reconnecting");
    scheduleReconnect();
  };

  ws.onerror = () => {
    if (ws) ws.close();
  };
}

function scheduleReconnect() {
  reconnectAttempts++;
  const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), maxReconnectDelay);
  setTimeout(() => {
    setupWebSocket();
  }, delay);
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", async () => {
  const isLoginPage = window.location.pathname === "/login";
  if (!isLoginPage) {
    const user = await checkAuth();
    if (user) {
      setupWebSocket();
    }
  }

  // Active navigation highlight
  const currentPath = window.location.pathname;
  document.querySelectorAll(".nav-item").forEach((item) => {
    if (item.getAttribute("data-route") === currentPath) {
      item.classList.add("bg-blue-600", "text-white");
      item.classList.remove("text-slate-300");
    }
  });

  // Logout button
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await fetch("/api/v1/auth/logout", { method: "POST" });
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
      window.location.href = "/login";
    });
  }

  // Mobile menu toggle
  const mobileMenuBtn = document.getElementById("mobile-menu-btn");
  const sidebar = document.getElementById("sidebar");
  if (mobileMenuBtn && sidebar) {
    mobileMenuBtn.addEventListener("click", () => {
      sidebar.classList.toggle("hidden");
    });
  }
});
