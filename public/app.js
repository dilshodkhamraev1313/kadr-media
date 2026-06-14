// ============================================================
//  Kadr Media Dashboard — Frontend logic
// ============================================================

const STAGES = [
  { key: 'ssenariy', label: 'Ssenariy' },
  { key: 'syomka',   label: 'Syomka' },
  { key: 'montaj',   label: 'Montaj' },
  { key: 'tasdiq',   label: 'Tasdiq' },
  { key: 'joylash',  label: 'Joylash' }
];
const STATUS_LABEL = { kutilmoqda: 'Kutilmoqda', jarayonda: 'Jarayonda', tayyor: 'Tayyor' };
const COLORS = ['#0a84ff', '#bf5af2', '#ff9f0a', '#30d158', '#ff375f', '#ffd60a', '#64d2ff', '#ff453a'];

let ME = null;
let USERS = [];
let CLIENTS = [];
let PROJECTS = [];
let STATS = null;
let VIEW = 'dashboard';
let FILTER = 'all';
let SEARCH = '';

// ---------- Utils ----------
const $ = (s) => document.querySelector(s);
const api = async (url, opts) => {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts
  });
  return r.json();
};
const initials = (name) => (name || '?').trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase();
const colorFor = (name) => {
  let h = 0;
  for (const ch of (name || '')) h = ch.charCodeAt(0) + ((h << 5) - h);
  return COLORS[Math.abs(h) % COLORS.length];
};
const esc = (s) => (s || '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.add('hidden'), 2200);
}
function fmtDate(d) {
  if (!d) return '—';
  const x = new Date(d + 'T00:00:00');
  return x.toLocaleDateString('uz-UZ', { day: 'numeric', month: 'short' });
}
function deadlineText(p) {
  if (!p.deadline) return { txt: 'Muddat yo\'q', cls: '' };
  if (p.fullyDone) return { txt: 'Yakunlandi ✓', cls: '' };
  if (p.daysLeft < 0) return { txt: `${Math.abs(p.daysLeft)} kun kechikdi`, cls: 'late' };
  if (p.daysLeft === 0) return { txt: 'Bugun!', cls: 'soon' };
  if (p.daysLeft <= 2) return { txt: `${p.daysLeft} kun qoldi`, cls: 'soon' };
  return { txt: fmtDate(p.deadline), cls: '' };
}

// ============================================================
//  LOGIN
// ============================================================
async function initLogin() {
  USERS = await api('/api/users');
  const wrap = $('#loginUsers');
  wrap.innerHTML = USERS.map((u) => `
    <button class="login-user" data-id="${u.id}">
      <div class="av" style="background:${u.color || colorFor(u.name)}">${initials(u.name)}</div>
      <div>
        <div class="lu-name">${esc(u.name)}</div>
        <div class="lu-role">${esc(u.title || u.role)}</div>
      </div>
    </button>
  `).join('');
  wrap.querySelectorAll('.login-user').forEach((b) =>
    b.addEventListener('click', () => loginAs(USERS.find((u) => u.id == b.dataset.id)))
  );

  // Avval kirgan bo'lsa — eslab qolamiz
  const saved = localStorage.getItem('km_user');
  if (saved) {
    const u = USERS.find((x) => x.id == saved);
    if (u) loginAs(u);
  }
}

function loginAs(user) {
  ME = user;
  localStorage.setItem('km_user', user.id);
  $('#login').classList.add('hidden');
  $('#app').classList.remove('hidden');

  $('#meName').textContent = user.name;
  $('#meRole').textContent = user.title || user.role;
  $('#meAvatar').textContent = initials(user.name);
  $('#meAvatar').style.background = user.color || colorFor(user.name);

  // CEO bo'lmaganlardan CEO ko'rinishini yashirish
  const isCeo = user.role === 'ceo';
  document.querySelectorAll('.ceo-only').forEach((el) => el.style.display = isCeo ? '' : 'none');

  // CEO uchun standart ko'rinish — CEO paneli
  VIEW = isCeo ? 'ceo' : 'dashboard';
  setActiveNav();
  refresh();
}

