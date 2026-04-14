import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

import asyncpg
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiohttp
import json

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [7973988177]
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "")
CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# ==================== ПРЕМИУМ ЭМОДЗИ ID ====================
EMOJI = {
    "settings": "5870982283724328568",      # ⚙
    "profile": "5870994129244131212",       # 👤
    "users": "5870772616305839506",         # 👥
    "user_check": "5891207662678317861",    # 👤✅
    "user_cross": "5893192487324880883",    # 👤❌
    "file": "5870528606328852614",          # 📁
    "smile": "5870764288364252592",         # 🙂
    "chart_up": "5870930636742595124",      # 📊
    "stats": "5870921681735781843",         # 📊
    "home": "5873147866364514353",          # 🏘
    "lock": "6037249452824072506",          # 🔒
    "unlock": "6037496202990194718",        # 🔓
    "megaphone": "6039422865189638057",     # 📣
    "check": "5870633910337015697",         # ✅
    "cross": "5870657884844462243",         # ❌
    "pencil": "5870676941614354370",        # 🖋
    "trash": "5870875489362513438",         # 🗑
    "down": "5893057118545646106",          # 📰
    "clip": "6039451237743595514",          # 📎
    "link": "5769289093221454192",          # 🔗
    "info": "6028435952299413210",          # ℹ
    "bot": "6030400221232501136",           # 🤖
    "eye": "6037397706505195857",           # 👁
    "eye_hidden": "6037243349675544634",    # 👁
    "send": "5963103826075456248",          # ⬆
    "download": "6039802767931871481",      # ⬇
    "bell": "6039486778597970865",          # 🔔
    "gift": "6032644646587338669",          # 🎁
    "clock": "5983150113483134607",         # ⏰
    "party": "6041731551845159060",         # 🎉
    "font": "5870801517140775623",          # 🔗
    "write": "5870753782874246579",         # ✍
    "media": "6035128606563241721",         # 🖼
    "geo": "6042011682497106307",           # 📍
    "wallet": "5769126056262898415",        # 👛
    "box": "5884479287171485878",           # 📦
    "crypto": "5260752406890711732",        # 👾
    "calendar": "5890937706803894250",      # 📅
    "tag": "5886285355279193209",           # 🏷
    "time_past": "5775896410780079073",     # 🕓
    "apps": "5778672437122045013",          # 📦
    "brush": "6050679691004612757",         # 🖌
    "add_text": "5771851822897566479",      # 🔡
    "format": "5778479949572738874",        # ↔
    "money": "5904462880941545555",         # 🪙
    "money_send": "5890848474563352982",    # 🪙
    "money_receive": "5879814368572478751", # 🏧
    "code": "5940433880585605708",          # 🔨
    "loading": "5345906554510012647",       # 🔄
    "shop": "5886285355279193209",          # 🏷
    "support": "6039422865189638057",       # 📣
    "add": "5891207662678317861",           # ➕
    "card": "5769126056262898415",          # 💳
    "sbp": "5879814368572478751",           # 📱
}

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self.create_tables()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    balance DECIMAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    emoji_id TEXT,
                    sort_order INT DEFAULT 0
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    category_id INT REFERENCES categories(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    price DECIMAL NOT NULL,
                    quantity INT DEFAULT -1,
                    content_type TEXT NOT NULL,
                    content_data JSONB,
                    emoji_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    product_id INT REFERENCES products(id),
                    quantity INT DEFAULT 1,
                    total_price DECIMAL NOT NULL,
                    payment_method TEXT,
                    status TEXT DEFAULT 'pending',
                    payment_proof TEXT,
                    crypto_invoice_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id SERIAL PRIMARY KEY,
                    message_text TEXT,
                    media_type TEXT,
                    media_file_id TEXT,
                    sent_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            categories = [
                ("Боты", EMOJI["bot"], 1),
                ("Интеграции", EMOJI["link"], 2),
                ("Другое", EMOJI["box"], 3)
            ]
            for name, emoji_id, sort_order in categories:
                await conn.execute("""
                    INSERT INTO categories (name, emoji_id, sort_order)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                """, name, emoji_id, sort_order)

    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            return dict(row) if row else None

    async def create_user(self, user_id: int, username: str, full_name: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, full_name, balance)
                VALUES ($1, $2, $3, 0)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name
            """, user_id, username, full_name)

    async def get_categories(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM categories ORDER BY sort_order")
            return [dict(row) for row in rows]

    async def get_products_by_category(self, category_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM products WHERE category_id = $1 AND (quantity = -1 OR quantity > 0) ORDER BY id",
                category_id
            )
            return [dict(row) for row in rows]

    async def get_product(self, product_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
            return dict(row) if row else None

    async def create_product(self, data: Dict) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO products (category_id, name, description, price, quantity, content_type, content_data, emoji_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, data['category_id'], data['name'], data['description'], data['price'],
                 data['quantity'], data['content_type'], json.dumps(data['content_data']), data.get('emoji_id'))
            return row['id']

    async def update_product(self, product_id: int, data: Dict):
        async with self.pool.acquire() as conn:
            updates = []
            values = []
            i = 1
            for key, value in data.items():
                if value is not None:
                    updates.append(f"{key} = ${i}")
                    values.append(json.dumps(value) if key == 'content_data' else value)
                    i += 1
            if updates:
                values.append(product_id)
                await conn.execute(f"""
                    UPDATE products SET {', '.join(updates)} WHERE id = ${i}
                """, *values)

    async def delete_product(self, product_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM products WHERE id = $1", product_id)

    async def create_order(self, data: Dict) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO orders (user_id, product_id, quantity, total_price, payment_method, status, crypto_invoice_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """, data['user_id'], data['product_id'], data.get('quantity', 1),
                 data['total_price'], data['payment_method'], data.get('status', 'pending'),
                 data.get('crypto_invoice_id'))
            return row['id']

    async def update_order_status(self, order_id: int, status: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE orders SET status = $1, updated_at = NOW() WHERE id = $2
            """, status, order_id)

    async def get_order(self, order_id: int) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
            return dict(row) if row else None

    async def get_pending_orders(self) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT o.*, p.name as product_name, u.username, u.full_name
                FROM orders o
                JOIN products p ON o.product_id = p.id
                JOIN users u ON o.user_id = u.user_id
                WHERE o.status = 'pending_payment_proof'
                ORDER BY o.created_at DESC
            """)
            return [dict(row) for row in rows]

    async def get_all_users(self) -> List[int]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [row['user_id'] for row in rows]

    async def get_stats(self) -> Dict:
        async with self.pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users")
            orders = await conn.fetchval("SELECT COUNT(*) FROM orders")
            completed = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
            revenue = await conn.fetchval("SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status = 'completed'")
            products = await conn.fetchval("SELECT COUNT(*) FROM products")
            return {
                "users": users,
                "orders": orders,
                "completed_orders": completed,
                "revenue": revenue,
                "products": products
            }

