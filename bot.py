import asyncio
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ContentType, LabeledPrice,
    PreCheckoutQuery, InputMediaPhoto, InputMediaVideo, InputMediaDocument
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Numeric, Boolean,
    DateTime, ForeignKey, select, update, delete, func
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship, joinedload
import aiohttp

load_dotenv()

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [7973988177]
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "")
SBP_PHONE = "+79818376180"
SBP_BANK = "ЮМАНИ"
CARD_NUMBER = "2204120136042245"
SUPPORT_USERNAME = "@VestSupport"
USDT_RATE = Decimal("90")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== PREMIUM EMOJI IDs ====================
EMOJI = {
    "settings": "5870982283724328568",
    "profile": "5870994129244131212",
    "chart": "5870921681735781843",
    "home": "5873147866364514353",
    "lock": "6037249452824072506",
    "megaphone": "6039422865189638057",
    "check": "5870633910337015697",
    "x": "5870657884844462243",
    "pencil": "5870676941614354370",
    "trash": "5870875489362513438",
    "info": "6028435952299413210",
    "bot": "6030400221232501136",
    "eye": "6037397706505195857",
    "send": "5963103826075456248",
    "download": "6039802767931871481",
    "bell": "6039486778597970865",
    "gift": "6032644646587338669",
    "clock": "5983150113483134607",
    "celebration": "6041731551845159060",
    "wallet": "5769126056262898415",
    "box": "5884479287171485878",
    "crypto": "5260752406890711732",
    "tag": "5886285355279193209",
    "money": "5904462880941545555",
    "code": "5940433880585605708",
    "loading": "5345906554510012647",
    "back": "6037345381550393842",
    "shop": "5774655832226548431",
    "cart": "5774754595229088266",
    "star": "5774728070676486384",
    "rocket": "5774703577138663221",
    "crown": "5774690191920027705",
    "gem": "5774679345232946287",
    "support": "5774328587013654113",
    "question": "5774313083886634093",
    "warning": "5774299306845660225",
    "add": "5774241868474352737",
    "search": "5774205483083891713",
    "refresh": "5345906554510012647",
    "save": "5774136094655064113",
    "heart": "5774087561670166545",
    "bookmark": "5774018945452811297",
    "pin": "5773985325580829691",
    "copy": "5773922509439305425",
    "image": "6035128606563241721",
    "video": "5773638085685020705",
    "play": "5773574092092024977",
    "close": "5870657884844462243",
    "telegram": "5773055512516888409",
    "database": "5771264668704442249",
    "fire": "5774719539799528529"
}

def em(text: str, emoji_id: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{text}</tg-emoji>'

def em_text(emoji_id: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">⚡</tg-emoji>'

# ==================== БАЗА ДАННЫХ ====================
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    balance = Column(Numeric(10, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_banned = Column(Boolean, default=False)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    emoji_id = Column(String, nullable=True)
    order_num = Column(Integer, default=0)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, default=-1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    category = relationship("Category", backref="products")

class ProductContent(Base):
    __tablename__ = "product_contents"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    content_type = Column(String, nullable=False)
    file_id = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    order_num = Column(Integer, default=0)
    product = relationship("Product", backref="contents")

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    amount = Column(Numeric(10, 2), nullable=False)
    payment_method = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    invoice_id = Column(String, nullable=True)
    receipt_file_id = Column(String, nullable=True)
    user = relationship("User", backref="purchases")
    product = relationship("Product", backref="purchases")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        cats = await session.execute(select(Category))
        if not cats.scalars().all():
            categories = [
                Category(name="Боты", emoji_id=EMOJI["bot"], order_num=1),
                Category(name="Интеграции", emoji_id=EMOJI["code"], order_num=2),
                Category(name="Другое", emoji_id=EMOJI["box"], order_num=3)
            ]
            session.add_all(categories)
            await session.commit()

# ==================== СОСТОЯНИЯ FSM ====================
class AddProductStates(StatesGroup):
    waiting_category = State()
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_quantity = State()
    waiting_content = State()
    waiting_edit_field = State()
    waiting_edit_value = State()

class BroadcastStates(StatesGroup):
    waiting_message = State()
    confirm = State()

class PaymentStates(StatesGroup):
    waiting_receipt = State()

class EditProductStates(StatesGroup):
    waiting_product = State()
    waiting_field = State()
    waiting_value = State()

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=f"{em('🛍', EMOJI['shop'])} Купить"),
        KeyboardButton(text=f"{em('👤', EMOJI['profile'])} Профиль")
    )
    builder.row(
        KeyboardButton(text=f"{em('🆘', EMOJI['support'])} Поддержка")
    )
    return builder.as_markup(resize_keyboard=True)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{em('📊', EMOJI['chart'])} Статистика",
            callback_data="admin_stats"
        )],
        [InlineKeyboardButton(
            text=f"{em('📢', EMOJI['megaphone'])} Рассылка",
            callback_data="admin_broadcast"
        )],
        [InlineKeyboardButton(
            text=f"{em('➕', EMOJI['add'])} Добавить товар",
            callback_data="admin_add_product"
        )],
        [InlineKeyboardButton(
            text=f"{em('📦', EMOJI['box'])} Управление товарами",
            callback_data="admin_products"
        )],
        [InlineKeyboardButton(
            text=f"{em('🔙', EMOJI['back'])} Закрыть",
            callback_data="close_panel"
        )]
    ])

