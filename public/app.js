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
  biriktirildi:   { label: 'Montaj kerak',    cls: 'st-yellow' },
  montaj_qilindi: { label: 'Sifat nazoratida', cls: 'st-orange' },
  sifat_ok:       { label: 'Rahbar qabulida',  cls: 'st-blue' },
  qabul_qilindi:  { label: 'Qabul · joylashga', cls: 'st-green' },
  joylandi:       { label: 'Joylandi ✓',       cls: 'st-green' },
  qaytarildi:     { label: 'Qaytarildi',       cls: 'st-red' },
  bekor_qilindi:  { label: 'Bekor qilindi',    cls: 'st-gray' },
};
const VIDEO_TYPE_LABEL = { reels: 'Reels', podcast: 'Podcast', youtube: 'YouTube video' };
const STUDIO_ROOMS_DEFAULT = {
  white: { label: '1-xona · White', color: '#0A84FF' },
  black: { label: '2-xona · Black', color: '#1C1C1E' },
};
const SHOOT_TYPE_LABEL = { reels: 'Reels', podcast: 'Podcast', youtube: 'YouTube video', vebinar: 'Vebinar' };
// Studio broni kirita oladiganlar (faqat Dilshod va Gulmira)
const studioCanEdit = () => !!ME && ['Dilshod Khamraev', 'Gulmira'].includes(ME.name);

let ME = null;
let TOKEN = localStorage.getItem('km_token') || null;
let TIERS = {};
let RANKS = { ranks: [], prices: {}, step: 100 };
// Lavozim chipi (montajyor rangi/darajasi)
const rankChip = (v) => v && v.editor_rank_label
  ? `<span class="rank-chip rank-${esc(v.editor_rank)}">${v.editor_rank_icon || '🎖'} ${esc(v.editor_rank_label)}</span>` : '';
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
  try { RANKS = await api('/api/ranks'); } catch (e) { RANKS = { ranks: [], prices: {}, step: 100 }; }
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
  // SMM (Aisha) — faqat joylash
  { view: 'joylash',   icon: '📷', label: 'Joylash',      roles: ['smm'] },
  // Jamoa
  { view: 'dashboard', icon: '▦', label: 'Boshqaruv',     roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'projects',  icon: '▣', label: 'Loyihalar',     roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'scripts',   icon: '✎', label: 'Ssenariylar',   roles: ['ceo', 'coordinator', 'lead', 'editor'] },
  { view: 'videos',    icon: '►', label: 'Montaj',        roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'qc',        icon: '🔎', label: 'Sifat nazorati', roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'shoots',    icon: '📹', label: 'Syomkalar',     roles: ['ceo', 'coordinator', 'lead'] },
  { view: 'studio',    icon: '🎥', label: 'Kadr Studio',   roles: ['ceo', 'coordinator', 'lead'], names: ['Dilshod Khamraev', 'Gulmira', 'Xonzoda', 'Said'] },
  { view: 'myscripts', icon: '✍️', label: 'Ssenariylarim', roles: ['coordinator', 'editor', 'lead'], names: ['Xonzoda', 'Umida'] },
  { view: 'editors',   icon: '◍', label: 'Montajchilar',  roles: ['ceo'] },
  { view: 'finance',   icon: '₿', label: 'Moliya',        roles: ['ceo'] },
  { view: 'team',      icon: '◐', label: 'Jamoa',         roles: ['ceo'] },
  { view: 'audit',     icon: '≡', label: 'Audit',         roles: ['ceo'] },
];
const NAV_FOR = (role) => NAV_ITEMS.filter((n) => n.roles.includes(role) && (!n.names || (ME && n.names.includes(ME.name))));

const navMBtn = (n) => `<button class="m-btn" data-view="${n.view}"><span>${n.icon}</span>${n.label}</button>`;

function buildNav() {
  const items = NAV_FOR(ME.role);
  $('#navMenu').innerHTML = items.map((n) =>
    `<button class="nav-btn" data-view="${n.view}"><span class="ic">${n.icon}</span> ${n.label}</button>`
  ).join('');
  // mobil pastki menyu: 5 tadan ko'p bo'lsa — 4 ta + "Ko'proq" (qolgan bo'limlar shu yerda)
  $('#mobileNav').innerHTML = items.length <= 5
    ? items.map(navMBtn).join('')
    : items.slice(0, 4).map(navMBtn).join('') + `<button class="m-btn" data-more="1"><span>⋯</span>Ko'proq</button>`;
  document.querySelectorAll('.nav-btn, .m-btn[data-view]').forEach((b) =>
    b.addEventListener('click', () => { VIEW = b.dataset.view; FILTER = 'all'; SEARCH = ''; render(); })
  );
  const moreBtn = document.querySelector('#mobileNav .m-btn[data-more]');
  if (moreBtn) moreBtn.addEventListener('click', openMoreMenu);
}
function openMoreMenu() {
  const items = NAV_FOR(ME.role);
  const list = items.map((n) =>
    `<button class="more-item${VIEW === n.view ? ' active' : ''}" data-view="${n.view}"><span class="ic">${n.icon}</span> ${n.label}</button>`
  ).join('');
  openModal('Menyu', `<div class="more-menu">${list}</div>`, () => {
    $('#modalBody').querySelectorAll('.more-item').forEach((b) => b.addEventListener('click', () => {
      VIEW = b.dataset.view; FILTER = 'all'; SEARCH = ''; closeModal(); render();
    }));
  });
}
function setActiveNav() {
  document.querySelectorAll('.nav-btn, .m-btn').forEach((b) => b.classList.toggle('active', b.dataset.view === VIEW));
  const more = document.querySelector('#mobileNav .m-btn[data-more]');
  if (more) {
    const visible = Array.from(document.querySelectorAll('#mobileNav .m-btn[data-view]')).some((b) => b.dataset.view === VIEW);
    more.classList.toggle('active', !visible);
  }
}

