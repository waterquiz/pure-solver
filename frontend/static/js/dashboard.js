// Pure Solver / Remote Image Display & AI Hub - Dashboard Client Logic

let allImages = [];
let currentFilterQuery = "";
const pageSize = 100;

// Helper: Format byte sizes
function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

// Helper: Format timestamp
function formatDate(isoStr) {
  if (!isoStr) return "-";
  const d = new Date(isoStr);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Helper: Format full date
function formatFullDate(isoStr) {
  if (!isoStr) return "-";
  const d = new Date(isoStr);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric"
  }) + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// Update count of images currently on screen
function updateScreenImagesCount() {
  const count = allImages.length;
  const elScreen = document.getElementById("stat-screen-images");
  if (elScreen) elScreen.textContent = count.toLocaleString();

  const elHeaderSlot = document.getElementById("header-slot-text");
  if (elHeaderSlot) elHeaderSlot.textContent = `${count} / 12 Active`;
}

// Load and refresh statistics
async function loadStats() {
  try {
    const res = await fetch("/api/v1/stats");
    if (!res.ok) return;
    const stats = await res.json();

    const elKeys = document.getElementById("stat-total-keys");
    if (elKeys) elKeys.textContent = (stats.active_api_keys ?? stats.total_api_keys ?? 0).toLocaleString();

    const elScreen = document.getElementById("stat-screen-images");
    if (elScreen) elScreen.textContent = (stats.active_screen_images ?? allImages.length).toLocaleString();

    const elQueued = document.getElementById("stat-queued-images");
    if (elQueued) elQueued.textContent = (stats.queued_images ?? 0).toLocaleString();

    const elHeaderSlot = document.getElementById("header-slot-text");
    if (elHeaderSlot) {
      const activeCount = stats.active_screen_images ?? allImages.length;
      elHeaderSlot.textContent = `${activeCount} / 12 Active`;
    }
  } catch (err) {
    console.error("Error loading stats:", err);
  }
}