def get_categories_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{em('🤖', EMOJI['bot'])} Боты",
            callback_data="category_1"
        )],
        [InlineKeyboardButton(
            text=f"{em('🔗', EMOJI['code'])} Интеграции",
            callback_data="category_2"
        )],
        [InlineKeyboardButton(
            text=f"{em('📦', EMOJI['box'])} Другое",
            callback_data="category_3"
        )],
        [InlineKeyboardButton(
            text=f"{em('🔙', EMOJI['back'])} Назад",
            callback_data="back_to_main"
        )]
    ])

def get_payment_methods_keyboard(purchase_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{em('👾', EMOJI['crypto'])} Crypto Bot",
            callback_data=f"pay_crypto_{purchase_id}"
        )],
        [InlineKeyboardButton(
            text=f"{em('💳', EMOJI['wallet'])} СБП",
            callback_data=f"pay_sbp_{purchase_id}"
        )],
        [InlineKeyboardButton(
            text=f"{em('💳', EMOJI['money'])} Карта",
            callback_data=f"pay_card_{purchase_id}"
        )],
        [InlineKeyboardButton(
            text=f"{em('🔙', EMOJI['back'])} Назад",
            callback_data="back_to_products"
        )]
    ])

def get_confirm_purchase_keyboard(purchase_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{em('✅', EMOJI['check'])} Подтвердить оплату",
            callback_data=f"confirm_payment_{purchase_id}"
        )],
        [InlineKeyboardButton(
            text=f"{em('❌', EMOJI['x'])} Отклонить",
            callback_data=f"reject_payment_{purchase_id}"
        )]
    ])

# ==================== ХЭНДЛЕРЫ ====================
router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = user.scalar()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
            session.add(user)
            await session.commit()
    
    welcome_text = f"""
{em('🎉', EMOJI['celebration'])} Добро пожаловать в <b>Vest Creator</b>!

{em('🤖', EMOJI['bot'])} Магазин телеграм ботов и интеграций
{em('⚡', EMOJI['rocket'])} Качественные решения для вашего бизнеса

{em('👇', EMOJI['arrow_down'])} Используйте меню для навигации:
"""
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@router.message(F.text.contains("Купить"))
async def buy_handler(message: Message):
    await message.answer(
        f"{em('🛍', EMOJI['shop'])} <b>Выберите категорию:</b>",
        reply_markup=get_categories_keyboard()
    )