db = Database()

# ==================== СОСТОЯНИЯ FSM ====================
class AddProductStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_quantity = State()
    waiting_for_content_type = State()
    waiting_for_text_content = State()
    waiting_for_media = State()
    waiting_for_emoji = State()

class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm = State()

class OrderStates(StatesGroup):
    waiting_for_payment_proof = State()

# ==================== КЛАВИАТУРЫ С ПРЕМИУМ ЭМОДЗИ ====================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура главного меню с премиум эмодзи"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Купить"),
                KeyboardButton(text="Профиль")
            ],
            [
                KeyboardButton(text="Поддержка")
            ]
        ],
        resize_keyboard=True
    )

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Админ клавиатура с премиум эмодзи"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Статистика"),
                KeyboardButton(text="Рассылка")
            ],
            [
                KeyboardButton(text="Добавить товар"),
                KeyboardButton(text="Редактировать товары")
            ],
            [
                KeyboardButton(text="Заявки на оплату"),
                KeyboardButton(text="Выйти из админки")
            ]
        ],
        resize_keyboard=True
    )

def get_categories_keyboard(categories: List[Dict]) -> InlineKeyboardMarkup:
    """Клавиатура категорий с премиум эмодзи"""
    buttons = []
    for cat in categories:
        text = cat['name']
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"category_{cat['id']}"
        )])
    buttons.append([InlineKeyboardButton(
        text="Назад",
        callback_data="back_to_main_menu"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_products_keyboard(products: List[Dict], category_id: int) -> InlineKeyboardMarkup:
    """Клавиатура товаров"""
    buttons = []
    for product in products:
        stock = "" if product['quantity'] == -1 else f" ({product['quantity']} шт.)"
        buttons.append([InlineKeyboardButton(
            text=f"{product['name']} - {product['price']}₽{stock}",
            callback_data=f"product_{product['id']}"
        )])
    buttons.append([InlineKeyboardButton(
        text="Назад",
        callback_data="back_to_categories"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_product_detail_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура деталей товара"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Купить",
            callback_data=f"buy_{product_id}"
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data=f"back_to_products_{product_id}"
        )]
    ])

def get_payment_methods_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора способа оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Crypto Bot",
            callback_data=f"pay_crypto_{order_id}"
        )],
        [InlineKeyboardButton(
            text="СБП",
            callback_data=f"pay_sbp_{order_id}"
        )],
        [InlineKeyboardButton(
            text="Карта",
            callback_data=f"pay_card_{order_id}"
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data="back_to_shop"
        )]
    ])

def get_payment_confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Я оплатил",
            callback_data=f"paid_{order_id}"
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data=f"back_to_payment_{order_id}"
        )]
    ])

def get_admin_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для админа по заявке"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Одобрить",
            callback_data=f"approve_order_{order_id}"
        )],
        [InlineKeyboardButton(
            text="Отклонить",
            callback_data=f"reject_order_{order_id}"
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data="admin_panel"
        )]
    ])

def get_broadcast_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Отмена",
            callback_data="cancel_broadcast"
        )]
    ])

def get_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Отправить",
            callback_data="confirm_broadcast"
        )],
        [InlineKeyboardButton(
            text="Отмена",
            callback_data="cancel_broadcast"
        )]
    ])

