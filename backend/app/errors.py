class AppError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato. `code` frontendda tarjima uchun ishlatiladi."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


class InsufficientFunds(AppError):
    def __init__(self):
        super().__init__("insufficient_funds", "Balansda mablag' yetarli emas", 402)


class NotFound(AppError):
    def __init__(self, what: str = "Ma'lumot"):
        super().__init__("not_found", f"{what} topilmadi", 404)


class Forbidden(AppError):
    def __init__(self, message: str = "Ruxsat yo'q"):
        super().__init__("forbidden", message, 403)


class BadState(AppError):
    def __init__(self, message: str = "Bu amalni hozir bajarib bo'lmaydi"):
        super().__init__("bad_state", message, 409)
