from datetime import datetime
import calendar as pycalendar

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from utils import MONTHS_RU, format_number, shift_month


def worker_menu_text(number: int) -> str:
    return (
        f"📱 Ваш рабочий номер: №{number}\n\n"
        f"Выберите действие:"
    )


def worker_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Календарь / Статистика", callback_data="menu_calendar")],
        [InlineKeyboardButton(text="📊 Архив", callback_data="menu_archive")],
    ])


def admin_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Сгенерировать доступ", callback_data="admin_generate")],
        [InlineKeyboardButton(text="🎯 Сгенерировать для номера", callback_data="admin_generate_custom")],
        [InlineKeyboardButton(text="📋 Список воркеров", callback_data="admin_list")],
        [InlineKeyboardButton(text="📊 Статистика воркера", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🗑 Удалить воркера", callback_data="admin_delete_start")],
    ])


async def build_calendar(number: int, year: int, month: int, mode: str = 'w') -> InlineKeyboardMarkup:
    days_with_data = await db.get_month_days_with_data(number, year, month)

    month_name = MONTHS_RU.get(month, str(month))
    keyboard = []

    keyboard.append([
        InlineKeyboardButton(text=f"{month_name} {year}", callback_data="noop")
    ])

    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([
        InlineKeyboardButton(text=wd, callback_data="noop") for wd in weekdays
    ])

    cal = pycalendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            else:
                marker = "✅" if day in days_with_data else ""
                text = f"{marker}{day}" if marker else str(day)
                row.append(InlineKeyboardButton(
                    text=text,
                    callback_data=f"calday:{number}:{year}:{month}:{day}:{mode}"
                ))
        keyboard.append(row)

    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)

    keyboard.append([
        InlineKeyboardButton(
            text="⬅️",
            callback_data=f"calnav:{number}:{year}:{month}:prev:{mode}"
        ),
        InlineKeyboardButton(
            text="➡️",
            callback_data=f"calnav:{number}:{year}:{month}:next:{mode}"
        ),
    ])

    if mode == 'w':
        keyboard.append([
            InlineKeyboardButton(text="📊 Архив", callback_data="menu_archive")
        ])
        keyboard.append([
            InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin_panel_back")
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_day_actions(number: int, year: int, month: int, day: int, mode: str = 'w') -> InlineKeyboardMarkup:
    keyboard = []

    if mode == 'w':
        keyboard.append([
            InlineKeyboardButton(
                text="💰 Внести/Изменить Депозит",
                callback_data=f"dep:{number}:{year}:{month}:{day}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text="🔄 Добавить круг",
                callback_data=f"circ:{number}:{year}:{month}:{day}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ Назад к календарю",
            callback_data=f"backcal:{number}:{year}:{month}:{mode}"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def build_archive_list(number: int, mode: str = 'w') -> InlineKeyboardMarkup:
    now = datetime.now()
    keyboard = []

    year, month = now.year, now.month
    months_list = []
    for _ in range(12):
        months_list.append((year, month))
        year, month = shift_month(year, month, -1)

    for y, m in months_list:
        total_profit = await db.get_month_total_profit(number, y, m)
        month_name = MONTHS_RU.get(m, str(m))
        text = f"{month_name} {y} — ${format_number(total_profit)}"
        keyboard.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"archmonth:{number}:{y}:{m}:{mode}"
            )
        ])

    if mode == 'w':
        keyboard.append([
            InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_back")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin_panel_back")
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def render_day_summary(number: int, date_str: str) -> str:
    year, month, day = map(int, date_str.split("-"))
    date_formatted = f"{day:02d}.{month:02d}.{year:04d}"

    deposit = await db.get_deposit(number, date_str)
    circles = await db.get_circles(number, date_str)

    total_profit = sum(c['profit_usd'] for c in circles)

    lines = [
        f"📅 Статистика за {date_formatted}",
        f"🔢 Рабочий номер: №{number}",
        "----------------------------",
        f"💰 Рабочий депозит: {format_number(deposit)} ₽",
        f"📈 Чистый профит за день: ${format_number(total_profit)}",
        "",
        "🏦 Обработанные круги и банки:"
    ]

    if circles:
        for c in circles:
            lines.append(
                f"• {c['bank']} | Принято: {format_number(c['amount_rub'])} ₽ "
                f"({c['payments_count']} пл.) | Профит: +${format_number(c['profit_usd'])}"
            )
    else:
        lines.append("Нет кругов за этот день.")

    return "\n".join(lines)
