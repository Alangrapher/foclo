let pyApi = window.pywebview ? window.pywebview.api : null;
const proto = document.getElementById('prototype');
const compactBtn = document.getElementById('compactBtn');
const expandBtn = document.getElementById('expandBtn');
const darkToggle = document.getElementById('darkToggle');
const modal = document.getElementById('easterEggModal');
const trigger = document.getElementById('easterEggTrigger');

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
let isDark = false;
let isMoss = false;
let clickCount = 0;
let clickTimer = null;
let lastExport = 'No exports yet';

function whenReady(fn) {
  if (window.pywebview && window.pywebview.api) {
    pyApi = window.pywebview.api;
    fn();
  } else {
    window.addEventListener('pywebviewready', () => {
      pyApi = window.pywebview.api;
      fn();
    });
  }
}

whenReady(async () => {
  await loadAll();
  setInterval(refreshClocks, 500);
});

document.addEventListener('DOMContentLoaded', () => {
  bindStaticControls();
  if (!pyApi) renderAll();
});

function bindStaticControls() {
  document.querySelectorAll('.nav-item[data-page]').forEach(item => item.addEventListener('click', () => switchPage(item.dataset.page)));
  compactBtn.addEventListener('click', enterCompact);
  expandBtn.addEventListener('click', exitCompact);
  darkToggle.addEventListener('click', toggleThemeClick);
  trigger.addEventListener('click', () => modal.classList.add('show'));
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('show'); });
  const removeSlotModal = document.getElementById('removeSlotModal');
  removeSlotModal.addEventListener('click', e => { if (e.target === removeSlotModal) closeRemoveSlotModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { modal.classList.remove('show'); closeRemoveSlotModal(); } });
  document.querySelectorAll('#page-export .btn-secondary').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('#page-export .btn-secondary').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  }));
  const exportButton = document.querySelector('#page-export .btn-primary');
  if (exportButton) exportButton.addEventListener('click', () => {
    lastExport = new Date().toLocaleString([], {hour: '2-digit', minute: '2-digit', year: 'numeric', month: 'short', day: 'numeric'});
    document.querySelector('#page-export .page-sub').textContent = 'Last export: ' + lastExport;
  });
}

async function loadAll() {
  if (!window.pywebview || !window.pywebview.api) return;
  await Promise.all([loadSubjects(), loadSlots(), loadTodos(), loadRecords()]);
  renderAll();
}

async function loadSubjects() {
  subjects = await window.pywebview.api.get_subjects();
}

async function loadSlots() {
  const localState = {};
  slots.forEach(s => { localState[s.index] = { subject_id: s.subject_id, description: s.description, collapsed: s.collapsed }; });
  slots = await window.pywebview.api.get_all_slots();
  if (!slots.length) slots = [{index: 0, status: 'idle', subject_id: null, description: '', display_time: '00:00:00', collapsed: false}];
  slots.forEach(s => {
    if (localState[s.index]) {
      if (s.subject_id === null || s.subject_id === undefined) s.subject_id = localState[s.index].subject_id;
      if (s.description === null || s.description === undefined || s.description === '') s.description = localState[s.index].description || '';
      s.collapsed = localState[s.index].collapsed || false;
    }
    if (s.collapsed === undefined) s.collapsed = false;
  });
  compactIndex = Math.min(compactIndex, slots.length - 1);
}

async function loadTodos() {
  todos = await window.pywebview.api.get_todos();
}

async function loadRecords() {
  records = await window.pywebview.api.get_records(recordsFilter);
}

async function refreshClocks() {
  if (window.pywebview && window.pywebview.api) {
    await loadSlots();
  } else {
    tickLocalSlots();
  }
  updateTimerCards();
  renderCompact();
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
  renderRecords();
  renderSettings();
  renderCompact();
}

function subjectById(id) {
  return subjects.find(s => Number(s.id) === Number(id));
}

function subjectOptions(selectedId) {
  return '<option value="">— Select subject —</option>' + subjects.map(s => `<option value="${s.id}"${Number(s.id) === Number(selectedId) ? ' selected' : ''}>${esc(s.name)}</option>`).join('');
}

