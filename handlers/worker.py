from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import database as db
from states import DepositStates, CircleStates
from keyboards import (
    build_calendar, build_day_actions, build_archive_list, render_day_summary
)
from utils import shift_month, parse_amount

router = Router()


# ---------------------------------------------------------------------------
# ГЛАВНОЕ МЕНЮ: КАЛЕНДАРЬ / АРХИВ
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu_calendar")
async def open_calendar(callback: CallbackQuery):
    worker = await db.get_worker_by_telegram_id(callback.from_user.id)
    if not worker:
        await callback.answer("⛔ Ошибка доступа. Введите /start", show_alert=True)
        return

    now = datetime.now()
    markup = await build_calendar(worker['number'], now.year, now.month, mode='w')
    await callback.message.edit_text(
        f"📅 Календарь — №{worker['number']}\nВыберите день:",
        reply_markup=markup
    )
    await callback.answer()


@router.callback_query(F.data == "menu_archive")
async def open_archive(callback: CallbackQuery):
    worker = await db.get_worker_by_telegram_id(callback.from_user.id)
    if not worker:
        await callback.answer("⛔ Ошибка доступа. Введите /start", show_alert=True)
        return

    markup = await build_archive_list(worker['number'], mode='w')
    await callback.message.edit_text(
        f"📊 Архив — №{worker['number']}\nВыберите месяц:",
        reply_markup=markup
    )
    await callback.answer()


@router.callback_query(F.data.startswith("archmonth:"))
async def open_archive_month(callback: CallbackQuery):
    _, number, year, month, mode = callback.data.split(":")
    number, year, month = int(number), int(year), int(month)

    if mode == 'w':
        worker = await db.get_worker_by_telegram_id(callback.from_user.id)
        if not worker or worker['number'] != number:
            await callback.answer("⛔ Доступ запрещен", show_alert=True)
            return

    markup = await build_calendar(number, year, month, mode=mode)
    await callback.message.edit_text(
        f"📅 Календарь — №{number}\nВыберите день:",
        reply_markup=markup
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# НАВИГАЦИЯ ПО КАЛЕНДАРЮ
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("calnav:"))
async def nav_calendar(callback: CallbackQuery):
    _, number, year, month, direction, mode = callback.data.split(":")
    number, year, month = int(number), int(year), int(month)

    if mode == 'w':
        worker = await db.get_worker_by_telegram_id(callback.from_user.id)
        if not worker or worker['number'] != number:
            await callback.answer("⛔ Доступ запрещен", show_alert=True)
            return

    delta = -1 if direction == "prev" else 1
    new_year, new_month = shift_month(year, month, delta)

    markup = await build_calendar(number, new_year, new_month, mode=mode)
    await callback.message.edit_text(
        f"📅 Календарь — №{number}\nВыберите день:",
        reply_markup=markup
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# ВЫБОР ДНЯ
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("calday:"))
async def select_day(callback: CallbackQuery):
    _, number, year, month, day, mode = callback.data.split(":")
    number, year, month, day = int(number), int(year), int(month), int(day)

    if mode == 'w':
        worker = await db.get_worker_by_telegram_id(callback.from_user.id)
        if not worker or worker['number'] != number:
            await callback.answer("⛔ Доступ запрещен", show_alert=True)
            return

    date_str = f"{year:04d}-{month:02d}-{day:02d}"
    text = await render_day_summary(number, date_str)
    markup = build_day_actions(number, year, month, day, mode)

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("backcal:"))
async def back_to_calendar(callback: CallbackQuery):
    _, number, year, month, mode = callback.data.split(":")
    number, year, month = int(number), int(year), int(month)

    markup = await build_calendar(number, year, month, mode=mode)
    await callback.message.edit_text(
        f"📅 Календарь — №{number}\nВыберите день:",
        reply_markup=markup
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# ДЕПОЗИТ
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("dep:"))
async def start_deposit(callback: CallbackQuery, state: FSMContext):
    _, number, year, month, day = callback.data.split(":")
    number, year, month, day = int(number), int(year), int(month), int(day)

    worker = await db.get_worker_by_telegram_id(callback.from_user.id)
    if not worker or worker['number'] != number:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.update_data(number=number, year=year, month=month, day=day)
    await state.set_state(DepositStates.waiting_amount)
    await callback.message.answer(
        "💰 Введите сумму депозита в рублях (₽), например: 15000"
    )
    await callback.answer()


