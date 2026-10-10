// API Test Console Logic

let selectedFile = null;

// Populate API keys dropdown
async function populateKeysDropdown() {
  const dropdown = document.getElementById("key-selector-dropdown");
  if (!dropdown) return;

  try {
    const res = await fetch("/api/v1/api-keys");
    if (!res.ok) return;
    const keys = await res.json();

    dropdown.innerHTML = '<option value="">-- Choose an existing active key --</option>';
    keys.filter(k => k.is_active).forEach((k) => {
      const opt = document.createElement("option");
      opt.value = k.masked_key;
      opt.textContent = `${k.name} (${k.masked_key})`;
      dropdown.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading keys for test:", err);
  }
}

// File drop zone handling
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("test-file-input");
const fileLabel = document.getElementById("selected-file-label");

if (dropZone && fileInput) {
  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("border-blue-500", "bg-slate-900");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("border-blue-500", "bg-slate-900");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("border-blue-500", "bg-slate-900");
    if (e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });
}

function handleFileSelected(file) {
  selectedFile = file;
  if (fileLabel) {
    fileLabel.innerHTML = `<span class="text-emerald-400 font-bold">${file.name}</span> (${(file.size / 1024).toFixed(1)} KB)`;
  }
}

// Key selector sync
const keyDropdown = document.getElementById("key-selector-dropdown");
const manualKeyInput = document.getElementById("manual-api-key-input");

if (keyDropdown && manualKeyInput) {
  keyDropdown.addEventListener("change", () => {
    if (keyDropdown.value) {
      manualKeyInput.placeholder = "Enter full raw PS_... key for selected item";
    }
  });
}

// Submit test request
const testForm = document.getElementById("api-test-form");
const sendBtn = document.getElementById("send-request-btn");
const statusBadge = document.getElementById("response-status-badge");
const latencyBadge = document.getElementById("response-latency-badge");
const jsonViewer = document.getElementById("response-json-viewer");
const previewBox = document.getElementById("test-preview-box");
const previewImg = document.getElementById("test-preview-img");
const previewName = document.getElementById("test-preview-name");
const previewLink = document.getElementById("test-preview-link");

if (testForm) {
  testForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const apiKey = manualKeyInput.value.trim();
    if (!apiKey) {
      showToast("Please provide an API key", "warning");
      return;
    }
    if (!selectedFile) {
      showToast("Please choose or drop an image file", "warning");
      return;
    }

    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i><span>Uploading...</span>';
    previewBox.classList.add("hidden");
    jsonViewer.textContent = "// Sending request...";

    const formData = new FormData();
    formData.append("file", selectedFile);

    const customFilename = document.getElementById("test-custom-filename").value.trim();
    if (customFilename) formData.append("filename", customFilename);

    const clientId = document.getElementById("test-client-id").value.trim();
    if (clientId) formData.append("client_id", clientId);

    const textInput = document.getElementById("test-text");
    const userText = textInput ? textInput.value.trim() : "";
    if (userText) {
      formData.append("text", userText);
      formData.append("description", userText);
    }

    const startTime = performance.now();
    try {
      const res = await fetch("/api/v1/images", {
        method: "POST",
        headers: {
          "X-API-Key": apiKey
        },
        body: formData
      });

      const endTime = performance.now();
      const latency = Math.round(endTime - startTime);

      const data = await res.json();

      // Display Status & Latency
      statusBadge.classList.remove("hidden");
      latencyBadge.classList.remove("hidden");
      statusBadge.textContent = `${res.status} ${res.statusText || (res.ok ? "Created" : "Error")}`;
      latencyBadge.textContent = `${latency} ms`;

      if (res.ok) {
        statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
        showToast("Image uploaded successfully!", "success");

        // Display preview
        if (data.image) {
          previewBox.classList.remove("hidden");
          previewImg.src = data.image.url;
          previewName.textContent = data.image.filename;
          previewLink.href = data.image.url;
        }
      } else {
        statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-rose-500/20 text-rose-400 border border-rose-500/30";
        showToast(`Request failed: ${data.error?.message || "HTTP " + res.status}`, "error");
      }

      // Format JSON Viewer
      jsonViewer.textContent = JSON.stringify(data, null, 2);

    } catch (err) {
      statusBadge.classList.remove("hidden");
      statusBadge.className = "px-2.5 py-0.5 rounded-full text-xs font-bold font-mono bg-rose-500/20 text-rose-400";
      statusBadge.textContent = "Network Error";
      jsonViewer.textContent = `// Network or CORS error:\n${err.message}`;
      showToast("Network error executing test", "error");
    } finally {
      sendBtn.disabled = false;
      sendBtn.innerHTML = '<i class="fa-solid fa-bolt"></i><span>Send POST /api/v1/images</span>';
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  populateKeysDropdown();
});