function renderTimer() {
  const page = document.getElementById('page-timer');
  const tileRow = page.querySelector('.tile-row');
  let node = page.querySelector('.page-header').nextElementSibling;
  while (node && node !== tileRow) {
    const next = node.nextElementSibling;
    if (node.classList.contains('card')) node.remove();
    node = next;
  }
  slots.forEach(slot => page.insertBefore(timerCard(slot), tileRow));
  renderTodayRecords();
  updateTiles();
}

function timerCard(slot) {
  const index = slot.index;
  const subj = subjectById(slot.subject_id);
  const status = slot.status || 'idle';
  const label = status[0].toUpperCase() + status.slice(1);
  const actionText = status === 'running' ? 'Pause' : status === 'paused' ? 'Resume' : 'Start';
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
    <div class="form-row"${slot.collapsed ? ' style="display:none"' : ''}><div class="form-label">Subject</div><div class="select-wrapper"><select class="form-select" onchange="setSlotSubject(${index}, this.value)">${subjectOptions(slot.subject_id)}</select></div></div>
    <div class="form-row"${slot.collapsed ? ' style="display:none"' : ''}><div class="form-label">Description (optional)</div><input class="form-input" placeholder="What are you working on?" value="${attr(slot.description || '')}" oninput="setSlotDescription(${index}, this.value)"></div>
    <div class="btn-row"${slot.collapsed ? ' style="display:none"' : ''}>
      <button class="btn btn-primary" style="flex:1;" onclick="primaryTimerAction(${index})"><svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${iconPath}</svg>${actionText}</button>
      <button class="btn btn-secondary" style="flex:1;" onclick="archiveSlot(${index})"><svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 15h18"/><path d="m15 8-3 3-3-3"/></svg>Archive</button>
    </div>`;
  return card;
}

async function primaryTimerAction(index) {
  const slot = slots[index];
  if (slot.status === 'running') await pauseSlot(index);
  else await startSlot(index);
}

async function startSlot(index) {
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  const sid = card ? Number(card.querySelector('.form-select').value) || null : slots[index].subject_id;
  const desc = card ? card.querySelector('.form-input').value : slots[index].description;
  if (window.pywebview && window.pywebview.api) {
    await window.pywebview.api.set_description(index, desc || '');
    await window.pywebview.api.start_slot(index, sid);
    await loadSlots();
  } else {
    slots.forEach(s => { if (s.status === 'running') pauseLocal(s); });
    Object.assign(slots[index], {status: 'running', subject_id: sid, description: desc || '', startedAt: Date.now()});
  }
  renderTimer(); renderCompact();
}

async function pauseSlot(index) {
  if (window.pywebview && window.pywebview.api) {
    await window.pywebview.api.pause_slot(index);
    await loadSlots();
  } else pauseLocal(slots[index]);
  renderTimer(); renderCompact();
}

async function archiveSlot(index) {
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  const sid = card ? Number(card.querySelector('.form-select').value) || null : slots[index].subject_id;
  const desc = card ? card.querySelector('.form-input').value : slots[index].description;
  if (window.pywebview && window.pywebview.api) {
    await window.pywebview.api.archive_slot(index, sid, desc || '');
    // Clear local state so loadSlots merge doesn't restore old subject/description
    slots[index].subject_id = null;
    slots[index].description = '';
    await Promise.all([loadSlots(), loadRecords()]);
  } else {
    const slot = slots[index];
    records.unshift({id: Date.now(), subject_id: sid, subject_name: subjectById(sid)?.name || '—', description: desc || '—', start: '', end: '', duration: slot.display_time, date: todayIso()});
    Object.assign(slot, {status: 'idle', subject_id: null, description: '', display_time: '00:00:00', elapsed: 0, startedAt: null});
  }
  renderAll();
}

async function addSlot() {
  if (slots.length >= 5) return;
  if (window.pywebview && window.pywebview.api) { await window.pywebview.api.add_slot(); await loadSlots(); }
  else slots.push({index: slots.length, status: 'idle', subject_id: null, description: '', display_time: '00:00:00', collapsed: false});
  renderTimer(); renderCompact();
}

async function removeSlot(index) {
  if (slots.length <= 1) return;
  if (window.pywebview && window.pywebview.api) { await window.pywebview.api.remove_slot(index); await loadSlots(); }
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
  pendingRemoveSlot = index;
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  const subj = subjectById(slot.subject_id);
  const name = subj ? subj.name : 'this timer';
  const modal = document.getElementById('removeSlotModal');
  modal.querySelector('.remove-slot-msg').textContent = `Timer is ${slot.status}. Close "${name}"?`;
  modal.classList.add('show');
}

function closeRemoveSlotModal() {
  document.getElementById('removeSlotModal').classList.remove('show');
  pendingRemoveSlot = null;
}

async function archiveThenRemove() {
  const index = pendingRemoveSlot;
  if (index === null || index === undefined) return;
  await archiveSlot(index);
  closeRemoveSlotModal();
}

async function clearAndRemove() {
  const index = pendingRemoveSlot;
  if (index === null || index === undefined) return;
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

function setSlotDescription(index, value) {
  slots[index].description = value;
  if (window.pywebview && window.pywebview.api) window.pywebview.api.set_description(index, value);
  const card = document.querySelector(`.timer-slot-card[data-slot="${index}"]`);
  if (card) {
    const subj = subjectById(slots[index].subject_id);
    const el = card.querySelector('.timer-subject-line');
    if (el) el.textContent = `${subj ? subj.name : '—'}${slots[index].description ? ' — ' + slots[index].description : ''}`;
  }
  renderCompact();
}

function toggleCollapse(el, ev) {
  if (ev) ev.stopPropagation();
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
  const todayRows = records.slice(0, 3);
  tbody.innerHTML = todayRows.length ? todayRows.map(r => `<tr ondblclick="fillRecordToSlot(${r.id})"><td>${esc(r.subject_name || '—')}</td><td>${esc(r.description || '—')}</td><td style="text-align:right">${esc(r.duration || '0m')}</td></tr>`).join('') : '<tr><td>—</td><td>No records yet</td><td style="text-align:right">0m</td></tr>';
}

function fillRecordToSlot(id) {
  const record = records.find(r => Number(r.id) === Number(id));
  if (!record) return;
  const slot = slots.find(s => s.status === 'idle') || slots[0];
  const subj = subjects.find(s => s.name === record.subject_name);
  slot.subject_id = subj ? subj.id : null;
  slot.description = record.description || '';
  if (window.pywebview && window.pywebview.api) window.pywebview.api.set_description(slot.index, slot.description);
  switchPage('timer');
  renderTimer();
}

function updateTiles() {
  const vals = document.querySelectorAll('#page-timer .tile-value');
  if (vals[0]) vals[0].textContent = records.length ? records[0].duration : '0m';
  if (vals[1]) vals[1].textContent = records.length + ' records';
}

let _lastCompactKey = '';

function renderCompact() {
  const slot = slots[compactIndex] || slots[0];
  if (!slot) return;
  const panel = document.getElementById('compactPanel');
  const subj = subjectById(slot.subject_id);
  const status = slot.status || 'idle';
  panel.querySelector('.compact-top').innerHTML = `<span class="badge ${status}"><span class="dot"></span> ${status[0].toUpperCase() + status.slice(1)}</span>`;
  panel.querySelector('.compact-slot-indicator').textContent = `${compactIndex + 1} / ${slots.length}`;
  panel.querySelector('.compact-clock').textContent = slot.display_time || '00:00:00';
  const subjText = subj ? subj.name : '—';
  const desc = slot.description ? ' — ' + slot.description : '';
  panel.querySelector('.compact-subject').textContent = subjText + desc;
  panel.querySelector('.compact-subject').style.display = '';
  const arrows = panel.querySelectorAll('.arrow');
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
  const action = status === 'running' ? 'Pause' : status === 'paused' ? 'Resume' : 'Start';
  const key = `${compactIndex}-${status}`;
  if (key !== _lastCompactKey) {
    _lastCompactKey = key;
    const icon = status === 'running' ? '<rect x="14" y="3" width="5" height="18" rx="1"/><rect x="5" y="3" width="5" height="18" rx="1"/>' : '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/>';
    panel.querySelector('.compact-actions').innerHTML = `<button class="btn btn-primary" style="width:145px" onclick="primaryTimerAction(${slot.index})"><svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icon}</svg>${action}</button><button class="btn btn-secondary" style="width:145px" onclick="archiveSlot(${slot.index})"><svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 15h18"/><path d="m15 8-3 3-3-3"/></svg>Archive</button>`;
  }
}

