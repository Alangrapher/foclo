#!/usr/bin/env python3
"""Build index.html from prototype.html + dynamic JS bridge."""
import re

# Read prototype
with open("prototype.html", "r") as f:
    proto = f.read()

# Extract CSS (from <style> to </style>)
css_start = proto.index("<style>") + len("<style>")
css_end = proto.index("</style>")
css = proto[css_start:css_end]

# Extract HTML body (from <body> to </script> before </body>)
body_start = proto.index("<body>")
# Find the last </script> before </body>
script_end = proto.rindex("</script>")
body_end = proto.index("</body>", script_end)
html_body = proto[body_start + len("<body>"):body_end]

# Remove the fake topbar section (lines with class="topbar")
html_body = re.sub(r'<div class="topbar">.*?</div>', '', html_body, flags=re.DOTALL)

# Build index.html
index = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Alangrapher</title>
<style>
{css}
</style>
</head>
<body>
{html_body}

<!-- Dynamic JS bridge — replaces prototype's static JS -->
<script>
// ═══ pywebview bridge ═══════════════════════════════════════
let api = null;
const REQUIRED_API_METHODS = [
    'get_subjects',
    'get_all_slots',
    'get_todos',
    'get_records',
    'get_settings'
];

function getApi() {{
    return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
}}

function hasRequiredApiMethods(candidate) {{
    return !!candidate && REQUIRED_API_METHODS.every(name => typeof candidate[name] === 'function');
}}

function ready(fn) {{
    let started = false;
    const startIfReady = () => {{
        const candidate = getApi();
        if (!hasRequiredApiMethods(candidate)) return false;
        api = candidate;
        if (!started) {{
            started = true;
            fn();
        }}
        return true;
    }};

    if (startIfReady()) return;

    let attempts = 0;
    const checkInterval = setInterval(() => {{
        attempts++;
        if (startIfReady()) {{
            clearInterval(checkInterval);
        }} else if (attempts === 50) {{
            console.error('pywebview API not ready yet; continuing to wait');
        }}
    }}, 100);

    window.addEventListener('pywebviewready', () => {{
        if (startIfReady()) clearInterval(checkInterval);
    }});
}}

// ═══ Global state mirror ═══════════════════════════════════
let _slots = [];
let _subjects = [];
let _todos = [];
let _recordsFilter = 'today';

// ═══ Init ══════════════════════════════════════════════════
ready(async () => {{
    await loadSubjects();
    await refreshAll();
    setInterval(refreshAll, 500);
}});

async function refreshAll() {{
    if (!api) return;
    await refreshSlots();
    await refreshTodos();
    await refreshRecords();
}}

// ═══ Slots / Timer ═════════════════════════════════════════
async function refreshSlots() {{
    _slots = await api.get_all_slots();
    _subjects = await api.get_subjects();
    renderTimerPage();
}}

function renderTimerPage() {{
    const container = document.querySelector('#page-timer');
    if (!container) return;

    // Rebuild cards
    const oldCards = container.querySelectorAll('.card');
    oldCards.forEach(c => c.remove());

    _slots.forEach((slot, i) => {{
        const card = buildTimerCard(slot, i);
        // Insert before tile-row
        const tileRow = container.querySelector('.tile-row');
        if (tileRow) {{
            container.insertBefore(card, tileRow);
        }} else {{
            container.appendChild(card);
        }}
    }});
}}