// ---------------------------------------------------------------------------
// Puter.js AI SDK Integration (Client-side Vision Inference)
// ---------------------------------------------------------------------------
function loadPuter() {
  return new Promise((resolve, reject) => {
    if (window.puter) {
      resolve(window.puter);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://js.puter.com/v2/";
    script.onload = () => (window.puter ? resolve(window.puter) : reject(new Error("Puter not found")));
    script.onerror = () => reject(new Error("Failed to load Puter SDK"));
    document.head.appendChild(script);
  });
}

function parseAiResponse(res) {
  let text = "";
  if (typeof res === "string") {
    text = res;
  } else if (res?.message && typeof res.message.content === "string") {
    text = res.message.content;
  } else if (typeof res?.text === "string") {
    text = res.text;
  } else if (typeof res?.message === "string") {
    text = res.message;
  } else if (res) {
    text = JSON.stringify(res);
  }
  return text.trim().toLowerCase();
}

async function getBase64ImageFromUrl(imageUrl) {
  const res = await fetch(imageUrl);
  const blob = await res.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// Check and update Puter.js authentication UI
async function updatePuterAuthUI() {
  const container = document.getElementById("puter-auth-container");
  if (!container) return;

  try {
    const puter = await loadPuter();
    const signedIn = puter.auth.isSignedIn();

    if (signedIn) {
      let user = null;
      try { user = await puter.auth.getUser(); } catch (_) {}
      container.innerHTML = `
        <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200/80 text-emerald-700 text-xs font-semibold shadow-sm">
          <i class="fa-solid fa-circle-check text-emerald-500 text-xs"></i>
          <span>${user?.username ? '@' + user.username : 'Puter Online'}</span>
          <button id="puter-signout-btn" class="text-slate-400 hover:text-rose-500 ml-1 transition" title="Sign out of Puter">
            <i class="fa-solid fa-right-from-bracket text-[10px]"></i>
          </button>
        </div>
      `;
      container.querySelector("#puter-signout-btn")?.addEventListener("click", async () => {
        await puter.auth.signOut();
        updatePuterAuthUI();
        if (typeof showToast === "function") showToast("Signed out of Puter", "info");
      });
    } else {
      container.innerHTML = `
        <button id="puter-connect-btn" class="px-3.5 py-1.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-sm transition">
          <i class="fa-solid fa-bolt text-blue-600 text-xs"></i>
          <span>Puter SDK</span>
        </button>
      `;
      container.querySelector("#puter-connect-btn")?.addEventListener("click", async () => {
        try {
          if (typeof showToast === "function") showToast("Opening Puter sign-in...", "info");
          const user = await puter.auth.signIn();
          if (typeof showToast === "function") showToast(`Connected to Puter: @${user?.username || 'User'}`, "success");
          updatePuterAuthUI();
        } catch (err) {
          console.error("Puter sign-in error:", err);
          if (typeof showToast === "function") showToast("Puter connection popup was closed", "info");
        }
      });
    }
  } catch (err) {
    console.warn("Could not check Puter auth state:", err);
  }
}

// Concurrent AI Analysis Queue (handles 12+ browsers simultaneously)
const aiTaskQueue = [];
let activeAiWorkers = 0;
const MAX_CONCURRENT_AI = 3;
const enqueuedOrProcessedImageIds = new Set();

function enqueueAiTask(img, boxEl) {
  if (enqueuedOrProcessedImageIds.has(img.id)) return;
  enqueuedOrProcessedImageIds.add(img.id);
  aiTaskQueue.push({ img, boxEl });
  processNextAiTask();
}

async function processNextAiTask() {
  if (activeAiWorkers >= MAX_CONCURRENT_AI || aiTaskQueue.length === 0) return;
  activeAiWorkers++;
  const { img, boxEl } = aiTaskQueue.shift();

  try {
    await analyzeImageWithPuter(img, boxEl);
  } catch (err) {
    console.error(`AI Task failed for image ${img.id}:`, err);
  } finally {
    activeAiWorkers--;
    processNextAiTask();
  }
}

// Robust extractor: extracts cell integers strictly from 1 to 9, rejecting spurious digits like 3x3 or 9 cells
function extractMatchedCells(rawText) {
  if (!rawText) return [];
  const clean = (typeof rawText === "string" ? rawText : JSON.stringify(rawText)).trim();

  // 1. Explicit "None"
  if (/^(none|nothing|null|no cells|no tiles|n\/a)\.?$/i.test(clean) || (/\bnone\b/i.test(clean) && !/\d/.test(clean))) {
    return [];
  }

  // 2. Clean comma-separated digits: e.g. "1, 4, 7" or "2, 5" or "1"
  const commaSeparatedMatch = clean.match(/^([1-9](?:\s*,\s*[1-9])*)\.?$/);
  if (commaSeparatedMatch) {
    const digits = commaSeparatedMatch[1].match(/[1-9]/g) || [];
    return [...new Set(digits.map(n => parseInt(n, 10)))].sort((a, b) => a - b);
  }

  // 3. JSON array pattern: [2, 5, 8] or [1] or []
  const bracketMatch = clean.match(/\[\s*([0-9,\s]*)\s*\]/);
  if (bracketMatch) {
    try {
      const parsed = JSON.parse(bracketMatch[0]);
      if (Array.isArray(parsed)) {
        return [...new Set(parsed.map(n => parseInt(n, 10)).filter(n => n >= 1 && n <= 9))].sort((a, b) => a - b);
      }
    } catch (_) {}
    const innerDigits = bracketMatch[1].match(/[1-9]/g) || [];
    return [...new Set(innerDigits.map(n => parseInt(n, 10)))].sort((a, b) => a - b);
  }

  // 4. Pattern like "Cells: 2, 5, 8"
  const cellsPrefixMatch = clean.match(/(?:cells?|tiles?|numbers?|output)\s*[:=]?\s*([1-9,\s]+)/i);
  if (cellsPrefixMatch) {
    const digits = cellsPrefixMatch[1].match(/[1-9]/g) || [];
    return [...new Set(digits.map(n => parseInt(n, 10)))].sort((a, b) => a - b);
  }

  // 5. Sanitize 3x3, 9 cells, and coordinates before extracting digits
  const sanitized = clean
    .replace(/3\s*[xX*×by]\s*3/gi, '')
    .replace(/9\s*(cells?|tiles?|squares?|grid)/gi, '')
    .replace(/(top|left|bottom|right|middle|center)\s*to\s*(bottom|right|left)/gi, '');
  const digits = sanitized.match(/[1-9]/g) || [];
  return [...new Set(digits.map(n => parseInt(n, 10)))].sort((a, b) => a - b);
}

async function analyzeImageWithPuter(img, boxEl) {
  const statusContainer = boxEl.querySelector(`#ai-status-${img.id}`);
  if (statusContainer) {
    statusContainer.innerHTML = `
      <div class="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-xs font-semibold animate-pulse">
        <i class="fa-solid fa-circle-notch fa-spin text-amber-600"></i>
        <span>AI Vision Analyzing...</span>
      </div>
    `;
  }

  try {
    const puter = await loadPuter();

    // Ensure user is authenticated to Puter if needed
    if (!puter.auth.isSignedIn()) {
      try {
        if (typeof showToast === "function") showToast("Connecting to Puter account...", "info");
        const user = await puter.auth.signIn();
        updatePuterAuthUI();
        if (typeof showToast === "function") showToast(`Puter connected: @${user?.username || 'User'}`, "success");
      } catch (authErr) {
        if (statusContainer) {
          statusContainer.innerHTML = `
            <div class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs">
              <i class="fa-solid fa-circle-exclamation text-amber-500"></i>
              <span>Puter login needed</span>
              <button class="ai-connect-btn underline hover:text-blue-600 font-semibold ml-1">Connect</button>
            </div>
          `;
          statusContainer.querySelector(".ai-connect-btn")?.addEventListener("click", () => {
            analyzeImageWithPuter(img, boxEl);
          });
        }
        return;
      }
    }

    const base64Img = await getBase64ImageFromUrl(img.url);
    const targetText = img.text || img.description || "target object";

    const prompt = `Inspect the provided image carefully. The image is a 3x3 grid containing 9 cells. The cells are numbered 1 to 9, reading left to right, top to bottom like this:
[1] [2] [3]
[4] [5] [6]
[7] [8] [9]

Your task is to find all cells that clearly contain ALL of the following objects: "${targetText}".
Return a comma-separated list of the cell numbers that match. If no cells match, return "None".
Do not include any other text, reasoning, or punctuation besides the numbers.`;

    const selectedModel = document.getElementById("ai-model-select")?.value || "gemini-2.5-flash";
    console.log(`⏳ Sending image to Puter AI (${selectedModel})... Client: "${img.client_id || 'unknown'}" Target: "${targetText}"`);
    let response = null;
    try {
      response = await puter.ai.chat(prompt, base64Img, { model: selectedModel });
    } catch (err1) {
      console.warn(`Model ${selectedModel} failed, trying fallback model...`, err1);
      const fallbackModel = selectedModel.includes("gemini") ? "claude-3-5-sonnet" : "gemini-2.5-flash";
      response = await puter.ai.chat(prompt, base64Img, { model: fallbackModel });
    }
    const rawText = parseAiResponse(response);
    console.log(`✅ [${img.client_id || 'Client'}] AI Output received:`, rawText);

    const uniqueMatches = extractMatchedCells(rawText);

    // Save result to backend
    try {
      await fetch(`/api/v1/images/${img.id}/ai-result`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          matched_cells: uniqueMatches,
          raw_output: rawText,
          model: selectedModel
        })
      });
    } catch (saveErr) {
      console.warn("Could not save AI result to backend:", saveErr);
    }

    img.matched_cells = uniqueMatches;
    img.ai_result = { matched_cells: uniqueMatches, raw_output: rawText, model: selectedModel };

    renderAiStatus(img, boxEl);
    if (typeof showToast === "function") {
      showToast(`[${img.client_id || 'Client'}] Solved: [${uniqueMatches.length ? uniqueMatches.join(", ") : "None"}]`, "success");
    }
  } catch (err) {
    console.error("❌ Puter AI Analysis failed:", err);
    if (statusContainer) {
      statusContainer.innerHTML = `
        <div class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs">
          <i class="fa-solid fa-triangle-exclamation text-rose-500"></i>
          <span>AI failed</span>
          <button class="ai-retry-btn underline hover:text-rose-900 ml-1 font-semibold">Retry</button>
        </div>
      `;
      statusContainer.querySelector(".ai-retry-btn")?.addEventListener("click", () => {
        analyzeImageWithPuter(img, boxEl);
      });
    }
  }
}

