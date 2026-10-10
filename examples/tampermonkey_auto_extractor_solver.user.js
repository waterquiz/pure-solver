// ==UserScript==
// @name         Image & Text Extractor -> Remote Display & Puter AI Solver
// @namespace    http://tampermonkey.net/
// @version      1.1.0
// @description  Extracts image and target text from any webpage, sends them to Remote Image Display API, and receives Puter AI solved cells (1-9) with multi-browser isolation
// @author       Remote Image Display
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @connect      localhost
// @connect      127.0.0.1
// @connect      railway.app
// @connect      *
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // =========================================================================
    // 1. CONFIGURATION (Set your server URL and API key here)
    // =========================================================================
    const CONFIG = {
        // Change to your local or deployed Railway server URL
        SERVER_URL: 'http://localhost:8000',

        // Replace with your actual API key generated from http://localhost:8000/dashboard/api-keys
        API_KEY: 'YOUR_API_KEY_HERE',

        // Multi-Browser Identifier:
        // Set manually per browser (e.g. 'browser-1', 'browser-2') or keep 'auto' to automatically
        // generate and save a distinct persistent ID for each browser instance/profile.
        BROWSER_ID: 'auto',

        // Selectors to extract image (tries in order until found)
        IMAGE_SELECTORS: [
            'img.captcha-img',
            'img.challenge-image',
            'canvas.challenge-canvas',
            '#main-image',
            '.task-image img',
            'img[src*="blob:"]',
            'img[src*="data:image"]',
            'img' // fallback: largest image on screen
        ],

        // Selectors to extract target text/prompt (tries in order until found)
        TEXT_SELECTORS: [
            '.prompt-text',
            '.challenge-instructions',
            '.task-prompt',
            'h2.instruction',
            '.prompt',
            'strong',
            'h3'
        ],

        // Auto-detect when page loads or wait for manual trigger button
        AUTO_SOLVE_ON_LOAD: false,

        // Keyboard shortcut: Alt + S
        TRIGGER_KEY: 'KeyS'
    };

    // Helper: Retrieve or generate persistent unique browser ID
    function getBrowserId() {
        if (CONFIG.BROWSER_ID && CONFIG.BROWSER_ID !== 'auto') {
            return CONFIG.BROWSER_ID;
        }
        let stored = null;
        try {
            stored = GM_getValue('puter_browser_client_id', null);
        } catch (_) {}
        if (!stored) {
            // Generate clean distinct browser ID e.g. "browser-b4e2"
            stored = 'browser-' + Math.random().toString(36).substring(2, 6);
            try {
                GM_setValue('puter_browser_client_id', stored);
            } catch (_) {}
        }
        return stored;
    }

    // =========================================================================
    // 2. SLEEK FLOATING ON-SCREEN HUD WIDGET
    // =========================================================================
    let hud = null;
    let statusText = null;

    function createHUD() {
        if (hud) return;

        const myBrowserId = getBrowserId();

        hud = document.createElement('div');
        hud.id = 'ai-solver-hud';
        Object.assign(hud.style, {
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            zIndex: '999999',
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: '12px',
            padding: '12px 16px',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.5)',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            fontSize: '13px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            minWidth: '240px'
        });

        hud.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:6px;">
                <div style="display:flex; align-items:center; gap:6px;">
                    <span style="font-weight:700; color:#38bdf8; font-size:12px; letter-spacing:0.5px;">⚡ PUTER AI SOLVER</span>
                    <span style="font-size:10px; padding:2px 5px; border-radius:4px; background:#1e293b; color:#38bdf8; font-family:monospace; border:1px solid #0284c7;" title="Isolated Browser Profile">${myBrowserId}</span>
                </div>
                <span style="font-size:10px; color:#94a3b8; font-family:monospace;">Alt+S</span>
            </div>
            <div id="ai-hud-status" style="font-size:12px; color:#cbd5e1; display:flex; align-items:center; gap:6px;">
                <span>Ready to extract</span>
            </div>
            <div id="ai-hud-results" style="display:none; font-family:monospace; font-size:12px; font-weight:bold; color:#4ade80;"></div>
            <button id="ai-hud-action-btn" style="
                background: linear-gradient(135deg, #2563eb, #1d4ed8);
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
                cursor: pointer;
                transition: opacity 0.2s;
            ">Extract & Send to AI</button>
        `;

        document.body.appendChild(hud);

        statusText = hud.querySelector('#ai-hud-status');
        const actionBtn = hud.querySelector('#ai-hud-action-btn');

        actionBtn.addEventListener('click', () => {
            extractAndSendPipeline();
        });
    }

    function setHUDStatus(msg, color = '#cbd5e1', spinner = false) {
        if (!statusText) return;
        statusText.innerHTML = `
            ${spinner ? '<span style="display:inline-block; animation:spin 1s linear infinite;">⏳</span>' : ''}
            <span style="color:${color};">${msg}</span>
        `;
    }

    function showHUDResults(matchedCells) {
        const resDiv = hud.querySelector('#ai-hud-results');
        if (!resDiv) return;
        resDiv.style.display = 'block';
        if (matchedCells && matchedCells.length > 0) {
            resDiv.innerHTML = `🎯 Solved Cells: [${matchedCells.join(', ')}]`;
            resDiv.style.color = '#4ade80';
        } else {
            resDiv.innerHTML = `🎯 Solved: None found`;
            resDiv.style.color = '#94a3b8';
        }
    }

    // =========================================================================
    // 3. IMAGE & TEXT EXTRACTION HELPERS
    // =========================================================================

    // Extract the primary image element or canvas
    function findTargetImage() {
        for (const selector of CONFIG.IMAGE_SELECTORS) {
            const el = document.querySelector(selector);
            if (el && (el.naturalWidth > 100 || el.width > 100 || el.tagName === 'CANVAS')) {
                return el;
            }
        }

        // Fallback: Pick largest visible image on webpage
        const allImages = Array.from(document.querySelectorAll('img')).filter(img => {
            const rect = img.getBoundingClientRect();
            return rect.width > 120 && rect.height > 120;
        });

        if (allImages.length > 0) {
            allImages.sort((a, b) => (b.width * b.height) - (a.width * a.height));
            return allImages[0];
        }

        return null;
    }

    // Extract target query text (e.g. "Blone and moon", "House")
    function findTargetText() {
        for (const selector of CONFIG.TEXT_SELECTORS) {
            const el = document.querySelector(selector);
            if (el && el.innerText && el.innerText.trim().length > 1) {
                // Remove generic wrapper phrases if needed
                let clean = el.innerText.trim();
                clean = clean.replace(/^(click all|select all|find all|look for)\s*/i, '');
                return clean;
            }
        }

        return 'Target Object';
    }

    // Convert Image/Canvas element into a Blob for multipart/form-data upload
    async function imageElementToBlob(el) {
        if (el.tagName === 'CANVAS') {
            return new Promise(resolve => el.toBlob(resolve, 'image/png'));
        }

        if (el.tagName === 'IMG') {
            // Check if it's already a Data URL or Blob URL
            if (el.src.startsWith('data:') || el.src.startsWith('blob:')) {
                const res = await fetch(el.src);
                return await res.blob();
            }

            // Otherwise, render to canvas to get pure PNG Blob (handles CORS canvas if clean)
            try {
                const canvas = document.createElement('canvas');
                canvas.width = el.naturalWidth || el.width || 300;
                canvas.height = el.naturalHeight || el.height || 300;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(el, 0, 0);
                return await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
            } catch (canvasErr) {
                // If tainted canvas, fetch directly via GM_xmlhttpRequest
                return await fetchImageAsBlobGM(el.src);
            }
        }

        throw new Error('Unsupported image element type');
    }

    // Fallback fetch image as blob using GM_xmlhttpRequest (bypasses CORS)
    function fetchImageAsBlobGM(url) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: 'GET',
                url: url,
                responseType: 'blob',
                onload: res => resolve(res.response),
                onerror: err => reject(err)
            });
        });
    }

    // =========================================================================
    // 4. MAIN PIPELINE: EXTRACT -> SEND TO SERVER -> PUTER AI -> RETURN
    // =========================================================================
    async function extractAndSendPipeline() {
        try {
            setHUDStatus('Locating image & text...', '#38bdf8', true);

            // 1. Locate elements
            const imgEl = findTargetImage();
            const promptText = findTargetText();

            if (!imgEl) {
                setHUDStatus('❌ Target image not found on page', '#f87171');
                console.warn('[Puter AI Solver] No image found matching selectors');
                return;
            }

            console.log('[Puter AI Solver] Image element found:', imgEl);
            console.log('[Puter AI Solver] Extracted target query text:', promptText);

            // 2. Convert to Blob
            setHUDStatus('Preparing image blob...', '#38bdf8', true);
            const blob = await imageElementToBlob(imgEl);

            if (!blob) {
                setHUDStatus('❌ Failed to convert image to blob', '#f87171');
                return;
            }

            // 3. Build multipart FormData with isolated browser client_id
            const myBrowserId = getBrowserId();
            const formData = new FormData();
            formData.append('file', blob, 'extracted_task.png');
            formData.append('text', promptText);
            formData.append('client_id', myBrowserId);

            setHUDStatus(`Sending [${myBrowserId}] -> Puter AI...`, '#fbbf24', true);
            console.log(`[Puter AI Solver - ${myBrowserId}] Sending to ${CONFIG.SERVER_URL}/api/v1/images ...`);

            // 4. Send to Website API via GM_xmlhttpRequest (waits for Puter AI, auto-deletes 4s after output)
            GM_xmlhttpRequest({
                method: 'POST',
                url: `${CONFIG.SERVER_URL}/api/v1/images?wait_for_ai=true&auto_delete_seconds=4&timeout_seconds=40`,
                headers: {
                    'X-API-Key': CONFIG.API_KEY
                },
                data: formData,
                timeout: 45000,
                onload: function(response) {
                    try {
                        const json = JSON.parse(response.responseText);
                        console.log(`[Puter AI Solver - ${myBrowserId}] Response from website:`, json);

                        if (response.status === 200 || response.status === 201) {
                            // Ensure the returned payload belongs specifically to THIS browser
                            if (json.client_id && json.client_id !== myBrowserId) {
                                console.error(`[Puter AI Solver] Cross-browser security warning! Response is for ${json.client_id}, but this browser is ${myBrowserId}`);
                                return;
                            }

                            const matchedCells = json.matched_cells || (json.image && json.image.matched_cells);
                            const rawOutput = json.output || (json.image && json.image.output) || 'Processed';

                            setHUDStatus(`✅ Solved for [${myBrowserId}]! (Auto-deleting in 4s)`, '#4ade80');
                            showHUDResults(matchedCells);

                            console.log('====================================');
                            console.log(`🎯 [${myBrowserId}] SOLVED CELLS:`, matchedCells);
                            console.log(`📝 [${myBrowserId}] Raw Output:`, rawOutput);
                            console.log('====================================');

                            // Trigger custom event so any other script on page can listen
                            window.dispatchEvent(new CustomEvent('puter_ai_solved', {
                                detail: {
                                    browserId: myBrowserId,
                                    matchedCells: matchedCells,
                                    output: rawOutput,
                                    imageInfo: json.image
                                }
                            }));
                        } else {
                            const errMsg = (json.error && json.error.message) || json.detail || 'API error';
                            setHUDStatus(`❌ ${errMsg}`, '#f87171');
                        }
                    } catch (parseErr) {
                        setHUDStatus('❌ Invalid response from server', '#f87171');
                        console.error('[Puter AI Solver] Response parse error:', response.responseText);
                    }
                },
                onerror: function(err) {
                    setHUDStatus('❌ Failed to connect to website', '#f87171');
                    console.error('[Puter AI Solver] Network error:', err);
                },
                ontimeout: function() {
                    setHUDStatus('⚠️ Request timed out', '#f87171');
                }
            });

        } catch (err) {
            setHUDStatus(`❌ Error: ${err.message}`, '#f87171');
            console.error('[Puter AI Solver] Extraction error:', err);
        }
    }

    // =========================================================================
    // 5. KEYBOARD SHORTCUT & INITIALIZATION
    // =========================================================================
    window.addEventListener('keydown', (e) => {
        if (e.altKey && e.code === CONFIG.TRIGGER_KEY) {
            e.preventDefault();
            extractAndSendPipeline();
        }
    });

    // Expose global solver function to browser console
    window.solveCurrentChallenge = extractAndSendPipeline;

    // Boot HUD on page
    createHUD();

    if (CONFIG.AUTO_SOLVE_ON_LOAD) {
        setTimeout(extractAndSendPipeline, 1500);
    }

    console.log('[Puter AI Solver] Tampermonkey script loaded! Press Alt+S or click "Extract & Send to AI".');
})();