// ============================================================
//  NAVIGATION
// ============================================================
function setActiveNav() {
  document.querySelectorAll('.nav-btn, .m-btn').forEach((b) =>
    b.classList.toggle('active', b.dataset.view === VIEW)
  );
}
document.querySelectorAll('.nav-btn, .m-btn').forEach((b) =>
  b.addEventListener('click', () => { VIEW = b.dataset.view; setActiveNav(); render(); })
);
$('#logoutBtn').addEventListener('click', () => {
  localStorage.removeItem('km_user');
  location.reload();
});
$('#searchInput').addEventListener('input', (e) => { SEARCH = e.target.value.toLowerCase(); render(); });
$('#addBtn').addEventListener('click', () => openModal(null));

// ============================================================
//  DATA
// ============================================================
async function refresh() {
  [PROJECTS, STATS, CLIENTS] = await Promise.all([
    api('/api/projects'),
    api('/api/stats'),
    api('/api/clients')
  ]);
  render();
}

// ============================================================
//  RENDER
// ============================================================
const TITLES = {
  dashboard: ['Boshqaruv paneli', 'Bugungi holat — bir qarashda'],
  projects:  ['Loyihalar', 'Barcha loyihalar kartochka ko\'rinishida'],
  team:      ['Jamoa yuklamasi', 'Har bir rahbarning yuklamasi'],
  ceo:       ['CEO ko\'rinishi', 'Butun agentlik bitta ekranda']
};

function render() {
  $('#viewTitle').textContent = TITLES[VIEW][0];
  $('#viewSub').textContent = TITLES[VIEW][1];
  const c = $('#content');
  if (VIEW === 'dashboard') c.innerHTML = renderDashboard();
  else if (VIEW === 'projects') c.innerHTML = renderProjects();
  else if (VIEW === 'team') c.innerHTML = renderTeam();
  else if (VIEW === 'ceo') c.innerHTML = renderCeo();
  bindCards();
}

// ----- Stat cards -----
function statCards() {
  return `
    <div class="stats-grid">
      <div class="stat-card accent-blue">
        <div class="stat-ic">▣</div>
        <div class="stat-val">${STATS.total}</div>
        <div class="stat-label">Jami loyihalar</div>
      </div>
      <div class="stat-card accent-red">
        <div class="stat-ic">⏱</div>
        <div class="stat-val">${STATS.overdue}</div>
        <div class="stat-label">Kechikayotgan</div>
      </div>
      <div class="stat-card accent-green">
        <div class="stat-ic">✓</div>
        <div class="stat-val">${STATS.todayTasks}</div>
        <div class="stat-label">Bugun bajarilgan vazifalar</div>
      </div>
      <div class="stat-card accent-orange">
        <div class="stat-ic">⚠</div>
        <div class="stat-val">${STATS.atRisk}</div>
        <div class="stat-label">Xavf ostida</div>
      </div>
    </div>`;
}

// ----- Dashboard -----
function renderDashboard() {
  const list = filteredProjects();
  return `
    ${statCards()}
    <div class="filter-row">
      ${filterChips()}
    </div>
    <div class="cards-grid">
      ${list.length ? list.map(projectCard).join('') : emptyState()}
    </div>`;
}

// ----- Projects -----
function renderProjects() {
  const list = filteredProjects();
  return `
    <div class="filter-row">${filterChips()}</div>
    <div class="cards-grid">
      ${list.length ? list.map(projectCard).join('') : emptyState()}
    </div>`;
}

function filterChips() {
  const chips = [
    ['all', 'Hammasi'],
    ['active', 'Faol'],
    ['overdue', 'Kechikkan'],
    ['risk', 'Xavf ostida'],
    ['done', 'Yakunlangan'],
    ['mine', 'Mening loyihalarim']
  ];
  return chips.map(([k, l]) =>
    `<button class="chip ${FILTER === k ? 'active' : ''}" data-filter="${k}">${l}</button>`
  ).join('');
}

function filteredProjects() {
  let list = PROJECTS;
  if (FILTER === 'active') list = list.filter((p) => !p.fullyDone);
  else if (FILTER === 'overdue') list = list.filter((p) => p.overdue);
  else if (FILTER === 'risk') list = list.filter((p) => p.atRisk);
  else if (FILTER === 'done') list = list.filter((p) => p.fullyDone);
  else if (FILTER === 'mine') list = list.filter((p) => p.responsible === ME.name);
  if (SEARCH) list = list.filter((p) =>
    (p.name + ' ' + p.client + ' ' + p.responsible).toLowerCase().includes(SEARCH)
  );
  return list;
}

