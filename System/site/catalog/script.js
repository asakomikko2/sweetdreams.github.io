let products = [];
let filteredProducts = [];
let currentPage = 1;
const ITEMS_PER_PAGE = 12;
const SEARCH_MIN_CHARS = 2;
const SEARCH_RESULTS_LIMIT = 10;

let activeTypes = [];
let activeSize = [];
let activeColor = [];

const productsGrid = document.getElementById('productsGrid');
const skeletonGrid = document.getElementById('skeletonGrid');
const sortSelect = document.getElementById('sortSelect');
const searchInput = document.getElementById('searchInput');
const clearSearch = document.getElementById('clearSearch');
const searchDropdown = document.getElementById('searchDropdown');
const filterToggleBtn = document.getElementById('filterToggleBtn');
const filterBody = document.getElementById('filterBody');
const resetFiltersBtn = document.getElementById('resetFilters');
const filterCount = document.getElementById('filterCount');
const sizeOptionsDiv = document.getElementById('sizeOptions');
const colorOptionsDiv = document.getElementById('colorOptions');
const typeOptionsDiv = document.getElementById('typeOptions');
const activeFiltersDiv = document.getElementById('activeFilters');
const paginationDiv = document.getElementById('pagination');
const logo = document.getElementById('logo');

const cartFloatBtn = document.getElementById('cartFloatBtn');
const cartFloatCount = document.getElementById('cartFloatCount');
const heroProductsCount = document.getElementById('heroProductsCount');
const heroSizesCount = document.getElementById('heroSizesCount');

const PLACEHOLDER = '/images/placeholder.png';
const THEME_STORAGE_KEY = 'spd-theme';
let revealObserver;
let searchDebounceTimer;

const filterStateMap = {
    type: () => activeTypes,
    size: () => activeSize,
    color: () => activeColor,
};

function setupRevealObserver() {
    if (revealObserver) return revealObserver;
    revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                revealObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });
    return revealObserver;
}

function initRevealAnimations() {
    const observer = setupRevealObserver();
    document.querySelectorAll('.hero-catalog, .filter-section, .product-card, .footer').forEach((el, index) => {
        if (!el.classList.contains('reveal')) {
            el.classList.add('reveal');
            el.style.transitionDelay = `${Math.min(index * 40, 180)}ms`;
        }
        observer.observe(el);
    });
}

function debounce(fn, delay = 120) {
    return (...args) => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => fn(...args), delay);
    };
}

function buildAssistantSuggestion(rawReply) {
    const match = rawReply.match(/\[\[PRODUCT:([^\]]+)\]\]/);
    if (!match) return { reply: rawReply, product: null };
    const sku = match[1].trim();
    const product = products.find((item) => item.sku === sku) || null;
    return {
        reply: rawReply.replace(match[0], '').trim(),
        product,
    };
}

function buildProductUrl(product) {
    const identifier = product?.public_id || product?.sku || product?.slug || '';
    return `/catalog/${encodeURIComponent(identifier)}`;
}

function initAIFallback() {
    const assistantFloatBtn = document.getElementById('assistantFloatBtn');
    const assistantModal = document.getElementById('assistantModal');
    const closeAssistant = document.getElementById('closeAssistant');
    const assistantInput = document.getElementById('assistantInput');
    const assistantSend = document.getElementById('assistantSend');
    const assistantMessages = document.getElementById('assistantMessages');

    if (!assistantFloatBtn || !assistantModal || assistantFloatBtn.dataset.aiBound === 'true') return;

    assistantFloatBtn.dataset.aiBound = 'true';

    const toggleAssistant = (e) => {
        e.preventDefault();
        assistantModal.classList.toggle('show');
    };
    const closeAssistantModal = (e) => {
        if (e) e.preventDefault();
        assistantModal.classList.remove('show');
    };

    assistantFloatBtn.addEventListener('click', toggleAssistant);
    assistantFloatBtn.addEventListener('touchstart', toggleAssistant, { passive: false });
    if (closeAssistant) {
        closeAssistant.addEventListener('click', closeAssistantModal);
        closeAssistant.addEventListener('touchstart', closeAssistantModal, { passive: false });
    }

    async function sendAssistantMessage() {
        const msg = assistantInput?.value.trim();
        if (!msg || !assistantMessages) return;

        assistantMessages.innerHTML += `<div class="assistant-message user">${escapeHtml(msg)}</div>`;
        assistantInput.value = '';

        const loading = document.createElement('div');
        loading.className = 'assistant-message bot';
        loading.textContent = '...';
        assistantMessages.appendChild(loading);
        assistantMessages.scrollTop = assistantMessages.scrollHeight;

        try {
            const data = typeof window.sendSweetPillowAIMessage === 'function'
                ? await window.sendSweetPillowAIMessage(msg)
                : await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg })
                }).then((res) => res.json());
            loading.remove();
            renderAssistantReply(data.reply || 'Извините, произошла ошибка.');
        } catch (error) {
            loading.remove();
            assistantMessages.innerHTML += `<div class="assistant-message bot">Ошибка соединения</div>`;
        }

        assistantMessages.scrollTop = assistantMessages.scrollHeight;
    }

    if (assistantSend) assistantSend.addEventListener('click', sendAssistantMessage);
    if (assistantInput) {
        assistantInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendAssistantMessage();
        });
    }
}