function renderAiStatus(img, boxEl) {
  const statusContainer = boxEl.querySelector(`#ai-status-${img.id}`);
  if (!statusContainer) return;

  const matched = img.matched_cells || (img.ai_result && img.ai_result.matched_cells);
  if (matched !== undefined && matched !== null) {
    if (matched.length > 0) {
      statusContainer.innerHTML = `
        <div class="flex flex-col items-center gap-1.5">
          <div class="inline-flex items-center gap-2 px-3 py-1 bg-emerald-50 border border-emerald-200/80 rounded-xl text-emerald-800 text-xs font-semibold shadow-sm">
            <i class="fa-solid fa-bullseye text-emerald-600"></i>
            <span>Output:</span>
            <div class="flex items-center gap-1">
              ${matched.map(n => `<span class="px-2 py-0.5 rounded-md bg-emerald-600 text-white font-mono font-bold text-xs shadow-sm">${n}</span>`).join("")}
            </div>
          </div>
          <div class="text-[10px] text-slate-400 font-mono flex items-center gap-1">
            <i class="fa-solid fa-clock-rotate-left text-slate-400"></i>
            <span>Auto-clean in ~4s</span>
          </div>
        </div>
      `;
    } else {
      statusContainer.innerHTML = `
        <div class="flex flex-col items-center gap-1.5">
          <div class="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-50 border border-slate-200 rounded-xl text-slate-600 text-xs font-medium">
            <i class="fa-solid fa-ban text-slate-400"></i>
            <span>Output: None</span>
          </div>
          <div class="text-[10px] text-slate-400 font-mono flex items-center gap-1">
            <i class="fa-solid fa-clock-rotate-left text-slate-400"></i>
            <span>Auto-clean in ~4s</span>
          </div>
        </div>
      `;
    }
  } else {
    statusContainer.innerHTML = `
      <div class="inline-flex items-center gap-1.5 px-3 py-1 bg-blue-50 border border-blue-200/80 rounded-xl text-blue-700 text-xs font-semibold animate-pulse">
        <i class="fa-solid fa-circle-notch fa-spin text-blue-600"></i>
        <span>Puter AI Analyzing...</span>
      </div>
    `;
    enqueueAiTask(img, boxEl);
  }
}

