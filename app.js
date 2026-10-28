/* MSF Library — app.js
 *
 * Three "pages" rendered as separate <main> blocks; the nav switches between
 * them without any scroll or hash-jump.
 *
 * Upload  → tracks files locally in localStorage (no server call needed).
 * Sync    → pushes the queue through the Python server, rebuilds the index,
 *           and hot-reloads the Search page — no page refresh required.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Document collection  (window.MSF_DOCUMENTS comes from documents.js)
// ─────────────────────────────────────────────────────────────────────────────

const documents = Array.isArray(window.MSF_DOCUMENTS) ? window.MSF_DOCUMENTS : [];
const pageSize  = 20;
let submittedQuery = '';
let page = 0;

const LANG_LABELS = { en: 'English', fr: 'French', ar: 'Arabic', es: 'Spanish', und: 'Unknown' };

const get     = (id)   => document.getElementById(id);
const checked = (name) => Array.from(
  document.querySelectorAll(`input[name="${name}"]:checked`),
  (el) => el.value,
);

// ─────────────────────────────────────────────────────────────────────────────
// Tab / page switching  (no scroll, no hash navigation)
// ─────────────────────────────────────────────────────────────────────────────

function showPage(name) {
  document.querySelectorAll('.page').forEach((el) => el.classList.remove('active-page'));
  document.querySelectorAll('.nav-link').forEach((el) => el.classList.remove('active'));

  const page = document.getElementById(`${name}-page`);
  const link = document.querySelector(`.nav-link[data-page="${name}"]`);
  if (page) page.classList.add('active-page');
  if (link) link.classList.add('active');

  // Refresh the sync panel whenever the user navigates to it.
  if (name === 'sync') _renderSyncPanel();
}

document.querySelectorAll('.nav-link').forEach((link) => {
  link.addEventListener('click', (e) => {
    e.preventDefault();
    showPage(link.dataset.page);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Search page
// ─────────────────────────────────────────────────────────────────────────────

function documentCard(record) {
  const article = document.createElement('article');
  article.className = 'card';

  const title = document.createElement('h3');
  title.dir = 'auto';
  if (record.id) {
    const a = document.createElement('a');
    a.href = `/doc/${encodeURIComponent(record.id)}`;
    a.target = '_blank';
    a.rel = 'noopener';
    a.textContent = record.title || 'Title unavailable';
    title.append(a);
  } else {
    title.textContent = record.title || 'Title unavailable';
  }

  const meta = document.createElement('p');
  meta.className = 'card-meta';
  const bits = [record.location, record.date,
    (record.languages || []).map((l) => LANG_LABELS[l] || l).join(', ')].filter(Boolean);
  meta.textContent = bits.join(' · ');

  const excerpt = document.createElement('p');
  excerpt.dir = 'auto';
  excerpt.textContent = record.summary || 'No summary available.';

  article.append(title, meta, excerpt);
  return article;
}

function matchingDocuments() {
  const languages = checked('language');
  const genres    = checked('genre');
  const locations = checked('location');
  const q = submittedQuery.toLocaleLowerCase();

  return documents.filter((r) => {
    const text  = `${r.title || ''} ${r.summary || ''}`.toLocaleLowerCase();
    const langs = r.languages?.length ? r.languages : ['und'];
    return (!q || text.includes(q))
      && (!languages.length || languages.some((v) => langs.includes(v)))
      && (!genres.length    || genres.includes(r.genre || 'unknown'))
      && (!locations.length || locations.includes(r.location || 'unknown'));
  });
}

function activeFilterCount() {
  return checked('language').length + checked('genre').length + checked('location').length;
}

function updateCounts() {
  for (const span of document.querySelectorAll('.filter-bar .count')) {
    const n = checked(span.dataset.group).length;
    span.textContent = n ? `(${n})` : '';
  }
}

function renderSearch() {
  const matches = matchingDocuments();
  updateCounts();
  get('results').replaceChildren();

  if (!documents.length) {
    get('search-status').textContent = 'No documents yet. Upload files and Synchronize to populate your library.';
  } else {
    const filtered = submittedQuery || activeFilterCount();
    get('search-status').textContent = filtered
      ? `${matches.length} of ${documents.length} documents match.`
      : `Showing all ${documents.length} documents.`;
    get('results').append(
      ...matches.slice(page * pageSize, (page + 1) * pageSize).map(documentCard),
    );
  }

  const total = matches.length;
  get('page-status').textContent = total
    ? `Page ${page + 1} of ${Math.ceil(total / pageSize)}`
    : 'No results to display';
  get('previous').disabled = page === 0;
  get('next').disabled = (page + 1) * pageSize >= total;
}

function filterOption(group, value, label) {
  const wrap = document.createElement('label');
  const input = document.createElement('input');
  input.type  = 'checkbox';
  input.name  = group;
  input.value = value;
  wrap.append(input, document.createTextNode(' ' + label));
  return wrap;
}

function distinct(selector) {
  return [...new Set(documents.flatMap(selector))].filter(Boolean)
    .sort((a, b) => a.localeCompare(b));
}

function buildFilters() {
  const locations = distinct((r) => [r.location || 'unknown']);
  const genres    = distinct((r) => [r.genre    || 'unknown']);
  const languages = distinct((r) => r.languages?.length ? r.languages : ['und']);

  get('location-filters').replaceChildren(
    ...locations.map((v) => filterOption('location', v, v === 'unknown' ? 'Unknown' : v)));
  get('genre-filters').replaceChildren(
    ...genres.map((v) => filterOption('genre', v, v === 'unknown' ? 'Unknown' : v)));
  get('language-filters').replaceChildren(
    ...languages.map((v) => filterOption('language', v, LANG_LABELS[v] || v)));
}

get('search-form').addEventListener('submit', (e) => {
  e.preventDefault();
  submittedQuery = get('query').value.trim();
  page = 0;
  renderSearch();
});

get('filter-bar').addEventListener('change', () => { page = 0; renderSearch(); });

get('clear-filters').addEventListener('click', () => {
  document.querySelectorAll('.filter-bar input[type="checkbox"]').forEach((i) => { i.checked = false; });
  page = 0;
  renderSearch();
});

for (const [id, step] of [['previous', -1], ['next', 1]]) {
  get(id).addEventListener('click', () => { page += step; renderSearch(); });
}

document.addEventListener('click', (e) => {
  if (e.target.closest('.filter-bar')) return;
  document.querySelectorAll('.filter-bar details[open]').forEach((d) => { d.open = false; });
});

// ─────────────────────────────────────────────────────────────────────────────
// Upload page  — local queue only, no server call on upload
// ─────────────────────────────────────────────────────────────────────────────

const SYNC_LAST_KEY  = 'msf_last_sync_ts';
const SYNC_LOCAL_KEY = 'msf_local_uploads';  // [{name, title, author, date, size}]

function _getLastSyncTime()      { const s = localStorage.getItem(SYNC_LAST_KEY); return s ? new Date(s) : null; }
function _setLastSyncTime(d)     { localStorage.setItem(SYNC_LAST_KEY, (d || new Date()).toISOString()); }
function _getQueue()             { try { return JSON.parse(localStorage.getItem(SYNC_LOCAL_KEY) || '[]'); } catch { return []; } }
function _saveQueue(list)        { localStorage.setItem(SYNC_LOCAL_KEY, JSON.stringify(list)); }

// Auto-set today's date into the hidden field whenever the form is touched.
function _setTodayDate() {
  const input = get('up-date');
  if (input) input.value = new Date().toISOString().slice(0, 10);
}

function _renderUploadQueue() {
  const queue = _getQueue();
  const wrap  = get('upload-queue-wrap');
  const list  = get('upload-queue');
  if (!wrap || !list) return;

  if (!queue.length) {
    wrap.style.display = 'none';
    return;
  }
  wrap.style.display = '';
  list.replaceChildren(...queue.map((entry) => {
    const li = document.createElement('li');
    li.className = 'upload-queue-item';

    const info = document.createElement('span');
    info.textContent = `${entry.title || entry.name}`;
    const meta = document.createElement('span');
    meta.className = 'upload-queue-meta';
    meta.textContent = `${entry.author} · ${entry.date} · ${(entry.size / 1024).toFixed(1)} KB`;

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'upload-queue-remove';
    remove.setAttribute('aria-label', `Remove ${entry.name}`);
    remove.textContent = '✕';
    remove.addEventListener('click', () => {
      _saveQueue(_getQueue().filter((e) => e.name !== entry.name));
      _renderUploadQueue();
      _renderSyncPanel();
    });

    li.append(info, meta, remove);
    return li;
  }));
}

// Set date on page load and whenever the upload page becomes active.
_setTodayDate();

get('upload-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const fileInput  = get('up-file');
  const authorInput = get('up-author');
  const titleInput = get('up-title');
  const status     = get('up-status');

  const file   = fileInput.files[0];
  const author = authorInput.value.trim();
  const title  = titleInput.value.trim();
  const date   = get('up-date').value || new Date().toISOString().slice(0, 10);

  // Validation
  if (!file)   { status.textContent = 'Please select a file.';   return; }
  if (!author) { status.textContent = 'Author is required.';     return; }
  if (!title)  { status.textContent = 'Title is required.';      return; }

  const existing = _getQueue();
  if (existing.some((e) => e.name === file.name)) {
    status.textContent = `"${file.name}" is already in the queue.`;
    return;
  }

  // Add to local queue — no server call.
  _saveQueue([...existing, { name: file.name, title, author, date, size: file.size }]);
  status.textContent = `"${title}" added to the queue. Go to Synchronize to index it.`;

  // Reset form fields but keep the date.
  fileInput.value    = '';
  authorInput.value  = '';
  titleInput.value   = '';
  _setTodayDate();

  _renderUploadQueue();
  // Update the sync panel badge if already rendered.
  _renderSyncPanel();
});

// ─────────────────────────────────────────────────────────────────────────────
// Synchronize page
// ─────────────────────────────────────────────────────────────────────────────

function _relativeTime(date) {
  const min = Math.floor((Date.now() - date.getTime()) / 60000);
  if (min < 1)  return 'Just now';
  if (min < 60) return `${min} minute${min === 1 ? '' : 's'} ago`;
  const h = Math.floor(min / 60);
  if (h < 24)   return `${h} hour${h === 1 ? '' : 's'} ago`;
  const d = Math.floor(h / 24);
  return `${d} day${d === 1 ? '' : 's'} ago`;
}

function _syncFileItem(label, badgeText, badgeClass) {
  const li    = document.createElement('li');
  const badge = document.createElement('span');
  badge.className  = `sync-file-badge ${badgeClass}`;
  badge.textContent = badgeText;
  li.append(badge, document.createTextNode(' ' + label));
  return li;
}

function _emptyNote(text) {
  const li = document.createElement('li');
  li.style.cssText = 'list-style:none;padding:6px 0;color:#716363;font-size:13px;border:none';
  li.textContent   = text;
  return li;
}

function _renderSyncPanel() {
  const lastSync = _getLastSyncTime();
  const timeEl   = get('sync-last-time');
  const badgeEl  = get('sync-badge');
  if (!timeEl) return;

  // ── Last sync time ───────────────────────────────────────────────────────
  timeEl.textContent = lastSync
    ? `${lastSync.toLocaleString()}  (${_relativeTime(lastSync)})`
    : 'Never synchronized';

  const queue = _getQueue();

  // ── Badge ────────────────────────────────────────────────────────────────
  if (!lastSync) {
    badgeEl.textContent = 'Unknown';
    badgeEl.className   = 'sync-badge sync-badge--unknown';
  } else if (queue.length || (Date.now() - lastSync.getTime()) / 3600000 > 24) {
    badgeEl.textContent = 'Out of sync';
    badgeEl.className   = 'sync-badge sync-badge--stale';
  } else {
    badgeEl.textContent = 'Up to date';
    badgeEl.className   = 'sync-badge sync-badge--ok';
  }

  // ── Outgoing: queued uploads ─────────────────────────────────────────────
  const outList = get('outgoing-list');
  get('outgoing-count').textContent = queue.length || '0';
  outList.replaceChildren();
  if (queue.length) {
    outList.append(...queue.map((e) =>
      _syncFileItem(`${e.title} (${e.name})`, 'Queued', 'sync-file-badge--local')));
  } else {
    outList.append(_emptyNote('No uploads queued — nothing to push.'));
  }

  // ── Incoming: new docs in the collection since last sync ─────────────────
  // These are documents in window.MSF_DOCUMENTS whose date is after lastSync.
  const inList = get('incoming-list');
  let incoming = [];
  if (lastSync) {
    incoming = documents.filter((r) => {
      if (!r.date) return false;
      const d = new Date(r.date);
      return !isNaN(d.getTime()) && d > lastSync;
    });
  }
  get('incoming-count').textContent = incoming.length || '0';
  inList.replaceChildren();
  if (incoming.length) {
    inList.append(...incoming.slice(0, 10).map((r) =>
      _syncFileItem(r.title || r.id, 'New', 'sync-file-badge--new')));
    if (incoming.length > 10) {
      inList.append(_emptyNote(`…and ${incoming.length - 10} more.`));
    }
  } else {
    inList.append(_emptyNote(
      lastSync
        ? 'No new documents added since your last sync.'
        : 'Sync now to check for available documents.',
    ));
  }
}

async function _performSync() {
  const btn      = get('sync-now');
  const progress = get('sync-progress');
  const badgeEl  = get('sync-badge');
  const queue    = _getQueue();

  btn.disabled = true;
  btn.classList.add('spinning');
  badgeEl.textContent = 'Syncing…';
  badgeEl.className   = 'sync-badge sync-badge--syncing';
  progress.textContent = 'Indexing documents and refreshing search…';

  try {
    // Pass the queue metadata to the server so it can create proper Parsed stubs.
    const resp = await fetch('/api/sync', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ queue }),
    });

    if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
    const result = await resp.json();

    _setLastSyncTime(new Date());
    _saveQueue([]);       // clear the local queue
    _renderUploadQueue(); // refresh the upload page queue list

    const syncedCount = (result.synced || []).length;
    const errorCount  = (result.errors || []).length;

    // ── Hot-reload the Search page with fresh data ───────────────────────
    if (Array.isArray(result.records) && result.records.length) {
      documents.length = 0;
      result.records.forEach((r) => documents.push(r));
      buildFilters();
      page = 0;
      renderSearch();
    }

    if (errorCount && !syncedCount) {
      progress.textContent = `Sync failed with ${errorCount} error(s). Check the server terminal.`;
    } else if (syncedCount) {
      const total = result.total_documents || documents.length;
      progress.textContent = `Done — ${syncedCount} file(s) indexed. Your library now has ${total} documents.`;
    } else {
      progress.textContent = 'Already up to date — nothing new to sync.';
    }

  } catch (err) {
    progress.textContent = `Sync failed: ${err.message}. Is the server running? (python server.py)`;
    badgeEl.textContent = 'Error';
    badgeEl.className   = 'sync-badge sync-badge--stale';
  } finally {
    btn.disabled = false;
    btn.classList.remove('spinning');
    _renderSyncPanel();
    setTimeout(() => {
      if (!progress.textContent.includes('failed') && !progress.textContent.includes('Error')) {
        progress.textContent = '';
      }
    }, 7000);
  }
}

get('sync-now').addEventListener('click', _performSync);

// Keep relative-time label fresh every minute.
setInterval(() => {
  const t  = _getLastSyncTime();
  const el = get('sync-last-time');
  if (t && el) el.textContent = `${t.toLocaleString()}  (${_relativeTime(t)})`;
}, 60000);

// ─────────────────────────────────────────────────────────────────────────────
// Initial render
// ─────────────────────────────────────────────────────────────────────────────

buildFilters();
renderSearch();
_renderUploadQueue();
_renderSyncPanel();
