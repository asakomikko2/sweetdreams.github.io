let aiCatalogDataPromise;

function loadCatalogData() {
    if (!aiCatalogDataPromise) {
        aiCatalogDataPromise = fetch('/api/products')
            .then((res) => {
                if (!res.ok) throw new Error('catalog data unavailable');
                return res.json();
            })
            .catch(() => []);
    }
    return aiCatalogDataPromise;
}

function summarizeCatalog(products) {
    const types = new Set();
    const sizes = new Set();
    const materials = new Set();
    const names = [];
    let minPrice = Infinity;
    let maxPrice = 0;

    products.forEach((product) => {
        const name = (product.name || '').trim();
        const description = (product.description || '').toLowerCase();
        const price = Number(product.price || 0);

        if (name) names.push(name);
        if (price > 0) {
            minPrice = Math.min(minPrice, price);
            maxPrice = Math.max(maxPrice, price);
        }

        const lowerName = name.toLowerCase();
        if (lowerName.includes('наволочк')) types.add('наволочки');
        else if (lowerName.includes('наперник')) types.add('наперники');
        else types.add('подушки');

        const sizeMatch = lowerName.match(/(\d{2,3})\s*[x×]\s*(\d{2,3})/);
        if (sizeMatch) sizes.add(`${sizeMatch[1]}x${sizeMatch[2]}`);

        if (description.includes('холлофайбер')) materials.add('холлофайбер');
        if (description.includes('пух') || description.includes('перо')) materials.add('пух-перо');
        if (description.includes('сатин')) materials.add('супер-сатин');
        if (description.includes('хлоп') || description.includes('х/б')) materials.add('хлопковая ткань');
    });

    return {
        total: products.length,
        types: Array.from(types).sort(),
        sizes: Array.from(sizes).sort((a, b) => parseInt(a, 10) - parseInt(b, 10)).slice(0, 18),
        materials: Array.from(materials).sort(),
        minPrice: Number.isFinite(minPrice) ? Math.round(minPrice) : null,
        maxPrice: maxPrice || null,
        examples: names.slice(0, 12),
    };
}

function formatPriceRange(summary) {
    if (!summary.minPrice || !summary.maxPrice) return 'цены уточняются';
    return `${summary.minPrice.toLocaleString('ru-RU')} - ${summary.maxPrice.toLocaleString('ru-RU')} сум`;
}

function normalizeText(value) {
    return (value || '').toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
}

function scoreProductMatch(product, query) {
    const haystack = normalizeText(`${product.name} ${product.description || ''} ${product.size || ''}`);
    const tokens = normalizeText(query).split(' ').filter(Boolean);
    if (!tokens.length) return 0;
    return tokens.reduce((score, token) => score + (haystack.includes(token) ? 2 : 0), 0);
}

function getRelevantProducts(products, userMessage) {
    return [...products]
        .map((product) => ({ product, score: scoreProductMatch(product, userMessage) }))
        .sort((a, b) => b.score - a.score)
        .filter((item) => item.score > 0)
        .slice(0, 8)
        .map((item) => item.product);
}

function buildRelevantProductsContext(products) {
    if (!products.length) return 'Точных совпадений по запросу в каталоге не найдено, отвечай общим советом без выдуманных товаров.';
    return [
        'Ниже список самых близких товаров из каталога. Используй только их SKU, если рекомендуешь конкретный товар:',
        ...products.map((product) => `SKU: ${product.sku} | Название: ${product.name} | Цена: ${product.price || 'нет цены'} | Описание: ${(product.description || '').slice(0, 220)}`),
    ].join('\n');
}

function buildAssistantPrompt(summary) {
    return [
        'Ты виртуальный консультант магазина Sweet Pillow Dreams.',
        'Представляйся только как консультант Sweet Pillow Dreams или помощник Sweet Pillow Dreams.',
        'Никогда не называй модель, провайдера, API, Groq, Llama Scout, нейросеть или искусственный интеллект, если пользователь сам прямо не спрашивает про устройство ассистента.',
        'Отвечай только на русском языке.',
        'Тон: спокойный, вежливый, человеческий, полезный.',
        'Задача: помогать с выбором подушек, наволочек, наперников, размеров, наполнителей, уходом, ощущением по жесткости, комфортом сна, а также с базовой навигацией по ассортименту магазина.',
        'Если вопрос не по теме сна, подушек, текстиля, ухода, реставрации или ассортимента магазина, вежливо скажи, что помогаешь только по товарам Sweet Pillow Dreams и комфорту сна.',
        'Если не хватает данных для точного совета, задай 1 короткий уточняющий вопрос.',
        'Не придумывай характеристики, которых нет в данных. Если чего-то не знаешь, говори честно и предлагай ориентироваться по доступным вариантам.',
        'Не упоминай скидки, акции, промокоды и внутренние технические детали.',
        `В каталоге сейчас около ${summary.total} товаров.`,
        `Основные типы товаров: ${summary.types.join(', ') || 'подушки и текстиль'}.`,
        `Популярные размеры: ${summary.sizes.join(', ') || 'размеры уточняются'}.`,
        `Материалы и наполнители, встречающиеся в данных: ${summary.materials.join(', ') || 'хлопковая ткань, холлофайбер, пух-перо'}.`,
        `Диапазон цен по данным каталога: ${formatPriceRange(summary)}.`,
        `Примеры товаров: ${summary.examples.join('; ')}.`,
        'Когда рекомендуешь вариант, опирайся на положение сна, желаемую высоту, мягкость, размер и материал.',
        'Если пользователь спрашивает, что выбрать, предлагай 2-3 подходящих направления, а не длинный список.',
        'Пиши кратко, но содержательно: обычно 3-6 предложений.',
        'Если есть один явно подходящий товар из переданного релевантного списка, добавь в самом конце отдельной строкой маркер вида [[PRODUCT:SKU]].',
        'Если уверенной конкретной рекомендации нет, не добавляй маркер.',
        'Никогда не показывай пользователю служебные пояснения про маркер.',
    ].join('\n');
}