function buildTimerCard(slot, index) {{
    const card = document.createElement('div');
    card.className = 'card';
    card.dataset.slot = index;

    const subjName = _subjects.find(s => s.id === slot.subject_id);
    const badgeClass = slot.status === 'running' ? 'running' : slot.status === 'paused' ? 'paused' : 'idle';
    const badgeText = slot.status.charAt(0).toUpperCase() + slot.status.slice(1);

    const showActions = slot.status !== 'idle';
    const primaryLabel = slot.status === 'running' ? 'Pause' : slot.status === 'paused' ? 'Resume' : 'Start';
    const primaryAction = slot.status === 'running' ? `pauseSlot(${{index}})` : `startSlot(${{index}})`;

    // Build subject options
    let subjOpts = '<option>— Select subject —</option>';
    _subjects.forEach(s => {{
        const sel = s.id === slot.subject_id ? ' selected' : '';
        subjOpts += `<option value="${{s.id}}"${{sel}}>${{s.name}}</option>`;
    }});

    card.innerHTML = `
        <div class="slot-header">
            <span class="slot-label">Timer ${{index + 1}}</span>
            <span class="badge ${{badgeClass}}"><span class="dot"></span> ${{badgeText}}</span>
            <span class="slot-subject">${{subjName ? subjName.name : '—'}}</span>
            <span style="color:var(--muted);cursor:pointer;font-size:13px;" onclick="toggleCollapse(this)">
                <svg style="width:14px;height:14px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
            </span>
            ${{_slots.length > 1 ? `<span style="color:var(--muted);cursor:pointer;font-size:11px;" onclick="removeSlot(${{index}})">
                <svg style="width:12px;height:12px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
            </span>` : ''}}
            ${{_slots.length < 5 ? `<button class="add-slot-btn" title="Add timer slot (max 5)" onclick="addSlot()">
                <svg style="width:16px;height:16px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
            </button>` : ''}}
        </div>
        <div class="timer-clock">${{slot.display_time}}</div>
        <div class="timer-subject-line">${{subjName ? subjName.name : '—'}}</div>
        <div class="form-row"><div class="form-label">Subject</div>
            <div class="select-wrapper">
                <select class="form-select" onchange="setSlotSubject(${{index}}, this.value)">${{subjOpts}}</select>
            </div>
        </div>
        <div class="form-row"><div class="form-label">Description (optional)</div>
            <input class="form-input" placeholder="What are you working on?" value="${{slot.description || ''}}"
                onchange="setSlotDesc(${{index}}, this.value)">
        </div>
        <div class="btn-row">
            <button class="btn btn-primary" style="flex:1;" onclick="${{primaryAction}}">
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    ${{slot.status === 'running'
                        ? '<rect x="14" y="3" width="5" height="18" rx="1"/><rect x="5" y="3" width="5" height="18" rx="1"/>'
                        : '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/>'}}
                </svg>${{primaryLabel}}</button>
            <button class="btn btn-secondary" style="flex:1;" onclick="archiveSlot(${{index}})">
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 15h18"/><path d="m15 8-3 3-3-3"/>
                </svg>Archive</button>
        </div>
    `;
    return card;
}}

async function startSlot(index) {{
    if (_slots[index] && _slots[index].pendingAction) return;
    if (_slots[index]) _slots[index].pendingAction = true;
    const card = document.querySelector(`.card[data-slot="${{index}}"] .form-select`);
    const sel = card;
    const btn = card ? card.closest('.card').querySelector('.btn-primary') : null;
    if (btn) {{
        btn.disabled = true;
        btn.childNodes.forEach(c => {{ if (c.nodeType === 3) c.textContent = 'Working...'; }});
    }}
    const sid = sel ? parseInt(sel.value) || null : null;
    try {{
        await api.start_slot(index, sid);
    }} finally {{
        if (_slots[index]) _slots[index].pendingAction = false;
        refreshAll();
    }}
}}

async function pauseSlot(index) {{
    if (_slots[index] && _slots[index].pendingAction) return;
    if (_slots[index]) _slots[index].pendingAction = true;
    const card = document.querySelector(`.card[data-slot="${{index}}"]`);
    const btn = card ? card.querySelector('.btn-primary') : null;
    if (btn) {{
        btn.disabled = true;
        btn.childNodes.forEach(c => {{ if (c.nodeType === 3) c.textContent = 'Working...'; }});
    }}
    try {{
        await api.pause_slot(index);
    }} finally {{
        if (_slots[index]) _slots[index].pendingAction = false;
        refreshAll();
    }}
}}

