from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

import database as db
from config import ADMIN_IDS, CALENDAR_IMAGE
from states import AdminStates
from keyboards import admin_main_menu, build_calendar
from utils import split_text, answer_with_photo, replace_with_text

router = Router()


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await state.clear()
    await message.answer("🛠 Админ-панель", reply_markup=admin_main_menu())


@router.callback_query(F.data == "admin_panel_back")
async def admin_panel_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await replace_with_text(callback, "🛠 Админ-панель", admin_main_menu())


@router.callback_query(F.data == "admin_generate")
async def admin_generate(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    result = await db.generate_worker()
    if result is None:
        await callback.message.answer("❌ Все номера от 1000 до 2000 заняты!")
    else:
        number, key = result
        await callback.message.answer(
            f"✅ Создан новый доступ:\n\n🔢 Номер: {number}\n🔑 Ключ: `{key}`\n\nПередайте этот ключ воркеру.",
            parse_mode="Markdown"
        )


@router.callback_query(F.data == "admin_generate_custom")
async def admin_generate_custom_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_custom_number)
    await callback.message.answer("Введите номер (1000-2000), для которого нужно сгенерировать ключ:")


@router.message(AdminStates.waiting_custom_number)
async def admin_generate_custom_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text.isdigit() or not (1000 <= int(text) <= 2000):
        await message.answer("❌ Введите корректный номер от 1000 до 2000:")
        return
    number = int(text)
    await state.clear()
    key = await db.generate_worker_for_number(number)
    if key is None:
        await message.answer(
            f"❌ Номер №{number} уже занят. Сначала удалите текущего воркера, "
            f"либо выберите другой номер."
        )
        return
    await message.answer(
        f"✅ Создан новый доступ:\n\n🔢 Номер: {number}\n🔑 Ключ: `{key}`\n\nПередайте этот ключ воркеру.",
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin_list")
async def admin_list(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    workers = await db.get_all_workers()
    if not workers:
        await callback.message.answer("Список пуст. Нет созданных номеров.")
        return
    lines = ["📋 Список воркеров:\n"]
    for w in workers:
        status = f"привязан (TG ID: {w['telegram_id']})" if w['is_bound'] else "свободен"
        lines.append(f"№{w['number']} | Ключ: {w['secret_key']} | {status}")
    text = "\n".join(lines)
    for chunk in split_text(text):
        await callback.message.answer(chunk)


@router.callback_query(F.data == "admin_stats")
async def admin_stats_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_worker_number)
    await callback.message.answer("Введите номер воркера (1000-2000):")


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
    await answer_with_photo(message, CALENDAR_IMAGE, f"📅 Статистика воркера №{number}\nВыберите день:", markup)


@router.callback_query(F.data == "admin_delete_start")
async def admin_delete_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_delete_number)
    await callback.message.answer("Введите номер воркера, которого нужно удалить (1000-2000):")


@router.message(AdminStates.waiting_delete_number)
async def admin_delete_process(message: Message, state: FSMContext):
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

    status = f"привязан к TG ID {worker['telegram_id']}" if worker['is_bound'] else "свободен (ключ не использован)"
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delconfirm:{number}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel_back")]
    ])
    await message.answer(
        f"⚠️ Вы уверены, что хотите удалить воркера №{number}?\n"
        f"Статус: {status}\n"
        f"Ключ: {worker['secret_key']}\n\n"
        f"Будет удалена ВСЯ статистика (депозиты и круги) этого номера. "
        f"Номер снова станет свободным для генерации нового ключа.",
        reply_markup=confirm_kb
    )


@router.callback_query(F.data.startswith("delconfirm:"))
async def admin_delete_confirm(callback: CallbackQuery):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    _, number_str = callback.data.split(":")
    number = int(number_str)
    deleted = await db.delete_worker(number)
    if deleted:
        text = f"✅ Воркер №{number} удалён. Номер свободен для новой генерации."
    else:
        text = f"❌ Воркер №{number} уже не найден (возможно, удалён ранее)."
    await replace_with_text(callback, text, admin_main_menu())
