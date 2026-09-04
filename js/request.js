// TODO: create a Formspree form (https://formspree.io) under Em.r.mangos@gmail.com
// and replace this with the real endpoint before launch.
const REQUEST_FORMSPREE_ENDPOINT = 'https://formspree.io/f/xzebvkaw';

document.addEventListener('DOMContentLoaded', async () => {
  const container = document.getElementById('request-items');
  const form = document.getElementById('request-form');
  const orderSummaryField = document.getElementById('order-summary-field');
  const totalEl = document.getElementById('request-total');
  const emptyMsg = document.getElementById('request-empty');
  if (!container || !form) return;

  let items = [];
  try {
    const res = await fetch(INVENTORY_API_URL);
    const data = await res.json();
    items = data.items || [];
  } catch (err) {
    console.error(err);
  }

  const itemsById = () => Object.fromEntries(items.map((i) => [i.id, i]));

  function renderCart() {
    const cart = getCart();
    const byId = itemsById();
    const ids = Object.keys(cart);

    if (ids.length === 0) {
      container.innerHTML = '';
      emptyMsg.hidden = false;
      form.hidden = true;
      totalEl.textContent = '';
      return;
    }

    emptyMsg.hidden = true;
    form.hidden = false;

    let total = 0;
    let allPriced = true;
    let removedAny = false;

    const rows = ids.map((id) => {
      const item = byId[id];
      if (!item) {
        removedAny = true;
        return null;
      }
      const avail = computeAvailability(item);
      const soldOut = avail.label === 'Sold Out' || avail.label === 'Coming Soon';
      if (soldOut) {
        removedAny = true;
        return `<tr class="request-row unavailable"><td colspan="4">${escapeHtml(item.name)} is no longer available (${avail.label}) and has been removed from your request.</td></tr>`;
      }
      const lineTotal = item.price != null ? item.price * cart[id] : null;
      if (lineTotal == null) allPriced = false; else total += lineTotal;
      return `<tr class="request-row" data-id="${id}">
        <td>${escapeHtml(item.name)}${item.variety ? ` (${escapeHtml(item.variety)})` : ''}</td>
        <td><input type="number" min="1" class="qty-input" value="${cart[id]}" aria-label="Quantity for ${escapeHtml(item.name)}"></td>
        <td>${item.price != null ? `$${item.price.toFixed(2)} / ${escapeHtml(item.unit)}` : (item.priceNote ? escapeHtml(item.priceNote) : 'Call for pricing')}</td>
        <td>${lineTotal != null ? `$${lineTotal.toFixed(2)}` : '—'} <button type="button" class="link-btn remove-btn">Remove</button></td>
      </tr>`;
    });

    if (removedAny) {
      ids.forEach((id) => {
        const item = byId[id];
        if (!item || ['Sold Out', 'Coming Soon'].includes(computeAvailability(item).label)) {
          removeFromCart(id);
        }
      });
    }

    container.innerHTML = `<table class="request-table">
      <thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Line Total</th></tr></thead>
      <tbody>${rows.join('')}</tbody>
    </table>`;

    totalEl.textContent = allPriced
      ? `Estimated total: $${total.toFixed(2)} (final pricing confirmed by Earth Mother Mango before fulfillment)`
      : `Estimated total: $${total.toFixed(2)}+ (some items require a call for current pricing; final pricing confirmed by Earth Mother Mango before fulfillment)`;

    container.querySelectorAll('.qty-input').forEach((input) => {
      input.addEventListener('change', () => {
        const row = input.closest('.request-row');
        const qty = Math.max(1, parseInt(input.value, 10) || 1);
        setCartQty(row.dataset.id, qty);
        renderCart();
      });
    });
    container.querySelectorAll('.remove-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const row = btn.closest('.request-row');
        removeFromCart(row.dataset.id);
        renderCart();
      });
    });
  }

  renderCart();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const cart = getCart();
    const byId = itemsById();
    const lines = Object.entries(cart).map(([id, qty]) => {
      const item = byId[id];
      if (!item) return null;
      const priceText = item.price != null ? `$${item.price.toFixed(2)}` : (item.priceNote || 'call for pricing');
      const lineTotal = item.price != null ? ` = $${(item.price * qty).toFixed(2)}` : '';
      return `${qty} x ${item.name}${item.variety ? ` (${item.variety})` : ''} @ ${priceText}${lineTotal}`;
    }).filter(Boolean);

    orderSummaryField.value = lines.join('\n');

    const statusEl = document.getElementById('request-status');
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    statusEl.textContent = 'Sending your request...';
    statusEl.className = 'form-status';

    try {
      const res = await fetch(REQUEST_FORMSPREE_ENDPOINT, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: new FormData(form)
      });
      if (!res.ok) throw new Error('Request failed');
      clearCart();
      form.hidden = true;
      container.innerHTML = '';
      emptyMsg.hidden = true;
      totalEl.textContent = '';
      statusEl.textContent = "Thanks! We'll be in touch within 1-2 days to confirm your order.";
      statusEl.className = 'form-status success';
    } catch (err) {
      console.error(err);
      const mailBody = encodeURIComponent(
        `Order request:\n\n${lines.join('\n')}\n\nName: ${form.name.value}\nEmail: ${form.email.value}\nPhone: ${form.phone.value}\nNotes: ${form.notes.value}`
      );
      statusEl.innerHTML = `Sorry, something went wrong sending your request. Please <a href="mailto:Em.r.mangos@gmail.com?subject=Order%20Request&body=${mailBody}">email us directly</a> with your order instead.`;
      statusEl.className = 'form-status error';
      submitBtn.disabled = false;
    }
  });
});
