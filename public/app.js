// ============================================================
//  Kadr Media Dashboard — Frontend
// ============================================================

const STAGES = [
  { key: 'ssenariy', label: 'Ssenariy' },
  { key: 'syomka',   label: 'Syomka' },
  { key: 'montaj',   label: 'Montaj' },
  { key: 'tasdiq',   label: 'Tasdiq' },
  { key: 'joylash',  label: 'Joylash' },
];
const STATUS_LABEL = { kutilmoqda: 'Kutilmoqda', jarayonda: 'Jarayonda', tayyor: 'Tayyor' };
const COLORS = ['#0a84ff', '#bf5af2', '#ff9f0a', '#30d158', '#ff375f', '#ffd60a', '#64d2ff', '#ff453a'];

const SCRIPT_ST = {
  yozilmoqda:        { label: 'Yozilmoqda',        dot: '🟡', cls: 'st-yellow' },
  tasdiq_kutilmoqda: { label: 'Tasdiq kutilmoqda', dot: '🟠', cls: 'st-orange' },
  tasdiqlandi:       { label: 'Tasdiqlandi',       dot: '🟢', cls: 'st-green' },
  qaytarildi:        { label: 'Qaytarildi',        dot: '🔴', cls: 'st-red' },
};
const VIDEO_ST = {
  topshirildi:   { label: 'Topshirildi',   cls: 'st-orange' },
  qabul_qilindi: { label: 'Qabul qilindi', cls: 'st-green' },
  qaytarildi:    { label: 'Qaytarildi',    cls: 'st-red' },
};

let ME = null;
let TOKEN = localStorage.getItem('km_token') || null;
let TIERS = {};
let VIEW = '';
let FILTER = 'all';
let SEARCH = '';
const DATA = {}; // cache: projects, scripts, videos, editors, team, clients, finance, audit, cabinet

// ---------- Utils ----------
const $ = (s) => document.querySelector(s);
const esc = (s) => (s == null ? '' : String(s)).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const initials = (n) => (n || '?').trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
const colorFor = (n) => { let h = 0; for (const c of (n || '')) h = c.charCodeAt(0) + ((h << 5) - h); return COLORS[Math.abs(h) % COLORS.length]; };
const money = (n) => String(n || 0).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + " so'm";

async function api(url, opts = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json', 'X-Token': TOKEN || '' }, ...opts });
  if (r.status === 401) { doLogout(); throw new Error('401'); }
  return r.json();
}
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.remove('hidden');
  clearTimeout(t._t); t._t = setTimeout(() => t.classList.add('hidden'), 2400);
}
const UZ_MONTHS = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'];
function fmtDate(d) {
  if (!d) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(d));
  if (m) return parseInt(m[3], 10) + ' ' + UZ_MONTHS[parseInt(m[2], 10) - 1];
  return d;
}

// ============================================================
//  AUTH
// ============================================================
$('#loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = $('#loginUser').value.trim();
  const password = $('#loginPass').value;
  $('#loginBtn').textContent = 'Tekshirilmoqda...';
  $('#loginError').classList.add('hidden');
  try {
    const r = await fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) throw new Error('bad');
    const d = await r.json();
    TOKEN = d.token; ME = d.user;
    localStorage.setItem('km_token', TOKEN);
    startApp();
  } catch (err) {
    $('#loginError').textContent = 'Login yoki parol noto\'g\'ri';
    $('#loginError').classList.remove('hidden');
  }
  $('#loginBtn').textContent = 'Kirish';
});

async function tryRestore() {
  if (!TOKEN) return showLogin();
  try {
    ME = await api('/api/me');
    if (ME && ME.id) startApp(); else showLogin();
  } catch (e) { showLogin(); }
}
function showLogin() { $('#login').classList.remove('hidden'); $('#app').classList.add('hidden'); }
function doLogout() {
  try { api('/api/logout', { method: 'POST' }); } catch (e) {}
  TOKEN = null; ME = null; localStorage.removeItem('km_token');
  location.reload();
}
$('#logoutBtn').addEventListener('click', doLogout);

async function startApp() {
  $('#login').classList.add('hidden');
  $('#app').classList.remove('hidden');
  $('#meName').textContent = ME.name;
  $('#meRole').textContent = ME.title || ME.role;
  $('#meAvatar').textContent = initials(ME.name);
  $('#meAvatar').style.background = ME.color || colorFor(ME.name);
  try { TIERS = await api('/api/tiers'); } catch (e) { TIERS = {}; }
  buildNav();
  VIEW = NAV_FOR(ME.role)[0].view;
  render();
}

// ============================================================
//  NAVIGATION (rolga qarab)
// ============================================================
const NAV_ITEMS = [
  // Montajchi uchun (birinchi)
  { view: 'cabinet',   icon: '★', label: 'Mening kabinetim', roles: ['editor'] },
  { view: 'myvideos',  icon: '►', label: 'Videolarim',    roles: ['editor'] },
  // Mijoz uchun (birinchi)
  { view: 'client',    icon: '▦', label: 'Loyihalarim',   roles: ['client'] },
  { view: 'cscripts',  icon: '✎', label: 'Ssenariylar',   roles: ['client'] },
  { view: 'cvideos',   icon: '►', label: 'Videolar',      roles: ['client'] },
  // Jamoa
  { view: 'dashboard', icon: '▦', label: 'Boshqaruv',     roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'projects',  icon: '▣', label: 'Loyihalar',     roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'scripts',   icon: '✎', label: 'Ssenariylar',   roles: ['ceo', 'coordinator', 'lead', 'editor'] },
  { view: 'videos',    icon: '►', label: 'Montaj',        roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'editors',   icon: '◍', label: 'Montajchilar',  roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'finance',   icon: '₿', label: 'Moliya',        roles: ['ceo', 'coordinator'] },
  { view: 'team',      icon: '◐', label: 'Jamoa',         roles: ['ceo', 'coordinator'] },
  { view: 'audit',     icon: '≡', label: 'Audit',         roles: ['ceo', 'coordinator'] },
];
const NAV_FOR = (role) => NAV_ITEMS.filter((n) => n.roles.includes(role));