async function archiveSlot(index) {{
    if (_slots[index] && _slots[index].pendingAction) return;
    if (_slots[index]) _slots[index].pendingAction = true;
    const card = document.querySelector(`.card[data-slot="${{index}}"]`);
    const btn = card ? card.querySelector('.btn-secondary') : null;
    if (btn) {{
        btn.disabled = true;
        btn.childNodes.forEach(c => {{ if (c.nodeType === 3) c.textContent = 'Working...'; }});
    }}
    try {{
        const sel = card ? card.querySelector('.form-select') : null;
        const inp = card ? card.querySelector('.form-input') : null;
        const sid = sel ? parseInt(sel.value) || null : null;
        const desc = inp ? inp.value : '';
        await api.archive_slot(index, sid, desc);
    }} finally {{
        if (_slots[index]) _slots[index].pendingAction = false;
        refreshAll();
    }}
}}

async function addSlot() {{
    await api.add_slot();
    refreshAll();
}}

async function removeSlot(index) {{
    await api.remove_slot(index);
    refreshAll();
}}

function setSlotSubject(index, value) {{
    // Handled by start_slot / archive_slot
}}

function setSlotDesc(index, value) {{
    api.set_description(index, value);
}}

function toggleCollapse(el) {{
    const card = el.closest('.card');
    const clock = card.querySelector('.timer-clock');
    const subjLine = card.querySelector('.timer-subject-line');
    const rows = card.querySelectorAll('.form-row, .btn-row');
    const hidden = clock.style.display === 'none';
    clock.style.display = hidden ? '' : 'none';
    if (subjLine) subjLine.style.display = hidden ? '' : 'none';
    rows.forEach(r => r.style.display = hidden ? '' : 'none');
    el.querySelector('svg').innerHTML = hidden
        ? '<path d="m6 9 6 6 6-6"/>'
        : '<path d="m18 15-6-6-6 6"/>';
}}

// ═══ Todos ═══════════════════════════════════════════════
async function refreshTodos() {{
    _todos = await api.get_todos();
    renderTodos();
}}

function renderTodos() {{
    const list = document.querySelector('#page-todo .todo-list');
    if (!list) return;
    // Remove old items (keep the inline add row)
    const oldItems = list.querySelectorAll('.todo-item');
    oldItems.forEach(el => el.remove());

    _todos.forEach(todo => {{
        const item = document.createElement('div');
        item.className = 'todo-item' + (todo.status === 'done' ? ' done' : '');
        item.dataset.id = todo.id;
        item.innerHTML = `
            <div class="todo-checkbox" onclick="toggleTodo(${{todo.id}})"></div>
            <div class="todo-item-info">
                <div class="todo-item-subject">${{escapeHTML(todo.subject)}}</div>
                ${{todo.description ? `<div class="todo-item-desc">${{escapeHTML(todo.description)}}</div>` : ''}}
            </div>
            <span class="todo-start-btn" onclick="startTodoTimer(${{todo.id}})" title="Start timer">
                <svg style="width:14px;height:14px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z"/>
                </svg>
            </span>`;
        list.appendChild(item);
    }});
    updateTodoCounter();
}}

// Override prototype's addTodo
async function addTodo() {{
    if (!api) return;
    const subjInput = document.getElementById('todoSubject');
    const descInput = document.getElementById('todoDesc');
    const subj = subjInput.value.trim();
    if (!subj) return;
    await api.add_todo(subj, descInput.value.trim());
    subjInput.value = '';
    descInput.value = '';
    refreshTodos();
}}
window.addTodo = addTodo;

async function toggleTodo(id) {{
    await api.toggle_todo(id);
    refreshTodos();
}}

function updateTodoCounter() {{
    const pending = _todos.filter(t => t.status === 'pending').length;
    const done = _todos.filter(t => t.status === 'done').length;
    const counter = document.getElementById('todoCounter');
    if (counter) counter.textContent = `${{pending}} pending · ${{done}} done`;
}}

