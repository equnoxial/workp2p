from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    # Состояние ожидания ввода секретного ключа от пользователя
    waiting_key = State()


class DepositStates(StatesGroup):
    # Состояние ожидания суммы депозита
    waiting_amount = State()


class CircleStates(StatesGroup):
    # Состояния для ведения кругов P2P
    waiting_bank = State()
    waiting_amount = State()
    waiting_payments = State()
    waiting_profit = State()


class AdminStates(StatesGroup):
    # Состояние ожидания номера воркера в админ-панели
    waiting_worker_number = State()
