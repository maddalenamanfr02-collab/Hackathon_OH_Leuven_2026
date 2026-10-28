/* Standalone demonstration data. This file never changes the main collection.
 * Replace searchDemo() with a service request when connecting a real algorithm.
 */
const demoDocuments = [
  { id: 'a', title: 'Care planning overview', category: 'Guidelines', excerpt: 'A fictional document used to demonstrate a guideline result.', text: 'This is a placeholder document view. In the connected application, this area could show the retrieved document or an excerpt, with access to its original file.' },
  { id: 'b', title: 'Community care research', category: 'Research', excerpt: 'A fictional article used to demonstrate a research result.', text: 'This tab represents a second opened document. Switch back to Search results to open another record without losing your query or category selection.' },
  { id: 'c', title: 'Care programme field notes', category: 'Field notes', excerpt: 'A fictional record used to demonstrate a field report result.', text: 'This is a demonstration of document navigation only. It contains no medical recommendations and does not represent a document from your collection.' },
];
const categories = ['All results', 'Guidelines', 'Research', 'Field notes'];
let results = [];
let category = 'All results';
let activeDocument = 'results';
const opened = new Set();
const get = (id) => document.getElementById(id);

// Keep the algorithm boundary explicit: it returns records; rendering owns tabs.
function searchDemo(query) {
  return demoDocuments.filter((record) =>
    `${record.title} ${record.excerpt}`.toLowerCase().includes(query.toLowerCase()),
  );
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

// Native buttons support activation; roving focus adds standard tab navigation.
function tabButton(id, label, selected, panelId, activate) {
  const button = element('button', label);
  button.type = 'button';
  button.id = id;
  button.setAttribute('role', 'tab');
  button.setAttribute('aria-selected', String(selected));
  button.setAttribute('aria-controls', panelId);
  button.tabIndex = selected ? 0 : -1;
  button.addEventListener('click', activate);
  return button;
}

function panel(id, tabId, hidden) {
  const node = element('div');
  node.id = id;
  node.setAttribute('role', 'tabpanel');
  node.setAttribute('aria-labelledby', tabId);
  node.tabIndex = 0;
  node.hidden = hidden;
  return node;
}

function render() {
  const tabs = get('workspace-tabs');
  const panels = get('workspace-panels');
  tabs.replaceChildren();
  panels.replaceChildren();
  const select = (id) => {
    activeDocument = id;
    render();
    get(`tab-${id}`).focus();
  };
  tabs.append(tabButton('tab-results', 'Search results', activeDocument === 'results', 'panel-results', () => select('results')));
  const searchPanel = panel('panel-results', 'tab-results', activeDocument !== 'results');
  const categoryTabs = element('div', '', 'tabs');
  categoryTabs.setAttribute('role', 'tablist');
  categoryTabs.setAttribute('aria-label', 'Result categories');
  searchPanel.append(categoryTabs);

  categories.forEach((name, index) => {
    const count = results.filter((record) => name === 'All results' || record.category === name).length;
    const tabId = `category-${index}`;
    const panelId = `category-panel-${index}`;
    categoryTabs.append(tabButton(tabId, `${name} (${count})`, category === name, panelId, () => {
      category = name;
      render();
      get(tabId).focus();
    }));
    const resultPanel = panel(panelId, tabId, category !== name);
    const visible = results.filter((record) => name === 'All results' || record.category === name);
    if (!visible.length) resultPanel.append(element('p', 'No matching demonstration documents. Try “care” or another category.'));
    visible.forEach((record) => {
      const card = element('article', '', 'card');
      card.append(element('span', record.category, 'tag'), element('h2', record.title), element('p', record.excerpt));
      const open = element('button', 'Open document tab');
      open.type = 'button';
      open.addEventListener('click', () => { opened.add(record.id); select(record.id); });
      card.append(open);
      resultPanel.append(card);
    });
    searchPanel.append(resultPanel);
  });
  panels.append(searchPanel);

  for (const id of opened) {
    const record = demoDocuments.find((item) => item.id === id);
    tabs.append(tabButton(`tab-${id}`, record.title, activeDocument === id, `panel-${id}`, () => select(id)));
    const documentPanel = panel(`panel-${id}`, `tab-${id}`, activeDocument !== id);
    documentPanel.append(element('span', `${record.category} · Fictional document`, 'tag'), element('h2', record.title), element('p', record.text));
    const close = element('button', 'Close document tab');
    close.addEventListener('click', () => { opened.delete(id); select('results'); });
    documentPanel.append(close);
    panels.append(documentPanel);
  }
}

document.addEventListener('keydown', (event) => {
  if (event.target.getAttribute('role') !== 'tab') return;
  const tabs = [...event.target.parentElement.children];
  const index = tabs.indexOf(event.target);
  let target;
  if (event.key === 'ArrowRight') target = tabs[(index + 1) % tabs.length];
  if (event.key === 'ArrowLeft') target = tabs[(index - 1 + tabs.length) % tabs.length];
  if (event.key === 'Home') target = tabs[0];
  if (event.key === 'End') target = tabs[tabs.length - 1];
  if (target) { event.preventDefault(); target.click(); }
});

function submitSearch() {
  const input = get('demo-query');
  const query = input.value.trim();
  input.setCustomValidity(query ? '' : 'Enter a topic or keyword.');
  if (!input.reportValidity()) return;
  results = searchDemo(query);
  activeDocument = 'results';
  category = 'All results';
  get('demo-status').textContent = `${results.length} demonstration results for “${query}”.`;
  render();
}
get('demo-query').addEventListener('input', () => get('demo-query').setCustomValidity(''));
get('demo-search').addEventListener('submit', (event) => { event.preventDefault(); submitSearch(); });
submitSearch();