function buildNav() {
  const items = NAV_FOR(ME.role);
  $('#navMenu').innerHTML = items.map((n) =>
    `<button class="nav-btn" data-view="${n.view}"><span class="ic">${n.icon}</span> ${n.label}</button>`
  ).join('');
  // mobil pastki menyu (5 tagacha)
  $('#mobileNav').innerHTML = items.slice(0, 5).map((n) =>
    `<button class="m-btn" data-view="${n.view}"><span>${n.icon}</span>${n.label}</button>`
  ).join('');
  document.querySelectorAll('.nav-btn, .m-btn').forEach((b) =>
    b.addEventListener('click', () => { VIEW = b.dataset.view; FILTER = 'all'; SEARCH = ''; render(); })
  );
}
function setActiveNav() {
  document.querySelectorAll('.nav-btn, .m-btn').forEach((b) => b.classList.toggle('active', b.dataset.view === VIEW));
}

// ============================================================
//  RENDER ROUTER
// ============================================================
const TITLES = {
  dashboard: ['Boshqaruv paneli', 'Bugungi holat — bir qarashda'],
  projects:  ['Loyihalar', 'Barcha loyihalar'],
  scripts:   ['Ssenariylar', 'Yozish, tasdiqlash, versiyalar'],
  videos:    ['Montaj — videolar', 'Topshirish va tasdiqlash'],
  editors:   ['Montajchilar', 'Kabinetlar va hisob-kitob'],
  finance:   ['Moliya', 'Montaj xarajatlari va to\'lovlar'],
  team:      ['Jamoa yuklamasi', 'Rahbarlar yuklamasi'],
  audit:     ['Audit log', 'Barcha harakatlar tarixi'],
  cabinet:   ['Mening kabinetim', 'Ishlagan, to\'langan, qolgan'],
  myvideos:  ['Videolarim', 'Topshirgan videolarim'],
  client:    ['Loyihalarim', 'Sizning loyihalaringiz holati'],
  cscripts:  ['Ssenariylar', 'Loyihangiz ssenariylari'],
  cvideos:   ['Videolar', 'Tayyor videolaringiz'],
};

async function render() {
  setActiveNav();
  $('#viewTitle').textContent = (TITLES[VIEW] || ['—', ''])[0];
  $('#viewSub').textContent = (TITLES[VIEW] || ['', ''])[1];
  $('#content').innerHTML = '<div class="empty"><div class="em-ic">⏳</div>Yuklanmoqda...</div>';
  buildTopbarActions();
  try {
    if (VIEW === 'dashboard') await viewDashboard();
    else if (VIEW === 'projects') await viewProjects();
    else if (VIEW === 'scripts' || VIEW === 'cscripts') await viewScripts();
    else if (VIEW === 'videos') await viewVideos();
    else if (VIEW === 'myvideos' || VIEW === 'cvideos') await viewVideos();
    else if (VIEW === 'editors') await viewEditors();
    else if (VIEW === 'finance') await viewFinance();
    else if (VIEW === 'team') await viewTeam();
    else if (VIEW === 'audit') await viewAudit();
    else if (VIEW === 'cabinet') await viewCabinet();
    else if (VIEW === 'client') await viewProjects();
  } catch (e) {
    if (e.message !== '401') $('#content').innerHTML = '<div class="empty"><div class="em-ic">⚠️</div>Xatolik yuz berdi</div>';
  }
}

function buildTopbarActions() {
  const a = $('#topbarActions');
  let html = '';
  const canSearch = ['projects', 'scripts', 'videos', 'editors', 'client', 'cscripts', 'cvideos', 'myvideos'].includes(VIEW);
  if (canSearch) html += `<div class="search-box"><span>⌕</span><input id="searchInput" placeholder="Qidirish..." value="${esc(SEARCH)}" /></div>`;
  const role = ME.role;
  if ((VIEW === 'projects') && ['ceo', 'coordinator', 'lead'].includes(role)) html += `<button class="btn-primary" data-act="add-project">+ Loyiha</button>`;
  if ((VIEW === 'scripts') && role !== 'client') html += `<button class="btn-primary" data-act="add-script">+ Ssenariy</button>`;
  if ((VIEW === 'videos' || VIEW === 'myvideos') && role !== 'client') html += `<button class="btn-primary" data-act="add-video">+ Video</button>`;
  if (VIEW === 'finance') html += `<button class="btn-primary" data-act="add-payment">+ To'lov</button>`;
  a.innerHTML = html;
  if (canSearch) $('#searchInput').addEventListener('input', (e) => { SEARCH = e.target.value.toLowerCase(); render(); });
  a.querySelectorAll('[data-act]').forEach((b) => b.addEventListener('click', () => {
    const act = b.dataset.act;
    if (act === 'add-project') openProjectModal(null);
    if (act === 'add-script') openScriptModal(null);
    if (act === 'add-video') openVideoModal();
    if (act === 'add-payment') openPaymentModal();
  }));
}

// ============================================================
//  Helpers: badges, cards
// ============================================================
function statTile(ic, val, label, accent) {
  return `<div class="stat-card accent-${accent}"><div class="stat-ic">${ic}</div><div class="stat-val">${val}</div><div class="stat-label">${label}</div></div>`;
}
function emptyState(msg) { return `<div class="empty"><div class="em-ic">📭</div>${msg || 'Hozircha bo\'sh'}</div>`; }
function matchSearch(text) { return !SEARCH || (text || '').toLowerCase().includes(SEARCH); }

// ---------- DASHBOARD (loyihalar + stats) ----------
async function viewDashboard() {
  const [stats, projects] = await Promise.all([api('/api/stats'), api('/api/projects')]);
  DATA.projects = projects;
  const c = $('#content');
  c.innerHTML = `
    <div class="stats-grid">
      ${statTile('▣', stats.total, 'Jami loyihalar', 'blue')}
      ${statTile('⏱', stats.overdue, 'Kechikayotgan', 'red')}
      ${statTile('✓', stats.todayTasks, 'Bugun bajarilgan', 'green')}
      ${statTile('⚠', stats.atRisk, 'Xavf ostida', 'orange')}
    </div>
    <div class="section-head"><h3>Loyihalar</h3></div>
    <div class="cards-grid">${projects.map(projectCard).join('') || emptyState()}</div>`;
  bindProjectCards();
}