@router.message(F.text.contains("Профиль"))
async def profile_handler(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = user.scalar()
        if user:
            purchases = await session.execute(
                select(func.count(Purchase.id)).where(
                    Purchase.user_id == message.from_user.id,
                    Purchase.status == "completed"
                )
            )
            total_purchases = purchases.scalar() or 0
            
            profile_text = f"""
{em('👤', EMOJI['profile'])} <b>Профиль</b>

{em('📛', EMOJI['tag'])} Юзернейм: @{message.from_user.username or 'Не указан'}
{em('💰', EMOJI['wallet'])} Баланс: {user.balance} ₽
{em('📦', EMOJI['box'])} Покупок: {total_purchases}
"""
            await message.answer(profile_text)

@router.message(F.text.contains("Поддержка"))
async def support_handler(message: Message):
    support_text = f"""
{em('🆘', EMOJI['support'])} <b>Поддержка</b>

{em('📞', EMOJI['phone'])} Свяжитесь с нами: {SUPPORT_USERNAME}
{em('⏰', EMOJI['clock'])} Время работы: 24/7

{em('❓', EMOJI['question'])} По любым вопросам обращайтесь в поддержку!
"""
    await message.answer(support_text)

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        f"{em('⚙️', EMOJI['settings'])} <b>Админ панель</b>",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    async with AsyncSessionLocal() as session:
        users_count = await session.execute(select(func.count(User.id)))
        users_count = users_count.scalar()
        
        products_count = await session.execute(select(func.count(Product.id)))
        products_count = products_count.scalar()
        
        purchases = await session.execute(
            select(func.sum(Purchase.amount)).where(Purchase.status == "completed")
        )
        total_revenue = purchases.scalar() or 0
        
        pending_purchases = await session.execute(
            select(func.count(Purchase.id)).where(Purchase.status == "pending")
        )
        pending_purchases = pending_purchases.scalar()
        
        stats_text = f"""
{em('📊', EMOJI['chart'])} <b>Статистика</b>

{em('👥', EMOJI['profile'])} Пользователей: {users_count}
{em('📦', EMOJI['box'])} Товаров: {products_count}
{em('💰', EMOJI['money'])} Доход: {total_revenue} ₽
{em('⏳', EMOJI['clock'])} Ожидают оплаты: {pending_purchases}
"""
        await callback.message.edit_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{em('🔄', EMOJI['refresh'])} Обновить",
                    callback_data="admin_stats"
                )],
                [InlineKeyboardButton(
                    text=f"{em('🔙', EMOJI['back'])} Назад",
                    callback_data="back_to_admin"
                )]
            ])
        )

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    await callback.message.edit_text(
        f"{em('📢', EMOJI['megaphone'])} <b>Отправьте сообщение для рассылки:</b>\n\n"
        f"{em('ℹ️', EMOJI['info'])} Поддерживается текст, фото, видео, файлы",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} Отмена",
                callback_data="back_to_admin"
            )]
        ])
    )
    await state.set_state(BroadcastStates.waiting_message)

@router.message(BroadcastStates.waiting_message)
async def broadcast_message_received(message: Message, state: FSMContext, bot: Bot):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.update_data(
        message_type="text" if message.text else 
        "photo" if message.photo else
        "video" if message.video else
        "document" if message.document else "text",
        content=message.model_dump()
    )
    
    await message.answer(
        f"{em('✅', EMOJI['check'])} Сообщение получено. Отправить рассылку?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('✅', EMOJI['check'])} Отправить",
                callback_data="confirm_broadcast"
            )],
            [InlineKeyboardButton(
                text=f"{em('❌', EMOJI['x'])} Отмена",
                callback_data="back_to_admin"
            )]
        ])
    )
    await state.set_state(BroadcastStates.confirm)

@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        users = await session.execute(select(User.telegram_id))
        users = users.scalars().all()
    
    success = 0
    failed = 0
    
    for user_id in users:
        try:
            if data.get("message_type") == "text":
                await bot.send_message(user_id, data["content"]["text"])
            elif data.get("message_type") == "photo":
                await bot.send_photo(user_id, data["content"]["photo"][-1].file_id,
                                   caption=data["content"].get("caption"))
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)
    
    await callback.message.edit_text(
        f"{em('📢', EMOJI['megaphone'])} <b>Рассылка завершена</b>\n\n"
        f"{em('✅', EMOJI['check'])} Успешно: {success}\n"
        f"{em('❌', EMOJI['x'])} Неудачно: {failed}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} Назад",
                callback_data="back_to_admin"
            )]
        ])
    )
    await state.clear()

