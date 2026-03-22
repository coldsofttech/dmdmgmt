/* =========================================================
   Resource Planner — holidays.js
   ========================================================= */

'use strict';

/* ── Delete ─────────────────────────────────────────────── */
let _pendingDeletePk   = null;
let _pendingDeleteName = null;

function deleteHoliday(pk, name) {
  _pendingDeletePk   = pk;
  _pendingDeleteName = name;

  const nameEl = document.getElementById('delete-holiday-name');
  if (nameEl) nameEl.textContent = name;

  const modal = document.getElementById('deleteModal');
  if (!modal) return;

  const btn    = document.getElementById('confirm-delete-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    try {
      const res  = await fetch(`/holidays/${_pendingDeletePk}/delete/`, {
        method:  'POST',
        headers: { 'X-CSRFToken': _getCsrf() },
      });
      const data = await res.json();
      if (data.ok) {
        _showFlash('Holiday deleted.', 'success');

        // If the detail page set a redirect URL, use it.
        // Otherwise remove the row from the table in place (list / FY detail page).
        if (window._deleteRedirectUrl) {
          setTimeout(() => { window.location.href = window._deleteRedirectUrl; }, 600);
        } else {
          document.querySelector(
            `tr[data-holiday-id="${_pendingDeletePk}"]`
          )?.remove();
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

/* ── Table sort ─────────────────────────────────────────── */
let _sortState = { col: -1, asc: true };

function sortTable(colIndex) {
  const tbody = document.querySelector('#holidays-table tbody');
  if (!tbody) return;

  _sortState.asc = _sortState.col === colIndex ? !_sortState.asc : true;
  _sortState.col = colIndex;

  document.querySelectorAll('#holidays-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (_sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-holiday-id]'));
  rows.sort((a, b) => {
    const aCell = a.cells[colIndex];
    const bCell = b.cells[colIndex];
    const aVal  = (aCell?.dataset.sort ?? aCell?.innerText ?? '').trim();
    const bVal  = (bCell?.dataset.sort ?? bCell?.innerText ?? '').trim();
    const cmp   = aVal.localeCompare(bVal, undefined, { numeric: true });
    return _sortState.asc ? cmp : -cmp;
  });
  rows.forEach(r => tbody.appendChild(r));
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