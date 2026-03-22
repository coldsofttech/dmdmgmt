/* =========================================================
   Resource Planner — projects.js  (v3)
   ========================================================= */

'use strict';

/* ── List page: multi-filter ───────────────────────────── */
const searchInput      = document.getElementById('project-search');
const statusFilter     = document.getElementById('status-filter');
const substatusFilter  = document.getElementById('substatus-filter');
const typeFilter       = document.getElementById('type-filter');
const teamFilter       = document.getElementById('team-filter');
const priorityFilter   = document.getElementById('priority-filter');
const confidenceFilter = document.getElementById('confidence-filter');

if (searchInput) searchInput.addEventListener('input', filterProjectTable);

function filterProjectTable() {
  const query      = (searchInput?.value      || '').toLowerCase().trim();
  const status     = (statusFilter?.value     || '').toLowerCase().trim();
  const substatus  = (substatusFilter?.value  || '').toLowerCase().trim();
  const type       = (typeFilter?.value       || '').toLowerCase().trim();
  const team       = (teamFilter?.value       || '').toLowerCase().trim();
  const priority   = (priorityFilter?.value   || '').toLowerCase().trim();
  const confidence = (confidenceFilter?.value || '').toLowerCase().trim();

  const rows = document.querySelectorAll('#projects-table tbody tr[data-project-id]');
  let visible = 0;

  rows.forEach(row => {
    const d = row.dataset;
    const matchQ  = !query      || [d.name,d.programme,d.code,d.label].some(v=>(v||'').includes(query));
    const matchS  = !status     || (d.status     || '') === status;
    const matchSS = !substatus  || (d.substatus  || '') === substatus;
    const matchTy = !type       || (d.type       || '') === type;
    const matchT  = !team       || (d.team       || '') === team;
    const matchP  = !priority   || (d.priority   || '') === priority;
    const matchC  = !confidence || (d.confidence || '') === confidence;

    const show = matchQ && matchS && matchSS && matchTy && matchT && matchP && matchC;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  let emptyRow = document.getElementById('empty-filter-row');
  if (!visible) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'empty-filter-row';
      emptyRow.innerHTML = `<td colspan="20" class="text-center py-4 text-secondary">
        <i class="bi bi-search me-2"></i>No projects match your filters.</td>`;
      document.querySelector('#projects-table tbody')?.appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* ── List page: sort ───────────────────────────────────── */
let sortState = { col: -1, asc: true };

function sortProjectTable(colIndex) {
  const tbody = document.querySelector('#projects-table tbody');
  if (!tbody) return;
  sortState.asc = sortState.col === colIndex ? !sortState.asc : true;
  sortState.col = colIndex;

  document.querySelectorAll('#projects-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex ? (sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down') : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-project-id]'));
  rows.sort((a, b) => {
    const aVal = (a.cells[colIndex]?.innerText || '').trim();
    const bVal = (b.cells[colIndex]?.innerText || '').trim();
    return sortState.asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  });
  rows.forEach(r => tbody.appendChild(r));
}

/* ── Form: dynamic sub-status ──────────────────────────── */
function updateSubStatus(statusValue) {
  const subSelect = document.getElementById('id_sub_status');
  if (!subSelect || typeof ALL_SUB_STATUSES === 'undefined') return;
  const options = ALL_SUB_STATUSES[statusValue] || [];
  const current = subSelect.value;
  subSelect.innerHTML = '<option value="">— Select —</option>';
  options.forEach(opt => {
    const el = document.createElement('option');
    el.value = el.textContent = opt;
    if (opt === current) el.selected = true;
    subSelect.appendChild(el);
  });
}

/* ── Form: display name hint ───────────────────────────── */
function updateDisplayNameHint() {
  const prog    = (document.getElementById('id_programme_name')?.value || '').trim();
  const proj    = (document.getElementById('id_project_name')?.value   || '').trim();
  const override = (document.getElementById('id_display_name')?.value  || '').trim();
  const preview  = document.getElementById('display-name-preview');
  if (!preview) return;
  preview.textContent = (!override && (prog || proj))
    ? `Will be saved as: "${prog ? prog + ': ' : ''}${proj}"`
    : '';
}

/* ── Form: disable assigned team in collaborators ──────── */
function updateCollaboratorOptions() {
  const assignedSel = document.getElementById('id_assigned_team');
  const collabSel   = document.getElementById('id_collaborators');
  if (!assignedSel || !collabSel) return;
  const assignedPk = assignedSel.value;
  Array.from(collabSel.options).forEach(opt => {
    const isAssigned = opt.value && opt.value === assignedPk;
    opt.disabled = isAssigned;
    opt.title    = isAssigned ? 'Cannot be same as assigned team' : '';
    if (isAssigned) opt.selected = false;
  });
}

/* ── Form: auto-calculate cost ─────────────────────────── */
function recalcCost() {
  const daysEl   = document.getElementById('id_estimate_days');
  const contEl   = document.getElementById('id_contingency_pct');
  const display  = document.getElementById('cost-display');
  if (!display) return;

  const days        = parseFloat(daysEl?.value) || 0;
  const contingency = parseFloat(contEl?.value) || 0;
  const dayPrice    = (typeof DAY_PRICE !== 'undefined') ? parseFloat(DAY_PRICE) : 0;
  const total       = days * dayPrice * (1 + contingency / 100);

  display.textContent = '£' + total.toLocaleString('en-GB', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/* ── Detail: comment inline edit ───────────────────────── */
function editComment(projectPk, commentPk) {
  const card      = document.getElementById(`comment-${commentPk}`);
  const bodyEl    = card?.querySelector('.comment-body');
  const actionsEl = card?.querySelector('.comment-actions');
  if (!card || !bodyEl) return;

  const currentText = bodyEl.dataset.raw || bodyEl.innerText.trim();
  const editWrap    = document.createElement('div');
  editWrap.id       = `edit-wrap-${commentPk}`;

  const editArea    = document.createElement('textarea');
  editArea.className = 'form-control rp-input mt-2';
  editArea.rows      = 3;
  editArea.value     = currentText;

  const saveBtn   = document.createElement('button');
  saveBtn.type    = 'button';
  saveBtn.className = 'btn btn-sm btn-primary mt-2 me-2';
  saveBtn.textContent = 'Save';

  const cancelBtn   = document.createElement('button');
  cancelBtn.type    = 'button';
  cancelBtn.className = 'btn btn-sm btn-outline-secondary mt-2';
  cancelBtn.textContent = 'Cancel';

  editWrap.append(editArea, saveBtn, cancelBtn);
  bodyEl.style.display    = 'none';
  if (actionsEl) actionsEl.style.display = 'none';
  card.appendChild(editWrap);
  editArea.focus();

  cancelBtn.addEventListener('click', () => {
    editWrap.remove();
    bodyEl.style.display    = '';
    if (actionsEl) actionsEl.style.display = '';
  });

  saveBtn.addEventListener('click', async () => {
    const newBody = editArea.value.trim();
    if (!newBody) { editArea.classList.add('is-invalid'); return; }
    try {
      const res  = await fetch(`/projects/${projectPk}/comments/${commentPk}/edit/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _getCsrf() },
        body: JSON.stringify({ body: newBody }),
      });
      const data = await res.json();
      if (!data.ok) { _showFlash(data.detail || 'Save failed.', 'error'); return; }
      bodyEl.textContent = data.body;
      bodyEl.dataset.raw = data.body;
      bodyEl.style.display = '';
      if (actionsEl) actionsEl.style.display = '';
      editWrap.remove();
      let badge = card.querySelector('.comment-edited-badge');
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'comment-edited-badge text-secondary ms-2';
        badge.style.fontSize = '11px';
        card.querySelector('.comment-meta')?.appendChild(badge);
      }
      badge.textContent = `· edited ${data.updated_at}`;
    } catch { _showFlash('An unexpected error occurred.', 'error'); }
  });
}

/* ── Detail: comment delete ────────────────────────────── */
async function deleteComment(projectPk, commentPk) {
  if (!confirm('Delete this comment? This cannot be undone.')) return;
  try {
    const res  = await fetch(`/projects/${projectPk}/comments/${commentPk}/delete/`, {
      method: 'POST', headers: { 'X-CSRFToken': _getCsrf() },
    });
    const data = await res.json();
    if (data.ok) {
      document.getElementById(`comment-${commentPk}`)?.remove();
      _showFlash('Comment deleted.', 'success');
    } else { _showFlash('Delete failed.', 'error'); }
  } catch { _showFlash('An unexpected error occurred.', 'error'); }
}

/* ── Detail: code history modal ───────────────────────── */
async function showCodeHistory(event, projectPk) {
  event.preventDefault();
  const modal = bootstrap.Modal.getOrCreateInstance(
    document.getElementById('codeHistoryModal')
  );
  const body = document.getElementById('code-history-body');
  body.innerHTML = '<div class="text-center py-3 text-secondary">Loading…</div>';
  modal.show();

  try {
    const res  = await fetch(`/projects/${projectPk}/code-history/`);
    const data = await res.json();
    if (!data.ok || !data.history.length) {
      body.innerHTML = '<p class="text-secondary">No code changes recorded.</p>';
      return;
    }
    body.innerHTML = `
      <table class="table rp-table mb-0">
        <thead><tr>
          <th>Old code</th><th>New code</th>
          <th>Changed by</th><th>Changed at</th><th>Note</th>
        </tr></thead>
        <tbody>
          ${data.history.map(h => `
            <tr>
              <td><span class="rp-code">${h.old_code || '—'}</span></td>
              <td><span class="rp-code">${h.new_code || '—'}</span></td>
              <td>${h.changed_by}</td>
              <td style="white-space:nowrap">${h.changed_at}</td>
              <td class="text-secondary">${h.note || '—'}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  } catch { body.innerHTML = '<p class="text-danger">Failed to load history.</p>'; }
}

/* ── Detail: estimate history modal ───────────────────── */
async function showEstimateHistory(event, projectPk) {
  event.preventDefault();
  const modal = bootstrap.Modal.getOrCreateInstance(
    document.getElementById('estimateHistoryModal')
  );
  const body = document.getElementById('estimate-history-body');
  body.innerHTML = '<div class="text-center py-3 text-secondary">Loading…</div>';
  modal.show();

  try {
    const res  = await fetch(`/projects/${projectPk}/estimate-history/`);
    const data = await res.json();
    if (!data.ok || !data.history.length) {
      body.innerHTML = '<p class="text-secondary">No estimate changes recorded.</p>';
      return;
    }
    body.innerHTML = `
      <table class="table rp-table mb-0">
        <thead><tr>
          <th>Old days</th><th>New days</th>
          <th>Old cont%</th><th>New cont%</th>
          <th>Day price</th><th>Total cost</th>
          <th>Changed by</th><th>Changed at</th>
        </tr></thead>
        <tbody>
          ${data.history.map(h => `
            <tr>
              <td>${h.old_days}</td>
              <td>${h.new_days}</td>
              <td>${h.old_contingency}</td>
              <td>${h.new_contingency}</td>
              <td>${h.day_price}</td>
              <td><strong>${h.total_cost}</strong></td>
              <td>${h.changed_by}</td>
              <td style="white-space:nowrap">${h.changed_at}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  } catch { body.innerHTML = '<p class="text-danger">Failed to load history.</p>'; }
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

function onProjectCodeInput(input) {
  const wrap    = document.getElementById('code-note-wrap');
  if (!wrap) return;   // not on edit page (create page has no wrap)
 
  const original = (input.dataset.original || '').trim();
  const current  = (input.value || '').trim();
  const changed  = current !== original;
 
  wrap.style.display = changed ? '' : 'none';
 
  // Clear the note when the user reverts to the original code
  // so they don't accidentally submit a stale note
  if (!changed) {
    const noteEl = wrap.querySelector('textarea');
    if (noteEl) noteEl.value = '';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  updateCollaboratorOptions();
  updateDisplayNameHint();
  recalcCost();
});