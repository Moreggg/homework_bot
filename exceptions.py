class UnknownStatusError(Exception):
    """Исключение выбрасывается, когда API возвращает домашку без статуса.
    Или когда возвращается недокументированный статус домашки.
    """

    pass


class MissedTokensError(Exception):
    """Исключение выбрасывается при отсутствии любой переменной окружения."""

    pass


class EmptyResponseFromAPI(Exception):
    """Исключение выбрасывается, когда в ответе от API нет ожидаемых данных."""

    pass
