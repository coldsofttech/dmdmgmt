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

  // Snapshot the active cell references before async gap
  const savedCell     = _activeCell;
  const savedAsmtPk   = _activeAsmtPk;
  const savedSprintPk = _activeSprintPk;

  closeCellEditor();

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
      // ── Update the edited cell ──────────────────────
      const display = _fmt(days);
      savedCell.innerHTML = days > 0
        ? display
        : '<span class="rp-grid-zero">—</span>';
      savedCell.dataset.days = days;
      savedCell.dataset.val  = days;
      savedCell.classList.remove('rp-grid-cell--auto');
      savedCell.classList.toggle('rp-grid-cell--manual', days > 0);

      // ── Phase 2: live section updates ───────────────

      // 1. Section 2 tfoot sprint total (use server value for accuracy)
      if (data.sprint_total !== undefined) {
        _updateS2TotalFromServer(savedSprintPk, data.sprint_total);
      } else {
        _updateS2Totals(savedCell);
      }

      // 2. Section 3 remaining for this member × sprint
      if (data.member_remaining !== undefined) {
        const memberPk = savedCell.dataset.member ||
          _getMemberPkFromAssignment(savedAsmtPk);
        if (memberPk) {
          _updateS3Cell(memberPk, savedSprintPk, parseFloat(data.member_remaining));
        }
      }

      // 3. Conflict banner
      if (data.conflict_count !== undefined) {
        _updateConflictBanner(data.conflict_count, data.new_conflicts || []);
      }

      // 4. Unmapped banner
      if (data.unmapped_count !== undefined) {
        _updateUnmappedBanner(data.unmapped_count);
      }

      // 5. Flash — include any new conflict warnings
      let flashMsg = `Saved: ${display === '—' ? '0' : display}d`;
      if (data.new_conflicts && data.new_conflicts.length) {
        const warnings = data.new_conflicts
          .filter(c => c.severity === 'WARNING')
          .map(c => c.description);
        const errors = data.new_conflicts
          .filter(c => c.severity === 'ERROR')
          .map(c => c.description);
        if (errors.length) {
          _showFlash(`${flashMsg} — ⚠ ${errors[0]}`, 'error');
          return;
        }
        if (warnings.length) {
          _showFlash(`${flashMsg} — ⚠ ${warnings[0]}`, 'warning');
          return;
        }
      }
      _showFlash(flashMsg, 'success');

    } else {
      _showFlash(data.detail || 'Save failed.', 'error');
    }
  } catch {
    _showFlash('Network error — check connection.', 'error');
  }
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


/* ── Section 2 totals — local recompute (fallback) ───── */

function _updateS2Totals(changedCell) {
  const table    = changedCell.closest('.rp-grid-table');
  if (!table) return;
  const sprintPk  = changedCell.dataset.sprint;
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

  totalCell.innerHTML   = total > 0
    ? _fmt(total)
    : '<span class="rp-grid-zero">—</span>';
  totalCell.dataset.val = total;
}

/* ── Phase 2: server-accurate sprint total update ────── */

function _updateS2TotalFromServer(sprintPk, serverTotal) {
  const teamPk = _getActiveTeamPk();
  if (!teamPk) return;
  const s2Table = document.getElementById(`grid-s2-${teamPk}`);
  if (!s2Table) return;
  const footCell = s2Table.querySelector(`tfoot td[data-sprint="${sprintPk}"]`);
  if (!footCell) return;
  const val = parseFloat(serverTotal) || 0;
  footCell.innerHTML   = val > 0 ? _fmt(val) : '<span class="rp-grid-zero">—</span>';
  footCell.dataset.val = val;
}

/* ── Phase 2: Section 3 remaining cell live update ────── */