function projectCard(p) {
  const dl = deadlineText(p);
  const badges = [];
  if (p.fullyDone) badges.push('<span class="badge done">✓ Tayyor</span>');
  else {
    if (p.overdue) badges.push('<span class="badge overdue">⏱ Kechikkan</span>');
    if (p.atRisk && !p.overdue) badges.push('<span class="badge risk">⚠ Xavf</span>');
  }
  return `
    <div class="project-card" data-id="${p.id}">
      <div class="pc-top">
        <div>
          <div class="pc-name">${esc(p.name)}</div>
        </div>
        <div class="pc-badges">${badges.join('')}</div>
      </div>
      <div class="pc-client">📁 ${esc(p.client) || '—'}</div>

      <div class="pc-stages">
        ${STAGES.map((s) => `<div class="stage-dot ${p[s.key]}">${s.label}</div>`).join('')}
      </div>

      <div class="pc-progress">
        <div class="progress-bar"><div class="progress-fill" style="width:${p.progress}%"></div></div>
        <div class="pc-progress-label"><span>${p.doneCount}/5 bosqich</span><span>${p.progress}%</span></div>
      </div>

      ${p.muammo ? `<div class="pc-problem">⚠ ${esc(p.muammo)}</div>` : ''}

      <div class="pc-foot">
        <div class="pc-resp">
          <div class="mini-av" style="background:${colorFor(p.responsible)}">${initials(p.responsible)}</div>
          <span>${esc(p.responsible) || 'Tayinlanmagan'}</span>
        </div>
        <div class="pc-deadline ${dl.cls}">📅 ${dl.txt}</div>
      </div>
    </div>`;
}

// ----- Team / Workload -----
function renderTeam() {
  return `
    ${statCards()}
    <div class="section-head"><h3>Rahbarlar yuklamasi</h3></div>
    <div class="team-grid">
      ${STATS.workload.map((w) => {
        const u = USERS.find((x) => x.name === w.name) || {};
        const max = Math.max(...STATS.workload.map((x) => x.total), 1);
        const pct = Math.round((w.total / max) * 100);
        return `
        <div class="team-card">
          <div class="team-head">
            <div class="team-av" style="background:${u.color || colorFor(w.name)}">${initials(w.name)}</div>
            <div>
              <div class="team-name">${esc(w.name)}</div>
              <div class="team-role">${esc(u.title || 'Loyiha rahbari')}</div>
            </div>
          </div>
          <div class="wl-bars">
            <div>
              <div class="wl-row"><span class="lbl">Jami loyiha</span><span class="val">${w.total}</span></div>
              <div class="wl-meter"><div class="wl-meter-fill" style="width:${pct}%;background:${u.color || colorFor(w.name)}"></div></div>
            </div>
            <div class="wl-row"><span class="lbl">Faol</span><span class="val" style="color:var(--blue)">${w.active}</span></div>
            <div class="wl-row"><span class="lbl">Kechikkan</span><span class="val" style="color:var(--red)">${w.overdue}</span></div>
            <div class="wl-row"><span class="lbl">Xavf ostida</span><span class="val" style="color:var(--orange)">${w.atRisk}</span></div>
          </div>
        </div>`;
      }).join('')}
    </div>`;
}