// ---------- PROJECTS ----------
async function viewProjects() {
  const projects = await api('/api/projects');
  DATA.projects = projects;
  let list = projects.filter((p) => matchSearch(p.name + ' ' + p.client + ' ' + p.responsible));
  if (FILTER === 'overdue') list = list.filter((p) => p.overdue);
  else if (FILTER === 'risk') list = list.filter((p) => p.atRisk);
  else if (FILTER === 'done') list = list.filter((p) => p.fullyDone);
  const chips = [['all', 'Hammasi'], ['overdue', 'Kechikkan'], ['risk', 'Xavf'], ['done', 'Yakunlangan']];
  $('#content').innerHTML = `
    <div class="filter-row">${chips.map(([k, l]) => `<button class="chip ${FILTER === k ? 'active' : ''}" data-f="${k}">${l}</button>`).join('')}</div>
    <div class="cards-grid">${list.map(projectCard).join('') || emptyState('Loyiha topilmadi')}</div>`;
  $('#content').querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => { FILTER = c.dataset.f; render(); }));
  bindProjectCards();
}

function projectCard(p) {
  const badges = [];
  if (p.fullyDone) badges.push('<span class="badge done">✓ Tayyor</span>');
  else { if (p.overdue) badges.push('<span class="badge overdue">⏱ Kechikkan</span>'); if (p.atRisk && !p.overdue) badges.push('<span class="badge risk">⚠ Xavf</span>'); }
  const dl = !p.deadline ? 'Muddat yo\'q' : p.fullyDone ? 'Yakunlandi' : p.daysLeft < 0 ? `${Math.abs(p.daysLeft)} kun kechikdi` : p.daysLeft === 0 ? 'Bugun!' : p.daysLeft <= 2 ? `${p.daysLeft} kun qoldi` : fmtDate(p.deadline);
  const dlCls = (!p.fullyDone && p.deadline && p.daysLeft < 0) ? 'late' : (!p.fullyDone && p.daysLeft <= 2) ? 'soon' : '';
  const clickable = ['ceo', 'coordinator', 'lead'].includes(ME.role);
  return `
    <div class="project-card ${clickable ? 'clickable' : ''}" data-id="${p.id}">
      <div class="pc-top"><div class="pc-name">${esc(p.name)}</div><div class="pc-badges">${badges.join('')}</div></div>
      <div class="pc-client">📁 ${esc(p.client) || '—'}</div>
      <div class="pc-stages">${STAGES.map((s) => `<div class="stage-dot ${p[s.key]}">${s.label}</div>`).join('')}</div>
      ${p.plan ? `
      <div class="plan-box">
        <div class="plan-head"><span>📅 Oylik reja (${p.plan} ta/oy)</span><b>${p.planDone}/${p.planTotal} · ${p.planPct}%</b></div>
        <div class="plan-grid">${STAGES.map((s) => {
          const dn = p['done_' + s.key] || 0; const pct = p.plan ? Math.min(Math.round(dn / p.plan * 100), 100) : 0;
          const full = dn >= p.plan;
          return `<div class="plan-stage"><div class="pl-top"><span>${s.label}</span><b class="${full ? 'full' : ''}">${dn}/${p.plan}</b></div>
            <div class="pl-bar"><div class="pl-fill ${full ? 'done' : ''}" style="width:${pct}%"></div></div></div>`;
        }).join('')}</div>
      </div>` : `
      <div class="pc-progress"><div class="progress-bar"><div class="progress-fill" style="width:${p.progress}%"></div></div>
        <div class="pc-progress-label"><span>${p.doneCount}/5 bosqich</span><span>${p.progress}%</span></div></div>`}
      ${p.muammo ? `<div class="pc-problem">⚠ ${esc(p.muammo)}</div>` : ''}
      <div class="pc-foot"><div class="pc-resp"><div class="mini-av" style="background:${colorFor(p.responsible)}">${initials(p.responsible)}</div><span>${esc(p.responsible) || '—'}</span></div>
        <div class="pc-deadline ${dlCls}">📅 ${dl}</div></div>
    </div>`;
}
function bindProjectCards() {
  if (!['ceo', 'coordinator', 'lead'].includes(ME.role)) return;
  document.querySelectorAll('.project-card.clickable').forEach((el) =>
    el.addEventListener('click', () => openProjectModal((DATA.projects || []).find((p) => p.id == el.dataset.id))));
}

// ============================================================
//  SSENARIYLAR
// ============================================================
async function viewScripts() {
  const [scripts, stats] = await Promise.all([api('/api/scripts'), (ME.role !== 'client' ? api('/api/script-stats') : Promise.resolve([]))]);
  DATA.scripts = scripts;
  let list = scripts.filter((s) => matchSearch(s.title + ' ' + s.project + ' ' + s.author));
  if (['yozilmoqda', 'tasdiq_kutilmoqda', 'tasdiqlandi', 'qaytarildi'].includes(FILTER)) list = list.filter((s) => s.status === FILTER);
  const chips = [['all', 'Hammasi'], ['tasdiq_kutilmoqda', '🟠 Tasdiq kutmoqda'], ['tasdiqlandi', '🟢 Tasdiqlangan'], ['qaytarildi', '🔴 Qaytgan']];
  let statsHtml = '';
  if (ME.role !== 'client' && stats.length) {
    statsHtml = `<div class="section-head"><h3>Ssenaristlar</h3></div><div class="mini-stat-row">` +
      stats.map((s) => `<div class="mini-stat"><div class="mini-stat-av" style="background:${colorFor(s.author)}">${initials(s.author)}</div>
        <div><b>${esc(s.author)}</b><div class="muted">${s.total} yozgan · ${s.approved} tasdiq · ${s.rate}%</div></div></div>`).join('') + `</div>`;
  }
  $('#content').innerHTML = `
    ${statsHtml}
    <div class="filter-row">${chips.map(([k, l]) => `<button class="chip ${FILTER === k ? 'active' : ''}" data-f="${k}">${l}</button>`).join('')}</div>
    <div class="cards-grid">${list.map(scriptCard).join('') || emptyState('Ssenariy yo\'q')}</div>`;
  $('#content').querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => { FILTER = c.dataset.f; render(); }));
  $('#content').querySelectorAll('.script-card').forEach((el) => el.addEventListener('click', (e) => {
    if (e.target.closest('button')) return;
    openScriptModal((DATA.scripts || []).find((s) => s.id == el.dataset.id));
  }));
  $('#content').querySelectorAll('[data-sact]').forEach((b) => b.addEventListener('click', async (e) => {
    e.stopPropagation();
    await scriptAction(b.dataset.id, b.dataset.sact);
  }));
}

