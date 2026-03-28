/* =========================================================
   Resource Planner — resource_plan.js  (Round C)
   Fixes:
   2.15 — Month toggle uses data-val (not data-days / innerText)
          so all three sections aggregate correctly
   2.23 — LOCKED plan blocks all cell edits at JS level too
   2.24 — Smart decimal formatter: 8→8, 8.5→8.5, 8.25→8.25
   Also:
   - Accordion chevron: right→down on expand (CSS drives it)
   - Section 1.5 aggregates correctly in month view
   ========================================================= */

'use strict';

/* ── Decimal formatter (2.24) ────────────────────────────
   Rules:
     8.00  → "8"
     8.50  → "8.5"
     8.25  → "8.25"
     0.00  → "—"
──────────────────────────────────────────────────────── */
function _fmt(value) {
  const n = parseFloat(value);
  if (isNaN(n) || n === 0) return '—';
  // Remove trailing zeros after decimal point
  return n % 1 === 0 ? String(n) : n.toFixed(2).replace(/0+$/, '');
}

/* ── Sprint / Month toggle (2.15) ─────────────────────── */

let _viewMode = 'sprint';

function setViewMode(mode) {
  if (window._planLocked) return;
  _viewMode = mode;
  document.getElementById('btn-sprint-view')?.classList.toggle('active', mode === 'sprint');
  document.getElementById('btn-month-view')?.classList.toggle('active', mode === 'month');

  if (mode === 'sprint') {
    _showSprintColumns();
  } else {
    _showMonthColumns();
  }
}

function _showSprintColumns() {
  // Restore all sprint TH columns
  document.querySelectorAll('th.sprint-col').forEach(th => {
    th.style.display = '';
  });
  // Remove synthetic month headers
  document.querySelectorAll('th.month-col-synthetic').forEach(el => el.remove());
  // Restore all sprint TD cells
  document.querySelectorAll('td[data-sprint]').forEach(td => {
    td.style.display = '';
  });
  // Remove merged month cells
  document.querySelectorAll('td.month-merged').forEach(td => td.remove());
}

function _showMonthColumns() {
  // Build month → [sprint_pk, ...] map from the first table's TH headers
  const monthMap   = {};
  const monthOrder = [];

  document.querySelectorAll('th.sprint-col[data-sprint]').forEach(th => {
    const month    = th.dataset.month;
    const sprintPk = th.dataset.sprint;
    if (month && !monthMap[month]) {
      monthMap[month] = [];
      monthOrder.push(month);
    }
    if (month) monthMap[month].push(sprintPk);
  });

  document.querySelectorAll('.rp-grid-table').forEach(table => {
    _collapseTableToMonths(table, monthMap, monthOrder);
  });
}

function _collapseTableToMonths(table, monthMap, monthOrder) {
  // ── Header ────────────────────────────────────────────
  const headerRow = table.querySelector('thead tr');
  if (!headerRow) return;

  headerRow.querySelectorAll('th.sprint-col').forEach(th => {
    th.style.display = 'none';
  });
  headerRow.querySelectorAll('th.month-col-synthetic').forEach(el => el.remove());

  monthOrder.forEach(month => {
    const th = document.createElement('th');
    th.className = 'rp-grid-th month-col-synthetic';
    th.innerHTML = `<div class="rp-grid-th-label">${month}</div>`;
    headerRow.appendChild(th);
  });

  // ── Body + tfoot ──────────────────────────────────────
  table.querySelectorAll('tbody tr, tfoot tr').forEach(row => {
    // Hide individual sprint cells
    row.querySelectorAll('td[data-sprint]').forEach(td => {
      td.style.display = 'none';
    });
    // Remove previous month merged cells
    row.querySelectorAll('td.month-merged').forEach(td => td.remove());

    monthOrder.forEach(month => {
      const sprintPks = monthMap[month] || [];
      let total    = 0;
      let allLocked = true;
      let anyOver   = false;
      let anyOntrack = false;
      let hasData   = false;

      sprintPks.forEach(pk => {
        // Use data-val — set on EVERY cell type (s1, s1.5, s2, s3, tfoot)
        // This avoids the old bug of reading innerText which contained icons/badges
        const cell = row.querySelector(`td[data-sprint="${pk}"]`);
        if (cell) {
          const raw = parseFloat(cell.dataset.val) || 0;
          total += raw;
          if (raw !== 0) hasData = true;
          if (!cell.classList.contains('rp-grid-cell--locked')) allLocked = false;
          if (cell.classList.contains('rp-grid-cell--over'))    anyOver   = true;
          if (cell.classList.contains('rp-grid-cell--ontrack')) anyOntrack = true;
        }
      });

      const td = document.createElement('td');
      td.className = 'rp-grid-cell month-merged';
      td.dataset.val = total;

      if (allLocked && sprintPks.length > 0) td.classList.add('rp-grid-cell--locked');
      if (anyOver)    td.classList.add('rp-grid-cell--over');
      if (anyOntrack && !anyOver) td.classList.add('rp-grid-cell--ontrack');

      td.textContent = hasData ? _fmt(total) : '—';
      if (!hasData) td.classList.add('rp-grid-zero');

      row.appendChild(td);
    });
  });
}