function enterCompact() {
  document.documentElement.classList.add('showing-compact');
  proto.classList.add('showing-compact');
  document.querySelector('.sidebar').style.display = 'none';
  document.querySelector('.content').style.display = 'none';
  const cp = document.getElementById('compactPanel');
  cp.style.display = 'flex';
  const runningIdx = slots.findIndex(s => s.status === 'running');
  compactIndex = runningIdx >= 0 ? runningIdx : 0;
  renderCompact();
  if (pyApi && pyApi.resize_window) pyApi.resize_window(380, 230);
}

function exitCompact() {
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
  if (pyApi && pyApi.resize_window) pyApi.resize_window(760, 620);
}

function switchPage(name) {
  document.querySelectorAll('.nav-item[data-page]').forEach(n => n.classList.toggle('active', n.dataset.page === name));
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + name));
}

function toggleThemeClick() {
  clickCount++;
  if (clickCount === 1) clickTimer = setTimeout(() => { clickCount = 0; }, 2000);
  if (clickCount >= 8) {
    clearTimeout(clickTimer); clickCount = 0; isMoss = !isMoss;
    document.documentElement.classList.toggle('moss', isMoss);
    if (isMoss) {
      isDark = false; document.documentElement.classList.remove('dark');
      document.querySelector('.sidebar-brand').textContent = 'MOSS_SYS :: ONLINE';
      darkToggle.innerHTML = '<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="#cc2200" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.341 6.484A10 10 0 0 1 10.266 21.85"/><path d="M3.659 17.516A10 10 0 0 1 13.74 2.152"/><circle cx="12" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/></svg> Enable';
      darkToggle.style.color = '#cc2200'; darkToggle.style.borderColor = '#cc2200';
    } else {
      document.querySelector('.sidebar-brand').textContent = 'Alangrapher';
      darkToggle.style.color = ''; darkToggle.style.borderColor = ''; updateDarkButton();
    }
    return;
  }
  if (isMoss) return;
  isDark = !isDark;
  document.documentElement.classList.toggle('dark', isDark);
  updateDarkButton();
}