def get_content_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Текст",
            callback_data="content_text"
        )],
        [InlineKeyboardButton(
            text="Фото",
            callback_data="content_photo"
        )],
        [InlineKeyboardButton(
            text="Видео",
            callback_data="content_video"
        )],
        [InlineKeyboardButton(
            text="Файл",
            callback_data="content_document"
        )],
        [InlineKeyboardButton(
            text="Отмена",
            callback_data="cancel_add_product"
        )]
    ])

def get_admin_products_keyboard(products: List[Dict]) -> InlineKeyboardMarkup:
    buttons = []
    for product in products:
        buttons.append([InlineKeyboardButton(
            text=f"{product['name']} - {product['price']}₽",
            callback_data=f"edit_product_{product['id']}"
        )])
    buttons.append([InlineKeyboardButton(
        text="Назад",
        callback_data="admin_panel"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_edit_fields_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Название",
            callback_data=f"edit_field_name_{product_id}"
        )],
        [InlineKeyboardButton(
            text="Описание",
            callback_data=f"edit_field_desc_{product_id}"
        )],
        [InlineKeyboardButton(
            text="Цена",
            callback_data=f"edit_field_price_{product_id}"
        )],
        [InlineKeyboardButton(
            text="Количество",
            callback_data=f"edit_field_qty_{product_id}"
        )],
        [InlineKeyboardButton(
            text="Удалить товар",
            callback_data=f"delete_product_{product_id}"
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data="admin_products"
        )]
    ])

# ==================== ФУНКЦИИ ПОМОЩНИКИ ====================
async def check_crypto_payment(invoice_id: str) -> Optional[Dict]:
    async with aiohttp.ClientSession() as session:
        headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
        async with session.get(f"{CRYPTO_BOT_API_URL}/getInvoices", headers=headers, params={"invoice_ids": invoice_id}) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]
    return None

async def create_crypto_invoice(amount_rub: float, description: str) -> Optional[Dict]:
    amount_usdt = round(amount_rub / 90, 2)
    
    async with aiohttp.ClientSession() as session:
        headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
        data = {
            "asset": "USDT",
            "amount": str(amount_usdt),
            "description": description,
            "allow_comments": False,
            "allow_anonymous": False
        }
        async with session.post(f"{CRYPTO_BOT_API_URL}/createInvoice", headers=headers, json=data) as resp:
            result = await resp.json()
            if result.get("ok"):
                return result["result"]
    return None

async def send_product_content(user_id: int, product: Dict):
    content_data = json.loads(product['content_data']) if isinstance(product['content_data'], str) else product['content_data']
    content_type = product['content_type']
    
    if content_type == 'text':
        await bot.send_message(user_id, content_data['text'])
    elif content_type == 'photo':
        media_group = []
        for i, file_id in enumerate(content_data['file_ids'][:10]):
            if i == 0:
                media_group.append(InputMediaPhoto(media=file_id, caption=content_data.get('caption', '')))
            else:
                media_group.append(InputMediaPhoto(media=file_id))
        if media_group:
            await bot.send_media_group(user_id, media_group)
    elif content_type == 'video':
        for file_id in content_data['file_ids'][:10]:
            await bot.send_video(user_id, file_id, caption=content_data.get('caption', ''))
    elif content_type == 'document':
        for file_id in content_data['file_ids'][:10]:
            await bot.send_document(user_id, file_id, caption=content_data.get('caption', ''))

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@router.message(Command("start"))
async def cmd_start(message: Message):
    await db.create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    welcome_text = f"""<b>Добро пожаловать в Vest Creator!</b>

<tg-emoji emoji-id="{EMOJI['bot']}"></tg-emoji> Здесь вы можете приобрести:
• Готовых Telegram ботов
• Интеграции для ваших проектов
• Другие полезные решения

Используйте кнопки ниже для навигации."""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer(f"<tg-emoji emoji-id=\"{EMOJI['cross']}\"></tg-emoji> У вас нет доступа к админ-панели.")
        return
    
    await message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['settings']}\"></tg-emoji> Админ-панель</b>",
        reply_markup=get_admin_keyboard()
    )

# ==================== ОБРАБОТЧИКИ ТЕКСТОВЫХ СООБЩЕНИЙ ====================
@router.message(F.text == "Купить")
async def shop_menu(message: Message):
    categories = await db.get_categories()
    
    text = f"<b><tg-emoji emoji-id=\"{EMOJI['shop']}\"></tg-emoji> Выберите категорию:</b>"
    await message.answer(text, reply_markup=get_categories_keyboard(categories))

