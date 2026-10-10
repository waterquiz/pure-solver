/**
 * ============================================================
 * 9-Grid CAPTCHA AI Solver — Content Script
 * ============================================================
 * Flow:
 *   1. Detect 9-grid CAPTCHA on page
 *   2. Extract: grid image (base64) + target text label
 *   3. POST to Pure Receiver backend → Puter AI processes it
 *   4. Receive matched_cells [] from backend
 *   5. Click each matched cell on the CAPTCHA grid
 *   6. Click Next / Verify / Skip button
 *   7. Repeat for every new stage automatically
 * ============================================================
 */

(function () {
  'use strict';

  // ─── State ────────────────────────────────────────────────────────────────
  let lastProcessedSignature = '';
  let isProcessing           = false;

  // ─── Config (loaded from chrome.storage.sync via message) ─────────────────
  let CONFIG = {
    backendUrl        : 'https://pure-solver-production.up.railway.app',
    apiKey            : 'PS_900a2dbb943ac30d39ba1993ca3614379a04bb',
    autoDelay         : 1000,   // ms to wait before clicking after receiving AI result
    waitForAi         : true,   // use wait_for_ai=true so upload blocks until result ready
    autoDeleteSeconds : 4,
    imageEnabled      : true    // Default: ON
  };

  // Ask background script for saved config on startup
  chrome.runtime.sendMessage({ type: 'GET_CONFIG' }, (cfg) => {
    if (cfg) {
      Object.assign(CONFIG, cfg);
      if (CONFIG.imageEnabled === false) {
        updateHud('Paused (Image: OFF)', 'PAUSED', '#94a3b8', '#94a3b820');
      }
    }
  });

  // Listen for config updates from popup
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === 'CONFIG_UPDATED' && msg.config) {
      Object.assign(CONFIG, msg.config);
      if (CONFIG.imageEnabled === false) {
        updateHud('Paused (Image: OFF)', 'PAUSED', '#94a3b8', '#94a3b820');
      } else {
        updateHud('Watching page...', 'IMAGE ON', '#22c55e', '#22c55e20');
      }
    }
  });

  // ─── Unique stable browser ID ─────────────────────────────────────────────
  function getBrowserId() {
    let id = localStorage.getItem('__captcha_solver_browser_id__');
    if (!id) {
      id = 'browser-' + Math.random().toString(36).slice(2, 10) + '-' + Date.now();
      localStorage.setItem('__captcha_solver_browser_id__', id);
    }
    return id;
  }
  const BROWSER_ID = getBrowserId();

  // ─── Helpers ──────────────────────────────────────────────────────────────
  function randomDelay(min = 600, max = 1400) {
    return new Promise(r => setTimeout(r, Math.floor(Math.random() * (max - min + 1)) + min));
  }

  function getBase64Image(img) {
    if (img.src && img.src.startsWith('data:image/')) return img.src;
    const canvas = document.createElement('canvas');
    canvas.width  = img.naturalWidth  || img.width  || 300;
    canvas.height = img.naturalHeight || img.height || 300;
    try {
      canvas.getContext('2d').drawImage(img, 0, 0);
      return canvas.toDataURL('image/png');
    } catch (e) {
      console.warn('[Solver] Canvas tainted – returning src directly:', e.message);
      return img.src;
    }
  }

  function isCellSelected(cellEl) {
    return !!(cellEl && cellEl.classList.contains('sel'));
  }

  function getStageIndex() {
    const bullets = document.querySelectorAll('.bullets .bullet');
    for (let i = 0; i < bullets.length; i++) {
      if (bullets[i].classList.contains('active')) return i + 1;
    }
    return 1;
  }

  function findButtonByLabel(label) {
    const l = label.toLowerCase();
    const buttons = document.querySelectorAll('button, .button, input[type="button"], input[type="submit"]');
    for (const btn of buttons) {
      const span = btn.querySelector('span.label, .btn-label, .text');
      const spanText = (span?.textContent || '').trim().toLowerCase();
      if (spanText === l || spanText.includes(l)) return btn;

      const directText = (btn.textContent || '').trim().toLowerCase();
      if (directText === l || directText.includes(l)) return btn;

      const val = (btn.value || '').trim().toLowerCase();
      if (val === l || val.includes(l)) return btn;

      const aria = (btn.getAttribute('aria-label') || '').trim().toLowerCase();
      if (aria === l || aria.includes(l)) return btn;
    }
    return null;
  }

  function isButtonReady(btn) {
    if (!btn || btn.disabled) return false;
    const s = window.getComputedStyle(btn);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const rect = btn.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  // ─── Standard CAPTCHA grid click ─────────────────────────────────────────
  async function humanClick(el) {
    if (typeof el.click === 'function') el.click();
    const rect    = el.getBoundingClientRect();
    const clientX = rect.left + rect.width  / 2;
    const clientY = rect.top  + rect.height / 2;
    const opts    = { bubbles: true, cancelable: true, clientX, clientY };
    el.dispatchEvent(new PointerEvent('pointerdown', opts));
    el.dispatchEvent(new MouseEvent ('mousedown',    opts));
    await new Promise(r => setTimeout(r, 60));
    el.dispatchEvent(new PointerEvent('pointerup',   opts));
    el.dispatchEvent(new MouseEvent ('mouseup',      opts));
  }

  async function selectCellWithRetry(cellEl) {
    for (let attempt = 1; attempt <= 3; attempt++) {
      if (isCellSelected(cellEl)) return true;
      await humanClick(cellEl);
      await new Promise(r => setTimeout(r, 400));
      if (isCellSelected(cellEl)) return true;
      await randomDelay(400, 700);
    }
    return false;
  }

  // ─── Next / Verify / Skip ─────────────────────────────────────────────────
  async function clickNextOrVerify() {
    await randomDelay(1200, 2200);
    for (let attempt = 0; attempt < 15; attempt++) {
      const nextBtn   = findButtonByLabel('Next') || findButtonByLabel('Skip');
      const verifyBtn = findButtonByLabel('Verify');
      const submitBtn = findButtonByLabel('Submit');
      const notFoundBtn = findButtonByLabel('Object not found') || findButtonByLabel('Not found');

      const target = (nextBtn && isButtonReady(nextBtn)) ? nextBtn
                   : (verifyBtn && isButtonReady(verifyBtn)) ? verifyBtn
                   : (notFoundBtn && isButtonReady(notFoundBtn)) ? notFoundBtn
                   : (submitBtn && isButtonReady(submitBtn)) ? submitBtn
                   : null;

      if (target) {
        console.log(`[Solver] 🎯 Found button: "${target.textContent?.trim() || target.value || 'Action'}" -> Clicking`);
        await humanClick(target);
        return;
      }
      await new Promise(r => setTimeout(r, 500));
    }
    console.warn('[Solver] Could not find Next / Verify / Submit button.');
  }

  // ─── On-Screen Live Status HUD (Heads-Up Display) ─────────────────────────
  let hudEl = null;
  function initHud() {
    if (hudEl || !document.body) return;
    hudEl = document.createElement('div');
    hudEl.id = '__captcha_solver_hud__';
    hudEl.innerHTML = `
      <div style="
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 2147483640;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 12px 16px;
        color: #0f172a;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        font-size: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.08);
        min-width: 220px;
        user-select: none;
        transition: all 0.2s ease;
      ">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
          <div style="display: flex; align-items: center; gap: 6px; font-weight: 800; color: #2563eb;">
            <span>⚡</span>
            <span>Pure Solver</span>
          </div>
          <span id="__hud_badge__" style="
            background: #eff6ff;
            color: #2563eb;
            border: 1px solid #bfdbfe;
            border-radius: 6px;
            font-size: 10px;
            padding: 2px 7px;
            font-weight: 700;
          ">ACTIVE</span>
        </div>
        <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">
          Client: <strong style="color: #0f172a;" id="__hud_client__">${BROWSER_ID}</strong>
        </div>
        <div style="font-size: 11px; color: #64748b;">
          Status: <span id="__hud_status__" style="color: #2563eb; font-weight: 600;">Watching page...</span>
        </div>
      </div>
    `;
    document.body.appendChild(hudEl);
  }

  function updateHud(statusText, badgeText = 'ACTIVE', badgeColor = '#4ade80', badgeBg = '#22c55e20') {
    initHud();
    const statusSpan = document.getElementById('__hud_status__');
    const badgeSpan  = document.getElementById('__hud_badge__');
    if (statusSpan) statusSpan.textContent = statusText;
    if (badgeSpan) {
      badgeSpan.textContent = badgeText;
      badgeSpan.style.color = badgeColor;
      badgeSpan.style.background = badgeBg;
      badgeSpan.style.borderColor = badgeColor + '40';
    }
  }

  // ─── Core: Send image + text to backend, receive matched cells ────────────
  async function fetchAiResultFromBackend(base64DataUrl, targetText) {
    if (!CONFIG.apiKey) {
      console.error('[Solver] ❌ No API Key configured. Open the extension popup to set it.');
      updateHud('Missing API Key! Open extension popup.', 'CONFIG ERROR', '#ef4444', '#ef444420');
      return null;
    }

    updateHud(`Uploading image to Pure Receiver...`, 'UPLOADING', '#f59e0b', '#f59e0b20');

    // Convert base64 data URL → Blob → File
    const [header, data] = base64DataUrl.split(',');
    const mime           = header.match(/:(.*?);/)[1];
    const byteChars      = atob(data);
    const byteArr        = new Uint8Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) byteArr[i] = byteChars.charCodeAt(i);
    const blob = new Blob([byteArr], { type: mime });
    const file = new File([blob], 'captcha_grid.png', { type: mime });

    const fd = new FormData();
    fd.append('file', file);
    fd.append('text', targetText);
    fd.append('client_id', BROWSER_ID);

    const url = `${CONFIG.backendUrl}/api/v1/images?wait_for_ai=${CONFIG.waitForAi}&auto_delete_seconds=${CONFIG.autoDeleteSeconds}`;

    try {
      const res = await fetch(url, {
        method  : 'POST',
        headers : { 'X-API-Key': CONFIG.apiKey },
        body    : fd
      });

      if (!res.ok) {
        const errBody = await res.text();
        console.error('[Solver] ❌ Backend error', res.status, errBody);
        updateHud(`Error ${res.status}: ${errBody.slice(0, 30)}`, 'ERROR', '#ef4444', '#ef444420');
        return null;
      }

      const json = await res.json();
      console.log('[Solver] 📨 Backend response:', json);

      // Verify the response belongs to THIS browser
      if (json.client_id && json.client_id !== BROWSER_ID) {
        console.warn('[Solver] ⚠️ Response client_id mismatch! Expected:', BROWSER_ID, 'Got:', json.client_id);
        return null;
      }

      // If already solved directly:
      if (json.matched_cells && Array.isArray(json.matched_cells)) {
        return json.matched_cells;
      }

      // If buffered in backend queue (when >12 images active on screen):
      if (json.status === 'queued' || (json.image_id && !json.matched_cells)) {
        updateHud('Queued in backend (waiting for slot)...', 'QUEUED', '#a855f7', '#a855f720');
        console.log('[Solver] ⏳ Image queued in backend buffer. Polling for resolution...');

        const pollImgId = json.image_id;
        // Poll every 1.5s up to 60s
        for (let p = 0; p < 40; p++) {
          await new Promise(r => setTimeout(r, 1500));
          try {
            const checkUrl = `${CONFIG.backendUrl}/api/v1/images/by-client/${BROWSER_ID}/latest/result`;
            const checkRes = await fetch(checkUrl, {
              headers: { 'X-API-Key': CONFIG.apiKey }
            });
            if (checkRes.ok) {
              const checkJson = await checkRes.json();
              if (checkJson.status === 'completed' && Array.isArray(checkJson.matched_cells)) {
                console.log('[Solver] 🎯 Queued image resolved! Cells:', checkJson.matched_cells);
                return checkJson.matched_cells;
              }
            }
          } catch (pollErr) {
            console.warn('[Solver] Poll attempt error:', pollErr);
          }
        }
      }

      return json.matched_cells || [];
    } catch (err) {
      console.error('[Solver] ❌ Network error sending to backend:', err);
      updateHud('Network connection failed', 'OFFLINE', '#ef4444', '#ef444420');
      return null;
    }
  }

  // ─── CAPTCHA solving pipeline ─────────────────────────────────────────────
  async function processCaptchaGrid() {
    const textEl   = document.querySelector('.captcha-info strong');
    const gridWrap = document.querySelector('.grid-wrap');
    const mainImg  = gridWrap?.querySelector('img.gr-image');

    if (!textEl || !mainImg) return;

    const targetText    = textEl.textContent.trim();
    const currentStage  = getStageIndex();
    const signature     = `Stage${currentStage}_${targetText}_${mainImg.src.slice(0, 80)}`;

    if (signature === lastProcessedSignature) return;

    // Wait for image to fully load
    if (!mainImg.complete || mainImg.naturalWidth === 0) {
      mainImg.onload = () => checkPage();
      return;
    }

    isProcessing           = true;
    lastProcessedSignature = signature;

    await new Promise(r => setTimeout(r, 800));

    console.log(`\n${'='.repeat(50)}`);
    console.log(`[Solver] 🎯 STAGE ${currentStage} | Target: "${targetText}"`);
    console.log(`[Solver] 🌐 Browser ID: ${BROWSER_ID}`);
    console.log(`${'='.repeat(50)}`);

    updateHud(`Stage ${currentStage}: "${targetText}"`, 'CAPTCHA FOUND', '#38bdf8', '#38bdf820');

    try {
      // 1️⃣  Extract image as base64
      const base64Img = getBase64Image(mainImg);
      console.log('[Solver] 📸 Image captured, sending to backend…');

      // 2️⃣  Send to Pure Receiver backend → Puter AI processes it
      const matchedCells = await fetchAiResultFromBackend(base64Img, targetText);

      if (!matchedCells) {
        console.error('[Solver] ❌ No AI result received. Skipping stage.');
        updateHud('No response received. Advancing...', 'SKIPPING', '#f59e0b', '#f59e0b20');
        await clickNextOrVerify();
        isProcessing = false;
        return;
      }

      console.log('[Solver] 📊 AI matched cells:', matchedCells);
      updateHud(`AI Solved: Cells [${matchedCells.join(', ')}]`, 'SOLVED', '#22c55e', '#22c55e20');

      // 3️⃣  Small delay before clicking (human-like)
      await randomDelay(CONFIG.autoDelay, CONFIG.autoDelay + 600);

      // 4️⃣  Click each matched cell on the live CAPTCHA grid
      let successCount = 0;
      for (const cellNum of matchedCells) {
        updateHud(`Selecting cell ${cellNum}...`, 'CLICKING', '#a855f7', '#a855f720');
        await randomDelay(600, 1200);
        const liveCells = document.querySelectorAll('.grid-wrap .cell');
        const liveCell  = liveCells[cellNum - 1];
        if (liveCell) {
          const ok = await selectCellWithRetry(liveCell);
          if (ok) {
            successCount++;
            console.log(`[Solver] ✅ Cell ${cellNum} selected`);
          } else {
            console.warn(`[Solver] ⚠️ Cell ${cellNum} – selection failed`);
          }
        }
        await randomDelay(250, 500);
      }

      // 5️⃣  Click Next / Verify button
      updateHud('Clicking Next / Verify...', 'ADVANCING', '#3b82f6', '#3b82f620');
      if (successCount > 0 || matchedCells.length === 0) {
        if (matchedCells.length === 0) {
          console.log('[Solver] ℹ️ No matching cells (AI returned empty). Clicking Next/Verify to skip…');
        }
        await clickNextOrVerify();
      } else {
        console.warn('[Solver] ⚠️ Cells matched but website rejected clicks. Trying Verify anyway…');
        await clickNextOrVerify();
      }
      updateHud(`Stage ${currentStage} completed!`, 'WAITING', '#4ade80', '#22c55e20');

      // Update solve count in local storage
      try {
        chrome.storage.local.get(['solverStats'], (res) => {
          const stats = res?.solverStats || { used: 8750, limit: 12000 };
          stats.used = (stats.used || 8750) + 1;
          chrome.storage.local.set({ solverStats: stats });
        });
      } catch (_) {}

    } catch (err) {
      console.error('[Solver] ❌ Unexpected error:', err);
      updateHud('Unexpected error occurred', 'ERROR', '#ef4444', '#ef444420');
    } finally {
      isProcessing = false;
    }
  }

  // ─── Find Object ("oldsolver") CAPTCHA Solver ───────────────────────────
  function extractBackgroundBase64(el) {
    if (!el) return null;
    const bg = el.style.backgroundImage || el.style.background || window.getComputedStyle(el).backgroundImage;
    if (!bg) return null;
    const match = bg.match(/url\(['"]?(data:image\/[^'"]+)['"]?\)/i);
    return match ? match[1] : null;
  }

  function findButtonWithText(selector, textPatterns) {
    const btns = document.querySelectorAll(selector);
    for (const b of btns) {
      const txt = (b.textContent || '').trim().toLowerCase();
      for (const p of textPatterns) {
        if (txt === p.toLowerCase() || txt.includes(p.toLowerCase())) {
          return b;
        }
      }
    }
    return null;
  }

  async function processFindObjectCaptcha() {
    const commentEl = document.querySelector('.comment-row');
    const oldsolver = document.querySelector('.oldsolver');
    if (!commentEl || !oldsolver) return;

    // e.g. 'Find object "whale"' -> extracts whale or full text
    const rawComment = commentEl.textContent.trim();
    const quoteMatch = rawComment.match(/["'“]([^"'”]+)["'”]/);
    const targetObject = quoteMatch ? quoteMatch[1].trim() : rawComment.replace(/^find\s+object\s*:?/i, '').trim();

    // Get background image base64 or url
    let base64Img = extractBackgroundBase64(oldsolver);
    if (!base64Img) {
      // Check if child img exists
      const innerImg = oldsolver.querySelector('img');
      if (innerImg) {
        base64Img = getBase64Image(innerImg);
      }
    }

    if (!base64Img) {
      console.warn('[Solver] Could not extract image from .oldsolver');
      return;
    }

    const signature = `FindObj_${targetObject}_${base64Img.slice(0, 100)}`;
    if (signature === lastProcessedSignature) return;

    isProcessing = true;
    lastProcessedSignature = signature;

    await new Promise(r => setTimeout(r, 600));

    console.log(`\n${'='.repeat(50)}`);
    console.log(`[Solver] 🎯 FIND OBJECT CAPTCHA | Target: "${targetObject}"`);
    console.log(`[Solver] 🌐 Browser ID: ${BROWSER_ID}`);
    console.log(`${'='.repeat(50)}`);

    updateHud(`Find object: "${targetObject}"`, 'CAPTCHA FOUND', '#38bdf8', '#38bdf820');

    try {
      // Send image + text to Pure Receiver backend
      const matchedCells = await fetchAiResultFromBackend(base64Img, targetObject);

      console.log('[Solver] 📊 AI matched cells:', matchedCells);

      const submitBtn = document.querySelector('button.btn-submit') || 
                        findButtonWithText('button', ['submit']);
      const notFoundBtn = document.querySelector('button.btn-default') || 
                          findButtonWithText('button', ['object not found', 'not found']);

      await randomDelay(CONFIG.autoDelay, CONFIG.autoDelay + 600);

      if (!matchedCells || matchedCells.length === 0) {
        // AI found nothing (None)
        console.log('[Solver] ℹ️ Output is None/empty. Looking for "Object not found" or "Submit"...');

        if (notFoundBtn && isButtonReady(notFoundBtn)) {
          updateHud('Result: None → Object not found', 'NOT FOUND', '#f59e0b', '#f59e0b20');
          console.log('[Solver] 🎯 Found "Object not found" button. Clicking...');
          await humanClick(notFoundBtn);
        } else if (submitBtn && isButtonReady(submitBtn)) {
          updateHud('Result: None → Submit', 'SUBMITTING', '#f59e0b', '#f59e0b20');
          console.log('[Solver] 🎯 Found "Submit" button. Clicking Submit without selection...');
          await humanClick(submitBtn);
        } else {
          console.log('[Solver] Neither Object not found nor Submit found, trying Next/Verify fallback...');
          await clickNextOrVerify();
        }
      } else {
        // AI returned matching cell(s)
        updateHud(`AI Solved: Cell(s) [${matchedCells.join(', ')}]`, 'SOLVED', '#22c55e', '#22c55e20');

        // Check if oldsolver has cell elements or grid coordinates
        const cells = oldsolver.querySelectorAll('.cell, [data-cell], .grid-item');
        if (cells.length >= 9) {
          for (const cellNum of matchedCells) {
            const cellEl = cells[cellNum - 1];
            if (cellEl) {
              await humanClick(cellEl);
              await randomDelay(300, 600);
            }
          }
        } else {
          // If .oldsolver has no child cells, simulate click by 3x3 grid coordinates
          const rect = oldsolver.getBoundingClientRect();
          const cellWidth = rect.width / 3;
          const cellHeight = rect.height / 3;

          for (const cellNum of matchedCells) {
            const index = cellNum - 1;
            const col = index % 3;
            const row = Math.floor(index / 3);
            const clientX = rect.left + col * cellWidth + cellWidth / 2;
            const clientY = rect.top + row * cellHeight + cellHeight / 2;

            const opts = { bubbles: true, cancelable: true, clientX, clientY };
            oldsolver.dispatchEvent(new PointerEvent('pointerdown', opts));
            oldsolver.dispatchEvent(new MouseEvent('mousedown', opts));
            await new Promise(r => setTimeout(r, 60));
            oldsolver.dispatchEvent(new PointerEvent('pointerup', opts));
            oldsolver.dispatchEvent(new MouseEvent('mouseup', opts));
            oldsolver.dispatchEvent(new MouseEvent('click', opts));
            console.log(`[Solver] ✅ Clicked grid cell ${cellNum} at (${Math.round(clientX)}, ${Math.round(clientY)})`);
            await randomDelay(400, 700);
          }
        }

        // After selecting cell(s), click Submit button
        await randomDelay(600, 1000);
        updateHud('Clicking Submit...', 'SUBMITTING', '#2563eb', '#2563eb20');
        if (submitBtn && isButtonReady(submitBtn)) {
          await humanClick(submitBtn);
          console.log('[Solver] ✅ Submit button clicked');
        } else {
          console.warn('[Solver] Submit button not ready or not found');
        }
      }

      // Record solver stats
      try {
        chrome.storage.local.get(['solverStats'], (res) => {
          const stats = res?.solverStats || { used: 8750, limit: 12000 };
          stats.used = (stats.used || 8750) + 1;
          chrome.storage.local.set({ solverStats: stats });
        });
      } catch (_) {}

    } catch (err) {
      console.error('[Solver] ❌ Error in processFindObjectCaptcha:', err);
      updateHud('Error processing captcha', 'ERROR', '#ef4444', '#ef444420');
    } finally {
      isProcessing = false;
    }
  }

  // ─── Master Controller ────────────────────────────────────────────────────
  async function checkPage() {
    if (isProcessing) return;

    if (CONFIG.imageEnabled === false) {
      updateHud('Paused (Image: OFF)', 'PAUSED', '#94a3b8', '#94a3b820');
      return;
    }

    // Type 1: Standard .grid-wrap + .captcha-info CAPTCHA
    const textEl   = document.querySelector('.captcha-info strong');
    const gridWrap = document.querySelector('.grid-wrap');
    const mainImg  = gridWrap?.querySelector('img.gr-image');

    if (textEl && gridWrap && mainImg) {
      await processCaptchaGrid();
      return;
    }

    // Type 2: Find Object CAPTCHA (.comment-row + .oldsolver + Submit / Object not found)
    const commentEl = document.querySelector('.comment-row');
    const oldsolver = document.querySelector('.oldsolver');

    if (commentEl && oldsolver) {
      await processFindObjectCaptcha();
      return;
    }
  }

  // ─── Event Listeners ──────────────────────────────────────────────────────
  window.addEventListener('load', () => setTimeout(checkPage, 1000));
  setInterval(checkPage, 2000);

  new MutationObserver(() => {
    if (!isProcessing) checkPage();
  }).observe(document.documentElement, {
    childList       : true,
    subtree         : true,
    attributes      : true,
    attributeFilter : ['src', 'class']
  });

  console.log(`[CAPTCHA AI Solver] ✅ Content script loaded. Browser ID: ${BROWSER_ID}`);
})();