// ----- CEO -----
function renderCeo() {
  const overdue = PROJECTS.filter((p) => p.overdue);
  const risk = PROJECTS.filter((p) => p.atRisk && !p.overdue);
  const active = PROJECTS.filter((p) => !p.fullyDone);

  const stageOf = (p) => {
    const next = STAGES.find((s) => p[s.key] !== 'tayyor');
    return next ? next.label : 'Yakunlandi';
  };

  return `
    ${statCards()}
    <div class="ceo-grid">
      <div>
        <div class="panel">
          <h3>🗺️ Qaysi loyiha qayerda</h3>
          <div class="ceo-list">
            ${active.length ? active.map((p) => `
              <div class="ceo-item" data-id="${p.id}">
                <div class="ci-left">
                  <div class="mini-av" style="background:${colorFor(p.responsible)}">${initials(p.responsible)}</div>
                  <div>
                    <div class="ci-name">${esc(p.name)}</div>
                    <div class="ci-sub">${esc(p.client)} · ${esc(p.responsible)}</div>
                  </div>
                </div>
                <span class="pill blue">${stageOf(p)} · ${p.progress}%</span>
              </div>`).join('') : '<div class="muted">Faol loyiha yo\'q</div>'}
          </div>
        </div>
      </div>

      <div>
        <div class="panel">
          <h3>⏱ Kim kechikyapti</h3>
          <div class="ceo-list">
            ${overdue.length ? overdue.map((p) => `
              <div class="ceo-item" data-id="${p.id}">
                <div class="ci-left">
                  <div class="mini-av" style="background:${colorFor(p.responsible)}">${initials(p.responsible)}</div>
                  <div>
                    <div class="ci-name">${esc(p.responsible)}</div>
                    <div class="ci-sub">${esc(p.name)}</div>
                  </div>
                </div>
                <span class="pill red">${Math.abs(p.daysLeft)} kun</span>
              </div>`).join('') : '<div class="muted">Hech kim kechikmayapti ✓</div>'}
          </div>
        </div>

        <div class="panel">
          <h3>⚠️ Xavf ostidagi loyihalar</h3>
          <div class="ceo-list">
            ${risk.length ? risk.map((p) => `
              <div class="ceo-item" data-id="${p.id}">
                <div class="ci-left">
                  <div>
                    <div class="ci-name">${esc(p.name)}</div>
                    <div class="ci-sub">${p.muammo ? esc(p.muammo) : 'Muddat yaqin, ish kam'}</div>
                  </div>
                </div>
                <span class="pill orange">${p.progress}%</span>
              </div>`).join('') : '<div class="muted">Xavf ostida loyiha yo\'q ✓</div>'}
          </div>
        </div>

        <div class="panel">
          <h3>📈 Bugungi natijalar</h3>
          <div style="display:flex;gap:18px;margin-bottom:14px">
            <div><div style="font-size:26px;font-weight:800;color:var(--green)">${STATS.todayTasks}</div><div class="muted">bajarilgan vazifa</div></div>
            <div><div style="font-size:26px;font-weight:800">${STATS.completed}</div><div class="muted">yakunlangan loyiha</div></div>
          </div>
          ${STATS.recent.length ? STATS.recent.slice(0, 6).map((a) => `
            <div class="activity-item">
              <div class="activity-dot"></div>
              <div>
                <b>${esc(a.actor)}</b> — ${esc(a.project_name)}
                <div class="muted">${stageLabel(a.stage)} tayyor bo'ldi</div>
              </div>
              <div class="at-time">${esc((a.created_at || '').slice(5, 16))}</div>
            </div>`).join('') : '<div class="muted">Hali faollik yo\'q</div>'}
        </div>
      </div>
    </div>`;
}
function stageLabel(k) { return (STAGES.find((s) => s.key === k) || {}).label || k; }

function emptyState() {
  return `<div class="empty"><div class="em-ic">🔍</div>Bu filtrda loyiha topilmadi</div>`;
}

// ----- bind cards & chips -----
function bindCards() {
  document.querySelectorAll('.project-card, .ceo-item').forEach((el) =>
    el.addEventListener('click', () => openModal(PROJECTS.find((p) => p.id == el.dataset.id)))
  );
  document.querySelectorAll('.chip').forEach((c) =>
    c.addEventListener('click', () => { FILTER = c.dataset.filter; render(); })
  );
}

// ============================================================
//  MODAL (qo'shish / tahrirlash)
// ============================================================
let EDITING = null;
let DRAFT = {};

