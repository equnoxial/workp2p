import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.context import FSMContext

import database as db
from states import AuthStates
from keyboards import worker_main_menu, worker_menu_text
from utils import answer_with_photo, replace_with_text
from config import TRUE_IMAGE, FALSE_IMAGE

router = Router()

GIF_PATH = "assets/welcome.gif"

WELCOME_TEXT = (
    "Добро пожаловать!\n"
    "Вы попали в бота «помощника», с его помощью вы сможете:\n\n"
    "🔰Вести статистику сделок.\n\n"
    "🔰Отслеживать свои результаты. \n\n"
    "🔰Видеть свой профит за день\n\n"
    "⚜️Желаем успехов и хорошей работы ⚜️"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    worker = await db.get_worker_by_telegram_id(message.from_user.id)

    if worker:
        await message.answer(
            worker_menu_text(worker['number']),
            reply_markup=worker_main_menu()
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начать работу 🚀", callback_data="start_work")]
        ]
    )

    try:
        animation = FSInputFile(GIF_PATH)
        await message.answer_animation(
            animation=animation,
            caption=WELCOME_TEXT,
            reply_markup=keyboard
        )
    except Exception as e:
        logging.warning(f"Не удалось отправить анимацию приветствия: {e}")
        await message.answer(WELCOME_TEXT, reply_markup=keyboard)


@router.callback_query(F.data == "start_work")
async def process_start_work(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AuthStates.waiting_key)
    await callback.message.answer(
        "🔐 Для доступа введите ваш секретный ключ (например: P2P-AA0000):"
    )


@router.message(AuthStates.waiting_key)
async def process_key(message: Message, state: FSMContext):
    key = (message.text or "").strip()

    if not key:
        await answer_with_photo(message, FALSE_IMAGE, "❌ Ключ не может быть пустым. Введите ключ:")
        return

    worker = await db.get_worker_by_key(key)

    if not worker:
        await answer_with_photo(
            message, FALSE_IMAGE,
            "❌ Неверный ключ. Проверьте правильность ввода (учитывайте регистр) и попробуйте снова."
        )
        return

    if worker['is_bound'] and worker['telegram_id'] != message.from_user.id:
        await answer_with_photo(
            message, FALSE_IMAGE,
            "❌ Этот ключ уже используется другим пользователем. Обратитесь к администратору."
        )
        return

    await db.bind_worker(worker['number'], message.from_user.id)
    await state.clear()

    success_text = f"✅ Доступ подтвержден!\n📱 Ваш рабочий номер: №{worker['number']}"
    await answer_with_photo(message, TRUE_IMAGE, success_text, worker_main_menu())


@router.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "menu_back")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()

    worker = await db.get_worker_by_telegram_id(callback.from_user.id)
    if not worker:
        await callback.answer("⛔ Ошибка доступа. Введите /start", show_alert=True)
        return

    await replace_with_text(callback, worker_menu_text(worker['number']), worker_main_menu())
