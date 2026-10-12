from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    waiting_key = State()


class DepositStates(StatesGroup):
    waiting_amount = State()


class CircleStates(StatesGroup):
    waiting_bank = State()
    waiting_amount = State()
    waiting_payments = State()
    waiting_profit = State()


class AdminStates(StatesGroup):
    waiting_worker_number = State()