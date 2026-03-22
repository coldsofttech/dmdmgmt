/* =========================================================
   Resource Planner — financial_years.js
   Handles: set-active and delete confirmation modals
   ========================================================= */

'use strict';

/* ── Set Active ────────────────────────────────────────── */
let _pendingSetActivePk   = null;
let _pendingSetActiveName = null;

function setActiveFY(pk, name) {
  _pendingSetActivePk   = pk;
  _pendingSetActiveName = name;

  const nameEl = document.getElementById('set-active-fy-name');
  if (nameEl) nameEl.textContent = name;

  const modal = document.getElementById('setActiveModal');
  if (!modal) return;

  const btn    = document.getElementById('confirm-set-active-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    await _doSetActive(_pendingSetActivePk, _pendingSetActiveName);
  });

  bootstrap.Modal.getOrCreateInstance(modal).show();
}

async function _doSetActive(pk, name) {
  try {
    const res  = await fetch(`/financial-years/${pk}/set-active/`, {
      method:  'POST',
      headers: { 'X-CSRFToken': _getCsrf() },
    });
    const data = await res.json();
    if (data.ok) {
      _showFlash(`${name} is now the active financial year.`, 'success');
      setTimeout(() => location.reload(), 800);
    } else {
      _showFlash(data.detail || 'Failed to set active.', 'error');
    }
  } catch {
    _showFlash('An unexpected error occurred.', 'error');
  }
}

/* ── Delete ─────────────────────────────────────────────── */
let _pendingDeletePk   = null;
let _pendingDeleteName = null;

function deleteFY(pk, name) {
  _pendingDeletePk   = pk;
  _pendingDeleteName = name;

  const nameEl = document.getElementById('delete-fy-name');
  if (nameEl) nameEl.textContent = name;

  const modal = document.getElementById('deleteModal');
  if (!modal) return;

  const btn    = document.getElementById('confirm-delete-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    await _doDelete(_pendingDeletePk, _pendingDeleteName);
  });

  bootstrap.Modal.getOrCreateInstance(modal).show();
}

async function _doDelete(pk, name) {
  try {
    const res  = await fetch(`/financial-years/${pk}/delete/`, {
      method:  'POST',
      headers: { 'X-CSRFToken': _getCsrf() },
    });
    const data = await res.json();
    if (data.ok) {
      _showFlash(`${name} deleted.`, 'success');
      setTimeout(() => { window.location.href = '/financial-years/'; }, 700);
    } else {
      _showFlash(data.detail || 'Failed to delete.', 'error');
    }
  } catch {
    _showFlash('An unexpected error occurred.', 'error');
  }
}

/* ── Helpers ───────────────────────────────────────────── */
function _getCsrf() {
  if (typeof getCsrfToken === 'function') return getCsrfToken();
  const c = document.cookie.split(';').find(x => x.trim().startsWith('csrftoken='));
  return c ? c.split('=')[1].trim() : '';
}

function _showFlash(msg, type) {
  if (typeof showFlash === 'function') { showFlash(msg, type); return; }
  alert(msg);
}

/* ── List page: status filter ──────────────────────────── */
function filterFYTable() {
  const status = (document.getElementById('status-filter')?.value || '').toLowerCase();
  const rows   = document.querySelectorAll('#fy-table tbody tr[data-fy-id]');
  let visible  = 0;

  rows.forEach(row => {
    const rowStatus = (row.dataset.status || '').toLowerCase();
    const show = !status || rowStatus === status;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  // Empty-state row when everything is filtered out
  let emptyRow = document.getElementById('filter-empty-row');
  if (!visible) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'filter-empty-row';
      emptyRow.innerHTML = `<td colspan="7" class="text-center py-4 text-secondary">
        <i class="bi bi-search me-2"></i>No financial years match the selected filter.</td>`;
      document.querySelector('#fy-table tbody')?.appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* ── List page: sort ───────────────────────────────────── */
let _sortState = { col: -1, asc: true };

function sortFYTable(colIndex) {
  const tbody = document.querySelector('#fy-table tbody');
  if (!tbody) return;

  _sortState.asc = _sortState.col === colIndex ? !_sortState.asc : true;
  _sortState.col = colIndex;

  // Update sort icons
  document.querySelectorAll('#fy-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (_sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-fy-id]'));
  rows.sort((a, b) => {
    // Prefer data-sort attribute (ISO date / numeric) over inner text
    const aCell = a.cells[colIndex];
    const bCell = b.cells[colIndex];
    const aVal  = (aCell?.dataset.sort ?? aCell?.innerText ?? '').trim();
    const bVal  = (bCell?.dataset.sort ?? bCell?.innerText ?? '').trim();

    // Numeric comparison for Days and Status sort-key columns
    const aNum = parseFloat(aVal);
    const bNum = parseFloat(bVal);
    const useNum = !isNaN(aNum) && !isNaN(bNum);

    let cmp = useNum ? aNum - bNum : aVal.localeCompare(bVal);
    return _sortState.asc ? cmp : -cmp;
  });

  rows.forEach(row => tbody.appendChild(row));
}