const CATEGORY_LABELS = {
  'trees-scions': 'Trees & Scions',
  'fresh-fruit': 'Fresh Fruit',
  'vegetables-herbs': 'Vegetables & Herbs',
  'cottage-foods': 'Cottage Foods'
};

const PLACEHOLDER_IMG = 'data:image/svg+xml;utf8,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">' +
  '<rect width="100%" height="100%" fill="#f0ead6"/>' +
  '<text x="50%" y="50%" font-family="sans-serif" font-size="18" fill="#8a7a52" text-anchor="middle" dominant-baseline="middle">Photo coming soon</text>' +
  '</svg>'
);

let ALL_ITEMS = [];
let activeCategory = 'all';
let searchTerm = '';

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function computeAvailability(item) {
  if (item.status === 'seasonal') return { label: 'Seasonal', cssClass: 'badge-seasonal' };
  if (item.status === 'coming-soon') return { label: 'Coming Soon', cssClass: 'badge-coming-soon' };
  if (item.quantityOnHand <= 0) return { label: 'Sold Out', cssClass: 'badge-sold-out' };
  if (item.quantityOnHand <= (item.lowStockThreshold ?? 3)) return { label: 'Low Stock', cssClass: 'badge-low-stock' };
  return { label: 'In Stock', cssClass: 'badge-in-stock' };
}

function propagationLabel(item) {
  if (item.propagation === 'grafted') return 'Grafted';
  if (item.propagation === 'seed') return 'From Seed';
  return null;
}

function formatPrice(item) {
  if (item.price == null) return item.priceNote ? escapeHtml(item.priceNote) : 'Call for pricing';
  const price = `$${item.price.toFixed(2)} / ${escapeHtml(item.unit)}`;
  return item.priceNote ? `${price} (${escapeHtml(item.priceNote)})` : price;
}

function itemCardHtml(item, opts = {}) {
  const { showActions = true } = opts;
  const avail = computeAvailability(item);
  const hasPhoto = !!(item.photos && item.photos[0]);
  const photo = hasPhoto ? item.photos[0] : PLACEHOLDER_IMG;
  const disabled = avail.label === 'Sold Out' || avail.label === 'Coming Soon';
  const propagation = propagationLabel(item);

  const actionsHtml = showActions
    ? `<div class="card-actions">
        <label class="qty-label">Qty
          <input type="number" min="1" value="1" class="qty-input" ${disabled ? 'disabled' : ''} aria-label="Quantity for ${escapeHtml(item.name)}">
        </label>
        <button type="button" class="btn btn-primary add-btn" ${disabled ? 'disabled' : ''}>Add to Request</button>
      </div>`
    : `<div class="card-actions"><a class="btn btn-secondary" href="catalog.html">View in Catalog</a></div>`;

  return `
    <article class="card" data-id="${item.id}">
      <div class="card-photo${hasPhoto ? '' : ' no-photo'}">
        <img src="${photo}" alt="${escapeHtml(item.name)}" loading="lazy"
             onerror="this.onerror=null;this.src='${PLACEHOLDER_IMG}';this.closest('.card-photo').classList.add('no-photo');">
        <span class="badge ${avail.cssClass}">${avail.label}</span>
      </div>
      <div class="card-body">
        <h3>${escapeHtml(item.name)}</h3>
        ${item.variety ? `<p class="card-variety">${escapeHtml(item.variety)}</p>` : ''}
        ${propagation ? `<span class="tag tag-propagation">${propagation}</span>` : ''}
        <p class="card-desc">${escapeHtml(item.description)}</p>
        ${item.seasonNote ? `<p class="card-season">${escapeHtml(item.seasonNote)}</p>` : ''}
        <p class="card-price">${formatPrice(item)}</p>
        ${avail.label !== 'Coming Soon' ? `<p class="card-qty">${item.quantityOnHand} on hand</p>` : ''}
      </div>
      ${actionsHtml}
    </article>`;
}

function render() {
  const grid = document.getElementById('catalog-grid');
  if (!grid) return;
  const term = searchTerm.trim().toLowerCase();

  const filtered = ALL_ITEMS
    .filter((item) => activeCategory === 'all' || item.category === activeCategory)
    .filter((item) => !term || item.name.toLowerCase().includes(term) || item.description.toLowerCase().includes(term))
    .sort((a, b) => {
      if (!!b.featured !== !!a.featured) return b.featured ? 1 : -1;
      if ((a.sortOrder ?? 0) !== (b.sortOrder ?? 0)) return (a.sortOrder ?? 0) - (b.sortOrder ?? 0);
      return a.name.localeCompare(b.name);
    });

  if (filtered.length === 0) {
    grid.innerHTML = '<p class="empty-state">No items match your filters right now. Try a different category or search term.</p>';
    return;
  }

  grid.innerHTML = filtered.map((item) => itemCardHtml(item)).join('');

  grid.querySelectorAll('.card').forEach((card) => {
    const id = card.dataset.id;
    const btn = card.querySelector('.add-btn');
    const qtyInput = card.querySelector('.qty-input');
    if (btn && !btn.disabled) {
      btn.addEventListener('click', () => {
        const qty = Math.max(1, parseInt(qtyInput.value, 10) || 1);
        addToCart(id, qty);
        btn.textContent = 'Added ✓';
        setTimeout(() => { btn.textContent = 'Add to Request'; }, 1200);
      });
    }
  });
}

function initFilters() {
  document.querySelectorAll('.category-filter').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.category-filter').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      activeCategory = btn.dataset.category;
      render();
    });
  });

  const search = document.getElementById('catalog-search');
  if (search) {
    search.addEventListener('input', () => {
      searchTerm = search.value;
      render();
    });
  }
}

async function loadCatalog() {
  try {
    const res = await fetch('data/inventory.json');
    const data = await res.json();
    ALL_ITEMS = data.items || [];
    const updatedEl = document.getElementById('inventory-updated');
    if (updatedEl && data.updated) updatedEl.textContent = `Inventory last updated: ${data.updated}`;
    render();
  } catch (err) {
    console.error(err);
    const grid = document.getElementById('catalog-grid');
    if (grid) grid.innerHTML = '<p class="empty-state">Sorry, we could not load the catalog right now. Please try again later or contact us directly.</p>';
  }
}

async function loadFeatured() {
  const container = document.getElementById('featured-grid');
  if (!container) return;
  try {
    const res = await fetch('data/inventory.json');
    const data = await res.json();
    const items = (data.items || []).filter((i) => i.featured).slice(0, 4);
    container.innerHTML = items.length
      ? items.map((i) => itemCardHtml(i, { showActions: false })).join('')
      : '<p class="empty-state">Check back soon for featured items.</p>';
  } catch (err) {
    console.error(err);
    container.innerHTML = '<p class="empty-state">Unable to load featured items right now.</p>';
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  if (document.getElementById('catalog-grid')) {
    initFilters();
    await loadCatalog();
  }
  if (document.getElementById('featured-grid')) {
    await loadFeatured();
  }
  if (typeof updateCartBadge === 'function') updateCartBadge();
});