function updateDarkButton() {
  darkToggle.innerHTML = isDark
    ? '<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg> Light'
    : '<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 5h4"/><path d="M20 3v4"/><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/></svg> Dark';
}

async function addTodo() {
  const subjInput = document.getElementById('todoSubject');
  const descInput = document.getElementById('todoDesc');
  const subject = subjInput.value.trim();
  if (!subject) return;
  const description = descInput.value.trim();
  if (window.pywebview && window.pywebview.api) { await window.pywebview.api.add_todo(subject, description); await loadTodos(); }
  else todos.push({id: Date.now(), subject, description, status: 'pending'});
  subjInput.value = ''; descInput.value = ''; renderTodos();
}

async function toggleTodo(arg) {
  const id = typeof arg === 'number' ? arg : Number(arg.closest('.todo-item').dataset.id);
  if (window.pywebview && window.pywebview.api) { await window.pywebview.api.toggle_todo(id); await loadTodos(); }
  else { const t = todos.find(x => x.id === id); if (t) t.status = t.status === 'done' ? 'pending' : 'done'; }
  renderTodos();
}

async function startTodoTimer(arg) {
  const id = typeof arg === 'number' ? arg : Number(arg.closest('.todo-item').dataset.id);
  const todo = todos.find(t => Number(t.id) === Number(id));
  if (!todo || todo.status === 'done') return;
  let slot = slots.find(s => s.status === 'idle') || slots[0];
  let subj = subjects.find(s => s.name === todo.subject);
  if (!subj) { subj = {id: null, name: todo.subject, color: '#5E6AD2'}; }
  slot.subject_id = subj.id;
  slot.description = todo.description || '';
  switchPage('timer');
  await startSlot(slot.index);
}