function scriptCard(s) {
  const st = SCRIPT_ST[s.status] || SCRIPT_ST.yozilmoqda;
  const isApprover = ['ceo', 'coordinator', 'lead'].includes(ME.role);
  let actions = '';
  if (ME.role !== 'client') {
    if (s.status === 'yozilmoqda' || s.status === 'qaytarildi') actions += `<button class="mini-btn blue" data-sact="submit" data-id="${s.id}">Tasdiqqa</button>`;
    if (isApprover && s.status === 'tasdiq_kutilmoqda') {
      actions += `<button class="mini-btn green" data-sact="approve" data-id="${s.id}">✓ Tasdiq</button>`;
      actions += `<button class="mini-btn red" data-sact="return" data-id="${s.id}">↩ Qaytar</button>`;
    }
  }
  return `
    <div class="script-card" data-id="${s.id}">
      <div class="pc-top"><div class="pc-name">${esc(s.title)}</div><span class="pill ${st.cls}">${st.dot} ${st.label}</span></div>
      <div class="pc-client">📁 ${esc(s.project) || '—'} · ✍ ${esc(s.author)}</div>
      ${s.hook ? `<div class="script-prev">${esc((s.hook || '').slice(0, 90))}${(s.hook || '').length > 90 ? '…' : ''}</div>` : ''}
      <div class="pc-foot">
        <div class="muted">${s.approved_by ? '✓ ' + esc(s.approved_by) : ''}${s.expert_ok ? ' · 🎓 ekspert' : ''}</div>
        <div class="card-actions">${actions}</div>
      </div>
    </div>`;
}
async function scriptAction(id, action) {
  await api(`/api/scripts/${id}/action`, { method: 'POST', body: JSON.stringify({ action }) });
  toast(action === 'approve' ? '✓ Tasdiqlandi' : action === 'return' ? '↩ Qaytarildi' : 'Tasdiqqa yuborildi');
  render();
}

// ============================================================
//  VIDEOLAR (montaj)
// ============================================================
async function viewVideos() {
  const videos = await api('/api/videos');
  DATA.videos = videos;
  let list = videos.filter((v) => matchSearch(v.title + ' ' + v.project + ' ' + v.editor));
  if (['topshirildi', 'qabul_qilindi', 'qaytarildi'].includes(FILTER)) list = list.filter((v) => v.status === FILTER);
  const chips = [['all', 'Hammasi'], ['topshirildi', 'Topshirilgan'], ['qabul_qilindi', 'Qabul qilingan'], ['qaytarildi', 'Qaytgan']];
  $('#content').innerHTML = `
    <div class="filter-row">${chips.map(([k, l]) => `<button class="chip ${FILTER === k ? 'active' : ''}" data-f="${k}">${l}</button>`).join('')}</div>
    <div class="cards-grid">${list.map(videoCard).join('') || emptyState('Video yo\'q')}</div>`;
  $('#content').querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => { FILTER = c.dataset.f; render(); }));
  $('#content').querySelectorAll('[data-vact]').forEach((b) => b.addEventListener('click', () => videoActionUI(b.dataset.id, b.dataset.vact)));
}

function videoCard(v) {
  const st = VIDEO_ST[v.status] || VIDEO_ST.topshirildi;
  const isApprover = ['ceo', 'coordinator', 'lead'].includes(ME.role);
  let actions = '';
  if (isApprover && v.status === 'topshirildi') {
    actions += `<button class="mini-btn green" data-vact="accept" data-id="${v.id}">✓ Qabul</button>`;
    actions += `<button class="mini-btn red" data-vact="return" data-id="${v.id}">↩ Qaytar</button>`;
  }
  if (isApprover && v.status === 'qabul_qilindi') actions += `<button class="mini-btn blue" data-vact="instagram" data-id="${v.id}">📷 IG link</button>`;
  return `
    <div class="video-card">
      <div class="pc-top"><div class="pc-name">${esc(v.title)}</div><span class="pill ${st.cls}">${st.label}</span></div>
      <div class="pc-client">📁 ${esc(v.project) || '—'} · 🎬 ${esc(v.editor)}</div>
      <div class="video-meta">
        ${v.amount ? `<span class="money-chip">💰 ${money(v.amount)}${v.tier ? ' · ' + (TIERS[v.tier] ? TIERS[v.tier].label : v.tier) : ''}</span>` : ''}
        ${v.drive_link ? `<a href="${esc(v.drive_link)}" target="_blank" class="link-chip">🔗 Drive</a>` : ''}
        ${v.instagram_link ? `<a href="${esc(v.instagram_link)}" target="_blank" class="link-chip">📷 Instagram</a>` : ''}
      </div>
      ${v.note ? `<div class="pc-problem soft">📝 ${esc(v.note)}</div>` : ''}
      <div class="pc-foot"><div class="muted">📅 ${fmtDate(v.vdate)}${v.approved_by ? ' · ✓ ' + esc(v.approved_by) : ''}</div>
        <div class="card-actions">${actions}</div></div>
    </div>`;
}
function videoActionUI(id, action) {
  if (action === 'accept') {
    const opts = Object.entries(TIERS).map(([k, t]) => `<button class="tier-btn" data-tier="${k}">${t.label}<br><b>${money(t.price)}</b></button>`).join('');
    openModal('Videoni qabul qilish', `<p class="muted" style="margin-bottom:14px">Daraja tanlang — pul avtomatik hisoblanadi:</p><div class="tier-grid">${opts}</div>`, () => {
      $('#modalBody').querySelectorAll('.tier-btn').forEach((b) => b.addEventListener('click', async () => {
        await api(`/api/videos/${id}/action`, { method: 'POST', body: JSON.stringify({ action: 'accept', tier: b.dataset.tier }) });
        closeModal(); toast('✅ Qabul qilindi — pul hisoblandi'); render();
      }));
    });
  } else if (action === 'return') {
    openModal('Videoni qaytarish', `<div class="field"><label>Sabab / izoh</label><textarea id="vrnote" placeholder="Nima tuzatish kerak..."></textarea></div><button class="btn-save" id="vrbtn">Qaytarish</button>`, () => {
      $('#vrbtn').addEventListener('click', async () => {
        await api(`/api/videos/${id}/action`, { method: 'POST', body: JSON.stringify({ action: 'return', note: $('#vrnote').value }) });
        closeModal(); toast('↩ Qaytarildi'); render();
      });
    });
  } else if (action === 'instagram') {
    openModal('Instagram link', `<div class="field"><label>Instagram post linki</label><input id="iglink" placeholder="https://instagram.com/..." /></div><button class="btn-save" id="igbtn">Saqlash</button>`, () => {
      $('#igbtn').addEventListener('click', async () => {
        await api(`/api/videos/${id}/action`, { method: 'POST', body: JSON.stringify({ action: 'instagram', instagram_link: $('#iglink').value }) });
        closeModal(); toast('📷 Link saqlandi'); render();
      });
    });
  }
}