@router.message(F.text == "Профиль")
async def profile_menu(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        user = {"username": message.from_user.username, "balance": 0}
        await db.create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    
    profile_text = f"""<b><tg-emoji emoji-id="{EMOJI['profile']}"></tg-emoji> Профиль</b>

<tg-emoji emoji-id="{EMOJI['profile']}"></tg-emoji> <b>Username:</b> @{user['username'] or 'Не указан'}
<tg-emoji emoji-id="{EMOJI['wallet']}"></tg-emoji> <b>Баланс:</b> {user['balance']} ₽"""
    
    await message.answer(profile_text)

@router.message(F.text == "Поддержка")
async def support_menu(message: Message):
    support_text = f"""<b><tg-emoji emoji-id="{EMOJI['support']}"></tg-emoji> Поддержка</b>

<tg-emoji emoji-id="{EMOJI['support']}"></tg-emoji> По всем вопросам обращайтесь: @VestSupport"""
    
    await message.answer(support_text)

@router.message(F.text == "Статистика")
async def admin_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    stats = await db.get_stats()
    stats_text = f"""<b><tg-emoji emoji-id="{EMOJI['stats']}"></tg-emoji> Статистика</b>

<tg-emoji emoji-id="{EMOJI['profile']}"></tg-emoji> Пользователей: {stats['users']}
<tg-emoji emoji-id="{EMOJI['box']}"></tg-emoji> Товаров: {stats['products']}
<tg-emoji emoji-id="{EMOJI['stats']}"></tg-emoji> Всего заказов: {stats['orders']}
<tg-emoji emoji-id="{EMOJI['check']}"></tg-emoji> Выполнено: {stats['completed_orders']}
<tg-emoji emoji-id="{EMOJI['money']}"></tg-emoji> Выручка: {stats['revenue']} ₽"""
    
    await message.answer(stats_text)

@router.message(F.text == "Рассылка")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['megaphone']}\"></tg-emoji> Отправьте сообщение для рассылки всем пользователям.</b>",
        reply_markup=get_broadcast_keyboard()
    )
    await state.set_state(BroadcastStates.waiting_for_message)

@router.message(F.text == "Добавить товар")
async def admin_add_product_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    categories = await db.get_categories()
    buttons = []
    for cat in categories:
        buttons.append([InlineKeyboardButton(
            text=cat['name'],
            callback_data=f"add_cat_{cat['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_add_product")])
    
    await message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['add']}\"></tg-emoji> Выберите категорию для нового товара:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(AddProductStates.waiting_for_category)

@router.message(F.text == "Редактировать товары")
async def admin_edit_products(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM products ORDER BY id")
        products = [dict(row) for row in rows]
    
    if not products:
        await message.answer(f"<b><tg-emoji emoji-id=\"{EMOJI['info']}\"></tg-emoji> Нет товаров для редактирования.</b>")
        return
    
    await message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['pencil']}\"></tg-emoji> Выберите товар для редактирования:</b>",
        reply_markup=get_admin_products_keyboard(products)
    )

@router.message(F.text == "Заявки на оплату")
async def admin_pending_orders(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    orders = await db.get_pending_orders()
    if not orders:
        await message.answer(f"<b><tg-emoji emoji-id=\"{EMOJI['info']}\"></tg-emoji> Нет заявок на рассмотрение.</b>")
        return
    
    for order in orders:
        order_text = f"""<b><tg-emoji emoji-id="{EMOJI['money_receive']}"></tg-emoji> Заявка #{order['id']}</b>

<tg-emoji emoji-id="{EMOJI['profile']}"></tg-emoji> Пользователь: @{order['username']} ({order['full_name']})
<tg-emoji emoji-id="{EMOJI['box']}"></tg-emoji> Товар: {order['product_name']}
<tg-emoji emoji-id="{EMOJI['money']}"></tg-emoji> Сумма: {order['total_price']} ₽
<tg-emoji emoji-id="{EMOJI['wallet']}"></tg-emoji> Метод: {order['payment_method']}"""
        
        if order.get('payment_proof'):
            try:
                await bot.send_photo(
                    message.from_user.id,
                    order['payment_proof'],
                    caption=order_text,
                    reply_markup=get_admin_order_keyboard(order['id'])
                )
            except:
                await message.answer(
                    order_text + f"\n\n<tg-emoji emoji-id=\"{EMOJI['file']}\"></tg-emoji> Чек: {order['payment_proof']}",
                    reply_markup=get_admin_order_keyboard(order['id'])
                )
        else:
            await message.answer(order_text, reply_markup=get_admin_order_keyboard(order['id']))

@router.message(F.text == "Выйти из админки")
async def admin_exit(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> Вы вышли из админ-панели.</b>",
        reply_markup=get_main_keyboard()
    )

# ==================== CALLBACK ОБРАБОТЧИКИ ====================
@router.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['home']}\"></tg-emoji> Главное меню</b>",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    categories = await db.get_categories()
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI['shop']}\"></tg-emoji> Выберите категорию:</b>",
        reply_markup=get_categories_keyboard(categories)
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_shop")
async def back_to_shop(callback: CallbackQuery):
    categories = await db.get_categories()
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI['shop']}\"></tg-emoji> Выберите категорию:</b>",
        reply_markup=get_categories_keyboard(categories)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("category_"))
async def show_category_products(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    products = await db.get_products_by_category(category_id)
    
    if not products:
        await callback.message.edit_text(
            f"<b><tg-emoji emoji-id=\"{EMOJI['info']}\"></tg-emoji> В этой категории пока нет товаров.</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_categories")]
            ])
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI['box']}\"></tg-emoji> Выберите товар:</b>",
        reply_markup=get_products_keyboard(products, category_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("product_"))
