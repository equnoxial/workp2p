import calendar
from datetime import datetime

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from utils import MONTHS_RU, format_number, shift_month


# ---------------------------------------------------------------------------
# ГЛАВНЫЕ МЕНЮ
# ---------------------------------------------------------------------------

def worker_main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Календарь / Статистика", callback_data="menu_calendar")
    kb.button(text="📊 Архив", callback_data="menu_archive")
    kb.adjust(1)
    return kb.as_markup()


def worker_menu_text(number: int) -> str:
    return f"📱 Ваш рабочий номер: №{number}\n\nВыберите действие:"


def admin_main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Сгенерировать доступ", callback_data="admin_generate")
    kb.button(text="📋 Список воркеров", callback_data="admin_list")
    kb.button(text="📊 Статистика воркера", callback_data="admin_stats")
    kb.adjust(1)
    return kb.as_markup()


# ---------------------------------------------------------------------------
# КАЛЕНДАРЬ
# ---------------------------------------------------------------------------

async def build_calendar(number: int, year: int, month: int, mode: str = 'w') -> InlineKeyboardMarkup:
    """
    mode: 'w' — обычный воркер (может редактировать),
          'a' — просмотр админом (только чтение)
    """
    days_with_data = await db.get_month_days_with_data(number, year, month)
    month_name = MONTHS_RU[month]

    rows = [[
        InlineKeyboardButton(text="◀️", callback_data=f"calnav:{number}:{year}:{month}:prev:{mode}"),
        InlineKeyboardButton(text=f"{month_name} {year}", callback_data="noop"),
        InlineKeyboardButton(text="▶️", callback_data=f"calnav:{number}:{year}:{month}:next:{mode}"),
    ]]

    _, days_in_month = calendar.monthrange(year, month)
    day_buttons = []
    for day in range(1, days_in_month + 1):
        mark = "✅" if day in days_with_data else "▫️"
        day_buttons.append(InlineKeyboardButton(
            text=f"{mark}{day}",
            callback_data=f"calday:{number}:{year}:{month}:{day}:{mode}"
        ))

    for i in range(0, len(day_buttons), 7):
        rows.append(day_buttons[i:i + 7])

    back_cb = "menu_back" if mode == 'w' else "admin_panel_back"
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data=back_cb)])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_day_actions(number: int, year: int, month: int, day: int, mode: str = 'w') -> InlineKeyboardMarkup:
    rows = []
    if mode == 'w':
        rows.append([InlineKeyboardButton(
            text="💰 Внести/Изменить Депозит",
            callback_data=f"dep:{number}:{year}:{month}:{day}"
        )])
        rows.append([InlineKeyboardButton(
            text="🔄 Добавить круг",
            callback_data=f"circ:{number}:{year}:{month}:{day}"
        )])
    rows.append([InlineKeyboardButton(
        text="⬅️ Назад к календарю",
        callback_data=f"backcal:{number}:{year}:{month}:{mode}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# АРХИВ (СПИСОК МЕСЯЦЕВ)
# ---------------------------------------------------------------------------

async def build_archive_list(number: int, mode: str = 'w') -> InlineKeyboardMarkup:
    rows = []
    now = datetime.now()
    year, month = now.year, now.month

    for i in range(12):
        y, m = shift_month(year, month, -i)
        total = await db.get_month_total_profit(number, y, m)
        month_name = MONTHS_RU[m]
        rows.append([InlineKeyboardButton(
            text=f"{month_name} {y} — ${total:.2f}",
            callback_data=f"archmonth:{number}:{y}:{m}:{mode}"
        )])

    back_cb = "menu_back" if mode == 'w' else "admin_panel_back"
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# ТЕКСТ СВОДКИ ЗА ДЕНЬ
# ---------------------------------------------------------------------------

async def render_day_summary(number: int, date_str: str) -> str:
    deposit = await db.get_deposit(number, date_str)
    circles = await db.get_circles(number, date_str)
    total_profit = sum(c['profit_usd'] for c in circles)

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_formatted = date_obj.strftime("%d.%m.%Y")

    text = f"📅 Статистика за {date_formatted}\n"
    text += f"🔢 Рабочий номер: №{number}\n"
    text += "----------------------------\n"

    deposit_text = format_number(deposit) if deposit else "0"
    text += f"💰 Рабочий депозит: {deposit_text} ₽\n"

    sign = "+" if total_profit >= 0 else ""
    text += f"📈 Чистый профит за день: {sign}${total_profit:.2f}\n\n"

    if circles:
        text += "🏦 Обработанные круги и банки:\n"
        for c in circles:
            p_sign = "+" if c['profit_usd'] >= 0 else ""
            text += (
                f"• {c['bank']} | Принято: {format_number(c['amount_rub'])} ₽ "
                f"({c['payments_count']} пл.) | Профит: {p_sign}${c['profit_usd']:.2f}\n"
            )
    else:
        text += "🏦 Кругов за этот день пока нет.\n"

    return text