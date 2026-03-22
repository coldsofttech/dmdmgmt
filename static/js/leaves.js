/* =========================================================
   Resource Planner — leaves.js
   ========================================================= */

'use strict';

/* ── Live filter (search + dropdowns) ───────────────────────
   Mirrors filterTable() in teams.js exactly:
   · Search input fires on every 'input' keystroke
   · All three dropdowns call filterLeavesTable() via onchange
   · Reads data-* attributes from each <tr>, never cell text
   ─────────────────────────────────────────────────────────── */
const leaveSearchInput = document.getElementById('leave-search');
const fyFilter         = document.getElementById('fy-filter');
const teamFilter       = document.getElementById('team-filter');
const memberFilter     = document.getElementById('member-filter');

// Wire the search input to fire on every keystroke instantly
if (leaveSearchInput) {
  leaveSearchInput.addEventListener('input', filterLeavesTable);
}

function filterLeavesTable() {
  const query      = (leaveSearchInput?.value || '').toLowerCase().trim();
  const fyVal      = (fyFilter?.value         || '').toLowerCase().trim();
  const teamVal    = (teamFilter?.value        || '').toLowerCase().trim();
  const memberVal  = (memberFilter?.value      || '').toLowerCase().trim();

  const rows    = document.querySelectorAll('#leaves-table tbody tr[data-leave-id]');
  let   visible = 0;

  rows.forEach(row => {
    const member = (row.dataset.member || '').toLowerCase();
    const team   = (row.dataset.team   || '').toLowerCase();
    const fy     = (row.dataset.fy     || '').toLowerCase();

    // Search matches against member name
    const matchSearch = !query     || member.includes(query);
    const matchFy     = !fyVal     || fy     === fyVal;
    const matchTeam   = !teamVal   || team   === teamVal;
    const matchMember = !memberVal || member === memberVal;

    const show = matchSearch && matchFy && matchTeam && matchMember;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  // Update the stat card count to reflect visible rows
  const countEl = document.getElementById('visible-count');
  if (countEl) countEl.textContent = visible;

  // Show/hide the "no results" empty row
  let emptyRow = document.getElementById('empty-filter-row');
  if (visible === 0 && rows.length > 0) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'empty-filter-row';
      emptyRow.innerHTML = `
        <td colspan="7" class="text-center py-4 text-secondary">
          <i class="bi bi-search me-2"></i>No leaves match your filters.
        </td>`;
      document.querySelector('#leaves-table tbody').appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* ── Holiday cache ───────────────────────────────────────────
   Fetched once per FY pk, cached here for the form's live
   working-day preview. Not used on the list page.
   ─────────────────────────────────────────────────────────── */
const _holidayCache = {};
let   _currentFyPk  = '';

async function loadHolidaysForFy(fyPk) {
  if (!fyPk) { _currentFyPk = ''; return; }
  _currentFyPk = String(fyPk);
  if (_holidayCache[_currentFyPk]) return;
  try {
    const res  = await fetch(`/leaves/holiday-dates/?fy=${encodeURIComponent(fyPk)}`);
    const data = await res.json();
    _holidayCache[_currentFyPk] = new Set(data.holiday_dates || []);
  } catch {
    _holidayCache[_currentFyPk] = new Set();
  }
}

async function onFyChange(fyPk) {
  await loadHolidaysForFy(fyPk);
  calcDays();
}

/* ── Working-day calculation (mirrors models.py) ─────────────
   Returns { working, calendar, weekends, publicHols } or null.
   ─────────────────────────────────────────────────────────── */
function _countWorkingDays(startStr, endStr) {
  if (!startStr || !endStr) return null;
  const start = new Date(startStr + 'T00:00:00');
  const end   = new Date(endStr   + 'T00:00:00');
  if (isNaN(start) || isNaN(end) || end < start) return null;

  const holidays = _holidayCache[_currentFyPk] || new Set();
  let calendar = 0, weekends = 0, publicHols = 0, working = 0;
  let current  = new Date(start);

  while (current <= end) {
    calendar++;
    const iso = current.toISOString().slice(0, 10);
    const dow = current.getDay(); // 0=Sun, 6=Sat
    if (dow === 0 || dow === 6)   { weekends++;    }
    else if (holidays.has(iso))   { publicHols++;  }
    else                          { working++;     }
    current = new Date(current.getTime() + 86400000);
  }
  return { working, calendar, weekends, publicHols };
}

/* ── Form: live working-days preview ─────────────────────── */
function calcDays() {
  const startEl     = document.getElementById('id_start_date');
  const endEl       = document.getElementById('id_end_date');
  const displayEl   = document.getElementById('days-display');
  const breakdownEl = document.getElementById('days-breakdown');
  if (!displayEl) return;

  const result = _countWorkingDays(startEl?.value, endEl?.value);

  if (!result) {
    displayEl.textContent       = '—';
    displayEl.style.background  = '#f0fdf4';
    displayEl.style.borderColor = '#bbf7d0';
    displayEl.style.color       = '#15803d';
    if (breakdownEl) breakdownEl.textContent = 'Excludes weekends and public holidays.';
    return;
  }

  const { working, calendar, weekends, publicHols } = result;
  displayEl.textContent       = `${working}d`;
  displayEl.style.background  = working > 20 ? '#fef2f2' : working > 10 ? '#fffbeb' : '#f0fdf4';
  displayEl.style.borderColor = working > 20 ? '#fecaca' : working > 10 ? '#fde68a' : '#bbf7d0';
  displayEl.style.color       = working > 20 ? '#991b1b' : working > 10 ? '#92400e' : '#15803d';

  if (breakdownEl) {
    const parts = [
      `${calendar} calendar day${calendar !== 1 ? 's' : ''}`,
      `− ${weekends} weekend${weekends !== 1 ? 's' : ''}`,
    ];
    if (publicHols > 0) parts.push(`− ${publicHols} public holiday${publicHols !== 1 ? 's' : ''}`);
    parts.push(`= <strong>${working} working day${working !== 1 ? 's' : ''}</strong>`);
    breakdownEl.innerHTML = parts.join(' ');
  }
}

/* ── Delete ─────────────────────────────────────────────── */
let _pendingDeletePk   = null;
let _pendingDeleteName = null;

function deleteLeave(pk, name) {
  _pendingDeletePk   = pk;
  _pendingDeleteName = name;

  const nameEl = document.getElementById('delete-leave-name');
  if (nameEl) nameEl.textContent = name;

  const modal = document.getElementById('deleteModal');
  if (!modal) return;

  const btn    = document.getElementById('confirm-delete-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    try {
      const res  = await fetch(`/leaves/${_pendingDeletePk}/delete/`, {
        method:  'POST',
        headers: { 'X-CSRFToken': _getCsrf() },
      });
      const data = await res.json();
      if (data.ok) {
        _showFlash('Leave deleted.', 'success');
        if (window._deleteRedirectUrl) {
          setTimeout(() => { window.location.href = window._deleteRedirectUrl; }, 600);
        } else {
          document.querySelector(`tr[data-leave-id="${_pendingDeletePk}"]`)?.remove();
          filterLeavesTable(); // recount visible rows after removal
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

function sortLeavesTable(colIndex) {
  const tbody = document.querySelector('#leaves-table tbody');
  if (!tbody) return;

  _sortState.asc = _sortState.col === colIndex ? !_sortState.asc : true;
  _sortState.col = colIndex;

  document.querySelectorAll('#leaves-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (_sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-leave-id]'));
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
  if (!window._initialFyPk) calcDays();
});