// Render a single Image Box HTML Element
function createImageBoxElement(img, boxIndex) {
  const box = document.createElement("div");
  box.className = "image-card-box fade-in-entry group bg-white border border-slate-200/80 rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition";
  box.id = `image-box-${img.id}`;
  box.setAttribute("data-client-id", (img.client_id || "").toLowerCase());
  box.setAttribute("data-text", (img.text || img.description || img.filename || "").toLowerCase());

  const displayText = img.text || img.description || img.filename || "Untitled Image";

  box.innerHTML = `
    <!-- Box Header: Index Number, Client Browser ID & Time -->
    <div class="px-4 py-2.5 bg-slate-50/80 border-b border-slate-100 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="px-2.5 py-0.5 rounded-lg bg-blue-600 text-white font-mono text-xs font-bold shadow-sm">
          #${boxIndex}
        </span>
        ${img.client_id ? `
          <span class="px-2 py-0.5 rounded-lg bg-blue-50 text-blue-700 font-mono text-[11px] border border-blue-200 flex items-center gap-1" title="Browser Client: ${img.client_id}">
            <i class="fa-solid fa-globe text-[10px] text-blue-500"></i>
            <span>${img.client_id}</span>
          </span>
        ` : ''}
      </div>
      <div class="flex items-center space-x-2">
        <span class="text-[11px] text-slate-400 font-mono" title="${formatFullDate(img.created_at)}">
          ${formatDate(img.created_at)}
        </span>
        <a href="/api/v1/images/${img.id}/download" download class="text-slate-400 hover:text-blue-600 transition px-1" title="Download Image">
          <i class="fa-solid fa-download text-xs"></i>
        </a>
        <button class="box-delete-btn text-slate-400 hover:text-rose-500 transition px-1" title="Delete Image">
          <i class="fa-solid fa-trash-can text-xs"></i>
        </button>
      </div>
    </div>

    <!-- Image Display Box -->
    <div class="image-card-preview bg-slate-950" title="Click to view full image">
      <img src="${img.url}" alt="${displayText}" loading="lazy">
      <div class="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
        <span class="px-3.5 py-1.5 bg-white text-slate-800 text-xs rounded-xl font-bold shadow-lg pointer-events-none">
          <i class="fa-solid fa-expand mr-1 text-blue-600"></i> Expand
        </span>
      </div>
    </div>

    <!-- Centered User Sent Text (e.g. Blone and moon / House) -->
    <div class="px-4 pt-3.5 pb-1 bg-white border-t border-slate-100 text-center">
      <h3 class="font-bold text-sm text-slate-900 tracking-tight break-words">
        ${displayText}
      </h3>
    </div>

    <!-- AI Vision Output Area (Puter.js Gemini) -->
    <div class="px-4 pb-3.5 pt-1 bg-white text-center">
      <div id="ai-status-${img.id}" class="ai-status-container flex items-center justify-center min-h-[30px]">
      </div>
    </div>
  `;

  // Attach event listeners for this box
  const previewArea = box.querySelector(".image-card-preview");
  const deleteBtn = box.querySelector(".box-delete-btn");

  const openModal = () => {
    const modal = document.getElementById("image-modal");
    const modalImg = document.getElementById("modal-image-el");
    const modalTitle = document.getElementById("modal-image-title");
    if (modal && modalImg) {
      modalImg.src = img.url;
      modalTitle.textContent = displayText;
      modal.classList.remove("hidden");
    }
  };

  previewArea.addEventListener("click", openModal);

  deleteBtn.addEventListener("click", async () => {
    // Immediately animate and remove box from screen
    box.style.transform = "scale(0.9)";
    box.style.opacity = "0";
    setTimeout(() => box.remove(), 200);

    allImages = allImages.filter(i => i.id !== img.id);
    updateScreenImagesCount();
    loadStats();
    if (allImages.length === 0) showEmptyPlaceholder();
    else applyFilter();

    try {
      const token = localStorage.getItem("auth_token");
      const headers = token ? { "Authorization": `Bearer ${token}` } : {};
      await fetch(`/api/v1/images/${img.id}`, { method: "DELETE", headers });
      if (typeof showToast === "function") showToast(`Image "${img.filename || 'image'}" deleted`, "success");
    } catch (e) {
      console.warn("Backend delete error:", e);
    }
  });

  renderAiStatus(img, box);
  return box;
}