// ========== УТИЛИТЫ ==========
function showToast(m) {
    const t = document.getElementById('toast');
    if(t){ t.textContent = m; t.style.display = 'block'; setTimeout(() => t.style.display = 'none', 2000); }
}
function formatPrice(p) { return p ? Number(p).toLocaleString() + ' сум' : 'Цена не указана'; }
function escapeHtml(t) { if(!t) return ''; return t.replace(/[&<>]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[m])); }
function tr(text) { return window.SPD_I18N ? window.SPD_I18N.t(text) : text; }
function getProductDescription(product) {
    return window.SPD_I18N ? window.SPD_I18N.productDescription(product) : (product?.description || '');
}
function fetchJson(url, options) {
    return fetch(url, options).then((response) => {
        if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        return response.json();
    });
}

function renderAssistantReply(rawReply) {
    const { reply, product } = buildAssistantSuggestion(rawReply);
    const botMessage = document.createElement('div');
    botMessage.className = 'assistant-message bot';
    botMessage.innerHTML = escapeHtml(reply || 'Не получилось подготовить ответ.');

    if (product) {
        const suggestion = document.createElement('div');
        suggestion.className = 'assistant-suggestion';
        suggestion.innerHTML = `
            <div class="assistant-suggestion-title">Показать подходящий товар?</div>
            <div class="assistant-suggestion-name">${escapeHtml(cleanProductName(product.name))}</div>
            <div class="assistant-suggestion-actions">
                <button class="assistant-choice-btn confirm" data-action="open-product">Да</button>
                <button class="assistant-choice-btn" data-action="dismiss-product">Нет</button>
            </div>
        `;
        const confirmBtn = suggestion.querySelector('[data-action="open-product"]');
        const dismissBtn = suggestion.querySelector('[data-action="dismiss-product"]');
        confirmBtn.addEventListener('click', () => {
            window.location.href = buildProductUrl(product);
        });
        dismissBtn.addEventListener('click', () => {
            suggestion.remove();
        });
        botMessage.appendChild(suggestion);
    }

    const assistantMessages = document.getElementById('assistantMessages');
    assistantMessages?.appendChild(botMessage);
    if (assistantMessages) assistantMessages.scrollTop = assistantMessages.scrollHeight;
}
window.renderAssistantReply = renderAssistantReply;
function getDescriptionPreview(text) {
    if (!text) return 'Подробности о модели доступны на странице товара.';
    const normalized = text
        .replace(/[*_#`>\[\]]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    return normalized.slice(0, 118) + (normalized.length > 118 ? '...' : '');
}

function cleanProductName(name) {
    if (!name) return '';
    let cleaned = name.replace(/\s*[-–—]\s*комфортный сон/gi, '');
    cleaned = cleaned.replace(/\s+1\s*шт\.?/gi, '');
    cleaned = cleaned.replace(/,?\s*1\s*шт\.?/gi, '');
    cleaned = cleaned.replace(/\s+комфортный сон/gi, '');
    cleaned = cleaned.replace(/для наволочки,\s*/gi, '');
    return cleaned.trim();
}

function getProductTypeFromName(name) {
    if (!name) return 'Подушки';
    const n = name.toLowerCase();
    if (n.includes('для наволочки')) return 'Подушки';
    if (n.includes('наволочк')) return 'Наволочки';
    if (n.includes('наперник')) return 'Наперники';
    return 'Подушки';
}

function extractSizeFromName(name) {
    if (!name) return null;
    const match = name.match(/(\d{2,3})\s*[x×]\s*(\d{2,3})/);
    return match ? match[1] + 'x' + match[2] : null;
}

function extractColorFromName(name) {
    if (!name) return null;
    const lower = name.toLowerCase();
    const colorMap = {
        'белый': 'Белый', 'белая': 'Белый',
        'голубой': 'Голубой', 'голубая': 'Голубой',
        'серый': 'Серый', 'серая': 'Серый',
        'темно-серый': 'Серый', 'темно-серая': 'Серый',
        'розовый': 'Розовый', 'розовая': 'Розовый',
        'фиолетовый': 'Фиолетовый', 'фиолетовая': 'Фиолетовый',
        'чёрный': 'Чёрный', 'черный': 'Чёрный',
        'чёрная': 'Чёрный', 'черная': 'Чёрный',
        'бордовый': 'Бордовый', 'бордовая': 'Бордовый',
    };
    for (const [key, value] of Object.entries(colorMap)) {
        if (lower.includes(key)) {
            if (key.includes('фиолетов') && lower.includes('окантовк')) continue;
            return value;
        }
    }
    return null;
}

function getProductTags(product) {
    const tags = [getProductTypeFromName(product.name)];
    const size = extractSizeFromName(product.name);
    const color = extractColorFromName(product.name);
    if (size) tags.push(size);
    if (color) tags.push(color);
    return tags.slice(0, 3);
}

function getFilterArray(filterType) {
    return filterStateMap[filterType]?.();
}

function getSearchResults(query) {
    return products
        .filter((product) => (cleanProductName(product.name) || '').toLowerCase().includes(query))
        .slice(0, SEARCH_RESULTS_LIMIT);
}

function renderSearchDropdown(results) {
    if (!searchDropdown) return;
    searchDropdown.innerHTML = results.map((product) => `
        <div class="search-item" data-sku="${product.sku}">
            <span class="search-item-name">${escapeHtml(cleanProductName(product.name))}</span>
            <span class="search-item-price">${formatPrice(product.price)}</span>
        </div>
    `).join('');
    searchDropdown.classList.toggle('show', results.length > 0);
    document.querySelectorAll('.search-item').forEach((item) => {
        item.onclick = () => {
            const product = products.find((entry) => entry.sku === item.dataset.sku);
            window.location.href = buildProductUrl(product || { sku: item.dataset.sku });
        };
    });
}

function resetSearch() {
    if (!searchInput || !clearSearch || !searchDropdown) return;
    searchInput.value = '';
    clearSearch.classList.remove('visible');
    searchDropdown.classList.remove('show');
}

function updateHeroStats() {
    if (heroProductsCount) heroProductsCount.textContent = '100+';
    if (heroSizesCount) {
        const sizes = new Set(products.map(p => extractSizeFromName(p.name)).filter(Boolean));
        heroSizesCount.textContent = sizes.size;
    }
}

// ========== КОРЗИНА ==========
function getCart() { return JSON.parse(localStorage.getItem('cart') || '[]'); }
function saveCart(c) { localStorage.setItem('cart', JSON.stringify(c)); updateCartCount(); }
function updateCartCount() {
    const cart = getCart();
    const total = cart.reduce((s,i) => s + i.quantity, 0);
    if(cartFloatCount) cartFloatCount.textContent = total;
}
function addToCart(p, quantity = 1) {
    let cart = getCart();
    const ex = cart.find(i => i.sku === p.sku);
    if (ex) ex.quantity += quantity;
    else cart.push({ sku: p.sku, name: cleanProductName(p.name), price: p.price, size: extractSizeFromName(p.name) || '', image: p.images?.[0] || PLACEHOLDER, quantity });
    cart.sort((a,b) => (a.sku === p.sku ? -1 : 1));
    saveCart(cart);
    showToast(`✅ Добавлено в корзину (${quantity} шт.)`);
    renderProducts();
}
function removeFromCart(sku) {
    let cart = getCart();
    cart = cart.filter(i => i.sku !== sku);
    saveCart(cart);
    showToast('🗑️ Товар убран из корзины');
    renderProducts();
}
function isInCart(sku) { return getCart().some(i => i.sku === sku); }

// ========== TELEGRAM ==========
function sendToTelegram(text) { window.open(`https://t.me/pillows_uz?text=${encodeURIComponent(text)}`, '_blank'); }
function buyNow(p, quantity = 1) {
    const total = (p.price || 0) * quantity;
    let text = `Здравствуйте! Хочу заказать ${quantity > 1 ? quantity + ' ' : ''}${cleanProductName(p.name)}`;
    const size = extractSizeFromName(p.name);
    if (size) text += `, ${size}`;
    text += ` (${formatPrice(total)})`;
    sendToTelegram(text);
    showToast('✅ Переход в Telegram');
}

// ========== ФИЛЬТРАЦИЯ ==========
function initFilters() {
    const types = new Set(), sizesSet = new Set(), colorsSet = new Set();
    products.forEach(p => {
        types.add(getProductTypeFromName(p.name));
        const size = extractSizeFromName(p.name); if (size) sizesSet.add(size);
        const color = extractColorFromName(p.name); if (color) colorsSet.add(color);
    });
    if (typeOptionsDiv) typeOptionsDiv.innerHTML = Array.from(types).sort().map(v => `<button class="filter-option" data-type="type" data-value="${v}">${v}</button>`).join('');
    if (sizeOptionsDiv) sizeOptionsDiv.innerHTML = Array.from(sizesSet).sort((a,b) => parseInt(a.split('x')[0]) - parseInt(b.split('x')[0])).map(v => `<button class="filter-option" data-type="size" data-value="${v}">${v}</button>`).join('');
    if (colorOptionsDiv) colorOptionsDiv.innerHTML = Array.from(colorsSet).sort().map(v => `<button class="filter-option" data-type="color" data-value="${v}">${v}</button>`).join('');
    document.querySelectorAll('.filter-option').forEach(btn => btn.onclick = () => toggleFilter(btn, btn.dataset.type));
    updateFilterCount();
}

function toggleFilter(btn, filterType) {
    btn.classList.toggle('active');
    const val = btn.dataset.value;
    const arr = getFilterArray(filterType);
    if (!arr) return;
    if (btn.classList.contains('active')) { if (!arr.includes(val)) arr.push(val); }
    else { const idx = arr.indexOf(val); if (idx > -1) arr.splice(idx, 1); }
    updateFilterCount();
    filterProducts();
}

function updateFilterCount() { if (filterCount) filterCount.textContent = activeTypes.length + activeSize.length + activeColor.length; }

function filterProducts() {
    let filtered = products.filter(p => {
        if (activeTypes.length && !activeTypes.includes(getProductTypeFromName(p.name))) return false;
        if (activeSize.length) { const size = extractSizeFromName(p.name); if (!size || !activeSize.includes(size)) return false; }
        if (activeColor.length) { const color = extractColorFromName(p.name); if (!color || !activeColor.includes(color)) return false; }
        return true;
    });
    const sort = sortSelect?.value || 'default';
    if (sort === 'price-asc') filtered.sort((a,b) => (a.price||0)-(b.price||0));
    else if (sort === 'price-desc') filtered.sort((a,b) => (b.price||0)-(a.price||0));
    else if (sort === 'name-asc') filtered.sort((a,b) => (cleanProductName(a.name)||'').localeCompare(cleanProductName(b.name)||''));
    filteredProducts = filtered;
    currentPage = 1;
    renderProducts();
    updateActiveFiltersUI();
}

function updateActiveFiltersUI() {
    if (!activeFiltersDiv) return;
    activeFiltersDiv.innerHTML = '';
    activeTypes.forEach(v => addChip(v, 'type'));
    activeSize.forEach(v => addChip(v, 'size'));
    activeColor.forEach(v => addChip(v, 'color'));
    document.querySelectorAll('.filter-chip button').forEach(btn => {
        btn.onclick = (e) => {
            const type = btn.dataset.type, val = btn.dataset.value;
            const arr = getFilterArray(type);
            if (!arr) return;
            const idx = arr.indexOf(val);
            if (idx > -1) arr.splice(idx, 1);
            document.querySelectorAll(`.filter-option[data-type="${type}"][data-value="${val}"]`).forEach(el=>el.classList.remove('active'));
            updateFilterCount(); filterProducts();
        };
    });
}
function addChip(val, type) {
    const chip = document.createElement('div'); chip.className = 'filter-chip';
    chip.innerHTML = `${val} <button data-type="${type}" data-value="${val}">×</button>`;
    activeFiltersDiv.appendChild(chip);
}

// ========== ОТРИСОВКА ==========
function renderProducts() {
    if (!productsGrid) return;
    const totalPages = Math.ceil(filteredProducts.length / ITEMS_PER_PAGE);
    const start = (currentPage-1)*ITEMS_PER_PAGE;
    const visible = filteredProducts.slice(start, start+ITEMS_PER_PAGE);
    if (!visible.length) { productsGrid.innerHTML = `<div class="not-found-card"><span class="not-found-code">0</span><h1>${tr('Товары не найдены')}</h1><p>${tr('Товары не найдены. Попробуйте сбросить фильтры или изменить запрос.')}</p></div>`; paginationDiv.innerHTML=''; return; }
    productsGrid.className = 'products-grid';
    productsGrid.innerHTML = '';
    visible.forEach((product) => productsGrid.appendChild(createProductCard(product)));
    renderPagination(totalPages);
    initRevealAnimations();
}

function createProductCard(product) {
    const images = product.images?.length ? product.images : [PLACEHOLDER];
    const inCart = isInCart(product.sku);
    const tags = getProductTags(product);
    const card = document.createElement('div');
    card.className = 'product-card';
    card.dataset.sku = product.sku;

    const imageDiv = document.createElement('div');
    imageDiv.className = 'product-image';
    images.forEach((img, index) => {
        const slide = document.createElement('img');
        slide.src = img;
        slide.className = `image-slide ${index === 0 ? 'active' : ''}`;
        slide.dataset.index = index;
        slide.onerror = () => { slide.src = PLACEHOLDER; };
        imageDiv.appendChild(slide);
    });

    if (images.length > 1) {
        attachGalleryNavigation(imageDiv, images.length);
    }

    const infoDiv = document.createElement('div');
    infoDiv.className = 'product-info';
    infoDiv.innerHTML = `
        <div class="product-tags">${tags.map((tag) => `<span class="product-tag">${escapeHtml(tag)}</span>`).join('')}</div>
        <div class="product-title">${escapeHtml(cleanProductName(product.name))}</div>
        <div class="product-description-preview">${escapeHtml(getDescriptionPreview(getProductDescription(product)))}</div>
        <div class="product-price-row">
            <div class="product-price">${formatPrice(product.price)}</div>
            <div class="product-price-note">${tr('Быстрый заказ в Telegram')}</div>
        </div>
        <div class="product-actions">
            <button class="buy-btn-small" data-sku="${product.sku}">${tr('Купить')}</button>
            <button class="cart-btn-small" data-sku="${product.sku}">${inCart ? tr('Убрать') : tr('В корзину')}</button>
        </div>
    `;

    card.appendChild(imageDiv);
    card.appendChild(infoDiv);

    card.addEventListener('click', (event) => {
        if (event.target.closest('.buy-btn-small, .cart-btn-small, .image-nav-btn, .image-dot')) return;
        window.location.href = buildProductUrl(product);
    });

    const buyBtn = infoDiv.querySelector('.buy-btn-small');
    const cartBtn = infoDiv.querySelector('.cart-btn-small');
    buyBtn.addEventListener('click', (event) => { event.stopPropagation(); buyNow(product, 1); });
    cartBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        if (isInCart(product.sku)) removeFromCart(product.sku);
        else addToCart(product, 1);
    });

    return card;
}

