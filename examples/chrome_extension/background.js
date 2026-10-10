/**
 * Background Service Worker
 * - Stores and distributes configuration (API key, backend URL, etc.)
 * - Handles inter-script messaging
 */

const DEFAULT_CONFIG = {
  backendUrl        : 'http://localhost:8000',
  apiKey            : 'PS_900a2dbb943ac30d39ba1993ca3614379a04bb',
  autoDelay         : 1000,
  waitForAi         : true,
  autoDeleteSeconds : 4,
  imageEnabled      : true
};

// ─── On install: set default config ───────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.get('config', (data) => {
    if (!data.config || !data.config.apiKey) {
      chrome.storage.sync.set({ config: Object.assign({}, DEFAULT_CONFIG, data.config || {}, { apiKey: DEFAULT_CONFIG.apiKey }) });
    }
  });
});

// ─── Message handler ──────────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

  // Popup asks: give me the current config
  if (msg.type === 'GET_CONFIG') {
    chrome.storage.sync.get('config', (data) => {
      sendResponse(data.config || DEFAULT_CONFIG);
    });
    return true; // async response
  }

  // Popup sends updated config → save + relay to all content scripts in active tabs
  if (msg.type === 'SAVE_CONFIG') {
    const newConfig = Object.assign({}, DEFAULT_CONFIG, msg.config);
    chrome.storage.sync.set({ config: newConfig }, () => {
      // Relay updated config to all matching content scripts
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach((tab) => {
          if (tab.id) {
            chrome.tabs.sendMessage(tab.id, {
              type   : 'CONFIG_UPDATED',
              config : newConfig
            }).catch(() => {}); // tab may not have our content script
          }
        });
      });
      sendResponse({ success: true });
    });
    return true;
  }
});