// Show empty state placeholder
function showEmptyPlaceholder() {
  const container = document.getElementById("image-boxes-container");
  const emptyPlaceholder = document.getElementById("empty-stream-placeholder");
  const noSearchResults = document.getElementById("no-search-results");
  if (container) container.innerHTML = "";
  if (noSearchResults) noSearchResults.classList.add("hidden");
  if (emptyPlaceholder) emptyPlaceholder.classList.remove("hidden");
}

// Apply live client-side search filter
function applyFilter() {
  const container = document.getElementById("image-boxes-container");
  const emptyPlaceholder = document.getElementById("empty-stream-placeholder");
  const noSearchResults = document.getElementById("no-search-results");
  const clearBtn = document.getElementById("clear-search-btn");

  if (allImages.length === 0) {
    showEmptyPlaceholder();
    if (clearBtn) clearBtn.classList.add("hidden");
    return;
  }

  if (emptyPlaceholder) emptyPlaceholder.classList.add("hidden");

  if (!currentFilterQuery) {
    if (clearBtn) clearBtn.classList.add("hidden");
    if (noSearchResults) noSearchResults.classList.add("hidden");
    // Show all boxes
    const boxes = container?.querySelectorAll(".image-card-box");
    boxes?.forEach(b => b.classList.remove("hidden"));
    return;
  }

  if (clearBtn) clearBtn.classList.remove("hidden");

  let matchCount = 0;
  const boxes = container?.querySelectorAll(".image-card-box");
  boxes?.forEach(b => {
    const cId = b.getAttribute("data-client-id") || "";
    const txt = b.getAttribute("data-text") || "";
    if (cId.includes(currentFilterQuery) || txt.includes(currentFilterQuery)) {
      b.classList.remove("hidden");
      matchCount++;
    } else {
      b.classList.add("hidden");
    }
  });

  if (matchCount === 0) {
    if (noSearchResults) noSearchResults.classList.remove("hidden");
  } else {
    if (noSearchResults) noSearchResults.classList.add("hidden");
  }
}

