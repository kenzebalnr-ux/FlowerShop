'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const money = value => `${new Intl.NumberFormat('kk-KZ').format(Number(value) || 0)} ₸`;
const safeImage = value => { try { const url = new URL(value, location.origin); return ['http:', 'https:'].includes(url.protocol) ? escapeHTML(url.href) : '/static/favicon.svg'; } catch { return '/static/favicon.svg'; } };
const readStorage = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const saveStorage = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Storage may be disabled in a private browser. */ } };
let storedCart = readStorage('flowershop-cart', []);
let storedFavorites = readStorage('flowershop-favorites', []);
const state = {
  products: [], categories: [], cache: new Map(),
  cart: Array.isArray(storedCart) ? storedCart.filter(item => Number.isInteger(item?.id) && Number.isInteger(item?.quantity) && item.quantity > 0 && item.quantity <= 20) : [],
  favorites: new Set(Array.isArray(storedFavorites) ? storedFavorites.filter(Number.isInteger) : []),
  favoriteOnly: false, category: '', search: '', sort: 'popular', min: '', max: '',
  user: null, token: '', authMode: 'login', checkoutAfterLogin: false, loading: false,
};
try { state.token = sessionStorage.getItem('flowershop-token') || ''; } catch { /* Session storage is optional. */ }
let catalogRequest = 0;
let toastTimer;
let searchTimer;

async function api(path, options = {}) {
  const headers = { Accept: 'application/json', ...options.headers };
  if (options.body) headers['Content-Type'] = 'application/json';
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let response;
  try { response = await fetch(`/api${path}`, { ...options, headers }); }
  catch { throw new Error('Сервермен байланыс үзілді. Интернетті тексеріп, қайта көріңіз.'); }
  let payload;
  try { payload = response.status === 204 ? null : await response.json(); }
  catch { payload = null; }
  if (!response.ok) {
    const detail = payload?.detail;
    let message = typeof detail === 'string' ? detail : (payload?.message || 'Сұраныс орындалмады. Деректерді тексеріп, қайталаңыз.');
    if (Array.isArray(detail)) message = detail.map(item => item.msg || 'Енгізілген деректерді тексеріңіз.').join(' ');
    const error = new Error(message);
    error.status = response.status;
    if (response.status === 401 && state.token) { clearSession(); }
    throw error;
  }
  return payload;
}

function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3400);
}

function openDialog(id) {
  $$('dialog[open]').forEach(dialog => dialog.close());
  const dialog = $(`#${id}`);
  dialog.showModal();
}

function closeDialog(dialog) { dialog.close(); }

function persistCart() {
  saveStorage('flowershop-cart', state.cart);
  updateCounters();
}

function updateCounters() {
  const count = state.cart.reduce((sum, item) => sum + item.quantity, 0);
  $('#cart-count').textContent = count;
  $('#cart-count').hidden = !count;
  $('#cart-button').setAttribute('aria-label', `Себетті ашу, ${count} гүл шоғы`);
  $('#favorite-count').textContent = state.favorites.size;
  $('#favorite-count').hidden = !state.favorites.size;
  $('#favorites-button').setAttribute('aria-pressed', String(state.favoriteOnly));
  $('#account-button').setAttribute('aria-label', state.user ? `${state.user.name}: жеке кабинет` : 'Жеке кабинетке кіру');
}

function categoryName(id) { return state.categories.find(category => category.id === id)?.name || 'Гүл шоғы'; }

function renderCategories() {
  $('#category-tabs').innerHTML = `<button class="category-tab${!state.category ? ' active' : ''}" data-category="" aria-pressed="${!state.category}">Барлық гүлдер</button>` + state.categories.map(category => `<button class="category-tab${String(category.id) === state.category ? ' active' : ''}" data-category="${category.id}" aria-pressed="${String(category.id) === state.category}">${escapeHTML(category.name)}</button>`).join('');
}

function skeletons() {
  $('#product-grid').innerHTML = Array.from({length: 8}, () => '<div aria-hidden="true"><div class="skeleton skeleton-image"></div><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line short"></div></div>').join('');
}

