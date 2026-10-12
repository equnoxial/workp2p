import random
import string
from datetime import datetime

import aiosqlite

from config import DB_PATH


# ---------------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ БД
# ---------------------------------------------------------------------------

async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                number INTEGER PRIMARY KEY,
                secret_key TEXT UNIQUE NOT NULL,
                telegram_id INTEGER UNIQUE,
                is_bound INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                number INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                PRIMARY KEY (number, date)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS circles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number INTEGER NOT NULL,
                date TEXT NOT NULL,
                bank TEXT NOT NULL,
                amount_rub REAL NOT NULL,
                payments_count INTEGER NOT NULL,
                profit_usd REAL NOT NULL,
                created_at TEXT
            )
        """)
        await conn.commit()


# ---------------------------------------------------------------------------
# WORKERS (НОМЕРА И КЛЮЧИ)
# ---------------------------------------------------------------------------

def _generate_key() -> str:
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"P2P-{suffix}"


async def generate_worker():
    """
    Находит свободный номер от 1000 до 2000, генерирует уникальный ключ,
    создает запись в БД. Возвращает (number, key) или None, если мест нет.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute("SELECT number FROM workers")
        occupied_numbers = {row[0] for row in await cursor.fetchall()}

        free_number = None
        for n in range(1000, 2001):
            if n not in occupied_numbers:
                free_number = n
                break

        if free_number is None:
            return None

        cursor = await conn.execute("SELECT secret_key FROM workers")
        existing_keys = {row[0] for row in await cursor.fetchall()}

        key = _generate_key()
        while key in existing_keys:
            key = _generate_key()

        await conn.execute(
            "INSERT INTO workers (number, secret_key, telegram_id, is_bound, created_at) "
            "VALUES (?, ?, NULL, 0, ?)",
            (free_number, key, datetime.now().isoformat())
        )
        await conn.commit()
        return free_number, key


async def get_worker_by_key(key: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM workers WHERE secret_key = ?", (key,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def bind_worker(number: int, telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE workers SET telegram_id = ?, is_bound = 1 WHERE number = ?",
            (telegram_id, number)
        )
        await conn.commit()


async def get_worker_by_telegram_id(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM workers WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_worker_by_number(number: int):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM workers WHERE number = ?", (number,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_workers():
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM workers ORDER BY number")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# ДЕПОЗИТЫ
# ---------------------------------------------------------------------------

async def set_deposit(number: int, date: str, amount: float):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO deposits (number, date, amount) VALUES (?, ?, ?) "
            "ON CONFLICT(number, date) DO UPDATE SET amount = excluded.amount",
            (number, date, amount)
        )
        await conn.commit()


async def get_deposit(number: int, date: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT amount FROM deposits WHERE number = ? AND date = ?",
            (number, date)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


# ---------------------------------------------------------------------------
# КРУГИ
# ---------------------------------------------------------------------------

async def add_circle(number: int, date: str, bank: str,
                      amount_rub: float, payments_count: int, profit_usd: float):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO circles "
            "(number, date, bank, amount_rub, payments_count, profit_usd, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (number, date, bank, amount_rub, payments_count, profit_usd,
             datetime.now().isoformat())
        )
        await conn.commit()


async def get_circles(number: int, date: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM circles WHERE number = ? AND date = ? ORDER BY id",
            (number, date)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# АГРЕГАЦИЯ ДЛЯ КАЛЕНДАРЯ И АРХИВА
# ---------------------------------------------------------------------------

async def get_month_days_with_data(number: int, year: int, month: int) -> set:
    prefix = f"{year:04d}-{month:02d}-"
    days = set()
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT date FROM deposits WHERE number = ? AND date LIKE ?",
            (number, f"{prefix}%")
        )
        for row in await cursor.fetchall():
            days.add(int(row[0].split("-")[2]))

        cursor = await conn.execute(
            "SELECT DISTINCT date FROM circles WHERE number = ? AND date LIKE ?",
            (number, f"{prefix}%")
        )
        for row in await cursor.fetchall():
            days.add(int(row[0].split("-")[2]))

    return days


async def get_month_total_profit(number: int, year: int, month: int) -> float:
    prefix = f"{year:04d}-{month:02d}-"
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT SUM(profit_usd) FROM circles WHERE number = ? AND date LIKE ?",
            (number, f"{prefix}%")
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] is not None else 0.0