function _updateS3Cell(memberPk, sprintPk, remaining) {
  const teamPk = _getActiveTeamPk();
  if (!teamPk) return;
  const s3Table = document.getElementById(`grid-s3-${teamPk}`);
  if (!s3Table) return;
  const row  = s3Table.querySelector(`tr[data-member="${memberPk}"]`);
  if (!row) return;
  const cell = row.querySelector(`td[data-sprint="${sprintPk}"]`);
  if (!cell) return;

  const rem = parseFloat(remaining);
  cell.innerHTML   = (rem !== 0) ? _fmt(rem) : '<span class="rp-grid-zero">—</span>';
  cell.dataset.val = rem;

  cell.classList.remove(
    'rp-grid-cell--over', 'rp-grid-cell--ontrack', 'rp-grid-cell--s3-ok', 'rp-grid-cell--zero'
  );
  if      (rem < 0)  cell.classList.add('rp-grid-cell--over');
  else if (rem === 0) cell.classList.add('rp-grid-cell--ontrack');
  else                cell.classList.add('rp-grid-cell--s3-ok');

  _updateS3TeamTotal(teamPk, sprintPk);
}

function _updateS3TeamTotal(teamPk, sprintPk) {
  const s3Table  = document.getElementById(`grid-s3-${teamPk}`);
  if (!s3Table) return;
  const footCell = s3Table.querySelector(`tfoot td[data-sprint="${sprintPk}"]`);
  if (!footCell) return;

  let total = 0;
  s3Table.querySelectorAll(`tbody tr[data-member] td[data-sprint="${sprintPk}"]`)
         .forEach(td => { total += parseFloat(td.dataset.val) || 0; });

  footCell.innerHTML   = _fmt(total);
  footCell.dataset.val = total;
  footCell.classList.remove('rp-grid-cell--over', 'rp-grid-cell--ontrack');
  if      (total < 0)  footCell.classList.add('rp-grid-cell--over');
  else if (total === 0) footCell.classList.add('rp-grid-cell--ontrack');
}

/* ── Phase 2: conflict banner live update ────────────── */

function _updateConflictBanner(count, newConflicts) {
  const banner = document.getElementById('conflict-banner');
  if (!banner) return;

  if (count === 0) {
    banner.classList.add('d-none');
    return;
  }

  // Ensure banner is visible with correct markup
  if (banner.classList.contains('d-none')) {
    banner.className =
      'alert alert-danger d-flex gap-2 align-items-start mb-4';
    banner.style.fontSize = '13px';
    banner.innerHTML = `
      <i class="bi bi-exclamation-triangle-fill mt-1 flex-shrink-0"></i>
      <div>
        <strong id="conflict-count-text"></strong>
        <ul class="mb-0 mt-1 ps-3" id="conflict-list"></ul>
      </div>`;
  }

  const countText = document.getElementById('conflict-count-text');
  if (countText) {
    countText.textContent =
      `${count} unresolved conflict${count !== 1 ? 's' : ''}`;
  }

  // Prepend new conflict items to the list (cap at 5)
  const ul = document.getElementById('conflict-list');
  if (ul && newConflicts && newConflicts.length) {
    newConflicts.forEach(c => {
      const li = document.createElement('li');
      li.innerHTML =
        `<span class="fw-500">${_conflictLabel(c.type)}</span> — ${c.description}`;
      ul.prepend(li);
    });
    const items = ul.querySelectorAll('li');
    items.forEach((li, i) => { if (i >= 5) li.remove(); });
  }
}

function _conflictLabel(type) {
  const map = {
    CAPACITY_EXCEEDED: 'Capacity exceeded',
    OVER_BUDGET:       'Over budget/estimate',
    UNDER_BUDGET:      'Under budget/estimate',
    ENGINEER_LEAVE:    'Engineer has leave',
    THRESHOLD_BREACH:  'Threshold breached',
    PRIORITY_CLASH:    'Priority clash',
  };
  return map[type] || type;
}

/* ── Phase 2: unmapped banner live update ────────────── */

function _updateUnmappedBanner(count) {
  const banner    = document.getElementById('unmapped-banner');
  const countText = document.getElementById('unmapped-count-text');
  if (!banner) return;
  if (count === 0) {
    banner.classList.add('d-none');
    return;
  }
  banner.classList.remove('d-none');
  if (countText) {
    countText.textContent =
      `${count} active project${count !== 1 ? 's' : ''}`;
  }
}

/* ── Active team tab helper ──────────────────────────── */

function _getActiveTeamPk() {
  const active = document.querySelector('#teamTabs .nav-link.active');
  return active ? active.id.replace('tab-', '') : null;
}

