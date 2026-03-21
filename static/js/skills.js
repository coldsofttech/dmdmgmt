/* =========================================================
   Resource Planner — skills.js
   Handles: live search, sort, status filter,
            Excel import, client-side export
   ========================================================= */

'use strict';

/* ── Live search + filter ──────────────────────────────── */
const searchInput  = document.getElementById('skill-search');
const statusFilter = document.getElementById('status-filter');

if (searchInput) {
  searchInput.addEventListener('input', filterSkillTable);
}

function filterSkillTable() {
  const query  = (searchInput?.value  || '').toLowerCase().trim();
  const status = (statusFilter?.value || '').toLowerCase().trim();
  const rows   = document.querySelectorAll('#skills-table tbody tr[data-skill-id]');
  let   visible = 0;

  rows.forEach(row => {
    const code   = (row.dataset.code   || '');
    const desc   = (row.dataset.desc   || '');
    const rowSt  = (row.dataset.status || '');

    const matchQ = !query  || code.includes(query) || desc.includes(query);
    const matchS = !status || rowSt === status;
    const show   = matchQ && matchS;

    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  // Empty state row
  let emptyRow = document.getElementById('empty-filter-row');
  if (!visible) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'empty-filter-row';
      emptyRow.innerHTML = `
        <td colspan="6" class="text-center py-4 text-secondary">
          <i class="bi bi-search me-2"></i>No skills match your filters.
        </td>`;
      document.querySelector('#skills-table tbody')?.appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* ── Column sort ───────────────────────────────────────── */
let sortState = { col: -1, asc: true };

function sortSkillTable(colIndex) {
  const tbody = document.querySelector('#skills-table tbody');
  if (!tbody) return;

  sortState.asc = sortState.col === colIndex ? !sortState.asc : true;
  sortState.col = colIndex;

  document.querySelectorAll('#skills-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-skill-id]'));
  rows.sort((a, b) => {
    const aVal = (a.cells[colIndex]?.innerText || '').trim();
    const bVal = (b.cells[colIndex]?.innerText || '').trim();
    return sortState.asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  });
  rows.forEach(row => tbody.appendChild(row));
}

/* ── Excel Import ──────────────────────────────────────── */
async function importSkillsExcel(input) {
  const file = input.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const wb   = XLSX.read(e.target.result, { type: 'binary' });
      const ws   = wb.Sheets[wb.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(ws, { defval: '' });

      if (!rows.length) {
        showFlash('The uploaded file appears to be empty.', 'warning');
        return;
      }

      // Expected columns: Skill, Description, Active
      const skills = rows.map(r => ({
        skill:       String(r['Skill']       || r['skill']       || '').trim().toUpperCase(),
        description: String(r['Description'] || r['description'] || '').trim(),
        is_active:   String(r['Active']      || r['is_active']   || 'true').toLowerCase() !== 'false',
      })).filter(s => s.skill && /^[A-Z0-9]+$/.test(s.skill) && s.skill.length <= 20);

      if (!skills.length) {
        showFlash(
          'No valid rows found. Ensure the sheet has a "Skill" column with alphanumeric codes (max 20 chars).',
          'warning'
        );
        return;
      }

      let created = 0, failed = 0;
      for (const skill of skills) {
        try {
          await apiFetch('/api/v1/skills/', { method: 'POST', body: JSON.stringify(skill) });
          created++;
        } catch {
          failed++;
        }
      }

      showFlash(
        `Import complete: ${created} created${failed ? `, ${failed} skipped (duplicates or errors)` : ''}.`,
        failed ? 'warning' : 'success'
      );
      setTimeout(() => location.reload(), 1200);

    } catch (err) {
      console.error('Excel parse error:', err);
      showFlash('Could not read the Excel file. Please check the format.', 'error');
    }
  };
  reader.readAsBinaryString(file);
  input.value = '';
}

/* ── Client-side Excel export (current filtered view) ──── */
function exportCurrentViewExcel() {
  const rows = Array.from(
    document.querySelectorAll('#skills-table tbody tr[data-skill-id]')
  ).filter(r => r.style.display !== 'none');

  const data = [['Skill', 'Description', 'Status', 'Created', 'Updated']];
  rows.forEach(r => {
    data.push([
      r.cells[0]?.innerText.trim(),
      r.cells[1]?.innerText.trim(),
      r.cells[2]?.innerText.trim(),
      r.cells[3]?.innerText.trim(),
      r.cells[4]?.innerText.trim(),
    ]);
  });

  const ws = XLSX.utils.aoa_to_sheet(data);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Skills');
  XLSX.writeFile(wb, 'skills_export.xlsx');
}