@router.callback_query(F.data.startswith("category_"))
async def show_products(callback: CallbackQuery):
    category_id = int(callback.data.split("_")[1])
    
    async with AsyncSessionLocal() as session:
        products = await session.execute(
            select(Product)
            .where(Product.category_id == category_id, Product.is_active == True)
            .options(joinedload(Product.category))
        )
        products = products.scalars().all()
    
    if not products:
        await callback.message.edit_text(
            f"{em('📦', EMOJI['box'])} <b>Товаров пока нет</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{em('🔙', EMOJI['back'])} Назад",
                    callback_data="back_to_categories"
                )]
            ])
        )
        return
    
    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(
            text=f"{product.name} - {product.price} ₽",
            callback_data=f"product_{product.id}"
        )])
    keyboard.append([InlineKeyboardButton(
        text=f"{em('🔙', EMOJI['back'])} Назад",
        callback_data="back_to_categories"
    )])
    
    await callback.message.edit_text(
        f"{em('🛍', EMOJI['shop'])} <b>Товары:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    
    async with AsyncSessionLocal() as session:
        product = await session.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(joinedload(Product.category))
        )
        product = product.scalar()
    
    if not product:
        await callback.answer("Товар не найден")
        return
    
    in_stock = "В наличии" if product.quantity == -1 or product.quantity > 0 else "Нет в наличии"
    
    text = f"""
{em('📦', EMOJI['box'])} <b>{product.name}</b>

{em('📝', EMOJI['pencil'])} {product.description or 'Описание отсутствует'}

{em('💰', EMOJI['money'])} <b>Цена:</b> {product.price} ₽
{em('📊', EMOJI['chart'])} <b>В наличии:</b> {in_stock}
"""
    
    keyboard = [[InlineKeyboardButton(
        text=f"{em('🛒', EMOJI['cart'])} Купить",
        callback_data=f"buy_{product.id}"
    )]]
    keyboard.append([InlineKeyboardButton(
        text=f"{em('🔙', EMOJI['back'])} Назад",
        callback_data=f"category_{product.category_id}"
    )])
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    
    async with AsyncSessionLocal() as session:
        product = await session.execute(select(Product).where(Product.id == product_id))
        product = product.scalar()
        
        if not product or not product.is_active:
            await callback.answer("Товар недоступен")
            return
        
        if product.quantity != -1 and product.quantity <= 0:
            await callback.answer("Товар закончился")
            return
        
        user = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user.scalar()
        
        if user.balance >= product.price:
            # Покупка с баланса
            user.balance -= product.price
            if product.quantity > 0:
                product.quantity -= 1
            
            purchase = Purchase(
                user_id=user.telegram_id,
                product_id=product.id,
                amount=product.price,
                payment_method="balance",
                status="completed"
            )
            session.add(purchase)
            await session.commit()
            
            await deliver_product(callback.message, product, user.telegram_id)
            await callback.message.edit_text(
                f"{em('✅', EMOJI['check'])} <b>Покупка успешна!</b>\n\n"
                f"Товар: {product.name}\n"
                f"Списано с баланса: {product.price} ₽"
            )
        else:
            purchase = Purchase(
                user_id=callback.from_user.id,
                product_id=product.id,
                amount=product.price,
                payment_method="pending",
                status="pending"
            )
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)
            
            await callback.message.edit_text(
                f"{em('💳', EMOJI['wallet'])} <b>Выберите способ оплаты:</b>\n\n"
                f"Товар: {product.name}\n"
                f"Сумма: {product.price} ₽",
                reply_markup=get_payment_methods_keyboard(purchase.id)
            )

@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(callback: CallbackQuery, bot: Bot):
    purchase_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        purchase = await session.execute(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(joinedload(Purchase.product))
        )
        purchase = purchase.scalar()
        
        if not purchase:
            await callback.answer("Заказ не найден")
            return
        
        amount_usdt = purchase.amount / USDT_RATE
        
        # Создание счёта в Crypto Bot
        async with aiohttp.ClientSession() as http_session:
            headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
            data = {
                "asset": "USDT",
                "amount": str(amount_usdt),
                "description": f"Покупка {purchase.product.name}",
                "hidden_message": f"purchase_{purchase.id}",
                "expires_in": 3600
            }
            async with http_session.get(
                "https://pay.crypt.bot/api/createInvoice",
                headers=headers,
                params=data
            ) as resp:
                result = await resp.json()
                
                if result.get("ok"):
                    invoice = result["result"]
                    purchase.payment_method = "crypto"
                    purchase.invoice_id = invoice["invoice_id"]
                    await session.commit()
                    
                    await callback.message.edit_text(
                        f"{em('👾', EMOJI['crypto'])} <b>Счёт создан</b>\n\n"
                        f"Сумма: {amount_usdt} USDT\n"
                        f"{em('🔗', EMOJI['link'])} <a href='{invoice['pay_url']}'>Ссылка на оплату</a>\n\n"
                        f"{em('⏰', EMOJI['clock'])} Счёт действителен 1 час",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(
                                text=f"{em('✅', EMOJI['check'])} Проверить оплату",
                                callback_data=f"check_crypto_{purchase.id}"
                            )],
                            [InlineKeyboardButton(
                                text=f"{em('🔙', EMOJI['back'])} Назад",
                                callback_data=f"buy_{purchase.product_id}"
                            )]
                        ])
                    )
                else:
                    await callback.answer("Ошибка создания счёта", show_alert=True)

