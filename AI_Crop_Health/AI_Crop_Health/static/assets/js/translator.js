(function () {
  const LANGUAGES = [
    { code: "en", name: "English", native: "English" },
    { code: "hi", name: "Hindi", native: "हिंदी" },
    { code: "gu", name: "Gujarati", native: "ગુજરાતી" },
    { code: "bn", name: "Bengali", native: "বাংলা" },
    { code: "ta", name: "Tamil", native: "தமிழ்" },
    { code: "te", name: "Telugu", native: "తెలుగు" },
    { code: "mr", name: "Marathi", native: "मराठी" },
    { code: "kn", name: "Kannada", native: "ಕನ್ನಡ" },
    { code: "ml", name: "Malayalam", native: "മലയാളം" },
    { code: "pa", name: "Punjabi", native: "ਪੰਜਾਬੀ" },
    { code: "or", name: "Odia", native: "ଓଡ଼ିଆ" },
    { code: "ur", name: "Urdu", native: "اردو" },
    { code: "as", name: "Assamese", native: "অসমীয়া" }
  ];

  const LANG_SET = new Set(LANGUAGES.map((item) => item.code));
  const LANGUAGE_STORAGE_KEY = "selectedLanguage";
  const BROWSER_CACHE_PREFIX = "translation_cache_v2_";
  const endpoint = window.TRANSLATE_ENDPOINT || "/translate/";
  const MAX_TEXTS_PER_BATCH = 50;
  const MAX_UNCACHED_TEXTS = 3000;
  const MAX_NODE_SCAN = 5000;
  const MAX_CONCURRENT_BATCHES = 3;

  const originalTextByNode = new Map();
  const originalPlaceholderByElement = new Map();

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
      return parts.pop().split(";").shift();
    }
    return "";
  }

  function loadLanguageCache(lang) {
    try {
      const raw = localStorage.getItem(`${BROWSER_CACHE_PREFIX}${lang}`);
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      return {};
    }
  }

  function saveLanguageCache(lang, cacheData) {
    try {
      localStorage.setItem(`${BROWSER_CACHE_PREFIX}${lang}`, JSON.stringify(cacheData));
    } catch (error) {
      // Ignore storage write issues.
    }
  }

  function isVisibleElement(element) {
    if (!element) {
      return false;
    }
    if (element.closest("[data-no-translate='true']")) {
      return false;
    }
    return element.getClientRects().length > 0;
  }

  function shouldTranslateText(text) {
    if (!text) {
      return false;
    }
    const normalized = text.replace(/\s+/g, " ").trim();
    if (!normalized) {
      return false;
    }
      if (normalized.length > 800) {
      return false;
    }
    return /[A-Za-z]/.test(normalized);
  }

  function collectTextNodes() {
    const nodes = [];
    const seenNodes = new Set();

    function collectFromRoot(root) {
      if (!root || nodes.length >= MAX_NODE_SCAN) {
        return;
      }
      if (!isVisibleElement(root)) {
        return;
      }

      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      while (walker.nextNode()) {
        if (nodes.length >= MAX_NODE_SCAN) {
          break;
        }
        const textNode = walker.currentNode;
        if (seenNodes.has(textNode)) {
          continue;
        }
        const parent = textNode.parentElement;
        if (!parent) {
          continue;
        }
        const tag = parent.tagName;
        if (["SCRIPT", "STYLE", "NOSCRIPT", "CODE", "PRE", "IFRAME"].includes(tag)) {
          continue;
        }

        const original = originalTextByNode.get(textNode) || textNode.nodeValue;
        if (!originalTextByNode.has(textNode)) {
          originalTextByNode.set(textNode, original);
        }
        if (!shouldTranslateText(original)) {
          continue;
        }
        seenNodes.add(textNode);
        nodes.push({ node: textNode, originalText: original });
      }
    }

    const translatableRoots = document.querySelectorAll(".translatable");
    translatableRoots.forEach((root) => collectFromRoot(root));

    const fallbackRoots = [
      document.querySelector("#header"),
      document.querySelector("#topbar"),
      document.querySelector("main"),
      document.querySelector("#footer"),
      document.body
    ].filter(Boolean);

    fallbackRoots.forEach((root) => collectFromRoot(root));

    return nodes;
  }

  function chunkArray(items, chunkSize) {
    const chunks = [];
    for (let index = 0; index < items.length; index += chunkSize) {
      chunks.push(items.slice(index, index + chunkSize));
    }
    return chunks;
  }

  function collectPlaceholderElements() {
    const fields = document.querySelectorAll("input[placeholder], textarea[placeholder]");
    const eligible = [];

    fields.forEach((field) => {
      if (field.closest("[data-no-translate='true']")) {
        return;
      }
      const marked = field.dataset.translatePlaceholder === "true" || field.classList.contains("translatable");
      if (!marked) {
        return;
      }
      const original = originalPlaceholderByElement.get(field) || field.getAttribute("placeholder") || "";
      if (!originalPlaceholderByElement.has(field)) {
        originalPlaceholderByElement.set(field, original);
      }
      if (!shouldTranslateText(original)) {
        return;
      }
      eligible.push({ element: field, originalText: original });
    });

    return eligible;
  }

  function setLoading(isLoading) {
    const loader = document.getElementById("translation-loading");
    if (!loader) {
      return;
    }
    loader.classList.toggle("show", isLoading);
  }

  function showTranslationNotice(message) {
    const loader = document.getElementById("translation-loading");
    if (!loader) {
      return;
    }

    loader.classList.add("show");
    loader.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i><span>${message}</span>`;
    setTimeout(function () {
      loader.classList.remove("show");
      loader.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span><span>Translating...</span>';
    }, 2500);
  }

  async function requestTranslations(texts, targetLang, attempt) {
    const currentAttempt = typeof attempt === "number" ? attempt : 0;
    const controller = new AbortController();
    const timeoutMs = currentAttempt === 0 ? 30000 : 45000;
    const timeoutId = setTimeout(function () {
      controller.abort("timeout");
    }, timeoutMs);

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({ target_lang: targetLang, texts }),
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error("Translation API request failed");
      }

      return await response.json();
    } catch (error) {
      if (error && error.name === "AbortError") {
        // Retry once with smaller payload to reduce timeout probability.
        if (currentAttempt === 0 && texts.length > 1) {
          const mid = Math.ceil(texts.length / 2);
          const left = texts.slice(0, mid);
          const right = texts.slice(mid);
          const [leftResult, rightResult] = await Promise.all([
            requestTranslations(left, targetLang, 1),
            requestTranslations(right, targetLang, 1)
          ]);
          return {
            fallback: !!(leftResult.fallback || rightResult.fallback),
            translations: [
              ...(leftResult.translations || left),
              ...(rightResult.translations || right)
            ]
          };
        }

        return {
          fallback: true,
          timeout: true,
          translations: texts
        };
      }

      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  function setSelectValues(lang) {
    const desktopSelect = document.getElementById("language-select-desktop");
    if (desktopSelect) {
      desktopSelect.value = lang;
    }

    document.querySelectorAll(".mobile-language-option").forEach((button) => {
      const active = button.dataset.lang === lang;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function restoreEnglishText() {
    collectTextNodes().forEach(({ node, originalText }) => {
      node.nodeValue = originalText;
    });

    collectPlaceholderElements().forEach(({ element, originalText }) => {
      element.setAttribute("placeholder", originalText);
    });
  }

  async function applyLanguage(lang) {
    const selectedLang = LANG_SET.has(lang) ? lang : "en";
    localStorage.setItem(LANGUAGE_STORAGE_KEY, selectedLang);
    document.documentElement.setAttribute("lang", selectedLang);
    setSelectValues(selectedLang);

    if (selectedLang === "en") {
      restoreEnglishText();
      return;
    }

    const textNodes = collectTextNodes();
    const placeholders = collectPlaceholderElements();
    const cacheData = loadLanguageCache(selectedLang);

    const allEntries = [
      ...textNodes.map((item) => ({ type: "text", node: item.node, original: item.originalText })),
      ...placeholders.map((item) => ({ type: "placeholder", element: item.element, original: item.originalText }))
    ];

    const uniqueTexts = [];
    const missingSet = new Set();

    allEntries.forEach((entry) => {
      const clean = entry.original.replace(/\s+/g, " ").trim();
      if (!clean) {
        return;
      }
      if (!cacheData[clean] && !missingSet.has(clean)) {
        missingSet.add(clean);
        uniqueTexts.push(clean);
      }
    });

    setLoading(true);
    try {
      let hadProviderFailure = false;

      if (uniqueTexts.length) {
        const limitedTexts = uniqueTexts.slice(0, MAX_UNCACHED_TEXTS);
        const chunks = chunkArray(limitedTexts, MAX_TEXTS_PER_BATCH);

        for (let i = 0; i < chunks.length; i += MAX_CONCURRENT_BATCHES) {
          const chunkGroup = chunks.slice(i, i + MAX_CONCURRENT_BATCHES);
          const results = await Promise.all(
            chunkGroup.map((chunk) => requestTranslations(chunk, selectedLang))
          );

          chunkGroup.forEach((chunk, groupIndex) => {
            const apiData = results[groupIndex] || {};
            if (apiData.fallback) {
              hadProviderFailure = true;
              if (apiData.timeout) {
                showTranslationNotice("Network is slow. Partial translation applied.");
              }
              return;
            }
            const translatedList = apiData.translations || [];
            chunk.forEach((source, index) => {
              cacheData[source] = translatedList[index] || source;
            });
          });
        }

        if (uniqueTexts.length > MAX_UNCACHED_TEXTS) {
          showTranslationNotice("Some long page text skipped. Reopen page to continue.");
        }
        saveLanguageCache(selectedLang, cacheData);

        if (hadProviderFailure) {
          showTranslationNotice("Some text could not be translated right now.");
        }
      }

      allEntries.forEach((entry) => {
        const source = entry.original.replace(/\s+/g, " ").trim();
        const translated = cacheData[source] || source;
        if (entry.type === "text") {
          entry.node.nodeValue = translated;
        } else {
          entry.element.setAttribute("placeholder", translated);
        }
      });
    } catch (error) {
      showTranslationNotice("Translation service busy. Please try again.");
      console.warn("Translation failed:", error);
    } finally {
      setLoading(false);
    }
  }

  function getDefaultLanguage() {
    const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (saved && LANG_SET.has(saved)) {
      return saved;
    }

    const browserLang = (navigator.language || "en").slice(0, 2).toLowerCase();
    if (LANG_SET.has(browserLang)) {
      return browserLang;
    }
    return "en";
  }

  function closeMobileMenu() {
    const menu = document.getElementById("mobile-language-menu");
    if (menu) {
      menu.classList.remove("show");
      menu.setAttribute("aria-hidden", "true");
    }
  }

  function initMobileLanguageMenu() {
    const trigger = document.getElementById("mobile-language-trigger");
    const menu = document.getElementById("mobile-language-menu");
    const optionsContainer = document.getElementById("mobile-language-options");

    if (!trigger || !menu || !optionsContainer) {
      return;
    }

    optionsContainer.innerHTML = "";

    LANGUAGES.forEach((language) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "mobile-language-option";
      button.dataset.lang = language.code;
      button.innerHTML = `<span>${language.native}</span><small>${language.code.toUpperCase()}</small>`;
      button.addEventListener("click", async function () {
        closeMobileMenu();
        await applyLanguage(language.code);
      });
      optionsContainer.appendChild(button);
    });

    trigger.addEventListener("click", function () {
      const show = !menu.classList.contains("show");
      menu.classList.toggle("show", show);
      menu.setAttribute("aria-hidden", show ? "false" : "true");
    });

    document.addEventListener("click", function (event) {
      if (!menu.contains(event.target) && !trigger.contains(event.target)) {
        closeMobileMenu();
      }
    });
  }

  function speakCurrentPage(lang) {
    if (!("speechSynthesis" in window)) {
      return;
    }
    const pageText = Array.from(document.querySelectorAll(".translatable"))
      .map((element) => element.textContent.trim())
      .filter(Boolean)
      .join(". ");

    if (!pageText) {
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(pageText);
    utterance.lang = lang;
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  }

  function initTTS() {
    const desktopButton = document.getElementById("tts-toggle-desktop");
    const mobileButton = document.getElementById("tts-toggle-mobile");

    const handler = function () {
      const lang = localStorage.getItem(LANGUAGE_STORAGE_KEY) || "en";
      speakCurrentPage(lang);
    };

    if (desktopButton) {
      desktopButton.addEventListener("click", handler);
    }
    if (mobileButton) {
      mobileButton.addEventListener("click", handler);
    }
  }

  function initDesktopSelect() {
    const desktopSelect = document.getElementById("language-select-desktop");
    if (!desktopSelect) {
      return;
    }

    desktopSelect.addEventListener("change", async function (event) {
      await applyLanguage(event.target.value);
    });
  }

  document.addEventListener("DOMContentLoaded", async function () {
    initMobileLanguageMenu();
    initDesktopSelect();
    initTTS();

    await applyLanguage(getDefaultLanguage());
  });
})();
