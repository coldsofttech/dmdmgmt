/* =========================================================
   Resource Planner — teams.js
   Handles: live search, column sort, dept/status filter,
            delete confirmation, Excel import, export trigger
   ========================================================= */

'use strict';

/* ── Live search + filter ──────────────────────────────── */
const searchInput  = document.getElementById('team-search');
const deptFilter   = document.getElementById('dept-filter');
const statusFilter = document.getElementById('status-filter');

if (searchInput) {
  searchInput.addEventListener('input', filterTable);
}

function filterTable() {
  const query      = (searchInput?.value  || '').toLowerCase().trim();
  const dept       = (deptFilter?.value   || '').toLowerCase().trim();
  const status     = (statusFilter?.value || '').toLowerCase().trim();
  const rows       = document.querySelectorAll('#teams-table tbody tr[data-team-id]');
  let   visible    = 0;

  rows.forEach(row => {
    const name    = (row.dataset.name   || '').toLowerCase();
    const rowDept = (row.dataset.dept   || '').toLowerCase();
    const rowStat = (row.dataset.status || '').toLowerCase();

    const matchQ = !query  || name.includes(query) || rowDept.includes(query);
    const matchD = !dept   || rowDept === dept;
    const matchS = !status || rowStat === status;

    const show = matchQ && matchD && matchS;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  // Show empty state if all hidden
  let emptyRow = document.getElementById('empty-filter-row');
  if (!visible) {
    if (!emptyRow) {
      emptyRow = document.createElement('tr');
      emptyRow.id = 'empty-filter-row';
      emptyRow.innerHTML = `
        <td colspan="6" class="text-center py-4 text-secondary">
          <i class="bi bi-search me-2"></i>No teams match your filters.
        </td>`;
      document.querySelector('#teams-table tbody').appendChild(emptyRow);
    }
    emptyRow.style.display = '';
  } else if (emptyRow) {
    emptyRow.style.display = 'none';
  }
}

/* ── Column sort ───────────────────────────────────────── */
let sortState = { col: -1, asc: true };

function sortTable(colIndex) {
  const tbody = document.querySelector('#teams-table tbody');
  if (!tbody) return;

  // Toggle direction if same column
  if (sortState.col === colIndex) {
    sortState.asc = !sortState.asc;
  } else {
    sortState.col = colIndex;
    sortState.asc = true;
  }

  // Update header icons
  document.querySelectorAll('#teams-table thead th .rp-sort-icon').forEach((icon, i) => {
    icon.className = 'bi rp-sort-icon ' + (
      i === colIndex
        ? (sortState.asc ? 'bi-chevron-up' : 'bi-chevron-down')
        : 'bi-chevron-expand'
    );
  });

  const rows = Array.from(tbody.querySelectorAll('tr[data-team-id]'));

  rows.sort((a, b) => {
    const aCell = a.cells[colIndex];
    const bCell = b.cells[colIndex];
    if (!aCell || !bCell) return 0;

    const aVal = aCell.innerText.trim();
    const bVal = bCell.innerText.trim();

    // Numeric columns (capacity)
    const aNum = parseFloat(aVal);
    const bNum = parseFloat(bVal);
    if (!isNaN(aNum) && !isNaN(bNum)) {
      return sortState.asc ? aNum - bNum : bNum - aNum;
    }
    return sortState.asc
      ? aVal.localeCompare(bVal)
      : bVal.localeCompare(aVal);
  });

  rows.forEach(row => tbody.appendChild(row));
}

/* ── Excel Import ──────────────────────────────────────── */
async function importTeamsExcel(input) {
  const file = input.files[0];
  if (!file) return;

  // Read workbook in-browser via SheetJS (loaded in base.html)
  const reader = new FileReader();
  reader.onload = async (e) => {
    try {
      const wb    = XLSX.read(e.target.result, { type: 'binary' });
      const ws    = wb.Sheets[wb.SheetNames[0]];
      const rows  = XLSX.utils.sheet_to_json(ws, { defval: '' });

      if (!rows.length) {
        showFlash('The uploaded file appears to be empty.', 'warning');
        return;
      }

      // Map Excel columns → API payload
      // Expected columns: Name, Department, Description, Capacity, Active
      const teams = rows.map(r => ({
        name:        String(r['Name']        || r['name']        || '').trim(),
        department:  String(r['Department']  || r['department']  || '').trim(),
        description: String(r['Description'] || r['description'] || '').trim(),
        capacity:    parseInt(r['Capacity']  || r['capacity']    || 0, 10),
        is_active:   String(r['Active']      || r['is_active']   || 'true')
                       .toLowerCase() !== 'false',
      })).filter(t => t.name);

      if (!teams.length) {
        showFlash('No valid rows found. Make sure the sheet has a "Name" column.', 'warning');
        return;
      }

      // POST each team to the API
      let created = 0, failed = 0;
      for (const team of teams) {
        try {
          await apiFetch('/api/v1/teams/', { method: 'POST', body: JSON.stringify(team) });
          created++;
        } catch {
          failed++;
        }
      }

      showFlash(
        `Import complete: ${created} created${failed ? `, ${failed} failed` : ''}.`,
        failed ? 'warning' : 'success'
      );
      setTimeout(() => location.reload(), 1200);

    } catch (err) {
      console.error('Excel parse error:', err);
      showFlash('Could not read the Excel file. Please check the format.', 'error');
    }
  };
  reader.readAsBinaryString(file);

  // Reset input so same file can be re-imported
  input.value = '';
}

/* ── Export helpers ────────────────────────────────────── */
// Export links in the dropdown use server-side routes (see team_list.html).
// Optionally, a client-side Excel snapshot:
function exportCurrentViewExcel() {
  const rows    = Array.from(document.querySelectorAll('#teams-table tbody tr[data-team-id]'))
                    .filter(r => r.style.display !== 'none');

  const data = [['Name', 'Department', 'Capacity', 'Status']];
  rows.forEach(r => {
    data.push([
      r.cells[0]?.innerText.trim(),
      r.cells[1]?.innerText.trim(),
      r.cells[3]?.innerText.trim(),
      r.cells[4]?.innerText.trim(),
    ]);
  });

  const ws = XLSX.utils.aoa_to_sheet(data);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Teams');
  XLSX.writeFile(wb, 'teams_export.xlsx');
}

/* ── Delete confirmation (delegates to main.js) ─────────── */
// confirmDelete(id, name) is already defined in main.js and reused here.
// The modal HTML is embedded in team_list.html and team_form.html.
// The delete button in each row calls: confirmDelete(team.id, team.name)