@router.callback_query(F.data.startswith("pay_sbp_"))
async def pay_sbp(callback: CallbackQuery):
    purchase_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        purchase = await session.execute(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(joinedload(Purchase.product))
        )
        purchase = purchase.scalar()
        
        purchase.payment_method = "sbp"
        await session.commit()
        
        text = f"""
{em('💳', EMOJI['wallet'])} <b>Оплата через СБП</b>

{em('📱', EMOJI['phone'])} <b>Номер телефона:</b> {SBP_PHONE}
{em('🏦', EMOJI['home'])} <b>Банк:</b> {SBP_BANK}
{em('💰', EMOJI['money'])} <b>Сумма:</b> {purchase.amount} ₽

{em('📎', EMOJI['paperclip'])} После оплаты отправьте чек (скриншот) в этот чат.
"""
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{em('✅', EMOJI['check'])} Я оплатил",
                    callback_data=f"upload_receipt_{purchase.id}"
                )],
                [InlineKeyboardButton(
                    text=f"{em('🔙', EMOJI['back'])} Назад",
                    callback_data=f"buy_{purchase.product_id}"
                )]
            ])
        )

@router.callback_query(F.data.startswith("pay_card_"))
async def pay_card(callback: CallbackQuery):
    purchase_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        purchase = await session.execute(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(joinedload(Purchase.product))
        )
        purchase = purchase.scalar()
        
        purchase.payment_method = "card"
        await session.commit()
        
        text = f"""
{em('💳', EMOJI['wallet'])} <b>Оплата картой</b>

{em('💳', EMOJI['money'])} <b>Номер карты:</b> {CARD_NUMBER}
{em('💰', EMOJI['money'])} <b>Сумма:</b> {purchase.amount} ₽

{em('📎', EMOJI['paperclip'])} После оплаты отправьте чек (скриншот) в этот чат.
"""
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{em('✅', EMOJI['check'])} Я оплатил",
                    callback_data=f"upload_receipt_{purchase.id}"
                )],
                [InlineKeyboardButton(
                    text=f"{em('🔙', EMOJI['back'])} Назад",
                    callback_data=f"buy_{purchase.product_id}"
                )]
            ])
        )

@router.callback_query(F.data.startswith("upload_receipt_"))
async def upload_receipt(callback: CallbackQuery, state: FSMContext):
    purchase_id = int(callback.data.split("_")[2])
    await state.update_data(purchase_id=purchase_id)
    await state.set_state(PaymentStates.waiting_receipt)
    
    await callback.message.edit_text(
        f"{em('📎', EMOJI['paperclip'])} <b>Отправьте фото чека:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} Отмена",
                callback_data=f"buy_0"
            )]
        ])
    )

@router.message(PaymentStates.waiting_receipt, F.photo)
async def receipt_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    purchase_id = data.get("purchase_id")
    
    async with AsyncSessionLocal() as session:
        purchase = await session.execute(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(joinedload(Purchase.product), joinedload(Purchase.user))
        )
        purchase = purchase.scalar()
        
        if purchase:
            purchase.receipt_file_id = message.photo[-1].file_id
            await session.commit()
            
            # Отправка админам
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_photo(
                        admin_id,
                        message.photo[-1].file_id,
                        caption=f"""
{em('💰', EMOJI['money'])} <b>Новая оплата</b>

{em('👤', EMOJI['profile'])} Пользователь: @{purchase.user.username or purchase.user.telegram_id}
{em('📦', EMOJI['box'])} Товар: {purchase.product.name}
{em('💳', EMOJI['wallet'])} Сумма: {purchase.amount} ₽
{em('💵', EMOJI['money'])} Метод: {purchase.payment_method}
""",
                        reply_markup=get_confirm_purchase_keyboard(purchase.id)
                    )
                except:
                    pass
            
            await message.answer(
                f"{em('✅', EMOJI['check'])} <b>Чек отправлен на проверку!</b>\n\n"
                f"{em('⏰', EMOJI['clock'])} Ожидайте подтверждения от администратора."
            )
    
    await state.clear()