function renderTodos() {
  const list = document.querySelector('#page-todo .todo-list');
  list.innerHTML = todos.map(t => `<div class="todo-item${t.status === 'done' ? ' done' : ''}" data-id="${t.id}"><div class="todo-checkbox" onclick="toggleTodo(${t.id})"></div><div class="todo-item-info"><div class="todo-item-subject">${esc(t.subject)}</div>${t.description ? `<div class="todo-item-desc">${esc(t.description)}</div>` : ''}</div><span class="todo-start-btn" onclick="startTodoTimer(${t.id})" title="Start timer"><svg style="width:14px;height:14px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/></svg></span></div>`).join('');
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
  document.querySelector('#page-records .records-scroll-wrap').classList.toggle('showing-dates', recordsFilter !== 'today');
  if (window.pywebview && window.pywebview.api) await loadRecords();
  renderRecords();
}

async function addRecord() {
  const row = document.getElementById('recordsAddRow');
  const subjName = row.querySelector('.records-add-subject').value;
  const subj = subjects.find(s => s.name === subjName) || subjects[0];
  const desc = row.querySelector('.records-add-desc').value.trim() || '—';
  const start = row.querySelector('.records-add-start').value;
  const end = row.querySelector('.records-add-end').value;
  const date = document.getElementById('recordsDateField').value || todayIso();
  if (window.pywebview && window.pywebview.api) {
    await window.pywebview.api.add_record(subj ? subj.id : 1, desc, `${date}T${start}:00`, `${date}T${end}:00`);
    await loadRecords();
  } else records.unshift({id: Date.now(), subject_id: subj?.id, subject_name: subjName, description: desc, start, end, duration: calcDur(start, end), date});
  row.querySelector('.records-add-desc').value = '';
  renderRecords(); renderTodayRecords();
}

function renderRecords() {
  const tbody = document.getElementById('recordsBody');
  tbody.innerHTML = records.map(r => `<tr data-id="${r.id}" data-date="${attr(r.date || todayIso())}" data-subject="${attr(r.subject_name || '—')}" data-desc="${attr(r.description || '—')}" data-start="${attr(r.start || '')}" data-end="${attr(r.end || '')}" data-dur="${attr(r.duration || '0m')}" ondblclick="fillRecordToSlot(${r.id})"><td class="cell-date records-date-col">${esc(r.date || todayIso())}</td><td class="cell-subj">${esc(r.subject_name || '—')}</td><td class="cell-desc">${esc(r.description || '—')}</td><td class="cell-start">${esc(r.start || '')}</td><td class="cell-end">${esc(r.end || '')}</td><td class="cell-dur" style="text-align:right">${esc(r.duration || '0m')}</td><td><span class="records-actions"><span class="act" onclick="editRecord(this)" title="Edit">✎</span><span class="act del" onclick="delRecord(this)" title="Delete">🗑</span></span></td></tr>`).join('');
  document.getElementById('recordsCount').textContent = records.length;
}

function editRecord(span) {
  const tr = span.closest('tr');
  if (tr.classList.contains('records-editing')) return;
  tr.classList.add('records-editing');
  tr.querySelector('.cell-date').innerHTML = `<input type="date" value="${attr(tr.dataset.date)}">`;
  tr.querySelector('.cell-subj').innerHTML = `<select>${subjects.map(s => `<option${s.name === tr.dataset.subject ? ' selected' : ''}>${esc(s.name)}</option>`).join('')}</select>`;
  tr.querySelector('.cell-desc').innerHTML = `<input type="text" value="${attr(tr.dataset.desc)}">`;
  tr.querySelector('.cell-start').innerHTML = `<input type="time" value="${attr(tr.dataset.start)}">`;
  tr.querySelector('.cell-end').innerHTML = `<input type="time" value="${attr(tr.dataset.end)}">`;
  tr.querySelector('td:last-child').innerHTML = '<span class="edit-actions-inline"><span class="act save" onclick="saveEdit(this)" title="Save">✓</span><span class="act cancel" onclick="cancelEdit(this)" title="Cancel">✕</span></span>';
}