async function startTodoTimer(id) {{
    const todo = _todos.find(t => t.id === id);
    if (!todo || todo.status === 'done') return;
    // Switch to Timer page and refresh slot state
    switchPage('timer');
    await refreshSlots();
    // Fill first idle slot, or create a new one
    let idleIdx = _slots.findIndex(s => s.status === 'idle');
    if (idleIdx < 0) {{
        const result = await api.add_slot();
        if (result.ok) {{
            await refreshSlots();
            idleIdx = _slots.findIndex(s => s.status === 'idle');
        }}
    }}
    if (idleIdx >= 0) {{
        _slots[idleIdx].pendingAction = true;
        await api.set_description(idleIdx, todo.description || todo.subject);
        await api.start_slot(idleIdx, todo.subject_id || null);
        _slots[idleIdx].pendingAction = false;
        refreshAll();
    }}
}}

// ═══ Records ═════════════════════════════════════════════
async function refreshRecords() {{
    const records = await api.get_records(_recordsFilter);
    renderRecords(records);
}}

function renderRecords(records) {{
    const tbody = document.getElementById('recordsBody');
    if (!tbody) return;
    tbody.innerHTML = records.map(r => `
        <tr data-id="${{r.id}}" data-subject="${{escapeAttr(r.subject_name)}}" data-desc="${{escapeAttr(r.description)}}"
            data-start="${{r.start}}" data-end="${{r.end}}" data-dur="${{r.duration}}" data-date="${{r.date}}"${{r.date === todayIso() ? ' ondblclick="fillRecordToSlot(' + r.id + ')" title="Double-click to load into timer"' : ''}}>
            <td class="records-date-col cell-date">${{r.date}}</td>
            <td class="cell-subj">${{escapeHTML(r.subject_name)}}</td>
            <td class="cell-desc">${{escapeHTML(r.description) || '—'}}</td>
            <td class="cell-start">${{r.start}}</td>
            <td class="cell-end">${{r.end}}</td>
            <td class="cell-dur">${{r.duration}}</td>
            <td><span class="records-actions">
                <span class="act" onclick="editRecord(this)">✎</span>
                <span class="act del" onclick="delRecord(this)">🗑</span>
            </span></td>
        </tr>
    `).join('');
}}

// Override prototype's setRecordsFilter
async function setRecordsFilter(filter) {{
    _recordsFilter = filter === 'Today' ? 'today' : filter === 'Week' ? 'week' : 'all';
    document.querySelectorAll('#page-records .filter-chips .chip').forEach(c => c.classList.remove('active'));
    const chips = document.querySelectorAll('#page-records .filter-chips .chip');
    chips.forEach(c => {{
        const t = c.textContent.trim();
        if ((filter === 'Today' && t.startsWith('Today')) ||
            (filter === 'Week' && t.startsWith('This Week')) ||
            (filter === 'Month' && t.startsWith('This Month')) ||
            (filter === 'All' && t === 'All')) c.classList.add('active');
    }});
    const dateField = document.getElementById('recordsDateField');
    if (dateField) {{
        dateField.style.display = (filter === 'Today') ? 'none' : '';
        if (filter === 'Today') dateField.value = new Date().toISOString().slice(0, 10);
    }}
    const scrollWrap = document.querySelector('#page-records .records-scroll-wrap');
    if (scrollWrap) {{
        if (filter === 'Today') scrollWrap.classList.remove('showing-dates');
        else scrollWrap.classList.add('showing-dates');
    }}
    refreshRecords();
}}
window.setRecordsFilter = setRecordsFilter;

async function delRecord(span) {{
    const tr = span.closest('tr');
    const id = parseInt(tr.dataset.id);
    if (id) await api.delete_record(id);
    refreshRecords();
}}

// ═══ Subjects ═══════════════════════════════════════════
async function addSubject() {{
    if (!api) return;
    const row = document.querySelector('#page-subjects .subject-row:first-child');
    const inp = row ? row.parentElement.previousElementSibling.querySelector('input') : null;
    if (!inp) return;
    const name = inp.value.trim();
    if (!name) return;
    await api.add_subject(name);
    inp.value = '';
    refreshSubjects();
}}
window.addSubject = addSubject;

async function refreshSubjects() {{
    _subjects = await api.get_subjects();
    renderSubjects(_subjects);
}}

