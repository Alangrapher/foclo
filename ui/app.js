const REQUIRED_API_METHODS = [
  'get_subjects',
  'get_all_slots',
  'get_todos',
  'get_records',
  'get_settings'
];

function getPyApi() {
  return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
}

function hasRequiredApiMethods(api) {
  return !!api && REQUIRED_API_METHODS.every(name => typeof api[name] === 'function');
}

let pyApi = getPyApi();

// localStorage wrapper — pywebview html= mode uses about:blank origin,
// which WebKit blocks as insecure, throwing "The operation is insecure".
const safeStorage = {
  get(key, fallback = null) {
    try { const v = localStorage.getItem(key); return v !== null ? v : fallback; }
    catch(e) { return fallback; }
  },
  set(key, val) {
    try { localStorage.setItem(key, val); } catch(e) {}
  },
  remove(key) {
    try { localStorage.removeItem(key); } catch(e) {}
  }
};

const proto = document.getElementById('prototype');
const compactBtn = document.getElementById('compactBtn');
const expandBtn = document.getElementById('expandBtn');
const darkToggle = document.getElementById('darkToggle');
const closeBtn = document.getElementById('closeBtn');
const modal = document.getElementById('easterEggModal');
const trigger = document.getElementById('easterEggTrigger');
const quitModal = document.getElementById('quitConfirmModal');

let subjects = [
  {id: 1, name: 'Code Review', color: '#5E6AD2'},
  {id: 2, name: 'Writing', color: '#34C98B'},
  {id: 3, name: 'Design', color: '#F0B73F'}
];
let slots = [{index: 0, status: 'idle', subject_id: null, description: '', display_time: '00:00:00', collapsed: false}];
let todos = [];
let records = [];
let recordsFilter = 'today';
let compactIndex = 0;
let weekStart = 'sun'; // 'sun' or 'mon'
let minimizeToTray = true;
let defaultSlots = '3';
let isDark = false;
let isMoss = false;
let previousTheme = 'light';
let compactRestorePending = false;
let clickCount = 0;
let clickTimer = null;
let lastExport = 'No exports yet';
let isRefreshing = false;
let isExporting = false;
// Migration: fallback to old key name (Alangrapher → Foclo v1.0 rename)
let exportFolder = safeStorage.get('foclo.exportFolder', '') || safeStorage.get('alangrapher.exportFolder', '');
let clockIntervalId = null;

const SUBJECT_COLORS = ['#5E6AD2', '#34C98B', '#F0B73F', '#D64430', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316'];

function whenReady(fn) {
  let started = false;
  let rendered = false;

  const startIfReady = () => {
    const api = getPyApi();
    if (!hasRequiredApiMethods(api)) return false;
    pyApi = api;
    if (!started) {
      started = true;
      fn();
    }
    return true;
  };

  if (startIfReady()) return;

  let attempts = 0;
  const maxAttempts = 50; // 5 seconds before dev/offline fallback
  const checkInterval = setInterval(() => {
    attempts++;
    if (startIfReady()) {
      clearInterval(checkInterval);
    } else if (attempts === maxAttempts && !rendered && !pyApi) {
      rendered = true;
      console.error('pywebview API not available after ' + maxAttempts + ' attempts; rendering offline state while continuing to wait');
      fn();
    }
  }, 100);

  window.addEventListener('pywebviewready', () => {
    if (rendered) return;  // already rendered offline, don't double-init
    if (startIfReady()) clearInterval(checkInterval);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  restoreUiPreferences();
  initializeDynamicDates();
  bindStaticControls();
  // Load data when pywebview API is ready, then render.
  // Must happen after DOMContentLoaded so renderAll() can find DOM elements.
  whenReady(async () => {
    try {
      await loadAll();
    } catch (e) {
      console.error('Failed to load app state:', e);
    }
    startClockInterval();
  });
});

// ═══════════════════════════════════════════════════════════
// Windows frameless drag support
// macOS uses -webkit-app-region CSS (WebKit); Windows WebView2
// ignores this, so we hook mousedown and trigger native OS drag
// via the Win32 SendMessage(WM_NCLBUTTONDOWN, HTCAPTION) trick.
// ═══════════════════════════════════════════════════════════
(function setupFramelessDrag() {
  if (!navigator.platform.includes('Win')) return;

  // Elements whose mousedown should NOT trigger dragging
  const INTERACTIVE_SELECTOR = [
    'button', 'input', 'select', 'textarea', 'a',
    '.nav-item', '.btn', '.chip', '.toggle', '.toggle-slider',
    '.todo-checkbox', '.todo-start-btn', '.todo-del-btn',
    '.act', '.compact-expand', '.theme-toggle',
    '.confirm-btn', '.add-slot-btn', '.arrow',
    '[data-page]', '.slot-header span', '.header-actions',
    '.modal-card', '.modal-overlay',
    '.compact-panel', '.compact-actions'
  ].join(', ');

  document.addEventListener('mousedown', async (e) => {
    // Don't interfere with right-clicks or middle clicks
    if (e.button !== 0) return;
    // Don't start drag on interactive elements
    if (e.target.closest(INTERACTIVE_SELECTOR)) return;
    // Don't start drag on scrollbar region (rightmost 16px)
    if (e.clientX > document.documentElement.clientWidth - 16) return;

    // Prevent default to avoid text selection during drag
    e.preventDefault();

    const api = getPyApi();
    if (api && typeof api.start_window_drag === 'function') {
      try {
        await api.start_window_drag();
      } catch (_) { /* silently ignore */ }
    }
  });
})();

window.addEventListener('beforeunload', () => {
  if (clockIntervalId) clearInterval(clockIntervalId);
});

function startClockInterval() {
  if (clockIntervalId) return;
  clockIntervalId = setInterval(() => {
    refreshClocks().catch(e => console.error('Failed to refresh clocks:', e));
  }, 500);
}

async function callApi(promise, context = 'API call') {
  try {
    const result = await promise;
    if (result && result.ok === false) {
      showApiError(`${context} failed: ${result.error || 'Unknown error'}`);
      return result;
    }
    return result;
  } catch (e) {
    showApiError(`${context} failed: ${e.message || e}`);
    return {ok: false, error: e.message || String(e)};
  }
}

function showApiError(message) {
  console.error(message);
  let banner = document.getElementById('apiErrorBanner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'apiErrorBanner';
    document.body.appendChild(banner);
  }
  banner.textContent = message;
  banner.classList.add('show');
  clearTimeout(showApiError._timer);
  showApiError._timer = setTimeout(() => banner.classList.remove('show'), 5000);
}

function initializeDynamicDates() {
  const today = todayIso();
  const now = new Date();
  const dayOfWeek = now.getDay();
  const offset = weekStart === 'mon' ? (dayOfWeek === 0 ? 6 : dayOfWeek - 1) : dayOfWeek;
  const start = new Date(now);
  start.setDate(now.getDate() - offset);

  const timerSub = document.querySelector('#page-timer .page-sub');
  if (timerSub) timerSub.textContent = `Today · ${today}`;
  const recordsDate = document.getElementById('recordsDateField');
  if (recordsDate) recordsDate.value = today;
  const exportStart = document.getElementById('export-start');
  const exportEnd = document.getElementById('export-end');
  if (exportStart) exportStart.value = formatLocalDate(start);
  if (exportEnd) exportEnd.value = today;
}

function bindStaticControls() {
  document.querySelectorAll('.nav-item[data-page]').forEach(item => item.addEventListener('click', () => switchPage(item.dataset.page)));
  compactBtn.addEventListener('click', enterCompact);
  expandBtn.addEventListener('click', exitCompact);
  closeBtn.addEventListener('click', async () => {
    if (!pyApi) return;
    // minimizeToTray works on macOS (NSStatusBar) and Windows (pystray)
    const isDesktop = navigator.platform.toLowerCase().includes('mac') || navigator.platform.toLowerCase().includes('win');
    if (minimizeToTray && isDesktop) {
      await callApi(pyApi.hide_window(), 'Hide window');
    } else {
      try {
        const active = await callApi(pyApi.any_slot_active(), 'Check active timers');
        if (!active) {
          await callApi(pyApi.quit_app(), 'Quit app');
        } else {
          showQuitModal();
        }
      } catch (e) {
        await callApi(pyApi.quit_app(), 'Quit app');
      }
    }
  });
  darkToggle.addEventListener('click', toggleThemeClick);
  trigger.addEventListener('click', () => showModal(modal));
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });
  const removeSlotModal = document.getElementById('removeSlotModal');
  if (removeSlotModal) removeSlotModal.addEventListener('click', e => { if (e.target === removeSlotModal) closeRemoveSlotModal(); });
  const quickAddModal = document.getElementById('quickAddSubjectModal');
  quickAddModal.addEventListener('click', e => { if (e.target === quickAddModal) closeQuickAddSubjectModal(); });
  quitModal.addEventListener('click', e => { if (e.target === quitModal) closeQuitModal(); });
  document.getElementById('resetConfirmModal').addEventListener('click', e => { if (e.target === e.currentTarget) closeResetModal(); });
  document.getElementById('switchTimerModal').addEventListener('click', e => { if (e.target === e.currentTarget) closeSwitchTimerModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAllModals(); });
  document.querySelectorAll('#page-export .btn-secondary').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('#page-export .btn-secondary').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }));
  // Browse button for export folder
  const exportBrowseBtn = document.getElementById('export-browse-btn');
  const exportPathEl = document.getElementById('export-path');
  // Restore saved export folder display on page load
  if (exportPathEl && exportFolder) exportPathEl.textContent = exportFolder;
  let browseBusy = false; // flag-based guard, avoids pointer-events: none from :disabled
  let browseTimer = null;
  if (exportBrowseBtn) {
    exportBrowseBtn.addEventListener('click', async () => {
      if (browseBusy) return;
      if (!window.pywebview || !window.pywebview.api) {
        if (exportPathEl) exportPathEl.textContent = 'API not ready — please wait';
        return;
      }
      browseBusy = true;
      exportBrowseBtn.classList.add('btn-busy');
      // Safety timeout: reset busy state after 30s if promise hangs
      clearTimeout(browseTimer);
      browseTimer = setTimeout(() => {
        browseBusy = false;
        exportBrowseBtn.classList.remove('btn-busy');
      }, 30000);
      try {
        const result = await callApi(window.pywebview.api.choose_export_folder(exportFolder), 'Choose export folder');
        if (result && result.ok && result.path) {
          exportFolder = result.path;
          safeStorage.set('foclo.exportFolder', exportFolder);
          if (exportPathEl) exportPathEl.textContent = exportFolder;
        }
      } catch (e) { /* user cancelled */ }
      clearTimeout(browseTimer);
      exportBrowseBtn.classList.remove('btn-busy');
      browseBusy = false;
    });
  }
  const exportButton = document.querySelector('#page-export .btn-primary');
  if (exportButton) exportButton.addEventListener('click', async () => {
    if (isExporting) return;
    if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.export_timesheet !== 'function') {
      document.querySelector('#page-export .page-sub').textContent = 'Export unavailable: backend is not ready';
      return;
    }
    const start = document.getElementById('export-start').value;
    const end = document.getElementById('export-end').value;
    const fmtBtn = document.querySelector('#export-format-group .btn-secondary.active');
    const format = fmtBtn ? fmtBtn.dataset.format : 'xlsx';

    try {
      isExporting = true;
      exportButton.disabled = true;
      const result = await callApi(window.pywebview.api.export_timesheet(start, end, format, exportFolder), 'Export timesheet');
      lastExport = new Date().toLocaleString([], {hour: '2-digit', minute: '2-digit', year: 'numeric', month: 'short', day: 'numeric'});
      if (result && result.ok) {
        document.querySelector('#page-export .page-sub').textContent = 'Last export: ' + lastExport + ' → ' + result.path;
      } else {
        document.querySelector('#page-export .page-sub').textContent = 'Export failed: ' + (result?.error || 'Unknown error');
      }
    } catch (e) {
      document.querySelector('#page-export .page-sub').textContent = 'Export failed: ' + (e.message || e);
    } finally {
      isExporting = false;
      exportButton.disabled = false;
    }
  });
  document.getElementById('quitKeepBtn').addEventListener('click', quitPause);
  document.getElementById('quitArchiveBtn').addEventListener('click', quitArchive);
  bindSettingsControls();
}

