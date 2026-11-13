'use strict';
const $ = (id) => document.getElementById(id);
const dateParts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Bangkok', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
const part = (type) => dateParts.find((item) => item.type === type).value;
const today = `${part('year')}-${part('month')}-${part('day')}`;
let selectedDate = today;
let month = today.slice(0, 7);
let tasks = [];
let filter = 'all';
let loaded = false;
let accountReady = false;
let busy = false;
let requestNumber = 0;
let editingId = null;
let deletingTask = null;
let messageTimer;
const labels = { normal: 'ปกติ', high: 'สำคัญมาก', low: 'ไม่เร่งด่วน' };
const formatDate = (date, options) => new Intl.DateTimeFormat('th-TH', { timeZone: 'UTC', ...options }).format(new Date(date + 'T12:00:00Z'));

async function api(path, method = 'GET', data) {
  const options = { method, credentials: 'same-origin', signal: AbortSignal.timeout(15000) };
  if (data !== undefined) { options.headers = { 'Content-Type': 'application/json' }; options.body = JSON.stringify(data); }
  if (!['GET', 'HEAD'].includes(method)) {
    options.headers = { ...options.headers,
      'X-CSRFToken': document.cookie.split('; ').find((item) => item.startsWith('goodplanner_csrftoken='))?.split('=')[1] || ''
    };
  }
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error('เชื่อมต่อไม่สำเร็จ กรุณาตรวจว่าเซิร์ฟเวอร์เปิดอยู่แล้วลองอีกครั้ง'); }
  if (response.status === 401) {
    tasks = [];
    loaded = false;
    render();
    location.replace('/login.html');
    throw new Error('เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่');
  }
  let result;
  try { result = await response.json(); }
  catch { throw new Error('โหลดข้อมูลไม่สำเร็จ กรุณาลองอีกครั้ง'); }
  if (!response.ok) throw new Error(result.message || 'ไม่สามารถดำเนินการได้ กรุณาลองอีกครั้ง');
  return result;
}
function message(text, error = false) {
  $('status-text').textContent = text;
  $('status').classList.toggle('error', error);
  $('status').hidden = false;
  clearTimeout(messageTimer);
  if (!error) messageTimer = setTimeout(() => { $('status').hidden = true; }, 6000);
}
function controls() {
  for (const id of ['new-task', 'add-day-task', 'sidebar-new-task']) $(id).disabled = !accountReady || busy || !loaded;
  $('logout').disabled = !accountReady || busy;
  $('previous-month').disabled = month === '1900-01';
  $('next-month').disabled = month === '2100-12';
  document.querySelectorAll('.task-check, .edit-task, .delete-task').forEach((el) => { el.disabled = busy; });
}
function emptyState(title, description, symbol = '✓') {
  const element = document.createElement('div');
  element.className = 'empty-state';
  const icon = document.createElement('span'); icon.className = 'empty-icon'; icon.textContent = symbol; icon.setAttribute('aria-hidden', 'true');
  const heading = document.createElement('h3'); heading.textContent = title;
  const copy = document.createElement('p'); copy.textContent = description;
  element.append(icon, heading, copy);
  return element;
}
function render() {
  $('month-title').textContent = formatDate(month + '-01', { month: 'long', year: 'numeric' });
  $('selected-date-title').textContent = formatDate(selectedDate, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  $('jump-date').value = selectedDate;
  $('total-count').textContent = loaded ? tasks.length : '—';
  $('done-count').textContent = loaded ? tasks.filter((task) => task.completed).length : '—';
  $('pending-count').textContent = loaded ? tasks.filter((task) => !task.completed).length : '—';

  const [year, monthNumber] = month.split('-').map(Number);
  const start = new Date(Date.UTC(year, monthNumber - 1, 1)).getUTCDay();
  const days = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
  const cellCount = Math.ceil((start + days) / 7) * 7;
  const fragment = document.createDocumentFragment();
  for (let index = 0; index < cellCount; index++) {
    const day = index - start + 1;
    if (day < 1 || day > days) {
      const blank = document.createElement('div'); blank.className = 'day-blank'; blank.setAttribute('aria-hidden', 'true'); fragment.append(blank); continue;
    }
    const date = `${month}-${String(day).padStart(2, '0')}`;
    const dayTasks = tasks.filter((task) => task.date === date);
    const button = document.createElement('button'); button.type = 'button'; button.className = 'day-cell';
    button.dataset.date = date;
    button.classList.toggle('today', date === today);
    button.classList.toggle('selected', date === selectedDate);
    button.setAttribute('aria-pressed', String(date === selectedDate));
    if (date === today) button.setAttribute('aria-current', 'date');
    button.setAttribute('aria-label', formatDate(date, { day: 'numeric', month: 'long', year: 'numeric' }) + (date === today ? ' วันนี้' : '') + (loaded ? ` มี ${dayTasks.length} งาน` : ''));
    const number = document.createElement('span'); number.className = 'day-number'; number.textContent = day; button.append(number);
    if (dayTasks.length) {
      const count = document.createElement('span'); count.className = 'day-count'; count.textContent = `${dayTasks.length} งาน`; count.setAttribute('aria-hidden', 'true'); button.append(count);
    }
    for (const task of dayTasks.slice(0, 2)) {
      const preview = document.createElement('span'); preview.className = 'day-preview';
      preview.classList.toggle('high', task.priority === 'high'); preview.classList.toggle('done', task.completed);
      preview.textContent = task.title; preview.title = task.title; preview.setAttribute('aria-hidden', 'true'); button.append(preview);
    }
    if (dayTasks.length > 2) { const more = document.createElement('span'); more.className = 'more-tasks'; more.textContent = `+${dayTasks.length - 2} งาน`; more.setAttribute('aria-hidden', 'true'); button.append(more); }
    button.addEventListener('click', () => { selectedDate = date; render(); document.querySelector(`[data-date="${date}"]`).focus({ preventScroll: true }); });
    fragment.append(button);
  }
  $('calendar-days').replaceChildren(fragment);
  renderTasks();
  controls();
}
function renderTasks() {
  document.querySelectorAll('[data-filter]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
  const list = $('task-list');
  list.setAttribute('aria-busy', String(!loaded && $('load-error').hidden));
  const dayTasks = tasks.filter((task) => task.date === selectedDate);
  const done = dayTasks.filter((task) => task.completed).length;
  $('day-progress').max = Math.max(dayTasks.length, 1);
  $('day-progress').value = done;
  $('day-progress-label').textContent = loaded && dayTasks.length ? `${Math.round(done / dayTasks.length * 100)}%` : '';
  $('day-summary').textContent = loaded ? (dayTasks.length ? `${dayTasks.length} งาน · เสร็จแล้ว ${done} งาน` : 'พื้นที่ว่างสำหรับแผนดี ๆ ของคุณ') : ($('load-error').hidden ? 'กำลังโหลดงาน…' : 'ยังโหลดงานไม่สำเร็จ');
  $('add-day-task').textContent = selectedDate === today ? '＋ เพิ่มงานในวันนี้' : '＋ เพิ่มงานในวันที่เลือก';
  list.replaceChildren();
  if (!loaded) { list.append(emptyState($('load-error').hidden ? 'กำลังโหลดแผนของคุณ…' : 'โหลดแผนไม่สำเร็จ', $('load-error').hidden ? 'อีกสักครู่ก็พร้อมวางแผน' : 'กด “ลองอีกครั้ง” ด้านบนเพื่อโหลดใหม่', '◷')); return; }
  const visible = dayTasks.filter((task) => filter === 'all' || (filter === 'done' ? task.completed : !task.completed));
  if (!visible.length) {
    list.append(emptyState(filter === 'all' ? 'ยังไม่มีแผนในวันที่เลือก' : filter === 'done' ? 'ยังไม่มีงานที่เสร็จแล้ว' : 'ไม่มีงานค้างในวันที่เลือก', filter === 'all' ? 'เพิ่มงานแรก แล้วเริ่มต้นวันในแบบของคุณ' : filter === 'done' ? 'ทำเสร็จแล้ว กดเครื่องหมายหน้าชื่องานได้เลย' : 'พักสักนิด หรือวางแผนสิ่งต่อไปได้เลย'));
    return;
  }
  for (const task of visible) {
    const card = $('task-template').content.firstElementChild.cloneNode(true);
    card.classList.toggle('completed', task.completed);
    const check = card.querySelector('.task-check'); check.checked = task.completed;
    check.setAttribute('aria-label', `${task.completed ? 'ทำเครื่องหมายว่ายังไม่เสร็จ' : 'ทำเครื่องหมายว่าเสร็จแล้ว'}: ${task.title}`);
    check.addEventListener('change', () => { check.checked = task.completed; toggleTask(task); });
    card.querySelector('.task-title').textContent = task.title;
    card.querySelector('.task-notes').textContent = task.notes; card.querySelector('.task-notes').hidden = !task.notes;
    card.querySelector('.task-time').textContent = task.time ? `${task.time}${task.endTime ? '–' + task.endTime : ''} น.` : 'ไม่ระบุเวลา';
    const badge = card.querySelector('.priority-badge'); badge.textContent = labels[task.priority]; badge.classList.add(task.priority);
    const edit = card.querySelector('.edit-task'); edit.setAttribute('aria-label', 'แก้ไข ' + task.title); edit.addEventListener('click', () => openEditor(task));
    const remove = card.querySelector('.delete-task'); remove.setAttribute('aria-label', 'ลบ ' + task.title); remove.addEventListener('click', () => openDelete(task));
    if (task.readOnly) {
      check.remove(); edit.remove(); remove.remove();
      badge.textContent = task.kind;
      const link = document.createElement('a'); link.className = 'group-task-link';
      link.href = `/groups.html?group=${task.groupId}&tab=${task.kind === 'งานกลุ่ม' ? 'board' : 'free'}`;
      link.textContent = `ดูในกลุ่ม ${task.groupName} ↗`;
      card.querySelector('.task-actions').append(link);
    }
    list.append(card);
  }
}
async function loadMonth() {
  const request = ++requestNumber;
  tasks = []; loaded = false; $('load-error').hidden = true; render();
  try {
    const [result, shared] = await Promise.all([api('/api/tasks?month=' + encodeURIComponent(month)), api('/api/group-feed?month=' + encodeURIComponent(month))]);
    if (request !== requestNumber) return;
    tasks = [...result.tasks, ...shared.tasks].sort((a, b) => a.date.localeCompare(b.date) || Number(a.completed) - Number(b.completed) || (a.time || '99:99').localeCompare(b.time || '99:99')); loaded = true;
  } catch (error) {
    if (request !== requestNumber) return;
    $('load-error-text').textContent = error.message; $('load-error').hidden = false;
  }
  if (request === requestNumber) render();
}
function selectDate(date) {
  selectedDate = date;
  if (date.slice(0, 7) !== month) { month = date.slice(0, 7); loadMonth(); }
  else render();
}
function changeMonth(delta) {
  const [year, number] = month.split('-').map(Number);
  const next = new Date(Date.UTC(year, number - 1 + delta, 1)).toISOString().slice(0, 10);
  if (next < '1900-01-01' || next > '2100-12-31') return;
  selectDate(next);
}
function openEditor(task = null) {
  if (busy || !loaded) return;
  editingId = task?.id ?? null;
  $('task-form').reset(); $('task-error').hidden = true;
  $('task-dialog-title').textContent = task ? 'แก้ไขงาน' : 'เพิ่มงานใหม่';
  $('task-title').value = task?.title || '';
  $('task-date').value = task?.date || selectedDate;
  $('task-time').value = task?.time || '';
  $('task-end-time').value = task?.endTime || '';
  $('task-priority').value = task?.priority || 'normal';
  $('task-notes').value = task?.notes || '';
  $('task-dialog').showModal(); $('task-title').focus();
}
function editorBusy(value) {
  busy = value;
  for (const element of $('task-form').elements) element.disabled = value;
  $('close-task').disabled = value;
  $('save-task').textContent = value ? 'กำลังบันทึก…' : 'บันทึกงาน';
  controls();
}
$('task-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy) return;
  const data = { title: $('task-title').value.trim(), date: $('task-date').value, time: $('task-time').value, endTime: $('task-end-time').value, priority: $('task-priority').value, notes: $('task-notes').value.trim() };
  if (!data.title) { $('task-error').textContent = 'กรุณากรอกชื่องาน'; $('task-error').hidden = false; $('task-title').focus(); return; }
  $('task-error').hidden = true; editorBusy(true);
  try {
    const { task } = await api(editingId ? `/api/tasks/${editingId}` : '/api/tasks', editingId ? 'PATCH' : 'POST', data);
    $('task-dialog').close(); selectedDate = task.date; month = task.date.slice(0, 7);
    filter = 'all';
    message(editingId ? 'บันทึกการแก้ไขแล้ว' : 'เพิ่มงานและบันทึกแล้ว');
    await loadMonth();
  } catch (error) { $('task-error').textContent = error.message; $('task-error').hidden = false; }
  finally { editorBusy(false); }
});
async function toggleTask(task) {
  if (busy) return;
  busy = true; controls();
  try { await api(`/api/tasks/${task.id}`, 'PATCH', { completed: !task.completed }); message(task.completed ? 'เปลี่ยนเป็นงานที่ต้องทำแล้ว' : 'บันทึกว่างานเสร็จแล้ว'); await loadMonth(); }
  catch (error) { message(error.message, true); }
  finally { busy = false; controls(); }
}
function openDelete(task) {
  if (busy) return;
  deletingTask = task; $('delete-description').textContent = task.title; $('delete-error').hidden = true; $('delete-dialog').showModal();
}
$('confirm-delete').addEventListener('click', async () => {
  if (busy || !deletingTask) return;
  busy = true; controls(); $('confirm-delete').disabled = true; $('cancel-delete').disabled = true; $('delete-error').hidden = true;
  try { await api(`/api/tasks/${deletingTask.id}`, 'DELETE'); $('delete-dialog').close(); message('ลบงานแล้ว'); await loadMonth(); }
  catch (error) { $('delete-error').textContent = error.message; $('delete-error').hidden = false; }
  finally { busy = false; $('confirm-delete').disabled = false; $('cancel-delete').disabled = false; controls(); }
});
for (const id of ['close-task', 'cancel-task']) $(id).addEventListener('click', () => { if (!busy) $('task-dialog').close(); });
$('cancel-delete').addEventListener('click', () => { if (!busy) $('delete-dialog').close(); });
for (const id of ['task-dialog', 'delete-dialog']) $(id).addEventListener('cancel', (event) => { if (busy) event.preventDefault(); });
for (const id of ['new-task', 'add-day-task', 'sidebar-new-task']) $(id).addEventListener('click', () => openEditor());
$('previous-month').addEventListener('click', () => changeMonth(-1));
$('next-month').addEventListener('click', () => changeMonth(1));
$('go-today').addEventListener('click', () => selectDate(today));
$('jump-date').addEventListener('change', () => { if ($('jump-date').value && $('jump-date').validity.valid) selectDate($('jump-date').value); });
document.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => {
  filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
  renderTasks(); controls();
}));
$('logout').addEventListener('click', async () => {
  if (busy) return;
  busy = true; controls();
  try { await api('/api/logout', 'POST', {}); location.replace('/login.html'); }
  catch (error) { message(error.message, true); busy = false; controls(); }
});
function showEmailSetting(on) {
  const button = $('email-toggle');
  button.hidden = false;
  button.setAttribute('aria-pressed', String(on));
  button.textContent = on ? '✉ อีเมลเตือน: เปิด' : '✉ อีเมลเตือน: ปิด';
}
$('email-toggle').addEventListener('click', async () => {
  const on = $('email-toggle').getAttribute('aria-pressed') !== 'true';
  try {
    const { user } = await api('/api/me', 'PATCH', { emailReminders: on });
    showEmailSetting(user.emailReminders);
    message(user.emailReminders ? 'เปิดการแจ้งเตือนทางอีเมลแล้ว' : 'ปิดการแจ้งเตือนทางอีเมลแล้ว');
  } catch (error) { message(error.message, true); }
});
async function bootstrap() {
  if (location.protocol === 'file:') { location.replace('login.html'); return; }
  try {
    const { user } = await api('/api/me');
    $('account-name').textContent = user.displayName;
    $('avatar').textContent = Array.from(user.displayName)[0].toUpperCase();
    showEmailSetting(user.emailReminders);
    $('admin-link').hidden = !user.isAdmin;
    accountReady = true;
    await loadMonth();
  } catch (error) { $('load-error-text').textContent = error.message; $('load-error').hidden = false; render(); }
}
$('retry').addEventListener('click', () => accountReady ? loadMonth() : bootstrap());
$('dismiss-status').addEventListener('click', () => { clearTimeout(messageTimer); $('status').hidden = true; });
window.addEventListener('pageshow', (event) => { if (event.persisted) bootstrap(); });
$('workspace-today').textContent = formatDate(today, { day:'numeric', month:'short', year:'numeric' });
render();
bootstrap();
