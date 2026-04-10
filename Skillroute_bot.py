"""
SkillRoute Bot — Waitlist + CustDev заглушка v2
Фиксы: "Другое" с уточнением, кнопка пропуска, расширенные сегменты и цены.

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

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
DB_PATH = "skillroute_waitlist.db"
PROMO_CODE = "SKILL50"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        data.get("price_ready"), data.get("dream_topic", "—"), data.get("is_test", 0),
        datetime.now().isoformat()
    ))
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM users WHERE is_test = 0").fetchone()[0]
    conn.close()
    return count

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    real = conn.execute("SELECT COUNT(*) FROM users WHERE is_test = 0").fetchone()[0]
    test = conn.execute("SELECT COUNT(*) FROM users WHERE is_test = 1").fetchone()[0]
    segments = conn.execute("SELECT segment, COUNT(*) FROM users WHERE is_test = 0 GROUP BY segment").fetchall()
    topics = conn.execute("SELECT topic, COUNT(*) FROM users WHERE is_test = 0 GROUP BY topic ORDER BY COUNT(*) DESC").fetchall()
    pains = conn.execute("SELECT pain, COUNT(*) FROM users WHERE is_test = 0 GROUP BY pain ORDER BY COUNT(*) DESC").fetchall()
    prices = conn.execute("SELECT price_ready, COUNT(*) FROM users WHERE is_test = 0 GROUP BY price_ready ORDER BY COUNT(*) DESC").fetchall()
    conn.close()
    return total, real, test, segments, topics, pains, prices

def reset_test_users():
    conn = sqlite3.connect(DB_PATH)
    deleted = conn.execute("DELETE FROM users WHERE is_test = 1").rowcount
    conn.commit()
    conn.close()
    return deleted

def reset_all_users():
    conn = sqlite3.connect(DB_PATH)
    deleted = conn.execute("DELETE FROM users").rowcount
    conn.commit()
    conn.close()
    return deleted

class Survey(StatesGroup):
    segment = State()
    topic = State()
    topic_other = State()
    level = State()
    time_per_day = State()
    pain = State()
    current_learning = State()
    price_ready = State()
    dream_topic = State()

def kb_segment():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏢 Наёмный сотрудник", callback_data="seg_employee")],
        [InlineKeyboardButton(text="🚀 Предприниматель / фрилансер", callback_data="seg_entrepreneur")],
        [InlineKeyboardButton(text="🎓 Студент вуза / магистрант", callback_data="seg_student")],
        [InlineKeyboardButton(text="⚡ Совмещаю работу и учёбу", callback_data="seg_hybrid")],
        [InlineKeyboardButton(text="🔄 Меняю профессию / в поиске работы", callback_data="seg_career_change")],
        [InlineKeyboardButton(text="🚫 Не хочу проходить опрос", callback_data="seg_skip_all")],
    ])

def kb_topic():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Маркетинг / SMM", callback_data="top_marketing")],
        [InlineKeyboardButton(text="🎨 Дизайн", callback_data="top_design")],
        [InlineKeyboardButton(text="💰 Финансы / Инвестиции", callback_data="top_finance")],
        [InlineKeyboardButton(text="📊 Бизнес / Управление", callback_data="top_business")],
        [InlineKeyboardButton(text="💻 IT / Программирование", callback_data="top_it")],
        [InlineKeyboardButton(text="🔤 Иностранные языки", callback_data="top_languages")],
        [InlineKeyboardButton(text="✍️ Другое (напишу сам)", callback_data="top_other")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="top_skip")],
    ])

def kb_level():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌱 С нуля — ничего не знаю", callback_data="lvl_zero")],
        [InlineKeyboardButton(text="📗 Базовый — знаю основы", callback_data="lvl_base")],
        [InlineKeyboardButton(text="📘 Продвинутый — хочу экспертизу", callback_data="lvl_advanced")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="lvl_skip")],
    ])

def kb_time():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ 30 минут в день", callback_data="time_30")],
        [InlineKeyboardButton(text="⏱ 1 час в день", callback_data="time_60")],
        [InlineKeyboardButton(text="⏱ 2+ часа в день", callback_data="time_120")],
        [InlineKeyboardButton(text="📅 Только по выходным", callback_data="time_weekend")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="time_skip")],
    ])

def kb_pain():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌊 Слишком много информации", callback_data="pain_overload")],
        [InlineKeyboardButton(text="❓ Не знаю с чего начать", callback_data="pain_start")],
        [InlineKeyboardButton(text="😴 Начинаю и бросаю", callback_data="pain_dropout")],
        [InlineKeyboardButton(text="💸 Курсы слишком дорогие", callback_data="pain_expensive")],
        [InlineKeyboardButton(text="⏰ Нет времени", callback_data="pain_time")],
        [InlineKeyboardButton(text="🤷 Нет чёткой цели", callback_data="pain_nogoal")],
        [InlineKeyboardButton(text="✅ Ничего не мешает", callback_data="pain_none")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="pain_skip")],
    ])

def kb_current_learning():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 YouTube", callback_data="cur_youtube")],
        [InlineKeyboardButton(text="📚 Платные курсы", callback_data="cur_courses")],
        [InlineKeyboardButton(text="📖 Статьи и блоги", callback_data="cur_articles")],
        [InlineKeyboardButton(text="🤖 ChatGPT / нейросети", callback_data="cur_ai")],
        [InlineKeyboardButton(text="🎓 Бесплатные курсы (Stepik и т.д.)", callback_data="cur_free")],
        [InlineKeyboardButton(text="🚫 Сейчас не учусь", callback_data="cur_nothing")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="cur_skip")],
    ])

def kb_price():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 Только бесплатно", callback_data="price_free")],
        [InlineKeyboardButton(text="💳 До 299₽/мес", callback_data="price_299")],
        [InlineKeyboardButton(text="💳 До 499₽/мес", callback_data="price_499")],
        [InlineKeyboardButton(text="💳 До 999₽/мес", callback_data="price_999")],
        [InlineKeyboardButton(text="💎 Больше 999₽/мес", callback_data="price_above")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="price_skip")],
    ])

def kb_dream_skip():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить и завершить", callback_data="dream_skip")],
    ])

def kb_reset_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Удалить только тестовых", callback_data="reset_test")],
        [InlineKeyboardButton(text="🔥 Удалить ВСЕХ (полный сброс)", callback_data="reset_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="reset_cancel")],
    ])

LABELS = {
    "seg_employee": "Наёмный сотрудник", "seg_entrepreneur": "Предприниматель / фрилансер",
    "seg_student": "Студент вуза / магистрант", "seg_hybrid": "Совмещает работу и учёбу",
    "seg_career_change": "Меняет профессию / в поиске работы",
    "top_marketing": "Маркетинг / SMM", "top_design": "Дизайн",
    "top_finance": "Финансы / Инвестиции", "top_business": "Бизнес / Управление",
    "top_it": "IT / Программирование", "top_languages": "Иностранные языки", "top_skip": "—",
    "lvl_zero": "С нуля", "lvl_base": "Базовый", "lvl_advanced": "Продвинутый", "lvl_skip": "—",
    "time_30": "30 мин/день", "time_60": "1 час/день", "time_120": "2+ часа/день",
    "time_weekend": "По выходным", "time_skip": "—",
    "pain_overload": "Слишком много информации", "pain_start": "Не знаю с чего начать",
    "pain_dropout": "Начинаю и бросаю", "pain_expensive": "Курсы дорогие",
    "pain_time": "Нет времени", "pain_nogoal": "Нет чёткой цели",
    "pain_none": "Ничего не мешает", "pain_skip": "—",
    "cur_youtube": "YouTube", "cur_courses": "Платные курсы", "cur_articles": "Статьи и блоги",
    "cur_ai": "ChatGPT / нейросети", "cur_free": "Бесплатные курсы",
    "cur_nothing": "Не учусь", "cur_skip": "—",
    "price_free": "Только бесплатно", "price_299": "До 299₽/мес",
    "price_499": "До 499₽/мес", "price_999": "До 999₽/мес",
    "price_above": "Больше 999₽/мес", "price_skip": "—",
}

def is_admin(user_id: int) -> bool:
    return ADMIN_ID and str(user_id) == str(ADMIN_ID)

async def finish_survey(source, state: FSMContext, bot: Bot):
    data = await state.get_data()
    count = save_user(data)
    is_test = data.get("is_test", 0)
    send = source.message.answer if isinstance(source, CallbackQuery) else source.answer

    if is_test:
        await send(
            f"🧪 <b>Тестовый прогон завершён!</b>\n\nПромокод: <code>{PROMO_CODE}</code>\n"
            f"Реальных заявок: {count}\nЭтот ответ НЕ в статистике.", parse_mode="HTML")
    else:
        spots = max(0, 100 - count)
        await send(
            f"🎉 <b>Спасибо! Ты в списке.</b>\n\n"
            f"Твой промокод: <code>{PROMO_CODE}</code>\nСкидка 50% на первый месяц.\n\n"
            f"📊 Ты #{count} в очереди. "
            f"{'Осталось ' + str(spots) + ' мест.' if spots > 0 else 'Все 100 мест заняты, но промокод твой!'}\n\n"
            f"Напишем сюда когда бот будет готов.\n\n👉 @skillroute_channel", parse_mode="HTML")

    if ADMIN_ID and not is_test:
        summary = (
            f"🆕 <b>Заявка #{count}</b>\n\n"
            f"👤 {data.get('full_name')} (@{data.get('tg_username', '—')})\n"
            f"🏷 {data.get('segment', '—')}\n📚 {data.get('topic', '—')}\n"
            f"📊 {data.get('level', '—')}\n⏱ {data.get('time_per_day', '—')}\n"
            f"😤 {data.get('pain', '—')}\n📖 {data.get('current_learning', '—')}\n"
            f"💳 {data.get('price_ready', '—')}\n💬 {data.get('dream_topic', '—')}")
        try:
            await bot.send_message(int(ADMIN_ID), summary, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")
    await state.clear()

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    is_test = 1 if (message.text and "test" in message.text.lower() and is_admin(message.from_user.id)) else 0
    await state.update_data(tg_id=message.from_user.id, tg_username=message.from_user.username,
                            full_name=message.from_user.full_name, is_test=is_test)
    prefix = "🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b>\n\n" if is_test else ""
    await message.answer(
        f"{prefix}👋 Привет! Я <b>SkillRoute</b> — AI-бот, который составит тебе "
        "персональный план обучения из лучших бесплатных ресурсов.\n\n"
        "🚧 Бот в разработке. Ответь на несколько вопросов (1 мин) "
        "— получи промокод <b>SKILL50</b> (−50% на первый месяц).\n\n"
        "Любой вопрос можно пропустить ⏭\n\n"
        '<a href="https://skillroute.vercel.app/privacy">Политика конфиденциальности</a>',
        parse_mode="HTML", disable_web_page_preview=True)
    await message.answer("❶ <b>Кто ты?</b>", parse_mode="HTML", reply_markup=kb_segment())
    await state.set_state(Survey.segment)

@router.callback_query(Survey.segment, F.data == "seg_skip_all")
async def on_skip_all(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("👋 Без проблем!")
    await cb.message.answer("Если передумаешь — /start\n\n👉 @skillroute_channel")
    await state.clear()

@router.callback_query(Survey.segment, F.data.startswith("seg_"))
async def on_segment(cb: CallbackQuery, state: FSMContext):
    await state.update_data(segment=LABELS[cb.data])
    await cb.message.edit_text(f"✅ {LABELS[cb.data]}")
    await cb.message.answer("❷ <b>Какую тему хочешь изучить?</b>", parse_mode="HTML", reply_markup=kb_topic())
    await state.set_state(Survey.topic)

@router.callback_query(Survey.topic, F.data == "top_other")
async def on_topic_other(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text("✍️ Другое")
    await cb.message.answer("Напиши свою тему — что хочешь изучить?\n\n"
        "<i>Например: «3D-моделирование», «копирайтинг», «криптовалюты»</i>", parse_mode="HTML")
    await state.set_state(Survey.topic_other)

@router.message(Survey.topic_other)
async def on_topic_other_text(message: Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer(f"✅ {message.text}")
    await message.answer("❸ <b>Какой у тебя уровень в этой теме?</b>", parse_mode="HTML", reply_markup=kb_level())
    await state.set_state(Survey.level)

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
        "❽ <b>Последний!</b>\n\nКакую тему давно хочешь изучить, но не можешь начать? Почему?\n\n"
        "<i>Например: «Хочу разобраться в таргете, но не понимаю с чего начать»</i>",
        parse_mode="HTML", reply_markup=kb_dream_skip())
    await state.set_state(Survey.dream_topic)

@router.callback_query(Survey.dream_topic, F.data == "dream_skip")
async def on_dream_skip(cb: CallbackQuery, state: FSMContext):
    await state.update_data(dream_topic="—")
    await cb.message.edit_text("⏭ Пропущено")
    await finish_survey(cb, state, cb.bot)

@router.message(Survey.dream_topic)
async def on_dream_topic(message: Message, state: FSMContext):
    await state.update_data(dream_topic=message.text)
    await finish_survey(message, state, message.bot)

# ── Admin ──────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id): return
    total, real, test, segments, topics, pains, prices = get_stats()
    text = f"📊 <b>Статистика</b>\n\nВсего: <b>{total}</b> (реальных: {real}, тест: {test})\n\n"
    if real > 0:
        text += "👥 <b>Сегменты:</b>\n"
        for s, c in segments: text += f"  • {s}: {c} ({round(c/real*100)}%)\n"
        text += "\n📚 <b>Темы:</b>\n"
        for t, c in topics[:7]: text += f"  • {t}: {c} ({round(c/real*100)}%)\n"
        text += "\n😤 <b>Боли:</b>\n"
        for p, c in pains[:7]: text += f"  • {p}: {c} ({round(c/real*100)}%)\n"
        text += "\n💳 <b>Цена:</b>\n"
        for p, c in prices: text += f"  • {p}: {c} ({round(c/real*100)}%)\n"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("reset"))
async def cmd_reset(message: Message):
    if not is_admin(message.from_user.id): return
    total, real, test, *_ = get_stats()
    await message.answer(
        f"⚠️ <b>Сброс</b>\n\nВ базе: {total} (реальных: {real}, тест: {test})\n\nЧто удалить?",
        parse_mode="HTML", reply_markup=kb_reset_confirm())

@router.callback_query(F.data == "reset_test")
async def on_reset_test(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    d = reset_test_users()
    await cb.message.edit_text(f"🧹 Удалено тестовых: {d}")

@router.callback_query(F.data == "reset_all")
async def on_reset_all(cb: CallbackQuery):
    if not is_admin(cb.from_user.id): return
    d = reset_all_users()
    await cb.message.edit_text(f"🔥 Полный сброс! Удалено: {d}")

@router.callback_query(F.data == "reset_cancel")
async def on_reset_cancel(cb: CallbackQuery):
    await cb.message.edit_text("❌ Отмена")

@router.message(Command("export"))
async def cmd_export(message: Message):
    if not is_admin(message.from_user.id): return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM users WHERE is_test = 0")
    rows = cursor.fetchall()
    columns = [d[0] for d in cursor.description]
    conn.close()
    if not rows:
        await message.answer("Нет данных.")
        return
    import io
    out = io.StringIO()
    out.write(",".join(columns) + "\n")
    for r in rows: out.write(",".join(str(v or "").replace(",", ";") for v in r) + "\n")
    from aiogram.types import BufferedInputFile
    f = BufferedInputFile(out.getvalue().encode("utf-8"),
        filename=f"skillroute_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
    await message.answer_document(f, caption=f"📁 {len(rows)} записей")

@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id): return
    await message.answer(
        "🔧 <b>Команды:</b>\n\n/stats — статистика\n/export — CSV\n/reset — сброс\n/help — справка\n\n"
        "💡 <code>/start test</code> — тестовый прогон (не в счётчик)", parse_mode="HTML")

async def main():
    if not BOT_TOKEN: raise ValueError("BOT_TOKEN not set")
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("SkillRoute bot v2 started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