function renderProducts() {
  const products = state.products.filter(product => !state.favoriteOnly || state.favorites.has(product.id));
  $('#product-grid').setAttribute('aria-busy', 'false');
  $('#result-count').textContent = state.favoriteOnly ? `Таңдаулылар: ${products.length} гүл шоғы` : `${products.length} гүл шоғы табылды`;
  $('#catalog-title').innerHTML = state.favoriteOnly ? 'Жүрегіңіз қалаған <em>гүлдер</em>' : 'Сіздің ерекше <em>таңдауыңыз</em>';
  $('#reset-filters').hidden = !(state.favoriteOnly || state.category || state.search || state.min || state.max);
  if (!products.length) {
    $('#product-grid').innerHTML = `<div class="empty-state">${icon(state.favoriteOnly ? 'heart' : 'search')}<h3>${state.favoriteOnly ? 'Сүйікті гүлдеріңіз осында болады' : 'Гүл шоғы табылмады'}</h3><p>${state.favoriteOnly ? 'Ұнаған гүл шоғындағы жүрек белгісін басып, оны осы жерге сақтаңыз.' : 'Іздеу сөзін немесе баға аралығын өзгертіп көріңіз.'}</p><button class="button button-outline" data-reset>Барлық гүлдерді қарау</button></div>`;
    return;
  }
  $('#product-grid').innerHTML = products.map(product => {
    const favorite = state.favorites.has(product.id);
    const soldOut = product.stock <= 0;
    return `<article class="product-card"><button class="product-favorite${favorite ? ' selected' : ''}" data-favorite="${product.id}" aria-label="${escapeHTML(product.name)}: ${favorite ? 'таңдаулыдан алып тастау' : 'таңдаулыға қосу'}" aria-pressed="${favorite}">${icon('heart')}</button><button class="product-image-button" data-detail="${product.id}" aria-label="${escapeHTML(product.name)} — толық ақпарат">${product.badge ? `<span class="product-badge">${escapeHTML(product.badge)}</span>` : ''}<img src="${safeImage(product.image_url)}" alt="${escapeHTML(product.name)}" loading="lazy"></button><p class="product-category">${escapeHTML(categoryName(product.category_id))}</p><button class="product-name" data-detail="${product.id}">${escapeHTML(product.name)}</button><div class="product-bottom"><div><div class="product-meta"><span class="product-price">${money(product.price)}</span>${product.old_price > product.price ? `<span class="old-price">${money(product.old_price)}</span>` : ''}</div><p class="stock-hint">${soldOut ? 'Уақытша таусылды' : 'Тапсырыс беруге болады'}</p></div><button class="add-to-cart" data-add="${product.id}" aria-label="${escapeHTML(product.name)}: себетке қосу" ${soldOut ? 'disabled' : ''}>${icon('plus')}</button></div></article>`;
  }).join('');
  addImageFallbacks($('#product-grid'));
}

function addImageFallbacks(root) {
  $$('img', root).forEach(image => image.addEventListener('error', () => {
    image.src = '/static/favicon.svg';
    image.style.objectFit = 'contain';
    image.style.padding = '30px';
  }, {once: true}));
}

async function loadProducts() {
  const request = ++catalogRequest;
  state.loading = true;
  $('#product-grid').setAttribute('aria-busy', 'true');
  $('#result-count').textContent = 'Гүлдер жүктелуде…';
  const params = new URLSearchParams({sort: state.sort});
  if (state.category) params.set('category_id', state.category);
  if (state.search) params.set('search', state.search);
  if (state.min !== '') params.set('min_price', state.min);
  if (state.max !== '') params.set('max_price', state.max);
  try {
    const products = await api(`/products?${params}`);
    if (request !== catalogRequest) return;
    state.products = Array.isArray(products) ? products : products.items || [];
    state.products.forEach(product => state.cache.set(product.id, product));
    renderProducts();
  } catch (error) {
    if (request !== catalogRequest) return;
    $('#product-grid').setAttribute('aria-busy', 'false');
    $('#result-count').textContent = 'Каталог жүктелмеді';
    $('#product-grid').innerHTML = `<div class="empty-state">${icon('flower')}<h3>Бір сәт күте тұрыңыз</h3><p>${escapeHTML(error.message)}</p><button class="button button-primary" data-retry>Қайта жүктеу</button></div>`;
  } finally { if (request === catalogRequest) state.loading = false; }
}

