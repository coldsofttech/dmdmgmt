/* =========================================================
   Resource Planner — resource_plan.js
   Phase 1 covers:
     - Sprint / month column toggle
     - Inline cell editing (Section 2 editable cells)
     - Delete plan confirmation
     - Accordion chevron animation
     - Month aggregation (collapse sprint cols into month cols)
   ========================================================= */

'use strict';

/* ── Sprint / Month toggle ──────────────────────────────── */

let _viewMode = 'sprint';  // 'sprint' | 'month'

function setViewMode(mode) {
  _viewMode = mode;

  // Update button states
  document.getElementById('btn-sprint-view')?.classList.toggle('active', mode === 'sprint');
  document.getElementById('btn-month-view')?.classList.toggle('active', mode === 'month');

  if (mode === 'sprint') {
    _showSprintColumns();
  } else {
    _showMonthColumns();
  }
}

function _showSprintColumns() {
  // Show all individual sprint columns
  document.querySelectorAll('.sprint-col').forEach(th => {
    th.style.display = '';
  });
  // Remove any synthetic month header columns
  document.querySelectorAll('.month-col-synthetic').forEach(el => el.remove());
  // Restore all sprint data cells
  document.querySelectorAll('td.rp-grid-cell[data-sprint]').forEach(td => {
    td.style.display = '';
  });
  document.querySelectorAll('td.month-merged').forEach(td => td.remove());
}

function _showMonthColumns() {
  // Build month → [sprint_pks] map from the DOM
  const monthMap = {};    // month_name → [sprint_pk, ...]
  const monthOrder = [];  // ordered month names

  document.querySelectorAll('th.sprint-col[data-sprint]').forEach(th => {
    const month    = th.dataset.month;
    const sprintPk = th.dataset.sprint;
    if (!monthMap[month]) {
      monthMap[month] = [];
      monthOrder.push(month);
    }
    monthMap[month].push(sprintPk);
  });

  // For each table, collapse sprint columns into month columns
  document.querySelectorAll('.rp-grid-table').forEach(table => {
    _collapseToMonths(table, monthMap, monthOrder);
  });
}

function _collapseToMonths(table, monthMap, monthOrder) {
  // ── Header ───────────────────────────────────────────
  const headerRow = table.querySelector('thead tr');
  if (!headerRow) return;

  // Hide individual sprint TH columns
  headerRow.querySelectorAll('th.sprint-col').forEach(th => {
    th.style.display = 'none';
  });

  // Remove existing synthetic month headers
  headerRow.querySelectorAll('.month-col-synthetic').forEach(el => el.remove());

  // Add one TH per month
  monthOrder.forEach(month => {
    const th = document.createElement('th');
    th.className = 'rp-grid-th month-col-synthetic';
    th.innerHTML = `<div class="rp-grid-th-label">${month}</div>`;
    headerRow.appendChild(th);
  });

  // ── Body rows ─────────────────────────────────────────
  table.querySelectorAll('tbody tr, tfoot tr').forEach(row => {
    // Hide sprint cells
    row.querySelectorAll('td[data-sprint]').forEach(td => {
      td.style.display = 'none';
    });
    // Remove existing merged month cells
    row.querySelectorAll('td.month-merged').forEach(td => td.remove());

    // Add one aggregated TD per month
    monthOrder.forEach(month => {
      const sprintPks = monthMap[month];
      let total = 0;
      let allLocked = true;
      let anyOver = false;
      let anyOntrack = false;

      sprintPks.forEach(pk => {
        const cell = row.querySelector(`td[data-sprint="${pk}"]`);
        if (cell) {
          const val = parseFloat(cell.dataset.days || cell.innerText.trim()) || 0;
          total += val;
          if (!cell.classList.contains('rp-grid-cell--locked')) allLocked = false;
          if (cell.classList.contains('rp-grid-cell--over'))    anyOver   = true;
          if (cell.classList.contains('rp-grid-cell--ontrack')) anyOntrack = true;
        }
      });

      const td = document.createElement('td');
      td.className = 'rp-grid-cell month-merged';
      if (allLocked)  td.classList.add('rp-grid-cell--locked');
      if (anyOver)    td.classList.add('rp-grid-cell--over');
      if (anyOntrack) td.classList.add('rp-grid-cell--ontrack');

      td.textContent = total > 0 ? total.toFixed(2).replace(/\.00$/, '') : '—';
      row.appendChild(td);
    });
  });
}


/* ── Inline cell editing (Section 2) ───────────────────── */

let _activeCell    = null;
let _activePlanPk  = null;
let _activeAsmtPk  = null;
let _activeSprintPk = null;

// Wire up click handlers after DOM loads
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('td.rp-grid-cell--editable').forEach(td => {
    td.addEventListener('click', openCellEditor);
  });
  _wireAccordionChevrons();
});

function openCellEditor(e) {
  const td = e.currentTarget;
  if (td.dataset.locked === 'true') return;  // never edit locked cells

  _activeCell     = td;
  _activePlanPk   = td.dataset.plan;
  _activeAsmtPk   = td.dataset.assignment;
  _activeSprintPk = td.dataset.sprint;

  const editor   = document.getElementById('rp-cell-editor');
  const input    = document.getElementById('rp-cell-input');
  const hintEl   = document.getElementById('rp-cell-hint');
  if (!editor || !input) return;

  // Current value
  const current = parseFloat(td.dataset.days) || 0;
  input.value   = current;

  // Position editor near the cell
  const rect = td.getBoundingClientRect();
  editor.style.top  = (rect.bottom + window.scrollY + 4) + 'px';
  editor.style.left = Math.min(rect.left + window.scrollX, window.innerWidth - 200) + 'px';
  editor.classList.remove('d-none');
  input.focus();
  input.select();

  if (hintEl) {
    const isAuto = td.classList.contains('rp-grid-cell--auto');
    hintEl.textContent = isAuto
      ? 'Currently auto-filled. Editing will mark as manual override.'
      : 'Manually overridden.';
  }
}

