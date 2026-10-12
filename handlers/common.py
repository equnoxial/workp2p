from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from states import AuthStates
from keyboards import worker_main_menu, worker_menu_text

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    worker = await db.get_worker_by_telegram_id(message.from_user.id)

    if worker:
        await message.answer(
            worker_menu_text(worker['number']),
            reply_markup=worker_main_menu()
        )
    else:
        await state.set_state(AuthStates.waiting_key)
        await message.answer(
            "🔐 Добро пожаловать в P2P Tracker Bot!\n\n"
            "Для доступа введите ваш секретный ключ (например: P2P-XF8392):"
        )


@router.message(AuthStates.waiting_key)
async def process_key(message: Message, state: FSMContext):
    key = (message.text or "").strip()

    if not key:
        await message.answer("❌ Ключ не может быть пустым. Введите ключ:")
        return

    worker = await db.get_worker_by_key(key)

    if not worker:
        await message.answer(
            "❌ Неверный ключ. Проверьте правильность ввода "
            "(учитывайте регистр) и попробуйте снова."
        )
        return

    if worker['is_bound'] and worker['telegram_id'] != message.from_user.id:
        await message.answer(
            "❌ Этот ключ уже используется другим пользователем. "
            "Обратитесь к администратору."
        )
        return

    await db.bind_worker(worker['number'], message.from_user.id)
    await state.clear()
    await message.answer(
        f"✅ Доступ подтвержден!\n📱 Ваш рабочий номер: №{worker['number']}",
        reply_markup=worker_main_menu()
    )


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "menu_back")
async def back_to_menu(callback: CallbackQuery):
    worker = await db.get_worker_by_telegram_id(callback.from_user.id)
    if not worker:
        await callback.answer("⛔ Ошибка доступа. Введите /start", show_alert=True)
        return

    await callback.message.edit_text(
        worker_menu_text(worker['number']),
        reply_markup=worker_main_menu()
    )
    await callback.answer()