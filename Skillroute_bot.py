"""
SkillRoute Bot — Waitlist + CustDev заглушка
Бот собирает сегмент пользователя, тему обучения, боли и выдаёт промокод.
Данные сохраняются в SQLite.

Деплой: Railway / Render / VPS
Стек: aiogram 3, SQLite

Переменные окружения:
  BOT_TOKEN=your_telegram_bot_token
  ADMIN_ID=your_telegram_user_id
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ── Config ──────────────────────────────────────────────

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
DB_PATH = "skillroute_waitlist.db"
PROMO_CODE = "SKILL50"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Database ────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            tg_username TEXT,
            full_name TEXT,
            segment TEXT,
            topic TEXT,
            level TEXT,
            time_per_day TEXT,
            pain TEXT,
            current_learning TEXT,
            price_ready TEXT,
            dream_topic TEXT,
            is_test INTEGER DEFAULT 0,
            registered_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_user(data: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO users 
        (tg_id, tg_username, full_name, segment, topic, level, 
         time_per_day, pain, current_learning, price_ready, dream_topic, is_test, registered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["tg_id"], data.get("tg_username"), data.get("full_name"),
        data.get("segment"), data.get("topic"), data.get("level"),
        data.get("time_per_day"), data.get("pain"), data.get("current_learning"),
        data.get("price_ready"), data.get("dream_topic"), data.get("is_test", 0),
        datetime.now().isoformat()
    ))
    conn.commit()
    # Считаем только реальных (не тестовых)
    count = conn.execute("SELECT COUNT(*) FROM users WHERE is_test = 0").fetchone()[0]
    conn.close()
    return count


def get_real_count():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM users WHERE is_test = 0").fetchone()[0]
    conn.close()
    return count


def get_stats():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    real = conn.execute("SELECT COUNT(*) FROM users WHERE is_test = 0").fetchone()[0]
    test = conn.execute("SELECT COUNT(*) FROM users WHERE is_test = 1").fetchone()[0]
    segments = conn.execute(
        "SELECT segment, COUNT(*) FROM users WHERE is_test = 0 GROUP BY segment"
    ).fetchall()
    topics = conn.execute(
        "SELECT topic, COUNT(*) FROM users WHERE is_test = 0 GROUP BY topic ORDER BY COUNT(*) DESC"
    ).fetchall()
    pains = conn.execute(
        "SELECT pain, COUNT(*) FROM users WHERE is_test = 0 GROUP BY pain ORDER BY COUNT(*) DESC"
    ).fetchall()
    prices = conn.execute(
        "SELECT price_ready, COUNT(*) FROM users WHERE is_test = 0 GROUP BY price_ready ORDER BY COUNT(*) DESC"
    ).fetchall()
    conn.close()
    return total, real, test, segments, topics, pains, prices


def reset_test_users():
    """Удаляет всех тестовых пользователей"""
    conn = sqlite3.connect(DB_PATH)
    deleted = conn.execute("DELETE FROM users WHERE is_test = 1").rowcount
    conn.commit()
    conn.close()
    return deleted


def reset_all_users():
    """Удаляет ВСЕХ пользователей (полный сброс)"""
    conn = sqlite3.connect(DB_PATH)
    deleted = conn.execute("DELETE FROM users").rowcount
    conn.commit()
    conn.close()
    return deleted


def mark_as_test(tg_id: int):
    """Помечает пользователя как тестового"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET is_test = 1 WHERE tg_id = ?", (tg_id,))
    conn.commit()
    conn.close()


# ── States ──────────────────────────────────────────────

class Survey(StatesGroup):
    segment = State()
    topic = State()
    level = State()
    time_per_day = State()
    pain = State()
    current_learning = State()
    price_ready = State()
    dream_topic = State()


# ── Keyboards ───────────────────────────────────────────