// ============================================================
//  RENDER ROUTER
// ============================================================
const TITLES = {
  dashboard: ['Boshqaruv paneli', 'Bugungi holat — bir qarashda'],
  projects:  ['Loyihalar', 'Barcha loyihalar'],
  scripts:   ['Ssenariylar', 'Yozish, tasdiqlash, versiyalar'],
  videos:    ['Montaj — videolar', 'Biriktirish va qabul qilish'],
  qc:        ['Sifat nazorati', 'Montaj qilingan, tasdiq kutayotgan videolar'],
  shoots:    ['Syomkalar', 'Loyiha syomkalari — operator va pul'],
  myscripts: ['Ssenariylarim', 'Tasdiqlangan ssenariylar va hisoblangan pul'],
  studio:    ['Kadr Studio', 'Syomka xonalari bandligi va bronlar'],
  joylash:   ['Joylash (SMM)', 'Tayyor videolarni Instagram\'ga joylash'],
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
    else if (VIEW === 'myvideos' || VIEW === 'cvideos' || VIEW === 'joylash') await viewVideos();
    else if (VIEW === 'qc') await viewQC();
    else if (VIEW === 'shoots') await viewShoots();
    else if (VIEW === 'myscripts') await viewScenarist();
    else if (VIEW === 'studio') await viewStudio();
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
  const canSearch = ['projects', 'scripts', 'videos', 'qc', 'shoots', 'joylash', 'editors', 'client', 'cscripts', 'cvideos', 'myvideos'].includes(VIEW);
  if (canSearch) html += `<div class="search-box"><span>⌕</span><input id="searchInput" placeholder="Qidirish..." value="${esc(SEARCH)}" /></div>`;
  const role = ME.role;
  if ((VIEW === 'projects') && ['ceo', 'coordinator', 'lead'].includes(role)) html += `<button class="btn-primary" data-act="add-project">+ Loyiha</button>`;
  if ((VIEW === 'scripts') && role !== 'client') html += `<button class="btn-primary" data-act="add-script">+ Ssenariy</button>`;
  if (VIEW === 'videos' && ['ceo', 'coordinator', 'lead'].includes(role)) html += `<button class="btn-primary" data-act="add-video">+ Video biriktirish</button>`;
  if (VIEW === 'shoots' && ['ceo', 'coordinator', 'lead'].includes(role)) html += `<button class="btn-primary" data-act="add-shoot">+ Syomka</button>`;
  if (VIEW === 'myscripts') html += `<button class="btn-primary" data-act="add-scenarist">+ Ssenariy</button>`;
  if (VIEW === 'finance') html += `<button class="btn-primary" data-act="add-payment">+ To'lov</button>`;
  if (VIEW === 'studio') {
    if (studioCanEdit()) html += `<button class="btn-ghost" data-act="studio-expenses">🧾 Xarajatlar</button>`;
    if (studioCanEdit()) html += `<button class="btn-ghost" data-act="studio-finance">💰 Pul hisoboti</button>`;
    if (studioCanEdit()) html += `<button class="btn-primary" data-act="add-booking">+ Bron qilish</button>`;
  }
  a.innerHTML = html;
  if (canSearch) $('#searchInput').addEventListener('input', (e) => { SEARCH = e.target.value.toLowerCase(); render(); });
  a.querySelectorAll('[data-act]').forEach((b) => b.addEventListener('click', () => {
    const act = b.dataset.act;
    if (act === 'add-project') openProjectModal(null);
    if (act === 'add-script') openScriptModal(null);
    if (act === 'add-video') openVideoModal();
    if (act === 'add-shoot') openShootModal();
    if (act === 'add-scenarist') openScenaristModal();
    if (act === 'add-payment') openPaymentModal();
    if (act === 'add-booking') openStudioBookingModal();
    if (act === 'studio-finance') openStudioFinanceModal();
    if (act === 'studio-expenses') openStudioExpensesModal();
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
      ${statTile('📷', stats.readyToPost || 0, 'Joylash kutmoqda', 'orange')}
      ${statTile('✅', stats.postedCount || 0, 'Joylandi ✓', 'green')}
    </div>
    <div class="section-head"><h3>Loyihalar</h3></div>
    <div class="cards-grid">${projects.map(projectCard).join('') || emptyState()}</div>`;
  bindProjectCards();
}

// ---------- PROJECTS ----------
async function viewProjects() {
  const projects = await api('/api/projects' + '');
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
  const [scripts, stats] = await Promise.all([api('/api/scripts' + ''), (ME.role !== 'client' ? api('/api/script-stats') : Promise.resolve([]))]);
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
  const videos = await api('/api/videos' + (VIEW === 'videos' ? '' : ''));
  DATA.videos = videos;
  let list = videos.filter((v) => matchSearch(v.title + ' ' + v.project + ' ' + v.editor));
  if (Object.keys(VIDEO_ST).includes(FILTER)) list = list.filter((v) => v.status === FILTER);
  const chips = (VIEW === 'joylash')
    ? [['all', 'Hammasi'], ['qabul_qilindi', 'Joylash kerak'], ['joylandi', 'Joylandi']]
    : [['all', 'Hammasi'], ['biriktirildi', 'Montaj kerak'], ['montaj_qilindi', 'Sifatda'], ['sifat_ok', 'Qabulda'], ['qabul_qilindi', 'Qabul qilingan'], ['qaytarildi', 'Qaytgan']];
  $('#content').innerHTML = `
    <div class="filter-row">${chips.map(([k, l]) => `<button class="chip ${FILTER === k ? 'active' : ''}" data-f="${k}">${l}</button>`).join('')}</div>
    <div class="cards-grid">${list.map(videoCard).join('') || emptyState('Video yo\'q')}</div>`;
  bindVideoCards();
}

async function viewQC() {
  const videos = await api('/api/qc');
  DATA.videos = videos;
  const list = videos.filter((v) => matchSearch(v.title + ' ' + v.project + ' ' + v.editor));
  $('#content').innerHTML = `
    <p class="muted" style="margin-bottom:16px">🔎 Montaj qilingan, sifat nazorati kutayotgan videolar. Ko'rib, tasdiqlang yoki qaytaring.</p>
    <div class="cards-grid">${list.map(videoCard).join('') || emptyState('Tekshirish uchun video yo\'q ✓')}</div>`;
  bindVideoCards();
}

function bindVideoCards() {
  $('#content').querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => { FILTER = c.dataset.f; render(); }));
  $('#content').querySelectorAll('[data-vact]').forEach((b) => b.addEventListener('click', (e) => {
    e.stopPropagation();
    videoActionUI(b.dataset.id, b.dataset.vact);
  }));
  if (['ceo', 'coordinator', 'lead', 'smm'].includes(ME.role)) {
    $('#content').querySelectorAll('.video-card.clickable').forEach((card) => {
      card.addEventListener('click', () => {
        const v = (DATA.videos || []).find((x) => x.id == card.dataset.vid);
        if (v) openVideoDetailModal(v);
      });
    });
  }
}

function videoActions(v) {
  const role = ME.role;
  const isApprover = ['ceo', 'coordinator', 'lead'].includes(role);
  const b = [];
  if ((v.editor === ME.name || ['ceo', 'coordinator'].includes(role)) && (v.status === 'biriktirildi' || v.status === 'qaytarildi'))
    b.push(`<button class="mini-btn blue" data-vact="montaj_done" data-id="${v.id}">✓ Montaj qildim</button>`);
  if (isApprover && (v.status === 'biriktirildi' || v.status === 'qaytarildi'))
    b.push(`<button class="mini-btn gray" data-vact="cancel" data-id="${v.id}">🚫 Bekor qilish</button>`);
  if (isApprover && v.status === 'montaj_qilindi') {
    b.push(`<button class="mini-btn green" data-vact="qc_ok" data-id="${v.id}">✓ Sifat OK</button>`);
    b.push(`<button class="mini-btn red" data-vact="qc_return" data-id="${v.id}">↩ Qaytar</button>`);
  }
  if (isApprover && v.status === 'sifat_ok') {
    b.push(`<button class="mini-btn green" data-vact="accept" data-id="${v.id}">✓ Qabul (pul)</button>`);
    b.push(`<button class="mini-btn red" data-vact="return" data-id="${v.id}">↩ Qaytar</button>`);
  }
  if (['smm', 'ceo', 'coordinator'].includes(role) && v.status === 'qabul_qilindi')
    b.push(`<button class="mini-btn blue" data-vact="posted" data-id="${v.id}">📷 Joyladim</button>`);
  return b.join('');
}

function videoCard(v) {
  const st = VIDEO_ST[v.status] || VIDEO_ST.biriktirildi;
  const who = [];
  if (v.assigned_by) who.push('🎬 ' + esc(v.assigned_by));
  if (v.qc_by) who.push('🔎 ' + esc(v.qc_by));
  if (v.approved_by) who.push('✓ ' + esc(v.approved_by));
  if (v.posted_by) who.push('📷 ' + esc(v.posted_by));
  const isClickable = ['ceo', 'coordinator', 'lead', 'smm'].includes(ME.role);
  return `
    <div class="video-card${isClickable ? ' clickable' : ''}" data-vid="${v.id}">
      <div class="pc-top"><div class="pc-name">${esc(v.title)}</div><span class="pill ${st.cls}">${st.label}</span></div>
      <div class="pc-client">📁 ${esc(v.project) || '—'} · 🎬 ${esc(v.editor) || '—'}</div>
      <div class="video-meta">
        <span class="link-chip">🎞 ${esc(VIDEO_TYPE_LABEL[v.vtype] || 'Reels')}</span>
        ${rankChip(v)}
        ${(v.pay_visible && v.amount) ? `<span class="money-chip">💰 ${money(v.amount)}</span>` : ''}
        ${v.drive_link ? `<span class="link-chip">🔗 Drive</span>` : ''}
        ${v.instagram_link ? `<span class="link-chip">📷 Instagram</span>` : ''}
      </div>
      ${v.note ? `<div class="pc-problem soft">📝 ${esc(v.note)}</div>` : ''}
      <div class="pc-foot"><div class="muted">📅 ${fmtDate(v.vdate)}${who.length ? ' · ' + who.join(' ') : ''}</div>
        <div class="card-actions">${videoActions(v)}</div></div>
    </div>`;
}

async function doVideoAction(id, body, msg) {
  await api(`/api/videos/${id}/action`, { method: 'POST', body: JSON.stringify(body) });
  closeModal(); toast(msg); render();
}

function videoActionUI(id, action) {
  if (action === 'accept') {
    const v = (DATA.videos || []).find((x) => x.id == id) || {};
    const vtype = v.vtype || 'reels';
    const rankLine = v.editor_rank_label
      ? `<div class="mrow"><span>🎖 Montajyor lavozimi</span><b>${v.editor_rank_icon || ''} ${esc(v.editor_rank_label)}</b></div>` : '';
    const payLine = (v.pay_visible && v.amount)
      ? `<div class="mrow"><span>💰 Hisoblanadigan haq</span><b>${money(v.amount)}</b></div>`
      : `<div class="muted" style="margin:8px 0">Pul montajyor lavozimiga qarab avtomatik hisoblanadi.</div>`;
    openModal('Videoni qabul qilish', `
      <p class="muted" style="margin-bottom:12px">Tasdiqlasangiz, pul montajyorga avtomatik yoziladi.</p>
      <div class="money-rows" style="margin-bottom:14px">
        <div class="mrow"><span>🎬 Montajchi</span><b>${esc(v.editor || '—')}</b></div>
        <div class="mrow"><span>🎞 Video turi</span><b>${esc(VIDEO_TYPE_LABEL[vtype] || 'Reels')}</b></div>
        ${rankLine}
        ${payLine}
      </div>
      <button class="btn-save" id="vaccept" style="background:var(--green)">✓ Qabul qilish</button>`, () => {
      $('#vaccept').addEventListener('click', () => doVideoAction(id, { action: 'accept' }, '✅ Qabul qilindi — pul hisoblandi'));
    });
  } else if (action === 'cancel') {
    openModal('Biriktirishni bekor qilish', `<p class="muted" style="margin-bottom:12px">Bu video "Bekor qilindi" deb belgilanadi (yozuv tarixda qoladi).</p><div class="field"><label>Sabab (ixtiyoriy)</label><textarea id="vcnote" placeholder="Nega bekor qilinmoqda..."></textarea></div><button class="btn-save" id="vcbtn" style="background:var(--red)">🚫 Bekor qilish</button>`, () => {
      $('#vcbtn').addEventListener('click', () => doVideoAction(id, { action: 'cancel', note: $('#vcnote').value }, '🚫 Bekor qilindi'));
    });
  } else if (action === 'montaj_done') {
    openModal('Montajni topshirish', `<div class="field"><label>Drive link (tayyor video)</label><input id="vdl" placeholder="https://drive.google..." /></div><div class="field"><label>Izoh (ixtiyoriy)</label><textarea id="vdn"></textarea></div><button class="btn-save" id="vdb">✓ Montaj qildim · sifatga yuborish</button>`, () => {
      $('#vdb').addEventListener('click', () => doVideoAction(id, { action: 'montaj_done', drive_link: $('#vdl').value, note: $('#vdn').value }, '🎞 Sifat nazoratiga yuborildi'));
    });
  } else if (action === 'qc_ok') {
    api(`/api/videos/${id}/action`, { method: 'POST', body: JSON.stringify({ action: 'qc_ok' }) }).then(() => { toast('✓ Sifat tasdiqlandi'); render(); });
  } else if (action === 'qc_return' || action === 'return') {
    openModal('Videoni qaytarish', `<div class="field"><label>Qaytarish sababi</label><textarea id="vrnote" placeholder="Nima tuzatish kerak..."></textarea></div><button class="btn-save" id="vrbtn">Qaytarish</button>`, () => {
      $('#vrbtn').addEventListener('click', () => doVideoAction(id, { action, note: $('#vrnote').value }, '↩ Qaytarildi'));
    });
  } else if (action === 'posted') {
    openModal('Instagram\'ga joylash', `<div class="field"><label>Instagram post linki</label><input id="iglink" placeholder="https://instagram.com/..." /></div><button class="btn-save" id="igbtn">✓ Joyladim</button>`, () => {
      $('#igbtn').addEventListener('click', () => doVideoAction(id, { action: 'posted', instagram_link: $('#iglink').value }, '📷 Instagram\'ga joylandi'));
    });
  }
}

function openVideoDetailModal(v) {
  const st = VIDEO_ST[v.status] || VIDEO_ST.biriktirildi;
  const chain = [];
  if (v.assigned_by) chain.push(`<div class="mrow"><span>🎬 Biriktirgan</span><b>${esc(v.assigned_by)}</b></div>`);
  if (v.qc_by) chain.push(`<div class="mrow"><span>🔎 Sifat nazorat</span><b>${esc(v.qc_by)}</b></div>`);
  if (v.approved_by) chain.push(`<div class="mrow"><span>✓ Qabul qilgan</span><b>${esc(v.approved_by)}</b></div>`);
  if (v.posted_by) chain.push(`<div class="mrow"><span>📷 Joylagan</span><b>${esc(v.posted_by)}</b></div>`);
  const driveBtn = v.drive_link
    ? `<a href="${esc(v.drive_link)}" target="_blank" rel="noopener" class="btn-drive">🎞 Videoni ko'rish (Drive)</a>`
    : '<div class="muted" style="margin:10px 0">Drive link hali kiritilmagan</div>';
  const actions = videoActions(v);
  openModal(v.title, `
    <div style="margin-bottom:10px"><span class="pill ${st.cls}">${st.label}</span></div>
    <div class="money-rows" style="margin-bottom:12px">
      <div class="mrow"><span>📁 Loyiha</span><b>${esc(v.project || '—')}</b></div>
      <div class="mrow"><span>🎞 Video turi</span><b>${esc(VIDEO_TYPE_LABEL[v.vtype] || 'Reels')}</b></div>
      <div class="mrow"><span>🎬 Montajchi</span><b>${esc(v.editor || '—')}${v.editor_rank_label ? ` · ${v.editor_rank_icon || ''} ${esc(v.editor_rank_label)}` : ''}</b></div>
      <div class="mrow"><span>📅 Sana</span><b>${fmtDate(v.vdate)}</b></div>
      ${(v.pay_visible && v.amount) ? `<div class="mrow"><span>💰 Haq (lavozim bo'yicha)</span><b>${money(v.amount)}</b></div>` : ''}
      ${chain.join('')}
    </div>
    ${v.note ? `<div class="pc-problem soft" style="margin-bottom:12px">📝 ${esc(v.note)}</div>` : ''}
    ${driveBtn}
    ${v.instagram_link ? `<a href="${esc(v.instagram_link)}" target="_blank" rel="noopener" class="link-chip" style="display:inline-block;margin-bottom:12px">📷 Instagram post</a>` : ''}
    ${actions ? `<div class="modal-actions">${actions}</div>` : ''}
  `, () => {
    $('#modalBody').querySelectorAll('[data-vact]').forEach((b) =>
      b.addEventListener('click', () => { closeModal(); videoActionUI(b.dataset.id, b.dataset.vact); })
    );
  });
}

// ============================================================
//  KADR STUDIO — syomka bronlari (kalendar)
// ============================================================
let STUDIO_MONTH = null;

function studioHours(start, end) {
  if (!start || !end) return 0;
  const [sh, sm] = start.split(':').map(Number);
  const [eh, em] = end.split(':').map(Number);
  let mins = (eh * 60 + em) - (sh * 60 + sm);
  if (mins <= 0) mins += 1440;
  return Math.round(mins / 60 * 100) / 100;
}

async function viewStudio() {
  const data = await api('/api/studio');
  DATA.studio = data;
  const rooms = data.rooms || STUDIO_ROOMS_DEFAULT;
  if (!STUDIO_MONTH) { const t = new Date(); STUDIO_MONTH = { y: t.getFullYear(), m: t.getMonth() }; }
  const { y, m } = STUDIO_MONTH;
  const UZ_MONTH_FULL = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr'];
  const byDate = {};
  data.bookings.forEach((b) => { (byDate[b.bdate] = byDate[b.bdate] || []).push(b); });
  const first = new Date(y, m, 1);
  const startDow = (first.getDay() + 6) % 7; // dushanba = 0
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const now = new Date();
  const todayISO = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const legend = Object.entries(rooms).map(([, r]) =>
    `<span class="room-tag"><i style="background:${r.color}"></i>${esc(r.label)}</span>`).join('');
  const wd = ['Du', 'Se', 'Cho', 'Pa', 'Ju', 'Sha', 'Ya'];
  let cells = wd.map((d) => `<div class="cal-wd">${d}</div>`).join('');
  for (let i = 0; i < startDow; i++) cells += `<div class="cal-cell empty"></div>`;
  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${y}-${String(m + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const list = (byDate[iso] || []).slice().sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));
    const pills = list.map((b) => {
      const cancelled = b.status === 'bekor_qilindi';
      const rc = cancelled ? '#6b6b72' : ((rooms[b.room] || {}).color || '#888');
      return `<div class="cal-ev${b.paid ? '' : ' unpaid'}${cancelled ? ' cancelled' : ''}" data-bk="${b.id}" style="background:${rc}" title="${esc(b.client_name || '')}">${esc((b.start_time || '').slice(0, 5))} ${esc(b.client_name || '')}</div>`;
    }).join('');
    cells += `<div class="cal-cell${iso === todayISO ? ' today' : ''}" data-day="${iso}"><div class="cal-daynum">${day}</div>${pills}</div>`;
  }
  $('#content').innerHTML = `
    <div class="cal-toolbar">
      <button class="btn-ghost" data-cal="prev">‹</button>
      <h3 class="cal-title">${UZ_MONTH_FULL[m]} ${y}</h3>
      <button class="btn-ghost" data-cal="next">›</button>
      <button class="btn-ghost" data-cal="today">Bugun</button>
      <div class="cal-legend">${legend}</div>
    </div>
    <div class="cal-grid">${cells}</div>
    <p class="muted" style="margin-top:12px">📌 Kun ustiga bossangiz — o'sha kundagi bronlar ro'yxati ochiladi. Bron ustiga bossangiz — tafsiloti.</p>`;
  $('#content').querySelectorAll('[data-cal]').forEach((b) => b.addEventListener('click', () => {
    const a = b.dataset.cal;
    if (a === 'prev') { STUDIO_MONTH.m--; if (STUDIO_MONTH.m < 0) { STUDIO_MONTH.m = 11; STUDIO_MONTH.y--; } }
    else if (a === 'next') { STUDIO_MONTH.m++; if (STUDIO_MONTH.m > 11) { STUDIO_MONTH.m = 0; STUDIO_MONTH.y++; } }
    else if (a === 'today') { const t = new Date(); STUDIO_MONTH = { y: t.getFullYear(), m: t.getMonth() }; }
    render();
  }));
  $('#content').querySelectorAll('.cal-cell[data-day]').forEach((c) => c.addEventListener('click', (e) => {
    if (e.target.closest('.cal-ev')) return;
    openStudioDayModal(c.dataset.day);
  }));
  $('#content').querySelectorAll('.cal-ev').forEach((ev) => ev.addEventListener('click', (e) => {
    e.stopPropagation();
    const b = data.bookings.find((x) => x.id == ev.dataset.bk);
    if (b) openStudioDetailModal(b);
  }));
}

// Kun ustiga bosilganda — o'sha kundagi bronlar ro'yxati
function openStudioDayModal(iso) {
  const data = DATA.studio || { bookings: [], rooms: STUDIO_ROOMS_DEFAULT };
  const rooms = data.rooms || STUDIO_ROOMS_DEFAULT;
  const list = (data.bookings || []).filter((b) => b.bdate === iso)
    .sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));
  const rows = list.map((b) => {
    const room = rooms[b.room] || {};
    const cancelled = b.status === 'bekor_qilindi';
    const st = SHOOT_TYPE_LABEL[b.shoot_type] || '';
    const badge = cancelled ? ['red', 'bekor'] : (b.paid ? ['green', "to'landi"] : ['orange', 'qarz']);
    return `<button class="day-row${cancelled ? ' cancelled' : ''}" data-bk="${b.id}">
      <span class="dr-time">${esc((b.start_time || '').slice(0, 5))}–${esc((b.end_time || '').slice(0, 5))}</span>
      <span class="dr-dot" style="background:${cancelled ? '#6b6b72' : (room.color || '#888')}"></span>
      <span class="dr-main"><b>${esc(b.client_name || '')}</b><span class="muted"> · ${esc(st)}${b.operator ? ' · 👤 ' + esc(b.operator) : ''}</span></span>
      <span class="pill ${badge[0]}">${badge[1]}</span>
    </button>`;
  }).join('') || '<div class="muted" style="padding:10px 0">Bu kunda bron yo\'q</div>';
  const addBtn = studioCanEdit() ? `<button class="btn-save" id="day_add" style="margin-top:14px">+ Yangi bron</button>` : '';
  openModal(`📅 ${fmtDate(iso)} — bronlar (${list.length})`, `<div class="day-list">${rows}</div>${addBtn}`, () => {
    $('#modalBody').querySelectorAll('.day-row').forEach((r) => r.addEventListener('click', () => {
      const b = (data.bookings || []).find((x) => x.id == r.dataset.bk);
      if (b) openStudioDetailModal(b);
    }));
    const add = $('#day_add');
    if (add) add.addEventListener('click', () => openStudioBookingModal(iso));
  });
}

function openStudioBookingModal(presetDate) {
  const data = DATA.studio || {};
  const rooms = data.rooms || STUDIO_ROOMS_DEFAULT;
  const operators = data.operators || ['Said', 'Umid'];
  const shootTypes = data.shootTypes || SHOOT_TYPE_LABEL;
  const opPay = data.operatorPay || { reels: 50000, podcast: 100000, youtube: 50000, vebinar: 200000 };
  const roomOpts = Object.entries(rooms).map(([k, r]) => `<option value="${k}">${esc(r.label)}</option>`).join('');
  const typeOpts = Object.entries(shootTypes).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join('');
  const opOpts = `<option value="">— operator yo'q —</option>` + operators.map((o) => `<option>${esc(o)}</option>`).join('');
  openModal('Kadr Studio — bron qilish', `
    <div class="field"><label>Mijoz ismi</label><input id="sb_name" placeholder="Mijoz ismi" /></div>
    <div class="field-row">
      <div class="field"><label>Telefon</label><input id="sb_phone" placeholder="+998 90 123 45 67" /></div>
      <div class="field"><label>Xona</label><select id="sb_room">${roomOpts}</select></div>
    </div>
    <div class="field-row">
      <div class="field"><label>Syomka turi</label><select id="sb_type">${typeOpts}</select></div>
      <div class="field"><label>Operator</label><select id="sb_op">${opOpts}</select></div>
    </div>
    <div id="sb_oppay" class="calc-line"></div>
    <div class="field"><label>Sana</label><input id="sb_date" type="date" value="${presetDate || ''}" /></div>
    <div class="field-row">
      <div class="field"><label>Boshlanish</label><input id="sb_start" type="time" value="10:00" /></div>
      <div class="field"><label>Tugash</label><input id="sb_end" type="time" value="12:00" /></div>
    </div>
    <div id="sb_hours" class="calc-line"></div>
    <div class="field-row">
      <div class="field"><label>Umumiy to'lov (so'm)</label><input id="sb_amount" type="number" inputmode="numeric" placeholder="masalan: 900000" /></div>
      <div class="field"><label>To'langan / avans (so'm)</label><input id="sb_paidamt" type="number" inputmode="numeric" placeholder="0" /></div>
    </div>
    <div class="field"><label>Izoh</label><textarea id="sb_note" placeholder="masalan: 2 kishi, rekvizit kerak"></textarea></div>
    <div class="modal-actions"><button class="btn-save" id="sb_save">🎥 Bron qilish</button></div>`,
  () => {
    const showHours = () => {
      const h = studioHours($('#sb_start').value, $('#sb_end').value);
      $('#sb_hours').innerHTML = h > 0 ? `⏱ Soati — <b>${h} soat</b>` : `<span class="muted">Vaqtni to'g'ri kiriting</span>`;
    };
    const showOpPay = () => {
      const op = $('#sb_op').value; const t = $('#sb_type').value;
      $('#sb_oppay').innerHTML = op
        ? `👤 ${esc(op)} operatorga hisoblanadi: <b>${money(opPay[t] || 0)}</b>`
        : `<span class="muted">Operator tanlanmasa — operator puli hisoblanmaydi</span>`;
    };
    ['sb_start', 'sb_end'].forEach((id) => $('#' + id).addEventListener('input', showHours));
    ['sb_op', 'sb_type'].forEach((id) => $('#' + id).addEventListener('change', showOpPay));
    showHours(); showOpPay();
    $('#sb_save').addEventListener('click', async () => {
      const name = $('#sb_name').value.trim();
      if (!name) { toast('Mijoz ismini kiriting'); return; }
      const bdate = $('#sb_date').value;
      if (!bdate) { toast('Sanani tanlang'); return; }
      const body = {
        client_name: name, phone: $('#sb_phone').value, room: $('#sb_room').value,
        shoot_type: $('#sb_type').value, operator: $('#sb_op').value,
        bdate, start_time: $('#sb_start').value, end_time: $('#sb_end').value,
        amount: parseInt($('#sb_amount').value || '0', 10),
        paid_amount: parseInt($('#sb_paidamt').value || '0', 10),
        note: $('#sb_note').value,
      };
      await api('/api/studio', { method: 'POST', body: JSON.stringify(body) });
      closeModal(); toast('🎥 Bron saqlandi'); render();
    });
  });
}

function openStudioDetailModal(b) {
  const data = DATA.studio || {};
  const rooms = data.rooms || STUDIO_ROOMS_DEFAULT;
  const room = rooms[b.room] || { label: b.room };
  const cancelled = b.status === 'bekor_qilindi';
  const total = b.amount || 0; const paid = b.paid_amount || 0; const rem = Math.max(total - paid, 0);
  const st = (data.shootTypes && data.shootTypes[b.shoot_type]) || SHOOT_TYPE_LABEL[b.shoot_type] || '—';
  const canEdit = studioCanEdit();
  let actions = '';
  if (canEdit && cancelled) {
    actions = `<button class="mini-btn red" id="sb_delbtn">🗑 O'chirish</button>`;
  } else if (canEdit) {
    actions = `${rem > 0 ? `<button class="mini-btn green" id="sb_paybtn">+ To'lov qo'shish</button>` : ''}
      <button class="mini-btn gray" id="sb_cancelbtn">🚫 Bekor qilish</button>
      <button class="mini-btn red" id="sb_delbtn">🗑 O'chirish</button>`;
  }
  openModal(`Bron · ${esc(b.client_name || '')}`, `
    ${cancelled ? `<div class="pill st-red" style="display:inline-block;margin-bottom:10px">🚫 Bekor qilindi</div>` : ''}
    <div class="money-rows" style="margin-bottom:12px">
      <div class="mrow"><span>🏠 Xona</span><b>${esc(room.label)}</b></div>
      <div class="mrow"><span>🎬 Syomka turi</span><b>${esc(st)}</b></div>
      ${b.operator ? `<div class="mrow"><span>👤 Operator</span><b>${esc(b.operator)}${cancelled ? '' : ` · ${money(b.operator_pay)}`}</b></div>` : ''}
      <div class="mrow"><span>📅 Sana</span><b>${fmtDate(b.bdate)}</b></div>
      <div class="mrow"><span>⏱ Vaqt</span><b>${esc((b.start_time || '').slice(0, 5))}–${esc((b.end_time || '').slice(0, 5))} · ${b.hours} soat</b></div>
      <div class="mrow"><span>📞 Telefon</span><b>${esc(b.phone || '—')}</b></div>
      <div class="mrow" style="border-top:1px solid var(--border);padding-top:6px"><span>💰 Umumiy</span><b>${money(total)}</b></div>
      <div class="mrow"><span style="color:var(--green)">To'langan</span><b style="color:var(--green)">${money(paid)}</b></div>
      <div class="mrow"><span style="color:var(--orange)">Qolgan</span><b style="color:var(--orange)">${money(rem)}</b></div>
      <div class="mrow"><span>👮 Bron qildi</span><b>${esc(b.created_by || '—')}</b></div>
    </div>
    ${b.note ? `<div class="pc-problem soft" style="margin-bottom:12px">📝 ${esc(b.note)}</div>` : ''}
    ${actions ? `<div class="modal-actions">${actions}</div>` : ''}`,
  () => {
    const pay = $('#sb_paybtn');
    if (pay) pay.addEventListener('click', () => openStudioPayModal(b, rem));
    const cn = $('#sb_cancelbtn');
    if (cn) cn.addEventListener('click', async () => {
      if (!confirm('Syomkani bekor qilasizmi? Operatorga pul hisoblanmaydi.')) return;
      await api(`/api/studio/${b.id}/cancel`, { method: 'POST', body: '{}' });
      closeModal(); toast('🚫 Bekor qilindi'); render();
    });
    const del = $('#sb_delbtn');
    if (del) del.addEventListener('click', async () => {
      if (!confirm('Butunlay o\'chirasizmi?')) return;
      await api(`/api/studio/${b.id}`, { method: 'DELETE' });
      closeModal(); toast('O\'chirildi'); render();
    });
  });
}

function openStudioPayModal(b, rem) {
  openModal('To\'lov qo\'shish', `
    <p class="muted" style="margin-bottom:10px">Qolgan summa: <b>${money(rem)}</b></p>
    <div class="field"><label>Qo'shiladigan to'lov (so'm)</label><input id="pay_amt" type="number" inputmode="numeric" value="${rem}" /></div>
    <button class="btn-save" id="pay_ok">✅ To'lovni qo'shish</button>`, () => {
    $('#pay_ok').addEventListener('click', async () => {
      const a = parseInt($('#pay_amt').value || '0', 10);
      if (a <= 0) { toast('Summani kiriting'); return; }
      await api(`/api/studio/${b.id}/pay`, { method: 'POST', body: JSON.stringify({ amount: a }) });
      closeModal(); toast('💰 To\'lov qo\'shildi'); render();
    });
  });
}

async function openStudioFinanceModal() {
  const f = await api('/api/studio/finance');
  const rooms = f.rooms || STUDIO_ROOMS_DEFAULT;
  const rows = f.months.map((mo) => `
    <div class="fin-month">
      <div class="fm-head"><b>${esc(mo.month)}</b><span class="muted">${mo.count} bron</span></div>
      <div class="mrow"><span>${esc(rooms.white.label)}</span><b>${money(mo.white)}</b></div>
      <div class="mrow"><span>${esc(rooms.black.label)}</span><b>${money(mo.black)}</b></div>
      <div class="mrow" style="border-top:1px solid var(--border);padding-top:6px"><span>Tushum</span><b>${money(mo.total)}</b></div>
      <div class="mrow"><span style="color:var(--pink)">Operator puli</span><b style="color:var(--pink)">−${money(mo.operatorPay)}</b></div>
      <div class="mrow"><span style="color:var(--pink)">Xarajatlar</span><b style="color:var(--pink)">−${money(mo.expenses)}</b></div>
      <div class="mrow"><span>Sof foyda</span><b>${money(mo.net)}</b></div>
      <div class="mrow"><span style="color:var(--green)">To'langan</span><b style="color:var(--green)">${money(mo.paid)}</b></div>
      <div class="mrow"><span style="color:var(--orange)">Qarz</span><b style="color:var(--orange)">${money(mo.debt)}</b></div>
    </div>`).join('') || '<div class="muted">Hali bron yo\'q</div>';
  openModal('🎥 Kadr Studio — pul hisoboti', `
    <div class="stats-grid" style="margin-bottom:14px">
      ${statTile('💰', money(f.totalAll), 'Jami tushum', 'blue')}
      ${statTile('👤', money(f.operatorPayAll), 'Operator puli', 'purple')}
      ${statTile('🧾', money(f.expensesAll || 0), 'Xarajatlar', 'orange')}
      ${statTile('📈', money(f.netAll), 'Sof foyda', 'green')}
    </div>
    <div class="fin-months">${rows}</div>`);
}

async function openStudioExpensesModal() {
  const f = await api('/api/studio/expenses');
  const names = f.names || [];
  const nameOpts = names.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join('') + `<option value="__other">Boshqa harajat...</option>`;
  const list = (f.expenses || []).map((e) => `
    <div class="day-row" style="cursor:default">
      <span class="dr-main"><b>${esc(e.name)}</b>${e.note ? `<span class="muted"> · ${esc(e.note)}</span>` : ''}<div class="muted" style="font-size:12px">📅 ${fmtDate(e.edate)} · ${esc(e.created_by || '')}</div></span>
      <b style="color:var(--pink)">−${money(e.amount)}</b>
      <button class="mini-btn red" data-expdel="${e.id}">🗑</button>
    </div>`).join('') || '<div class="muted" style="padding:8px 0">Hali xarajat yo\'q</div>';
  openModal('🧾 Kadr Studio — xarajatlar', `
    <div class="stats-grid" style="margin-bottom:14px">
      ${statTile('🧾', money(f.totalAll), 'Jami xarajat', 'orange')}
    </div>
    <div class="panel" style="margin-bottom:14px">
      <div class="field"><label>Xarajat nomi</label><select id="ex_name">${nameOpts}</select></div>
      <div id="ex_otherwrap" class="field" style="display:none"><label>Boshqa nomi</label><input id="ex_other" placeholder="masalan: taksi" /></div>
      <div class="field-row">
        <div class="field"><label>Summa (so'm)</label><input id="ex_amt" type="number" inputmode="numeric" placeholder="masalan: 200000" /></div>
        <div class="field"><label>Sana</label><input id="ex_date" type="date" /></div>
      </div>
      <div class="field"><label>Izoh (ixtiyoriy)</label><input id="ex_note" /></div>
      <button class="btn-save" id="ex_save">+ Xarajat qo'shish</button>
    </div>
    <div class="day-list">${list}</div>`,
  () => {
    $('#ex_name').addEventListener('change', () => {
      $('#ex_otherwrap').style.display = $('#ex_name').value === '__other' ? '' : 'none';
    });
    $('#ex_save').addEventListener('click', async () => {
      let name = $('#ex_name').value;
      if (name === '__other') name = $('#ex_other').value.trim() || 'Boshqa';
      const amount = parseInt($('#ex_amt').value || '0', 10);
      if (amount <= 0) { toast('Summani kiriting'); return; }
      await api('/api/studio/expenses', { method: 'POST', body: JSON.stringify({ name, amount, edate: $('#ex_date').value || null, note: $('#ex_note').value }) });
      toast('🧾 Xarajat qo\'shildi'); openStudioExpensesModal();
    });
    $('#modalBody').querySelectorAll('[data-expdel]').forEach((b) => b.addEventListener('click', async () => {
      if (!confirm('Xarajatni o\'chirasizmi?')) return;
      await api(`/api/studio/expenses/${b.dataset.expdel}`, { method: 'DELETE' });
      toast('O\'chirildi'); openStudioExpensesModal();
    }));
  });
}

// ============================================================
//  KADR MEDIA SYOMKALARI (loyiha syomkalari)
// ============================================================
async function viewShoots() {
  const data = await api('/api/shoots');
  DATA.shoots = data;
  let list = (data.shoots || []).filter((s) => matchSearch((s.project || '') + ' ' + (s.operator || '') + ' ' + (SHOOT_TYPE_LABEL[s.shoot_type] || '')));
  if (['active', 'bekor_qilindi'].includes(FILTER)) list = list.filter((s) => (s.status || 'active') === FILTER);
  const activeCount = (data.shoots || []).filter((s) => (s.status || 'active') !== 'bekor_qilindi').length;
  const opStats = Object.entries(data.operatorTotals || {}).map(([n, v]) => statTile('👤', money(v), n + ' — operator puli', 'purple')).join('');
  const chips = [['all', 'Hammasi'], ['active', 'Aktiv'], ['bekor_qilindi', 'Bekor qilingan']];
  $('#content').innerHTML = `
    <div class="stats-grid">
      ${statTile('🎬', activeCount, 'Aktiv syomkalar', 'blue')}
      ${opStats}
    </div>
    <div class="filter-row">${chips.map(([k, l]) => `<button class="chip ${FILTER === k ? 'active' : ''}" data-f="${k}">${l}</button>`).join('')}</div>
    <div class="cards-grid">${list.map(shootCard).join('') || emptyState('Syomka yo\'q')}</div>`;
  $('#content').querySelectorAll('.chip').forEach((c) => c.addEventListener('click', () => { FILTER = c.dataset.f; render(); }));
  $('#content').querySelectorAll('.shoot-card').forEach((card) => card.addEventListener('click', () => {
    const s = (data.shoots || []).find((x) => x.id == card.dataset.sid);
    if (s) openShootDetailModal(s);
  }));
}

function shootCard(s) {
  const cancelled = (s.status || 'active') === 'bekor_qilindi';
  const st = SHOOT_TYPE_LABEL[s.shoot_type] || s.shoot_type;
  return `
    <div class="video-card clickable shoot-card${cancelled ? ' shoot-cancelled' : ''}" data-sid="${s.id}">
      <div class="pc-top"><div class="pc-name">📁 ${esc(s.project || '—')}</div>
        <span class="pill ${cancelled ? 'st-red' : 'st-blue'}">${cancelled ? 'Bekor qilindi' : 'Aktiv'}</span></div>
      <div class="video-meta">
        <span class="link-chip">🎥 ${esc(st)}</span>
        ${s.operator ? `<span class="link-chip">👤 ${esc(s.operator)}</span>` : ''}
        ${(s.operator && !cancelled) ? `<span class="money-chip">💰 ${money(s.operator_pay)}</span>` : ''}
      </div>
      ${s.note ? `<div class="pc-problem soft">📝 ${esc(s.note)}</div>` : ''}
      <div class="pc-foot"><div class="muted">📅 ${fmtDate(s.sdate)} · 👮 ${esc(s.created_by || '')}</div></div>
    </div>`;
}

async function openShootModal() {
  const data = DATA.shoots || {};
  if (!DATA.projects) DATA.projects = await api('/api/projects');
  const operators = data.operators || ['Said', 'Umid'];
  const shootTypes = data.shootTypes || SHOOT_TYPE_LABEL;
  const opPay = data.operatorPay || { reels: 50000, podcast: 100000, youtube: 50000, vebinar: 200000 };
  const projOpts = (DATA.projects || []).map((p) => `<option value="${esc(p.name)}" data-id="${p.id}">${esc(p.name)}</option>`).join('');
  const typeOpts = Object.entries(shootTypes).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join('');
  const opOpts = `<option value="">— operator yo'q —</option>` + operators.map((o) => `<option>${esc(o)}</option>`).join('');
  openModal('Loyihaga syomka belgilash', `
    <div class="field"><label>Loyiha</label><select id="sh_proj">${projOpts}</select></div>
    <div class="field-row">
      <div class="field"><label>Syomka turi</label><select id="sh_type">${typeOpts}</select></div>
      <div class="field"><label>Operator</label><select id="sh_op">${opOpts}</select></div>
    </div>
    <div id="sh_oppay" class="calc-line"></div>
    <div class="field"><label>Sana</label><input id="sh_date" type="date" /></div>
    <div class="field"><label>Izoh</label><textarea id="sh_note" placeholder="masalan: mijoz manzilida, 2 lokatsiya"></textarea></div>
    <div class="modal-actions"><button class="btn-save" id="sh_save">🎬 Belgilash</button></div>`,
  () => {
    const showPay = () => {
      const op = $('#sh_op').value; const t = $('#sh_type').value;
      $('#sh_oppay').innerHTML = op
        ? `👤 ${esc(op)} operatorga hisoblanadi: <b>${money(opPay[t] || 0)}</b>`
        : `<span class="muted">Operator tanlanmasa — operator puli hisoblanmaydi</span>`;
    };
    ['sh_op', 'sh_type'].forEach((id) => $('#' + id).addEventListener('change', showPay));
    showPay();
    $('#sh_save').addEventListener('click', async () => {
      const sel = $('#sh_proj'); const opt = sel.options[sel.selectedIndex];
      if (!sel.value) { toast('Loyihani tanlang'); return; }
      const body = {
        project: sel.value, project_id: opt ? opt.dataset.id : null,
        shoot_type: $('#sh_type').value, operator: $('#sh_op').value,
        sdate: $('#sh_date').value || null, note: $('#sh_note').value,
      };
      await api('/api/shoots', { method: 'POST', body: JSON.stringify(body) });
      closeModal(); toast('🎬 Syomka belgilandi'); render();
    });
  });
}

function openShootDetailModal(s) {
  const cancelled = (s.status || 'active') === 'bekor_qilindi';
  const st = SHOOT_TYPE_LABEL[s.shoot_type] || s.shoot_type;
  const actions = cancelled
    ? `<button class="mini-btn red" id="sh_del">🗑 O'chirish</button>`
    : `<button class="mini-btn gray" id="sh_cancel">🚫 Bekor qilish</button><button class="mini-btn red" id="sh_del">🗑 O'chirish</button>`;
  openModal(`Syomka · ${esc(s.project || '')}`, `
    ${cancelled ? `<div class="pill st-red" style="display:inline-block;margin-bottom:10px">🚫 Bekor qilindi</div>` : ''}
    <div class="money-rows" style="margin-bottom:12px">
      <div class="mrow"><span>📁 Loyiha</span><b>${esc(s.project || '—')}</b></div>
      <div class="mrow"><span>🎥 Syomka turi</span><b>${esc(st)}</b></div>
      ${s.operator ? `<div class="mrow"><span>👤 Operator</span><b>${esc(s.operator)}${cancelled ? '' : ` · ${money(s.operator_pay)}`}</b></div>` : ''}
      <div class="mrow"><span>📅 Sana</span><b>${fmtDate(s.sdate)}</b></div>
      <div class="mrow"><span>👮 Belgiladi</span><b>${esc(s.created_by || '—')}</b></div>
    </div>
    ${s.note ? `<div class="pc-problem soft" style="margin-bottom:12px">📝 ${esc(s.note)}</div>` : ''}
    <div class="modal-actions">${actions}</div>`,
  () => {
    const cn = $('#sh_cancel');
    if (cn) cn.addEventListener('click', async () => {
      if (!confirm('Syomkani bekor qilasizmi? Operatorga pul hisoblanmaydi.')) return;
      await api(`/api/shoots/${s.id}/cancel`, { method: 'POST', body: '{}' });
      closeModal(); toast('🚫 Bekor qilindi'); render();
    });
    const del = $('#sh_del');
    if (del) del.addEventListener('click', async () => {
      if (!confirm('Butunlay o\'chirasizmi?')) return;
      await api(`/api/shoots/${s.id}`, { method: 'DELETE' });
      closeModal(); toast('O\'chirildi'); render();
    });
  });
}

// ============================================================
//  SSENARIST KABINETI
// ============================================================
async function viewScenarist() {
  const data = await api('/api/scenarist');
  DATA.scenarist = data;
  const list = (data.scripts || []).filter((s) => matchSearch((s.title || '') + ' ' + (s.project || '')));
  const rows = list.map((s) => {
    const cancelled = (s.status || 'active') === 'bekor_qilindi';
    return `
      <div class="video-card scenarist-card${cancelled ? ' shoot-cancelled' : ''}" data-scid="${s.id}">
        <div class="pc-top"><div class="pc-name">✍️ ${esc(s.title || 'Nomsiz')}</div>
          <span class="pill ${cancelled ? 'st-red' : 'st-green'}">${cancelled ? 'Bekor · minus' : money(s.amount)}</span></div>
        <div class="pc-client">📁 ${esc(s.project || '—')}${s.client ? ' · ' + esc(s.client) : ''}</div>
        ${s.note ? `<div class="pc-problem soft">📝 ${esc(s.note)}</div>` : ''}
        <div class="pc-foot"><div class="muted">📅 ${fmtDate(s.sdate)}</div>
          <div class="card-actions">${cancelled ? '' : `<button class="mini-btn gray" data-sccancel="${s.id}">🚫 Bekor</button>`}
            <button class="mini-btn red" data-scdel="${s.id}">🗑</button></div></div>
      </div>`;
  }).join('') || emptyState('Hali ssenariy kiritilmagan');
  $('#content').innerHTML = `
    <div class="stats-grid">
      ${statTile('✅', data.count, 'Tasdiqlangan ssenariy', 'green')}
      ${statTile('💰', money(data.earned), 'Hisoblangan pul', 'blue')}
      ${statTile('✍️', money(data.rate), 'Har ssenariy uchun', 'purple')}
    </div>
    <div class="cards-grid">${rows}</div>`;
  $('#content').querySelectorAll('[data-sccancel]').forEach((b) => b.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!confirm('Mijoz bekor qildimi? Pul kabinetdan minus bo\'ladi.')) return;
    await api(`/api/scenarist/${b.dataset.sccancel}/cancel`, { method: 'POST', body: '{}' });
    toast('🚫 Bekor qilindi — pul minus'); render();
  }));
  $('#content').querySelectorAll('[data-scdel]').forEach((b) => b.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!confirm('Butunlay o\'chirasizmi?')) return;
    await api(`/api/scenarist/${b.dataset.scdel}`, { method: 'DELETE' });
    toast('O\'chirildi'); render();
  }));
}

