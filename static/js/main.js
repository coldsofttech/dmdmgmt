/* =========================================================
   Resource Planner — main.js
   Shared utilities used across all pages
   ========================================================= */

'use strict';

/* ── CSRF token helper ─────────────────────────────────── */
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) return meta.getAttribute('content');
  const cookie = document.cookie.split(';')
    .find(c => c.trim().startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1].trim() : '';
}

/* ── Base API fetch ────────────────────────────────────── */
async function apiFetch(url, options = {}) {
  const defaults = {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
  };
  const config = {
    ...defaults,
    ...options,
    headers: { ...defaults.headers, ...(options.headers || {}) },
  };
  const res = await fetch(url, config);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw { status: res.status, data: body };
  }
  if (res.status === 204) return null;
  return res.json();
}

/* ── Flash message helper ──────────────────────────────── */
function showFlash(message, type = 'success') {
  const container = document.querySelector('.rp-messages')
    || (() => {
      const el = document.createElement('div');
      el.className = 'rp-messages px-4 pt-3';
      document.querySelector('.rp-main')?.prepend(el);
      return el;
    })();

  const alertClass = {
    success: 'alert-success',
    error:   'alert-danger',
    warning: 'alert-warning',
    info:    'alert-info',
  }[type] || 'alert-info';

  const alert = document.createElement('div');
  alert.className = `alert ${alertClass} alert-dismissible fade show`;
  alert.setAttribute('role', 'alert');
  alert.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
  `;
  container.appendChild(alert);

  // Auto-dismiss after 4s
  setTimeout(() => {
    const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
    bsAlert?.close();
  }, 4000);
}

/* ── Confirm delete (reused by teams.js and other modules) ─ */
function confirmDelete(id, name, deleteUrl, redirectUrl) {
  const modal   = document.getElementById('deleteModal');
  const nameEl  = document.getElementById('delete-team-name');
  const btn     = document.getElementById('confirm-delete-btn');

  if (!modal || !btn) return;

  nameEl.textContent = name;

  // Remove previous listener to prevent duplicates
  const newBtn = btn.cloneNode(true);
  btn.parentNode.replaceChild(newBtn, newBtn.previousSibling || btn);

  // Use passed URL or derive from current path
  const resolvedUrl  = deleteUrl || `/api/v1/teams/${id}/`;
  const resolvedRedir = redirectUrl || '/teams/';

  newBtn.addEventListener('click', async () => {
    try {
      await apiFetch(resolvedUrl, { method: 'DELETE' });
      bootstrap.Modal.getInstance(modal)?.hide();
      showFlash(`"${name}" was deleted successfully.`, 'success');
      setTimeout(() => { window.location.href = resolvedRedir; }, 800);
    } catch (err) {
      bootstrap.Modal.getInstance(modal)?.hide();
      showFlash(
        err?.data?.detail || `Failed to delete "${name}". Please try again.`,
        'error'
      );
    }
  });

  bootstrap.Modal.getOrCreateInstance(modal).show();
}

/* ── Download blob helper ──────────────────────────────── */
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}