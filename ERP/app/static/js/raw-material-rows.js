(function () {
  function designMaterialFromRoot(root) {
    const form = root.closest('form') || document;
    const fromSpecs = form.querySelector('.file-spec-material');
    if (fromSpecs && fromSpecs.value) return fromSpecs.value.trim();
    const rows = form.querySelectorAll('.file-spec-material');
    for (const input of rows) {
      const value = (input.value || '').trim();
      if (value) return value;
    }
    return '';
  }

  function populateSelect(select, materials, selectedId) {
    if (!select) return;
    select.innerHTML = '<option value="">Seleccionar materia prima...</option>';
    (materials || []).forEach((m) => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.dataset.unit = m.unit || 'planchas';
      const stockLabel = Number(m.stock).toLocaleString('es-EC', { maximumFractionDigits: 3 });
      opt.textContent = `${m.label} — ${stockLabel} ${m.unit}${m.is_low_stock ? ' ⚠ bajo' : ''}`;
      if (selectedId && String(m.id) === String(selectedId)) opt.selected = true;
      select.appendChild(opt);
    });
    updateRowHint(select.closest('.raw-material-row'));
  }

  function updateRowHint(row) {
    if (!row) return;
    const select = row.querySelector('.raw-material-select');
    const hint = row.querySelector('.raw-material-unit-hint');
    if (!select || !hint) return;
    const opt = select.options[select.selectedIndex];
    const unit = opt?.dataset?.unit || 'planchas';
    hint.innerHTML = unit === 'planchas'
      ? 'Unidad: <strong>planchas</strong>. Decimales OK: 0.25 (1/4), 0.5 (media), 1 (completa).'
      : `Unidad: <strong>${unit}</strong>. Puede usar decimales (ej. 1.5).`;
  }

  function syncRemoveButtons(list) {
    const rows = list.querySelectorAll('.raw-material-row');
    rows.forEach((row) => {
      const btn = row.querySelector('.raw-material-remove');
      if (btn) btn.classList.toggle('hidden', rows.length <= 1);
    });
  }

  function bindRow(root, row, materialsCache) {
    const select = row.querySelector('.raw-material-select');
    const qtyInput = row.querySelector('.raw-material-qty');

    select?.addEventListener('change', () => updateRowHint(row));
    qtyInput?.addEventListener('blur', () => {
      if (qtyInput.value) qtyInput.value = String(qtyInput.value).replace(',', '.');
    });
    row.querySelectorAll('.raw-qty-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (qtyInput) qtyInput.value = btn.dataset.qty;
      });
    });
    row.querySelector('.raw-material-remove')?.addEventListener('click', () => {
      row.remove();
      const list = root.querySelector('.raw-material-rows-list');
      if (!list.querySelector('.raw-material-row')) {
        addRow(root, materialsCache, {});
      }
      syncRemoveButtons(list);
    });

    if (materialsCache) populateSelect(select, materialsCache, select?.dataset.selectedId || '');
  }

  function rowHtml(values, matListId) {
    const esc = (v) => String(v ?? '').replace(/"/g, '&quot;');
    const qty = values.qty != null && values.qty !== '' ? values.qty : '';
    const selectedId = values.raw_material_id || '';
    return `
      <div class="raw-material-row rounded-xl border border-emerald-100 bg-white p-3 space-y-2">
        <div class="flex items-center justify-between gap-2">
          <label class="text-xs font-medium text-gray-600">Materia prima *</label>
          <button type="button" class="raw-material-remove w-8 h-8 rounded-lg border border-slate-200 text-slate-500 hover:bg-red-50 hover:text-red-600 hover:border-red-200 hidden" title="Quitar" aria-label="Quitar materia prima">×</button>
        </div>
        <select name="raw_material_id" class="raw-material-select w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm bg-white" data-selected-id="${esc(selectedId)}">
          <option value="">Cargando...</option>
        </select>
        <div>
          <label class="block text-xs text-gray-600 mb-1">Cantidad a consumir *</label>
          <input type="number" name="raw_material_qty" step="0.01" min="0.01" inputmode="decimal"
                 placeholder="Ej: 0.5" value="${esc(qty)}"
                 class="raw-material-qty w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm" />
          <div class="flex flex-wrap gap-1.5 mt-2">
            <button type="button" data-qty="0.25" class="raw-qty-btn px-2.5 py-1 rounded-lg border border-emerald-200 bg-white text-emerald-800 text-xs font-semibold hover:bg-emerald-50">1/4</button>
            <button type="button" data-qty="0.5" class="raw-qty-btn px-2.5 py-1 rounded-lg border border-emerald-200 bg-white text-emerald-800 text-xs font-semibold hover:bg-emerald-50">1/2</button>
            <button type="button" data-qty="0.75" class="raw-qty-btn px-2.5 py-1 rounded-lg border border-emerald-200 bg-white text-emerald-800 text-xs font-semibold hover:bg-emerald-50">3/4</button>
            <button type="button" data-qty="1" class="raw-qty-btn px-2.5 py-1 rounded-lg border border-emerald-200 bg-white text-emerald-800 text-xs font-semibold hover:bg-emerald-50">1</button>
            <button type="button" data-qty="2" class="raw-qty-btn px-2.5 py-1 rounded-lg border border-emerald-200 bg-white text-emerald-800 text-xs font-semibold hover:bg-emerald-50">2</button>
          </div>
          <p class="raw-material-unit-hint text-xs text-gray-500 mt-1.5">En <strong>planchas</strong> puede usar decimales: 0.25, 0.5, 1…</p>
        </div>
      </div>
    `;
  }

  function addRow(root, materialsCache, values) {
    const list = root.querySelector('.raw-material-rows-list');
    if (!list) return;
    const wrapper = document.createElement('div');
    wrapper.innerHTML = rowHtml(values || {}, root.dataset.matListId || '');
    const row = wrapper.firstElementChild;
    list.appendChild(row);
    bindRow(root, row, materialsCache);
    syncRemoveButtons(list);
    if (materialsCache) {
      populateSelect(row.querySelector('.raw-material-select'), materialsCache, values?.raw_material_id || '');
    }
    return row;
  }

  async function loadMaterials(root) {
    const designMat = designMaterialFromRoot(root);
    const selects = root.querySelectorAll('.raw-material-select');
    selects.forEach((sel) => {
      sel.innerHTML = '<option value="">Cargando...</option>';
    });
    try {
      const res = await fetch(`/inventory/api/materials?design_material=${encodeURIComponent(designMat)}`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      const data = await res.json();
      root._materialsCache = data || [];
      root.querySelectorAll('.raw-material-row').forEach((row) => {
        const sel = row.querySelector('.raw-material-select');
        populateSelect(sel, root._materialsCache, sel?.dataset.selectedId || sel?.value || '');
      });
    } catch (_) {
      selects.forEach((sel) => {
        sel.innerHTML = '<option value="">No se pudo cargar materia prima</option>';
      });
    }
  }

  window.initRawMaterialRows = function initRawMaterialRows(root) {
    if (!root || root.dataset.rawRowsInit === '1') return;
    root.dataset.rawRowsInit = '1';

    const list = root.querySelector('.raw-material-rows-list');
    const addBtn = root.querySelector('.add-raw-material-btn');
    if (!list) return;

    list.querySelectorAll('.raw-material-row').forEach((row) => bindRow(root, row, null));
    syncRemoveButtons(list);
    loadMaterials(root);

    addBtn?.addEventListener('click', () => {
      addRow(root, root._materialsCache || null, {});
      const rows = list.querySelectorAll('.raw-material-row');
      rows[rows.length - 1]?.querySelector('.raw-material-select')?.focus();
    });

    const form = root.closest('form') || document;
    form.querySelectorAll('.file-spec-material').forEach((input) => {
      input.addEventListener('change', () => loadMaterials(root));
    });

    root.reloadRawMaterials = () => loadMaterials(root);
  };

  window.validateRawMaterialRows = function validateRawMaterialRows(root) {
    if (!root || root.classList.contains('hidden')) return null;
    const rows = root.querySelectorAll('.raw-material-row');
    if (!rows.length) return 'Seleccione al menos una materia prima.';
    for (let i = 0; i < rows.length; i += 1) {
      const label = `#${i + 1}`;
      const rmId = (rows[i].querySelector('.raw-material-select')?.value || '').trim();
      const qty = (rows[i].querySelector('.raw-material-qty')?.value || '').trim();
      if (!rmId) return `Seleccione la materia prima ${label}.`;
      if (!qty) return `Indique la cantidad de la materia prima ${label}.`;
    }
    return null;
  };
})();