// ============================================================
//  MONTAJCHILAR (kabinetlar)
// ============================================================
async function viewEditors() {
  const editors = await api('/api/editors');
  DATA.editors = editors;
  let list = editors.filter((e) => matchSearch(e.name));
  const totalEarned = editors.reduce((a, e) => a + e.earned, 0);
  const totalRemaining = editors.reduce((a, e) => a + e.remaining, 0);
  const totalVideos = editors.reduce((a, e) => a + e.accepted, 0);
  $('#content').innerHTML = `
    <div class="stats-grid">
      ${statTile('🎬', totalVideos, 'Qabul qilingan video', 'blue')}
      ${statTile('💰', money(totalEarned), 'Jami hisoblangan', 'green')}
      ${statTile('⏳', money(totalRemaining), 'Qolgan to\'lov', 'orange')}
      ${statTile('👥', editors.length, 'Montajchilar', 'red')}
    </div>
    <div class="cards-grid">${list.map(editorCard).join('') || emptyState()}</div>`;
}
function editorCard(e) {
  const proj = e.byProject.slice(0, 3).map((p) => `${esc(p.project)}: ${p.count}`).join(' · ');
  return `
    <div class="team-card">
      <div class="team-head"><div class="team-av" style="background:${e.color || colorFor(e.name)}">${initials(e.name)}</div>
        <div><div class="team-name">${esc(e.name)}</div><div class="team-role">${e.accepted} video · ${proj || 'hozircha yo\'q'}</div></div></div>
      <div class="money-rows">
        <div class="mrow"><span>Hisoblangan</span><b>${money(e.earned)}</b></div>
        <div class="mrow"><span>To'langan</span><b style="color:var(--green)">${money(e.paid)}</b></div>
        <div class="mrow big"><span>Qolgan</span><b style="color:var(--orange)">${money(e.remaining)}</b></div>
      </div>
      <div class="ec-stats"><span>${e.accepted} qabul</span><span>${e.pending} kutmoqda</span><span>${e.returned} qaytgan</span><span>~${money(e.avg)}</span></div>
      ${['ceo', 'coordinator'].includes(ME.role) ? `<button class="btn-save sm" data-pay="${esc(e.name)}">💸 To'lov qilish</button>` : ''}
    </div>`;
}

// ============================================================
//  CABINET (montajchining o'zi)
// ============================================================
async function viewCabinet() {
  const c = await api('/api/cabinet');
  DATA.cabinet = c;
  const grouped = c.byProject.map((p) => `<div class="mrow"><span>${esc(p.project)}</span><b>${p.count} video</b></div>`).join('') || '<div class="muted">Hozircha video yo\'q</div>';
  const pays = c.payments.map((p) => `<div class="pay-row"><div><b>${money(p.amount)}</b><div class="muted">${fmtDate(p.pdate)} · ${esc(p.note) || '—'}</div></div><div class="muted">${esc(p.paid_by)}</div></div>`).join('') || '<div class="muted">To\'lov tarixi yo\'q</div>';
  $('#content').innerHTML = `
    <div class="stats-grid">
      ${statTile('🎬', c.accepted, 'Qabul qilingan', 'blue')}
      ${statTile('💰', money(c.earned), 'Hisoblangan', 'green')}
      ${statTile('✓', money(c.paid), 'To\'langan', 'purple')}
      ${statTile('⏳', money(c.remaining), 'Qolgan', 'orange')}
    </div>
    <div class="ceo-grid">
      <div class="panel"><h3>📁 Loyihalar bo'yicha</h3><div class="money-rows">${grouped}</div>
        <div class="ec-stats" style="margin-top:14px"><span>${c.videos} jami</span><span>${c.pending} kutmoqda</span><span>${c.returned} qaytgan</span></div></div>
      <div class="panel"><h3>💸 To'lov tarixim</h3>${pays}</div>
    </div>`;
}

// ============================================================
//  FINANCE (CEO)
// ============================================================
async function viewFinance() {
  const f = await api('/api/finance');
  DATA.finance = f;
  const proj = f.byProject.map((p) => `<div class="mrow"><span>${esc(p.project)}</span><b>${money(p.cost)}</b></div>`).join('') || '<div class="muted">Ma\'lumot yo\'q</div>';
  const eds = f.editors.map((e) => `<div class="ceo-item"><div class="ci-left"><div class="mini-av" style="background:${e.color || colorFor(e.name)}">${initials(e.name)}</div>
    <div><div class="ci-name">${esc(e.name)}</div><div class="ci-sub">${e.accepted} video · qolgan ${money(e.remaining)}</div></div></div>
    <span class="pill green">${money(e.earned)}</span></div>`).join('');
  $('#content').innerHTML = `
    <div class="stats-grid">
      ${statTile('📅', money(f.monthCost), 'Shu oy montaj xarajati', 'blue')}
      ${statTile('💰', money(f.totalEarned), 'Jami hisoblangan', 'green')}
      ${statTile('✓', money(f.totalPaid), 'Jami to\'langan', 'purple')}
      ${statTile('⏳', money(f.totalRemaining), 'Qolgan qarz', 'orange')}
    </div>
    <div class="ceo-grid">
      <div><div class="panel"><h3>👥 Montajchilar daromadi</h3><div class="ceo-list">${eds || emptyState()}</div></div></div>
      <div>
        <div class="panel"><h3>🏆 Eng faol montajchi</h3><div style="font-size:22px;font-weight:800">${esc(f.topEditor) || '—'}</div><div class="muted">${f.topEditorVideos} ta qabul qilingan video</div></div>
        <div class="panel"><h3>📁 Loyiha bo'yicha xarajat</h3><div class="money-rows">${proj}</div></div>
      </div>
    </div>`;
}

// ============================================================
//  TEAM (workload)
// ============================================================
async function viewTeam() {
  const stats = await api('/api/stats');
  const max = Math.max(...stats.workload.map((w) => w.total), 1);
  $('#content').innerHTML = `<div class="team-grid">${stats.workload.map((w) => `
    <div class="team-card"><div class="team-head"><div class="team-av" style="background:${colorFor(w.name)}">${initials(w.name)}</div>
      <div><div class="team-name">${esc(w.name)}</div><div class="team-role">Loyiha rahbari</div></div></div>
      <div class="wl-bars"><div><div class="wl-row"><span class="lbl">Jami loyiha</span><span class="val">${w.total}</span></div>
        <div class="wl-meter"><div class="wl-meter-fill" style="width:${Math.round(w.total / max * 100)}%;background:${colorFor(w.name)}"></div></div></div>
        <div class="wl-row"><span class="lbl">Faol</span><span class="val" style="color:var(--blue)">${w.active}</span></div>
        <div class="wl-row"><span class="lbl">Kechikkan</span><span class="val" style="color:var(--red)">${w.overdue}</span></div>
        <div class="wl-row"><span class="lbl">Xavf ostida</span><span class="val" style="color:var(--orange)">${w.atRisk}</span></div></div>
    </div>`).join('')}</div>`;
}

// ============================================================
//  AUDIT
// ============================================================
async function viewAudit() {
  const log = await api('/api/audit');
  $('#content').innerHTML = `<div class="panel"><div class="audit-list">${log.map((a) => `
    <div class="activity-item"><div class="activity-dot" style="background:${colorFor(a.actor)}"></div>
      <div><b>${esc(a.actor)}</b> — ${esc(a.action)} ${a.detail ? `<span class="muted">${esc(a.detail)}</span>` : ''}</div>
      <div class="at-time">${esc((a.created_at || '').slice(5, 16))}</div></div>`).join('') || emptyState('Harakatlar yo\'q')}</div></div>`;
}

// ============================================================
//  MODALS
// ============================================================
function openModal(title, bodyHTML, onMount) {
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = bodyHTML;
  $('#modal').classList.remove('hidden');
  if (onMount) onMount();
}
function closeModal() { $('#modal').classList.add('hidden'); }
$('#modalClose').addEventListener('click', closeModal);
$('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });

// ---- Project modal (mavjud) ----
let EDIT_P = null, PDRAFT = {};
async function openProjectModal(project) {
  if (!DATA.clients) DATA.clients = await api('/api/clients');
  if (!DATA.team) DATA.team = await api('/api/team');
  EDIT_P = project;
  PDRAFT = project ? { ...project } : { name: '', client: '', responsible: ME.name, deadline: '', muammo: '', izoh: '', ssenariy: 'kutilmoqda', syomka: 'kutilmoqda', montaj: 'kutilmoqda', tasdiq: 'kutilmoqda', joylash: 'kutilmoqda' };
  const leads = DATA.team.filter((u) => ['lead', 'coordinator'].includes(u.role));
  openModal(project ? 'Loyihani tahrirlash' : 'Yangi loyiha', `
    <div class="field"><label>Loyiha nomi</label><input id="pf_name" value="${esc(PDRAFT.name)}" /></div>
    <div class="field-row">
      <div class="field"><label>Mijoz</label><select id="pf_client"><option value="">—</option>${DATA.clients.map((c) => `<option ${PDRAFT.client === c.name ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></div>
      <div class="field"><label>Javobgar</label><select id="pf_resp"><option value="">—</option>${leads.map((u) => `<option ${PDRAFT.responsible === u.name ? 'selected' : ''}>${esc(u.name)}</option>`).join('')}</select></div>
    </div>
    <div class="field"><label>Deadline</label><input id="pf_deadline" type="date" value="${PDRAFT.deadline || ''}" /></div>
    <div class="divider"></div><div class="sec-label">📅 Oylik reja (mijoz bilan kelishilgan)</div>
    <div class="field"><label>Oyiga nechta video — har bosqich uchun shu son</label><input id="pf_plan" type="number" min="0" value="${PDRAFT.plan || 0}" placeholder="masalan: 15" /></div>
    <div class="sec-label" style="margin-top:12px">Bu oy bajarilgani (har bosqich):</div>
    <div class="plan-inputs">${STAGES.map((s) => `<div class="field"><label>${s.label}</label><input id="pf_done_${s.key}" type="number" min="0" value="${PDRAFT['done_' + s.key] || 0}" /></div>`).join('')}</div>
    <div class="divider"></div><div class="sec-label">Jarayon bosqichlari (umumiy holat)</div>
    <div class="stage-editor">${STAGES.map((s) => `<div class="stage-edit-row"><span class="sname">${s.label}</span>
      <div class="seg" data-stage="${s.key}">
        <button data-v="kutilmoqda" class="${PDRAFT[s.key] === 'kutilmoqda' ? 'on-k' : ''}">Kutilmoqda</button>
        <button data-v="jarayonda" class="${PDRAFT[s.key] === 'jarayonda' ? 'on-j' : ''}">Jarayonda</button>
        <button data-v="tayyor" class="${PDRAFT[s.key] === 'tayyor' ? 'on-t' : ''}">Tayyor</button></div></div>`).join('')}</div>
    <div class="divider"></div>
    <div class="field"><label>⚠ Muammo</label><textarea id="pf_muammo">${esc(PDRAFT.muammo)}</textarea></div>
    <div class="field"><label>Izoh</label><textarea id="pf_izoh">${esc(PDRAFT.izoh)}</textarea></div>
    <div class="modal-actions">${project ? '<button class="btn-del" id="pf_del">O\'chirish</button>' : ''}<button class="btn-save" id="pf_save">${project ? 'Saqlash' : 'Qo\'shish'}</button></div>`,
  () => {
    $('#modalBody').querySelectorAll('.seg').forEach((seg) => seg.querySelectorAll('button').forEach((btn) => btn.addEventListener('click', () => {
      PDRAFT[seg.dataset.stage] = btn.dataset.v;
      seg.querySelectorAll('button').forEach((x) => x.className = '');
      btn.className = btn.dataset.v === 'kutilmoqda' ? 'on-k' : btn.dataset.v === 'jarayonda' ? 'on-j' : 'on-t';
    })));
    $('#pf_save').addEventListener('click', saveProject);
    if (project) $('#pf_del').addEventListener('click', deleteProject);
  });
}
async function saveProject() {
  const body = { name: $('#pf_name').value.trim() || 'Nomsiz', client: $('#pf_client').value, responsible: $('#pf_resp').value,
    deadline: $('#pf_deadline').value || null, muammo: $('#pf_muammo').value.trim(), izoh: $('#pf_izoh').value.trim(),
    ssenariy: PDRAFT.ssenariy, syomka: PDRAFT.syomka, montaj: PDRAFT.montaj, tasdiq: PDRAFT.tasdiq, joylash: PDRAFT.joylash,
    plan: parseInt($('#pf_plan').value || '0', 10),
    done_ssenariy: parseInt($('#pf_done_ssenariy').value || '0', 10), done_syomka: parseInt($('#pf_done_syomka').value || '0', 10),
    done_montaj: parseInt($('#pf_done_montaj').value || '0', 10), done_tasdiq: parseInt($('#pf_done_tasdiq').value || '0', 10),
    done_joylash: parseInt($('#pf_done_joylash').value || '0', 10) };
  if (EDIT_P) await api(`/api/projects/${EDIT_P.id}`, { method: 'PUT', body: JSON.stringify(body) });
  else await api('/api/projects', { method: 'POST', body: JSON.stringify(body) });
  closeModal(); toast('✓ Saqlandi'); render();
}
async function deleteProject() {
  if (!confirm('O\'chirilsinmi?')) return;
  await api(`/api/projects/${EDIT_P.id}`, { method: 'DELETE' }); closeModal(); toast('O\'chirildi'); render();
}

// ---- Script modal ----
let EDIT_S = null;
async function openScriptModal(script) {
  if (!DATA.projects) DATA.projects = await api('/api/projects');
  EDIT_S = script;
  const s = script || { title: '', project: '', client: '', hook: '', story: '', cta: '', link: '', author: ME.name, status: 'yozilmoqda' };
  const projOpts = DATA.projects.map((p) => `<option value="${esc(p.name)}" data-client="${esc(p.client)}" ${s.project === p.name ? 'selected' : ''}>${esc(p.name)} (${esc(p.client)})</option>`).join('');
  const isApprover = ['ceo', 'coordinator', 'lead'].includes(ME.role);
  openModal(script ? 'Ssenariy' : 'Yangi ssenariy', `
    <div class="field"><label>Sarlavha</label><input id="sf_title" value="${esc(s.title)}" /></div>
    <div class="field"><label>Loyiha</label><select id="sf_project"><option value="">—</option>${projOpts}</select></div>
    <div class="field"><label>Hook (diqqat)</label><textarea id="sf_hook" placeholder="Boshlanish...">${esc(s.hook)}</textarea></div>
    <div class="field"><label>Story (asosiy)</label><textarea id="sf_story" placeholder="Asosiy qism...">${esc(s.story)}</textarea></div>
    <div class="field"><label>CTA (chaqiriq)</label><textarea id="sf_cta" placeholder="Obuna bo'ling...">${esc(s.cta)}</textarea></div>
    <div class="field"><label>Google Docs / link</label><input id="sf_link" value="${esc(s.link)}" placeholder="https://docs.google..." /></div>
    ${script ? `<div class="sc-status">Holat: <span class="pill ${(SCRIPT_ST[s.status] || {}).cls}">${(SCRIPT_ST[s.status] || {}).dot} ${(SCRIPT_ST[s.status] || {}).label}</span>${s.approved_by ? ' · ✓ ' + esc(s.approved_by) : ''}</div>` : ''}
    ${script && isApprover ? `<div class="field" style="margin-top:12px"><label>🎓 Ekspert tasdig'i</label>
      <div class="seg"><button id="exp_no" class="${!s.expert_ok ? 'on-k' : ''}">Yo'q</button><button id="exp_yes" class="${s.expert_ok ? 'on-t' : ''}">Ha</button></div></div>` : ''}
    <div class="modal-actions">
      ${script ? '<button class="btn-del" id="sf_ver">Versiyalar</button>' : ''}
      <button class="btn-save" id="sf_save">${script ? 'Saqlash' : 'Yaratish'}</button>
    </div>`,
  () => {
    let expOk = s.expert_ok ? 1 : 0;
    if ($('#exp_yes')) { $('#exp_yes').addEventListener('click', () => { expOk = 1; $('#exp_yes').className = 'on-t'; $('#exp_no').className = ''; }); $('#exp_no').addEventListener('click', () => { expOk = 0; $('#exp_no').className = 'on-k'; $('#exp_yes').className = ''; }); }
    $('#sf_save').addEventListener('click', async () => {
      const sel = $('#sf_project'); const client = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].dataset.client || '' : '';
      const body = { title: $('#sf_title').value.trim() || 'Nomsiz', project: $('#sf_project').value, client,
        hook: $('#sf_hook').value, story: $('#sf_story').value, cta: $('#sf_cta').value, link: $('#sf_link').value };
      let saved;
      if (EDIT_S) saved = await api(`/api/scripts/${EDIT_S.id}`, { method: 'PUT', body: JSON.stringify(body) });
      else saved = await api('/api/scripts', { method: 'POST', body: JSON.stringify(body) });
      if (EDIT_S && $('#exp_yes')) await api(`/api/scripts/${EDIT_S.id}/action`, { method: 'POST', body: JSON.stringify({ action: 'expert', expert_ok: expOk, expert_note: '' }) });
      closeModal(); toast('✓ Saqlandi'); render();
    });
    if (script) $('#sf_ver').addEventListener('click', () => showVersions(script.id));
  });
}
async function showVersions(sid) {
  const vers = await api(`/api/scripts/${sid}/versions`);
  openModal('Versiyalar tarixi', `<div class="ver-list">${vers.map((v) => `
    <div class="ver-item"><div class="ver-head"><b>Version ${v.version}</b><span class="muted">${esc(v.edited_by)} · ${esc((v.created_at || '').slice(5, 16))}</span></div>
      ${v.hook ? `<div class="ver-line"><b>Hook:</b> ${esc(v.hook)}</div>` : ''}
      ${v.story ? `<div class="ver-line"><b>Story:</b> ${esc(v.story)}</div>` : ''}
      ${v.cta ? `<div class="ver-line"><b>CTA:</b> ${esc(v.cta)}</div>` : ''}</div>`).join('') || emptyState('Versiya yo\'q')}</div>`);
}

// ---- Video modal ----
async function openVideoModal() {
  if (!DATA.projects) DATA.projects = await api('/api/projects');
  if (!DATA.scripts) DATA.scripts = await api('/api/scripts');
  if (!DATA.team) DATA.team = await api('/api/team');
  const editors = DATA.team.filter((u) => u.role === 'editor');
  const projOpts = DATA.projects.map((p) => `<option value="${esc(p.name)}" data-client="${esc(p.client)}">${esc(p.name)} (${esc(p.client)})</option>`).join('');
  const scriptOpts = DATA.scripts.map((s) => `<option value="${s.id}">#${s.id} ${esc(s.title)}</option>`).join('');
  const editorField = ME.role === 'editor'
    ? `<input id="vf_editor" value="${esc(ME.name)}" disabled />`
    : `<select id="vf_editor"><option value="">—</option>${editors.map((e) => `<option>${esc(e.name)}</option>`).join('')}</select>`;
  openModal('Video topshirish', `
    <div class="field"><label>Video nomi</label><input id="vf_title" placeholder="masalan: Nova reels #12" /></div>
    <div class="field-row">
      <div class="field"><label>Loyiha</label><select id="vf_project"><option value="">—</option>${projOpts}</select></div>
      <div class="field"><label>Montajchi</label>${editorField}</div>
    </div>
    <div class="field"><label>Ssenariy (ixtiyoriy — zanjir uchun)</label><select id="vf_script"><option value="">— bog'lanmagan —</option>${scriptOpts}</select></div>
    <div class="field-row">
      <div class="field"><label>Sana</label><input id="vf_date" type="date" /></div>
      <div class="field"><label>Drive link</label><input id="vf_drive" placeholder="https://drive..." /></div>
    </div>
    <div class="field"><label>Izoh</label><textarea id="vf_note"></textarea></div>
    <div class="modal-actions"><button class="btn-save" id="vf_save">Topshirish</button></div>`,
  () => {
    $('#vf_save').addEventListener('click', async () => {
      const sel = $('#vf_project'); const client = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].dataset.client || '' : '';
      const body = { title: $('#vf_title').value.trim() || 'Nomsiz video', project: $('#vf_project').value, client,
        editor: ME.role === 'editor' ? ME.name : $('#vf_editor').value, script_id: $('#vf_script').value || null,
        vdate: $('#vf_date').value || null, drive_link: $('#vf_drive').value, note: $('#vf_note').value };
      await api('/api/videos', { method: 'POST', body: JSON.stringify(body) });
      closeModal(); toast('🎬 Topshirildi'); render();
    });
  });
}

// ---- Payment modal ----
async function openPaymentModal(presetEditor) {
  if (!DATA.team) DATA.team = await api('/api/team');
  const editors = DATA.team.filter((u) => u.role === 'editor');
  openModal('To\'lov qilish', `
    <div class="field"><label>Montajchi</label><select id="pmf_ed"><option value="">—</option>${editors.map((e) => `<option ${presetEditor === e.name ? 'selected' : ''}>${esc(e.name)}</option>`).join('')}</select></div>
    <div class="field"><label>Summa (so'm)</label><input id="pmf_amt" type="number" placeholder="300000" /></div>
    <div class="field"><label>Izoh</label><input id="pmf_note" placeholder="Nova va Aziza loyihalari uchun" /></div>
    <div class="field"><label>Sana</label><input id="pmf_date" type="date" /></div>
    <div class="modal-actions"><button class="btn-save" id="pmf_save">💸 To'lash</button></div>`,
  () => {
    $('#pmf_save').addEventListener('click', async () => {
      const editor = $('#pmf_ed').value; const amount = parseInt($('#pmf_amt').value || '0', 10);
      if (!editor || !amount) { toast('Montajchi va summa kiriting'); return; }
      await api('/api/payments', { method: 'POST', body: JSON.stringify({ editor, amount, note: $('#pmf_note').value, pdate: $('#pmf_date').value || null }) });
      closeModal(); toast('💸 To\'lov saqlandi'); render();
    });
  });
}

// pay button on editor cards (delegated)
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-pay]');
  if (b) openPaymentModal(b.dataset.pay);
});

// ============================================================
//  START
// ============================================================
tryRestore();