async def show_product_detail(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = await db.get_product(product_id)
    
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    
    stock_text = "Неограниченно" if product['quantity'] == -1 else f"{product['quantity']} шт."
    
    detail_text = f"""<b>{product['name']}</b>

{product['description']}

<tg-emoji emoji-id="{EMOJI['money']}"></tg-emoji> <b>Цена:</b> {product['price']} ₽
<tg-emoji emoji-id="{EMOJI['box']}"></tg-emoji> <b>В наличии:</b> {stock_text}"""
    
    await callback.message.edit_text(
        detail_text,
        reply_markup=get_product_detail_keyboard(product_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("back_to_products_"))
async def back_to_products(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[3])
    product = await db.get_product(product_id)
    if product:
        products = await db.get_products_by_category(product['category_id'])
        await callback.message.edit_text(
            f"<b><tg-emoji emoji-id=\"{EMOJI['box']}\"></tg-emoji> Выберите товар:</b>",
            reply_markup=get_products_keyboard(products, product['category_id'])
        )
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = await db.get_product(product_id)
    
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    
    if product['quantity'] == 0:
        await callback.answer("Товар закончился", show_alert=True)
        return
    
    order_id = await db.create_order({
        'user_id': callback.from_user.id,
        'product_id': product_id,
        'total_price': product['price'],
        'payment_method': None
    })
    
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI['money_send']}\"></tg-emoji> Оформление заказа #{order_id}</b>\n\nВыберите способ оплаты:",
        reply_markup=get_payment_methods_keyboard(order_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    product = await db.get_product(order['product_id'])
    
    invoice = await create_crypto_invoice(float(order['total_price']), f"Заказ #{order_id} - {product['name']}")
    
    if not invoice:
        await callback.answer("Ошибка создания счета", show_alert=True)
        return
    
    await db.update_order_status(order_id, 'pending_crypto')
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET crypto_invoice_id = $1 WHERE id = $2",
            invoice['invoice_id'], order_id
        )
    
    pay_text = f"""<b><tg-emoji emoji-id=\"{EMOJI['crypto']}\"></tg-emoji> Оплата через Crypto Bot</b>

<tg-emoji emoji-id="{EMOJI['crypto']}"></tg-emoji> Сумма к оплате: {invoice['amount']} {invoice['asset']}
<tg-emoji emoji-id="{EMOJI['link']}"></tg-emoji> Ссылка для оплаты: {invoice['pay_url']}

После оплаты нажмите кнопку "Я оплатил"."""
    
    await callback.message.edit_text(
        pay_text,
        reply_markup=get_payment_confirmation_keyboard(order_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pay_sbp_"))
async def pay_sbp(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    
    await db.update_order_status(order_id, 'pending_sbp')
    
    sbp_text = f"""<b><tg-emoji emoji-id=\"{EMOJI['sbp']}\"></tg-emoji> Оплата через СБП</b>

<tg-emoji emoji-id="{EMOJI['money_send']}"></tg-emoji> Сумма: {order['total_price']} ₽
<tg-emoji emoji-id="{EMOJI['wallet']}"></tg-emoji> Номер телефона: +79818376180
<tg-emoji emoji-id="{EMOJI['money_receive']}"></tg-emoji> Банк: ЮMONEY

После оплаты отправьте скриншот/чек об оплате."""
    
    await state.set_state(OrderStates.waiting_for_payment_proof)
    await state.update_data(order_id=order_id, payment_method='sbp')
    
    await callback.message.edit_text(
        sbp_text,
        reply_markup=get_payment_confirmation_keyboard(order_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pay_card_"))
async def pay_card(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    
    await db.update_order_status(order_id, 'pending_card')
    
    card_text = f"""<b><tg-emoji emoji-id=\"{EMOJI['card']}\"></tg-emoji> Оплата картой</b>

<tg-emoji emoji-id="{EMOJI['money_send']}"></tg-emoji> Сумма: {order['total_price']} ₽
<tg-emoji emoji-id="{EMOJI['card']}"></tg-emoji> Номер карты: 2204 1201 3604 2245

После оплаты отправьте скриншот/чек об оплате."""
    
    await state.set_state(OrderStates.waiting_for_payment_proof)
    await state.update_data(order_id=order_id, payment_method='card')
    
    await callback.message.edit_text(
        card_text,
        reply_markup=get_payment_confirmation_keyboard(order_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("back_to_payment_"))
async def back_to_payment(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[3])
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI['money_send']}\"></tg-emoji> Выберите способ оплаты:</b>",
        reply_markup=get_payment_methods_keyboard(order_id)
    )
    await callback.answer()

async def complete_order(callback: CallbackQuery, order_id: int, order: Dict):
    product = await db.get_product(order['product_id'])
    
    await db.update_order_status(order_id, 'completed')
    
    if product['quantity'] > 0:
        await db.update_product(product['id'], {'quantity': product['quantity'] - 1})
    
    await callback.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> <b>Заказ #{order_id} оплачен!</b>\n\nСейчас я отправлю вам товар..."
    )
    
    await send_product_content(callback.from_user.id, product)
    
    await bot.send_message(
        callback.from_user.id,
        f"<tg-emoji emoji-id=\"{EMOJI['gift']}\"></tg-emoji> <b>Спасибо за покупку!</b>\n\nБудем рады видеть вас снова!"
    )

@router.callback_query(F.data.startswith("paid_"))
async def mark_as_paid(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])
    order = await db.get_order(order_id)
    
    if order['payment_method'] == 'crypto' or order['status'] == 'pending_crypto':
        invoice = await check_crypto_payment(order['crypto_invoice_id'])
        if invoice and invoice['status'] == 'paid':
            await complete_order(callback, order_id, order)
        else:
            await callback.answer("Оплата еще не поступила", show_alert=True)
    else:
        await callback.message.edit_text(
            f"<b><tg-emoji emoji-id=\"{EMOJI['file']}\"></tg-emoji> Отправьте скриншот/чек об оплате.</b>\n\nАдминистратор проверит платеж и подтвердит заказ.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data=f"back_to_payment_{order_id}")]
            ])
        )
        await state.set_state(OrderStates.waiting_for_payment_proof)
        await state.update_data(order_id=order_id)
    
    await callback.answer()

@router.message(StateFilter(OrderStates.waiting_for_payment_proof), F.photo | F.document)
async def receive_payment_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['order_id']
    
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET payment_proof = $1, status = 'pending_payment_proof' WHERE id = $2",
            file_id, order_id
        )
    
    await state.clear()
    
    order = await db.get_order(order_id)
    product = await db.get_product(order['product_id'])
    
    for admin_id in ADMIN_IDS:
        try:
            admin_text = f"""<b><tg-emoji emoji-id=\"{EMOJI['money_receive']}\"></tg-emoji> Новая заявка на оплату #{order_id}</b>

<tg-emoji emoji-id="{EMOJI['profile']}"></tg-emoji> Пользователь: @{message.from_user.username} ({message.from_user.full_name})
<tg-emoji emoji-id="{EMOJI['box']}"></tg-emoji> Товар: {product['name']}
<tg-emoji emoji-id="{EMOJI['money']}"></tg-emoji> Сумма: {order['total_price']} ₽
<tg-emoji emoji-id="{EMOJI['wallet']}"></tg-emoji> Метод: {order['payment_method']}"""
            
            if message.photo:
                await bot.send_photo(
                    admin_id,
                    message.photo[-1].file_id,
                    caption=admin_text,
                    reply_markup=get_admin_order_keyboard(order_id)
                )
            else:
                await bot.send_document(
                    admin_id,
                    message.document.file_id,
                    caption=admin_text,
                    reply_markup=get_admin_order_keyboard(order_id)
                )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> <b>Чек получен!</b>\n\nОжидайте подтверждения от администратора.",
        reply_markup=get_main_keyboard()
    )