function _getMemberPkFromAssignment(assignmentPk) {
  const s2Row = document.querySelector(`tr[data-assignment="${assignmentPk}"]`);
  return s2Row ? s2Row.dataset.member : null;
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


/* ═══════════════════════════════════════════════════════
   COLUMN FILTER SYSTEM (2.21)
   Tracks which sprint PKs are "visible". All four sections
   (S1, S1.5, S2, S3) are filtered simultaneously.
   Works in both sprint view and month view.
   ═══════════════════════════════════════════════════════ */

let _allSprintPks   = [];
let _visibleSprints = null;  // null = all shown

document.addEventListener('DOMContentLoaded', () => {
  if (window._sprintMeta) {
    _allSprintPks = window._sprintMeta.map(s => String(s.pk));
  }
});

function toggleColFilterPanel() {
  const panel = document.getElementById('col-filter-panel');
  const btn   = document.getElementById('btn-col-filter');
  if (!panel) return;
  const isOpen = !panel.classList.contains('d-none');
  panel.classList.toggle('d-none', isOpen);
  btn?.classList.toggle('active', !isOpen);
}

function toggleColChip(chip) {
  chip.classList.toggle('active');
  _applyColFilter();
}

function selectAllCols() {
  document.querySelectorAll('.rp-col-filter-chip').forEach(c => c.classList.add('active'));
  _applyColFilter();
}

function selectNoneCols() {
  document.querySelectorAll('.rp-col-filter-chip').forEach(c => c.classList.remove('active'));
  _applyColFilter();
}

function selectCurrentMonthCols() {
  const curMonth = new Date().toLocaleString('en-GB', { month: 'long' });
  document.querySelectorAll('.rp-col-filter-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.month === curMonth);
  });
  _applyColFilter();
}

function selectFutureCols() {
  // Approximate future = sprints in the latter half by DOM order
  const ths    = Array.from(document.querySelectorAll('th.sprint-col[data-sprint]'));
  const unique = [...new Map(ths.map(t => [t.dataset.sprint, t])).values()];
  const mid    = Math.floor(unique.length / 2);
  const futurePks = new Set(unique.slice(mid).map(t => t.dataset.sprint));
  document.querySelectorAll('.rp-col-filter-chip').forEach(c => {
    c.classList.toggle('active', futurePks.has(c.dataset.sprintPk));
  });
  _applyColFilter();
}

function _applyColFilter() {
  const activeChips = document.querySelectorAll('.rp-col-filter-chip.active');
  const activePks   = new Set(Array.from(activeChips).map(c => c.dataset.sprintPk));
  const allActive   = activePks.size >= _allSprintPks.length;
  _visibleSprints   = allActive ? null : activePks;

  // Update badge counter
  const badge = document.getElementById('col-filter-badge');
  if (badge) {
    if (allActive) {
      badge.classList.add('d-none');
    } else {
      const hidden = _allSprintPks.length - activePks.size;
      badge.textContent = hidden + ' hidden';
      badge.classList.remove('d-none');
    }
  }

  // Apply visibility to all tables
  document.querySelectorAll('.rp-grid-table').forEach(table => {
    _applyFilterToTable(table, activePks, allActive);
  });
}

function _applyFilterToTable(table, activePks, allActive) {
  // TH sprint columns in thead
  table.querySelectorAll('th.sprint-col[data-sprint]').forEach(th => {
    th.style.display = (allActive || activePks.has(th.dataset.sprint)) ? '' : 'none';
  });
  // TD data cells in tbody + tfoot
  table.querySelectorAll('td[data-sprint]').forEach(td => {
    td.style.display = (allActive || activePks.has(td.dataset.sprint)) ? '' : 'none';
  });
}

/* Patch setViewMode to re-apply filter after toggle */
const _baseSetViewMode = setViewMode;
setViewMode = function(mode) {
  _baseSetViewMode(mode);
  // After mode switch, re-apply column filter to newly shown/hidden columns
  if (_visibleSprints !== null) {
    const activeChips = document.querySelectorAll('.rp-col-filter-chip.active');
    const activePks   = new Set(Array.from(activeChips).map(c => c.dataset.sprintPk));
    document.querySelectorAll('.rp-grid-table').forEach(t => {
      _applyFilterToTable(t, activePks, false);
    });
  }
};