// Render all images to the container
function renderImageBoxes() {
  const container = document.getElementById("image-boxes-container");
  const emptyPlaceholder = document.getElementById("empty-stream-placeholder");
  if (!container) return;

  container.innerHTML = "";

  if (allImages.length === 0) {
    showEmptyPlaceholder();
    return;
  }

  if (emptyPlaceholder) emptyPlaceholder.classList.add("hidden");

  // Sort chronological (first image in Box #1, second in Box #2, etc.)
  const sorted = [...allImages].sort((a, b) => {
    const da = new Date(a.created_at).getTime();
    const db = new Date(b.created_at).getTime();
    return da - db;
  });

  sorted.forEach((img, idx) => {
    const boxNumber = idx + 1;
    const boxEl = createImageBoxElement(img, boxNumber);
    container.appendChild(boxEl);
  });

  updateScreenImagesCount();
  applyFilter();
}

// Fetch images from API
async function loadImages() {
  try {
    const res = await fetch(`/api/v1/images?page=1&page_size=${pageSize}&status=active`);
    if (!res.ok) return;
    const data = await res.json();

    allImages = data.images || [];
    renderImageBoxes();
  } catch (err) {
    console.error("Error loading images:", err);
  }
}

// AI Model Setting: Fetch and Switch Logic
async function loadAiModelSetting() {
  const selectEl = document.getElementById("ai-model-select");
  const displayEl = document.getElementById("stat-ai-model-display");
  if (!selectEl) return;

  try {
    const res = await fetch("/api/v1/settings/ai-model");
    if (!res.ok) return;
    const data = await res.json();

    selectEl.value = data.active_model;
    if (displayEl) displayEl.textContent = data.active_model;
  } catch (err) {
    console.error("Error loading AI model setting:", err);
  }
}

function initAiModelSelector() {
  const selectEl = document.getElementById("ai-model-select");
  const displayEl = document.getElementById("stat-ai-model-display");
  const statusEl = document.getElementById("model-save-status");
  if (!selectEl) return;

  selectEl.addEventListener("change", async (e) => {
    const newModel = e.target.value;
    if (statusEl) statusEl.textContent = "Saving...";

    try {
      const res = await fetch("/api/v1/settings/ai-model", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: newModel })
      });

      if (res.ok) {
        const data = await res.json();
        if (displayEl) displayEl.textContent = data.active_model;
        if (statusEl) {
          statusEl.textContent = "Saved";
          setTimeout(() => { statusEl.textContent = ""; }, 2500);
        }
        if (typeof showToast === "function") {
          showToast(`AI Model switched to ${data.active_model_name}`, "success");
        }
      } else {
        const err = await res.json();
        if (statusEl) statusEl.textContent = "Error";
        if (typeof showToast === "function") showToast(err.detail || "Failed to update AI model", "error");
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = "Error";
      if (typeof showToast === "function") showToast("Network error updating AI model", "error");
    }
  });
}

// Non-destructive box addition (preserves existing running DOM elements)
function addOrUpdateImageBox(img) {
  const container = document.getElementById("image-boxes-container");
  const emptyPlaceholder = document.getElementById("empty-stream-placeholder");
  if (!container) return;

  if (emptyPlaceholder) emptyPlaceholder.classList.add("hidden");

  let existingBox = document.getElementById(`image-box-${img.id}`);
  if (existingBox) {
    renderAiStatus(img, existingBox);
    return;
  }

  const boxNumber = allImages.findIndex(i => i.id === img.id) + 1 || allImages.length;
  const boxEl = createImageBoxElement(img, boxNumber);
  container.appendChild(boxEl);
  updateScreenImagesCount();
  applyFilter();
}