@router.callback_query(F.data.startswith("approve_order_"))
async def approve_order(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    product = await db.get_product(order['product_id'])
    
    await db.update_order_status(order_id, 'completed')
    
    if product['quantity'] > 0:
        await db.update_product(product['id'], {'quantity': product['quantity'] - 1})
    
    await bot.send_message(
        order['user_id'],
        f"<tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> <b>Ваш заказ #{order_id} подтвержден!</b>\n\nСейчас я отправлю вам товар..."
    )
    
    await send_product_content(order['user_id'], product)
    
    await bot.send_message(
        order['user_id'],
        f"<tg-emoji emoji-id=\"{EMOJI['gift']}\"></tg-emoji> <b>Спасибо за покупку!</b>"
    )
    
    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n<tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> <b>ОДОБРЕНО</b>"
    )
    await callback.answer("Заказ одобрен", show_alert=True)

@router.callback_query(F.data.startswith("reject_order_"))
async def reject_order(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    order = await db.get_order(order_id)
    
    await db.update_order_status(order_id, 'rejected')
    
    await bot.send_message(
        order['user_id'],
        f"<tg-emoji emoji-id=\"{EMOJI['cross']}\"></tg-emoji> <b>Ваш заказ #{order_id} отклонен.</b>\n\nПожалуйста, свяжитесь с поддержкой @VestSupport для уточнения деталей."
    )
    
    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n<tg-emoji emoji-id=\"{EMOJI['cross']}\"></tg-emoji> <b>ОТКЛОНЕНО</b>"
    )
    await callback.answer("Заказ отклонен", show_alert=True)

@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.message.delete()
    await callback.message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['settings']}\"></tg-emoji> Админ-панель</b>",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_products")
async def admin_products_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM products ORDER BY id")
        products = [dict(row) for row in rows]
    
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI['pencil']}\"></tg-emoji> Выберите товар для редактирования:</b>",
        reply_markup=get_admin_products_keyboard(products)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_product_"))
async def edit_product_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    product_id = int(callback.data.split("_")[2])
    product = await db.get_product(product_id)
    
    stock_text = "Неограниченно" if product['quantity'] == -1 else f"{product['quantity']} шт."
    
    detail_text = f"""<b><tg-emoji emoji-id=\"{EMOJI['pencil']}\"></tg-emoji> Редактирование товара</b>

<b>{product['name']}</b>
{product['description']}

Цена: {product['price']} ₽
В наличии: {stock_text}

Выберите поле для редактирования:"""
    
    await callback.message.edit_text(
        detail_text,
        reply_markup=get_edit_fields_keyboard(product_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("edit_field_"))
async def edit_field_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    parts = callback.data.split("_")
    field = parts[2]
    product_id = int(parts[3])
    
    await state.set_state(AddProductStates.waiting_for_name)
    await state.update_data(product_id=product_id, field=field)
    
    field_names = {
        'name': 'название',
        'desc': 'описание',
        'price': 'цену',
        'qty': 'количество (-1 для неограниченного)'
    }
    
    await callback.message.edit_text(
        f"<b>Введите новое {field_names[field]}:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=f"edit_product_{product_id}")]
        ])
    )
    await callback.answer()

