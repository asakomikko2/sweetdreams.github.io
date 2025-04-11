const cartIcon = document.getElementById("cartIcon");
const cartMenu = document.getElementById("cartMenu");
const cartItems = document.getElementById("cartItems");
const checkoutBtn = document.getElementById("checkout");
const cancelBtn = document.getElementById("cancel");
const checkoutForm = document.getElementById("checkoutForm");
const backBtn = document.getElementById("back");
const submitBtn = document.getElementById("submit");
const checkoutItems = document.getElementById("checkoutItems");

let cart = [];

document.querySelectorAll(".add-to-cart").forEach(btn => {
    btn.addEventListener("click", e => {
        const product = e.target.previousElementSibling.textContent;
        cart.push(product);
        updateCart();
        animateToCart(e.target);
    });
});

function animateToCart(button) {
    const circle = document.createElement("div");
    circle.classList.add("fly-circle");
    document.body.appendChild(circle);
    const rect = button.getBoundingClientRect();
    circle.style.left = rect.left + "px";
    circle.style.top = rect.top + "px";
    setTimeout(() => {
        circle.style.left = cartIcon.getBoundingClientRect().left + "px";
        circle.style.top = cartIcon.getBoundingClientRect().top + "px";
        circle.style.transform = "scale(0.1)";
    }, 10);
    setTimeout(() => circle.remove(), 1000);
}

cartIcon.addEventListener("click", () => {
    cartMenu.classList.toggle("hidden");
    checkoutForm.classList.add("hidden");
});

cancelBtn.addEventListener("click", () => {
    cartMenu.classList.add("hidden");
});

checkoutBtn.addEventListener("click", () => {
    checkoutForm.classList.remove("hidden");
    cartMenu.classList.add("hidden");
    updateCheckout();
});

backBtn.addEventListener("click", () => {
    checkoutForm.classList.add("hidden");
    cartMenu.classList.remove("hidden");
});

submitBtn.addEventListener("click", () => {
    const name = document.getElementById("name").value.trim();
    const phone = document.getElementById("phone").value.trim();
    const username = document.getElementById("username").value.trim();
    if (!name || !phone || !username) {
        alert("Все поля должны быть заполнены!");
        return;
    }
    fetch("/submit", {
        method: "POST",
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, phone, username, cart })
    }).then(() => {
        alert("✅ Заказ успешно отправлен!");
        cart = [];
        updateCart();
        checkoutForm.classList.add("hidden");
    });
});

function updateCart() {
    cartItems.innerHTML = "";
    cart.forEach((item, index) => {
        const div = document.createElement("div");
        div.innerHTML = `${item} <button onclick="removeItem(${index})">❌</button>`;
        cartItems.appendChild(div);
    });
}

function updateCheckout() {
    checkoutItems.innerHTML = "";
    cart.forEach(item => {
        const div = document.createElement("div");
        div.textContent = item;
        checkoutItems.appendChild(div);
    });
}

function removeItem(index) {
    cart.splice(index, 1);
    updateCart();
}