/* =========================================================
   Resource Planner — sprints.js
   Handles: delete sprint, delete all for FY,
            table sort, form helpers (duration preview, name hint)
   ========================================================= */

'use strict';

/* ── Delete single sprint ───────────────────────────────── */
let _pendingDeletePk   = null;
let _pendingDeleteName = null;

function deleteSprint(pk, name) {
  _pendingDeletePk   = pk;
  _pendingDeleteName = name;

  const nameEl = document.getElementById('delete-sprint-name');
  if (nameEl) nameEl.textContent = name;

  const modal = document.getElementById('deleteModal');
  if (!modal) return;

  const btn    = document.getElementById('confirm-delete-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    try {
      const res  = await fetch(`/sprints/${_pendingDeletePk}/delete/`, {
        method:  'POST',
        headers: { 'X-CSRFToken': _getCsrf() },
      });
      const data = await res.json();
      if (data.ok) {
        _showFlash('Sprint deleted.', 'success');
        if (window._deleteRedirectUrl) {
          setTimeout(() => { window.location.href = window._deleteRedirectUrl; }, 500);
        } else {
          document.querySelector(`tr[data-sprint-id="${_pendingDeletePk}"]`)?.remove();
          _updateTotalCount(-1);
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

/* ── Delete all sprints for a FY ────────────────────────── */
let _pendingDeleteFyPk   = null;
let _pendingDeleteFyName = null;

function confirmDeleteFY(fyPk, fyName) {
  _pendingDeleteFyPk   = fyPk;
  _pendingDeleteFyName = fyName;

  const nameEl = document.getElementById('delete-fy-name');
  if (nameEl) nameEl.textContent = fyName;

  const modal = document.getElementById('deleteFYModal');
  if (!modal) return;

  const btn    = document.getElementById('confirm-delete-fy-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    newBtn.disabled    = true;
    newBtn.textContent = 'Deleting…';

    const fd = new FormData();
    fd.append('fy', _pendingDeleteFyPk);

    try {
      const res  = await fetch('/sprints/delete-fy/', {
        method:  'POST',
        headers: { 'X-CSRFToken': _getCsrf() },
        body:    fd,
      });
      const data = await res.json();
      if (data.ok) {
        _showFlash(
          `${data.deleted} sprint${data.deleted !== 1 ? 's' : ''} deleted for ${_pendingDeleteFyName}.`,
          'success'
        );
        setTimeout(() => {
          window.location.href = `/sprints/?fy=${_pendingDeleteFyPk}`;
        }, 800);
      } else {
        _showFlash(data.detail || 'Delete failed.', 'error');
        newBtn.disabled    = false;
        newBtn.textContent = 'Delete all sprints';
      }
    } catch {
      _showFlash('An unexpected error occurred.', 'error');
      newBtn.disabled    = false;
      newBtn.textContent = 'Delete all sprints';
    }
  });

  bootstrap.Modal.getOrCreateInstance(modal).show();
}

/* ── Table sort ─────────────────────────────────────────── */
let _sortState = { col: -1, asc: true };

function sortSprintTable(colIndex) {
  const tbody = document.querySelector('#sprints-table tbody');
  if (!tbody) return;

  _sortState.asc = _sortState.col === colIndex ? !_sortState.asc : true;
  _sortState.col = colIndex;

  document.querySelectorAll('#sprints-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (_sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-sprint-id]'));
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

/* ── Form helpers (sprint_form.html) ────────────────────── */

/**
 * Auto-fill the sprint name field with "Sprint N" when the number changes,
 * but only if the name still matches the generated pattern (not custom-typed).
 */
function updateNameHint(numberVal) {
  const nameEl = document.getElementById('id_name');
  if (!nameEl) return;
  const current = nameEl.value.trim();
  if (!current || /^Sprint\s+\d+$/i.test(current)) {
    const n = parseInt(numberVal, 10);
    if (!isNaN(n) && n > 0) {
      nameEl.value = `Sprint ${n}`;
    }
  }
}

/**
 * Live duration preview for the sprint edit/create form.
 *
 * Sprint structure (2-week / 10 working-day sprint):
 *   start_date  = Monday  (first day of sprint)
 *   end_date    = Sunday  (last calendar day, 2 days after the second Friday)
 *   calendar    = 14 days (Mon to Sun inclusive)
 *   working     = 10 days (Mon–Fri × 2 weeks, excluding weekends)
 *
 * Month is derived from the last FRIDAY of the sprint
 * (i.e. end_date − 2 days when end_date is a Sunday), matching the server rule
 * that "month = month of the last working day".
 *
 * Note: holiday exclusion is handled server-side; the JS preview shows the
 * Mon–Fri day count without holiday deduction, which is accurate for display.
 */
function calcSprintDuration() {
  const startEl   = document.getElementById('id_start_date');
  const endEl     = document.getElementById('id_end_date');
  const displayEl = document.getElementById('duration-display');
  if (!displayEl) return;

  const startVal = startEl?.value;
  const endVal   = endEl?.value;

  if (!startVal || !endVal) {
    _setDurationDisplay(displayEl, '—', false);
    return;
  }

  const start = new Date(startVal + 'T00:00:00');
  const end   = new Date(endVal   + 'T00:00:00');

  if (isNaN(start) || isNaN(end) || end < start) {
    _setDurationDisplay(displayEl, '—', false);
    return;
  }

  // Total calendar days (inclusive)
  const calDays = Math.round((end - start) / 86400000) + 1;

  // Count Mon–Fri days in the sprint window (no holiday deduction client-side)
  let workingDays = 0;
  let cur = new Date(start);
  while (cur <= end) {
    const dow = cur.getDay(); // 0 = Sun, 6 = Sat
    if (dow !== 0 && dow !== 6) workingDays++;
    cur = new Date(cur.getTime() + 86400000);
  }

  /*
   * Month derivation:
   * Server sets month = end_date.month (month of the Sunday).
   * For a standard 14-day sprint this is the same as the last Friday's month
   * in almost all cases. When they differ (e.g. sprint ends Sun 1 Apr), the
   * server intentionally uses the Sunday's month so this preview matches.
   */
  const month = end.toLocaleString('en-GB', { month: 'long' });

  // Warn if the span doesn't look like a standard 2-week sprint
  const isStandard = (calDays === 14 && workingDays === 10);

  const label = isStandard
    ? `${calDays} calendar days · ${workingDays} working days · Month: ${month}`
    : `${calDays} calendar days · ${workingDays} working days · Month: ${month}`
      + (calDays !== 14 ? ` (standard is 14 cal days)` : '');

  _setDurationDisplay(displayEl, label, true);
}

function _setDurationDisplay(el, text, ok) {
  el.textContent     = text;
  el.style.background  = ok ? '#f0fdf4' : '#f8fafc';
  el.style.borderColor = ok ? '#bbf7d0' : '#e2e8f0';
  el.style.color       = ok ? '#15803d' : '#64748b';
}

/* ── Internal helpers ────────────────────────────────────── */

function _updateTotalCount(delta) {
  // Target the first stat-value on the page (Total sprints card)
  const el = document.querySelector('[data-stat="total-sprints"]')
          || document.querySelector('.rp-stat-value');
  if (!el) return;
  const current = parseInt(el.textContent, 10);
  if (!isNaN(current)) el.textContent = Math.max(0, current + delta);
}

function _getCsrf() {
  if (typeof getCsrfToken === 'function') return getCsrfToken();
  const c = document.cookie.split(';').find(x => x.trim().startsWith('csrftoken='));
  return c ? c.split('=')[1].trim() : '';
}

function _showFlash(msg, type) {
  if (typeof showFlash === 'function') { showFlash(msg, type); return; }
  alert(msg);
}

// Run duration preview immediately on page load (for the edit form with pre-filled dates)
document.addEventListener('DOMContentLoaded', () => {
  calcSprintDuration();
});