async function loadAll() {
  const api = getPyApi();
  if (!hasRequiredApiMethods(api)) {
    renderAll();
    return;
  }
  pyApi = api;
  try {
    await Promise.all([loadSubjects(), loadSlots(), loadTodos(), loadRecords(), loadSettings()]);
  } catch (e) {
    console.error('Failed to load app state:', e);
  }
  initializeDynamicDates();
  renderAll();
}

async function loadSubjects() {
  const result = await callApi(pyApi.get_subjects(), 'Load subjects');
  if (Array.isArray(result)) subjects = result;
}

async function loadSlots() {
  const localState = {};
  slots.forEach(s => { localState[s.index] = { subject_id: s.subject_id, description: s.description, collapsed: s.collapsed, pendingAction: s.pendingAction }; });
  const result = await callApi(pyApi.get_all_slots(), 'Load timers');
  if (Array.isArray(result)) slots = result;
  if (!slots.length) slots = [{index: 0, status: 'idle', subject_id: null, description: '', display_time: '00:00:00', collapsed: false}];
  slots.forEach(s => {
    if (localState[s.index]) {
      if (s.subject_id === null || s.subject_id === undefined) s.subject_id = localState[s.index].subject_id;
      if (s.description === null || s.description === undefined || s.description === '') s.description = localState[s.index].description || '';
      s.collapsed = localState[s.index].collapsed || false;
      // NOT merged: pendingAction — must never be restored from stale snapshot
      // (race condition: refreshClocks snapshots pendingAction=true before
      //  _doStartSlot finally clears it, then loadSlots writes true back,
      //  permanently locking Pause/Archive buttons on Windows edgechromium)
    }
    if (s.collapsed === undefined) s.collapsed = false;
  });
  compactIndex = Math.min(compactIndex, slots.length - 1);
}

async function loadTodos() {
  const result = await callApi(pyApi.get_todos(), 'Load todos');
  if (Array.isArray(result)) todos = result;
}

async function loadRecords() {
  const result = await callApi(pyApi.get_records(recordsFilter, weekStart), 'Load records');
  if (Array.isArray(result)) records = result;
}

async function loadSettings() {
  const s = await callApi(pyApi.get_settings(), 'Load settings');
  if (!s || s.ok === false) return;
  minimizeToTray = s.minimize_to_tray === '1';
  weekStart = s.week_starts_on === 'Monday' ? 'mon' : 'sun';
  defaultSlots = s.default_slots || '3';
  // Backup state
  window._backupPath = s.backup_location || '~/Documents/Foclo/backups/';
  window._autoBackup = s.auto_backup !== '0';
}

async function refreshClocks() {
  if (isRefreshing) return;
  isRefreshing = true;
  try {
    if (window.pywebview && window.pywebview.api) {
      await loadSlots();
    } else {
      tickLocalSlots();
    }
    updateTimerCards();
    renderCompact();
  } catch (e) {
    console.error('Clock refresh failed:', e);
  } finally {
    isRefreshing = false;
  }
}

function updateTimerCards() {
  slots.forEach(slot => {
    const card = document.querySelector(`.timer-slot-card[data-slot="${slot.index}"]`);
    if (!card) return;
    const clock = card.querySelector('.timer-clock');
    if (clock) clock.textContent = slot.display_time || '00:00:00';
    const subj = subjectById(slot.subject_id);
    const subjectEl = card.querySelector('.timer-subject-line');
    if (subjectEl) subjectEl.textContent = `${subj ? subj.name : '—'}${slot.description ? ' — ' + slot.description : ''}`;
    // Update collapsed header time
    const slotSubj = card.querySelector('.slot-subject');
    if (slotSubj && slot.collapsed) slotSubj.textContent = slot.display_time || '00:00:00';
    const badge = card.querySelector('.badge');
    const status = slot.status || 'idle';
    if (badge) {
      badge.className = `badge ${status}`;
      badge.innerHTML = `<span class="dot"></span> ${status[0].toUpperCase() + status.slice(1)}`;
    }
  });
}

function renderAll() {
  renderTimer();
  renderSubjects();
  renderTodos();
  renderGallery();
  renderSettings();
  renderCompact();
  if (compactRestorePending) {
    compactRestorePending = false;
    enterCompact();
  }
}

function subjectById(id) {
  return subjects.find(s => Number(s.id) === Number(id));
}

function subjectOptions(selectedId) {
  return '<option value="">— Select subject —</option>' + subjects.map(s => `<option value="${s.id}"${Number(s.id) === Number(selectedId) ? ' selected' : ''}>${esc(s.name)}</option>`).join('');
}

async function renderTimer() {
  const page = document.getElementById('page-timer');
  const tileRow = page.querySelector('.tile-row');
  let node = page.querySelector('.page-header').nextElementSibling;
  while (node && node !== tileRow) {
    const next = node.nextElementSibling;
    if (node.classList.contains('card')) node.remove();
    node = next;
  }
  if (tileRow) {
    slots.forEach(slot => page.insertBefore(timerCard(slot), tileRow));
  }
  renderTodayRecords();
  await updateTiles();
}

