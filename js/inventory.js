// TODO: replace with the deployed Worker URL from worker/README.md
const INVENTORY_API_URL = "https://emm-inventory-api.aaron-d6f.workers.dev";

document.addEventListener('DOMContentLoaded', async () => {
  const tbody = document.getElementById('inventory-tbody');
  if (!tbody) return;

  const summaryEl = document.getElementById('inventory-summary');
  const updatedEl = document.getElementById('inventory-updated');
  const search = document.getElementById('inventory-search');
  const issuesToggle = document.getElementById('inventory-issues-toggle');

  let items = [];
  let invActiveCategory = 'all';
  let invSearchTerm = '';
  let invIssuesOnly = false;

  try {
    const res = await fetch(INVENTORY_API_URL);
    const data = await res.json();
    items = data.items || [];
    if (updatedEl && data.updated) updatedEl.textContent = `Inventory last updated: ${data.updated}`;
  } catch (err) {
    console.error(err);
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">Sorry, we could not load inventory right now.</td></tr>';
    return;
  }

  function renderSummary() {
    const lowStock = items.filter((i) => computeAvailability(i).label === 'Low Stock').length;
    const soldOut = items.filter((i) => computeAvailability(i).label === 'Sold Out').length;
    const totalUnits = items.reduce((sum, i) => sum + (i.quantityOnHand || 0), 0);
    summaryEl.innerHTML = `
      <div class="inventory-stat"><strong>${items.length}</strong><span>Items tracked</span></div>
      <div class="inventory-stat"><strong>${totalUnits}</strong><span>Units on hand</span></div>
      <div class="inventory-stat"><strong>${lowStock}</strong><span>Low stock</span></div>
      <div class="inventory-stat"><strong>${soldOut}</strong><span>Sold out</span></div>
    `;
  }

  function render() {
    const term = invSearchTerm.trim().toLowerCase();
    const filtered = items
      .filter((i) => invActiveCategory === 'all' || i.category === invActiveCategory)
      .filter((i) => !term || i.name.toLowerCase().includes(term) || (i.variety || '').toLowerCase().includes(term))
      .filter((i) => !invIssuesOnly || ['Low Stock', 'Sold Out'].includes(computeAvailability(i).label))
      .sort((a, b) => {
        if (a.category !== b.category) return a.category.localeCompare(b.category);
        if ((a.sortOrder ?? 0) !== (b.sortOrder ?? 0)) return (a.sortOrder ?? 0) - (b.sortOrder ?? 0);
        return a.name.localeCompare(b.name);
      });

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No items match your filters.</td></tr>';
      return;
    }

    let lastCategory = null;
    const rows = [];
    filtered.forEach((item) => {
      if (item.category !== lastCategory) {
        lastCategory = item.category;
        rows.push(`<tr class="inventory-category-row"><td colspan="5">${escapeHtml(CATEGORY_LABELS[item.category] || item.category)}</td></tr>`);
      }
      const avail = computeAvailability(item);
      const propagation = item.propagation === 'grafted' ? 'Grafted'
        : item.propagation === 'seed' ? 'From Seed'
        : item.propagation === 'unknown' ? 'Unknown' : '—';
      rows.push(`<tr>
        <td>${escapeHtml(item.name)}</td>
        <td class="qty-cell">${item.quantityOnHand}</td>
        <td>${escapeHtml(item.unit)}</td>
        <td>${escapeHtml(propagation)}</td>
        <td><span class="badge badge-inline ${avail.cssClass}">${avail.label}</span></td>
      </tr>`);
    });
    tbody.innerHTML = rows.join('');
  }

  renderSummary();
  render();

  document.querySelectorAll('.category-filter').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.category-filter').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      invActiveCategory = btn.dataset.category;
      render();
    });
  });

  if (search) {
    search.addEventListener('input', () => {
      invSearchTerm = search.value;
      render();
    });
  }

  if (issuesToggle) {
    issuesToggle.addEventListener('change', () => {
      invIssuesOnly = issuesToggle.checked;
      render();
    });
  }
});
