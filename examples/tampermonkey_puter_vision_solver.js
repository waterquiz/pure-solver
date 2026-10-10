// ==UserScript==
// @name         Remote Image Solver - Puter.js Vision Integration
// @namespace    http://tampermonkey.net/
// @version      1.0.0
// @description  Dynamically loads Puter.js AI SDK, sends 3x3 grid images to Gemini Vision, extracts matching cells (1-9), and syncs with Remote Image Display API
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// ==/UserScript==

(function() {
    'use strict';

    // 1. Dynamic Loader for Puter.js SDK
    function loadPuter() {
        return new Promise((resolve, reject) => {
            if (window.puter) {
                resolve(window.puter);
                return;
            }
            const script = document.createElement('script');
            script.src = 'https://js.puter.com/v2/';
            script.onload = () => (window.puter ? resolve(window.puter) : reject(new Error('Puter not found')));
            script.onerror = () => reject(new Error('Failed to load Puter SDK'));
            document.head.appendChild(script);
        });
    }

    // 2. Base64 Conversion Helper
    function getBase64Image(imgElement) {
        const canvas = document.createElement('canvas');
        canvas.width = imgElement.naturalWidth || imgElement.width;
        canvas.height = imgElement.naturalHeight || imgElement.height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(imgElement, 0, 0);
        return canvas.toDataURL('image/png');
    }

    // 3. Response Normalizer & Parser
    function parseAiResponse(res) {
        let text = '';
        if (typeof res === 'string') {
            text = res;
        } else if (res?.message && typeof res.message.content === 'string') {
            text = res.message.content;
        } else if (typeof res?.text === 'string') {
            text = res.text;
        } else if (typeof res?.message === 'string') {
            text = res.message;
        } else if (res) {
            text = JSON.stringify(res);
        }
        return text.trim().toLowerCase();
    }

    // 4. Main Vision Analyzer Function
    async function solve3x3GridImage(imageElementOrBase64, targetText, model = 'gemini-2.5-flash') {
        try {
            console.log('⏳ Initializing Puter SDK...');
            const puter = await loadPuter();

            if (!puter.auth.isSignedIn()) {
                console.log('🔑 Signing in to Puter account...');
                await puter.auth.signIn();
            }


            const base64Img = (typeof imageElementOrBase64 === 'string')
                ? imageElementOrBase64
                : getBase64Image(imageElementOrBase64);

            const prompt = `Inspect the provided image carefully. The image is a 3x3 grid containing 9 cells. The cells are numbered 1 to 9, reading left to right, top to bottom like this:
[1] [2] [3]
[4] [5] [6]
[7] [8] [9]
Your task is to find all cells that clearly contain ALL of the following objects: "${targetText}".
Return a comma-separated list of the cell numbers that match. If no cells match, return "None".
Do not include any other text, reasoning, or punctuation besides the numbers.`;

            console.log(`🤖 Sending image to Puter AI (${model}) with query: "${targetText}"...`);
            const response = await puter.ai.chat(prompt, base64Img, { model: model });

            const rawText = parseAiResponse(response);
            console.log('📥 Raw AI Response:', rawText);

            // Extract unique numbers 1 through 9
            const matchedNumbers = rawText.match(/[1-9]/g) || [];
            const uniqueMatches = [...new Set(matchedNumbers.map(n => parseInt(n, 10)))];

            console.log('✅ AI Selected Cells (1-9):', uniqueMatches);
            return {
                matchedCells: uniqueMatches,
                rawOutput: rawText,
                model: model
            };
        } catch (err) {
            console.error('❌ AI Analysis Failed:', err);
            throw err;
        }
    }

    // Export to window for easy interactive console testing
    window.solve3x3GridImage = solve3x3GridImage;
    window.loadPuter = loadPuter;
    console.log('🚀 Puter AI 3x3 Grid Solver ready! Usage: await solve3x3GridImage(imgElement, "Blone and moon")');
})();