@router.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    purchase_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        purchase = await session.execute(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(joinedload(Purchase.product), joinedload(Purchase.user))
        )
        purchase = purchase.scalar()
        
        if purchase and purchase.status == "pending":
            purchase.status = "completed"
            
            if purchase.product.quantity > 0:
                purchase.product.quantity -= 1
            
            await session.commit()
            
            # Выдача товара
            try:
                await deliver_product_to_user(bot, purchase.user.telegram_id, purchase.product)
                await bot.send_message(
                    purchase.user.telegram_id,
                    f"{em('✅', EMOJI['check'])} <b>Оплата подтверждена!</b>\n\n"
                    f"Товар: {purchase.product.name}\n"
                    f"Товар выдан выше."
                )
            except:
                pass
            
            await callback.message.edit_caption(
                callback.message.caption + f"\n\n{em('✅', EMOJI['check'])} <b>Подтверждено</b>"
            )
            await callback.answer("✅ Оплата подтверждена")

@router.callback_query(F.data.startswith("reject_payment_"))
async def reject_payment(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    purchase_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        purchase = await session.execute(
            select(Purchase)
            .where(Purchase.id == purchase_id)
            .options(joinedload(Purchase.user))
        )
        purchase = purchase.scalar()
        
        if purchase and purchase.status == "pending":
            purchase.status = "rejected"
            await session.commit()
            
            try:
                await bot.send_message(
                    purchase.user.telegram_id,
                    f"{em('❌', EMOJI['x'])} <b>Оплата отклонена</b>\n\n"
                    f"Пожалуйста, свяжитесь с поддержкой: {SUPPORT_USERNAME}"
                )
            except:
                pass
            
            await callback.message.edit_caption(
                callback.message.caption + f"\n\n{em('❌', EMOJI['x'])} <b>Отклонено</b>"
            )
            await callback.answer("❌ Оплата отклонена")

async def deliver_product(message: Message, product: Product, user_id: int):
    """Выдача товара после покупки"""
    async with AsyncSessionLocal() as session:
        contents = await session.execute(
            select(ProductContent)
            .where(ProductContent.product_id == product.id)
            .order_by(ProductContent.order_num)
        )
        contents = contents.scalars().all()
        
        for content in contents:
            if content.content_type == "text":
                await message.answer(content.text)
            elif content.content_type == "photo":
                await message.answer_photo(content.file_id)
            elif content.content_type == "video":
                await message.answer_video(content.file_id)
            elif content.content_type == "document":
                await message.answer_document(content.file_id)

async def deliver_product_to_user(bot: Bot, user_id: int, product: Product):
    """Выдача товара пользователю по ID"""
    async with AsyncSessionLocal() as session:
        contents = await session.execute(
            select(ProductContent)
            .where(ProductContent.product_id == product.id)
            .order_by(ProductContent.order_num)
        )
        contents = contents.scalars().all()
        
        for content in contents:
            if content.content_type == "text":
                await bot.send_message(user_id, content.text)
            elif content.content_type == "photo":
                await bot.send_photo(user_id, content.file_id)
            elif content.content_type == "video":
                await bot.send_video(user_id, content.file_id)
            elif content.content_type == "document":
                await bot.send_document(user_id, content.file_id)

@router.callback_query(F.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    async with AsyncSessionLocal() as session:
        categories = await session.execute(select(Category).order_by(Category.order_num))
        categories = categories.scalars().all()
    
    keyboard = []
    for cat in categories:
        emoji_text = em("📁", cat.emoji_id) if cat.emoji_id else "📁"
        keyboard.append([InlineKeyboardButton(
            text=f"{emoji_text} {cat.name}",
            callback_data=f"add_cat_{cat.id}"
        )])
    keyboard.append([InlineKeyboardButton(
        text=f"{em('🔙', EMOJI['back'])} Назад",
        callback_data="back_to_admin"
    )])
    
    await callback.message.edit_text(
        f"{em('➕', EMOJI['add'])} <b>Выберите категорию:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("add_cat_"))
async def add_product_category_selected(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=cat_id)
    await state.set_state(AddProductStates.waiting_name)
    
    await callback.message.edit_text(
        f"{em('📝', EMOJI['pencil'])} <b>Введите название товара:</b>\n\n"
        f"{em('ℹ️', EMOJI['info'])} Можно использовать premium эмодзи",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} Отмена",
                callback_data="back_to_admin"
            )]
        ])
    )