function openScenaristModal() {
  openModal('Tasdiqlangan ssenariy kiritish', `
    <p class="muted" style="margin-bottom:12px">Mijoz tasdiqlagan ssenariyni kiriting — pul avtomatik hisoblanadi.</p>
    <div class="field"><label>Ssenariy nomi</label><input id="sc_title" placeholder="masalan: Nova reels #12 — hook" /></div>
    <div class="field-row">
      <div class="field"><label>Loyiha</label><input id="sc_proj" placeholder="Loyiha nomi" /></div>
      <div class="field"><label>Sana</label><input id="sc_date" type="date" /></div>
    </div>
    <div class="field"><label>Izoh (ixtiyoriy)</label><textarea id="sc_note"></textarea></div>
    <div class="modal-actions"><button class="btn-save" id="sc_save">✍️ Kiritish</button></div>`,
  () => {
    $('#sc_save').addEventListener('click', async () => {
      const title = $('#sc_title').value.trim();
      if (!title) { toast('Ssenariy nomini kiriting'); return; }
      const body = { title, project: $('#sc_proj').value, sdate: $('#sc_date').value || null, note: $('#sc_note').value };
      await api('/api/scenarist', { method: 'POST', body: JSON.stringify(body) });
      closeModal(); toast('✍️ Ssenariy kiritildi — pul hisoblandi'); render();
    });
  });
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
function rankProgressBar(e) {
  const nextTxt = e.next_label
    ? `Keyingi: ${esc(e.next_label)} — yana <b>${e.to_next}</b> qabul`
    : 'Eng yuqori lavozim! 🔱';
  return `
    <div class="rank-box">
      <div class="rank-top"><span class="rank-chip rank-${esc(e.rank_key)}">${e.rank_icon || '🎖'} ${esc(e.rank_label)}</span>
        <span class="muted">${e.accepted} qabul</span></div>
      <div class="rank-meter"><div class="rank-fill" style="width:${e.rank_pct || 0}%"></div></div>
      <div class="rank-next">${nextTxt}</div>
    </div>`;
}
function editorCard(e) {
  const proj = e.byProject.slice(0, 3).map((p) => `${esc(p.project)}: ${p.count}`).join(' · ');
  return `
    <div class="team-card">
      <div class="team-head"><div class="team-av" style="background:${e.color || colorFor(e.name)}">${initials(e.name)}</div>
        <div><div class="team-name">${esc(e.name)}</div><div class="team-role">${e.accepted} video · ${proj || 'hozircha yo\'q'}</div></div></div>
      ${rankProgressBar(e)}
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
  const grouped = c.byProject.map((p) => `<div class="mrow"><span>${esc(p.project)}</span><b>${p.count} video</b></div>`).join('') || '<div class="muted">Hozircha tasdiqlangan video yo\'q</div>';
  const pays = c.payments.map((p) => `<div class="pay-row"><div><b>${money(p.amount)}</b><div class="muted">${fmtDate(p.pdate)} · ${esc(p.note) || '—'}</div></div><div class="muted">${esc(p.paid_by)}</div></div>`).join('') || '<div class="muted">To\'lov tarixi yo\'q</div>';
  const todo = (c.videosList || []).filter((v) => v.status === 'biriktirildi' || v.status === 'qaytarildi');
  const todoHtml = todo.map((v) => `
    <div class="ceo-item">
      <div class="ci-left"><div><div class="ci-name">${esc(v.title)}</div><div class="ci-sub">${esc(v.project)}${v.status === 'qaytarildi' ? ' · ↩ qaytarilgan' : ''}</div></div></div>
      <button class="mini-btn blue" data-vact="montaj_done" data-id="${v.id}">✓ Montaj qildim</button>
    </div>`).join('') || '<div class="muted">Yangi topshiriq yo\'q ✓</div>';
  const nextTxt = c.next_label
    ? `<b>${esc(c.next_label)}</b> lavozimiga yana <b>${c.to_next}</b> ta qabul qilingan video kerak`
    : 'Tabriklaymiz — eng yuqori lavozimga yetdingiz! 🔱';
  const rankHero = `
    <div class="rank-hero rank-${esc(c.rank_key)}">
      <div class="rh-left">
        <div class="rh-icon">${c.rank_icon || '🎖'}</div>
        <div><div class="rh-label">${esc(c.rank_label)}</div>
          <div class="rh-sub">${c.accepted} ta muvaffaqiyatli montaj</div></div>
      </div>
      <div class="rh-prog">
        <div class="rank-meter big"><div class="rank-fill" style="width:${c.rank_pct || 0}%"></div></div>
        <div class="rh-next">${nextTxt}</div>
      </div>
    </div>`;
  $('#content').innerHTML = `
    ${rankHero}
    <div class="stats-grid">
      ${statTile('🎬', c.toDo, 'Montaj qilish kerak', 'orange')}
      ${statTile('⏳', c.inReview, 'Tasdiq jarayonida', 'blue')}
      ${statTile('💰', money(c.earned), 'Ishlangan', 'green')}
      ${statTile('₿', money(c.remaining), 'Qolgan to\'lov', 'purple')}
    </div>
    <div class="panel"><h3>🎬 Montaj qilishim kerak (${todo.length})</h3><div class="ceo-list">${todoHtml}</div></div>
    <div class="ceo-grid">
      <div class="panel"><h3>📁 Tasdiqlanganlar (loyiha bo'yicha)</h3><div class="money-rows">${grouped}</div>
        <div class="ec-stats" style="margin-top:14px"><span>${c.videos} jami</span><span>${c.accepted} tasdiqlangan</span><span>${c.returned} qaytgan</span></div></div>
      <div class="panel"><h3>💸 To'lov tarixim</h3>${pays}</div>
    </div>`;
  bindVideoCards();
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

// ---- Video biriktirish modal (rahbar montajchiga biriktiradi) ----
async function openVideoModal() {
  DATA.projects = await api('/api/projects');  // rahbar o'z loyihalari
  if (!DATA.scripts) DATA.scripts = await api('/api/scripts');
  if (!DATA.team) DATA.team = await api('/api/team');
  const editors = DATA.team.filter((u) => u.role === 'editor');
  const projOpts = DATA.projects.map((p) => `<option value="${esc(p.name)}" data-client="${esc(p.client)}">${esc(p.name)} (${esc(p.client)})</option>`).join('');
  const scriptOpts = DATA.scripts.map((s) => `<option value="${s.id}">#${s.id} ${esc(s.title)}</option>`).join('');
  openModal('Videoni montajchiga biriktirish', `
    <div class="field"><label>Video nomi</label><input id="vf_title" placeholder="masalan: Nova reels #12" /></div>
    <div class="field-row">
      <div class="field"><label>Video turi</label><select id="vf_vtype">
        <option value="reels">Reels</option>
        <option value="podcast">Podcast</option>
        <option value="youtube">YouTube video</option>
      </select></div>
      <div class="field"><label>Montajchi (kimga)</label><select id="vf_editor"><option value="">—</option>${editors.map((e) => `<option>${esc(e.name)}</option>`).join('')}</select></div>
    </div>
    <div class="field-row">
      <div class="field"><label>Loyiha (mijoz)</label><select id="vf_project"><option value="">—</option>${projOpts}</select></div>
    </div>
    <div class="field"><label>Ssenariy (ixtiyoriy — zanjir uchun)</label><select id="vf_script"><option value="">— bog'lanmagan —</option>${scriptOpts}</select></div>
    <div class="field-row">
      <div class="field"><label>Sana</label><input id="vf_date" type="date" /></div>
      <div class="field"><label>Material/Drive link</label><input id="vf_drive" placeholder="https://drive..." /></div>
    </div>
    <div class="field"><label>Izoh / topshiriq</label><textarea id="vf_note" placeholder="Montajchiga ko'rsatma..."></textarea></div>
    <div class="modal-actions"><button class="btn-save" id="vf_save">🎬 Biriktirish</button></div>`,
  () => {
    $('#vf_save').addEventListener('click', async () => {
      const sel = $('#vf_project'); const client = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].dataset.client || '' : '';
      if (!$('#vf_editor').value) { toast('Montajchini tanlang'); return; }
      const body = { title: $('#vf_title').value.trim() || 'Nomsiz video', project: $('#vf_project').value, client,
        vtype: $('#vf_vtype').value, editor: $('#vf_editor').value, script_id: $('#vf_script').value || null,
        vdate: $('#vf_date').value || null, drive_link: $('#vf_drive').value, note: $('#vf_note').value };
      await api('/api/videos', { method: 'POST', body: JSON.stringify(body) });
      closeModal(); toast('🎬 Biriktirildi'); render();
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