function timerCard(slot) {
  const index = slot.index;
  const subj = subjectById(slot.subject_id);
  const status = slot.status || 'idle';
  const label = status[0].toUpperCase() + status.slice(1);
  const isPending = !!slot.pendingAction;
  const hasRunningOther = slots.some(s => s.index !== index && s.status === 'running');
  const isSwitch = status !== 'running' && hasRunningOther;
  const subjectDisabled = status !== 'idle';
  const descDisabled = status === 'running';  // only lock description while actively running
  const actionText = status === 'running' ? 'Pause' : status === 'paused' ? (isSwitch ? 'Switch' : 'Resume') : (isSwitch ? 'Switch' : 'Start');
  const iconPath = status === 'running'
    ? '<rect x="14" y="3" width="5" height="18" rx="1"/><rect x="5" y="3" width="5" height="18" rx="1"/>'
    : '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/>';
  const card = document.createElement('div');
  card.className = 'card timer-slot-card';
  card.dataset.slot = index;
  card.innerHTML = `
    <div class="slot-header">
      <span class="slot-label">Timer ${index + 1}</span>
      <span class="badge ${status}"><span class="dot"></span> ${label}</span>
      <span class="slot-subject">${slot.collapsed ? esc(slot.display_time || '00:00:00') : (subj ? esc(subj.name) : '—')}</span>
      <span class="slot-collapse" onclick="toggleCollapse(this)" style="color:var(--muted);cursor:pointer;font-size:13px;"><svg style="width:14px;height:14px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${slot.collapsed ? '<path d="m6 9 6 6 6-6"/>' : '<path d="m18 15-6-6-6 6"/>'}</svg></span>
      ${slots.length > 1 ? `<span onclick="confirmRemoveSlot(${index})" style="color:var(--muted);cursor:pointer;font-size:11px;"><svg style="width:12px;height:12px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></span>` : ''}
      ${slots.length < 5 ? `<button class="add-slot-btn" title="Add timer slot (max 5)" onclick="addSlot()"><svg style="width:16px;height:16px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg></button>` : ''}
    </div>
    <div class="timer-clock"${slot.collapsed ? ' style="display:none"' : ''}>${slot.display_time || '00:00:00'}</div>
    <div class="timer-subject-line"${slot.collapsed ? ' style="display:none"' : ''}>${subj ? esc(subj.name) : '—'}${slot.description ? ' — ' + esc(slot.description) : ''}</div>
    <div class="form-row"${slot.collapsed ? ' style="display:none"' : ''}>
      <div class="form-label">Subject</div>
      <div class="select-wrapper"><select class="form-select" onchange="setSlotSubject(${index}, this.value)"${subjectDisabled ? ' disabled' : ''}>${subjectOptions(slot.subject_id)}</select></div>
    </div>
    <div class="form-row"${slot.collapsed ? ' style="display:none"' : ''}>
      <div class="form-label">Description (optional)</div>
      <input class="form-input" placeholder="What are you working on?" value="${attr(slot.description || '')}" oninput="setSlotDescription(${index}, this.value)"${descDisabled ? ' disabled' : ''}>
    </div>
    <div class="btn-row"${slot.collapsed ? ' style="display:none"' : ''}>
      <button class="btn btn-primary${isSwitch ? ' btn-switch' : ''}" style="flex:1;" onclick="primaryTimerAction(${index})"${isPending ? ' disabled' : ''}><svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${iconPath}</svg>${isPending ? 'Working...' : actionText}</button>
      <button class="btn btn-secondary" style="flex:1;" onclick="archiveSlot(${index})"${isPending ? ' disabled' : ''}><svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 15h18"/><path d="m15 8-3 3-3-3"/></svg>Archive</button>
    </div>`;
  return card;
}

async function primaryTimerAction(index) {
  const slot = slots[index];
  if (slot.status === 'running') await pauseSlot(index);
  else await startSlot(index);
}

async function startSlot(index, values = null) {
  if (!slots[index] || slots[index].pendingAction) return;
  const hasRunningOther = slots.some(s => s.index !== index && s.status === 'running');
  if (hasRunningOther && !values) {
    const runningSlot = slots.find(s => s.status === 'running');
    const subj = subjectById(runningSlot.subject_id);
    document.getElementById('switchTimerMsg').textContent =
      '"' + (subj ? subj.name : 'Timer ' + (runningSlot.index + 1)) + '" is running. Switch to this timer?';
    document.getElementById('switchTimerConfirmBtn').onclick = async () => {
      closeSwitchTimerModal();
      await _doStartSlot(index, null);
    };
    showModal(document.getElementById('switchTimerModal'));
    return;
  }
  await _doStartSlot(index, values);
}

async function _doStartSlot(index, values) {
  if (!slots[index]) return;
  slots[index].pendingAction = true;
  // In-place button update — don't destroy/recreate DOM (breaks clock refresh)
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  if (card) {
    const btn = card.querySelector('.btn-primary');
    if (btn) { btn.disabled = true; btn.childNodes.forEach(c => { if (c.nodeType === 3) c.textContent = 'Working...'; }); }
  }
  const sid = values && Object.prototype.hasOwnProperty.call(values, 'subject_id')
    ? values.subject_id
    : (card ? Number(card.querySelector('.form-select').value) || null : slots[index].subject_id);
  const desc = values && Object.prototype.hasOwnProperty.call(values, 'description')
    ? values.description
    : (card ? card.querySelector('.form-input').value : slots[index].description);
  try {
    if (window.pywebview && window.pywebview.api) {
      const descResult = await callApi(window.pywebview.api.set_description(index, desc || ''), 'Update timer description');
      if (!descResult || descResult.ok === false) return;
      const result = await callApi(window.pywebview.api.start_slot(index, sid), 'Start timer');
      if (!result || result.ok === false) return;
      await loadSlots();
    } else {
      slots.forEach(s => { if (s.status === 'running') pauseLocal(s); });
      Object.assign(slots[index], {status: 'running', subject_id: sid, description: desc || '', startedAt: Date.now()});
    }
  } finally {
    if (slots[index]) slots[index].pendingAction = false;
    startClockInterval();
    renderTimer(); renderCompact();
  }
}

async function pauseSlot(index) {
  if (!slots[index] || slots[index].pendingAction) return;
  slots[index].pendingAction = true;
  // In-place button update — don't destroy/recreate DOM
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  if (card) {
    const btn = card.querySelector('.btn-primary');
    if (btn) { btn.disabled = true; btn.childNodes.forEach(c => { if (c.nodeType === 3) c.textContent = 'Working...'; }); }
  }
  try {
    if (window.pywebview && window.pywebview.api) {
      const result = await callApi(window.pywebview.api.pause_slot(index), 'Pause timer');
      if (!result || result.ok === false) return;
      await loadSlots();
    } else pauseLocal(slots[index]);
  } finally {
    if (slots[index]) slots[index].pendingAction = false;
    startClockInterval();
    renderTimer(); renderCompact();
  }
}

async function archiveSlot(index) {
  if (!slots[index] || slots[index].pendingAction) return;
  slots[index].pendingAction = true;
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  const sid = card ? (Number(card.querySelector('.form-select')?.value) || null) : slots[index].subject_id;
  const desc = card ? card.querySelector('.form-input').value : slots[index].description;
  try {
    if (window.pywebview && window.pywebview.api) {
      const result = await callApi(window.pywebview.api.archive_slot(index, sid, desc || ''), 'Archive timer');
      if (!result || result.ok === false) return;
      // Clear local state so loadSlots merge doesn't restore old subject/description
      slots[index].subject_id = null;
      slots[index].description = '';
      await Promise.all([loadSlots(), loadRecords()]);
    } else {
      const slot = slots[index];
      records.unshift({id: Date.now(), subject_id: sid, subject_name: subjectById(sid)?.name || '—', description: desc || '—', start: '', end: '', duration: slot.display_time, date: todayIso()});
      Object.assign(slot, {status: 'idle', subject_id: null, description: '', display_time: '00:00:00', elapsed: 0, startedAt: null});
    }
  } finally {
    if (slots[index]) slots[index].pendingAction = false;
    renderAll();
  }
}

async function addSlot() {
  if (slots.length >= 5) return;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.add_slot(), 'Add timer slot');
    if (!result || result.ok === false) return;
    await loadSlots();
  }
  else slots.push({index: slots.length, status: 'idle', subject_id: null, description: '', display_time: '00:00:00', collapsed: false});
  renderTimer(); renderCompact();
}

async function removeSlot(index) {
  if (slots.length <= 1) return;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.remove_slot(index), 'Remove timer slot');
    if (!result || result.ok === false) return;
    await loadSlots();
  }
  else { slots.splice(index, 1); slots.forEach((s, i) => s.index = i); }
  compactIndex = Math.min(compactIndex, slots.length - 1);
  renderTimer(); renderCompact();
}

let pendingRemoveSlot = null;

function confirmRemoveSlot(index) {
  const slot = slots[index];
  if (!slot || (slot.status !== 'running' && slot.status !== 'paused')) {
    removeSlot(index);
    return;
  }
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  const subj = subjectById(slot.subject_id);
  const name = subj ? subj.name : 'this timer';
  const modal = document.getElementById('removeSlotModal');
  modal.querySelector('.remove-slot-msg').textContent = `Timer is ${slot.status}. Close "${name}"?`;
  showModal(modal);
  pendingRemoveSlot = index;
}

function closeRemoveSlotModal() {
  document.getElementById('removeSlotModal').classList.remove('show');
  pendingRemoveSlot = null;
}

async function archiveThenRemove() {
  const index = pendingRemoveSlot;
  if (index === null || index === undefined) return;
  await archiveSlot(index);
  await removeSlot(index);
  closeRemoveSlotModal();
}

async function clearAndRemove() {
  const index = pendingRemoveSlot;
  if (index === null || index === undefined) return;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.clear_slot(index), 'Clear timer slot');
    if (!result || result.ok === false) return;
  } else if (slots[index]) {
    Object.assign(slots[index], {status: 'idle', subject_id: null, description: '', display_time: '00:00:00', elapsed: 0, startedAt: null});
  }
  await removeSlot(index);
  closeRemoveSlotModal();
}

function setSlotSubject(index, value) {
  slots[index].subject_id = Number(value) || null;
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  if (card) {
    const subj = subjectById(slots[index].subject_id);
    const el = card.querySelector('.timer-subject-line');
    if (el) el.textContent = `${subj ? subj.name : '—'}${slots[index].description ? ' — ' + slots[index].description : ''}`;
  }
  renderCompact();
}

async function setSlotDescription(index, value) {
  slots[index].description = value;
  if (window.pywebview && window.pywebview.api) await callApi(window.pywebview.api.set_description(index, value), 'Update timer description');
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  if (card) {
    const subj = subjectById(slots[index].subject_id);
    const el = card.querySelector('.timer-subject-line');
    if (el) el.textContent = `${subj ? subj.name : '—'}${slots[index].description ? ' — ' + slots[index].description : ''}`;
  }
  renderCompact();
}

function toggleCollapse(el) {
  const card = el.closest('.card');
  const index = Number(card.dataset.slot);
  const clock = card.querySelector('.timer-clock');
  const isHidden = clock.style.display === 'none';
  slots[index].collapsed = !isHidden;
  card.querySelectorAll('.timer-clock,.timer-subject-line,.form-row,.btn-row').forEach(x => x.style.display = isHidden ? '' : 'none');
  // Update header text: collapsed shows time, expanded shows subject
  const slotSubj = card.querySelector('.slot-subject');
  if (slotSubj) {
    const subj = subjectById(slots[index].subject_id);
    slotSubj.textContent = !isHidden ? (slots[index].display_time || '00:00:00') : (subj ? subj.name : '—');
  }
  el.querySelector('svg').innerHTML = isHidden ? '<path d="m18 15-6-6-6 6"/>' : '<path d="m6 9 6 6 6-6"/>';
}

function renderTodayRecords() {
  const tbody = document.querySelector('#page-timer .records-table tbody');
  if (!tbody) return;
  const render = (todayRecords) => {
    tbody.innerHTML = todayRecords.length ? todayRecords.map(r => `<tr ondblclick="fillRecordToSlot(${r.id})" title="Double-click to load into timer" data-id="${r.id}" data-subject="${attr(r.subject_name || '—')}" data-desc="${attr(r.description || '—')}" data-dur="${attr(r.duration || '0m')}"><td class="cell-subj">${esc(r.subject_name || '—')}</td><td class="cell-desc cell-desc-wrap">${esc(r.description || '—')}</td><td class="cell-dur" style="text-align:right">${esc(r.duration || '0m')}</td><td><span class="records-actions"><span class="act" onclick="editRecord(this)" title="Edit">✎</span><span class="act del" onclick="delRecord(this)" title="Delete">🗑</span></span></td></tr>`).join('') : '<tr><td colspan="4" style="text-align:center;color:var(--muted)">No records yet</td></tr>';
  };
  if (window.pywebview && window.pywebview.api) {
    callApi(window.pywebview.api.get_records('today'), 'Load today records').then(result => {
      render(Array.isArray(result) ? result : []);
    }).catch(e => console.error('Failed to load today records:', e));
  } else {
    const todayRecords = records.filter(r => (r.date || '') === todayIso());
    render(todayRecords);
  }
}

async function fillRecordToSlot(id) {
  const record = records.find(r => Number(r.id) === Number(id));
  if (!record) return;
  // Only today's records can be loaded into timer
  if (record.date !== todayIso()) return;
  let slot = slots.find(s => s.status === 'idle');
  if (!slot) {
    await addSlot();
    slot = slots.find(s => s.status === 'idle') || slots[slots.length - 1];
  }
  const subj = subjects.find(s => s.name === record.subject_name);
  // Also try matching by subject_id for records loaded from API
  const subjById = !subj ? subjects.find(s => Number(s.id) === Number(record.subject_id)) : null;
  const bestSubj = subj || subjById;
  slot.subject_id = bestSubj ? bestSubj.id : null;
  slot.description = record.description || '';
  if (window.pywebview && window.pywebview.api) {
    await callApi(window.pywebview.api.set_description(slot.index, slot.description), 'Update timer description');
    await callApi(window.pywebview.api.set_resume_record(slot.index, record.id), 'Set resume record');
  }
  switchPage('timer');
  renderTimer();
}

async function updateTiles() {
  const now = new Date();
  const todayStr = todayIso();
  const dayOfWeek = now.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
  const offset = weekStart === 'mon' ? (dayOfWeek === 0 ? 6 : dayOfWeek - 1) : dayOfWeek;
  const weekStartDate = new Date(now); weekStartDate.setDate(now.getDate() - offset);
  const weekStartStr = formatLocalDate(weekStartDate);

  let todayH = 0, weekH = 0;
  let tileRecords = records;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.get_records('all'), 'Load records');
    if (Array.isArray(result)) tileRecords = result;
  }
  tileRecords.forEach(r => {
    const h = parseDurationS(r.duration || '0') / 3600;
    const d = r.date || '';
    if (d === todayStr) todayH += h;
    if (d >= weekStartStr && d <= todayStr) weekH += h;
  });

  const vals = document.querySelectorAll('#page-timer .tile-value');
  if (vals[0]) vals[0].textContent = todayH.toFixed(1) + 'h';
  if (vals[1]) vals[1].textContent = weekH.toFixed(1) + 'h';
}

let _lastCompactKey = '';

function renderCompact() {
  const slot = slots[compactIndex] || slots[0];
  if (!slot) return;
  const panel = document.getElementById('compactPanel');
  if (!panel) return;
  const subj = subjectById(slot.subject_id);
  const status = slot.status || 'idle';
  const compactTop = panel.querySelector('.compact-top');
  if (compactTop) compactTop.innerHTML = `<span class="badge ${status}"><span class="dot"></span> ${status[0].toUpperCase() + status.slice(1)}</span>`;
  const indicator = panel.querySelector('.compact-slot-indicator');
  if (indicator) indicator.textContent = `${compactIndex + 1} / ${slots.length}`;
  const clockEl = panel.querySelector('.compact-clock');
  if (clockEl) clockEl.textContent = slot.display_time || '00:00:00';
  const subjText = subj ? subj.name : '—';
  const desc = slot.description ? ' — ' + slot.description : '';
  const subjectEl = panel.querySelector('.compact-subject');
  if (subjectEl) { subjectEl.textContent = subjText + desc; subjectEl.style.display = ''; }
  const arrows = panel.querySelectorAll('.arrow');
  if (arrows.length >= 2) {
    arrows[0].style.visibility = slots.length > 1 ? 'visible' : 'hidden';
    arrows[1].style.visibility = slots.length > 1 ? 'visible' : 'hidden';
    arrows[0].onclick = () => {
      compactIndex = (compactIndex - 1 + slots.length) % slots.length;
      renderCompact();
    };
    arrows[1].onclick = () => {
      compactIndex = (compactIndex + 1) % slots.length;
      renderCompact();
    };
  }
  const hasRunningOther = slots.some(s => s.index !== slot.index && s.status === 'running');
  const isSwitch = status !== 'running' && hasRunningOther;
  const action = status === 'running' ? 'Pause' : status === 'paused' ? (isSwitch ? 'Switch' : 'Resume') : (isSwitch ? 'Switch' : 'Start');
  const key = `${compactIndex}-${status}-${isSwitch}-${!!slot.pendingAction}`;
  if (key !== _lastCompactKey) {
    _lastCompactKey = key;
    const icon = status === 'running' ? '<rect x="14" y="3" width="5" height="18" rx="1"/><rect x="5" y="3" width="5" height="18" rx="1"/>' : '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/>';
    panel.querySelector('.compact-actions').innerHTML = `<button class="btn btn-primary${isSwitch ? ' btn-switch' : ''}" style="width:145px" onclick="primaryTimerAction(${slot.index})"${slot.pendingAction ? ' disabled' : ''}><svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icon}</svg>${slot.pendingAction ? 'Working...' : action}</button><button class="btn btn-secondary" style="width:145px" onclick="archiveSlot(${slot.index})"${slot.pendingAction ? ' disabled' : ''}><svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 15h18"/><path d="m15 8-3 3-3-3"/></svg>Archive</button>`;
  }
}