@router.message(AddProductStates.waiting_name)
async def add_product_name(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.update_data(name=message.html_text)
    await state.set_state(AddProductStates.waiting_description)
    
    await message.answer(
        f"{em('📄', EMOJI['pencil'])} <b>Введите описание товара:</b>\n\n"
        f"{em('ℹ️', EMOJI['info'])} Можно использовать premium эмодзи\n"
        f"Или отправьте '-' чтобы пропустить",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} Отмена",
                callback_data="back_to_admin"
            )]
        ])
    )

@router.message(AddProductStates.waiting_description)
async def add_product_description(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    desc = None if message.text == "-" else message.html_text
    await state.update_data(description=desc)
    await state.set_state(AddProductStates.waiting_price)
    
    await message.answer(
        f"{em('💰', EMOJI['money'])} <b>Введите цену товара (в рублях):</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} Отмена",
                callback_data="back_to_admin"
            )]
        ])
    )

@router.message(AddProductStates.waiting_price)
async def add_product_price(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        price = Decimal(message.text.replace(",", "."))
        if price <= 0:
            raise ValueError
    except:
        await message.answer(f"{em('❌', EMOJI['x'])} Введите корректную цену (число > 0)")
        return
    
    await state.update_data(price=price)
    await state.set_state(AddProductStates.waiting_quantity)
    
    await message.answer(
        f"{em('📦', EMOJI['box'])} <b>Введите количество товара:</b>\n\n"
        f"{em('ℹ️', EMOJI['info'])} -1 для бесконечного количества",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} Отмена",
                callback_data="back_to_admin"
            )]
        ])
    )

@router.message(AddProductStates.waiting_quantity)
async def add_product_quantity(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        quantity = int(message.text)
    except:
        await message.answer(f"{em('❌', EMOJI['x'])} Введите целое число")
        return
    
    await state.update_data(quantity=quantity)
    await state.set_state(AddProductStates.waiting_content)
    
    await message.answer(
        f"{em('📎', EMOJI['paperclip'])} <b>Отправьте содержимое товара:</b>\n\n"
        f"{em('ℹ️', EMOJI['info'])} Можно отправить текст, фото, видео, файл\n"
        f"Отправляйте по одному, для завершения нажмите кнопку ниже",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('✅', EMOJI['check'])} Завершить",
                callback_data="finish_adding_content"
            )],
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} Отмена",
                callback_data="back_to_admin"
            )]
        ])
    )

@router.message(AddProductStates.waiting_content)
async def add_product_content(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    contents = data.get("contents", [])
    
    content_item = {"order_num": len(contents)}
    
    if message.text:
        content_item["type"] = "text"
        content_item["text"] = message.html_text
    elif message.photo:
        content_item["type"] = "photo"
        content_item["file_id"] = message.photo[-1].file_id
        content_item["caption"] = message.caption
    elif message.video:
        content_item["type"] = "video"
        content_item["file_id"] = message.video.file_id
        content_item["caption"] = message.caption
    elif message.document:
        content_item["type"] = "document"
        content_item["file_id"] = message.document.file_id
        content_item["caption"] = message.caption
    else:
        await message.answer(f"{em('❌', EMOJI['x'])} Неподдерживаемый тип контента")
        return
    
    contents.append(content_item)
    await state.update_data(contents=contents)
    
    await message.answer(
        f"{em('✅', EMOJI['check'])} Контент #{len(contents)} добавлен\n"
        f"{em('📎', EMOJI['paperclip'])} Отправьте ещё или нажмите 'Завершить'"
    )

@router.callback_query(F.data == "finish_adding_content")
async def finish_adding_content(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    contents = data.get("contents", [])
    
    if not contents:
        await callback.answer("Добавьте хотя бы один элемент контента", show_alert=True)
        return
    
    async with AsyncSessionLocal() as session:
        product = Product(
            category_id=data["category_id"],
            name=data["name"],
            description=data.get("description"),
            price=data["price"],
            quantity=data["quantity"]
        )
        session.add(product)
        await session.flush()
        
        for item in contents:
            content = ProductContent(
                product_id=product.id,
                content_type=item["type"],
                file_id=item.get("file_id"),
                text=item.get("text"),
                order_num=item["order_num"]
            )
            session.add(content)
        
        await session.commit()
    
    await callback.message.edit_text(
        f"{em('✅', EMOJI['check'])} <b>Товар успешно добавлен!</b>\n\n"
        f"Название: {data['name']}\n"
        f"Цена: {data['price']} ₽",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{em('🔙', EMOJI['back'])} В админ панель",
                callback_data="back_to_admin"
            )]
        ])
    )
    await state.clear()

