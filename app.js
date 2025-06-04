// app.js
window.Telegram.WebApp.ready();
const user = window.Telegram.WebApp.initDataUnsafe.user || { id: 0, username: 'User' };

// Инициализация Chart.js
const ctx = document.getElementById('crypto-chart').getContext('2d');
let cryptoChart = null;

// Навигация по страницам
function navigateTo(page) {
    document.querySelectorAll('.content > div').forEach(div => div.style.display = 'none');
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    
    if (page === 'home') {
        document.querySelector('.balance-section').style.display = 'block';
        document.querySelector('.actions-grid').style.display = 'grid';
        document.querySelector('.assets-section').style.display = 'block';
        document.querySelector('.nav-item:nth-child(1)').classList.add('active');
    } else if (page === 'stars') {
        document.querySelector('.stars-container').style.display = 'block';
        document.querySelector('.nav-item:nth-child(3)').classList.add('active');
    } else if (page === 'history') {
        document.querySelector('.history-section').style.display = 'block';
        document.querySelector('.nav-item:nth-child(2)').classList.add('active');
    } else if (page === 'profile') {
        // Реализуйте профиль, если нужно
    }
}

// Открытие/закрытие модальных окон
function openModal(modalId) {
    document.getElementById(modalId).classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
}

// Выбор количества Stars для покупки
let selectedStarsAmount = 500;
function selectStarsAmount(amount) {
    selectedStarsAmount = amount;
    document.querySelectorAll('.currency-option').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
}

// Загрузка данных пользователя
async function loadUserData() {
    try {
        const response = await fetch(`/user_data_api?user_id=${user.id}`);
        const data = await response.json();
        if (data.status === 'success') {
            document.querySelector('.balance-amount span').textContent = `${data.balance.toFixed(2)} USDT`;
            document.querySelector('.stars-amount span').textContent = data.stars;
            document.querySelector('.crypto-equivalent').textContent = `${(data.stars * 0.012987).toFixed(2)} USDT`;
            document.querySelector('.username').textContent = `@${data.username}`;
        }
    } catch (error) {
        console.error('Ошибка загрузки данных пользователя:', error);
    }
}

// Загрузка курсов криптовалют
async function loadCryptoRates() {
    try {
        const response = await fetch('/crypto_rates_api');
        const rates = await response.json();
        const assetList = document.querySelector('.assets-list');
        assetList.innerHTML = '';
        
        for (const [coin, data] of Object.entries(rates)) {
            const item = document.createElement('div');
            item.className = 'asset-item';
            item.innerHTML = `
                <div class="asset-info">
                    <div class="asset-icon">${coin.toUpperCase()}</div>
                    <div class="asset-details">
                        <div class="asset-name">${coin.toUpperCase()}</div>
                        <div class="asset-price">$${data.price.toFixed(2)}</div>
                    </div>
                </div>
                <div class="asset-balance">
                    <div class="balance-rub">${(data.balance || 0).toFixed(6)}</div>
                    <div class="asset-change ${data.change >= 0 ? 'positive' : 'negative'}">
                        ${data.change >= 0 ? '+' : ''}${data.change}%
                    </div>
                </div>
            `;
            assetList.appendChild(item);
        }

        // Обновление графика
        if (cryptoChart) cryptoChart.destroy();
        cryptoChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Object.keys(rates).map(() => new Date().toLocaleTimeString()),
                datasets: [{
                    label: 'Crypto Prices',
                    data: Object.values(rates).map(data => data.price),
                    borderColor: 'var(--accent-purple)',
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    } catch (error) {
        console.error('Ошибка загрузки курсов:', error);
    }
}

// Покупка Stars
function buyStars() {
    window.Telegram.WebApp.sendData(JSON.stringify({
        user_id: user.id,
        type: 'buy_stars',
        amount: selectedStarsAmount
    }));
    closeModal('stars-purchase-modal');
}

// Вывод Stars
function withdrawStars() {
    const amount = parseInt(document.getElementById('withdraw-amount').value);
    const recipient = document.getElementById('withdraw-recipient').value;
    
    if (!amount || amount <= 0 || !recipient) {
        alert('Введите корректное количество и получателя');
        return;
    }
    
    window.Telegram.WebApp.sendData(JSON.stringify({
        user_id: user.id,
        type: 'withdraw_stars',
        amount: amount,
        recipient: recipient
    }));
    closeModal('stars-withdraw-modal');
}

// Обмен Stars
document.querySelector('.exchange-btn').addEventListener('click', () => {
    const amount = parseInt(document.querySelector('.exchange-form .form-input').value);
    const currency = document.querySelector('.currency-option.active').textContent.toLowerCase();
    
    if (!amount || amount <= 0) {
        alert('Введите корректное количество Stars');
        return;
    }
    
    window.Telegram.WebApp.sendData(JSON.stringify({
        user_id: user.id,
        type: 'exchange_stars',
        amount: amount,
        currency: currency
    }));
    
    document.querySelector('.exchange-result-amount').textContent = `~${(amount * 0.012987).toFixed(2)} ${currency.toUpperCase()}`;
});

// Поиск криптовалют
document.getElementById('crypto-search').addEventListener('input', (e) => {
    const search = e.target.value.toLowerCase();
    document.querySelectorAll('.asset-item').forEach(item => {
        const coin = item.querySelector('.asset-name').textContent.toLowerCase();
        item.style.display = coin.includes(search) ? 'flex' : 'none';
    });
});

// Выбор валюты
document.querySelectorAll('.currency-option').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.currency-option').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    loadUserData();
    loadCryptoRates();
    navigateTo('home');
});
