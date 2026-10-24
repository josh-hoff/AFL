/* Site-wide player search. Included on every page; puts a search box on the right side of the
   Schedule / Standings / Rosters bar. It searches every season in data/seasons.json and opens
   player.html?id=<id>&season=<year>. Rosters load the first time the box is used. */
(function () {
  var nav = document.querySelector('nav.nav-tabs');
  if (!nav || nav.dataset.searchReady) return;
  nav.dataset.searchReady = '1';

  // ---------- styles ----------
  var css = '\n' +
    '.nav-tabs.has-search{display:grid;grid-template-columns:1fr auto 1fr;column-gap:1rem;align-items:stretch;justify-content:normal;}\n' +
    '.nav-tabs.has-search .nav-links{grid-column:2;display:flex;justify-content:center;gap:2rem;align-self:end;}\n' +
    '.nav-tabs.has-search .ps-wrap{grid-column:3;justify-self:end;align-self:center;padding:0.3rem 0;width:min(260px,100%);transition:width .15s;}\n' +
    '.nav-tabs.has-search .ps-wrap:focus-within{width:min(340px,100%);}\n' +
    '.ps-box{position:relative;}\n' +
    '.ps-box svg{position:absolute;left:.75rem;top:50%;transform:translateY(-50%);width:15px;height:15px;color:var(--text-muted,#5a6472);pointer-events:none;}\n' +
    '.ps-input{width:100%;box-sizing:border-box;border:1px solid var(--border,#e8e6e2);background:var(--bg-card,#fff);color:var(--text,#111418);border-radius:999px;padding:.42rem 2rem .42rem 2.2rem;font-size:.88rem;font-family:inherit;}\n' +
    '.ps-input:focus{outline:2px solid var(--tab-active,#f26522);outline-offset:1px;border-color:transparent;}\n' +
    '.ps-clear{position:absolute;right:.4rem;top:50%;transform:translateY(-50%);border:0;background:none;color:var(--text-muted,#5a6472);font-size:1.1rem;line-height:1;cursor:pointer;padding:.15rem .4rem;border-radius:6px;display:none;}\n' +
    '.ps-box.has .ps-clear{display:block;}\n' +
    '.ps-list{position:absolute;right:0;top:calc(100% + 8px);width:min(500px,calc(100vw - 32px));background:var(--bg-card,#fff);border:1px solid var(--border,#e8e6e2);border-radius:12px;box-shadow:0 12px 32px rgba(13,27,58,.18);z-index:200;overflow:hidden;display:none;max-height:min(70vh,470px);overflow-y:auto;text-align:left;}\n' +
    '.ps-list.open{display:block;}\n' +
    '.ps-it{display:flex;align-items:center;gap:.7rem;padding:.5rem .8rem;cursor:pointer;border-top:1px solid var(--border,#e8e6e2);color:var(--text,#111418);}\n' +
    '.ps-it:first-child{border-top:0;}\n' +
    '.ps-it.act{background:#fff3ea;}\n' +
    '.ps-it.t{box-shadow:inset 4px 0 0 var(--tab-active,#f26522);}\n' +
    '.ps-it.m:not(.t){box-shadow:inset 4px 0 0 #2f6fb0;}\n' +
    '.ps-av{width:38px;height:38px;border-radius:50%;background:#2b2b2b;position:relative;flex-shrink:0;}\n' +
    '.ps-av img.ps-ph{width:100%;height:100%;border-radius:50%;object-fit:cover;object-position:center 30%;display:block;}\n' +
    '.ps-av img.ps-org{position:absolute;right:-3px;bottom:-3px;width:17px;height:17px;border-radius:50%;background:#fff;border:1.5px solid #fff;box-shadow:0 1px 2px rgba(0,0,0,.25);object-fit:contain;padding:1px;}\n' +
    '.ps-tx{min-width:0;flex:1;}\n' +
    '.ps-nm{font-weight:600;font-size:.92rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}\n' +
    '.ps-nm mark{background:none;color:var(--tab-active,#f26522);font-weight:800;}\n' +
    '.ps-sub{font-size:.74rem;color:var(--text-muted,#5a6472);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}\n' +
    '.ps-tag{display:inline-block;font-size:.58rem;font-weight:800;padding:0 6px;border-radius:9px;background:var(--tab-active,#f26522);color:#fff;margin-left:6px;vertical-align:1px;}\n' +
    '.ps-pos{font-size:.7rem;font-weight:700;color:var(--text-muted,#5a6472);border:1px solid var(--border,#e8e6e2);border-radius:6px;padding:0 6px;flex-shrink:0;}\n' +
    '.ps-yrs{display:flex;gap:.3rem;flex-shrink:0;}\n' +
    '.ps-yr{font-size:.72rem;font-weight:700;color:var(--text-muted,#5a6472);border:1px solid var(--border,#e8e6e2);border-radius:999px;padding:.05rem .55rem;text-decoration:none;background:var(--bg-card,#fff);}\n' +
    '.ps-yr:first-child{color:var(--tab-active,#f26522);border-color:var(--tab-active,#f26522);}\n' +
    '.ps-yr:hover{background:var(--tab-active,#f26522);border-color:var(--tab-active,#f26522);color:#fff;}\n' +
    '.ps-none{padding:.9rem 1rem;color:var(--text-muted,#5a6472);font-size:.88rem;}\n' +
    '.ps-foot{display:flex;gap:1rem;justify-content:flex-end;flex-wrap:wrap;padding:.4rem .8rem;font-size:.68rem;color:var(--text-muted,#5a6472);background:#f2f1ee;border-top:1px solid var(--border,#e8e6e2);}\n' +
    '.ps-foot kbd{font-family:inherit;font-size:.65rem;border:1px solid var(--border,#e8e6e2);border-radius:4px;padding:0 4px;background:#fff;}\n' +
    '@media (max-width:760px){.nav-tabs.has-search{grid-template-columns:1fr;row-gap:.2rem;}.nav-tabs.has-search .nav-links{grid-column:1;}.nav-tabs.has-search .ps-wrap,.nav-tabs.has-search .ps-wrap:focus-within{grid-column:1;justify-self:stretch;width:auto;padding-bottom:.6rem;}.ps-list{left:0;right:0;width:auto;}}\n';
  var st = document.createElement('style');
  st.textContent = css;
  document.head.appendChild(st);

  // ---------- markup ----------
  var links = document.createElement('div');
  links.className = 'nav-links';
  while (nav.firstChild) links.appendChild(nav.firstChild);
  nav.appendChild(links);
  nav.classList.add('has-search');

  var wrap = document.createElement('div');
  wrap.className = 'ps-wrap';
  wrap.innerHTML =
    '<div class="ps-box">' +
    '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M13 13l4 4"/></svg>' +
    '<input class="ps-input" type="text" autocomplete="off" spellcheck="false" placeholder="Search players" aria-label="Search players" role="combobox" aria-expanded="false" aria-autocomplete="list">' +
    '<button class="ps-clear" type="button" aria-label="Clear search">&times;</button>' +
    '<div class="ps-list" role="listbox"></div>' +
    '</div>';
  nav.appendChild(wrap);
  var box = wrap.querySelector('.ps-box'), input = wrap.querySelector('.ps-input'),
      list = wrap.querySelector('.ps-list'), clr = wrap.querySelector('.ps-clear');

  // ---------- data ----------
  var players = null, loading = null, res = [], act = -1, words = '';
  function parseLine(line) {
    var out = [], cur = '', q = false;
    for (var i = 0; i < line.length; i++) {
      var c = line[i];
      if (c === '"') { if (q && line[i + 1] === '"') { cur += '"'; i++; } else q = !q; }
      else if (c === ',' && !q) { out.push(cur); cur = ''; }
      else cur += c;
    }
    out.push(cur);
    return out;
  }
  function parseCSV(text) {
    var lines = text.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    var h = parseLine(lines[0]);
    return lines.slice(1).map(function (l) {
      var v = parseLine(l), r = {};
      h.forEach(function (k, i) { r[k] = v[i] !== undefined ? v[i] : ''; });
      return r;
    });
  }
  function top100Rank(row) {
    var cur = null;
    Object.keys(row).filter(function (k) { return /^\d{4}-\d{2}-\d{2}$/.test(k); }).sort().forEach(function (d) {
      var v = parseInt(row[d], 10); if (!isNaN(v)) cur = v;
    });
    if (cur === null && row.rank) cur = parseInt(row.rank, 10);
    return isNaN(cur) ? null : cur;
  }
  function fetchText(url) {
    return fetch(url).then(function (r) { return r.ok ? r.text() : null; }).catch(function () { return null; });
  }
  function load() {
    if (players) return Promise.resolve();
    if (loading) return loading;
    loading = fetchText('data/seasons.json').then(function (t) {
      var seasons = [];
      try { seasons = JSON.parse(t) || []; } catch (e) {}
      if (!seasons.length) seasons = [new Date().getFullYear()];
      return Promise.all(seasons.map(function (y) {
        return Promise.all([fetchText('data/' + y + '/roster.csv'), fetchText('data/' + y + '/top100.csv')]).then(function (x) { return { y: y, roster: x[0], top: x[1] }; });
      }));
    }).then(function (all) {
      var by = {};
      all.forEach(function (s) {
        var ranks = {};
        if (s.top) parseCSV(s.top).forEach(function (r) { var k = top100Rank(r); if (k !== null) ranks[r.player_id] = k; });
        if (!s.roster) return;
        parseCSV(s.roster).forEach(function (r) {
          if (!r.player_id) return;
          var e = by[r.player_id] || (by[r.player_id] = { id: r.player_id, n: r.full_name, s: [] });
          e.s.push({ y: parseInt(s.y, 10), team: r.team, pos: r.position_abbreviation, org: r.org_id, orgn: r.org_name || '', t100: ranks[r.player_id] || null, mlb: !!r.mlb_debut_date });
        });
      });
      players = Object.keys(by).map(function (k) { return by[k]; });
      players.forEach(function (p) { p.s.sort(function (a, b) { return b.y - a.y; }); p.k = norm(p.n); });
    });
    return loading;
  }

  // ---------- search ----------
  function norm(s) { return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function search(raw) {
    var toks = norm(raw.trim()).split(/\s+/).filter(Boolean);
    if (!toks.length || !players) return [];
    var years = toks.filter(function (x) { return /^(19|20)\d\d$/.test(x); });
    var ws = toks.filter(function (x) { return years.indexOf(x) < 0; });
    words = ws.join(' ');
    var out = [];
    players.forEach(function (p) {
      if (years.length && !years.every(function (y) { return p.s.some(function (s) { return String(s.y) === y; }); })) return;
      var n = p.k, parts = n.split(' '), s = 0;
      if (!words) s = 10;
      else if (n === words) s = 100;
      else if (n.indexOf(words) === 0) s = 80;
      else if (parts.some(function (w) { return w.indexOf(words) === 0; })) s = 70;
      else if (ws.every(function (t) { return n.indexOf(t) >= 0; })) s = 55;
      else if (p.s.some(function (x) { return norm(x.team).indexOf(words) >= 0 || norm(x.orgn).indexOf(words) >= 0; })) s = 20;
      else return;
      if (p.s[0].t100) s += 3;
      if (p.s[0].mlb) s += 1;
      out.push([s, p]);
    });
    return out.sort(function (a, b) { return b[0] - a[0] || a[1].n.localeCompare(b[1].n); }).map(function (x) { return x[1]; });
  }
  function hi(name) {
    var n = norm(name), i = words ? n.indexOf(words) : -1;
    if (i < 0) return esc(name);
    return esc(name.slice(0, i)) + '<mark>' + esc(name.slice(i, i + words.length)) + '</mark>' + esc(name.slice(i + words.length));
  }
  function href(p, y) { return 'player.html?id=' + encodeURIComponent(p.id) + '&season=' + (y || p.s[0].y); }
  function photo(id) { return 'https://img.mlbstatic.com/mlb-photos/image/upload/c_fill,g_auto/w_120/v1/people/' + id + '/headshot/milb/current'; }

  function render() {
    var raw = input.value;
    box.classList.toggle('has', !!raw);
    if (!raw.trim()) { close(); return; }
    if (!players) { list.innerHTML = '<div class="ps-none">Loading players...</div>'; open(); return; }
    res = search(raw);
    act = res.length ? 0 : -1;
    var shown = res.slice(0, 8);
    if (!shown.length) {
      list.innerHTML = '<div class="ps-none">No player found for “' + esc(raw.trim()) + '”. Check the spelling, or try a team or a year.</div>';
    } else {
      list.innerHTML = shown.map(function (p, i) {
        var c = p.s[0];
        return '<div class="ps-it' + (c.t100 ? ' t' : '') + (c.mlb ? ' m' : '') + (i === act ? ' act' : '') + '" role="option" data-i="' + i + '">' +
          '<div class="ps-av"><img class="ps-ph" src="' + photo(p.id) + '" alt="" onerror="this.style.display=\'none\'">' +
          (c.org ? '<img class="ps-org" src="https://www.mlbstatic.com/team-logos/' + esc(c.org) + '.svg" alt="" onerror="this.style.display=\'none\'">' : '') + '</div>' +
          '<div class="ps-tx"><div class="ps-nm">' + hi(p.n) + (c.t100 ? '<span class="ps-tag">#' + c.t100 + '</span>' : '') + '</div>' +
          '<div class="ps-sub">' + esc(c.team) + (c.orgn ? ' · ' + esc(c.orgn) : '') + (p.s.length > 1 ? ' · also ' + p.s.slice(1).map(function (x) { return x.y; }).join(', ') : '') + '</div></div>' +
          '<span class="ps-pos">' + esc(c.pos) + '</span>' +
          '<span class="ps-yrs">' + p.s.map(function (x) { return '<a class="ps-yr" href="' + href(p, x.y) + '" title="' + esc(x.team) + ' (' + x.y + ')">' + x.y + '</a>'; }).join('') + '</span></div>';
      }).join('') +
        '<div class="ps-foot">' + (res.length > 8 ? '<span>' + (res.length - 8) + ' more, keep typing to narrow</span>' : '') +
        '<span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open latest</span><span>click a year for that season</span><span><kbd>Esc</kbd> close</span></div>';
    }
    open();
  }
  function open() { list.classList.add('open'); input.setAttribute('aria-expanded', 'true'); }
  function close() { list.classList.remove('open'); input.setAttribute('aria-expanded', 'false'); }
  function mark() {
    var items = list.querySelectorAll('.ps-it');
    items.forEach(function (e, i) { e.classList.toggle('act', i === act); });
    if (items[act]) items[act].scrollIntoView({ block: 'nearest' });
  }
  function go(p, y) { window.location.href = href(p, y); }

  input.addEventListener('focus', function () { load().then(function () { if (input.value.trim()) render(); }); });
  input.addEventListener('input', function () { render(); load().then(function () { if (input.value.trim()) render(); }); });
  input.addEventListener('keydown', function (e) {
    var n = Math.min(res.length, 8);
    if (e.key === 'ArrowDown' && n) { e.preventDefault(); act = (act + 1) % n; mark(); }
    else if (e.key === 'ArrowUp' && n) { e.preventDefault(); act = (act - 1 + n) % n; mark(); }
    else if (e.key === 'Enter' && act >= 0 && res[act]) { e.preventDefault(); go(res[act]); }
    else if (e.key === 'Escape') { close(); input.blur(); }
  });
  list.addEventListener('mousedown', function (e) { e.preventDefault(); });
  list.addEventListener('click', function (e) {
    var a = e.target.closest('.ps-it');
    if (!a) return;
    var yr = e.target.closest('.ps-yr');
    if (yr) return;                       // the year link navigates on its own
    var p = res[+a.getAttribute('data-i')];
    if (p) go(p);
  });
  list.addEventListener('mousemove', function (e) {
    var a = e.target.closest('.ps-it');
    if (!a) return;
    act = +a.getAttribute('data-i');
    list.querySelectorAll('.ps-it').forEach(function (x, i) { x.classList.toggle('act', i === act); });
  });
  clr.addEventListener('click', function () { input.value = ''; render(); input.focus(); });
  document.addEventListener('click', function (e) { if (!box.contains(e.target)) close(); });
  // "/" jumps to the search box from anywhere on the page
  document.addEventListener('keydown', function (e) {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target, tag = t && t.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable)) return;
    e.preventDefault();
    input.focus();
  });
})();
