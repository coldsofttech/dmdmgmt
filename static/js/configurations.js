/* =========================================================
   Resource Planner — configurations.js
   Handles: live search, column sort, reset-to-default
   ========================================================= */

'use strict';

/* ── Live search ───────────────────────────────────────── */
const searchInput = document.getElementById('config-search');
if (searchInput) {
  searchInput.addEventListener('input', filterConfigTable);
}

function filterConfigTable() {
  const query   = (searchInput?.value || '').toLowerCase().trim();
  const rows    = document.querySelectorAll('#config-table tbody tr[data-config-id]');
  let   visible = 0;

  rows.forEach(row => {
    const code  = row.dataset.code  || '';
    const label = row.dataset.label || '';
    const show  = !query || code.includes(query) || label.includes(query);
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  let emptyRow = document.getElementById('empty-filter-row');
  if (!visible) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'empty-filter-row';
      emptyRow.innerHTML = `
        <td colspan="6" class="text-center py-4 text-secondary">
          <i class="bi bi-search me-2"></i>No configurations match your search.
        </td>`;
      document.querySelector('#config-table tbody')?.appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* ── Column sort ───────────────────────────────────────── */
let sortState = { col: -1, asc: true };

function sortConfigTable(colIndex) {
  const tbody = document.querySelector('#config-table tbody');
  if (!tbody) return;

  sortState.asc = sortState.col === colIndex ? !sortState.asc : true;
  sortState.col = colIndex;

  document.querySelectorAll('#config-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-config-id]'));
  rows.sort((a, b) => {
    const aVal = (a.cells[colIndex]?.innerText || '').trim();
    const bVal = (b.cells[colIndex]?.innerText || '').trim();
    return sortState.asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  });
  rows.forEach(row => tbody.appendChild(row));
}

/* ── Reset to default ──────────────────────────────────── */
let _pendingResetId   = null;
let _pendingResetCode = null;

function resetConfig(id, code) {
  _pendingResetId   = id;
  _pendingResetCode = code;

  const codeEl = document.getElementById('reset-config-code');
  if (codeEl) codeEl.textContent = code;

  const modal = document.getElementById('resetModal');
  if (!modal) return;

  // Wire confirm button fresh each time (avoids stacking listeners)
  const btn    = document.getElementById('confirm-reset-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    await _doReset(_pendingResetId, _pendingResetCode);
  });

  bootstrap.Modal.getOrCreateInstance(modal).show();
}

async function _doReset(id, code) {
  try {
    const res = await fetch(`/settings/config/${id}/reset/`, {
      method:  'POST',
      headers: {
        'X-CSRFToken': _getCsrfToken(),
        'Content-Type': 'application/json',
      },
    });

    const data = await res.json();

    if (!res.ok || !data.ok) {
      _showFlash(data.detail || 'Reset failed. Please try again.', 'error');
      return;
    }

    // ── Update list page DOM inline (no full reload needed) ──
    const pill    = document.getElementById(`value-pill-${id}`);
    const updated = document.getElementById(`updated-${id}`);
    if (pill)    pill.textContent    = data.value;
    if (updated) updated.textContent = data.updated_at;

    // ── Update detail page DOM if we're on it ───────────────
    const valueDisplay   = document.getElementById('value-display');
    const updatedDisplay = document.getElementById('updated-display');
    if (valueDisplay)   valueDisplay.textContent   = data.value;
    if (updatedDisplay) updatedDisplay.textContent = data.updated_at;

    // Update value input if the edit form is open
    const valueInput = document.querySelector('input[name="value"]');
    if (valueInput) valueInput.value = data.value;

    _showFlash(`"${code}" has been reset to its default value (${data.value}).`, 'success');

  } catch (err) {
    console.error('Reset error:', err);
    _showFlash('An unexpected error occurred. Please try again.', 'error');
  }
}

/* ── Helpers ───────────────────────────────────────────── */
function _getCsrfToken() {
  // Prefer the global from main.js if available, else read cookie directly
  if (typeof getCsrfToken === 'function') return getCsrfToken();
  const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1].trim() : '';
}

function _showFlash(message, type) {
  // Prefer the global from main.js if available
  if (typeof showFlash === 'function') {
    showFlash(message, type);
    return;
  }
  // Fallback
  alert(message);
}