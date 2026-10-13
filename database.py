import random
import string
import aiosqlite

from config import DB_PATH


def _generate_key_candidate() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"P2P-{suffix}"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                number INTEGER PRIMARY KEY,
                secret_key TEXT UNIQUE NOT NULL,
                telegram_id INTEGER UNIQUE,
                is_bound INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                number INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                PRIMARY KEY (number, date)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS circles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number INTEGER NOT NULL,
                date TEXT NOT NULL,
                bank TEXT NOT NULL,
                amount_rub REAL NOT NULL,
                payments_count INTEGER NOT NULL,
                profit_usd REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.commit()


async def _find_free_number(db) -> int | None:
    cursor = await db.execute("SELECT number FROM workers")
    taken = {row[0] for row in await cursor.fetchall()}
    for number in range(1000, 2001):
        if number not in taken:
            return number
    return None


async def _insert_new_worker(db, number: int) -> str:
    while True:
        key = _generate_key_candidate()
        cursor = await db.execute("SELECT 1 FROM workers WHERE secret_key = ?", (key,))
        if not await cursor.fetchone():
            break
    await db.execute(
        "INSERT INTO workers (number, secret_key, telegram_id, is_bound) VALUES (?, ?, NULL, 0)",
        (number, key)
    )
    await db.commit()
    return key


async def generate_worker():
    """Создаёт воркера на первом свободном номере 1000-2000. Возвращает (number, key) или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        number = await _find_free_number(db)
        if number is None:
            return None
        key = await _insert_new_worker(db, number)
        return number, key


async def generate_worker_for_number(number: int):
    """Создаёт воркера на конкретном номере, если он свободен и в диапазоне 1000-2000.
    Возвращает ключ или None (номер занят/вне диапазона)."""
    if not (1000 <= number <= 2000):
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT number FROM workers WHERE number = ?", (number,))
        if await cursor.fetchone():
            return None
        key = await _insert_new_worker(db, number)
        return key


async def delete_worker(number: int) -> bool:
    """Полностью удаляет воркера и ВСЮ его статистику, освобождая номер для повторного использования."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT number FROM workers WHERE number = ?", (number,))
        if not await cursor.fetchone():
            return False
        await db.execute("DELETE FROM workers WHERE number = ?", (number,))
        await db.execute("DELETE FROM deposits WHERE number = ?", (number,))
        await db.execute("DELETE FROM circles WHERE number = ?", (number,))
        await db.commit()
        return True


async def get_worker_by_key(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM workers WHERE secret_key = ?", (key,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def bind_worker(number: int, telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE workers SET telegram_id = ?, is_bound = 1 WHERE number = ?",
            (telegram_id, number)
        )
        await db.commit()


async def get_worker_by_telegram_id(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM workers WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_worker_by_number(number: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM workers WHERE number = ?", (number,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_workers():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM workers ORDER BY number")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def set_deposit(number: int, date: str, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO deposits (number, date, amount) VALUES (?, ?, ?) "
            "ON CONFLICT(number, date) DO UPDATE SET amount = excluded.amount",
            (number, date, amount)
        )
        await db.commit()


async def get_deposit(number: int, date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT amount FROM deposits WHERE number = ? AND date = ?",
            (number, date)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_circle(number: int, date: str, bank: str, amount_rub: float, payments_count: int, profit_usd: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO circles (number, date, bank, amount_rub, payments_count, profit_usd) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (number, date, bank, amount_rub, payments_count, profit_usd)
        )
        await db.commit()


async def get_circles(number: int, date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM circles WHERE number = ? AND date = ? ORDER BY id",
            (number, date)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_month_days_with_data(number: int, year: int, month: int):
    prefix = f"{year:04d}-{month:02d}-"
    days = set()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT date FROM deposits WHERE number = ? AND date LIKE ?",
            (number, f"{prefix}%")
        )
        for row in await cursor.fetchall():
            days.add(int(row[0].split("-")[2]))
        cursor = await db.execute(
            "SELECT DISTINCT date FROM circles WHERE number = ? AND date LIKE ?",
            (number, f"{prefix}%")
        )
        for row in await cursor.fetchall():
            days.add(int(row[0].split("-")[2]))
    return days


async def get_month_total_profit(number: int, year: int, month: int) -> float:
    prefix = f"{year:04d}-{month:02d}-"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(profit_usd), 0) FROM circles WHERE number = ? AND date LIKE ?",
            (number, f"{prefix}%")
        )
        row = await cursor.fetchone()
        return row[0] if row else 0.0