function enterCompact() {
  safeStorage.set('foclo.compact', '1');
  document.documentElement.classList.add('showing-compact');
  proto.classList.add('showing-compact');
  document.querySelector('.sidebar').style.display = 'none';
  document.querySelector('.content').style.display = 'none';
  const cp = document.getElementById('compactPanel');
  cp.style.display = 'flex';
  const runningIdx = slots.findIndex(s => s.status === 'running');
  compactIndex = runningIdx >= 0 ? runningIdx : 0;
  renderCompact();
  if (pyApi && pyApi.resize_window) callApi(pyApi.resize_window(380, 230), 'Resize window');
}

function exitCompact() {
  safeStorage.set('foclo.compact', '0');
  document.documentElement.classList.remove('showing-compact');
  proto.classList.remove('showing-compact');
  document.querySelector('.sidebar').style.display = '';
  document.querySelector('.content').style.display = '';
  const cp = document.getElementById('compactPanel');
  cp.style.display = '';
  cp.style.position = '';
  cp.style.top = '';
  cp.style.left = '';
  cp.style.transform = '';
  if (pyApi && pyApi.resize_window) callApi(pyApi.resize_window(760, 620), 'Resize window');
}

function switchPage(name) {
  document.querySelectorAll('.nav-item[data-page]').forEach(n => n.classList.toggle('active', n.dataset.page === name));
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + name));
}

