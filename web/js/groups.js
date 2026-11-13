'use strict';
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char],
  );
const iconPaths = {
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  logout: '<path d="M9 4H4v16h5m6-12 4 4-4 4M8 12h11"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/>',
  team: '<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6m3 9v-2a6 6 0 0 0-2-4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  calendar:
    '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18m-13 5h2m4 0h2"/>',
  board: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16m6-16v16M6 8v4m6-4v7m6-7v3"/>',
  spark: '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H4v13h4"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  link: '<path d="m10 14 4-4m-6 6-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m4 0 2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 -1)"/>',
  folder: '<path d="M3 7V5a2 2 0 0 1 2-2h4l3 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true">${iconPaths[name] || iconPaths.folder}</svg>`;
document.querySelectorAll('[data-icon]').forEach((el) => {
  el.innerHTML = icon(el.dataset.icon);
});
const nowParts = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Bangkok',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).formatToParts(new Date());
const today = ['year', 'month', 'day'].map((type) => nowParts.find((p) => p.type === type).value).join('-');
const fmt = (day, options = { day: 'numeric', month: 'short', year: 'numeric' }) =>
  new Intl.DateTimeFormat('th-TH', { timeZone: 'UTC', ...options }).format(new Date(day + 'T00:00:00Z'));
const time = (value) =>
  `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
const minute = (value) => {
  const [h, m] = value.split(':').map(Number);
  return h * 60 + m;
};
let user,
  groups = [],
  group = null,
  availability = null,
  groupFilter = 'all',
  tab = 'info',
  selectedDay = today,
  calendarMonth = today.slice(0, 7),
  duration = '60',
  working = false,
  editingTask = null,
  confirmAction = null,
  generation = 0;
let notifications = [],
  deadlineTimer,
  closingAt = null,
  meetingConfirmation = null;
const durationText = (value) =>
  value % 60
    ? `${Math.floor(value / 60) ? Math.floor(value / 60) + ' ชม. ' : ''}${value % 60} นาที`
    : `${value / 60} ชั่วโมง`;
const deadlineText = (value) =>
  new Intl.DateTimeFormat('th-TH', {
    timeZone: 'Asia/Bangkok',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
const collecting = () => !!group?.availabilityDeadline && !group.availabilityClosed;
function renderPhase() {
  const deadline = group.availabilityDeadline;
  const chosen = !collecting() && group.meetings.length > 0;
  $('planning-phase').classList.toggle('closed', group.availabilityClosed);
  $('planning-phase').innerHTML =
    `<span class="phase-icon">${icon(collecting() ? 'clock' : chosen ? 'check' : 'calendar')}</span><div><strong>${chosen ? 'หัวหน้าเลือกวันนัดแล้ว' : deadline ? (collecting() ? 'กำลังรับเวลาไม่ว่างจากสมาชิก' : 'ปิดรับแล้ว · รอหัวหน้าเลือกวันและเวลา') : 'เลือกวันและเวลานัดของทีม'}</strong><p>${deadline ? `${collecting() ? 'ปิดรับวันที่' : 'ปิดรับเมื่อ'} ${deadlineText(deadline)} (เวลาไทย) · ` : ''}ทำงานครั้งละ ${durationText(group.durationMinutes)}${collecting() ? ' · เริ่มเลือกนัดได้หลังปิดรับ' : chosen ? ' · ดูรายละเอียดที่แท็บวันนัดของกลุ่ม' : ''}</p></div>`;
}
function watchDeadline() {
  clearTimeout(deadlineTimer);
  closingAt = collecting()
    ? Date.now() + Math.max(0, new Date(group.availabilityDeadline) - new Date(group.serverNow))
    : null;
  if (closingAt !== null)
    deadlineTimer = setTimeout(
      checkDeadline,
      Math.min(2147483647, Math.max(0, closingAt - Date.now()) + 100),
    );
}
async function checkDeadline() {
  if (!group || closingAt === null) return;
  if (Date.now() < closingAt) {
    deadlineTimer = setTimeout(checkDeadline, Math.min(2147483647, closingAt - Date.now() + 100));
    return;
  }
  if (working) {
    deadlineTimer = setTimeout(checkDeadline, 1000);
    return;
  }
  group.availabilityClosed = true;
  closingAt = null;
  if (tab === 'busy' || tab === 'info') tab = 'calendar';
  renderDetail();
  message('ปิดรับเวลาไม่ว่างแล้ว หัวหน้าสามารถเลือกวันและเวลานัดจากปฏิทินได้');
  await refresh();
}
const owner = () => group && group.ownerId === user.id;
const ownMember = () => group.members.find((m) => m.id === group.myMemberId);
const memberName = (id) => group.members.find((m) => m.id === id)?.name || 'สมาชิก';
const avatar = (m, i = 0) =>
  `<span class="member-avatar tone-${i % 4}" title="${esc(m.name)}">${esc(Array.from(m.name)[0] || '?')}</span>`;
const fieldError = (id, message) => {
  $(id).textContent = message || '';
  $(id).hidden = !message;
};

async function api(path, method = 'GET', data) {
  const options = { method, credentials: 'same-origin', signal: AbortSignal.timeout(20000), headers: {} };
  if (data !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(data);
  }
  if (method !== 'GET')
    options.headers['X-CSRFToken'] =
      document.cookie
        .split('; ')
        .find((v) => v.startsWith('goodplanner_csrftoken='))
        ?.split('=')[1] || '';
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error('เชื่อมต่อไม่สำเร็จ กรุณาตรวจสอบเซิร์ฟเวอร์แล้วลองอีกครั้ง');
  }
  if (response.status === 401) {
    location.href = '/login.html';
    throw new Error('กรุณาเข้าสู่ระบบใหม่');
  }
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.message || 'บันทึกไม่สำเร็จ กรุณาลองอีกครั้ง');
    error.details = result;
    throw error;
  }
  return result;
}
function message(text, error = false) {
  $('message').textContent = text;
  $('message').classList.toggle('error', error);
  $('message').hidden = false;
}
function setWorking(value) {
  working = value;
  document.querySelectorAll('button,input,select,textarea').forEach((el) => {
    if (value) {
      el.dataset.wasDisabled = el.disabled ? '1' : '0';
      el.disabled = true;
    } else if (el.dataset.wasDisabled !== undefined) {
      el.disabled = el.dataset.wasDisabled === '1';
      delete el.dataset.wasDisabled;
    }
  });
}
async function mutate(work, errorId, success) {
  if (working) return;
  if (errorId) fieldError(errorId, '');
  setWorking(true);
  try {
    await work();
    if (success) message(success);
  } catch (error) {
    if (errorId && $(errorId).closest('dialog')?.open) fieldError(errorId, error.message);
    else message(error.message, true);
  } finally {
    setWorking(false);
  }
}
function dateInput(id, value) {
  $(id).min = group.startDate;
  $(id).max = group.endDate;
  $(id).value = value;
}
function empty(text) {
  return `<div class="empty-inline">${esc(text)}</div>`;
}
const groupPath = (suffix) => `/api/groups/${group.id}${suffix}`;
function bind(id, event, fn) {
  $(id)?.addEventListener(event, fn);
}

function renderList() {
  $('group-count').textContent = groups.length;
  $('owned-count').textContent = groups.filter((g) => g.ownerId === user.id).length;
  $('joined-count').textContent = groups.filter((g) => g.ownerId !== user.id).length;
  $('completed-count').textContent = groups.reduce((sum, g) => sum + g.doneCount, 0);
  const query = $('group-search').value.trim().toLocaleLowerCase('th-TH');
  const filtered = groups.filter(
    (g) =>
      (groupFilter === 'all' || (groupFilter === 'owned' ? g.ownerId === user.id : g.ownerId !== user.id)) &&
      g.name.toLocaleLowerCase('th-TH').includes(query),
  );
  $('groups-grid').innerHTML = filtered.length
    ? filtered
        .map(
          (g) =>
            `<button class="group-card ${g.ownerId === user.id ? 'owned' : ''}" data-open-group="${g.id}" type="button" aria-label="เปิดกลุ่ม ${esc(g.name)}"><div class="card-top"><span class="group-symbol" aria-hidden="true">${icon('folder')}</span><span class="role-tag">${g.ownerId === user.id ? 'เจ้าของกลุ่ม' : 'สมาชิก'}</span></div><h2>${esc(g.name)}</h2><p class="card-period">${fmt(g.startDate)} — ${fmt(g.endDate)}</p><div class="card-progress"><p><span>ความคืบหน้าของทีม</span><span>${g.doneCount} / ${g.taskCount} งาน</span></p><progress aria-label="งานเสร็จ ${g.doneCount} จาก ${g.taskCount}" max="${g.taskCount || 1}" value="${g.doneCount}"></progress></div><div class="card-bottom"><span>${icon('team')} ${g.memberCount} สมาชิก</span><b>เปิดกลุ่ม ${icon('arrow')}</b></div></button>`,
        )
        .join('')
    : `<div class="empty-groups"><div class="empty-symbol" aria-hidden="true">${icon('team')}</div><h2>${groups.length ? 'ยังไม่มีกลุ่มในหมวดนี้' : 'ทุกทีมเริ่มต้นจากแผนแรก'}</h2><p class="subtle">สร้างพื้นที่เล็ก ๆ สำหรับทีมของคุณ<br>หรือใช้รหัสจากเพื่อน เพื่อเข้าร่วมกลุ่มที่มีอยู่แล้ว</p><button class="quiet-button" id="empty-create" type="button">＋ สร้างกลุ่มแรก</button></div>`;
  $('groups-grid')
    .querySelectorAll('[data-open-group]')
    .forEach((el) => el.addEventListener('click', () => openGroup(Number(el.dataset.openGroup))));
  bind('empty-create', 'click', openCreate);
  if (query && !filtered.length) {
    $('groups-grid').innerHTML =
      `<div class="empty-groups"><div class="empty-symbol" aria-hidden="true">${icon('search')}</div><h2>ไม่พบกลุ่มที่ค้นหา</h2><p class="subtle">ลองใช้ชื่ออื่น หรือเปลี่ยนตัวกรองกลุ่ม</p><button class="quiet-button" id="clear-group-search" type="button">ล้างคำค้นหา</button></div>`;
    bind('clear-group-search', 'click', () => {
      $('group-search').value = '';
      renderList();
      $('group-search').focus();
    });
  }
}
function renderInfo() {
  const done = group.tasks.filter((t) => t.status === 'done').length;
  const confirmed = group.members.filter((m) => m.confirmed).length;
  const progress = group.tasks.length ? Math.round((done / group.tasks.length) * 100) : 0;
  $('panel-info').innerHTML = `
    <div class="team-overview" aria-label="ภาพรวมของกลุ่ม">
      <div class="team-stat"><span class="stat-icon">${icon('team')}</span><div><span>สมาชิกในทีม</span><strong>${group.members.length}<small>คน</small></strong></div></div>
      <div class="team-stat"><span class="stat-icon amber">${icon('clock')}</span><div><span>ยืนยันเวลาว่างแล้ว</span><strong>${confirmed}<small>/ ${group.members.length} คน</small></strong></div></div>
      <div class="team-stat"><span class="stat-icon blue">${icon('check')}</span><div><span>งานที่เสร็จแล้ว</span><strong>${done}<small>/ ${group.tasks.length} งาน</small></strong></div><span class="stat-percent">${progress}%</span></div>
    </div>
    <div class="info-grid">
      <div class="info-main">
        <article class="panel-card members-card">
          <div class="panel-heading"><div><h2>สมาชิกในทีม</h2><p class="subtle">ทุกคนที่ร่วมวางแผนในพื้นที่นี้</p></div><span class="count-badge">${group.members.length} คน</span></div>
          <div class="member-list">${group.members.map((m, i) => `<div class="member-row">${avatar(m, i)}<div class="member-copy"><strong>${esc(m.name)}${m.id === group.myMemberId ? '<span class="you-tag">คุณ</span>' : ''}</strong><small>${m.userId === group.ownerId ? 'เจ้าของกลุ่ม' : 'สมาชิก'}</small></div><span class="status-chip ${m.confirmed ? 'ready' : ''}"><i></i>${m.confirmed ? 'ยืนยันเวลาแล้ว' : 'รอยืนยันเวลา'}</span></div>`).join('')}</div>
        </article>
        <section class="panel-card next-steps"><div class="panel-heading"><div><h2>เริ่มวางแผนด้วยกัน</h2><p class="subtle">พร้อมเมื่อไหร่ เลือกทำขั้นตอนต่อไปได้เลย</p></div></div>
          <button class="step-link" data-goto-tab="busy"><span class="step-number ${ownMember().confirmed ? 'complete' : ''}">${ownMember().confirmed ? icon('check') : '01'}</span><span><strong>บอกเวลาที่คุณไม่ว่าง</strong><small>${ownMember().confirmed ? 'คุณยืนยันเวลาแล้ว · กลับไปแก้ไขได้' : 'กรอกเวลาและยืนยัน เพื่อให้ทีมรู้ว่าคุณว่างตอนไหน'}</small></span>${icon('arrow')}</button>
          <button class="step-link" data-goto-tab="free"><span class="step-number">02</span><span><strong>วันนัดของกลุ่ม</strong><small>ดูวันปิดรับและวันนัดที่หัวหน้าเลือกให้ทีม</small></span>${icon('arrow')}</button>
          <button class="step-link" data-goto-tab="board"><span class="step-number">03</span><span><strong>แบ่งงานให้ชัดเจน</strong><small>ดูผู้รับผิดชอบและติดตามความคืบหน้าของงาน</small></span>${icon('arrow')}</button>
        </section>
      </div>
      <aside class="info-side">
        <section class="invite-card"><span class="invite-icon">${icon('link')}</span><span class="invite-eyebrow">ทำงานด้วยกันได้ดีกว่า</span><h2>ชวนเพื่อนเข้าทีม</h2><p>ส่งรหัสนี้ให้เพื่อน แล้วให้เพื่อนกรอก<br>ที่หน้าแผนงานกลุ่มหลังเข้าสู่ระบบ</p><div class="invite-box"><span>รหัสเข้าร่วมกลุ่ม</span><strong id="invite-code">${esc(group.inviteCode)}</strong></div><button class="copy-button" id="copy-code" type="button">${icon('copy')}คัดลอกรหัสเชิญ</button><p class="invite-note">แชร์รหัสเฉพาะคนในทีม · สูงสุด 50 คน</p></section>
        <section class="panel-card group-details"><h3>รายละเอียดการวางแผน</h3><div class="detail-facts"><div>${icon('clock')}<span>ช่วงเวลาที่สะดวกนัด</span><strong>${time(group.windowStart)}–${time(group.windowEnd)}</strong></div><div>${icon('calendar')}<span>นัดหมายในกลุ่ม</span><strong>${group.meetings.length} นัด</strong></div></div><p class="form-hint">เพื่อนต้องเข้าเว็บบนเซิร์ฟเวอร์เดียวกัน<br>จึงจะเห็นข้อมูลและวางแผนร่วมกันได้</p></section>
      </aside>
    </div>${owner() ? '<div class="delete-group-row"><button class="text-button danger-text" id="delete-group">ลบกลุ่มนี้</button></div>' : ''}`;
  $('panel-info')
    .querySelectorAll('[data-goto-tab]')
    .forEach((el) => el.addEventListener('click', () => selectTab(el.dataset.gotoTab)));
  bind('copy-code', 'click', async () => {
    try {
      await navigator.clipboard.writeText(group.inviteCode);
      message('คัดลอกรหัสกลุ่มแล้ว');
    } catch {
      message('คัดลอกอัตโนมัติไม่ได้ เลือกรหัสที่แสดงแล้วกด Ctrl+C', true);
    }
  });
  bind('delete-group', 'click', () =>
    askConfirm(
      'ลบกลุ่มนี้?',
      `กลุ่ม “${group.name}” พร้อมงาน นัดหมาย และเวลาไม่ว่างของสมาชิกในกลุ่มนี้จะถูกลบ`,
      async () => {
        await api(groupPath(''), 'DELETE');
        $('confirm-dialog').close();
        await showList();
      },
      'ลบกลุ่ม',
    ),
  );
}
function renderBusy() {
  const me = ownMember();
  const day = availability.days.find((d) => d.date === selectedDay);
  const slots = day?.busy.find((b) => b.memberId === me.id)?.slots || [];
  $('panel-busy').innerHTML =
    `<div class="busy-layout"><div class="panel-card"><h2>บอกเวลาที่คุณไม่ว่าง</h2><p class="subtle">กรอกให้ครบ แล้วกดยืนยันเวลาให้ทีมทราบ</p><form id="busy-form"><div class="field"><label for="busy-date">วันที่</label><input id="busy-date" type="date" min="${group.startDate}" max="${group.endDate}" value="${selectedDay}" required></div><label class="check-line"><input id="busy-all-day" type="checkbox">ไม่ว่างทั้งวัน</label><div class="form-row"><div class="field"><label for="busy-start">ตั้งแต่</label><input id="busy-start" type="time" value="09:00" required></div><div class="field"><label for="busy-end">ถึง</label><input id="busy-end" type="time" value="10:00" required></div></div><p class="form-error" id="busy-form-error" hidden role="alert"></p><button class="primary-button full-width" type="submit">＋ เพิ่มเวลาไม่ว่าง</button></form><div class="settings-block"><label class="check-line"><input id="share-personal" type="checkbox" ${me.sharePersonal ? 'checked' : ''}><span>นำเวลาจากแผนส่วนตัวมารวมด้วย</span></label><p class="form-hint">แชร์เฉพาะช่วงเวลา ชื่อและรายละเอียดงานยังเป็นส่วนตัว งานที่ไม่มีเวลาจบจะนับ 30 นาที ${group.availabilityDeadline ? 'นำเข้าข้อมูล ณ ตอนเปิดแชร์หรือยืนยันเวลา หากแผนส่วนตัวเปลี่ยนให้ยืนยันอีกครั้งก่อนปิดรับ' : ''}</p><button id="confirm-availability" class="quiet-button full-width" type="button">${me.confirmed ? 'ยกเลิกการยืนยันเวลา' : '✓ ยืนยันว่ากรอกเวลาครบแล้ว'}</button><p class="form-hint">ถ้าว่างทุกวัน ไม่ต้องเพิ่มช่วงเวลา กดยืนยันได้เลย</p></div></div><div class="panel-card"><div class="panel-heading"><div><p class="section-kicker">MY AVAILABILITY</p><h2>${fmt(selectedDay, { weekday: 'long', day: 'numeric', month: 'long' })}</h2></div><span class="status-chip ${me.confirmed ? 'ready' : ''}">${me.confirmed ? 'ยืนยันแล้ว' : 'ยังไม่ยืนยัน'}</span></div><div class="busy-list">${slots.length ? slots.map((s) => `<div class="busy-row"><time>${s.start === 0 && s.end === 1440 ? 'ทั้งวัน' : `${time(s.start)}–${time(s.end)}`}</time><span>${{ manual: 'เวลาที่คุณกรอก', personal: 'จากแผนส่วนตัว', meeting: 'นัดหมายกลุ่ม' }[s.source]}</span>${s.source === 'manual' ? `<button class="text-button danger-text" data-delete-slot="${s.id}" type="button">ลบช่วงเวลา</button>` : ''}</div>`).join('') : empty('ยังไม่มีช่วงไม่ว่างในวันนี้')}</div><p class="form-hint">เลือกวันด้านซ้ายเพื่อดูหรือเพิ่มเวลาในวันอื่น<br>นัดหมายกลุ่มจะนับเป็นเวลาไม่ว่างอัตโนมัติทุกกลุ่มที่คุณเข้าร่วม</p></div></div>`;
  if (group.availabilityClosed) {
    $('panel-busy').insertAdjacentHTML(
      'afterbegin',
      '<p class="availability-notice">ปิดรับแล้ว คุณดูเวลาที่ส่งไว้ได้ แต่เพิ่ม ลบ หรือเปลี่ยนการยืนยันไม่ได้</p>',
    );
    $('busy-form')
      .querySelectorAll('input:not(#busy-date),button')
      .forEach((el) => (el.disabled = true));
    $('panel-busy')
      .querySelectorAll('.settings-block input,.settings-block button,[data-delete-slot]')
      .forEach((el) => (el.disabled = true));
  }
  bind('busy-date', 'change', () => {
    const value = $('busy-date').value;
    if (value >= group.startDate && value <= group.endDate) {
      selectedDay = value;
      renderBusy();
    }
  });
  bind('busy-all-day', 'change', () => {
    ['busy-start', 'busy-end'].forEach((id) => ($(id).disabled = $('busy-all-day').checked));
  });
  bind('busy-form', 'submit', (event) => {
    event.preventDefault();
    const body = {
      date: $('busy-date').value,
      start: $('busy-all-day').checked ? 0 : minute($('busy-start').value),
      end: $('busy-all-day').checked ? 1440 : minute($('busy-end').value),
    };
    mutate(
      async () => {
        await api(groupPath('/busy'), 'POST', body);
        await reloadDetail();
      },
      'busy-form-error',
      'เพิ่มเวลาไม่ว่างแล้ว',
    );
  });
  bind('share-personal', 'change', () => {
    const value = $('share-personal').checked;
    mutate(
      async () => {
        try {
          await api(groupPath('/preferences'), 'PATCH', { sharePersonal: value });
        } catch (e) {
          $('share-personal').checked = !value;
          throw e;
        }
        await reloadDetail();
      },
      null,
      'บันทึกการแชร์ช่วงเวลาแล้ว',
    );
  });
  bind('confirm-availability', 'click', () =>
    mutate(
      async () => {
        await api(groupPath('/preferences'), 'PATCH', { confirmed: !me.confirmed });
        await reloadDetail();
      },
      null,
      me.confirmed ? 'ยกเลิกการยืนยันแล้ว' : 'ยืนยันเวลาแล้ว ทีมเห็นเวลาว่างของคุณได้แล้ว',
    ),
  );
  $('panel-busy')
    .querySelectorAll('[data-delete-slot]')
    .forEach((el) =>
      el.addEventListener('click', () =>
        mutate(
          async () => {
            await api(groupPath('/busy/' + el.dataset.deleteSlot), 'DELETE');
            await reloadDetail();
          },
          null,
          'ลบช่วงเวลาแล้ว',
        ),
      ),
    );
}
function renderCalendar() {
  const first = new Date(calendarMonth + '-01T00:00:00Z');
  const daysInMonth = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  let cells = Array.from({ length: first.getUTCDay() }, () => '<span></span>').join('');
  for (let n = 1; n <= daysInMonth; n++) {
    const day = `${calendarMonth}-${String(n).padStart(2, '0')}`;
    const stats = availability.days.find((d) => d.date === day),
      count = stats?.best?.count || 0,
      unsure = stats?.best?.unsureCount || 0;
    const busyPeople = stats?.busy.filter((b) => b.slots.length).length || 0;
    const slots = stats?.busy.flatMap((b) => b.slots).sort((a, b) => a.start - b.start) || [];
    const tone = !stats
      ? 'outside'
      : { 'all-free': 'all-free', maybe: 'maybe-free', none: 'none-free', 'no-window': 'none-free' }[
          stats.status
        ] || (busyPeople ? 'has-busy' : '');
    const note = !stats
      ? '—'
      : stats.status === 'all-free'
        ? 'ว่างแน่ทุกคน'
        : stats.status === 'maybe'
          ? `ไม่แน่ใจ ${unsure} คน`
          : stats.status === 'none'
            ? 'ไม่มีช่วงว่าง'
            : stats.status === 'no-window'
              ? 'ช่วงสั้นไป'
              : `ว่างแน่ ${count} คน`;
    cells += `<button class="group-day ${tone} ${day === selectedDay ? 'selected' : ''}" data-day="${day}" ${!stats ? 'disabled' : ''} aria-label="${fmt(day)} ว่างแน่ ${count} คน ไม่แน่ใจ ${unsure} คน ไม่ว่าง ${busyPeople} คน จากทั้งหมด ${group.members.length} คน"><strong>${n}</strong><small>${note}</small>${slots.length ? `<span class="day-time">${time(slots[0].start)}${slots.length > 1 ? ' +' : ''}</span>` : ''}</button>`;
  }
  const day = availability.days.find((d) => d.date === selectedDay);
  const dailyDetails = group.members
    .map((m) => {
      const slots = day?.busy.find((b) => b.memberId === m.id)?.slots || [];
      return `<div class="daily-member"><div>${avatar(m)}<strong>${esc(m.name)}</strong>${!m.confirmed ? '<span class="status-chip">ยังไม่ยืนยัน</span>' : ''}</div><p>${slots.length ? slots.map((slot) => `<span class="busy-period">${time(slot.start)}–${time(slot.end)}</span>`).join(' ') : m.confirmed ? 'ว่างแน่ ไม่ได้แจ้งช่วงไม่ว่าง' : 'ไม่แน่ใจ ยังไม่ยืนยันเวลา'}</p></div>`;
    })
    .join('');
  const timeline = group.members
    .map((m) => {
      const slots = day?.busy.find((b) => b.memberId === m.id)?.slots || [];
      return `<div class="timeline-row"><span class="timeline-name" title="${esc(m.name)}">${esc(m.name)}</span>${Array.from(
        { length: 24 },
        (_, i) => {
          const a = group.windowStart + ((group.windowEnd - group.windowStart) * i) / 24,
            b = group.windowStart + ((group.windowEnd - group.windowStart) * (i + 1)) / 24;
          const blocked = slots.some((s) => s.start < b && s.end > a);
          return `<span class="time-cell ${blocked ? 'blocked' : !m.confirmed ? 'unknown' : ''}" title="${esc(m.name)} ${time(Math.round(a))}–${time(Math.round(b))} ${blocked ? 'มีช่วงไม่ว่าง' : m.confirmed ? 'ว่างแน่' : 'ไม่แน่ใจ ยังไม่ยืนยัน'}"></span>`;
        },
      ).join('')}</div>`;
    })
    .join('');
  $('panel-calendar').innerHTML =
    `<div class="calendar-group-layout"><div class="panel-card"><div class="group-calendar-toolbar"><h2>${fmt(calendarMonth + '-01', { month: 'long', year: 'numeric' })}</h2><div><button class="arrow-button" id="group-prev-month" aria-label="เดือนก่อนหน้า" ${calendarMonth <= group.startDate.slice(0, 7) ? 'disabled' : ''}>‹</button><button class="arrow-button" id="group-next-month" aria-label="เดือนถัดไป" ${calendarMonth >= group.endDate.slice(0, 7) ? 'disabled' : ''}>›</button></div></div><div class="group-weekdays">${['อา.', 'จ.', 'อ.', 'พ.', 'พฤ.', 'ศ.', 'ส.'].map((d) => `<span>${d}</span>`).join('')}</div><div class="group-calendar-grid">${cells}</div><div class="calendar-legend"><span><i class="legend-dot"></i> ว่างแน่ทุกคน</span><span><i class="legend-dot maybe"></i> ไม่แน่ใจ ยังไม่ยืนยัน</span><span><i class="legend-dot busy"></i> มีคนไม่ว่าง</span><span>ทำงาน ${durationText(Number(duration))}</span></div><p class="calendar-note">กดวันที่เพื่อดูชื่อและช่วงเวลาไม่ว่างของแต่ละคน สีเหลืองหมายถึงยังรอยืนยัน ไม่ได้แปลว่าว่าง</p></div><div class="panel-card"><p class="section-kicker">TEAM TIMELINE</p><h2>${fmt(selectedDay, { day: 'numeric', month: 'long' })}</h2><p class="subtle">เห็นช่วงเวลาของทีมในวันเดียวกัน</p><div class="timeline-container">${timeline}<div class="timeline-axis"><span>${time(group.windowStart)}</span><span>${time(Math.round((group.windowStart + group.windowEnd) / 2))}</span><span>${time(group.windowEnd)}</span></div></div><div class="calendar-legend"><span><i class="legend-dot partial"></i> ว่าง</span><span><i class="legend-dot busy"></i> มีช่วงไม่ว่าง</span><span>สีเหลือง = ไม่แน่ใจ ยังไม่ยืนยัน</span></div><p class="calendar-note">ช่องเวลาที่มีช่วงไม่ว่างทับบางส่วนจะแสดงสีส้ม</p><h3 class="daily-heading">ช่วงเวลาไม่ว่างของแต่ละคน</h3><div class="daily-members">${dailyDetails}</div><div class="panel-heading meeting-list"><h2>นัดหมายวันนี้</h2>${owner() ? `<button id="calendar-meeting" class="primary-button" ${collecting() ? 'disabled' : ''}>${collecting() ? 'รอปิดรับเวลา' : '＋ เลือกนัดวันนี้'}</button>` : ''}</div>${meetingList(group.meetings.filter((m) => m.date === selectedDay))}</div></div>`;
  $('panel-calendar')
    .querySelectorAll('[data-day]')
    .forEach((el) =>
      el.addEventListener('click', () => {
        selectedDay = el.dataset.day;
        renderCalendar();
      }),
    );
  const move = (delta) => {
    const d = new Date(calendarMonth + '-01T00:00:00Z');
    d.setUTCMonth(d.getUTCMonth() + delta);
    calendarMonth = d.toISOString().slice(0, 7);
    selectedDay = calendarMonth + '-01';
    if (selectedDay < group.startDate) selectedDay = group.startDate;
    renderCalendar();
  };
  bind('group-prev-month', 'click', () => move(-1));
  bind('group-next-month', 'click', () => move(1));
  bind('calendar-meeting', 'click', () => openMeeting({ date: selectedDay }));
  bindMeetingDeletes('panel-calendar');
}
function meetingList(items) {
  return items.length
    ? items
        .map(
          (m) =>
            `<div class="meeting-item"><div><strong>${esc(m.title)}</strong><p>${fmt(m.date)} · ${time(m.start)}–${time(m.end)}<br>${m.participants.map((id) => esc(memberName(id))).join(', ')}</p>${m.acknowledgement?.acknowledgedAt ? '<small class="meeting-acknowledged">หัวหน้ายืนยันนัดหลังตรวจคำเตือนแล้ว</small>' : ''}</div>${owner() ? `<button class="text-button danger-text" data-delete-meeting="${m.id}" type="button">ยกเลิก</button>` : ''}</div>`,
        )
        .join('')
    : empty('ยังไม่มีนัดหมาย');
}
function bindMeetingDeletes(panel) {
  $(panel)
    .querySelectorAll('[data-delete-meeting]')
    .forEach((el) =>
      el.addEventListener('click', () => {
        const m = group.meetings.find((m) => m.id === Number(el.dataset.deleteMeeting));
        askConfirm(
          'ยกเลิกนัดหมาย?',
          `ยกเลิก “${m.title}” และนำออกจากแผนส่วนตัวของผู้เข้าร่วม`,
          async () => {
            await api(groupPath('/meetings/' + m.id), 'DELETE');
            $('confirm-dialog').close();
            await reloadDetail();
          },
          'ยกเลิกนัดหมาย',
        );
      }),
    );
}
function noSlotNotice() {
  const s = availability.summary;
  if (!s || s.reason === 'full') return '';
  const blockerText = s.blockers.length
    ? s.blockers.map((b) => `${esc(memberName(b.memberId))} (ติด ${b.blockedSlots} ช่วง)`).join(' · ')
    : '';
  if (s.reason === 'no-window')
    return `<div class="availability-notice schedule-notice warn"><span><strong>ยังหาเวลานัดไม่ได้</strong><br>การประชุมครั้งละ ${durationText(Number(duration))} ยาวเกินกรอบเวลานัดของกลุ่ม (${time(group.windowStart)}–${time(group.windowEnd)}) ลองลดความยาว หรือให้หัวหน้าขยายกรอบเวลา</span></div>`;
  if (s.reason === 'no-data')
    return `<div class="availability-notice schedule-notice"><span><strong>ยังไม่มีใครยืนยันเวลา</strong><br>ระบบจะสรุปวันว่างร่วมได้เมื่อมีสมาชิกกดยืนยันอย่างน้อยหนึ่งคน ตอนนี้ทุกคนอยู่ในสถานะไม่แน่ใจ</span></div>`;
  if (s.reason === 'conflict')
    return `<div class="availability-notice schedule-notice warn"><span><strong>ไม่มีวันที่ว่างตรงกันเลย</strong><br>ในช่วง ${fmt(group.startDate)} — ${fmt(group.endDate)} ไม่มีช่วง ${durationText(Number(duration))} ที่สมาชิกซึ่งยืนยันแล้วว่างพร้อมกันแม้แต่คนเดียว${blockerText ? `<br>คนที่ติดมากที่สุด: ${blockerText}` : ''}<br>ทางออก: ลดความยาวการประชุม ขยายกรอบเวลานัด ขยายช่วงวันที่ หรือคุยกับคนที่ติดมากที่สุดให้ขยับตาราง</span></div>`;
  return `<div class="availability-notice schedule-notice"><span><strong>ยังไม่มีวันที่ว่างครบทุกคน</strong><br>ดีที่สุดคือว่างแน่ ${s.bestCount} จาก ${s.memberCount} คน${s.confirmedCount < s.memberCount ? ` และยังไม่แน่ใจอีก ${s.memberCount - s.confirmedCount} คน` : ''}${blockerText ? `<br>คนที่ติดมากที่สุด: ${blockerText}` : ''}<br>เลือกวันที่คนว่างมากที่สุดจากปฏิทิน หรือขยายกรอบเวลานัด</span></div>`;
}
function renderFree() {
  const waiting = collecting(),
    chosen = group.meetings.length > 0;
  const heading = waiting
    ? 'กำลังรับเวลาไม่ว่างจากสมาชิก'
    : chosen
      ? 'หัวหน้าเลือกวันนัดแล้ว'
      : owner()
        ? 'เลือกวันและเวลานัดได้แล้ว'
        : 'รอหัวหน้าเลือกวันและเวลา';
  const description = waiting
    ? 'สมาชิกกรอกเวลาไม่ว่างได้จนถึงกำหนด แล้วหัวหน้าจะเลือกวันและเวลานัดให้ทีม'
    : chosen
      ? 'ตรวจสอบวัน เวลา และรายชื่อผู้เข้าร่วมด้านล่าง นัดจะแสดงในแผนส่วนตัวของผู้เข้าร่วมด้วย'
      : owner()
        ? 'ดูเวลาไม่ว่างของสมาชิกในปฏิทิน แล้วเลือกวันและเวลาที่ต้องการนัด'
        : 'เมื่อหัวหน้ายืนยันนัดแล้ว วันและเวลานัดจะแสดงที่นี่ให้ทุกคนเห็น';
  $('panel-free').innerHTML = `
    <div class="free-header"><div><p class="section-kicker">OUR NEXT MEETING</p><h2>วันนัดของกลุ่ม</h2><p class="subtle">นัดหมายในช่วง ${fmt(group.startDate)} — ${fmt(group.endDate)}</p></div><div class="duration-field">ทำงานครั้งละ <strong>${durationText(group.durationMinutes)}</strong></div></div>
    <section class="schedule-state ${waiting ? 'waiting' : chosen ? 'chosen' : 'ready'}" aria-labelledby="schedule-status-title">
      <div class="schedule-state-top"><span class="schedule-state-icon" aria-hidden="true">${icon(waiting ? 'clock' : chosen ? 'check' : 'calendar')}</span><div class="schedule-state-copy"><span class="schedule-label">${waiting ? 'รอถึงวันปิดรับ' : chosen ? 'ยืนยันนัดหมายแล้ว' : group.availabilityClosed ? 'ปิดรับเวลาไม่ว่างแล้ว' : 'หัวหน้าเป็นผู้เลือกนัด'}</span><h3 id="schedule-status-title">${heading}</h3><p>${description}</p></div></div>
      ${waiting ? `<div class="schedule-deadline"><span>ปิดรับวันที่</span><strong><time datetime="${esc(group.availabilityDeadline)}">${deadlineText(group.availabilityDeadline)}</time><small>เวลาไทย</small></strong><span>หลังจากนี้หัวหน้าจึงจะเลือกวันและเวลานัดได้</span></div>` : ''}
      <div class="schedule-actions">${owner() && !waiting ? `<button id="new-meeting" class="primary-button" type="button">${icon('plus')}${chosen ? 'เพิ่มนัดหมาย' : 'เลือกวันและเวลานัด'}</button>` : ''}${waiting ? '<button id="schedule-busy" class="primary-button" type="button">กรอกเวลาไม่ว่างของฉัน</button>' : ''}<button id="schedule-calendar" class="quiet-button" type="button">${icon('calendar')}ดูปฏิทินของทีม</button></div>
    </section>
    ${chosen ? `<div class="chosen-meetings" aria-label="นัดหมายที่หัวหน้าเลือก">${group.meetings.map((m) => `<article class="chosen-meeting"><div class="chosen-date"><span>${fmt(m.date, { weekday: 'long' })}</span><strong>${fmt(m.date, { day: 'numeric' })}</strong><span>${fmt(m.date, { month: 'short', year: 'numeric' })}</span></div><div class="chosen-meeting-copy"><p class="chosen-time">${icon('clock')}<time>${time(m.start)}–${time(m.end)}</time><span>${durationText(m.end - m.start)}</span></p><h3>${esc(m.title)}</h3><p class="chosen-participants">ผู้เข้าร่วม ${m.participants.length} คน · ${m.participants.map((id) => esc(memberName(id))).join(', ')}</p>${m.acknowledgement?.acknowledgedAt ? '<small class="meeting-acknowledged">หัวหน้ายืนยันนัดหลังตรวจคำเตือนแล้ว</small>' : ''}</div>${owner() ? `<button class="text-button danger-text" data-delete-meeting="${m.id}" type="button" aria-label="ยกเลิกนัด ${esc(m.title)}">ยกเลิกนัด</button>` : ''}</article>`).join('')}</div>` : ''}
    ${!chosen ? noSlotNotice() : ''}
    ${!chosen && availability.unconfirmed.length ? `<div class="availability-notice schedule-notice"><span>${waiting ? 'ยังไม่ยืนยันเวลา' : 'ไม่มีข้อมูลยืนยันเวลา'} ${availability.unconfirmed.length} คน: ${availability.unconfirmed.map((id) => esc(memberName(id))).join(', ')}<br>${waiting ? 'กรุณากรอกเวลาและยืนยันให้ครบก่อนปิดรับ' : 'หัวหน้าจะได้รับคำเตือนเมื่อนัดสมาชิกที่ยังไม่ยืนยันเวลา'}</span>${owner() && waiting ? '<button class="text-button" id="remind-members" type="button">ส่งเตือนในเว็บ</button>' : ''}</div>` : ''}`;
  bind('remind-members', 'click', () =>
    mutate(async () => {
      const r = await api(groupPath('/remind'), 'POST', {});
      message(r.message);
    }),
  );
  bind('new-meeting', 'click', () => openMeeting());
  bind('schedule-calendar', 'click', () => selectTab('calendar'));
  bind('schedule-busy', 'click', () => selectTab('busy'));
  bindMeetingDeletes('panel-free');
}
function renderBoard() {
  const statuses = { todo: 'รอเริ่ม', doing: 'กำลังทำ', done: 'เสร็จแล้ว' };
  $('panel-board').innerHTML =
    `<div class="board-toolbar"><div><h2>ทุกงานมีคนดูแล</h2><p class="subtle">${owner() ? 'มอบหมายงานให้ทีม แล้วติดตามความคืบหน้าได้ที่นี่' : 'เปลี่ยนสถานะงานที่คุณได้รับมอบหมายได้ที่การ์ดงาน'}</p></div>${owner() ? '<button class="primary-button" id="new-group-task">＋ มอบหมายงาน</button>' : ''}</div><div class="board">${Object.entries(
      statuses,
    )
      .map(([status, label]) => {
        const tasks = group.tasks.filter((t) => t.status === status);
        return `<section class="board-column ${status}"><h3><span class="column-dot"></span>${label}<span>${tasks.length}</span></h3>${
          tasks.length
            ? tasks
                .map((task) => {
                  const m = group.members.find((m) => m.id === task.assigneeId),
                    canEdit = owner() || task.assigneeId === group.myMemberId;
                  const overdue =
                    task.status !== 'done' &&
                    (task.date < today ||
                      (task.time && new Date(task.date + 'T' + task.time + ':00+07:00') < new Date()));
                  return `<article class="board-task"><h4>${esc(task.title)}</h4>${task.notes ? `<p>${esc(task.notes)}</p>` : ''}<span class="task-due ${overdue ? 'overdue' : ''}">${overdue ? 'เลยกำหนด · ' : ''}${fmt(task.date, { day: 'numeric', month: 'short' })}${task.time ? ' · ' + task.time : ''}</span><div class="board-task-footer">${avatar(m)}<span>${esc(m.name)}</span>${
                    canEdit
                      ? `<select aria-label="สถานะงาน ${esc(task.title)}" data-task-status="${task.id}">${Object.entries(
                          statuses,
                        )
                          .map(
                            ([v, l]) =>
                              `<option value="${v}" ${v === status ? 'selected' : ''}>${l}</option>`,
                          )
                          .join('')}</select>`
                      : ''
                  }</div>${owner() ? `<div class="task-owner-actions"><button class="text-button" data-edit-task="${task.id}">แก้ไข</button><button class="text-button danger-text" data-delete-task="${task.id}">ลบ</button></div>` : ''}</article>`;
                })
                .join('')
            : '<p class="board-empty">ยังไม่มีงานในขั้นตอนนี้</p>'
        }</section>`;
      })
      .join('')}</div>`;
  bind('new-group-task', 'click', () => openTask());
  $('panel-board')
    .querySelectorAll('[data-task-status]')
    .forEach((el) =>
      el.addEventListener('change', () => {
        const old = group.tasks.find((t) => t.id === Number(el.dataset.taskStatus)).status,
          value = el.value;
        mutate(
          async () => {
            try {
              await api(groupPath('/tasks/' + el.dataset.taskStatus), 'PATCH', { status: value });
            } catch (e) {
              el.value = old;
              throw e;
            }
            await reloadDetail();
          },
          null,
          'อัปเดตสถานะงานแล้ว',
        );
      }),
    );
  $('panel-board')
    .querySelectorAll('[data-edit-task]')
    .forEach((el) =>
      el.addEventListener('click', () =>
        openTask(group.tasks.find((t) => t.id === Number(el.dataset.editTask))),
      ),
    );
  $('panel-board')
    .querySelectorAll('[data-delete-task]')
    .forEach((el) =>
      el.addEventListener('click', () => {
        const task = group.tasks.find((t) => t.id === Number(el.dataset.deleteTask));
        askConfirm(
          'ลบงานนี้?',
          `ลบ “${task.title}” ออกจากกลุ่มและแผนส่วนตัวของผู้รับผิดชอบ`,
          async () => {
            await api(groupPath('/tasks/' + task.id), 'DELETE');
            $('confirm-dialog').close();
            await reloadDetail();
          },
          'ลบงาน',
        );
      }),
    );
}
function renderDetail() {
  $('group-name').textContent = group.name;
  $('group-role').textContent = owner()
    ? 'พื้นที่ของทีม · คุณเป็นเจ้าของกลุ่ม'
    : 'พื้นที่ของทีม · คุณเป็นสมาชิก';
  $('group-period').textContent =
    `${fmt(group.startDate)} — ${fmt(group.endDate)} · ${group.members.length} สมาชิก`;
  $('detail-avatars').innerHTML = group.members.slice(0, 6).map(avatar).join('');
  renderPhase();
  renderInfo();
  renderBusy();
  renderCalendar();
  renderFree();
  renderBoard();
  selectTab(tab);
}
function selectTab(value) {
  tab = value;
  document.querySelectorAll('[data-tab]').forEach((el) => {
    if (el.dataset.tab === value) el.setAttribute('aria-current', 'page');
    else el.removeAttribute('aria-current');
  });
  document.querySelectorAll('.tab-panel').forEach((el) => (el.hidden = el.id !== 'panel-' + value));
  if (group) history.replaceState(null, '', `/groups.html?group=${group.id}&tab=${tab}`);
}
async function reloadDetail() {
  if (!group) return;
  const id = group.id,
    stamp = ++generation;
  const [g, a] = await Promise.all([api(`/api/groups/${id}`), api(`/api/groups/${id}/availability`)]);
  if (stamp !== generation) return;
  group = g.group;
  availability = a;
  duration = String(group.durationMinutes);
  watchDeadline();
  if (selectedDay < group.startDate || selectedDay > group.endDate)
    selectedDay = today >= group.startDate && today <= group.endDate ? today : group.startDate;
  if (calendarMonth < group.startDate.slice(0, 7) || calendarMonth > group.endDate.slice(0, 7))
    calendarMonth = selectedDay.slice(0, 7);
  renderDetail();
  $('failure').hidden = true;
}
async function refreshNotifications() {
  const result = await api('/api/notifications');
  notifications = result.notifications;
  $('notification-count').textContent = result.unread;
  $('notification-count').hidden = !result.unread;
}
async function refresh() {
  $('failure').hidden = true;
  try {
    if (group) await reloadDetail();
    else {
      groups = (await api('/api/groups')).groups;
      renderList();
    }
    await refreshNotifications();
  } catch (error) {
    $('failure-text').textContent = error.message;
    $('failure').hidden = false;
  }
}
async function openGroup(id, requestedTab = null) {
  if (working) return;
  group = { id };
  tab = ['info', 'busy', 'calendar', 'free', 'board'].includes(requestedTab) ? requestedTab : 'info';
  calendarMonth = today.slice(0, 7);
  selectedDay = today;
  $('message').hidden = true;
  $('group-list-view').hidden = true;
  $('group-detail-view').hidden = true;
  try {
    await reloadDetail();
    if (group.availabilityClosed && !['info', 'busy', 'calendar', 'free', 'board'].includes(requestedTab))
      selectTab('calendar');
    $('group-detail-view').hidden = false;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (error) {
    group = null;
    history.replaceState(null, '', '/groups.html');
    $('group-list-view').hidden = false;
    await refresh();
    message(error.message, true);
  }
}
async function showList() {
  clearTimeout(deadlineTimer);
  closingAt = null;
  generation++;
  group = null;
  history.replaceState(null, '', '/groups.html');
  $('group-list-view').hidden = false;
  $('group-detail-view').hidden = true;
  await refresh();
}
function openCreate() {
  if (working) return;
  $('group-form').reset();
  const start = new Date(today + 'T00:00:00Z');
  start.setUTCDate(start.getUTCDate() + 1);
  $('group-start-date').value = start.toISOString().slice(0, 10);
  start.setUTCDate(start.getUTCDate() + 6);
  $('group-end-date').value = start.toISOString().slice(0, 10);
  $('group-deadline').value = today + 'T23:59';
  $('group-duration').value = '180';
  fieldError('group-form-error', '');
  $('group-dialog').showModal();
}
function openTask(task) {
  editingTask = task?.id || null;
  $('group-task-form').reset();
  $('group-task-dialog-title').textContent = task ? 'แก้ไขงานกลุ่ม' : 'มอบหมายงานใหม่';
  $('group-task-title').value = task?.title || '';
  $('group-task-notes').value = task?.notes || '';
  $('group-task-time').value = task?.time || '';
  $('group-task-assignee').innerHTML = group.members
    .map((m) => `<option value="${m.id}">${esc(m.name)}</option>`)
    .join('');
  $('group-task-assignee').value = task?.assigneeId || group.myMemberId;
  dateInput('group-task-date', task?.date || selectedDay);
  fieldError('group-task-form-error', '');
  $('group-task-dialog').showModal();
}
function meetingBody() {
  return {
    title: $('meeting-title').value,
    date: $('meeting-date').value,
    start: minute($('meeting-start').value),
    end: minute($('meeting-end').value),
    participants: Array.from($('meeting-participants').querySelectorAll('input:checked'), (el) =>
      Number(el.value),
    ),
  };
}
function showMeetingWarnings(conflicts, unconfirmed) {
  $('meeting-warning').hidden = !conflicts.length && !unconfirmed.length;
  $('meeting-warning').innerHTML =
    `${conflicts.length ? `<strong>เวลานัดทับกับสมาชิก ${conflicts.length} คน</strong><ul>${conflicts.map((m) => `<li><b>${esc(m.name)}</b> · ไม่ว่าง ${m.slots.map((slot) => `${time(slot.start)}–${time(slot.end)}`).join(', ')}</li>`).join('')}</ul>` : ''}${unconfirmed.length ? `<p>ยังไม่ยืนยันเวลา: ${unconfirmed.map((m) => esc(m.name)).join(', ')} — ยังสรุปไม่ได้ว่าคนเหล่านี้ว่าง</p>` : ''}<p>หัวหน้าสามารถเลือกเวลาอื่น หรือยืนยันนัดนี้หลังตรวจคำเตือน</p>`;
}
function updateMeetingPreview() {
  meetingConfirmation = null;
  $('meeting-ack').checked = false;
  $('meeting-ack-label').hidden = true;
  $('meeting-submit').textContent = 'ตรวจสอบและยืนยันนัด';
  if (group.availabilityDeadline) {
    const end = minute($('meeting-start').value) + group.durationMinutes;
    $('meeting-end').value = end <= 1440 ? time(end) : '';
  }
  const body = meetingBody(),
    day = availability.days.find((d) => d.date === body.date);
  const selected = group.members.filter((m) => body.participants.includes(m.id));
  const conflicts = selected
    .map((m) => ({
      ...m,
      slots: (day?.busy.find((b) => b.memberId === m.id)?.slots || []).filter(
        (slot) => slot.start < body.end && slot.end > body.start,
      ),
    }))
    .filter((m) => m.slots.length);
  showMeetingWarnings(
    conflicts,
    selected.filter((m) => !m.confirmed),
  );
}
function openMeeting(slot = {}) {
  if (!owner() || collecting()) return;
  $('meeting-form').reset();
  dateInput('meeting-date', slot.date || selectedDay);
  $('meeting-end').type = group.availabilityDeadline ? 'text' : 'time';
  $('meeting-start').min = time(group.windowStart);
  $('meeting-start').max = time(
    group.availabilityDeadline
      ? group.windowEnd - group.durationMinutes
      : Math.min(group.windowEnd - 1, 1439),
  );
  $('meeting-start').value = time(slot.start ?? group.windowStart);
  $('meeting-end').value = time((slot.start ?? group.windowStart) + group.durationMinutes);
  $('meeting-end').readOnly = !!group.availabilityDeadline;
  $('meeting-duration-note').textContent =
    `เวลาทำงาน ${durationText(group.durationMinutes)} · ${group.windowStart === 0 && group.windowEnd === 1440 ? 'เลือกเวลาเริ่มได้เอง และนัดจบภายในวันเดียวกัน' : `นัดได้ช่วง ${time(group.windowStart)}–${time(group.windowEnd)}`}`;
  // Include the entire team by default, including people who are busy.
  // The leader decides participants explicitly after seeing the warnings.
  $('meeting-participants').innerHTML = group.members
    .map(
      (m) =>
        `<label><input type="checkbox" name="participant" value="${m.id}" checked>${esc(m.name)}${!m.confirmed ? '<small>ยังไม่ยืนยันเวลา</small>' : ''}</label>`,
    )
    .join('');
  fieldError('meeting-form-error', '');
  updateMeetingPreview();
  $('meeting-dialog').showModal();
}

function askConfirm(title, description, fn, label) {
  $('confirm-title').textContent = title;
  $('confirm-description').textContent = description;
  $('confirm-action').textContent = label;
  confirmAction = fn;
  fieldError('confirm-error', '');
  $('confirm-dialog').showModal();
}

document
  .querySelectorAll('[data-close]')
  .forEach((el) => el.addEventListener('click', () => $(el.dataset.close).close()));
document.querySelectorAll('dialog').forEach((el) =>
  el.addEventListener('cancel', (event) => {
    if (working) event.preventDefault();
  }),
);
document.querySelectorAll('[data-tab]').forEach((el) =>
  el.addEventListener('click', () => {
    if (!working) {
      renderDetail();
      selectTab(el.dataset.tab);
    }
  }),
);
document.querySelectorAll('[data-group-filter]').forEach((el) =>
  el.addEventListener('click', () => {
    groupFilter = el.dataset.groupFilter;
    document
      .querySelectorAll('[data-group-filter]')
      .forEach((e) => e.setAttribute('aria-pressed', String(e === el)));
    renderList();
  }),
);
bind('create-group', 'click', openCreate);
bind('back-groups', 'click', showList);
bind('retry', 'click', () => (user ? refresh() : bootstrap()));
bind('refresh', 'click', refresh);
bind('refresh-detail', 'click', refresh);
bind('sidebar-create', 'click', openCreate);
bind('group-search', 'input', () => {
  if (user) renderList();
});
$('workspace-today').textContent = fmt(today, { day: 'numeric', month: 'short', year: 'numeric' });
bind('confirm-action', 'click', () => mutate(confirmAction, 'confirm-error', 'ทำรายการเรียบร้อยแล้ว'));
bind('group-form', 'submit', (event) => {
  event.preventDefault();
  const body = {
    name: $('new-group-name').value,
    startDate: $('group-start-date').value,
    endDate: $('group-end-date').value,
    durationMinutes: Number($('group-duration').value),
    availabilityDeadline: $('group-deadline').value + '+07:00',
  };
  mutate(
    async () => {
      const result = await api('/api/groups', 'POST', body);
      $('group-dialog').close();
      group = { id: result.group.id };
      tab = 'info';
      selectedDay = body.startDate;
      calendarMonth = selectedDay.slice(0, 7);
      await reloadDetail();
      $('group-list-view').hidden = true;
      $('group-detail-view').hidden = false;
    },
    'group-form-error',
    'สร้างกลุ่มแล้ว ส่งรหัสชวนเพื่อนมาเข้าร่วมได้เลย',
  );
});
bind('join-form', 'submit', (event) => {
  event.preventDefault();
  const code = $('join-code').value.trim();
  mutate(
    async () => {
      const result = await api('/api/groups/join', 'POST', { code });
      $('join-form').reset();
      group = { id: result.group.id };
      tab = result.group.availabilityClosed ? 'calendar' : 'busy';
      await reloadDetail();
      $('group-list-view').hidden = true;
      $('group-detail-view').hidden = false;
    },
    null,
    'เข้าร่วมกลุ่มแล้ว',
  );
});
bind('group-task-form', 'submit', (event) => {
  event.preventDefault();
  const body = {
    title: $('group-task-title').value,
    notes: $('group-task-notes').value,
    date: $('group-task-date').value,
    time: $('group-task-time').value,
    assigneeId: Number($('group-task-assignee').value),
  };
  mutate(
    async () => {
      await api(
        groupPath('/tasks' + (editingTask ? '/' + editingTask : '')),
        editingTask ? 'PATCH' : 'POST',
        body,
      );
      $('group-task-dialog').close();
      await reloadDetail();
    },
    'group-task-form-error',
    'บันทึกงานและเพิ่มในแผนส่วนตัวของผู้รับผิดชอบแล้ว',
  );
});
bind('meeting-form', 'input', (event) => {
  if (event.target.id !== 'meeting-ack') updateMeetingPreview();
});
bind('meeting-form', 'change', (event) => {
  if (event.target.id !== 'meeting-ack') updateMeetingPreview();
});
bind('meeting-form', 'submit', (event) => {
  event.preventDefault();
  if (meetingConfirmation && !$('meeting-ack').checked) {
    fieldError('meeting-form-error', 'กรุณาติ๊กยืนยันว่าได้ตรวจรายชื่อแล้ว หรือเปลี่ยนเวลานัด');
    return;
  }
  const body = meetingBody();
  if (meetingConfirmation) body.confirmationToken = meetingConfirmation;
  mutate(async () => {
    try {
      await api(groupPath('/meetings'), 'POST', body);
    } catch (error) {
      if (error.details?.code === 'meeting_conflict') {
        meetingConfirmation = error.details.confirmationToken;
        showMeetingWarnings(error.details.conflicts, error.details.unconfirmed);
        $('meeting-ack-label').hidden = false;
        $('meeting-ack').checked = false;
        $('meeting-submit').textContent = 'ยืนยันนัดตามคำเตือน';
        return;
      }
      throw error;
    }
    $('meeting-dialog').close();
    await reloadDetail();
    message('บันทึกนัดหมายและเพิ่มในแผนส่วนตัวของผู้เข้าร่วมแล้ว');
  }, 'meeting-form-error');
});
bind('notifications-button', 'click', () =>
  mutate(async () => {
    await refreshNotifications();
    $('notifications-list').innerHTML = notifications.length
      ? notifications
          .map(
            (n) =>
              `<a class="notification-item ${n.read ? '' : 'unread'}" href="/groups.html?group=${n.groupId}">${esc(n.message)}<time>${new Intl.DateTimeFormat('th-TH', { timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(n.createdAt))}</time></a>`,
          )
          .join('')
      : empty('ยังไม่มีการแจ้งเตือนใหม่');
    $('notifications-dialog').showModal();
  }),
);
bind('read-notifications', 'click', () =>
  mutate(
    async () => {
      await api('/api/notifications', 'PATCH', {});
      await refreshNotifications();
      $('notifications-list')
        .querySelectorAll('.unread')
        .forEach((el) => el.classList.remove('unread'));
    },
    null,
    'ทำเครื่องหมายว่าอ่านแล้ว',
  ),
);
bind('logout', 'click', () =>
  mutate(async () => {
    await api('/api/logout', 'POST', {});
    location.href = '/login.html';
  }),
);
async function bootstrap() {
  try {
    user = (await api('/api/me')).user;
    $('account-name').textContent = user.displayName;
    $('avatar').textContent = Array.from(user.displayName)[0] || 'G';
    groups = (await api('/api/groups')).groups;
    renderList();
    await refreshNotifications();
    const query = new URLSearchParams(location.search),
      id = Number(query.get('group'));
    if (Number.isSafeInteger(id) && id > 0) await openGroup(id, query.get('tab'));
  } catch (error) {
    $('failure-text').textContent = error.message;
    $('failure').hidden = false;
  }
}
// Reload only on returning to this page, so unsaved form fields are preserved.
document.addEventListener('visibilitychange', () => {
  if (
    !document.hidden &&
    user &&
    !working &&
    !document.querySelector('dialog[open]') &&
    !['busy'].includes(tab)
  )
    refresh();
});
window.addEventListener('pageshow', (event) => {
  if (event.persisted) location.reload();
});
bootstrap();