@router.message(DepositStates.waiting_amount)
async def process_deposit(message: Message, state: FSMContext):
    amount = parse_amount(message.text)

    if amount is None or amount <= 0:
        await message.answer(
            "❌ Некорректный ввод. Введите число больше нуля, например: 15000\n"
            "Попробуйте еще раз:"
        )
        return

    data = await state.get_data()
    number, year, month, day = data['number'], data['year'], data['month'], data['day']
    date_str = f"{year:04d}-{month:02d}-{day:02d}"

    await db.set_deposit(number, date_str, amount)
    await state.clear()

    summary = await render_day_summary(number, date_str)
    markup = build_day_actions(number, year, month, day, 'w')

    await message.answer("✅ Депозит обновлен!")
    await message.answer(summary, reply_markup=markup)


# ---------------------------------------------------------------------------
# КРУГ (FSM: банк -> сумма -> кол-во платежей -> профит)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("circ:"))
async def start_circle(callback: CallbackQuery, state: FSMContext):
    _, number, year, month, day = callback.data.split(":")
    number, year, month, day = int(number), int(year), int(month), int(day)

    worker = await db.get_worker_by_telegram_id(callback.from_user.id)
    if not worker or worker['number'] != number:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.update_data(number=number, year=year, month=month, day=day)
    await state.set_state(CircleStates.waiting_bank)
    await callback.message.answer("🏦 Введите название банка (например: Сбер, Т-Банк):")
    await callback.answer()


@router.message(CircleStates.waiting_bank)
async def process_bank(message: Message, state: FSMContext):
    bank = (message.text or "").strip()

    if not bank:
        await message.answer("❌ Название банка не может быть пустым. Введите снова:")
        return
    if len(bank) > 50:
        await message.answer("❌ Слишком длинное название (макс. 50 символов). Введите снова:")
        return

    await state.update_data(bank=bank)
    await state.set_state(CircleStates.waiting_amount)
    await message.answer("💵 Введите общую сумму принятых рублей за круг (₽), например: 15000")


@router.message(CircleStates.waiting_amount)
async def process_circle_amount(message: Message, state: FSMContext):
    amount = parse_amount(message.text)

    if amount is None or amount <= 0:
        await message.answer(
            "❌ Некорректный ввод. Введите число больше нуля, например: 15000\n"
            "Попробуйте еще раз:"
        )
        return

    await state.update_data(amount_rub=amount)
    await state.set_state(CircleStates.waiting_payments)
    await message.answer("🔢 Введите количество принятых платежей (целое число), например: 3")


@router.message(CircleStates.waiting_payments)
async def process_payments(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    if not text.isdigit() or int(text) <= 0:
        await message.answer(
            "❌ Введите целое положительное число (например: 3). Попробуйте еще раз:"
        )
        return

    await state.update_data(payments_count=int(text))
    await state.set_state(CircleStates.waiting_profit)
    await message.answer("📈 Введите чистый профит с этого круга в долларах ($), например: 25.5")


@router.message(CircleStates.waiting_profit)
async def process_profit(message: Message, state: FSMContext):
    profit = parse_amount(message.text)

    if profit is None:
        await message.answer(
            "❌ Некорректный ввод. Введите число, например: 25.5 (можно отрицательное). "
            "Попробуйте еще раз:"
        )
        return

    data = await state.get_data()
    number, year, month, day = data['number'], data['year'], data['month'], data['day']
    date_str = f"{year:04d}-{month:02d}-{day:02d}"

    await db.add_circle(
        number, date_str, data['bank'], data['amount_rub'],
        data['payments_count'], profit
    )
    await state.clear()

    summary = await render_day_summary(number, date_str)
    markup = build_day_actions(number, year, month, day, 'w')

    await message.answer("✅ Круг добавлен!")
    await message.answer(summary, reply_markup=markup)