def kb_segment():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 Наёмный сотрудник", callback_data="seg_employee")],
        [InlineKeyboardButton(text="🚀 Предприниматель", callback_data="seg_entrepreneur")],
        [InlineKeyboardButton(text="🎓 Студент", callback_data="seg_student")],
        [InlineKeyboardButton(text="⚡ Совмещаю работу и учёбу", callback_data="seg_hybrid")],
    ])

def kb_topic():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Маркетинг / SMM", callback_data="top_marketing")],
        [InlineKeyboardButton(text="🎨 Дизайн", callback_data="top_design")],
        [InlineKeyboardButton(text="💰 Финансы / Инвестиции", callback_data="top_finance")],
        [InlineKeyboardButton(text="📊 Бизнес / Управление", callback_data="top_business")],
        [InlineKeyboardButton(text="💻 IT / Программирование", callback_data="top_it")],
        [InlineKeyboardButton(text="🔤 Иностранные языки", callback_data="top_languages")],
        [InlineKeyboardButton(text="✍️ Другое", callback_data="top_other")],
    ])

def kb_level():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌱 С нуля", callback_data="lvl_zero")],
        [InlineKeyboardButton(text="📗 Знаю базу, хочу углубиться", callback_data="lvl_base")],
        [InlineKeyboardButton(text="📘 Продвинутый, хочу экспертизу", callback_data="lvl_advanced")],
    ])

def kb_time():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ 30 минут в день", callback_data="time_30")],
        [InlineKeyboardButton(text="⏱ 1 час в день", callback_data="time_60")],
        [InlineKeyboardButton(text="⏱ 2+ часа в день", callback_data="time_120")],
        [InlineKeyboardButton(text="📅 Только по выходным", callback_data="time_weekend")],
    ])

def kb_pain():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌊 Слишком много информации", callback_data="pain_overload")],
        [InlineKeyboardButton(text="❓ Не знаю с чего начать", callback_data="pain_start")],
        [InlineKeyboardButton(text="😴 Начинаю и бросаю", callback_data="pain_dropout")],
        [InlineKeyboardButton(text="💸 Курсы слишком дорогие", callback_data="pain_expensive")],
        [InlineKeyboardButton(text="⏰ Нет времени", callback_data="pain_time")],
        [InlineKeyboardButton(text="🤷 Нет чёткой цели", callback_data="pain_nogoal")],
    ])

def kb_current_learning():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 YouTube", callback_data="cur_youtube")],
        [InlineKeyboardButton(text="📚 Платные курсы", callback_data="cur_courses")],
        [InlineKeyboardButton(text="📖 Статьи и блоги", callback_data="cur_articles")],
        [InlineKeyboardButton(text="🤖 ChatGPT / нейросети", callback_data="cur_ai")],
        [InlineKeyboardButton(text="🎓 Бесплатные курсы (Stepik и т.д.)", callback_data="cur_free")],
        [InlineKeyboardButton(text="🚫 Сейчас не учусь", callback_data="cur_nothing")],
    ])

def kb_price():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 Только бесплатно", callback_data="price_free")],
        [InlineKeyboardButton(text="💳 До 299₽/мес", callback_data="price_299")],
        [InlineKeyboardButton(text="💳 До 499₽/мес", callback_data="price_499")],
        [InlineKeyboardButton(text="💳 До 999₽/мес", callback_data="price_999")],
    ])

def kb_reset_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Удалить только тестовых", callback_data="reset_test")],
        [InlineKeyboardButton(text="🔥 Удалить ВСЕХ (полный сброс)", callback_data="reset_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="reset_cancel")],
    ])


# ── Labels ──────────────────────────────────────────────