function toggleThemeClick() {
  clickCount++;
  if (clickCount === 1) clickTimer = setTimeout(() => { clickCount = 0; }, 2000);
  if (clickCount >= 8) {
    clearTimeout(clickTimer);
    clickCount = 0;
    if (isMoss) applyTheme(previousTheme);
    else {
      previousTheme = isDark ? 'dark' : 'light';
      applyTheme('moss');
    }
    return;
  }
  if (isMoss) {
    if (clickCount >= 5) {
      clearTimeout(clickTimer);
      clickCount = 0;
      applyTheme(previousTheme);
    }
    return;
  }
  applyTheme(isDark ? 'light' : 'dark');
}

function restoreUiPreferences() {
  // Migration: fallback to old key names (Alangrapher → Foclo v1.0 rename)
  const storedTheme = safeStorage.get('foclo.theme', '') || safeStorage.get('alangrapher.theme', 'light');
  previousTheme = safeStorage.get('foclo.previousTheme', '') || safeStorage.get('alangrapher.previousTheme', 'light');
  applyTheme(storedTheme, false);
  compactRestorePending = safeStorage.get('foclo.compact') === '1' || safeStorage.get('alangrapher.compact') === '1';
}

function applyTheme(theme, persist = true) {
  if (theme !== 'dark' && theme !== 'moss') theme = 'light';
  isMoss = theme === 'moss';
  isDark = theme === 'dark';
  if (!isMoss) previousTheme = theme;
  document.documentElement.classList.toggle('moss', isMoss);
  document.documentElement.classList.toggle('dark', isDark);
  document.querySelector('.sidebar-brand').textContent = isMoss ? 'MOSS_SYS :: ONLINE' : 'Foclo';
  darkToggle.style.color = isMoss ? '#cc2200' : '';
  darkToggle.style.borderColor = isMoss ? '#cc2200' : '';
  updateDarkButton();
  if (persist) {
    safeStorage.set('foclo.theme', theme);
    safeStorage.set('foclo.previousTheme', previousTheme);
  }
}

function updateDarkButton() {
  if (isMoss) {
    darkToggle.innerHTML = '<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="#cc2200" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.341 6.484A10 10 0 0 1 10.266 21.85"/><path d="M3.659 17.516A10 10 0 0 1 13.74 2.152"/><circle cx="12" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/></svg> Enable';
    return;
  }
  darkToggle.innerHTML = isDark
    ? '<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg> Light'
    : '<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 5h4"/><path d="M20 3v4"/><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/></svg> Dark';
}

async function addTodo() {
  const subjSelect = document.getElementById('todoSubject');
  const descInput = document.getElementById('todoDesc');
  const v = Number(subjSelect.value);
  const subjectId = isNaN(v) ? null : v;
  const subj = subjectById(subjectId);
  if (!subj) return;
  const subject = subj.name;
  const description = descInput.value.trim();
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.add_todo(subject, description, subjectId), 'Add todo');
    if (!result || result.ok === false) return;
    await loadTodos();
  }
  else todos.push({id: Date.now(), subject_id: subjectId, subject, description, status: 'pending'});
  subjSelect.value = ''; descInput.value = ''; renderTodos();
}

async function toggleTodo(arg) {
  const id = typeof arg === 'number' ? arg : Number(arg.closest('.todo-item').dataset.id);
  if (!id || isNaN(id)) return;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.toggle_todo(id), 'Update todo');
    if (!result || result.ok === false) return;
    await loadTodos();
  }
  else { const t = todos.find(x => x.id === id); if (t) t.status = t.status === 'done' ? 'pending' : 'done'; }
  renderTodos();
}

async function delTodo(arg) {
  const id = typeof arg === 'number' ? arg : Number(arg.closest('.todo-item')?.dataset?.id);
  if (!id || isNaN(id)) return;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.delete_todo(id), 'Delete todo');
    if (!result || result.ok === false) return;
    await loadTodos();
  }
  else todos = todos.filter(t => Number(t.id) !== id);
  renderTodos();
}

async function startTodoTimer(arg) {
  const id = typeof arg === 'number' ? arg : Number(arg.closest('.todo-item')?.dataset?.id);
  if (!id || isNaN(id)) return;
  const todo = todos.find(t => Number(t.id) === Number(id));
  if (!todo || todo.status === 'done') return;
  let slot = slots.find(s => s.status === 'idle');
  if (!slot) {
    await addSlot();
    slot = slots.find(s => s.status === 'idle') || slots[slots.length - 1];
  }
  let subj = subjectById(todo.subject_id);
  if (!subj) subj = subjects.find(s => s.name === todo.subject);
  if (!subj) { subj = {id: null, name: todo.subject, color: '#5E6AD2'}; }
  slot.subject_id = subj.id;
  slot.description = todo.description || '';
  switchPage('timer');
  await startSlot(slot.index, {subject_id: subj.id, description: todo.description || ''});
}

function renderTodos() {
  const list = document.querySelector('#page-todo .todo-list');
  list.innerHTML = todos.length ? todos.map(t => `<div class="todo-item${t.status === 'done' ? ' done' : ''}" data-id="${t.id}"><div class="todo-checkbox" onclick="toggleTodo(${t.id})"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><g class="todo-checkmark"><path d="M17 9 11 15 7 11"/></g></svg></div><div class="todo-item-info"><div class="todo-item-subject">${esc(t.subject)}</div>${t.description ? `<div class="todo-item-desc">${esc(t.description)}</div>` : ''}</div><span class="todo-del-btn" onclick="delTodo(${t.id})" title="Delete"><svg style="width:12px;height:12px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></span><span class="todo-start-btn" onclick="startTodoTimer(${t.id})" title="Start timer"><svg style="width:14px;height:14px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/></svg></span></div>`).join('') : '<div class="empty-state">No todos</div>';
  updateTodoCounter();
}

function updateTodoCounter() {
  const done = todos.filter(t => t.status === 'done').length;
  document.querySelector('#page-todo .page-sub').textContent = `${todos.length - done} pending · ${done} done`;
}

async function setRecordsFilter(filter) {
  recordsFilter = filter === 'Today' ? 'today' : filter === 'Week' ? 'week' : filter === 'Month' ? 'month' : 'all';
  document.querySelectorAll('#page-records .chip').forEach(c => c.classList.remove('active'));
  const labels = {Today: 'Today', Week: 'This Week', Month: 'This Month', All: 'All'};
  document.querySelectorAll('#page-records .chip').forEach(c => { if (c.textContent.trim() === labels[filter]) c.classList.add('active'); });
  const dateField = document.getElementById('recordsDateField');
  if (dateField) { dateField.style.display = recordsFilter === 'today' ? 'none' : ''; dateField.value = todayIso(); }
  if (window.pywebview && window.pywebview.api) await loadRecords();
  renderGallery(); renderTodayRecords(); updateTiles();
}

function renderGallery() {
  const gallery = document.getElementById('galleryView');
  // Group records by date
  const byDate = {};
  records.forEach(r => {
    const d = r.date || '';
    if (!byDate[d]) byDate[d] = [];
    byDate[d].push(r);
  });
  const dates = Object.keys(byDate).sort().reverse(); // newest first
  
  if (dates.length === 0) {
    gallery.innerHTML = '<div class="empty-state">No records yet</div>';
    document.getElementById('recordsCount').textContent = '0';
    return;
  }
  
  document.getElementById('recordsCount').textContent = records.length;
  
  gallery.innerHTML = dates.map(date => {
    const dayRecords = byDate[date];
    // Calculate total duration and per-subject durations
    const subjectTotals = {}; // {subject_name: {total_s, color}}
    let dayTotalS = 0;
    dayRecords.forEach(r => {
      const dur = (r.duration_s || 0);
      dayTotalS += dur;
      const sn = r.subject_name || '—';
      if (!subjectTotals[sn]) {
        subjectTotals[sn] = { total_s: 0, color: '' };
      }
      subjectTotals[sn].total_s += dur;
      // Look up color from subjects array
      const subj = subjectById(r.subject_id);
      if (subj) subjectTotals[sn].color = subj.color || '#5E6AD2';
    });
    
    return renderDayCard(date, dayRecords, dayTotalS, subjectTotals);
  }).join('');
}