function closeCellEditor() {
  document.getElementById('rp-cell-editor')?.classList.add('d-none');
  _activeCell     = null;
  _activePlanPk   = null;
  _activeAsmtPk   = null;
  _activeSprintPk = null;
}

async function saveCellEdit() {
  const input = document.getElementById('rp-cell-input');
  if (!input || !_activeCell) return;

  const rawVal = parseFloat(input.value);
  if (isNaN(rawVal) || rawVal < 0 || rawVal > 10) {
    _showFlash('Value must be between 0 and 10.', 'warning');
    return;
  }

  // Round to nearest 0.25 client-side before POST
  const days = Math.round(rawVal * 4) / 4;

  const url = `${window._cellUpdateBase}${_activeAsmtPk}/${_activeSprintPk}/`;
  try {
    const res  = await fetch(url, {
      method:  'POST',
      headers: {
        'Content-Type':  'application/json',
        'X-CSRFToken':   window._csrfToken,
      },
      body: JSON.stringify({ days, changed_by: 'User' }),
    });
    const data = await res.json();

    if (data.ok) {
      // Update the cell value in the DOM
      const displayVal = days > 0 ? String(days) : '—';
      _activeCell.innerHTML = days > 0
        ? displayVal
        : '<span class="rp-grid-zero">—</span>';
      _activeCell.dataset.days = days;

      // Update classes: was auto → now manual
      _activeCell.classList.remove('rp-grid-cell--auto');
      if (days > 0) _activeCell.classList.add('rp-grid-cell--manual');

      // Recompute the section 2 totals row for this sprint
      _updateS2Totals(_activeCell);

      _showFlash(`Saved: ${days}d`, 'success');
    } else {
      _showFlash(data.detail || 'Save failed.', 'error');
    }
  } catch (err) {
    _showFlash('Network error.', 'error');
  }

  closeCellEditor();
}

// Close editor on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeCellEditor();
});

// Close editor when clicking outside
document.addEventListener('click', e => {
  const editor = document.getElementById('rp-cell-editor');
  if (!editor || editor.classList.contains('d-none')) return;
  if (!editor.contains(e.target) && !e.target.classList.contains('rp-grid-cell--editable')) {
    closeCellEditor();
  }
});


/* ── Section 2 totals recomputation ─────────────────────── */

function _updateS2Totals(changedCell) {
  const table      = changedCell.closest('.rp-grid-table');
  if (!table) return;
  const sprintPk   = changedCell.dataset.sprint;
  const tfoot      = table.querySelector('tfoot tr');
  if (!tfoot) return;

  const totalCell = tfoot.querySelector(`td[data-sprint="${sprintPk}"]`);
  if (!totalCell) return;

  let total = 0;
  table.querySelectorAll(
    `tbody td.rp-grid-cell--editable[data-sprint="${sprintPk}"]`
  ).forEach(td => {
    total += parseFloat(td.dataset.days) || 0;
  });

  totalCell.innerHTML = total > 0
    ? total.toFixed(2).replace(/\.00$/, '')
    : '<span class="rp-grid-zero">—</span>';
}


/* ── Delete plan ────────────────────────────────────────── */

let _pendingDeletePk   = null;
let _pendingDeleteName = null;

function deletePlan(pk, name) {
  _pendingDeletePk   = pk;
  _pendingDeleteName = name;

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


/* ── Accordion chevron animation ───────────────────────── */

function _wireAccordionChevrons() {
  document.querySelectorAll('.rp-accordion-header').forEach(btn => {
    const targetId = btn.getAttribute('data-bs-target');
    const target   = targetId ? document.querySelector(targetId) : null;
    if (!target) return;
    target.addEventListener('show.bs.collapse', () => {
      btn.querySelector('.rp-accordion-chevron')?.classList.add('rp-accordion-chevron--open');
    });
    target.addEventListener('hide.bs.collapse', () => {
      btn.querySelector('.rp-accordion-chevron')?.classList.remove('rp-accordion-chevron--open');
    });
  });
}


/* ── Helpers ────────────────────────────────────────────── */

function _getCsrf() {
  if (window._csrfToken) return window._csrfToken;
  if (typeof getCsrfToken === 'function') return getCsrfToken();
  const c = document.cookie.split(';').find(x => x.trim().startsWith('csrftoken='));
  return c ? c.split('=')[1].trim() : '';
}

function _showFlash(msg, type) {
  if (typeof showFlash === 'function') { showFlash(msg, type); return; }
  // Fallback: brief toast-style alert at top of page
  const div  = document.createElement('div');
  div.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'warning'} alert-dismissible fade show`;
  div.style.cssText = 'position:fixed;top:70px;right:20px;z-index:9999;min-width:260px;font-size:13px';
  div.innerHTML = `${msg}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
  document.body.appendChild(div);
  setTimeout(() => div.remove(), 3500);
}