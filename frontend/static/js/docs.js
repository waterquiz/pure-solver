// Documentation Code Snippet Tab & Copy Handler

document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll(".lang-tab");
  const snippets = document.querySelectorAll(".snippet-box");
  const copyBtn = document.getElementById("copy-code-btn");

  // Replace placeholder localhost:8000 with current origin dynamically in snippets
  const currentOrigin = window.location.origin;
  document.querySelectorAll(".snippet-box code, .snippet-box pre").forEach((block) => {
    block.innerHTML = block.innerHTML.replaceAll("http://localhost:8000", currentOrigin);
  });

  // Tab switching
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => {
        t.classList.remove("active", "bg-blue-600", "text-white");
        t.classList.add("bg-slate-700", "text-slate-300");
      });
      tab.classList.add("active", "bg-blue-600", "text-white");
      tab.classList.remove("bg-slate-700", "text-slate-300");

      const targetId = tab.getAttribute("data-target");
      snippets.forEach((s) => {
        if (s.id === targetId) {
          s.classList.remove("hidden");
        } else {
          s.classList.add("hidden");
        }
      });
    });
  });

  // Copy active snippet
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const activeSnippet = document.querySelector(".snippet-box:not(.hidden)");
      if (!activeSnippet) return;

      const codeElement = activeSnippet.querySelector("code") || activeSnippet;
      const textToCopy = codeElement.innerText;

      try {
        await navigator.clipboard.writeText(textToCopy);
        showToast("Code copied to clipboard!", "success");
      } catch (e) {
        showToast("Failed to copy code", "warning");
      }
    });
  }
});