/* ── Inline cell editing ─────────────────────────────── */

let _activeCell     = null;
let _activePlanPk   = null;
let _activeAsmtPk   = null;
let _activeSprintPk = null;

document.addEventListener('DOMContentLoaded', () => {
  _wireEditableCells();
  _wireAccordionChevrons();
});

function _wireEditableCells() {
  document.querySelectorAll('td.rp-grid-cell--editable').forEach(td => {
    td.addEventListener('click', _openCellEditor);
  });
}

function _openCellEditor(e) {
  const td = e.currentTarget;

  // 2.23 — LOCKED plan guard
  if (window._planLocked) {
    _showFlash('This plan is locked. Change status to Draft or Active to edit.', 'warning');
    return;
  }
  if (td.dataset.locked === 'true') return;

  _activeCell     = td;
  _activePlanPk   = td.dataset.plan;
  _activeAsmtPk   = td.dataset.assignment;
  _activeSprintPk = td.dataset.sprint;

  const editor = document.getElementById('rp-cell-editor');
  const input  = document.getElementById('rp-cell-input');
  const hint   = document.getElementById('rp-cell-hint');
  if (!editor || !input) return;

  // 2.24 — Use data-days or data-val, NOT innerText
  const current = parseFloat(td.dataset.days ?? td.dataset.val) || 0;
  input.value   = current;

  const rect = td.getBoundingClientRect();
  editor.style.top  = (rect.bottom + window.scrollY + 6) + 'px';
  editor.style.left = Math.min(
    rect.left + window.scrollX,
    window.innerWidth - 220
  ) + 'px';
  editor.classList.remove('d-none');
  input.focus();
  input.select();

  if (hint) {
    hint.textContent = td.classList.contains('rp-grid-cell--auto')
      ? 'Auto-filled — editing marks as manual override.'
      : td.classList.contains('rp-grid-cell--manual')
        ? 'Manually overridden.'
        : 'Enter days (0–10, multiples of 0.25).';
  }
}

function closeCellEditor() {
  document.getElementById('rp-cell-editor')?.classList.add('d-none');
  _activeCell = _activePlanPk = _activeAsmtPk = _activeSprintPk = null;
}

async function saveCellEdit() {
  const input = document.getElementById('rp-cell-input');
  if (!input || !_activeCell) return;

  const raw = parseFloat(input.value);
  if (isNaN(raw) || raw < 0 || raw > 10) {
    _showFlash('Value must be 0–10.', 'warning');
    return;
  }

  // Round to nearest 0.25
  const days = Math.round(raw * 4) / 4;
  const url  = `${window._cellUpdateBase}${_activeAsmtPk}/${_activeSprintPk}/`;

  try {
    const res  = await fetch(url, {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  window._csrfToken,
      },
      body: JSON.stringify({ days, changed_by: 'User' }),
    });
    const data = await res.json();

    if (data.ok) {
      // 2.24 — Update cell display with smart formatter
      const display = _fmt(days);
      _activeCell.innerHTML = days > 0
        ? display
        : '<span class="rp-grid-zero">—</span>';

      // Keep data-days and data-val in sync
      _activeCell.dataset.days = days;
      _activeCell.dataset.val  = days;

      // Update classes
      _activeCell.classList.remove('rp-grid-cell--auto');
      if (days > 0) {
        _activeCell.classList.add('rp-grid-cell--manual');
      } else {
        _activeCell.classList.remove('rp-grid-cell--manual');
      }

      _updateS2Totals(_activeCell);
      _showFlash(`Saved: ${display === '—' ? '0' : display}d`, 'success');
    } else {
      // 2.23 — Show lock message if returned from server
      _showFlash(data.detail || 'Save failed.', 'error');
    }
  } catch {
    _showFlash('Network error.', 'error');
  }

  closeCellEditor();
}

