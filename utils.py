import logging

from aiogram.types import Message, CallbackQuery, FSInputFile


MONTHS_RU = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    """Сдвигает (год, месяц) на delta месяцев (может быть отрицательным)."""
    m = month - 1 + delta
    year += m // 12
    month = m % 12 + 1
    return year, month


def format_number(num) -> str:
    """Форматирует число с разделением тысяч пробелом: 15000 -> '15 000'."""
    try:
        return f"{float(num):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(num)


def split_text(text: str, limit: int = 3800) -> list[str]:
    """Разбивает длинный текст на части для отправки (лимит Telegram ~4096)."""
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
    """
    Безопасный парсинг суммы из текста пользователя.
    Возвращает float или None, если ввод некорректен.
    Поддерживает пробелы, запятые вместо точек.
    """
    if raw is None:
        return None
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    try:
        value = float(cleaned)
        return value
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# ХЕЛПЕРЫ ДЛЯ ОТПРАВКИ ФОТО (используются для Calendar/Statistics/True/False)
# ---------------------------------------------------------------------------

async def answer_with_photo(message: Message, photo_path: str, caption: str, reply_markup=None):
    """
    Отправляет новое сообщение с фото и подписью.
    Если файл не найден/поврежден - автоматически отправляет обычный текст,
    чтобы бот не падал с ошибкой.
    """
    try:
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        logging.warning(f"Не удалось отправить фото {photo_path}: {e}")
        await message.answer(caption, reply_markup=reply_markup)


async def replace_with_photo(callback: CallbackQuery, photo_path: str, caption: str, reply_markup=None):
    """
    Используется в callback-хендлерах (нажатие на инлайн-кнопку):
    отправляет новое сообщение с фото, затем удаляет старое сообщение.
    """
    await answer_with_photo(callback.message, photo_path, caption, reply_markup)
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить предыдущее сообщение: {e}")


async def show_day_with_photo(callback: CallbackQuery, photo_path: str,
                                short_caption: str, full_text: str, reply_markup=None):
    """
    Для статистики дня: отправляет фото с коротким заголовком,
    затем отдельным сообщением - полную статистику с клавиатурой действий.
    Это нужно, так как caption к фото ограничен 1024 символами,
    а полная статистика с кругами может быть длиннее.
    """
    await answer_with_photo(callback.message, photo_path, short_caption)
    await callback.message.answer(full_text, reply_markup=reply_markup)
    try:
        await callback.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить предыдущее сообщение: {e}")
