
document.addEventListener("DOMContentLoaded", () => {
    const catalogBtn = document.getElementById("catalogBtn");
    const catalog = document.getElementById("catalog");
    const productDetails = document.getElementById("productDetails");
    const cartIcon = document.getElementById("cartIcon");

    let cart = JSON.parse(localStorage.getItem("cart")) || [];

    catalogBtn.addEventListener("click", () => {
        catalog.classList.toggle("hidden");
        if (!catalog.classList.contains("loaded")) {
            loadProducts();
            catalog.classList.add("loaded");
        }
    });

    function loadProducts() {
        const products = [
            {name: "Подушка «Облако»", desc: "Мягкая и нежная", size: "50x70", price: "1200₽"},
            {name: "Наволочка «Лён»", desc: "Натуральный материал", size: "50x70", price: "600₽"},
            {name: "Ортопедическая подушка", desc: "Поддержка шеи", size: "60x40", price: "1800₽"},
            {name: "Подушка для беременных", desc: "Форма U", size: "140x80", price: "2400₽"},
            {name: "Детская подушка", desc: "Гипоаллергенная", size: "40x40", price: "900₽"},
            {name: "Наволочка с принтом", desc: "Яркие цвета", size: "50x70", price: "700₽"},
            {name: "Анатомическая подушка", desc: "Формуется по голове", size: "60x40", price: "2200₽"},
            {name: "Подушка «Снежинка»", desc: "Охлаждающая", size: "50x70", price: "2000₽"},
            {name: "Подушка для путешествий", desc: "U-форма", size: "30x30", price: "800₽"},
            {name: "Набор: Подушка + наволочка", desc: "Идеальное сочетание", size: "50x70", price: "1500₽"},
        ];

        products.forEach((p, index) => {
            const div = document.createElement("div");
            div.className = "card";
            div.innerHTML = `
                <img src="images/mockup_1.png" width="100%">
                <h3>${p.name}</h3>
                <p>${p.desc}<br>(${p.size}, ${p.price})</p>
                <button class="oval-button" onclick="openDetails()">Подробнее</button>
                <button class="oval-button" onclick="addToCart('${p.name}')">В корзину 🛒</button>
            `;
            catalog.appendChild(div);
        });
    }

    window.openDetails = () => {
        productDetails.classList.remove("hidden");
    };

    window.closeModal = () => {
        productDetails.classList.add("hidden");
    };

    window.addToCart = (productName) => {
        cart.push(productName);
        localStorage.setItem("cart", JSON.stringify(cart));

        // Анимация "полет круга"
        const circle = document.createElement("div");
        circle.style.position = "fixed";
        circle.style.width = "20px";
        circle.style.height = "20px";
        circle.style.borderRadius = "50%";
        circle.style.background = "#ffaaa7";
        circle.style.zIndex = 100;
        circle.style.left = "50%";
        circle.style.top = "50%";
        circle.style.transform = "translate(-50%, -50%)";
        document.body.appendChild(circle);

        setTimeout(() => {
            circle.style.transition = "all 0.8s ease";
            circle.style.left = cartIcon.getBoundingClientRect().left + "px";
            circle.style.top = cartIcon.getBoundingClientRect().top + "px";
            circle.style.opacity = "0";
            circle.style.transform = "scale(0)";
        }, 10);

        setTimeout(() => {
            circle.remove();
        }, 900);
    };
});