async function resetFilters() {
  state.category = ''; state.search = ''; state.min = ''; state.max = ''; state.favoriteOnly = false;
  $('#search').value = ''; $('#min-price').value = ''; $('#max-price').value = '';
  $('#price-filter').open = false;
  renderCategories(); updateCounters();
  await loadProducts();
}

function toggleFavorite(id) {
  if (state.favorites.has(id)) { state.favorites.delete(id); toast('Гүл таңдаулылардан алынды'); }
  else { state.favorites.add(id); toast('Гүл таңдаулыларға сақталды'); }
  saveStorage('flowershop-favorites', [...state.favorites]);
  updateCounters(); renderProducts();
  if ($('#product-dialog').open) renderProductDetail(id);
}

function addToCart(id) {
  const product = state.cache.get(id);
  if (!product || product.stock <= 0) return toast('Бұл гүл шоғы уақытша таусылды');
  const existing = state.cart.find(item => item.id === id);
  if ((existing?.quantity || 0) >= Math.min(product.stock, 20)) return toast('Бір гүл шоғынан ең көбі 20 дана немесе қоймадағы санды алуға болады');
  if (existing) existing.quantity += 1;
  else state.cart.push({id, quantity: 1});
  persistCart();
  toast('Гүл шоғы себетке қосылды');
  if ($('#cart-dialog').open) renderCart();
}

function cartDetails() {
  return state.cart.map(item => ({...item, product: state.cache.get(item.id)})).filter(item => item.product);
}

function subtotal() { return cartDetails().reduce((sum, item) => sum + item.product.price * item.quantity, 0); }

async function refreshCartProducts(refreshAll = false) {
  const missing = state.cart.filter(item => refreshAll || !state.cache.has(item.id));
  if (!missing.length) return true;
  let available = true;
  await Promise.all(missing.map(async item => {
    try { state.cache.set(item.id, await api(`/products/${item.id}`)); }
    catch (error) {
      if (error.status === 404) {
        state.cart = state.cart.filter(row => row.id !== item.id);
        persistCart(); toast('Каталогтан алынған гүл себеттен өшірілді');
      } else available = false;
    }
  }));
  return available;
}

async function openCart() {
  openDialog('cart-dialog');
  $('#cart-items').innerHTML = '<p style="padding-top:25px">Себет жүктелуде…</p>';
  $('#cart-footer').hidden = true;
  if (!await refreshCartProducts()) {
    $('#cart-items').innerHTML = `<div class="empty-state">${icon('bag')}<h3>Себет жүктелмеді</h3><p>Гүлдердің ағымдағы бағасын тексеру мүмкін болмады. Байланысты тексеріп, қайта көріңіз.</p><button class="button button-primary" id="retry-cart">Қайта көру</button></div>`;
    return;
  }
  renderCart();
}

function renderCart() {
  const items = cartDetails();
  $('#drawer-count').textContent = `(${state.cart.reduce((sum, item) => sum + item.quantity, 0)})`;
  $('#cart-footer').hidden = !items.length;
  if (!items.length) {
    $('#cart-items').innerHTML = `<div class="empty-state">${icon('bag')}<h3>Себетіңіз әзірге бос</h3><p>Әдемі сезім бір гүлден басталады. Каталогтан өз гүл шоғыңызды таңдаңыз.</p><button class="button button-primary" data-browse>Гүлдерді таңдау</button></div>`;
    return;
  }
  $('#cart-items').innerHTML = items.map(({id, quantity, product}) => `<article class="cart-row"><img src="${safeImage(product.image_url)}" alt="${escapeHTML(product.name)}"><div><div class="cart-row-top"><div><h3>${escapeHTML(product.name)}</h3><p>${money(product.price)}</p></div><button class="cart-remove" data-remove="${id}" aria-label="${escapeHTML(product.name)}: себеттен жою">${icon('close')}</button></div><div class="cart-row-bottom"><div class="quantity-control"><button data-quantity="${id}" data-delta="-1" aria-label="${escapeHTML(product.name)}: санын азайту">${icon('minus')}</button><span aria-label="Саны">${quantity}</span><button data-quantity="${id}" data-delta="1" aria-label="${escapeHTML(product.name)}: санын көбейту" ${quantity >= Math.min(product.stock, 20) ? 'disabled' : ''}>${icon('plus')}</button></div><span class="cart-row-price">${money(product.price * quantity)}</span></div></div></article>`).join('');
  $('#cart-footer').innerHTML = `<div class="cart-total"><span>Гүлдердің жалпы сомасы</span><strong>${money(subtotal())}</strong></div><p>Жеткізу құны мен промокод жеңілдігі келесі қадамда есептеледі.</p><button class="button button-primary" id="begin-checkout">Тапсырысты рәсімдеу</button>`;
  addImageFallbacks($('#cart-items'));
}

