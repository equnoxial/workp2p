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