// Close on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeCellEditor();
});

// Close on outside click
document.addEventListener('click', e => {
  const editor = document.getElementById('rp-cell-editor');
  if (!editor || editor.classList.contains('d-none')) return;
  if (!editor.contains(e.target) &&
      !e.target.closest('td.rp-grid-cell--editable')) {
    closeCellEditor();
  }
});


/* ── Section 2 totals recomputation ──────────────────── */

function _updateS2Totals(changedCell) {
  const table    = changedCell.closest('.rp-grid-table');
  if (!table) return;
  const sprintPk = changedCell.dataset.sprint;
  const totalCell = table.querySelector(
    `tfoot tr td[data-sprint="${sprintPk}"]`
  );
  if (!totalCell) return;

  let total = 0;
  table.querySelectorAll(
    `tbody td.rp-grid-cell--editable[data-sprint="${sprintPk}"],
     tbody td.rp-grid-cell--locked[data-sprint="${sprintPk}"]`
  ).forEach(td => {
    total += parseFloat(td.dataset.days ?? td.dataset.val) || 0;
  });

  totalCell.innerHTML = total > 0
    ? _fmt(total)
    : '<span class="rp-grid-zero">—</span>';
  totalCell.dataset.val = total;
}


/* ── Delete plan ─────────────────────────────────────── */

let _pendingDeletePk = null;

function deletePlan(pk, name) {
  _pendingDeletePk = pk;
  const nameEl = document.getElementById('delete-plan-name');
  if (nameEl) nameEl.textContent = name;

  const modal = document.getElementById('deleteModal');
  if (!modal) return;

  const btn    = document.getElementById('confirm-delete-btn');
  const newBtn = btn.cloneNode(true);
  btn.replaceWith(newBtn);

  newBtn.addEventListener('click', async () => {
    bootstrap.Modal.getInstance(modal)?.hide();
    try {
      const res  = await fetch(`/resource-plan/${_pendingDeletePk}/delete/`, {
        method:  'POST',
        headers: { 'X-CSRFToken': window._csrfToken || _getCsrf() },
      });
      const data = await res.json();
      if (data.ok) {
        _showFlash('Resource plan deleted.', 'success');
        setTimeout(() => { window.location.href = '/resource-plan/'; }, 700);
      } else {
        _showFlash(data.detail || 'Delete failed.', 'error');
      }
    } catch {
      _showFlash('Network error.', 'error');
    }
  });

  bootstrap.Modal.getOrCreateInstance(modal).show();
}


/* ── Accordion chevron (right → down on expand) ──────── */

function _wireAccordionChevrons() {
  document.querySelectorAll('.rp-accordion-header').forEach(btn => {
    const targetId = btn.getAttribute('data-bs-target');
    if (!targetId) return;
    const target = document.querySelector(targetId);
    if (!target) return;

    target.addEventListener('show.bs.collapse', () => {
      btn.querySelector('.rp-accordion-chevron')
         ?.classList.add('rp-accordion-chevron--open');
    });
    target.addEventListener('hide.bs.collapse', () => {
      btn.querySelector('.rp-accordion-chevron')
         ?.classList.remove('rp-accordion-chevron--open');
    });
  });
}


/* ── Helpers ─────────────────────────────────────────── */

function _getCsrf() {
  if (window._csrfToken) return window._csrfToken;
  if (typeof getCsrfToken === 'function') return getCsrfToken();
  const c = document.cookie.split(';').find(x => x.trim().startsWith('csrftoken='));
  return c ? c.split('=')[1].trim() : '';
}

function _showFlash(msg, type) {
  if (typeof showFlash === 'function') { showFlash(msg, type); return; }
  const div = document.createElement('div');
  div.className = `alert alert-${
    type === 'error' ? 'danger' : type === 'success' ? 'success' : 'warning'
  } alert-dismissible fade show`;
  div.style.cssText =
    'position:fixed;top:70px;right:20px;z-index:9999;min-width:260px;font-size:13px';
  div.innerHTML =
    `${msg}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
  document.body.appendChild(div);
  setTimeout(() => div.remove(), 3500);
}