@router.message(StateFilter(AddProductStates.waiting_for_name))
async def receive_edit_value(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    product_id = data.get('product_id')
    field = data.get('field')
    
    if not product_id:
        await state.update_data(name=message.text)
        await state.set_state(AddProductStates.waiting_for_description)
        await message.answer(f"<b><tg-emoji emoji-id=\"{EMOJI['write']}\"></tg-emoji> Введите описание товара:</b>")
        return
    
    field_map = {
        'name': 'name',
        'desc': 'description',
        'price': 'price',
        'qty': 'quantity'
    }
    
    value = message.text
    if field == 'price':
        try:
            value = Decimal(value)
        except:
            await message.answer("Неверный формат цены. Попробуйте снова.")
            return
    elif field == 'qty':
        try:
            value = int(value)
        except:
            await message.answer("Неверный формат количества. Попробуйте снова.")
            return
    
    await db.update_product(product_id, {field_map[field]: value})
    await state.clear()
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> <b>Поле обновлено!</b>",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data.startswith("delete_product_"))
async def delete_product_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    product_id = int(callback.data.split("_")[2])
    
    await db.delete_product(product_id)
    
    await callback.message.edit_text(
        f"<tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> <b>Товар удален!</b>"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("add_cat_"))
async def add_product_category(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    category_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=category_id)
    await state.set_state(AddProductStates.waiting_for_name)
    
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI['write']}\"></tg-emoji> Введите название товара:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="cancel_add_product")]
        ])
    )
    await callback.answer()

@router.message(StateFilter(AddProductStates.waiting_for_description))
async def add_product_description(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.update_data(description=message.text)
    await state.set_state(AddProductStates.waiting_for_price)
    
    await message.answer(f"<b><tg-emoji emoji-id=\"{EMOJI['money']}\"></tg-emoji> Введите цену товара (в рублях):</b>")

@router.message(StateFilter(AddProductStates.waiting_for_price))
async def add_product_price(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        price = Decimal(message.text)
    except:
        await message.answer("<b>Неверный формат цены. Введите число:</b>")
        return
    
    await state.update_data(price=price)
    await state.set_state(AddProductStates.waiting_for_quantity)
    
    await message.answer(f"<b><tg-emoji emoji-id=\"{EMOJI['box']}\"></tg-emoji> Введите количество товара (-1 для неограниченного):</b>")

@router.message(StateFilter(AddProductStates.waiting_for_quantity))
async def add_product_quantity(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        quantity = int(message.text)
    except:
        await message.answer("<b>Неверный формат. Введите целое число:</b>")
        return
    
    await state.update_data(quantity=quantity)
    await state.set_state(AddProductStates.waiting_for_content_type)
    
    await message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['file']}\"></tg-emoji> Выберите тип контента товара:</b>",
        reply_markup=get_content_type_keyboard()
    )

@router.callback_query(F.data.startswith("content_"), StateFilter(AddProductStates.waiting_for_content_type))
async def add_product_content_type(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    content_type = callback.data.split("_")[1]
    await state.update_data(content_type=content_type)
    
    if content_type == 'text':
        await state.set_state(AddProductStates.waiting_for_text_content)
        await callback.message.edit_text(
            f"<b><tg-emoji emoji-id=\"{EMOJI['write']}\"></tg-emoji> Введите текст, который получит покупатель:</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Отмена", callback_data="cancel_add_product")]
            ])
        )
    else:
        await state.set_state(AddProductStates.waiting_for_media)
        await callback.message.edit_text(
            f"<b><tg-emoji emoji-id=\"{EMOJI['media']}\"></tg-emoji> Отправьте {content_type} (до 10 штук). Когда закончите, нажмите кнопку Готово</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Готово", callback_data="media_done")],
                [InlineKeyboardButton(text="Отмена", callback_data="cancel_add_product")]
            ])
        )
        await state.update_data(media_files=[])
    
    await callback.answer()

