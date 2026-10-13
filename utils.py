import logging

from aiogram.types import Message, CallbackQuery, FSInputFile


MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month - 1 + delta
    year += m // 12
    month = m % 12 + 1
    return year, month


def format_number(num) -> str:
    try:
        return f"{float(num):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(num)


def split_text(text: str, limit: int = 3800) -> list[str]:
    parts = []
    while len(text) > limit:
        idx = text.rfind("\n", 0, limit)
        if idx == -1:
            idx = limit
        parts.append(text[:idx])
        text = text[idx:]
    if text:
        parts.append(text)
    return parts


def parse_amount(raw: str):
    if raw is None:
        return None
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    try:
        value = float(cleaned)
        return value
    except ValueError:
        return None


async def answer_with_photo(message: Message, photo_path: str, caption: str, reply_markup=None):
    try:
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        logging.warning(f"Не удалось отправить фото {photo_path}: {e}")
        await message.answer(caption, reply_markup=reply_markup)


async def replace_with_photo(callback: CallbackQuery, photo_path: str, caption: str, reply_markup=None):
    await answer_with_photo(callback.message, photo_path, caption, reply_markup)
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить предыдущее сообщение: {e}")


async def show_day_with_photo(callback: CallbackQuery, photo_path: str,
                                short_caption: str, full_text: str, reply_markup=None):
    await answer_with_photo(callback.message, photo_path, short_caption)
    await callback.message.answer(full_text, reply_markup=reply_markup)
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить предыдущее сообщение: {e}")


async def replace_with_text(callback: CallbackQuery, text: str, reply_markup=None):
    await callback.message.answer(text, reply_markup=reply_markup)
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить предыдущее сообщение: {e}")