LABELS = {
    "seg_employee": "Наёмный сотрудник",
    "seg_entrepreneur": "Предприниматель",
    "seg_student": "Студент",
    "seg_hybrid": "Совмещает работу и учёбу",
    "top_marketing": "Маркетинг / SMM",
    "top_design": "Дизайн",
    "top_finance": "Финансы / Инвестиции",
    "top_business": "Бизнес / Управление",
    "top_it": "IT / Программирование",
    "top_languages": "Иностранные языки",
    "top_other": "Другое",
    "lvl_zero": "С нуля",
    "lvl_base": "Базовый",
    "lvl_advanced": "Продвинутый",
    "time_30": "30 мин/день",
    "time_60": "1 час/день",
    "time_120": "2+ часа/день",
    "time_weekend": "По выходным",
    "pain_overload": "Слишком много информации",
    "pain_start": "Не знаю с чего начать",
    "pain_dropout": "Начинаю и бросаю",
    "pain_expensive": "Курсы дорогие",
    "pain_time": "Нет времени",
    "pain_nogoal": "Нет чёткой цели",
    "cur_youtube": "YouTube",
    "cur_courses": "Платные курсы",
    "cur_articles": "Статьи и блоги",
    "cur_ai": "ChatGPT / нейросети",
    "cur_free": "Бесплатные курсы",
    "cur_nothing": "Не учусь",
    "price_free": "Только бесплатно",
    "price_299": "До 299₽/мес",
    "price_499": "До 499₽/мес",
    "price_999": "До 999₽/мес",
}

# ── Helpers ─────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return ADMIN_ID and str(user_id) == str(ADMIN_ID)


# ── Router ──────────────────────────────────────────────

router = Router()


# ── /start ─────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    # Если админ отправляет /start test — помечаем как тестового
    is_test = 0
    if message.text and "test" in message.text.lower() and is_admin(message.from_user.id):
        is_test = 1

    await state.update_data(
        tg_id=message.from_user.id,
        tg_username=message.from_user.username,
        full_name=message.from_user.full_name,
        is_test=is_test,
    )

    welcome = (
        "👋 Привет! Я <b>SkillRoute</b> — AI-бот, который составит тебе "
        "персональный план обучения из лучших бесплатных ресурсов.\n\n"
        "🚧 Сейчас я в разработке. Ответь на 8 коротких вопросов (1 минута) "
        "— и получи промокод <b>SKILL50</b> на скидку 50% в первый месяц.\n\n"
        'Нажимая кнопку ниже, ты соглашаешься с '
        '<a href="https://skillroute.vercel.app/privacy">политикой конфиденциальности</a>.'
    )

    if is_test:
        welcome = "🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b> — ответы не считаются в счётчик\n\n" + welcome

    await message.answer(welcome, parse_mode="HTML", disable_web_page_preview=True)
    await message.answer("❶ <b>Кто ты?</b>", parse_mode="HTML", reply_markup=kb_segment())
    await state.set_state(Survey.segment)


# ── Survey Steps ───────────────────────────────────────

@router.callback_query(Survey.segment, F.data.startswith("seg_"))
async def on_segment(cb: CallbackQuery, state: FSMContext):
    await state.update_data(segment=LABELS[cb.data])
    await cb.message.edit_text(f"✅ {LABELS[cb.data]}")
    await cb.message.answer("❷ <b>Какую тему хочешь изучить?</b>", parse_mode="HTML", reply_markup=kb_topic())
    await state.set_state(Survey.topic)


@router.callback_query(Survey.topic, F.data.startswith("top_"))
async def on_topic(cb: CallbackQuery, state: FSMContext):
    await state.update_data(topic=LABELS[cb.data])
    await cb.message.edit_text(f"✅ {LABELS[cb.data]}")
    await cb.message.answer("❸ <b>Какой у тебя уровень в этой теме?</b>", parse_mode="HTML", reply_markup=kb_level())
    await state.set_state(Survey.level)


@router.callback_query(Survey.level, F.data.startswith("lvl_"))
async def on_level(cb: CallbackQuery, state: FSMContext):
    await state.update_data(level=LABELS[cb.data])
    await cb.message.edit_text(f"✅ {LABELS[cb.data]}")
    await cb.message.answer("❹ <b>Сколько времени в день готов уделять?</b>", parse_mode="HTML", reply_markup=kb_time())
    await state.set_state(Survey.time_per_day)


