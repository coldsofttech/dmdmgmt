/* =========================================================
   Resource Planner — budgets.js
   ========================================================= */

'use strict';

/* ── Live filter ────────────────────────────────────────── */
const budgetSearch  = document.getElementById('budget-search');
const fyFilter      = document.getElementById('fy-filter');
const statusFilter  = document.getElementById('status-filter');

if (budgetSearch) {
  budgetSearch.addEventListener('input', filterBudgets);
}

function filterBudgets() {
  const query     = (budgetSearch?.value  || '').toLowerCase().trim();
  const fyVal     = (fyFilter?.value      || '').toLowerCase().trim();
  const statusVal = (statusFilter?.value  || '').toLowerCase().trim();

  const rows    = document.querySelectorAll('#budgets-table tbody tr[data-budget-id]');
  let   visible = 0;

  rows.forEach(row => {
    const searchText = (row.dataset.search || '').toLowerCase();
    const rowFy      = (row.dataset.fy     || '').toLowerCase();
    const rowStatus  = (row.dataset.status || '').toLowerCase();

    const matchSearch = !query     || searchText.includes(query);
    const matchFy     = !fyVal     || rowFy     === fyVal;
    const matchStatus = !statusVal || rowStatus  === statusVal;

    const show = matchSearch && matchFy && matchStatus;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  const countEl = document.getElementById('visible-count');
  if (countEl) countEl.textContent = visible;

  let emptyRow = document.getElementById('empty-filter-row');
  if (visible === 0 && rows.length > 0) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'empty-filter-row';
      emptyRow.innerHTML = `
        <td colspan="8" class="text-center py-4 text-secondary">
          <i class="bi bi-search me-2"></i>No budget entries match your filters.
        </td>`;
      document.querySelector('#budgets-table tbody').appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* ── Sort ───────────────────────────────────────────────── */
let _sortState = { col: -1, asc: true };

function sortBudgets(colIndex) {
  const tbody = document.querySelector('#budgets-table tbody');
  if (!tbody) return;

  _sortState.asc = _sortState.col === colIndex ? !_sortState.asc : true;
  _sortState.col = colIndex;

  document.querySelectorAll('#budgets-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (_sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-budget-id]'));
  rows.sort((a, b) => {
    const aCell = a.cells[colIndex];
    const bCell = b.cells[colIndex];
    const aVal  = (aCell?.dataset.sort ?? aCell?.innerText ?? '').trim();
    const bVal  = (bCell?.dataset.sort ?? bCell?.innerText ?? '').trim();
    const aNum  = parseFloat(aVal);
    const bNum  = parseFloat(bVal);
    const cmp   = (!isNaN(aNum) && !isNaN(bNum))
      ? aNum - bNum
      : aVal.localeCompare(bVal, undefined, { numeric: true });
    return _sortState.asc ? cmp : -cmp;
  });
  rows.forEach(r => tbody.appendChild(r));
}

/* ── Delete ─────────────────────────────────────────────── */
let _pendingDeletePk   = null;
let _pendingDeleteName = null;

function deleteBudget(pk, name) {
  _pendingDeletePk   = pk;
  _pendingDeleteName = name;

  const nameEl = document.getElementById('delete-budget-name');
  if (nameEl) nameEl.textContent = name;

  const modal = document.getElementById('deleteModal');
  if (!modal) return;

  const btn    = document.getElementById('confirm-delete-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    try {
      const res  = await fetch(`/budgets/${_pendingDeletePk}/delete/`, {
        method:  'POST',
        headers: { 'X-CSRFToken': _getCsrf() },
      });
      const data = await res.json();
      if (data.ok) {
        _showFlash('Budget entry deleted.', 'success');
        if (window._deleteRedirectUrl) {
          setTimeout(() => { window.location.href = window._deleteRedirectUrl; }, 600);
        } else {
          document.querySelector(`tr[data-budget-id="${_pendingDeletePk}"]`)?.remove();
          filterBudgets();
        }
      } else {
        _showFlash(data.detail || 'Delete failed.', 'error');
      }
    } catch {
      _showFlash('An unexpected error occurred.', 'error');
    }
  });

  bootstrap.Modal.getOrCreateInstance(modal).show();
}

/* ── Form: live remaining preview ───────────────────────── */
function calcRemaining() {
  const allocEl     = document.getElementById('id_budget_allocated');
  const refinedEl   = document.getElementById('id_refined_budget');
  const displayEl   = document.getElementById('remaining-display');
  const breakdownEl = document.getElementById('remaining-breakdown');
  if (!displayEl) return;

  const estimates   = window._estimatesValue || 0;
  const allocated   = parseFloat(allocEl?.value)  || 0;
  const refined     = parseFloat(refinedEl?.value) || 0;

  // Active budget: refined if set, else allocated
  const activeBudget = (refinedEl?.value?.trim() !== '') ? refined : allocated;

  if (activeBudget <= 0) {
    displayEl.textContent       = '—';
    displayEl.style.background  = '#f8fafc';
    displayEl.style.borderColor = '#e2e8f0';
    displayEl.style.color       = '#475569';
    if (breakdownEl) breakdownEl.textContent =
      '(Refined budget if set, else allocated) − estimates. Only shown when budget > 0.';
    return;
  }

  const remaining = activeBudget - estimates;
  const pct       = activeBudget > 0 ? (remaining / activeBudget) : 1;

  displayEl.textContent = `£${remaining.toFixed(2)}`;

  if (remaining < 0) {
    // Over budget — red
    displayEl.style.background  = '#fef2f2';
    displayEl.style.borderColor = '#fecaca';
    displayEl.style.color       = '#991b1b';
  } else if (pct <= 0.10) {
    // At risk — amber
    displayEl.style.background  = '#fffbeb';
    displayEl.style.borderColor = '#fde68a';
    displayEl.style.color       = '#92400e';
  } else {
    // OK — green
    displayEl.style.background  = '#f0fdf4';
    displayEl.style.borderColor = '#bbf7d0';
    displayEl.style.color       = '#15803d';
  }

  if (breakdownEl) {
    const activeLabel = (refinedEl?.value?.trim() !== '') ? 'Refined' : 'Allocated';
    breakdownEl.innerHTML =
      `${activeLabel} £${activeBudget.toFixed(2)} − ` +
      `Estimates £${Number(estimates).toFixed(2)} = ` +
      `<strong>£${remaining.toFixed(2)}</strong>`;
  }
}

/* ── Project select: update estimates display ───────────── */
function onProjectChange(projectPk) {
  const select    = document.getElementById('id_project');
  const option    = select?.options[select.selectedIndex];
  const estimates = option?.dataset.estimates;
  const displayEl = document.getElementById('estimates-display');

  if (displayEl) {
    if (estimates && estimates !== '') {
      window._estimatesValue = parseFloat(estimates);
      displayEl.textContent  = `£${parseFloat(estimates).toFixed(2)}`;
    } else {
      window._estimatesValue = 0;
      displayEl.textContent  = '—';
    }
  }
  calcRemaining();
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

document.addEventListener('DOMContentLoaded', () => {
  calcRemaining();
});