// Toolbar Actions: Clear All, Refresh, Filter
function initToolbarActions() {
  // Clear All Button
  const clearBtn = document.getElementById("toolbar-clear-btn");
  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      // 1. Instantly wipe all cards from screen for immediate visual response
      const container = document.getElementById("image-boxes-container");
      if (container) {
        container.innerHTML = "";
      }
      allImages = [];
      showEmptyPlaceholder();
      updateScreenImagesCount();

      // Show brief spinner on button icon
      const icon = clearBtn.querySelector("i");
      if (icon) icon.className = "fa-solid fa-circle-notch fa-spin text-rose-500";

      try {
        const token = localStorage.getItem("auth_token");
        const headers = token ? { "Authorization": `Bearer ${token}` } : {};

        // 2. Call backend DELETE endpoint (with fallback to POST)
        let res = await fetch("/api/v1/images/clear/all", { method: "DELETE", headers });
        if (!res.ok) {
          res = await fetch("/api/v1/images/clear/all", { method: "POST", headers });
        }

        await loadStats();
        if (typeof showToast === "function") {
          showToast("All images cleared successfully.", "success");
        }
      } catch (err) {
        console.warn("Clear all error:", err);
        if (typeof showToast === "function") {
          showToast("Images cleared from screen.", "info");
        }
      } finally {
        if (icon) icon.className = "fa-regular fa-trash-can text-slate-400";
      }
    });
  }

  // Refresh Button
  const refreshBtn = document.getElementById("toolbar-refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      refreshBtn.querySelector("i")?.classList.add("fa-spin");
      await Promise.all([loadStats(), loadImages()]);
      setTimeout(() => {
        refreshBtn.querySelector("i")?.classList.remove("fa-spin");
      }, 500);
      if (typeof showToast === "function") showToast("Stream refreshed.", "info");
    });
  }

  // Live Filter Input
  const searchInput = document.getElementById("image-search-input");
  const clearSearchBtn = document.getElementById("clear-search-btn");
  const resetFilterBtn = document.getElementById("reset-filter-btn");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      currentFilterQuery = e.target.value.trim().toLowerCase();
      applyFilter();
    });
  }

  if (clearSearchBtn) {
    clearSearchBtn.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      currentFilterQuery = "";
      applyFilter();
    });
  }

  if (resetFilterBtn) {
    resetFilterBtn.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      currentFilterQuery = "";
      applyFilter();
    });
  }
}

// WebSocket Live Event Listener
window.addEventListener("ws_event", (e) => {
  const { type, data } = e.detail;

  if (type === "image_received") {
    const sender = data.client_id ? `[${data.client_id}]` : "";
    if (typeof showToast === "function") showToast(`New image received ${sender}: ${data.filename}`, "success");

    if (!allImages.some(img => img.id === data.id)) {
      allImages.push(data);
    }

    addOrUpdateImageBox(data);
    loadStats();
  } else if (type === "ai_result_ready") {
    const targetImg = allImages.find(i => i.id === data.id);
    if (targetImg) {
      targetImg.matched_cells = data.matched_cells;
      targetImg.ai_result = data;
      const targetBox = document.getElementById(`image-box-${data.id}`);
      if (targetBox) renderAiStatus(targetImg, targetBox);
    }
  } else if (type === "image_deleted") {
    allImages = allImages.filter(img => img.id !== data.id);
    const existingBox = document.getElementById(`image-box-${data.id}`);
    if (existingBox) {
      existingBox.style.transform = "scale(0.9)";
      existingBox.style.opacity = "0";
      setTimeout(() => existingBox.remove(), 250);
    }
    updateScreenImagesCount();
    loadStats();
    if (allImages.length === 0) showEmptyPlaceholder();
    else applyFilter();
  } else if (type === "all_images_cleared") {
    allImages = [];
    showEmptyPlaceholder();
    updateScreenImagesCount();
    loadStats();
  } else if (type === "queue_updated") {
    const elQueued = document.getElementById("stat-queued-images");
    if (elQueued && data.queued_count !== undefined) {
      elQueued.textContent = data.queued_count.toLocaleString();
    }
  }
});

// Fullscreen Modal Close Listeners
const modal = document.getElementById("image-modal");
if (modal) {
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });
}

// Boot initialization
document.addEventListener("DOMContentLoaded", () => {
  loadStats();
  loadImages();
  loadAiModelSetting();
  initAiModelSelector();
  initToolbarActions();
  updatePuterAuthUI();
});