function renderSubjects(subjects) {{
    const list = document.querySelector('#page-subjects .subjects-list');
    if (!list) return;
    const oldRows = list.querySelectorAll('.subject-row');
    oldRows.forEach(r => r.remove());
    subjects.forEach(s => {{
        const row = document.createElement('div');
        row.className = 'subject-row';
        row.innerHTML = `
            <span class="subject-dot" style="background:${{s.color}}"></span>
            <span class="subject-name">${{escapeHTML(s.name)}}</span>
            <span class="subject-actions">
                <span class="act" onclick="editSubject(this)">✎</span>
                <span class="act" onclick="delSubject(this)">🗑</span>
            </span>`;
        list.appendChild(row);
    }});
    updateSubjectsCount();
}}

function updateSubjectsCount() {{
    const n = document.querySelectorAll('#page-subjects .subjects-list .subject-row').length;
    const sub = document.querySelector('#page-subjects .page-sub');
    if (sub) sub.textContent = `${{n}} subjects — manage your activity categories`;
}}

async function delSubject(span) {{
    // Find subject ID by name
    const row = span.closest('.subject-row');
    const name = row.querySelector('.subject-name').textContent.trim();
    const subj = _subjects.find(s => s.name === name);
    if (subj) await api.delete_subject(subj.id);
    refreshSubjects();
}}

// ═══ Page switching ═════════════════════════════════════
function switchPage(name) {{
    document.querySelectorAll('.nav-item[data-page]').forEach(n => n.classList.remove('active'));
    document.querySelector(`.nav-item[data-page="${{name}}"]`).classList.add('active');
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
}}

document.querySelectorAll('.nav-item[data-page]').forEach(item => {{
    item.addEventListener('click', () => switchPage(item.dataset.page));
}});

// ═══ Theme toggle ═══════════════════════════════════════
const proto = document.getElementById('prototype');
const compactBtn = document.getElementById('compactBtn');
const expandBtn = document.getElementById('expandBtn');
const darkToggle = document.getElementById('darkToggle');

let isCompact = false, isDark = false, isMoss = false;
let clickCount = 0, clickTimer = null;

compactBtn.addEventListener('click', () => {{
    isCompact = true;
    proto.classList.add('showing-compact');
    document.querySelector('.sidebar').style.display = 'none';
    document.querySelector('.content').style.display = 'none';
    const cp = document.getElementById('compactPanel');
    cp.style.display = 'flex';
    cp.style.position = 'absolute';
    cp.style.top = '50%';
    cp.style.left = '50%';
    cp.style.transform = 'translate(-50%, -50%)';
    // Resize window to compact panel size
    if (api) api.resize_window(324, 620);
}});

expandBtn.addEventListener('click', () => {{
    isCompact = false;
    proto.classList.remove('showing-compact');
    document.querySelector('.sidebar').style.display = '';
    document.querySelector('.content').style.display = '';
    const cp = document.getElementById('compactPanel');
    cp.style.display = '';
    cp.style.position = '';
    cp.style.top = '';
    cp.style.left = '';
    cp.style.transform = '';
    // Restore full window size
    if (api) api.resize_window(760, 620);
}});

darkToggle.addEventListener('click', () => {{
    clickCount++;
    if (clickCount === 1) {{
        clickTimer = setTimeout(() => {{ clickCount = 0; }}, 2000);
    }}
    if (clickCount >= 8) {{
        clearTimeout(clickTimer);
        clickCount = 0;
        isMoss = !isMoss;
        const root = document.documentElement;
        if (isMoss) {{
            isDark = false;
            root.classList.remove('dark');
            root.classList.add('moss');
            darkToggle.innerHTML = `<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="#cc2200" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.341 6.484A10 10 0 0 1 10.266 21.85"/><path d="M3.659 17.516A10 10 0 0 1 13.74 2.152"/><circle cx="12" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="19" r="2"/></svg> EXIT MOSS`;
            darkToggle.style.color = '#cc2200';
            darkToggle.style.borderColor = '#cc2200';
        }} else {{
            root.classList.remove('moss');
            _updateDarkBtn();
            darkToggle.style.color = '';
            darkToggle.style.borderColor = '';
        }}
        return;
    }}
    if (isMoss) return;
    isDark = !isDark;
    if (isDark) {{
        document.documentElement.classList.add('dark');
    }} else {{
        document.documentElement.classList.remove('dark');
    }}
    _updateDarkBtn();
}});

