(function () {
  function normalize(value) {
    return (value || "").trim().toLowerCase();
  }

  function initCatalogCombobox(root) {
    const input = root.querySelector("[data-catalog-input]");
    const addBtn = root.querySelector("[data-catalog-add]");
    const listEl = root.querySelector("[data-catalog-list]");
    const apiUrl = root.dataset.apiUrl;

    if (!input || !addBtn || !listEl || !apiUrl) {
      return;
    }

    let options = [];
    try {
      options = JSON.parse(root.dataset.options || "[]");
    } catch (_err) {
      options = [];
    }

    if (input.value && !options.some((item) => normalize(item) === normalize(input.value))) {
      options.push(input.value.trim());
    }

    options = [...new Set(options.filter(Boolean))].sort((a, b) =>
      a.localeCompare(b, "es", { sensitivity: "base" })
    );

    function hideSuggestions() {
      listEl.classList.add("hidden");
      listEl.innerHTML = "";
    }

    function showSuggestions(items) {
      listEl.innerHTML = "";

      if (!items.length) {
        hideSuggestions();
        return;
      }

      items.slice(0, 12).forEach((item) => {
        const li = document.createElement("li");
        li.dataset.value = item;
        li.className =
          "px-3 py-2 cursor-pointer hover:bg-purple-50 text-sm text-gray-800";
        li.textContent = item;
        listEl.appendChild(li);
      });

      listEl.classList.remove("hidden");
    }

    function filterOptions(query) {
      const q = normalize(query);
      if (!q) {
        return options;
      }
      return options.filter((item) => normalize(item).includes(q));
    }

    function syncCanonicalValue(value) {
      const match = options.find((item) => normalize(item) === normalize(value));
      if (match) {
        input.value = match;
      }
    }

    function renderSuggestions() {
      showSuggestions(filterOptions(input.value));
    }

    async function addCurrentValue() {
      const name = input.value.trim();
      if (!name) {
        input.focus();
        return;
      }

      syncCanonicalValue(name);
      if (options.some((item) => normalize(item) === normalize(input.value))) {
        hideSuggestions();
        return;
      }

      addBtn.disabled = true;
      addBtn.classList.add("opacity-60");

      try {
        const response = await fetch(apiUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        });

        const data = await response.json();
        if (!response.ok || !data.ok) {
          alert(data.error || "No se pudo agregar al catálogo");
          return;
        }

        if (!options.some((item) => normalize(item) === normalize(data.name))) {
          options.push(data.name);
          options.sort((a, b) => a.localeCompare(b, "es", { sensitivity: "base" }));
        }

        input.value = data.name;
        root.dataset.options = JSON.stringify(options);
        hideSuggestions();
      } catch (_err) {
        alert("Error de conexión al guardar en catálogo");
      } finally {
        addBtn.disabled = false;
        addBtn.classList.remove("opacity-60");
      }
    }

    input.addEventListener("focus", renderSuggestions);
    input.addEventListener("input", renderSuggestions);

    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hideSuggestions();
        return;
      }

      if (event.key === "Enter") {
        const first = listEl.querySelector("[data-value]");
        if (!listEl.classList.contains("hidden") && first) {
          event.preventDefault();
          input.value = first.dataset.value;
          hideSuggestions();
        }
      }
    });

    input.addEventListener("blur", () => {
      window.setTimeout(() => {
        syncCanonicalValue(input.value);
        hideSuggestions();
      }, 150);
    });

    listEl.addEventListener("mousedown", (event) => {
      const item = event.target.closest("[data-value]");
      if (!item) {
        return;
      }
      event.preventDefault();
      input.value = item.dataset.value;
      hideSuggestions();
    });

    addBtn.addEventListener("click", addCurrentValue);
  }

  function boot() {
    document.querySelectorAll("[data-catalog-combobox]").forEach(initCatalogCombobox);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
