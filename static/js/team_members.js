/* =========================================================
   Resource Planner — team_members.js
   Search, filter, sort, move-team modal (list page),
   delete confirmation (reuses main.js confirmDelete)
   ========================================================= */

'use strict';

/* ── Live search + multi-filter ────────────────────────── */
const searchInput   = document.getElementById('member-search');
const teamFilter    = document.getElementById('team-filter');
const roleFilter    = document.getElementById('role-filter');
const locationFilter = document.getElementById('location-filter');
const statusFilter  = document.getElementById('status-filter');

if (searchInput) searchInput.addEventListener('input', filterMemberTable);

function filterMemberTable() {
  const query    = (searchInput?.value    || '').toLowerCase().trim();
  const team     = (teamFilter?.value     || '').toLowerCase().trim();
  const role     = (roleFilter?.value     || '').toLowerCase().trim();
  const location = (locationFilter?.value || '').toLowerCase().trim();
  const status   = (statusFilter?.value   || '').toLowerCase().trim();

  const rows = document.querySelectorAll('#members-table tbody tr[data-member-id]');
  let visible = 0;

  rows.forEach(row => {
    const matchQ = !query    || (row.dataset.name     || '').includes(query);
    const matchT = !team     || (row.dataset.team     || '') === team;
    const matchR = !role     || (row.dataset.role     || '') === role;
    const matchL = !location || (row.dataset.location || '') === location;
    const matchS = !status   || (row.dataset.status   || '') === status;
    const show   = matchQ && matchT && matchR && matchL && matchS;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  let emptyRow = document.getElementById('empty-filter-row');
  if (!visible) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'empty-filter-row';
      emptyRow.innerHTML = `
        <td colspan="9" class="text-center py-4 text-secondary">
          <i class="bi bi-search me-2"></i>No members match your filters.
        </td>`;
      document.querySelector('#members-table tbody')?.appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* ── Column sort ───────────────────────────────────────── */
let sortState = { col: -1, asc: true };

function sortMemberTable(colIndex) {
  const tbody = document.querySelector('#members-table tbody');
  if (!tbody) return;

  sortState.asc = sortState.col === colIndex ? !sortState.asc : true;
  sortState.col = colIndex;

  document.querySelectorAll('#members-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-member-id]'));
  rows.sort((a, b) => {
    const aVal = (a.cells[colIndex]?.innerText || '').trim();
    const bVal = (b.cells[colIndex]?.innerText || '').trim();
    // Date-aware sort for start date column (col 6)
    if (colIndex === 6) {
      const aD = new Date(aVal), bD = new Date(bVal);
      if (!isNaN(aD) && !isNaN(bD)) {
        return sortState.asc ? aD - bD : bD - aD;
      }
    }
    return sortState.asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  });
  rows.forEach(row => tbody.appendChild(row));
}

/* ── Move team modal (list page quick-move) ────────────── */
function openMoveModal(memberId, memberName, currentTeamPk) {
  const modal     = document.getElementById('moveModal');
  const nameEl    = document.getElementById('move-member-name');
  const form      = document.getElementById('move-form');
  const dateInput = document.getElementById('move-date');
  const teamSel   = document.getElementById('move-to-team');
  const errorEl   = document.getElementById('move-error');

  if (!modal) return;

  if (nameEl)    nameEl.textContent = memberName;
  if (dateInput) dateInput.value    = new Date().toISOString().split('T')[0];
  if (errorEl)   errorEl.classList.add('d-none');

  // Set action URL
  if (form) form.action = `/members/${memberId}/move/`;

  // Pre-select current team
  if (teamSel && currentTeamPk) {
    const opt = teamSel.querySelector(`option[value="${currentTeamPk}"]`);
    if (opt) opt.selected = true;
  }

  bootstrap.Modal.getOrCreateInstance(modal).show();
}

/* ── Move form submit (list page — plain POST, no JS fetch)
   The form posts directly; Django redirects back with flash message.
   If you want an async version, replace with fetch + JSON below.    */
// Nothing extra needed — the <form method="post"> handles it natively.