function openModal(project) {
  EDITING = project;
  DRAFT = project
    ? { ...project }
    : { name: '', client: '', responsible: ME.name, deadline: '', muammo: '', izoh: '',
        ssenariy: 'kutilmoqda', syomka: 'kutilmoqda', montaj: 'kutilmoqda', tasdiq: 'kutilmoqda', joylash: 'kutilmoqda' };

  $('#modalTitle').textContent = project ? 'Loyihani tahrirlash' : 'Yangi loyiha';
  $('#modalBody').innerHTML = `
    <div class="field">
      <label>Loyiha nomi</label>
      <input id="f_name" value="${esc(DRAFT.name)}" placeholder="Masalan: Reels — Yangi mahsulot" />
    </div>
    <div class="field-row">
      <div class="field">
        <label>Mijoz</label>
        <select id="f_client">
          <option value="">— Tanlang —</option>
          ${CLIENTS.map((c) => `<option ${DRAFT.client === c.name ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}
        </select>
      </div>
      <div class="field">
        <label>Javobgar (rahbar)</label>
        <select id="f_resp">
          <option value="">— Tanlang —</option>
          ${USERS.filter((u) => u.role !== 'ceo').map((u) => `<option ${DRAFT.responsible === u.name ? 'selected' : ''}>${esc(u.name)}</option>`).join('')}
        </select>
      </div>
    </div>
    <div class="field">
      <label>Deadline (muddat)</label>
      <input id="f_deadline" type="date" value="${DRAFT.deadline || ''}" />
    </div>

    <div class="divider"></div>
    <div class="sec-label">Jarayon bosqichlari</div>
    <div class="stage-editor">
      ${STAGES.map((s) => `
        <div class="stage-edit-row">
          <span class="sname">${s.label}</span>
          <div class="seg" data-stage="${s.key}">
            <button data-v="kutilmoqda" class="${DRAFT[s.key] === 'kutilmoqda' ? 'on-k' : ''}">Kutilmoqda</button>
            <button data-v="jarayonda" class="${DRAFT[s.key] === 'jarayonda' ? 'on-j' : ''}">Jarayonda</button>
            <button data-v="tayyor" class="${DRAFT[s.key] === 'tayyor' ? 'on-t' : ''}">Tayyor</button>
          </div>
        </div>`).join('')}
    </div>

    <div class="divider"></div>
    <div class="field">
      <label>⚠ Muammo (agar bo'lsa)</label>
      <textarea id="f_muammo" placeholder="Masalan: mijoz syomkaga kelmadi...">${esc(DRAFT.muammo)}</textarea>
    </div>
    <div class="field">
      <label>Izoh</label>
      <textarea id="f_izoh" placeholder="Qo'shimcha izohlar...">${esc(DRAFT.izoh)}</textarea>
    </div>

    <div class="modal-actions">
      ${project ? '<button class="btn-del" id="btnDel">O\'chirish</button>' : ''}
      <button class="btn-save" id="btnSave">${project ? 'Saqlash' : 'Qo\'shish'}</button>
    </div>`;

  // segment tugmalari
  $('#modalBody').querySelectorAll('.seg').forEach((seg) => {
    seg.querySelectorAll('button').forEach((btn) =>
      btn.addEventListener('click', () => {
        const stage = seg.dataset.stage;
        DRAFT[stage] = btn.dataset.v;
        seg.querySelectorAll('button').forEach((b) => b.className = '');
        btn.className = btn.dataset.v === 'kutilmoqda' ? 'on-k' : btn.dataset.v === 'jarayonda' ? 'on-j' : 'on-t';
      })
    );
  });

  $('#btnSave').addEventListener('click', saveProject);
  if (project) $('#btnDel').addEventListener('click', deleteProject);

  $('#modal').classList.remove('hidden');
}

function closeModal() { $('#modal').classList.add('hidden'); }
$('#modalClose').addEventListener('click', closeModal);
$('#modal').addEventListener('click', (e) => { if (e.target.id === 'modal') closeModal(); });

async function saveProject() {
  const body = {
    name: $('#f_name').value.trim() || 'Nomsiz loyiha',
    client: $('#f_client').value,
    responsible: $('#f_resp').value,
    deadline: $('#f_deadline').value || null,
    muammo: $('#f_muammo').value.trim(),
    izoh: $('#f_izoh').value.trim(),
    ssenariy: DRAFT.ssenariy, syomka: DRAFT.syomka, montaj: DRAFT.montaj,
    tasdiq: DRAFT.tasdiq, joylash: DRAFT.joylash,
    _actor: ME.name
  };
  if (EDITING) {
    await api(`/api/projects/${EDITING.id}`, { method: 'PUT', body: JSON.stringify(body) });
    toast('✓ Loyiha yangilandi');
  } else {
    await api('/api/projects', { method: 'POST', body: JSON.stringify(body) });
    toast('✓ Loyiha qo\'shildi');
  }
  closeModal();
  refresh();
}

async function deleteProject() {
  if (!confirm('Bu loyihani o\'chirishni tasdiqlaysizmi?')) return;
  await api(`/api/projects/${EDITING.id}`, { method: 'DELETE' });
  toast('Loyiha o\'chirildi');
  closeModal();
  refresh();
}

// ============================================================
//  START
// ============================================================
initLogin();