function _updateDarkBtn() {{
    if (isDark) {{
        darkToggle.innerHTML = `<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg> Light`;
    }} else {{
        darkToggle.innerHTML = `<svg class="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 5h4"/><path d="M20 3v4"/><path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/></svg> Dark`;
    }}
}}

// ═══ Code of Timing modal ═══════════════════════════════
const modal = document.getElementById('easterEggModal');
const trigger = document.getElementById('easterEggTrigger');
trigger.addEventListener('click', () => modal.classList.add('show'));
modal.addEventListener('click', (e) => {{ if (e.target === modal) modal.classList.remove('show'); }});
document.addEventListener('keydown', (e) => {{ if (e.key === 'Escape' && modal.classList.contains('show')) modal.classList.remove('show'); }});

// ═══ Double-click record → timer ════════════════════════
function todayIso() {{
    return new Date().toISOString().slice(0, 10);
}}

async function fillRecordToSlot(id) {{
    if (!api) return;
    // Only today's records can be loaded into timer
    const todayRecs = await api.get_records('today');
    const record = todayRecs.find(r => Number(r.id) === Number(id));
    if (!record) return;
    let idleIdx = _slots.findIndex(s => s.status === 'idle');
    if (idleIdx < 0) {{
        const result = await api.add_slot();
        if (result.ok) {{
            await refreshSlots();
            idleIdx = _slots.findIndex(s => s.status === 'idle');
        }}
    }}
    if (idleIdx < 0) return;
    const subj = _subjects.find(s => s.name === record.subject_name);
    await api.set_resume_record(idleIdx, record.id);
    if (subj) await api.set_description(idleIdx, record.description || '');
    switchPage('timer');
    refreshAll();
}}

