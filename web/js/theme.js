/* Light and dark mode. Runs before paint so the page never flashes white. */
(function () {
  var KEY = 'goodplanner-theme';
  var root = document.documentElement;

  function stored() {
    try { return localStorage.getItem(KEY); } catch (error) { return null; }
  }

  function preferred() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function apply(mode) {
    root.setAttribute('data-theme', mode);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', mode === 'dark' ? '#10151c' : '#123b78');
    var buttons = document.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute('aria-pressed', mode === 'dark' ? 'true' : 'false');
      buttons[i].setAttribute('aria-label', mode === 'dark' ? 'เปลี่ยนเป็นโหมดสว่าง' : 'เปลี่ยนเป็นโหมดมืด');
      buttons[i].textContent = mode === 'dark' ? '☀' : '☾';
    }
  }

  apply(stored() || preferred());

  document.addEventListener('DOMContentLoaded', function () {
    apply(root.getAttribute('data-theme'));
    var buttons = document.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener('click', function () {
        var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem(KEY, next); } catch (error) { /* private window */ }
        apply(next);
      });
    }
  });

  // Follow the operating system until the user picks a side themselves.
  if (window.matchMedia) {
    var query = window.matchMedia('(prefers-color-scheme: dark)');
    var listen = query.addEventListener ? query.addEventListener.bind(query, 'change') : query.addListener.bind(query);
    listen(function (event) { if (!stored()) apply(event.matches ? 'dark' : 'light'); });
  }
})();