function attachGalleryNavigation(imageDiv, imageCount) {
    const nav = document.createElement('div');
    nav.className = 'image-nav';
    nav.innerHTML = `
        <button class="image-nav-btn prev"><i class="fas fa-chevron-left"></i></button>
        <button class="image-nav-btn next"><i class="fas fa-chevron-right"></i></button>
        <div class="image-dots">${Array.from({ length: imageCount }, (_, index) => `<span class="image-dot ${index === 0 ? 'active' : ''}" data-index="${index}"></span>`).join('')}</div>
    `;
    imageDiv.appendChild(nav);

    const slides = imageDiv.querySelectorAll('.image-slide');
    const dots = imageDiv.querySelectorAll('.image-dot');
    const prevBtn = nav.querySelector('.prev');
    const nextBtn = nav.querySelector('.next');
    let currentIndex = 0;

    const showSlide = (index) => {
        slides.forEach((slide, slideIndex) => slide.classList.toggle('active', slideIndex === index));
        dots.forEach((dot, dotIndex) => dot.classList.toggle('active', dotIndex === index));
        currentIndex = index;
    };

    prevBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        showSlide((currentIndex - 1 + slides.length) % slides.length);
    });
    nextBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        showSlide((currentIndex + 1) % slides.length);
    });
    dots.forEach((dot, index) => dot.addEventListener('click', (event) => {
        event.stopPropagation();
        showSlide(index);
    }));
}

