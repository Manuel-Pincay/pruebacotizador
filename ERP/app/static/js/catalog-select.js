/**
 * Selects de catálogo con opción "+ Agregar..." (POST a data-api-url).
 * Requiere ErpDialog (y Swal si data-add-mode=unit).
 */
(function () {
  function bindCatalogSelects(root) {
    const scope = root || document;
    scope.querySelectorAll("form").forEach(function (form) {
      if (form.dataset.catalogSelectBound === "1") return;
      form.dataset.catalogSelectBound = "1";
      form.addEventListener("submit", function () {
        form.querySelectorAll(".catalog-select").forEach(function (select) {
          if (select.value === "__new__") select.value = "";
        });
      });
    });

    scope.querySelectorAll(".catalog-select").forEach(function (select) {
      if (select.dataset.catalogBound === "1") return;
      select.dataset.catalogBound = "1";
      let previousValue = select.value;

      async function promptCatalogValue(selectEl) {
        const addLabel = selectEl.dataset.addLabel || "Agregar nuevo";
        if (selectEl.dataset.addMode === "unit") {
          const result = await Swal.fire({
            title: addLabel,
            html:
              '<input id="swal-unit-name" class="swal2-input" placeholder="Nombre (ej. Milímetros)">' +
              '<input id="swal-unit-abbr" class="swal2-input" placeholder="Abreviatura (ej. mm)">',
            showCancelButton: true,
            confirmButtonText: "Guardar",
            cancelButtonText: "Cancelar",
            reverseButtons: true,
            focusConfirm: false,
            preConfirm: function () {
              const name = document.getElementById("swal-unit-name").value.trim();
              const abbreviation = document.getElementById("swal-unit-abbr").value.trim();
              if (!name || !abbreviation) {
                Swal.showValidationMessage("Completa nombre y abreviatura");
                return false;
              }
              return { name: name, abbreviation: abbreviation };
            },
          });
          if (!result.isConfirmed) return null;
          return result.value;
        }

        const value = await ErpDialog.prompt(addLabel, {
          title: addLabel,
          placeholder: "Nombre...",
          confirmText: "Guardar",
          validator: function (inputValue) {
            if (!inputValue || !inputValue.trim()) return "Ingresa un nombre";
          },
        });
        if (!value) return null;
        return { name: value.trim() };
      }

      select.addEventListener("change", async function () {
        if (select.value !== "__new__") {
          previousValue = select.value;
          return;
        }
        const apiUrl = select.dataset.apiUrl;
        const newOption = select.querySelector('option[value="__new__"]');
        const payload = await promptCatalogValue(select);
        if (!payload) {
          select.value = previousValue;
          return;
        }
        const formData = new FormData();
        Object.entries(payload).forEach(function ([key, value]) {
          formData.append(key, value);
        });
        try {
          const response = await fetch(apiUrl, { method: "POST", body: formData });
          const data = await response.json();
          if (!response.ok) throw new Error(data.message || "No se pudo guardar");
          const optionValue = data.value || data.name;
          const optionLabel = data.label || data.name;
          let option = Array.from(select.options).find(function (opt) {
            return opt.value === optionValue;
          });
          if (!option) {
            option = document.createElement("option");
            option.value = optionValue;
            option.textContent = optionLabel;
            select.insertBefore(option, newOption);
          }
          select.value = optionValue;
          previousValue = optionValue;
          if (window.ErpDialog && ErpDialog.toast) {
            ErpDialog.toast(data.created ? "Agregado correctamente" : "Ya existía, seleccionado");
          }
        } catch (error) {
          select.value = previousValue;
          if (window.ErpDialog && ErpDialog.error) {
            ErpDialog.error(error.message || "No se pudo guardar");
          } else {
            alert(error.message || "No se pudo guardar");
          }
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      bindCatalogSelects(document);
    });
  } else {
    bindCatalogSelects(document);
  }
  window.bindCatalogSelects = bindCatalogSelects;
})();
