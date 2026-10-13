from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from config import ADMIN_IDS, CALENDAR_IMAGE
from states import AdminStates
from keyboards import admin_main_menu, build_calendar
from utils import split_text, answer_with_photo

router = Router()


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await message.answer("🛠 Админ-панель", reply_markup=admin_main_menu())


@router.callback_query(F.data == "admin_panel_back")
async def admin_panel_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("🛠 Админ-панель", reply_markup=admin_main_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_generate")
async def admin_generate(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    result = await db.generate_worker()
    if result is None:
        await callback.message.answer("❌ Все номера от 1000 до 2000 заняты!")
    else:
        number, key = result
        await callback.message.answer(
            f"✅ Создан новый доступ:\n\n"
            f"🔢 Номер: {number}\n"
            f"🔑 Ключ: `{key}`\n\n"
            f"Передайте этот ключ воркеру.",
            parse_mode="Markdown"
        )
    await callback.answer()


@router.callback_query(F.data == "admin_list")
async def admin_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    workers = await db.get_all_workers()
    if not workers:
        await callback.message.answer("Список пуст. Нет созданных номеров.")
        await callback.answer()
        return

    lines = ["📋 Список воркеров:\n"]
    for w in workers:
        if w['is_bound']:
            status = f"привязан (TG ID: {w['telegram_id']})"
        else:
            status = "свободен"
        lines.append(f"№{w['number']} | Ключ: {w['secret_key']} | {status}")

    text = "\n".join(lines)
    for chunk in split_text(text):
        await callback.message.answer(chunk)
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_worker_number)
    await callback.message.answer("Введите номер воркера (1000-2000):")
    await callback.answer()


@router.message(AdminStates.waiting_worker_number)
async def admin_stats_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()

    if not text.isdigit() or not (1000 <= int(text) <= 2000):
        await message.answer("❌ Введите корректный номер от 1000 до 2000:")
        return

    number = int(text)
    worker = await db.get_worker_by_number(number)
    if not worker:
        await message.answer("❌ Номер не найден в базе. Попробуйте другой номер:")
        return

    await state.clear()
    now = datetime.now()
    markup = await build_calendar(number, now.year, now.month, mode='a')
    await answer_with_photo(
        message, CALENDAR_IMAGE,
        f"📅 Статистика воркера №{number}\nВыберите день:",
        markup
    )