function renderDayCard(date, dayRecords, dayTotalS, subjectTotals) {
  const dayH = (dayTotalS / 3600).toFixed(1);
  const dateObj = new Date(date + 'T00:00:00');
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const dayName = days[dateObj.getDay()];
  
  // Build subject color bar
  const subjectNames = Object.keys(subjectTotals);
  const barSegments = subjectNames.map(sn => {
    const st = subjectTotals[sn];
    const pct = dayTotalS > 0 ? (st.total_s / dayTotalS * 100) : 0;
    return `<span class="sb-seg" style="width:${pct.toFixed(1)}%;background:${st.color}" title="${esc(sn)}: ${(st.total_s/3600).toFixed(1)}h"></span>`;
  }).join('');
  
  // Build record rows
  const recordRows = dayRecords.map(r => {
    const start = r.start || '—';
    const end = r.end || '—';
    const dur = r.duration || '0h';
    const subjName = r.subject_name || '—';
    const desc = r.description || '—';
    const subj = subjectById(r.subject_id);
    const dotColor = subj ? subj.color : '#5E6AD2';
    return `<div class="grec-row" data-id="${r.id}" data-date="${attr(date)}" data-subject="${attr(subjName)}" data-desc="${attr(desc)}" data-dur="${attr(dur)}"${r.date === todayIso() ? ` ondblclick="fillRecordToSlot(${r.id})" title="Double-click to load into timer"` : ''}>
      <div class="grec-line1">
        <span class="grec-dot" style="background:${dotColor}"></span>
        <span class="grec-subj">${esc(subjName)}</span>
        <span class="grec-dur">${esc(dur)}</span>
        <span class="records-actions"><span class="act" onclick="editRecord(this)" title="Edit">✎</span><span class="act del" onclick="delRecord(this)" title="Delete">🗑</span></span>
      </div>
      <div class="grec-line2">
        <span class="grec-time">${start}–${end}</span>
        <span class="grec-desc">${esc(desc)}</span>
      </div>
    </div>`;
  }).join('');
  
  // Build Gantt strip
  const ganttStrip = renderGanttStrip(dayRecords, date);
  
  return `<div class="gallery-card">
    <div class="gcard-header">
      <span class="gcard-date">${date}</span>
      <span class="gcard-day">${dayName}</span>
      <span class="gcard-total">${dayH}h</span>
    </div>
    <div class="gcard-bar">
      <div class="gcard-bar-inner">${barSegments}</div>
      <div class="gcard-legend">
        ${subjectNames.map(sn => `<span class="glegend-item"><span class="glegend-dot" style="background:${subjectTotals[sn].color}"></span>${esc(sn)} ${(subjectTotals[sn].total_s/3600).toFixed(1)}h</span>`).join('')}
      </div>
    </div>
    ${ganttStrip}
    <div class="gcard-records">${recordRows}</div>
  </div>`;
}

function renderGanttStrip(dayRecords, date) {
  // Parse records with valid start_iso for positioning
  const positioned = dayRecords.map(r => {
    const iso = r.start_iso || '';
    if (!iso || !iso.includes('T')) return null;
    const timePart = iso.split('T')[1];
    const [h, m, s] = timePart.split(':').map(Number);
    const secFromMidnight = h * 3600 + m * 60 + (s || 0);
    const dur = r.duration_s || 0;
    const subj = subjectById(r.subject_id);
    return { ...r, secFromMidnight, dur, color: subj ? subj.color : '#5E6AD2' };
  }).filter(Boolean).sort((a, b) => a.secFromMidnight - b.secFromMidnight);
  
  if (positioned.length === 0) return '';
  
  // Overlap assignment: greedy row allocation (dynamic, no cap)
  const rows = []; // rows[i] = [{endSec, ...}, ...]
  
  positioned.forEach(rec => {
    const endSec = rec.secFromMidnight + rec.dur;
    let placed = false;
    for (let rowIdx = 0; rowIdx < rows.length; rowIdx++) {
      const last = rows[rowIdx][rows[rowIdx].length - 1];
      if (!last || last.endSec <= rec.secFromMidnight) {
        rows[rowIdx].push({ ...rec, endSec, rowIdx });
        placed = true;
        break;
      }
    }
    if (!placed) {
      // All existing rows occupied — add a new row
      const newRowIdx = rows.length;
      rows.push([{ ...rec, endSec, rowIdx: newRowIdx }]);
    }
  });
  
  const numRows = rows.length;
  const rowH = 13;
  const barH = 10;
  
  // Build hour markers
  const hourMarkers = [0, 6, 12, 18, 24].map(h => 
    `<span class="gantt-hour" style="left:${(h/24*100).toFixed(1)}%">${h}h</span>`
  ).join('');
  
  // Build bars
  const totalSec = 86400;
  const allBars = [];
  for (let ri = 0; ri < numRows; ri++) {
    rows[ri].forEach(rec => {
      const left = Math.max((rec.secFromMidnight / totalSec * 100), 0);
      const width = Math.max((rec.dur / totalSec * 100), 0.5);
      const desc = rec.description ? esc(rec.description) : '';
      const tooltip = desc
        ? `${esc(rec.subject_name)}: ${desc} (${rec.start}–${rec.end}, ${rec.duration})`
        : `${esc(rec.subject_name)} ${rec.start}–${rec.end} (${rec.duration})`;
      allBars.push(`<div class="gantt-bar" style="left:${left.toFixed(2)}%;width:${width.toFixed(2)}%;top:${ri*rowH}px;background:${rec.color}" title="${tooltip}"></div>`);
    });
  }
  
  const hasRecords = allBars.length > 0;
  const stripH = numRows * rowH + (rowH - barH);
  return `<div class="gcard-gantt">
    <div class="gantt-ticks">${hourMarkers}</div>
    <div class="gantt-strip" style="height:${stripH}px">
      ${hasRecords ? allBars.join('') : '<span class="gantt-empty">No timed records</span>'}
    </div>
  </div>`;
}

async function addRecord() {
  const row = document.getElementById('recordsAddRow');
  const subjName = row.querySelector('.records-add-subject').value;
  const subj = subjects.find(s => s.name === subjName) || subjects[0];
  const desc = row.querySelector('.records-add-desc').value.trim() || '—';
  const startTime = row.querySelector('.records-add-start').value;
  const endTime = row.querySelector('.records-add-end').value;
  const date = document.getElementById('recordsDateField').value || todayIso();
  if (!startTime || !endTime) {
    alert('Please enter both start and end time.');
    return;
  }
  const start = `${date}T${startTime}:00`;
  const end = `${date}T${endTime}:00`;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.add_record(subj ? subj.id : 1, desc, start, end), 'Add record');
    if (!result || result.ok === false) return;
    await loadRecords();
  } else records.unshift({id: Date.now(), subject_id: subj?.id, subject_name: subjName, description: desc, duration: '0h', date});
  row.querySelector('.records-add-desc').value = '';
  row.querySelector('.records-add-start').value = '';
  row.querySelector('.records-add-end').value = '';
  renderGallery(); renderTodayRecords(); updateTiles();
}

function editRecord(span) {
  const row = span.closest('tr, .grec-row');
  if (row.classList.contains('records-editing')) return;
  row.classList.add('records-editing');
  
  // Gallery row: convert grec cells to edit inputs
  if (row.matches('.grec-row')) {
    const record = records.find(r => Number(r.id) === Number(row.dataset.id));
    const currentSubjectId = record ? record.subject_id : null;
    
    // Subject: replace text with select
    const subjCell = row.querySelector('.grec-subj');
    subjCell.innerHTML = `<select>${subjects.map(s => `<option value="${s.id}"${Number(s.id) === Number(currentSubjectId) ? ' selected' : ''}>${esc(s.name)}</option>`).join('')}</select>`;
    
    // Description: replace text with input
    const descCell = row.querySelector('.grec-desc');
    descCell.innerHTML = `<input type="text" value="${attr(row.dataset.desc)}">`;
    
    // Time: extract HH:MM from start_iso/end_iso, replace with two time inputs
    const startIso = record ? (record.start_iso || record.start_time || '') : '';
    const endIso = record ? (record.end_iso || record.end_time || '') : '';
    const startHHMM = startIso && startIso.includes('T') ? startIso.split('T')[1].substring(0, 5) : '';
    const endHHMM = endIso && endIso.includes('T') ? endIso.split('T')[1].substring(0, 5) : '';
    const timeCell = row.querySelector('.grec-time');
    timeCell.innerHTML = `<input type="time" value="${startHHMM}" class="edit-start-time" style="width:80px">` +
      `<span style="margin:0 2px;color:var(--muted)">–</span>` +
      `<input type="time" value="${endHHMM}" class="edit-end-time" style="width:80px">`;
    
    // Duration: hide during edit
    row.querySelector('.grec-dur').style.display = 'none';
    
    // Actions: save/cancel
    row.querySelector('.records-actions').innerHTML = 
      '<span class="edit-actions-inline"><span class="act save" onclick="saveEdit(this)" title="Save">✓</span><span class="act cancel" onclick="cancelEdit(this)" title="Cancel">✕</span></span>';
    return;
  }
  
  // Table row: original logic (for Timer page today-records)
  const tr = row;
  if (tr.classList.contains('records-editing')) return;
  tr.classList.add('records-editing');
  const dateCell = tr.querySelector('.cell-date');
  if (dateCell) dateCell.innerHTML = `<input type="date" value="${attr(tr.dataset.date)}">`;
  const record = records.find(r => Number(r.id) === Number(tr.dataset.id));
  const currentSubjectId = record ? record.subject_id : null;
  tr.querySelector('.cell-subj').innerHTML = `<select>${subjects.map(s => `<option value="${s.id}"${Number(s.id) === Number(currentSubjectId) || (!currentSubjectId && s.name === tr.dataset.subject) ? ' selected' : ''}>${esc(s.name)}</option>`).join('')}</select>`;
  tr.querySelector('.cell-desc').innerHTML = `<input type="text" value="${attr(tr.dataset.desc)}">`;
  // Extract HH:MM from ISO timestamps for time inputs
  const startIso = record ? (record.start_iso || record.start_time || '') : '';
  const endIso = record ? (record.end_iso || record.end_time || '') : '';
  const startHHMM = startIso && startIso.includes('T') ? startIso.split('T')[1].substring(0, 5) : '';
  const endHHMM = endIso && endIso.includes('T') ? endIso.split('T')[1].substring(0, 5) : '';
  tr.querySelector('.cell-dur').innerHTML =
    `<input type="time" value="${startHHMM}" class="edit-start-time" style="width:85px">` +
    `<span style="margin:0 4px;color:var(--muted)">–</span>` +
    `<input type="time" value="${endHHMM}" class="edit-end-time" style="width:85px">`;
  tr.querySelector('td:last-child').innerHTML = '<span class="edit-actions-inline"><span class="act save" onclick="saveEdit(this)" title="Save">✓</span><span class="act cancel" onclick="cancelEdit(this)" title="Cancel">✕</span></span>';
}