async function requestAssistantReply(userMessage) {
    const products = await loadCatalogData();
    const summary = summarizeCatalog(products);
    const relevantProducts = getRelevantProducts(products, userMessage);
    const messages = [
        { role: 'system', content: buildAssistantPrompt(summary) },
        { role: 'system', content: buildRelevantProductsContext(relevantProducts) },
        { role: 'user', content: userMessage },
    ];

    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages }),
    });

    if (!response.ok) {
        throw new Error(`chat request failed: ${response.status}`);
    }

    return response.json();
}

window.sendSweetPillowAIMessage = requestAssistantReply;

function initAI() {
    const assistantFloatBtn = document.getElementById('assistantFloatBtn');
    const assistantModal = document.getElementById('assistantModal');
    const closeAssistant = document.getElementById('closeAssistant');
    const assistantInput = document.getElementById('assistantInput');
    const assistantSend = document.getElementById('assistantSend');
    const assistantMessages = document.getElementById('assistantMessages');

    if (!assistantFloatBtn || !assistantModal) {
        return;
    }
    if (assistantFloatBtn.dataset.aiBound === 'true') {
        return;
    }
    assistantFloatBtn.dataset.aiBound = 'true';

    assistantFloatBtn.addEventListener('click', (e) => {
        e.preventDefault();
        assistantModal.classList.toggle('show');
    });

    if (closeAssistant) {
        closeAssistant.addEventListener('click', () => assistantModal.classList.remove('show'));
    }

    async function send() {
        const msg = assistantInput.value.trim();
        if (!msg) return;

        assistantMessages.innerHTML += `<div class="assistant-message user">${escapeHtml(msg)}</div>`;
        assistantInput.value = '';

        const loading = document.createElement('div');
        loading.className = 'assistant-message bot';
        loading.textContent = 'Подбираю ответ...';
        assistantMessages.appendChild(loading);
        assistantMessages.scrollTop = assistantMessages.scrollHeight;

        try {
            const data = await requestAssistantReply(msg);
            loading.remove();
            if (typeof window.renderAssistantReply === 'function') window.renderAssistantReply(data.reply || 'Не получилось подготовить ответ.');
            else assistantMessages.innerHTML += `<div class="assistant-message bot">${escapeHtml(data.reply || 'Не получилось подготовить ответ.')}</div>`;
            assistantMessages.scrollTop = assistantMessages.scrollHeight;
        } catch (err) {
            loading.remove();
            assistantMessages.innerHTML += `<div class="assistant-message bot">Сейчас ответ не загрузился. Напишите нам в Telegram @pillows_uz, и мы поможем с выбором.</div>`;
        }
    }

    if (assistantSend) assistantSend.addEventListener('click', send);
    if (assistantInput) assistantInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') send(); });

    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let initialLeft = 0;
    let initialTop = 0;
    const header = assistantModal.querySelector('.assistant-header');
    if (header) {
        header.addEventListener('mousedown', (e) => {
            e.preventDefault();
            isDragging = true;
            const rect = assistantModal.getBoundingClientRect();
            startX = e.clientX;
            startY = e.clientY;
            initialLeft = rect.left;
            initialTop = rect.top;
            assistantModal.style.transition = 'none';
        });
        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            e.preventDefault();
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            let left = initialLeft + dx;
            let top = initialTop + dy;
            left = Math.min(Math.max(left, 0), window.innerWidth - assistantModal.offsetWidth);
            top = Math.min(Math.max(top, 0), window.innerHeight - assistantModal.offsetHeight);
            assistantModal.style.left = `${left}px`;
            assistantModal.style.top = `${top}px`;
            assistantModal.style.right = 'auto';
            assistantModal.style.bottom = 'auto';
        });
        window.addEventListener('mouseup', () => {
            isDragging = false;
            assistantModal.style.transition = '';
        });
    }
}