function renderPagination(total) {
    if (!paginationDiv || total<=1) { paginationDiv.innerHTML=''; return; }
    let html = '';
    if (currentPage>1) html += `<button class="page-btn" data-page="${currentPage-1}"><i class="fas fa-chevron-left"></i></button>`;
    for (let i=1;i<=total;i++) {
        if (i===1||i===total||(i>=currentPage-1&&i<=currentPage+1)) html += `<button class="page-btn ${i===currentPage?'active':''}" data-page="${i}">${i}</button>`;
        else if (i===currentPage-2||i===currentPage+2) html += `<span>...</span>`;
    }
    if (currentPage<total) html += `<button class="page-btn" data-page="${currentPage+1}"><i class="fas fa-chevron-right"></i></button>`;
    paginationDiv.innerHTML = html;
    document.querySelectorAll('.page-btn').forEach(b => b.onclick = () => { currentPage = parseInt(b.dataset.page); renderProducts(); window.scrollTo({top:0,behavior:'smooth'}); });
}

// ========== ЗАГРУЗКА ==========
fetchJson('/api/products').then(data => {
    products = data;
    updateHeroStats();
    initFilters();
    filterProducts();
    if (skeletonGrid) skeletonGrid.style.display = 'none';
    updateCartCount();
    // Инициализируем AI после загрузки
    if (typeof initAI === 'function') initAI();
    initAIFallback();
    initRevealAnimations();
}).catch(e => { productsGrid.innerHTML = '<div style="padding:50px">❌ Ошибка загрузки</div>'; });