async function saveEdit(span) {
  // Gallery row path
  const gRow = span.closest('.grec-row');
  if (gRow) {
    const date = gRow.dataset.date || todayIso();
    const subjectSelect = gRow.querySelector('.grec-subj select');
    const subjectId = Number(subjectSelect.value) || null;
    const desc = gRow.querySelector('.grec-desc input').value;
    const startInput = gRow.querySelector('.edit-start-time');
    const endInput = gRow.querySelector('.edit-end-time');
    let start, end;
    if (startInput && endInput && startInput.value && endInput.value) {
      start = `${date}T${startInput.value}:00`;
      end = `${date}T${endInput.value}:00`;
    } else {
      const fallback = recordRangeFromDuration(date, '0h');
      start = fallback.start; end = fallback.end;
    }
    const id = Number(gRow.dataset.id);
    if (window.pywebview && window.pywebview.api) {
      const result = await callApi(window.pywebview.api.update_record(id, {
        subject_id: subjectId, description: desc,
        start_time: start, end_time: end
      }), 'Update record');
      if (!result || result.ok === false) return;
      await loadRecords();
      renderGallery(); renderTodayRecords(); updateTiles();
      return;
    }
    const selectedSubject = subjectById(subjectId);
    gRow.dataset.subject = selectedSubject ? selectedSubject.name : (subjectSelect.options[subjectSelect.selectedIndex]?.text || '—');
    gRow.dataset.desc = desc;
    const r = records.find(x => Number(x.id) === id);
    if (r) Object.assign(r, {subject_id: subjectId, subject_name: gRow.dataset.subject, description: desc});
    renderGallery(); renderTodayRecords(); updateTiles();
    return;
  }

  // Table row path
  const tr = span.closest('tr');
  const startInput = tr.querySelector('.edit-start-time');
  const endInput = tr.querySelector('.edit-end-time');
  const dateInput = tr.querySelector('.cell-date input');
  const date = dateInput ? dateInput.value : tr.dataset.date || todayIso();
  const subjectSelect = tr.querySelector('.cell-subj select');
  const subjectId = Number(subjectSelect.value) || null;
  const selectedSubject = subjectById(subjectId);
  const desc = tr.querySelector('.cell-desc input').value;
  let start, end;
  if (startInput && endInput && startInput.value && endInput.value) {
    start = `${date}T${startInput.value}:00`;
    end = `${date}T${endInput.value}:00`;
  } else {
    const fallback = recordRangeFromDuration(date, '0h');
    start = fallback.start; end = fallback.end;
  }
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.update_record(Number(tr.dataset.id), {
      subject_id: subjectId,
      description: desc,
      start_time: start,
      end_time: end
    }), 'Update record');
    if (!result.ok) {
      renderGallery(); renderTodayRecords();
      return;
    }
    await loadRecords();
    renderGallery(); renderTodayRecords(); updateTiles();
    return;
  }
  Object.assign(tr.dataset, {date, subject: selectedSubject ? selectedSubject.name : subjectSelect.options[subjectSelect.selectedIndex]?.text || '—', desc, dur: '0h'});
  const r = records.find(x => Number(x.id) === Number(tr.dataset.id));
  if (r) Object.assign(r, {date: tr.dataset.date, subject_id: subjectId, subject_name: tr.dataset.subject, description: tr.dataset.desc, duration: tr.dataset.dur});
  renderGallery(); renderTodayRecords(); updateTiles();
}

function cancelEdit() { renderGallery(); renderTodayRecords(); }

async function delRecord(span) {
  const id = Number(span.closest('tr, .grec-row').dataset.id);
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.delete_record(id), 'Delete record');
    if (!result || result.ok === false) return;
    await loadRecords();
  }
  else records = records.filter(r => Number(r.id) !== id);
  renderGallery(); renderTodayRecords(); updateTiles();
}

async function addSubject() {
  const row = document.querySelector('#page-subjects .subjects-list').previousElementSibling;
  const input = row.querySelector('input');
  const dot = row.querySelector('.subject-dot');
  const name = input.value.trim();
  if (!name) return;
  const color = rgbToHex(dot.style.backgroundColor || dot.style.background || '#5E6AD2');
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.add_subject(name, color), 'Add subject');
    if (!result || result.ok === false) return;
    await loadSubjects();
  }
  else subjects.push({id: Date.now(), name, color});
  input.value = ''; renderSubjects(); renderTimer();
}

function renderSubjects() {
  const list = document.querySelector('#page-subjects .subjects-list');
  list.innerHTML = subjects.length ? subjects.map(s => `<div class="subject-row" data-id="${s.id}"><span class="subject-dot" style="background:${s.color};"></span><span class="subject-name">${esc(s.name)}</span><span class="subject-actions"><span class="act" onclick="editSubject(this)">✎</span><span class="act" onclick="delSubject(this)">🗑</span></span></div>`).join('') : '<div class="empty-state">No subjects. Add one first.</div>';
  const addSelect = document.querySelector('.records-add-subject');
  if (addSelect) addSelect.innerHTML = subjects.map(s => `<option>${esc(s.name)}</option>`).join('');
  const todoSelect = document.getElementById('todoSubject');
  if (todoSelect) todoSelect.innerHTML = '<option value="">— Select —</option>' + subjects.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  document.querySelector('#page-subjects .page-sub').textContent = `${subjects.length} subjects — manage your activity categories`;
}

function editSubject(span) {
  const row = span.closest('.subject-row');
  const name = row.querySelector('.subject-name').textContent.trim();
  const dot = row.querySelector('.subject-dot');
  const currentColor = rgbToHex(dot.style.backgroundColor || dot.style.background || '#5E6AD2');
  row.querySelector('.subject-name').innerHTML = `<input type="text" value="${attr(name)}" style="border:none;background:transparent;font-size:13px;color:var(--text);font-family:inherit;padding:2px 4px;border-bottom:1px solid var(--accent);outline:none;flex:1;">`;
  // Make color dot clickable to cycle through preset colors
  dot.classList.add('editable');
  dot.title = 'Click to change color';
  dot.dataset.color = currentColor;
  dot.onclick = function() {
    const colors = SUBJECT_COLORS;
    const idx = colors.indexOf(dot.dataset.color);
    const next = colors[(idx + 1) % colors.length];
    dot.dataset.color = next;
    dot.style.backgroundColor = next;
    dot.style.background = next;  // override for consistency
  };
  row.querySelector('.subject-actions').innerHTML = '<span class="act save" onclick="saveSubject(this)" style="color:var(--accent);">✓</span><span class="act cancel" onclick="renderSubjects()">✕</span>';
}

async function saveSubject(span) {
  const row = span.closest('.subject-row');
  const id = Number(row.dataset.id);
  const subj = subjects.find(s => Number(s.id) === id);
  const name = row.querySelector('input').value.trim();
  const dot = row.querySelector('.subject-dot');
  const color = dot.dataset.color || rgbToHex(dot.style.backgroundColor || subj?.color || '#5E6AD2');
  if (!subj || !name) return;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.update_subject(id, name, color), 'Update subject');
    if (!result || result.ok === false) return;
    await loadSubjects();
  }
  else subj.name = name;
  renderSubjects(); renderTimer();
}

async function delSubject(span) {
  const id = Number(span.closest('.subject-row').dataset.id);
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.delete_subject(id), 'Delete subject');
    if (!result || result.ok === false) return;
    await loadSubjects();
  }
  else subjects = subjects.filter(s => Number(s.id) !== id);
  renderSubjects(); renderTimer();
}

function openQuickAddSubjectModal() {
  document.getElementById('quickAddSubjectInput').value = '';
  showModal(document.getElementById('quickAddSubjectModal'));
  setTimeout(() => document.getElementById('quickAddSubjectInput').focus(), 100);
}

function closeQuickAddSubjectModal() {
  document.getElementById('quickAddSubjectModal').classList.remove('show');
}

function showModal(target) {
  if (!target) return;
  closeAllModals();
  target.classList.add('show');
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay.show').forEach(m => m.classList.remove('show'));
  pendingRemoveSlot = null;
}

async function submitQuickAddSubject() {
  const input = document.getElementById('quickAddSubjectInput');
  const name = input.value.trim();
  if (!name) return;
  if (window.pywebview && window.pywebview.api) {
    const result = await callApi(window.pywebview.api.add_subject(name, '#5E6AD2'), 'Add subject');
    if (!result || result.ok === false) return;
    await loadSubjects();
  }
  else subjects.push({id: Date.now(), name, color: '#5E6AD2'});
  closeQuickAddSubjectModal();
  renderSubjects(); renderTimer();
}

async function quickAddSubject() {
  openQuickAddSubjectModal();
}