function changeQuantity(id, delta) {
  const item = state.cart.find(row => row.id === id);
  if (!item) return;
  const product = state.cache.get(id);
  if (delta > 0 && item.quantity >= Math.min(product?.stock || 0, 20)) return toast('Бір гүл шоғынан ең көбі 20 дана немесе қоймадағы санды алуға болады');
  item.quantity += delta;
  if (item.quantity <= 0) state.cart = state.cart.filter(row => row.id !== id);
  persistCart(); renderCart();
}

function renderProductDetail(id) {
  const product = state.cache.get(id);
  if (!product) return;
  const favorite = state.favorites.has(id);
  $('#product-detail').innerHTML = `<div class="product-detail-grid"><img class="product-detail-image" src="${safeImage(product.image_url)}" alt="${escapeHTML(product.name)}"><div class="product-detail-copy"><span class="eyebrow">${escapeHTML(categoryName(product.category_id))}</span><h2>${escapeHTML(product.name)}</h2><div class="detail-price"><span class="product-price">${money(product.price)}</span>${product.old_price > product.price ? `<span class="old-price">${money(product.old_price)}</span>` : ''}</div><p>${escapeHTML(product.description)}</p><div class="detail-info"><div>${icon('leaf')}<span>${product.stock > 0 ? `Қоймада: ${product.stock} гүл шоғы` : 'Уақытша таусылды'}</span></div><div>${icon('gift')}<span>Жеке тілек жазылған ашықхат — тегін</span></div><div>${icon('truck')}<span>Жеткізу күні тапсырыста таңдалады</span></div></div><div class="detail-actions"><button class="button button-primary" data-add="${id}" ${product.stock <= 0 ? 'disabled' : ''}>${icon('bag')}Себетке қосу</button><button class="icon-button" data-favorite="${id}" aria-label="${favorite ? 'Таңдаулыдан алып тастау' : 'Таңдаулыға қосу'}" aria-pressed="${favorite}" style="${favorite ? 'color:var(--wine);background:var(--pink)' : ''}">${icon('heart')}</button></div></div></div>`;
  addImageFallbacks($('#product-detail'));
}

async function openProduct(id) {
  renderProductDetail(id);
  openDialog('product-dialog');
  try {
    state.cache.set(id, await api(`/products/${id}`));
    if ($('#product-dialog').open) renderProductDetail(id);
  } catch (error) { toast(error.message); }
}

function setAuthMode(mode) {
  state.authMode = mode;
  $$('.auth-tabs button').forEach(button => button.classList.toggle('active', button.dataset.authTab === mode));
  $('#name-field').hidden = mode !== 'register';
  $('#password-help').hidden = mode !== 'register';
  $('#auth-form').elements.name.required = mode === 'register';
  $('#auth-form').elements.password.autocomplete = mode === 'register' ? 'new-password' : 'current-password';
  $('#auth-form').elements.password.minLength = mode === 'register' ? 8 : 1;
  $('#auth-submit').textContent = mode === 'register' ? 'Тіркелу' : 'Кіру';
  $('#auth-title').innerHTML = mode === 'register' ? 'Әдемі сәттер <em>осы жерден басталады</em>' : 'Қайта көргенімізге <em>қуаныштымыз</em>';
  $('#auth-error').textContent = '';
}

function openAuth(forCheckout = false) {
  state.checkoutAfterLogin = forCheckout;
  setAuthMode('login');
  openDialog('auth-dialog');
}

