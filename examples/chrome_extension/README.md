# 9-Grid CAPTCHA AI Solver — Chrome Extension

A **Chrome Extension (Manifest V3)** that automatically solves 9-cell grid CAPTCHA challenges by integrating with your **Pure Receiver** backend and **Puter AI**.

---

## 📁 Extension Structure

```
chrome_extension/
├── manifest.json        ← Extension definition (MV3)
├── content.js           ← Injected into CAPTCHA pages — main solver logic
├── background.js        ← Service worker: config storage & message relay
├── popup.html           ← Extension popup UI (settings panel)
├── popup.js             ← Popup logic: load/save config, backend status check
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

---

## ⚡ How It Works

```
[CAPTCHA Page]
     │
     ├─ 1. Detect: .captcha-info strong (target text) + img.gr-image (grid image)
     │
     ├─ 2. Extract: Base64 PNG of the 3x3 grid image
     │
     ├─ 3. POST to Pure Receiver backend:
     │        POST /api/v1/images
     │        Headers: X-API-Key: PS_...
     │        Body: FormData { file, text, client_id }
     │
     ├─ 4. Backend sends to Puter AI (gemini-2.5-flash)
     │      • If slots < 12: processes immediately
     │      • If slots ≥ 12: queues in backend, waits for open slot
     │
     ├─ 5. Backend returns: matched_cells = [1, 4, 7]
     │
     ├─ 6. Extension clicks each matched cell on the grid
     │      • Retry up to 3x per cell if not selected
     │
     └─ 7. Clicks Next / Verify / Skip button to advance
```

---

## 🔧 Installation (Chrome)

1. Open Chrome → navigate to `chrome://extensions/`
2. Enable **Developer mode** (top-right toggle)
3. Click **"Load unpacked"**
4. Select the `chrome_extension/` folder
5. The extension icon 🤖 will appear in the toolbar

---

## ⚙️ Extension Popup (Streamlined Controls)

Click the toolbar icon 🤖 to open the extension popup:

* **🖼️ Image Solver: ON / OFF Switch (Default: ON)**
  * **ON (🟢 Active)**: Detects, uploads, solves, clicks matching cells, and advances stages automatically.
  * **OFF (⚪ Paused)**: Pauses all image detection and solving across the browser tab.
  * **Real-time Synchronization**: Changes apply instantly to all active tabs without needing to click a save button.

* **Pre-configured Defaults (Clean GUI, No Clutter)**:
  * **Backend URL**: `http://localhost:8000` (auto-connected)
  * **Default API Key**: `PS_900a2dbb943ac30d39ba1993ca3614379a04bb`
  * **Auto-clean**: 4 seconds delay before image deletion from backend.
  * *(Optional: A collapsed `⚙️ Advanced Config` section is available if you ever need to change URL or key).*

---

## 🌐 Multi-Browser Isolation

Each browser/tab generates a **unique `client_id`** stored in `localStorage`.  
The extension verifies that every AI response carries the matching `client_id` — ensuring Browser A never receives Browser B's output, even when 20+ users upload simultaneously.

---

## 🔄 Queue & 12-Active Limit

If 20+ users send images at the same moment:
- The **first 12** are processed immediately (active slots)
- The **remaining** are buffered in the backend queue
- When any active image finishes and deletes, the **next queued image auto-promotes**
- Your extension will simply wait for the backend's `wait_for_ai=true` response — no polling needed

---

## 🔁 Automatic Stage Progression

The extension handles **multi-stage CAPTCHAs** automatically:
- Tracks the current stage via `.bullets .bullet.active`
- Uses a unique per-stage **signature** to avoid re-processing the same grid
- After clicking cells → clicks **Next** (or **Skip** or **Verify**)
- MutationObserver + 2-second polling ensure every new grid is caught instantly

---

## 🛡️ Safety Features

- **Signature deduplication** — same grid never processed twice
- **Cell retry logic** — up to 3 retries per cell click with `sel` class verification
- **Client ID mismatch guard** — rejects AI responses not tagged with this browser's ID