function renderSettings() {
  const wsSelect = document.getElementById('weekStartSelect');
  if (wsSelect) wsSelect.value = weekStart;
  const mtToggle = document.getElementById('minimizeTrayToggle');
  if (mtToggle) mtToggle.checked = minimizeToTray;
  const defaultSlotsSelect = document.getElementById('defaultSlotsSelect');
  if (defaultSlotsSelect) defaultSlotsSelect.value = defaultSlots;

  // minimize-to-tray works on macOS and Windows
  const isDesktop = navigator.platform.toLowerCase().includes('mac') || navigator.platform.toLowerCase().includes('win');
  const mtRow = document.getElementById('minimizeTrayRow');
  if (mtRow) mtRow.style.display = isDesktop ? '' : 'none';

  // ── Backup ──────────────────────────────────────────

  const abToggle = document.getElementById('autoBackupToggle');
  if (abToggle) abToggle.checked = window._autoBackup !== false;

  const chooseBtn = document.getElementById('chooseBackupBtn');
  const backupPathEl = document.getElementById('backupPath');
  const backupDescEl = document.getElementById('backupDesc');
  if (backupPathEl) {
    // Reflect saved path
    const savedPath = window._backupPath || '~/Documents/Foclo/backups/';
    backupPathEl.textContent = savedPath;
    if (backupDescEl) backupDescEl.textContent = 'Hourly backup to ' + savedPath + '/';
  }

  // ── Restore ─────────────────────────────────────────
}

function bindSettingsControls() {
  const wsSelect = document.getElementById('weekStartSelect');
  if (wsSelect) {
    wsSelect.addEventListener('change', async () => {
      weekStart = wsSelect.value;
      if (window.pywebview && window.pywebview.api) {
        wsSelect.disabled = true;
        try {
          const result = await callApi(window.pywebview.api.update_setting('week_starts_on', weekStart === 'mon' ? 'Monday' : 'Sunday'), 'Update week setting');
          if (!result || result.ok === false) return;
        } finally {
          wsSelect.disabled = false;
        }
      }
      initializeDynamicDates();
      updateTiles();
    });
  }

  const mtToggle = document.getElementById('minimizeTrayToggle');
  if (mtToggle) {
    mtToggle.addEventListener('change', async () => {
      minimizeToTray = mtToggle.checked;
      if (window.pywebview && window.pywebview.api) {
        mtToggle.disabled = true;
        try {
          await callApi(window.pywebview.api.update_setting('minimize_to_tray', minimizeToTray ? '1' : '0'), 'Update minimize setting');
        } finally {
          mtToggle.disabled = false;
        }
      }
    });
  }

  const defaultSlotsSelect = document.getElementById('defaultSlotsSelect');
  if (defaultSlotsSelect) {
    defaultSlotsSelect.addEventListener('change', async e => {
      defaultSlots = e.target.value;
      if (window.pywebview && window.pywebview.api) {
        defaultSlotsSelect.disabled = true;
        try {
          await callApi(window.pywebview.api.update_setting('default_slots', defaultSlots), 'Update default slots setting');
        } finally {
          defaultSlotsSelect.disabled = false;
        }
      }
    });
  }

  const abToggle = document.getElementById('autoBackupToggle');
  if (abToggle) {
    abToggle.addEventListener('change', async () => {
      const enabled = abToggle.checked;
      if (window.pywebview && window.pywebview.api) {
        abToggle.disabled = true;
        try {
          await callApi(window.pywebview.api.update_setting('auto_backup', enabled ? '1' : '0'), 'Update backup setting');
        } finally {
          abToggle.disabled = false;
        }
      }
      window._autoBackup = enabled;
    });
  }

  const chooseBtn = document.getElementById('chooseBackupBtn');
  const backupPathEl = document.getElementById('backupPath');
  const backupDescEl = document.getElementById('backupDesc');
  if (chooseBtn && backupPathEl) {
    chooseBtn.addEventListener('click', async () => {
      if (!window.pywebview || !window.pywebview.api) return;
      try {
        const result = await callApi(window.pywebview.api.choose_backup_folder(backupPathEl.textContent), 'Choose backup folder');
        if (!result.ok) {
          if (!isCancelResult(result)) alert('Backup folder selection failed: ' + (result.error || 'No folder selected'));
          return;
        }
        window._backupPath = result.path;
        backupPathEl.textContent = result.path;
        if (backupDescEl) backupDescEl.textContent = 'Hourly backup to ' + result.path + '/';
      } catch (e) {
        alert('Backup folder selection failed: ' + (e.message || e));
      }
    });
  }

  const restoreBtn = document.getElementById('restoreBackupBtn');
  if (restoreBtn) {
    restoreBtn.addEventListener('click', async () => {
      if (!window.pywebview || !window.pywebview.api) return;
      try {
        const savedPath = window._backupPath || '~/Documents/Foclo/backups/';
        const pick = await callApi(window.pywebview.api.choose_backup_file(savedPath), 'Choose backup file');
        if (!pick.ok) {
          if (!isCancelResult(pick)) alert('Restore file selection failed: ' + (pick.error || 'No file selected'));
          return;
        }
        if (!confirm('This will replace ALL current data with the backup from:\n\n' + pick.path + '\n\nThe app will close after restore.')) return;
        const result = await callApi(window.pywebview.api.restore_backup(pick.path), 'Restore backup');
        if (!result.ok) alert('Restore failed: ' + result.error);
        // On success, the Python side calls window.destroy() - app quits
      } catch (e) {
        alert('Restore failed: ' + (e.message || e));
      }
    });
  }
}

function tickLocalSlots() {
  slots.forEach(s => {
    if (s.status === 'running' && s.startedAt) {
      const base = s.elapsed || 0;
      s.display_time = fmtSeconds(base + Math.floor((Date.now() - s.startedAt) / 1000));
    }
  });
}

function pauseLocal(s) {
  if (s.status === 'running' && s.startedAt) s.elapsed = (s.elapsed || 0) + Math.floor((Date.now() - s.startedAt) / 1000);
  s.startedAt = null; s.status = 'paused'; s.display_time = fmtSeconds(s.elapsed || 0);
}

function calcDur(start, end) {
  if (!start || !end) return '—';
  const [sh, sm] = start.split(':').map(Number), [eh, em] = end.split(':').map(Number);
  let mins = (eh * 60 + em) - (sh * 60 + sm);
  if (mins < 0) mins += 24 * 60;
  const h = Math.floor(mins / 60), m = mins % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

function fmtSeconds(sec) {
  sec = Number(sec);
  if (!Number.isFinite(sec)) sec = 0;
  sec = Math.max(0, Math.floor(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function todayIso() { return formatLocalDate(new Date()); }
function formatLocalDate(date) {
  const pad = n => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}
function esc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function attr(s) { return esc(s).replace(/"/g, '&quot;'); }
function isCancelResult(result) { return String(result?.error || '').toLowerCase() === 'cancelled'; }
function rgbToHex(value) {
  const m = String(value).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return value || '#5E6AD2';
  return '#' + [m[1], m[2], m[3]].map(n => Number(n).toString(16).padStart(2, '0')).join('').toUpperCase();
}

function parseDurationS(dur) {
  dur = String(dur ?? '');
  let total = 0;
  const h = dur.match(/([\d.]+)\s*h/);
  const m = dur.match(/(\d+)\s*m/);
  if (h) total += parseFloat(h[1]) * 3600;
  if (m) total += parseInt(m[1]) * 60;
  if (!h && !m) { const n = parseFloat(dur); if (!isNaN(n)) total = n * 3600; }
  return Math.round(total);
}

function recordRangeFromDuration(date, dur) {
  const startDate = date || todayIso();
  const [year, month, day] = startDate.split('-').map(Number);
  const startDt = new Date(year, month - 1, day, 0, 0, 0);
  const endDt = new Date(startDt.getTime() + parseDurationS(dur) * 1000);
  return {
    start: formatLocalIso(startDt),
    end: formatLocalIso(endDt)
  };
}

function formatLocalIso(date) {
  const pad = n => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

// ── Quit confirmation ────────────────────────────

function showQuitModal() {
  document.getElementById('quitConfirmMsg').textContent =
    'Timers are active. What would you like to do before quitting?';
  showModal(quitModal);
}

function closeQuitModal() {
  quitModal.classList.remove('show');
}

async function quitPause() {
  if (pyApi) {
    const result = await callApi(pyApi.pause_all_slots(), 'Pause timers');
    if (!result || result.ok === false) return;
    await callApi(pyApi.quit_app(), 'Quit app');
  }
}

async function quitArchive() {
  if (pyApi) {
    const result = await callApi(pyApi.archive_all_slots(), 'Archive timers');
    if (!result || result.ok === false) return;
    await callApi(pyApi.quit_app(), 'Quit app');
  }
}

function resetAllData() {
  if (!pyApi) {
    alert('API not ready — please wait for the app to finish loading.');
    return;
  }
  const modal = document.getElementById('resetConfirmModal');
  showModal(modal);
}

function closeResetModal() {
  document.getElementById('resetConfirmModal').classList.remove('show');
}

function closeSwitchTimerModal() {
  document.getElementById('switchTimerModal').classList.remove('show');
}

async function doResetAllData() {
  const result = await callApi(pyApi.reset_all_data(), 'Reset all data');
  if (result && result.ok) {
    document.getElementById('resetConfirmModal').classList.remove('show');
    await callApi(pyApi.quit_app(), 'Quit app');
  }
}
