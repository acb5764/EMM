const CART_KEY = 'emrCart';

function getCart() {
  try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; }
  catch { return {}; }
}

function saveCart(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  updateCartBadge();
}

function addToCart(id, qty) {
  const cart = getCart();
  cart[id] = (cart[id] || 0) + qty;
  saveCart(cart);
}

function setCartQty(id, qty) {
  const cart = getCart();
  if (qty <= 0) delete cart[id];
  else cart[id] = qty;
  saveCart(cart);
}

function removeFromCart(id) {
  setCartQty(id, 0);
}

function clearCart() {
  localStorage.removeItem(CART_KEY);
  updateCartBadge();
}

function cartCount() {
  return Object.values(getCart()).reduce((a, b) => a + b, 0);
}

function updateCartBadge() {
  const n = cartCount();
  document.querySelectorAll('[data-cart-badge]').forEach((el) => {
    el.textContent = String(n);
    el.hidden = n === 0;
  });
}
