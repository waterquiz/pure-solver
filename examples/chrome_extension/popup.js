/**
 * Popup Script (Pure Solver)
 * Syncs extension state with backend and drives the pixel-perfect UI.
 */

const $ = (id) => document.getElementById(id);

let currentConfig = {
  backendUrl        : 'https://pure-solver-production.up.railway.app',
  apiKey            : 'PS_900a2dbb943ac30d39ba1993ca3614379a04bb',
  autoDelay         : 1000,
  waitForAi         : true,
  autoDeleteSeconds : 4,
  imageEnabled      : true
};

let solverStats = {
  used  : 12000,
  limit : 12000
};

function formatNumber(num) {
  return Number(num).toLocaleString('en-US');
}

function updateStatsDisplay() {
  const solved = solverStats.used ?? 12000;
  const limit  = solverStats.limit ?? 12000;

  const usedEl = $('used');
  const capEl  = $('cap');
  const maxEl  = $('max');
  const fillEl = $('fill');

  if (usedEl) usedEl.textContent = formatNumber(solved);
  if (capEl)  capEl.textContent  = formatNumber(limit);
  if (maxEl)  maxEl.textContent  = formatNumber(limit);

  if (fillEl) {
    // When 12,000 / 12,000 completed -> Bar is 100% full
    const pct = limit > 0 ? Math.min(100, Math.max(0, (solved / limit) * 100)) : 100;
    fillEl.style.width = `${pct}%`;
  }
}

function updateKeyDisplay() {
  const keyInput = $('keyInput');
  if (keyInput) {
    keyInput.value = currentConfig.apiKey || 'PS_900a2dbb943ac30d39ba1993ca3614379a04bb';
  }
}

function loadConfig() {
  chrome.runtime.sendMessage({ type: 'GET_CONFIG' }, (cfg) => {
    if (cfg) Object.assign(currentConfig, cfg);

    const power = $('power');
    if (power) {
      power.checked = currentConfig.imageEnabled !== false;
    }

    updateKeyDisplay();
    checkBackendStatus(currentConfig.backendUrl);
  });

  chrome.storage.local.get(['solverStats'], (res) => {
    if (res && res.solverStats) {
      Object.assign(solverStats, res.solverStats);
    }
    updateStatsDisplay();
  });
}

// ─── Header Toggle Switch ───────────────────────────────────
const powerEl = $('power');
if (powerEl) {
  powerEl.addEventListener('change', (e) => {
    const on = e.target.checked;
    currentConfig.imageEnabled = on;

    const dot = $('dot');
    const statusText = $('statusText');
    if (statusText) statusText.textContent = on ? 'Server Connected' : 'Solver Paused';
    if (dot) {
      dot.style.background = on ? '#19e36b' : '#98a2b8';
      dot.style.boxShadow = on ? '' : 'none';
    }

    chrome.runtime.sendMessage({
      type   : 'SAVE_CONFIG',
      config : currentConfig
    });
  });
}

// ─── Editable API Key Input ─────────────────────────────────
const keyInputEl = $('keyInput');
if (keyInputEl) {
  // Save when user types or edits API key
  keyInputEl.addEventListener('input', () => {
    currentConfig.apiKey = keyInputEl.value.trim();
    chrome.runtime.sendMessage({
      type   : 'SAVE_CONFIG',
      config : currentConfig
    });
  });

  keyInputEl.addEventListener('change', () => {
    currentConfig.apiKey = keyInputEl.value.trim();
    chrome.runtime.sendMessage({
      type   : 'SAVE_CONFIG',
      config : currentConfig
    });
  });
}

// ─── Eye Reveal / Hide Button ───────────────────────────────
const eyeBtn = $('eye');
if (eyeBtn && keyInputEl) {
  eyeBtn.addEventListener('click', () => {
    const isPassword = keyInputEl.type === 'password';
    keyInputEl.type = isPassword ? 'text' : 'password';
    eyeBtn.setAttribute('aria-label', isPassword ? 'Hide API key' : 'Show API key');
  });
}

// ─── Copy Button ────────────────────────────────────────────
const copyBtn = $('copy');
if (copyBtn && keyInputEl) {
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(keyInputEl.value);
      copyBtn.classList.add('done');
      setTimeout(() => copyBtn.classList.remove('done'), 1200);
    } catch (err) {
      console.warn('Clipboard write failed:', err);
    }
  });
}

// ─── Backend Connectivity Check ─────────────────────────────
async function checkBackendStatus(baseUrl) {
  const dot  = $('dot');
  const text = $('statusText');
  if (!dot || !text) return;

  try {
    const ctrl = new AbortController();
    const id   = setTimeout(() => ctrl.abort(), 3500);
    const res  = await fetch(`${baseUrl || 'http://localhost:8000'}/health`, { signal: ctrl.signal });
    clearTimeout(id);

    if (res.ok) {
      dot.style.background = '#19e36b';
      dot.style.boxShadow  = '';
      text.textContent     = 'Server Connected';
    } else {
      dot.style.background = '#ef4444';
      dot.style.boxShadow  = 'none';
      text.textContent     = `Error ${res.status}`;
    }
  } catch (e) {
    dot.style.background = '#ef4444';
    dot.style.boxShadow  = 'none';
    text.textContent     = 'Backend Offline';
  }
}

// ─── Initialize ─────────────────────────────────────────────
loadConfig();
updateStatsDisplay();