@router.callback_query(Survey.time_per_day, F.data.startswith("time_"))
async def on_time(cb: CallbackQuery, state: FSMContext):
    await state.update_data(time_per_day=LABELS[cb.data])
    await cb.message.edit_text(f"✅ {LABELS[cb.data]}")
    await cb.message.answer("❺ <b>Что больше всего мешает учиться?</b>", parse_mode="HTML", reply_markup=kb_pain())
    await state.set_state(Survey.pain)


@router.callback_query(Survey.pain, F.data.startswith("pain_"))
async def on_pain(cb: CallbackQuery, state: FSMContext):
    await state.update_data(pain=LABELS[cb.data])
    await cb.message.edit_text(f"✅ {LABELS[cb.data]}")
    await cb.message.answer("❻ <b>Как ты сейчас учишься?</b>", parse_mode="HTML", reply_markup=kb_current_learning())
    await state.set_state(Survey.current_learning)


@router.callback_query(Survey.current_learning, F.data.startswith("cur_"))
async def on_current(cb: CallbackQuery, state: FSMContext):
    await state.update_data(current_learning=LABELS[cb.data])
    await cb.message.edit_text(f"✅ {LABELS[cb.data]}")
    await cb.message.answer("❼ <b>Сколько готов платить за AI-помощника?</b>", parse_mode="HTML", reply_markup=kb_price())
    await state.set_state(Survey.price_ready)


@router.callback_query(Survey.price_ready, F.data.startswith("price_"))
async def on_price(cb: CallbackQuery, state: FSMContext):
    await state.update_data(price_ready=LABELS[cb.data])
    await cb.message.edit_text(f"✅ {LABELS[cb.data]}")
    await cb.message.answer(
        "❽ <b>Последний вопрос!</b>\n\n"
        "Напиши свободным текстом: какую тему ты давно хочешь изучить, "
        "но никак не можешь начать? Почему?\n\n"
        "<i>Например: «Хочу разобраться в таргетированной рекламе, "
        "но не понимаю с чего начать и какие инструменты учить»</i>",
        parse_mode="HTML",
    )
    await state.set_state(Survey.dream_topic)