function clearSession() {
  state.token = ''; state.user = null;
  try { sessionStorage.removeItem('flowershop-token'); } catch { /* Optional storage. */ }
  updateCounters();
}

async function submitAuth(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const body = {email: form.elements.email.value.trim(), password: form.elements.password.value};
  if (state.authMode === 'register') body.name = form.elements.name.value.trim();
  const button = $('#auth-submit'); button.disabled = true;
  $('#auth-error').textContent = '';
  try {
    const result = await api(`/auth/${state.authMode}`, {method: 'POST', body: JSON.stringify(body)});
    state.token = result.access_token; state.user = result.user;
    try { sessionStorage.setItem('flowershop-token', state.token); } catch { /* Token remains in memory. */ }
    if (!state.user) state.user = await api('/auth/me');
    form.reset(); updateCounters();
    $('#auth-dialog').close();
    toast(`Қош келдіңіз, ${state.user.name}!`);
    if (state.checkoutAfterLogin) { state.checkoutAfterLogin = false; await beginCheckout(); }
    else await openAccount();
  } catch (error) { $('#auth-error').textContent = error.message; }
  finally { button.disabled = false; }
}

function kazakhDate(date = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Almaty', year:'numeric', month:'2-digit', day:'2-digit'}).format(date);
}

async function beginCheckout() {
  if (!state.cart.length) return toast('Алдымен себетке гүл қосыңыз');
  if (!state.user) return openAuth(true);
  if (!await refreshCartProducts(true)) return toast('Баға мен қойма қалдығын тексеру мүмкін болмады. Қайта көріңіз.');
  if (!cartDetails().length) return toast('Себетіңіз бос. Гүл шоғын таңдаңыз.');
  const unavailable = cartDetails().find(item => item.quantity > item.product.stock);
  if (unavailable) {
    await openCart();
    return toast(`«${unavailable.product.name}»: қоймада ${unavailable.product.stock} дана. Себеттегі санын азайтыңыз.`);
  }
  const form = $('#checkout-form');
  form.elements.recipient_name.value ||= state.user.name;
  form.elements.delivery_date.min = kazakhDate();
  form.elements.delivery_date.max = kazakhDate(new Date(Date.now() + 60 * 86400000));
  if (!form.elements.delivery_date.value || form.elements.delivery_date.value < form.elements.delivery_date.min) form.elements.delivery_date.value = form.elements.delivery_date.min;
  $('#checkout-error').textContent = '';
  $('#checkout-items').innerHTML = cartDetails().map(({quantity,product}) => `<div class="checkout-item"><img src="${safeImage(product.image_url)}" alt="${escapeHTML(product.name)}"><div>${escapeHTML(product.name)}<small>${quantity} дана × ${money(product.price)}</small></div><strong>${money(product.price * quantity)}</strong></div>`).join('');
  renderCheckoutTotals();
  addImageFallbacks($('#checkout-items'));
  openDialog('checkout-dialog');
}

function renderCheckoutTotals() {
  const form = $('#checkout-form');
  const code = form.elements.promo_code.value.trim().toUpperCase();
  const amount = subtotal();
  const discount = code === 'GUL10' ? Math.floor(amount * .1) : 0;
  const pickup = form.elements.delivery_method.value === 'pickup';
  const fee = pickup || amount - discount >= 25000 ? 0 : 1500;
  $('#address-field').hidden = pickup;
  form.elements.address.required = !pickup;
  $('#promo-feedback').textContent = code === 'GUL10' ? 'GUL10: 10% жеңілдік есептелді. Соңғы соманы сервер тексереді.' : code ? 'Промокод тапсырыс кезінде тексеріледі.' : 'GUL10 промокодымен 10% жеңілдік алыңыз.';
  $('#checkout-totals').innerHTML = `<div class="total-line"><span>Гүлдер сомасы</span><span>${money(amount)}</span></div>${discount ? `<div class="total-line discount"><span>Промокод жеңілдігі</span><span>−${money(discount)}</span></div>` : ''}<div class="total-line"><span>${pickup ? 'Өзіңіз алып кету' : 'Жеткізу'}</span><span>${fee ? money(fee) : 'Тегін'}</span></div><div class="total-line grand-total"><span>Барлығы</span><span>${money(amount - discount + fee)}</span></div>`;
}