// ═══ Helpers ════════════════════════════════════════════
function escapeHTML(s) {{
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}
function escapeAttr(s) {{
    return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}}

// ═══ Records: inline edit (kept from prototype) ════════
function editRecord(span) {{
    const tr = span.closest('tr');
    if (tr.classList.contains('records-editing')) return;
    tr.classList.add('records-editing');
    tr.dataset.subject = tr.querySelector('.cell-subj').textContent;
    tr.dataset.desc = tr.querySelector('.cell-desc').textContent;
    tr.dataset.start = tr.querySelector('.cell-start').textContent;
    tr.dataset.end = tr.querySelector('.cell-end').textContent;
    tr.dataset.dur = tr.querySelector('.cell-dur').textContent;
    tr.dataset.date = tr.querySelector('.cell-date') ? tr.querySelector('.cell-date').textContent : '';

    const subjOpts = _subjects.map(s => `<option value="${{s.name}}">${{s.name}}</option>`).join('');
    tr.querySelector('.cell-subj').innerHTML = `<select>${{subjOpts}}</select>`;
    tr.querySelector('.cell-desc').innerHTML = `<input type="text" value="${{escapeAttr(tr.dataset.desc)}}">`;
    tr.querySelector('.cell-start').innerHTML = `<input type="text" value="${{tr.dataset.start}}">`;
    tr.querySelector('.cell-end').innerHTML = `<input type="text" value="${{tr.dataset.end}}">`;
    tr.querySelector('.cell-dur').textContent = tr.dataset.dur;
    const actionsTd = tr.querySelector('td:last-child');
    actionsTd.innerHTML = `<span class="edit-actions-inline"><span class="act save" onclick="saveRecordEdit(this)">✓</span><span class="act cancel" onclick="cancelEdit(this)">✕</span></span>`;
}}

async function saveRecordEdit(span) {{
    const tr = span.closest('tr');
    const id = parseInt(tr.dataset.id);
    const desc = tr.querySelector('.cell-desc input').value;
    const start = tr.querySelector('.cell-start input').value;
    const end = tr.querySelector('.cell-end input').value;
    const subjSelect = tr.querySelector('.cell-subj select');
    const subjName = subjSelect ? subjSelect.value : null;
    const subj = subjName ? _subjects.find(s => s.name === subjName) : null;
    if (id && api) {{
        const payload = {{description: desc, start_time: start, end_time: end}};
        if (subj) payload.subject_id = subj.id;
        await api.update_record(id, payload);
    }}
    refreshRecords();
}}

function cancelEdit(span) {{
    const tr = span.closest('tr');
    tr.querySelector('.cell-subj').textContent = tr.dataset.subject;
    tr.querySelector('.cell-desc').textContent = tr.dataset.desc;
    tr.querySelector('.cell-start').textContent = tr.dataset.start;
    tr.querySelector('.cell-end').textContent = tr.dataset.end;
    tr.querySelector('.cell-dur').textContent = tr.dataset.dur;
    const actionsTd = tr.querySelector('td:last-child');
    actionsTd.innerHTML = `<span class="records-actions"><span class="act" onclick="editRecord(this)">✎</span><span class="act del" onclick="delRecord(this)">🗑</span></span>`;
    tr.classList.remove('records-editing');
}}

// ═══ Subjects: inline edit (kept from prototype) ═══════
function editSubject(span) {{
    const row = span.closest('.subject-row');
    if (row.classList.contains('editing')) return;
    row.classList.add('editing');
    const nameEl = row.querySelector('.subject-name');
    const oldName = nameEl.textContent.trim();
    nameEl.innerHTML = `<input type="text" value="${{escapeAttr(oldName)}}" style="border:none;background:transparent;font-size:13px;color:var(--text);font-family:inherit;padding:2px 4px;border-bottom:1px solid var(--accent);outline:none;flex:1;">`;
    const actions = row.querySelector('.subject-actions');
    actions.innerHTML = `<span class="act save" onclick="saveSubject(this)">✓</span><span class="act cancel" onclick="cancelSubject(this)">✕</span>`;
}}

async function saveSubject(span) {{
    const row = span.closest('.subject-row');
    const input = row.querySelector('.subject-name input');
    if (!input) return;
    const newName = input.value.trim();
    const oldName = row.querySelector('.subject-name').textContent.trim() || row.dataset.oldName || '';
    if (newName && api) {{
        const subj = _subjects.find(s => s.name === oldName);
        if (subj) await api.update_subject(subj.id, newName, subj.color);
        refreshSubjects();
    }}
}}

function cancelSubject(span) {{
    const row = span.closest('.subject-row');
    restoreSubjectActions(row);
    row.classList.remove('editing');
}}

function restoreSubjectActions(row) {{
    const actions = row.querySelector('.subject-actions');
    actions.innerHTML = `<span class="act" onclick="editSubject(this)">✎</span><span class="act" onclick="delSubject(this)">🗑</span>`;
}}

// ═══ Records: manual add ═══════════════════════════════
let _addingRecord = false;
async function addRecord() {{
    if (!api) return;
    if (_addingRecord) return;
    const subjField = document.getElementById('recordsSubject');
    const subjName = subjField ? subjField.value : '';
    const subj = _subjects.find(s => s.name === subjName);
    if (!subj) {{ alert('Please select a subject first.'); return; }}
    _addingRecord = true;
    try {{
        const descField = document.getElementById('recordsDesc');
        const startField = document.getElementById('recordsStart');
        const endField = document.getElementById('recordsEnd');
        const desc = descField ? descField.value : '';
        const start = startField ? startField.value : '';
        const end = endField ? endField.value : '';
        await api.add_record(subj.id, desc, start, end);
        if (descField) descField.value = '';
        if (startField) startField.value = '';
        if (endField) endField.value = '';
        refreshRecords();
    }} finally {{
        _addingRecord = false;
    }}
}}

// ═══ Close button — minimize to tray (Windows) ═══
const closeBtn = document.getElementById('closeBtn');
if (closeBtn) {{
    closeBtn.addEventListener('click', async () => {{
        if (!api) return;
        await api.hide_window();
    }});
}}
</script>
</body>
</html>"""

with open("index.html", "w") as f:
    f.write(index)

print(f"Generated index.html ({len(index)} chars)")
