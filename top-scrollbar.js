/* top-scrollbar.js
 * Adds a second horizontal scroll bar ABOVE any wide, horizontally scrolling box (tables, box scores, line
 * scores, ...), kept in sync with the one below it. It finds these boxes on its own, including ones that are
 * drawn later by a page's own script, so any new scrolling table gets a top bar automatically -- no extra
 * markup needed. Just include <script src="top-scrollbar.js"></script> on the page.
 * Opt a box out with data-no-top-scroll. The bar only shows while the box is actually wider than its frame,
 * and is hidden on touch screens (where people swipe instead).
 */
(function () {
  if (window.__topScrollbarLoaded) return;
  window.__topScrollbarLoaded = true;

  var css = [
    '.tsb{display:none;overflow-x:auto;overflow-y:hidden;height:14px;margin-bottom:2px;box-sizing:content-box;scrollbar-width:thin;scrollbar-color:rgba(120,130,145,.6) rgba(128,128,128,.14)}',
    '.tsb>div{height:1px}',
    '.tsb::-webkit-scrollbar{height:14px}',
    '.tsb::-webkit-scrollbar-track{background:rgba(128,128,128,.14);border-radius:8px}',
    '.tsb::-webkit-scrollbar-thumb{background:rgba(120,130,145,.6);border-radius:8px;border:3px solid transparent;background-clip:padding-box}',
    '.tsb::-webkit-scrollbar-thumb:hover{background:rgba(120,130,145,.85);background-clip:padding-box}',
    '@media (hover:none){.tsb{display:none!important}}'
  ].join('\n');
  var st = document.createElement('style');
  st.setAttribute('data-top-scrollbar', '');
  st.textContent = css;
  document.head.appendChild(st);

  var tracked = new Map(); // scrolling box -> { bar, ghost }
  var timer = null;

  function isScrollBox(el) {
    if (el === document.body || el === document.documentElement) return false;
    if (el.classList && el.classList.contains('tsb')) return false;
    if (el.closest && el.closest('.tsb,[data-no-top-scroll]')) return false;
    var cs = getComputedStyle(el);
    if (cs.overflowX !== 'auto' && cs.overflowX !== 'scroll') return false;
    if (cs.position === 'absolute' || cs.position === 'fixed') return false;
    if (cs.display === 'none' || cs.display === 'inline') return false;
    var pcs = el.parentElement && getComputedStyle(el.parentElement);
    // A bar can't sit "above" a box that is laid out beside its siblings in a row.
    if (pcs && (pcs.display === 'flex' || pcs.display === 'inline-flex') && pcs.flexDirection.indexOf('row') === 0 && !(el.previousElementSibling && el.previousElementSibling.classList.contains('tsb'))) {
      if (el.parentElement.children.length > 1) return false;
    }
    if (pcs && (pcs.display === 'grid' || pcs.display === 'inline-grid')) return false;
    return true;
  }

  function attach(el) {
    var bar = document.createElement('div');
    bar.className = 'tsb';
    bar.setAttribute('aria-hidden', 'true');
    var ghost = document.createElement('div');
    bar.appendChild(ghost);
    el.parentNode.insertBefore(bar, el);
    var rec = { bar: bar, ghost: ghost, lock: false };
    bar.addEventListener('scroll', function () {
      if (rec.lock) { rec.lock = false; return; }
      if (el.scrollLeft !== bar.scrollLeft) { rec.lock = true; el.scrollLeft = bar.scrollLeft; }
    });
    el.addEventListener('scroll', function () {
      if (rec.lock) { rec.lock = false; return; }
      if (bar.scrollLeft !== el.scrollLeft) { rec.lock = true; bar.scrollLeft = el.scrollLeft; }
    });
    tracked.set(el, rec);
    return rec;
  }

  function update(el, rec) {
    var cs = getComputedStyle(el);
    var over = el.scrollWidth > el.clientWidth + 1 && el.clientWidth > 0;
    if (!over) { rec.bar.style.display = 'none'; return; }
    rec.bar.style.display = 'block';
    rec.bar.style.width = el.clientWidth + 'px';
    rec.bar.style.marginLeft = (parseFloat(cs.marginLeft) + parseFloat(cs.borderLeftWidth)) + 'px';
    rec.ghost.style.width = el.scrollWidth + 'px';
    if (rec.bar.scrollLeft !== el.scrollLeft) { rec.lock = true; rec.bar.scrollLeft = el.scrollLeft; }
  }

  function scan() {
    timer = null;
    // Drop boxes that have left the page (a page's script re-drew them).
    tracked.forEach(function (rec, el) {
      if (!document.body.contains(el)) { if (rec.bar.parentNode) rec.bar.parentNode.removeChild(rec.bar); tracked.delete(el); }
      else if (rec.bar.nextElementSibling !== el && el.parentNode) { el.parentNode.insertBefore(rec.bar, el); }
    });
    var all = document.body.getElementsByTagName('*');
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (tracked.has(el)) continue;
      if (el.scrollWidth <= el.clientWidth + 1 || el.clientWidth === 0) continue;
      if (!isScrollBox(el)) continue;
      attach(el);
    }
    tracked.forEach(function (rec, el) { update(el, rec); });
  }

  function schedule() { if (timer === null) timer = setTimeout(scan, 60); }

  function start() {
    scan();
    new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var t = muts[i].target;
        if (t && t.classList && t.classList.contains('tsb')) continue;
        schedule(); return;
      }
    }).observe(document.body, { childList: true, subtree: true });
    window.addEventListener('resize', schedule);
    window.addEventListener('load', schedule);
    if (window.ResizeObserver) new ResizeObserver(schedule).observe(document.body);
  }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();