// ========== СОБЫТИЯ ==========
if (sortSelect) sortSelect.onchange = filterProducts;
if (resetFiltersBtn) resetFiltersBtn.onclick = () => {
    activeTypes=[]; activeSize=[]; activeColor=[];
    document.querySelectorAll('.filter-option').forEach(b=>b.classList.remove('active'));
    updateFilterCount(); filterProducts();
    resetSearch();
    showToast('🔄 Фильтры сброшены');
};
let filterCollapsed = false;
if (filterToggleBtn && filterBody) {
    filterToggleBtn.onclick = () => {
        filterCollapsed = !filterCollapsed;
        filterBody.classList.toggle('collapsed', filterCollapsed);
        const icon = filterToggleBtn.querySelector('i');
        if (icon) { icon.classList.toggle('fa-chevron-up', !filterCollapsed); icon.classList.toggle('fa-chevron-down', filterCollapsed); }
    };
}
window.addEventListener('spd:language-changed', () => {
    renderProducts();
    updateActiveFilters();
});
if (searchInput) {
    searchInput.oninput = debounce(() => {
        const query = searchInput.value.toLowerCase().trim();
        clearSearch.classList.toggle('visible', query.length > 0);
        if (query.length < SEARCH_MIN_CHARS) {
            if (searchDropdown) searchDropdown.classList.remove('show');
            return;
        }
        renderSearchDropdown(getSearchResults(query));
    });
    clearSearch.onclick = resetSearch;
}
document.addEventListener('click', (e) => {
    if (searchInput && !searchInput.contains(e.target) && !searchDropdown.contains(e.target)) searchDropdown.classList.remove('show');
});
if (logo) logo.onclick = () => window.location.href = '/catalog';
if (cartFloatBtn) {
    const goToCart = (e) => { e.preventDefault(); window.location.href = '/catalog/cart'; };
    cartFloatBtn.addEventListener('click', goToCart);
}

// ========== ТЁМНАЯ ТЕМА ==========
const themeToggle = document.getElementById('themeToggle');
if (themeToggle) {
    const themeIcon = themeToggle.querySelector('i');
    function applyTheme(mode) {
        document.documentElement.dataset.theme = mode;
        if (mode === 'dark') {
            document.body.classList.add('dark');
            themeIcon.className = 'fas fa-moon';
        } else {
            document.body.classList.remove('dark');
            themeIcon.className = 'fas fa-sun';
        }
        localStorage.setItem(THEME_STORAGE_KEY, mode);
        localStorage.setItem('theme', mode);
    }
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) || localStorage.getItem('theme');
    applyTheme(savedTheme || (prefersDark ? 'dark' : 'light'));
    themeToggle.addEventListener('click', () => {
        const isDark = document.body.classList.contains('dark');
        applyTheme(isDark ? 'light' : 'dark');
    });
}