@router.callback_query(F.data == "admin_products")
async def admin_products_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    async with AsyncSessionLocal() as session:
        products = await session.execute(
            select(Product)
            .options(joinedload(Product.category))
            .order_by(Product.created_at.desc())
            .limit(20)
        )
        products = products.scalars().all()
    
    if not products:
        await callback.message.edit_text(
            f"{em('📦', EMOJI['box'])} <b>Товаров пока нет</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{em('🔙', EMOJI['back'])} Назад",
                    callback_data="back_to_admin"
                )]
            ])
        )
        return
    
    keyboard = []
    for p in products:
        status = f"{em('✅', EMOJI['check'])}" if p.is_active else f"{em('❌', EMOJI['x'])}"
        keyboard.append([InlineKeyboardButton(
            text=f"{status} {p.name} - {p.price} ₽",
            callback_data=f"manage_product_{p.id}"
        )])
    keyboard.append([InlineKeyboardButton(
        text=f"{em('🔙', EMOJI['back'])} Назад",
        callback_data="back_to_admin"
    )])
    
    await callback.message.edit_text(
        f"{em('📦', EMOJI['box'])} <b>Управление товарами:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("manage_product_"))
async def manage_product(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    product_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        product = await session.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(joinedload(Product.category))
        )
        product = product.scalar()
    
    if not product:
        await callback.answer("Товар не найден")
        return
    
    status = "Активен" if product.is_active else "Неактивен"
    quantity = "∞" if product.quantity == -1 else product.quantity
    
    text = f"""
{em('📦', EMOJI['box'])} <b>{product.name}</b>

{em('🏷', EMOJI['tag'])} Категория: {product.category.name}
{em('💰', EMOJI['money'])} Цена: {product.price} ₽
{em('📊', EMOJI['chart'])} Количество: {quantity}
{em('👁', EMOJI['eye'])} Статус: {status}
"""
    
    keyboard = [
        [InlineKeyboardButton(
            text=f"{em('✏️', EMOJI['pencil'])} Редактировать",
            callback_data=f"edit_product_{product.id}"
        )],
        [InlineKeyboardButton(
            text=f"{em('🔄', EMOJI['refresh'])} Переключить статус",
            callback_data=f"toggle_product_{product.id}"
        )],
        [InlineKeyboardButton(
            text=f"{em('🗑', EMOJI['trash'])} Удалить",
            callback_data=f"delete_product_{product.id}"
        )],
        [InlineKeyboardButton(
            text=f"{em('🔙', EMOJI['back'])} Назад",
            callback_data="admin_products"
        )]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("toggle_product_"))
async def toggle_product(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    product_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        product = await session.execute(select(Product).where(Product.id == product_id))
        product = product.scalar()
        if product:
            product.is_active = not product.is_active
            await session.commit()
            await callback.answer(f"Статус изменён на {'активен' if product.is_active else 'неактивен'}")
            await manage_product(callback)

@router.callback_query(F.data.startswith("delete_product_"))
async def delete_product(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    
    product_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        await session.execute(delete(ProductContent).where(ProductContent.product_id == product_id))
        await session.execute(delete(Product).where(Product.id == product_id))
        await session.commit()
    
    await callback.answer("Товар удалён")
    await admin_products_list(callback)

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        f"{em('🏠', EMOJI['home'])} <b>Главное меню</b>",
        reply_markup=get_main_keyboard()
    )

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    await callback.message.edit_text(
        f"{em('🛍', EMOJI['shop'])} <b>Выберите категорию:</b>",
        reply_markup=get_categories_keyboard()
    )

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.edit_text(
        f"{em('⚙️', EMOJI['settings'])} <b>Админ панель</b>",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(F.data == "close_panel")
async def close_panel(callback: CallbackQuery):
    await callback.message.delete()

@router.callback_query(F.data == "back_to_products")
async def back_to_products(callback: CallbackQuery):
    await show_products(callback)

# ==================== ЗАПУСК ====================
async def main():
    await init_db()
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