async function submitCheckout(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!state.user) return openAuth(true);
  const body = {
    items: state.cart.map(({id, quantity}) => ({product_id:id, quantity})),
    recipient_name:form.elements.recipient_name.value.trim(), phone:form.elements.phone.value.trim(),
    delivery_method:form.elements.delivery_method.value,
    address:form.elements.delivery_method.value === 'pickup' ? '' : form.elements.address.value.trim(),
    delivery_date:form.elements.delivery_date.value, time_slot:form.elements.time_slot.value,
    card_message:form.elements.card_message.value.trim(), promo_code:form.elements.promo_code.value.trim().toUpperCase(),
    payment_method:'on_delivery',
  };
  $('#checkout-submit').disabled = true;
  $('#checkout-error').textContent = '';
  try {
    const order = await api('/orders', {method:'POST', body:JSON.stringify(body)});
    state.cart = []; persistCart(); form.reset();
    $('#success-description').textContent = `Тапсырыс № ${order.number || order.id} · ${money(order.total)}`;
    openDialog('success-dialog');
    await loadProducts();
  } catch (error) {
    $('#checkout-error').textContent = error.message;
    if (error.status === 401) toast('Сессия аяқталды. Қайта кіріңіз.');
  } finally { $('#checkout-submit').disabled = false; }
}

const statusNames = {new:'Жаңа',confirmed:'Расталды',preparing:'Дайындалуда',delivering:'Жеткізілуде',completed:'Аяқталды',cancelled:'Бас тартылды'};

async function openAccount() {
  if (!state.user) return openAuth();
  $('#account-name').textContent = state.user.name;
  $('#account-email').textContent = state.user.email;
  $('#orders-list').innerHTML = '<p>Тапсырыстар жүктелуде…</p>';
  openDialog('account-dialog');
  try {
    const response = await api('/orders');
    const orders = Array.isArray(response) ? response : response.items || [];
    if (!orders.length) {
      $('#orders-list').innerHTML = `<div class="empty-state">${icon('flower')}<h3>Әдемі сәттер алда</h3><p>Алғашқы тапсырысыңызды жасаңыз. Оның күйі мен толық ақпараты осы жерде сақталады.</p><button class="button button-primary" data-browse>Каталогты ашу</button></div>`;
      return;
    }
    $('#orders-list').innerHTML = orders.map(order => `<article class="order-card"><div class="order-header"><strong>№ ${escapeHTML(order.number || order.id)}</strong><span class="status-badge status-${Object.hasOwn(statusNames, order.status) ? order.status : 'new'}">${escapeHTML(statusNames[order.status] || order.status)}</span></div><p>${escapeHTML(order.recipient_name)} · ${escapeHTML(order.delivery_date || '')} · ${order.delivery_method === 'pickup' ? 'Өзіңіз алып кету' : 'Курьермен жеткізу'}</p>${order.address ? `<p>${escapeHTML(order.address)}</p>` : ''}<div class="order-products">${(order.items || []).map(item => `<img src="${safeImage(item.image_url)}" alt="${escapeHTML(item.product_name || item.name || 'Гүл шоғы')}">`).join('')}</div><ul class="order-items-text">${(order.items || []).map(item => `<li>${escapeHTML(item.product_name || item.name || 'Гүл шоғы')} × ${item.quantity} — ${money((item.unit_price || item.price) * item.quantity)}</li>`).join('')}</ul>${order.card_message ? `<p>Ашықхат: ${escapeHTML(order.card_message)}</p>` : ''}<div class="order-total">${money(order.total)}</div></article>`).join('');
    addImageFallbacks($('#orders-list'));
  } catch (error) {
    $('#orders-list').innerHTML = `<div class="empty-state"><p>${escapeHTML(error.message)}</p><button class="button button-outline" id="retry-orders">Қайта көру</button></div>`;
  }
}

