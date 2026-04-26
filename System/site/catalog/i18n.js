(function () {
    const STORAGE_KEY = 'spd-lang';
    const SUPPORTED = ['ru', 'uz'];
    const originalTextNodes = new WeakMap();
    const exact = {
        uz: {
            'Каталог': 'Katalog',
            'Корзина': 'Savat',
            'Фильтры': 'Filtrlar',
            'Сбросить': 'Tozalash',
            'Сортировка': 'Saralash',
            'Тип товара': 'Mahsulot turi',
            'Размер': 'O‘lcham',
            'Цвет': 'Rang',
            'По умолчанию': 'Standart',
            'Цена: по возрастанию': 'Narx: arzonidan',
            'Цена: по убыванию': 'Narx: qimmatidan',
            'Название: А-Я': 'Nomi: A-Y',
            'Коллекция для спокойного и здорового сна': 'Sokin va sog‘lom uyqu uchun kolleksiya',
            'Каталог подушек и текстиля, который ощущается как отдых': 'Dam olishdek yoqimli yostiq va tekstil katalogi',
            'Подберите размер, наполнитель и формат без лишнего шума. Мы собрали всё в одном аккуратном каталоге: от классических подушек до моделей для детей и будущих мам.': 'O‘lcham, to‘ldiruvchi va formatni ortiqcha shovqinsiz tanlang. Klassik yostiqlardan bolalar va bo‘lajak onalar modellarigacha hammasini bir katalogga jamladik.',
            'Если вы пока не знаете, что выбрать, можно начать с размера, наполнителя и привычной позы сна. А консультант Sweet Pillow Dreams подскажет направление без лишней технической путаницы.': 'Nimani tanlashni bilmasangiz, o‘lcham, to‘ldiruvchi va odatiy uyqu holatidan boshlang. Sweet Pillow Dreams maslahatchisi ortiqcha murakkabliksiz yo‘l ko‘rsatadi.',
            'товаров в каталоге': 'katalogdagi mahsulotlar',
            'популярных размеров': 'mashhur o‘lchamlar',
            'офлайн-магазин и мастерская': 'oflayn do‘kon va ustaxona',
            'Быстрый заказ в Telegram': 'Telegram orqali tez buyurtma',
            'Купить': 'Sotib olish',
            'В корзину': 'Savatga',
            'Убрать': 'Olib tashlash',
            'Описание': 'Tavsif',
            'Категория': 'Kategoriya',
            'Товары не найдены. Попробуйте сбросить фильтры или изменить запрос.': 'Mahsulotlar topilmadi. Filtrlarni tozalang yoki so‘rovni o‘zgartiring.',
            'Товары не найдены': 'Mahsulotlar topilmadi',
            'Товар не указан': 'Mahsulot ko‘rsatilmagan',
            'Товар не найден': 'Mahsulot topilmadi',
            'Мы не нашли этот товар. Возможно, ссылка устарела или товар уже убран из каталога.': 'Bu mahsulot topilmadi. Havola eskirgan yoki mahsulot katalogdan olib tashlangan bo‘lishi mumkin.',
            'Откройте товар из каталога или воспользуйтесь поиском.': 'Mahsulotni katalogdan oching yoki qidiruvdan foydalaning.',
            'Вернуться в каталог': 'Katalogga qaytish',
            'Ошибка загрузки': 'Yuklashda xatolik',
            'Не получилось загрузить данные товара. Попробуйте обновить страницу.': 'Mahsulot ma’lumotlarini yuklab bo‘lmadi. Sahifani yangilab ko‘ring.',
            'Ваша корзина пуста': 'Savatingiz bo‘sh',
            'Итого': 'Jami',
            'Цена': 'Narx',
            'Напишите вопрос...': 'Savolingizni yozing...',
            'Консультант Sweet Pillow Dreams': 'Sweet Pillow Dreams maslahatchisi',
            'Ответы опираются на данные каталога и могут требовать уточнения по размеру или наполнителю.': 'Javoblar katalog ma’lumotlariga asoslanadi va o‘lcham yoki to‘ldiruvchi bo‘yicha aniqlik talab qilishi mumkin.',
            'Здравствуйте! Я консультант Sweet Pillow Dreams. Подскажу по размерам, наполнителям, уходу и тому, что лучше выбрать для вашего сна.': 'Salom! Men Sweet Pillow Dreams maslahatchisiman. O‘lcham, to‘ldiruvchi, parvarish va uyqu uchun mos tanlov bo‘yicha yordam beraman.',
            'Комфорт для вашего сна с 2008 года': '2008 yildan beri uyqungiz uchun qulaylik',
            'Контакты': 'Aloqa',
            'Мы в соцсетях': 'Ijtimoiy tarmoqlar',
            'Режим работы': 'Ish vaqti',
            'Все права защищены': 'Barcha huquqlar himoyalangan',
            'Спасибо за понимание. Мы скоро вернёмся.': 'Tushunganingiz uchun rahmat. Tez orada qaytamiz.'
        }
    };

    const placeholders = {
        uz: {
            'Поиск по названию, описанию, размеру...': 'Nomi, tavsifi yoki o‘lchami bo‘yicha qidirish...',
            'Поиск по названию...': 'Nomi bo‘yicha qidirish...',
            'Поиск...': 'Qidirish...',
            'Напишите вопрос...': 'Savolingizni yozing...'
        }
    };

    function getLang() {
        const saved = localStorage.getItem(STORAGE_KEY);
        return SUPPORTED.includes(saved) ? saved : '';
    }

    function setLang(lang) {
        localStorage.setItem(STORAGE_KEY, SUPPORTED.includes(lang) ? lang : 'ru');
        document.documentElement.lang = localStorage.getItem(STORAGE_KEY);
        applyTranslations();
        window.dispatchEvent(new CustomEvent('spd:language-changed', { detail: { lang: getLang() || 'ru' } }));
    }

    function t(text, lang = getLang() || 'ru') {
        if (lang === 'ru') return text;
        return exact[lang]?.[text] || text;
    }

    function translateTextNode(node, lang) {
        if (!originalTextNodes.has(node)) originalTextNodes.set(node, node.nodeValue);
        const raw = originalTextNodes.get(node);
        const compact = raw.replace(/\s+/g, ' ').trim();
        if (!compact) return;
        const translated = t(compact, lang);
        if (translated !== compact) {
            node.nodeValue = raw.replace(compact, translated);
        } else {
            node.nodeValue = raw;
        }
    }

    function applyTranslations() {
        const lang = getLang() || 'ru';
        document.documentElement.lang = lang;
        document.querySelectorAll('[data-lang-current]').forEach((el) => {
            el.textContent = lang === 'uz' ? 'OZ' : 'RU';
        });
        document.querySelectorAll('input[placeholder]').forEach((input) => {
            const source = input.dataset.ruPlaceholder || input.getAttribute('placeholder');
            input.dataset.ruPlaceholder = source;
            input.setAttribute('placeholder', placeholders[lang]?.[source] || source);
        });
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                const parent = node.parentElement;
                if (!parent || ['SCRIPT', 'STYLE'].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach((node) => translateTextNode(node, lang));
    }

    function ensureSwitcher() {
        document.querySelectorAll('.header-content').forEach((header) => {
            if (header.querySelector('.language-toggle')) return;
            const button = document.createElement('button');
            button.className = 'language-toggle';
            button.type = 'button';
            button.innerHTML = '<span data-lang-current>RU</span>';
            button.title = 'RU / OZ';
            button.addEventListener('click', () => setLang((getLang() || 'ru') === 'ru' ? 'uz' : 'ru'));
            const theme = header.querySelector('.theme-toggle');
            if (theme) header.insertBefore(button, theme);
            else header.appendChild(button);
        });
    }

    function showLanguageGate() {
        if (getLang()) return;
        const gate = document.createElement('div');
        gate.className = 'language-gate';
        gate.innerHTML = `
            <div class="language-gate-card">
                <div class="language-gate-mark">Sweet Pillow Dreams</div>
                <h2>Выберите язык</h2>
                <p>Tilni tanlang</p>
                <div class="language-gate-actions">
                    <button data-lang-pick="ru">Русский</button>
                    <button data-lang-pick="uz">O‘zbek</button>
                </div>
            </div>
        `;
        document.body.appendChild(gate);
        gate.querySelectorAll('[data-lang-pick]').forEach((button) => {
            button.addEventListener('click', () => {
                setLang(button.dataset.langPick);
                gate.remove();
            });
        });
    }

    function productDescription(product) {
        const lang = getLang() || 'ru';
        if (lang === 'uz') return product?.description_uz || product?.description || '';
        return product?.description_ru || product?.description || '';
    }

    window.SPD_I18N = { getLang: () => getLang() || 'ru', setLang, t, applyTranslations, productDescription };

    document.addEventListener('DOMContentLoaded', () => {
        ensureSwitcher();
        showLanguageGate();
        applyTranslations();
    });
})();
