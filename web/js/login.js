'use strict';
const form = document.querySelector('form[data-mode]');
const registering = form.dataset.mode === 'register';
const email = document.getElementById('email');
const password = document.getElementById('password');
const notice = document.getElementById('notice');
const submit = form.querySelector('[type="submit"]');
const inputs = [...form.querySelectorAll('input')];

function setError(input, message) {
  document.getElementById(input.id + '-error').textContent = message;
  if (message) input.setAttribute('aria-invalid', 'true');
  else input.removeAttribute('aria-invalid');
}
function showNotice(message, error = false) {
  notice.textContent = message;
  notice.classList.toggle('notice-error', error);
  notice.hidden = false;
  notice.focus();
}
for (const toggle of document.querySelectorAll('[data-password], #toggle-password')) {
  toggle.addEventListener('click', () => {
    const input = document.getElementById(toggle.dataset.password || 'password');
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    toggle.setAttribute('aria-pressed', String(visible));
    toggle.setAttribute('aria-label', visible ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน');
    if (toggle.dataset.password) toggle.textContent = visible ? 'ซ่อน' : 'แสดง';
  });
}
for (const input of inputs) {
  input.addEventListener('input', () => { setError(input, ''); notice.hidden = true; });
}
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (submit.disabled) return;
  notice.hidden = true;
  if (location.protocol === 'file:') {
    showNotice('กรุณาเปิดเซิร์ฟเวอร์ด้วย start.cmd แล้วเข้า http://localhost:3000 เพื่อใช้งานระบบบัญชี', true);
    return;
  }
  inputs.forEach((input) => setError(input, ''));
  email.value = email.value.trim();
  const errors = new Map();
  if (!email.value) errors.set(email, 'กรุณากรอกอีเมล');
  else if (email.value.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) errors.set(email, 'กรุณากรอกอีเมลให้ถูกต้อง เช่น you@example.com');
  if (!password.value) errors.set(password, 'กรุณากรอกรหัสผ่าน');
  else if (password.value.length > 128) errors.set(password, 'รหัสผ่านต้องไม่เกิน 128 ตัวอักษร');
  const payload = { email: email.value, password: password.value };
  if (registering) {
    const name = document.getElementById('displayName');
    const confirm = document.getElementById('confirmPassword');
    if (!name.value.trim() || name.value.trim().length > 80) errors.set(name, 'กรุณากรอกชื่อที่แสดง 1–80 ตัวอักษร');
    if (password.value.length < 8) errors.set(password, 'รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร');
    if (!confirm.value || confirm.value !== password.value) errors.set(confirm, 'รหัสผ่านทั้งสองช่องต้องตรงกัน');
    payload.displayName = name.value.trim();
    payload.confirmPassword = confirm.value;
  }
  if (errors.size) {
    errors.forEach((message, input) => setError(input, message));
    inputs.find((input) => errors.has(input)).focus();
    return;
  }
  const originalLabel = submit.textContent;
  submit.disabled = true;
  submit.textContent = registering ? 'กำลังสมัครสมาชิก…' : 'กำลังเข้าสู่ระบบ…';
  form.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(registering ? '/api/register' : '/api/login', {
      method: 'POST', headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.cookie.split('; ').find((item) => item.startsWith('goodplanner_csrftoken='))?.split('=')[1] || ''
      },
      credentials: 'same-origin', body: JSON.stringify(payload), signal: AbortSignal.timeout(15000)
    });
    const result = await response.json();
    if (!response.ok) { showNotice(result.message || 'ไม่สามารถดำเนินการได้ กรุณาลองอีกครั้ง', true); return; }
    form.reset();
    location.assign(registering ? '/login.html?registered=1' : '/dashboard.html');
  } catch {
    showNotice('เชื่อมต่อไม่สำเร็จ กรุณาตรวจว่าเซิร์ฟเวอร์เปิดอยู่แล้วลองอีกครั้ง', true);
  } finally {
    submit.disabled = false;
    submit.textContent = originalLabel;
    form.removeAttribute('aria-busy');
  }
});
document.getElementById('forgot-password')?.addEventListener('click', () => {
  showNotice('ระบบนี้ยังไม่รองรับการส่งอีเมลรีเซ็ตรหัสผ่าน');
});
document.getElementById('google-login')?.addEventListener('click', () => {
  if (location.protocol === 'file:') {
    showNotice('กรุณาเปิดเซิร์ฟเวอร์ด้วย start.cmd ก่อนเข้าสู่ระบบด้วย Google', true);
    return;
  }
  location.assign('/auth/google');
});
if (location.protocol === 'file:') {
  showNotice('เปิด start.cmd ในโฟลเดอร์นี้ แล้วเข้า http://localhost:3000 เพื่อสมัครสมาชิกและเข้าสู่ระบบ');
} else {
  if (!registering && new URLSearchParams(location.search).has('registered')) {
    showNotice('สมัครสมาชิกสำเร็จแล้ว เข้าสู่ระบบด้วยอีเมลและรหัสผ่านที่คุณตั้งไว้ได้เลย');
    history.replaceState(null, '', '/login.html');
  }
  const googleError = new URLSearchParams(location.search).get('google_error');
  if (googleError) {
    const messages = {
      configuration: 'การเข้าสู่ระบบด้วย Google ยังไม่ได้ตั้งค่า Client ID และ Client Secret',
      cancelled: 'คุณยกเลิกการเข้าสู่ระบบด้วย Google',
      invalid: 'ไม่สามารถยืนยันคำขอเข้าสู่ระบบด้วย Google ได้ กรุณาลองอีกครั้ง',
      provider: 'Google เข้าสู่ระบบไม่สำเร็จ กรุณาลองอีกครั้ง'
    };
    showNotice(messages[googleError] || messages.provider, true);
    const cleanUrl = new URL(location.href);
    cleanUrl.searchParams.delete('google_error');
    history.replaceState(null, '', cleanUrl.pathname + cleanUrl.search + cleanUrl.hash);
  }
  fetch('/api/me', { credentials: 'same-origin' })
    .then((response) => { if (response.ok) location.replace('/dashboard.html'); }).catch(() => {});
}