document.addEventListener('click', event => {
  const target = event.target.closest('button, a');
  if (!target) return;
  if (target.hasAttribute('data-close')) { closeDialog(target.closest('dialog')); return; }
  if (target.hasAttribute('data-add')) { addToCart(Number(target.dataset.add)); return; }
  if (target.hasAttribute('data-favorite')) { toggleFavorite(Number(target.dataset.favorite)); return; }
  if (target.hasAttribute('data-detail')) { openProduct(Number(target.dataset.detail)); return; }
  if (target.hasAttribute('data-category')) {
    state.category = target.dataset.category;
    state.favoriteOnly = false; updateCounters(); renderCategories(); loadProducts(); return;
  }
  if (target.hasAttribute('data-quantity')) { changeQuantity(Number(target.dataset.quantity), Number(target.dataset.delta)); return; }
  if (target.hasAttribute('data-remove')) {
    state.cart = state.cart.filter(item => item.id !== Number(target.dataset.remove));
    persistCart(); renderCart(); return;
  }
  if (target.hasAttribute('data-auth-tab')) { setAuthMode(target.dataset.authTab); return; }
  if (target.hasAttribute('data-reset')) { resetFilters(); return; }
  if (target.hasAttribute('data-retry')) { loadProducts(); return; }
  if (target.hasAttribute('data-browse')) {
    $$('dialog[open]').forEach(dialog => dialog.close());
    $('#catalog').scrollIntoView({behavior:'smooth'}); return;
  }
  if (target.id === 'begin-checkout') beginCheckout();
  if (target.id === 'retry-orders') openAccount();
  if (target.id === 'retry-cart') openCart();
});

$$('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
});

$('#cart-button').addEventListener('click', openCart);
$('#account-button').addEventListener('click', openAccount);
$('#footer-account').addEventListener('click', openAccount);
$('#view-orders').addEventListener('click', openAccount);
$('#favorites-button').addEventListener('click', async () => {
  state.favoriteOnly = !state.favoriteOnly;
  state.category = ''; state.search = ''; state.min = ''; state.max = '';
  $('#search').value = ''; $('#min-price').value = ''; $('#max-price').value = '';
  updateCounters(); renderCategories();
  $('#catalog').scrollIntoView({behavior:'smooth'});
  await loadProducts();
});
$('.search-jump').addEventListener('click', () => { $('#catalog').scrollIntoView({behavior:'smooth'}); $('#search').focus({preventScroll:true}); });
$('#search').addEventListener('input', event => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.search = event.target.value.trim(); loadProducts(); }, 280);
});
$('#sort').addEventListener('change', event => { state.sort = event.target.value; loadProducts(); });
$('#reset-filters').addEventListener('click', resetFilters);
$('#apply-price').addEventListener('click', () => {
  const min = $('#min-price').value, max = $('#max-price').value;
  if ((min && Number(min) < 0) || (max && Number(max) < 0) || (min && max && Number(min) > Number(max))) return toast('Баға аралығын дұрыс көрсетіңіз');
  state.min = min; state.max = max;
  $('#price-filter').open = false; loadProducts();
});
$('#clear-price').addEventListener('click', () => {
  state.min = ''; state.max = ''; $('#min-price').value = ''; $('#max-price').value = '';
  $('#price-filter').open = false; loadProducts();
});
$('#auth-form').addEventListener('submit', submitAuth);
$('#checkout-form').addEventListener('submit', submitCheckout);
$('#checkout-form').addEventListener('input', renderCheckoutTotals);
$('#checkout-form').addEventListener('change', renderCheckoutTotals);
$('#logout-button').addEventListener('click', async () => {
  try { await api('/auth/logout', {method:'POST'}); } catch { /* The local session is cleared even if the network is unavailable. */ }
  clearSession(); $('#account-dialog').close(); toast('Аккаунттан шықтыңыз');
});
$('#year').textContent = new Date().getFullYear();

async function initialize() {
  updateCounters(); skeletons();
  const tasks = [
    api('/categories').then(categories => { state.categories = Array.isArray(categories) ? categories : categories.items || []; renderCategories(); if (!state.loading) renderProducts(); }).catch(() => {}),
    loadProducts(),
  ];
  if (state.token) tasks.push(api('/auth/me').then(user => {state.user = user; updateCounters();}).catch(error => {if (error.status === 401) clearSession();}));
  await Promise.allSettled(tasks);
  await refreshCartProducts();
}

initialize();

