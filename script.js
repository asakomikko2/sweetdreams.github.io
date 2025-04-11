let cart = [];

function addToCart(item, event) {
  cart.push(item);
  showAnimation(event);
}

function showAnimation(event) {
  const circle = document.createElement("div");
  circle.className = "fly-circle";
  document.body.appendChild(circle);
  const rect = event.target.getBoundingClientRect();
  circle.style.left = rect.left + "px";
  circle.style.top = rect.top + "px";
  setTimeout(() => circle.remove(), 1000);
}

function toggleCart() {
  document.getElementById("cart-menu").classList.toggle("hidden");
  updateCartList();
}

function updateCartList() {
  const list = document.getElementById("cart-items");
  list.innerHTML = "";
  cart.forEach((item, index) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${item}</span><button onclick="removeItem(${index})">✖</button>`;
    list.appendChild(li);
  });
}

function removeItem(index) {
  cart.splice(index, 1);
  updateCartList();
}

function openOrderForm() {
  document.getElementById("cart-menu").classList.add("hidden");
  document.getElementById("order-form").classList.remove("hidden");
  document.getElementById("order-products").value = cart.join("\n");
}

function backToCart() {
  document.getElementById("order-form").classList.add("hidden");
  document.getElementById("cart-menu").classList.remove("hidden");
}

function submitOrder() {
  const name = document.getElementById("name").value.trim();
  const phone = document.getElementById("phone").value.trim();
  const username = document.getElementById("username").value.trim();
  const error = document.getElementById("error-message");

  if (!name || !phone || !username) {
    error.textContent = "Все поля должны быть заполнены!";
    return;
  }

  error.textContent = "";
  alert("✅ Заказ успешно отправлен!");

  fetch('https://api.telegram.org/bot7846505135:AAHAMEpaMYKqDsRZBeMFw0XN9IHwkm2zDOg/sendMessage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: "-1002467157048",
      text: `🔔 @top4ik3333\n📦 Новый заказ:\n👤 Имя: ${name}\n📱 Телефон: ${phone}\n✈️ Telegram: ${username}\n🛍️ Товары:\n${cart.map(i => '• ' + i).join('\n')}`
    })
  });
}