@router.message(StateFilter(AddProductStates.waiting_for_text_content))
async def add_product_text_content(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.update_data(content_data={'text': message.text})
    await state.set_state(AddProductStates.waiting_for_emoji)
    
    await message.answer(f"<b><tg-emoji emoji-id=\"{EMOJI['smile']}\"></tg-emoji> Отправьте ID премиум эмодзи для товара (или 0 если не нужно):</b>")

@router.message(StateFilter(AddProductStates.waiting_for_media), F.photo | F.video | F.document)
async def add_product_media(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    media_files = data.get('media_files', [])
    
    if message.photo:
        file_id = message.photo[-1].file_id
        caption = message.caption
    elif message.video:
        file_id = message.video.file_id
        caption = message.caption
    else:
        file_id = message.document.file_id
        caption = message.caption
    
    if len(media_files) >= 10:
        await message.answer("<b>Максимум 10 файлов. Нажмите Готово</b>")
        return
    
    media_files.append(file_id)
    await state.update_data(media_files=media_files, caption=caption)
    
    await message.answer(f"<b>Файл добавлен ({len(media_files)}/10). Отправьте еще или нажмите Готово</b>")

@router.callback_query(F.data == "media_done", StateFilter(AddProductStates.waiting_for_media))
async def media_done_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    media_files = data.get('media_files', [])
    
    if not media_files:
        await callback.answer("Добавьте хотя бы один файл!", show_alert=True)
        return
    
    await state.update_data(content_data={'file_ids': media_files, 'caption': data.get('caption', '')})
    await state.set_state(AddProductStates.waiting_for_emoji)
    
    await callback.message.edit_text(
        f"<b><tg-emoji emoji-id=\"{EMOJI['smile']}\"></tg-emoji> Отправьте ID премиум эмодзи для товара (или 0 если не нужно):</b>"
    )
    await callback.answer()

@router.message(StateFilter(AddProductStates.waiting_for_emoji))
async def add_product_emoji(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    emoji_id = message.text if message.text != "0" else None
    
    data = await state.get_data()
    
    product_id = await db.create_product({
        'category_id': data['category_id'],
        'name': data['name'],
        'description': data['description'],
        'price': data['price'],
        'quantity': data['quantity'],
        'content_type': data['content_type'],
        'content_data': data['content_data'],
        'emoji_id': emoji_id
    })
    
    await state.clear()
    
    await message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> <b>Товар успешно добавлен!</b> (ID: {product_id})",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data == "cancel_add_product")
async def cancel_add_product(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['cross']}\"></tg-emoji> Добавление товара отменено.</b>",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

@router.message(StateFilter(BroadcastStates.waiting_for_message))
async def broadcast_receive_message(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    broadcast_data = {
        'text': message.html_text if message.text else message.caption,
        'media_type': None,
        'media_file_id': None
    }
    
    if message.photo:
        broadcast_data['media_type'] = 'photo'
        broadcast_data['media_file_id'] = message.photo[-1].file_id
    elif message.video:
        broadcast_data['media_type'] = 'video'
        broadcast_data['media_file_id'] = message.video.file_id
    elif message.document:
        broadcast_data['media_type'] = 'document'
        broadcast_data['media_file_id'] = message.document.file_id
    
    await state.update_data(broadcast=broadcast_data)
    await state.set_state(BroadcastStates.confirm)
    
    preview_text = f"<b><tg-emoji emoji-id=\"{EMOJI['megaphone']}\"></tg-emoji> Предпросмотр рассылки:</b>\n\n" + (broadcast_data['text'] or "[Без текста]")
    
    if broadcast_data['media_type'] == 'photo':
        await message.answer_photo(
            broadcast_data['media_file_id'],
            caption=preview_text,
            reply_markup=get_broadcast_confirm_keyboard()
        )
    elif broadcast_data['media_type'] == 'video':
        await message.answer_video(
            broadcast_data['media_file_id'],
            caption=preview_text,
            reply_markup=get_broadcast_confirm_keyboard()
        )
    elif broadcast_data['media_type'] == 'document':
        await message.answer_document(
            broadcast_data['media_file_id'],
            caption=preview_text,
            reply_markup=get_broadcast_confirm_keyboard()
        )
    else:
        await message.answer(
            preview_text,
            reply_markup=get_broadcast_confirm_keyboard()
        )

@router.callback_query(F.data == "confirm_broadcast", StateFilter(BroadcastStates.confirm))
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    broadcast = data['broadcast']
    
    users = await db.get_all_users()
    
    sent_count = 0
    failed_count = 0
    
    await callback.message.edit_text(f"<tg-emoji emoji-id=\"{EMOJI['loading']}\"></tg-emoji> <b>Рассылка началась...</b>")
    
    for user_id in users:
        try:
            if broadcast['media_type'] == 'photo':
                await bot.send_photo(user_id, broadcast['media_file_id'], caption=broadcast['text'])
            elif broadcast['media_type'] == 'video':
                await bot.send_video(user_id, broadcast['media_file_id'], caption=broadcast['text'])
            elif broadcast['media_type'] == 'document':
                await bot.send_document(user_id, broadcast['media_file_id'], caption=broadcast['text'])
            else:
                await bot.send_message(user_id, broadcast['text'])
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
        
        await asyncio.sleep(0.05)
    
    await state.clear()
    
    await callback.message.answer(
        f"<tg-emoji emoji-id=\"{EMOJI['check']}\"></tg-emoji> <b>Рассылка завершена!</b>\n\n"
        f"Отправлено: {sent_count}\n"
        f"Ошибок: {failed_count}",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data == "cancel_broadcast")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        f"<b><tg-emoji emoji-id=\"{EMOJI['cross']}\"></tg-emoji> Рассылка отменена.</b>",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

# ==================== ЗАПУСК БОТА ====================
async def main():
    await db.connect()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