@router.message(Survey.dream_topic)
async def on_dream_topic(message: Message, state: FSMContext):
    await state.update_data(dream_topic=message.text)
    data = await state.get_data()
    count = save_user(data)
    is_test = data.get("is_test", 0)

    if is_test:
        await message.answer(
            "🧪 <b>Тестовый прогон завершён!</b>\n\n"
            f"Промокод: <code>{PROMO_CODE}</code>\n"
            f"Реальных заявок в счётчике: {count}\n\n"
            "Этот ответ НЕ учитывается в статистике.",
            parse_mode="HTML",
        )
    else:
        spots_left = max(0, 100 - count)
        await message.answer(
            f"🎉 <b>Спасибо! Ты в списке.</b>\n\n"
            f"Твой промокод: <code>{PROMO_CODE}</code>\n"
            f"Скидка 50% на первый месяц подписки.\n\n"
            f"📊 Ты #{count} в очереди. "
            f"{'Осталось ' + str(spots_left) + ' мест с промокодом.' if spots_left > 0 else 'Все 100 мест заняты, но промокод всё равно твой!'}\n\n"
            f"Мы напишем тебе в этот чат, когда бот будет готов.\n\n"
            f"А пока — подпишись на наш канал:\n"
            f"👉 @skillroute_channel",
            parse_mode="HTML",
        )

    # Уведомление админу
    if ADMIN_ID and not is_test:
        test_mark = ""
        summary = (
            f"🆕 <b>Новая заявка #{count}</b>{test_mark}\n\n"
            f"👤 {data.get('full_name')} (@{data.get('tg_username', '—')})\n"
            f"🏷 Сегмент: {data.get('segment')}\n"
            f"📚 Тема: {data.get('topic')}\n"
            f"📊 Уровень: {data.get('level')}\n"
            f"⏱ Время: {data.get('time_per_day')}\n"
            f"😤 Боль: {data.get('pain')}\n"
            f"📖 Учится через: {data.get('current_learning')}\n"
            f"💳 Готов платить: {data.get('price_ready')}\n"
            f"💬 Мечта: {data.get('dream_topic')}"
        )
        try:
            await message.bot.send_message(int(ADMIN_ID), summary, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

    await state.clear()


# ── Admin Commands ─────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    total, real, test, segments, topics, pains, prices = get_stats()

    text = f"📊 <b>SkillRoute — Статистика</b>\n\n"
    text += f"Всего: <b>{total}</b> (реальных: {real}, тестовых: {test})\n\n"

    if real > 0:
        text += "👥 <b>Сегменты:</b>\n"
        for seg, cnt in segments:
            pct = round(cnt / real * 100)
            text += f"  • {seg}: {cnt} ({pct}%)\n"

        text += "\n📚 <b>Темы:</b>\n"
        for top, cnt in topics[:7]:
            pct = round(cnt / real * 100)
            text += f"  • {top}: {cnt} ({pct}%)\n"

        text += "\n😤 <b>Боли:</b>\n"
        for pain, cnt in pains[:6]:
            pct = round(cnt / real * 100)
            text += f"  • {pain}: {cnt} ({pct}%)\n"

        text += "\n💳 <b>Готовность платить:</b>\n"
        for price, cnt in prices:
            pct = round(cnt / real * 100)
            text += f"  • {price}: {cnt} ({pct}%)\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("reset"))
async def cmd_reset(message: Message):
    if not is_admin(message.from_user.id):
        return

    total, real, test, *_ = get_stats()
    await message.answer(
        f"⚠️ <b>Сброс данных</b>\n\n"
        f"Сейчас в базе: {total} записей (реальных: {real}, тестовых: {test})\n\n"
        f"Что удалить?",
        parse_mode="HTML",
        reply_markup=kb_reset_confirm(),
    )


@router.callback_query(F.data == "reset_test")
async def on_reset_test(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    deleted = reset_test_users()
    await cb.message.edit_text(f"🧹 Удалено тестовых записей: {deleted}\nСчётчик реальных заявок не изменился.")


@router.callback_query(F.data == "reset_all")
async def on_reset_all(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    deleted = reset_all_users()
    await cb.message.edit_text(f"🔥 Полный сброс! Удалено записей: {deleted}\nСчётчик обнулён.")


@router.callback_query(F.data == "reset_cancel")
async def on_reset_cancel(cb: CallbackQuery):
    await cb.message.edit_text("❌ Сброс отменён.")


@router.message(Command("export"))
async def cmd_export(message: Message):
    if not is_admin(message.from_user.id):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM users WHERE is_test = 0")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    if not rows:
        await message.answer("Пока нет реальных данных.")
        return

    import io
    output = io.StringIO()
    output.write(",".join(columns) + "\n")
    for row in rows:
        output.write(",".join(str(v or "").replace(",", ";") for v in row) + "\n")

    from aiogram.types import BufferedInputFile
    file = BufferedInputFile(
        output.getvalue().encode("utf-8"),
        filename=f"skillroute_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    )
    await message.answer_document(file, caption=f"📁 Экспорт: {len(rows)} реальных записей")


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🔧 <b>Админ-команды:</b>\n\n"
        "/stats — статистика по сегментам, темам, болям, ценам\n"
        "/export — выгрузка CSV (только реальные заявки)\n"
        "/reset — сброс данных (тестовые или все)\n"
        "/help — эта справка\n\n"
        "💡 <b>Тестовый режим:</b>\n"
        "Отправь боту <code>/start test</code> — пройдёшь опрос, "
        "но ответ не попадёт в счётчик и статистику.",
        parse_mode="HTML",
    )


# ── Main ───────────────────────────────────────────────

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set")

    init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("SkillRoute bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