function saveEdit(span) {
  const tr = span.closest('tr');
  const start = tr.querySelector('.cell-start input').value;
  const end = tr.querySelector('.cell-end input').value;
  Object.assign(tr.dataset, {date: tr.querySelector('.cell-date input').value, subject: tr.querySelector('.cell-subj select').value, desc: tr.querySelector('.cell-desc input').value, start, end, dur: calcDur(start, end)});
  const r = records.find(x => Number(x.id) === Number(tr.dataset.id));
  if (r) Object.assign(r, {date: tr.dataset.date, subject_name: tr.dataset.subject, description: tr.dataset.desc, start, end, duration: tr.dataset.dur});
  renderRecords();
}

function cancelEdit() { renderRecords(); }

async function delRecord(span) {
  const id = Number(span.closest('tr').dataset.id);
  if (window.pywebview && window.pywebview.api) { await window.pywebview.api.delete_record(id); await loadRecords(); }
  else records = records.filter(r => Number(r.id) !== id);
  renderRecords(); renderTodayRecords();
}

async function addSubject() {
  const row = document.querySelector('#page-subjects .subjects-list').previousElementSibling;
  const input = row.querySelector('input');
  const dot = row.querySelector('.subject-dot');
  const name = input.value.trim();
  if (!name) return;
  const color = rgbToHex(dot.style.backgroundColor || dot.style.background || '#5E6AD2');
  if (window.pywebview && window.pywebview.api) { await window.pywebview.api.add_subject(name, color); await loadSubjects(); }
  else subjects.push({id: Date.now(), name, color});
  input.value = ''; renderSubjects(); renderTimer();
}

function renderSubjects() {
  const list = document.querySelector('#page-subjects .subjects-list');
  list.innerHTML = subjects.map(s => `<div class="subject-row" data-id="${s.id}"><span class="subject-dot" style="background:${s.color};"></span><span class="subject-name">${esc(s.name)}</span><span class="subject-actions"><span class="act" onclick="editSubject(this)">✎</span><span class="act" onclick="delSubject(this)">🗑</span></span></div>`).join('');
  const addSelect = document.querySelector('.records-add-subject');
  if (addSelect) addSelect.innerHTML = subjects.map(s => `<option>${esc(s.name)}</option>`).join('');
  document.querySelector('#page-subjects .page-sub').textContent = `${subjects.length} subjects — manage your activity categories`;
}

function editSubject(span) {
  const row = span.closest('.subject-row');
  const name = row.querySelector('.subject-name').textContent.trim();
  row.querySelector('.subject-name').innerHTML = `<input type="text" value="${attr(name)}" style="border:none;background:transparent;font-size:13px;color:var(--text);font-family:inherit;padding:2px 4px;border-bottom:1px solid var(--accent);outline:none;flex:1;">`;
  row.querySelector('.subject-actions').innerHTML = '<span class="act save" onclick="saveSubject(this)" style="color:var(--accent);">✓</span><span class="act cancel" onclick="renderSubjects()">✕</span>';
}

async function saveSubject(span) {
  const row = span.closest('.subject-row');
  const id = Number(row.dataset.id);
  const subj = subjects.find(s => Number(s.id) === id);
  const name = row.querySelector('input').value.trim();
  if (!subj || !name) return;
  if (window.pywebview && window.pywebview.api) { await window.pywebview.api.update_subject(id, name, subj.color); await loadSubjects(); }
  else subj.name = name;
  renderSubjects(); renderTimer();
}

async function delSubject(span) {
  const id = Number(span.closest('.subject-row').dataset.id);
  if (window.pywebview && window.pywebview.api) { await window.pywebview.api.delete_subject(id); await loadSubjects(); }
  else subjects = subjects.filter(s => Number(s.id) !== id);
  renderSubjects(); renderTimer();
}

function renderSettings() {
  document.querySelectorAll('#page-settings .form-select')[1]?.addEventListener('change', async e => {
    if (window.pywebview && window.pywebview.api) await window.pywebview.api.update_setting('default_slots', e.target.value);
  });
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
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function todayIso() { return new Date().toISOString().slice(0, 10); }
function esc(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function attr(s) { return esc(s).replace(/"/g, '&quot;'); }
function rgbToHex(value) {
  const m = String(value).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return value || '#5E6AD2';
  return '#' + [m[1], m[2], m[3]].map(n => Number(n).toString(16).padStart(2, '0')).join('').toUpperCase();
}