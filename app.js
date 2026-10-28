/* Collection state starts empty. No sample records or simulated backend operations.
 * A future service adapter must supply real records and handle retrieval ranking.
 * Local text matching below is only for records explicitly supplied to this UI.
 */
// Service adapter hook: msf-retrieval `export` writes window.MSF_DOCUMENTS
// (see documents.js). Falls back to an empty collection when absent.
const documents = Array.isArray(window.MSF_DOCUMENTS) ? window.MSF_DOCUMENTS : [];
const pageSize = 20;
let submittedQuery = '';
let page = 0;

const get = (id) => document.getElementById(id);
const checked = (name) => Array.from(
  document.querySelectorAll(`input[name="${name}"]:checked`),
  (input) => input.value,
);

// Build document labels with textContent so document text cannot inject HTML.
function documentCard(record) {
  const article = document.createElement('article');
  article.className = 'card';
  const title = document.createElement('h3');
  title.dir = 'auto';
  title.textContent = record.title || 'Title unavailable';
  const excerpt = document.createElement('p');
  excerpt.dir = 'auto';
  excerpt.textContent = record.summary || 'No summary available.';
  article.append(title, excerpt);
  return article;
}

function renderSearch() {
  const languages = checked('language');
  const genres = checked('genre');
  const matches = documents.filter((record) => {
    const text = `${record.title || ''} ${record.summary || ''}`.toLocaleLowerCase();
    const recordLanguages = record.languages?.length ? record.languages : ['und'];
    return text.includes(submittedQuery.toLocaleLowerCase())
      && (!languages.length || languages.some((value) => recordLanguages.includes(value)))
      && (!genres.length || genres.includes(record.genre || 'unknown'));
  });

  get('results').replaceChildren();
  if (!submittedQuery) {
    get('search-status').textContent = 'Enter a topic or keyword to begin.';
  } else if (!documents.length) {
    get('search-status').textContent = `No documents connected. Your search for “${submittedQuery}” is ready once a local collection is connected.`;
  } else {
    get('search-status').textContent = `${matches.length} results for “${submittedQuery}”.`;
    get('results').append(...matches.slice(page * pageSize, (page + 1) * pageSize).map(documentCard));
  }

  const total = submittedQuery ? matches.length : 0;
  get('page-status').textContent = total ? `Page ${page + 1} of ${Math.ceil(total / pageSize)}` : 'No results to display';
  get('previous').disabled = page === 0;
  get('next').disabled = (page + 1) * pageSize >= total;
}

get('search-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const input = get('query');
  input.setCustomValidity(input.value.trim() ? '' : 'Enter a topic or keyword.');
  if (!input.reportValidity()) return;
  submittedQuery = input.value.trim();
  page = 0;
  renderSearch();
});
get('query').addEventListener('input', () => get('query').setCustomValidity(''));

// OR within each filter group; AND between language and genre groups.
document.querySelector('.filters').addEventListener('change', () => {
  page = 0;
  renderSearch();
});
get('clear-filters').addEventListener('click', () => {
  document.querySelectorAll('.filters input').forEach((input) => { input.checked = false; });
  page = 0;
  renderSearch();
});
for (const [id, step] of [['previous', -1], ['next', 1]]) {
  get(id).addEventListener('click', () => { page += step; renderSearch(); });
}

// Keep the Unknown option available before a metadata vocabulary is connected.
for (const genre of new Set(['unknown', ...documents.map((record) => record.genre || 'unknown')])) {
  const label = document.createElement('label');
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.name = 'genre';
  input.value = genre;
  label.append(input, genre === 'unknown' ? 'Unknown' : genre);
  get('genre-filters').append(label);
}

get('find').addEventListener('input', () => {
  const query = get('find').value.trim().toLocaleLowerCase();
  const matches = documents.filter((record) => (record.title || '').toLocaleLowerCase().includes(query));
  get('document-list').replaceChildren(...matches.map(documentCard));
  get('documents-status').textContent = !documents.length
    ? 'No documents connected.'
    : `${matches.length} documents found.`;
});

// Show only the user's actual selection; do not claim files were processed.
get('files').addEventListener('change', (event) => {
  const rows = Array.from(event.target.files, (file) => {
    const row = document.createElement('li');
    row.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB · Not processed`;
    return row;
  });
  get('file-list').replaceChildren(...rows);
});
