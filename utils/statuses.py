from enum import Enum


class RequestStatus(str, Enum):
    """Unified request statuses."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ACCEPTED = "ACCEPTED"
    ASSIGNED = "ASSIGNED"
    DONE = "DONE"
    REJECTED = "REJECTED"
    NEED_INFO = "NEED_INFO"

    @classmethod
    def all(cls):
        """Вернуть список кодов статусов без префикса класса."""
        return [status.value for status in cls]

    @classmethod
    def filter_list(cls):
        """Список статусов для фильтра на дашборде (без DONE) в нужном порядке."""
        return [
            cls.OPEN.value,
            cls.IN_PROGRESS.value,
            cls.ACCEPTED.value,
            cls.ASSIGNED.value,
            cls.REJECTED.value,
            cls.NEED_INFO.value,
        ]


_STATUS_LABELS_RU = {
    "OPEN": "Открыта",
    "IN_PROGRESS": "В работе",
    "ACCEPTED": "Приняты",
    "ASSIGNED": "Закреплены",
    "DONE": "Завершена",
    "REJECTED": "Отказ",
    "NEED_INFO": "Запрос информации",
}


def get_status_label(value: str) -> str:
    """Вернуть русскую подпись статуса по коду Enum."""
    return _STATUS_LABELS_RU.get(value, value)


def get_status_class(value: str) -> str:
    """Вернуть CSS-класс (окончание) для отображения статуса в таблицах/бейджах.

    Карта цветов по требованиям:
    - Запрос информации/Отказ -> красный
    - Открыта/В работе -> синий
    - Приняты -> светло-салатовый (success-light)
    - Закреплены -> ярко-зелёный (цвет выделения)
    - Завершена -> светло-салатовый (как processed)
    """
    if value in {RequestStatus.NEED_INFO.value, RequestStatus.REJECTED.value}:
        return "danger"
    if value in {RequestStatus.OPEN.value, RequestStatus.IN_PROGRESS.value}:
        return "info"
    if value == RequestStatus.ASSIGNED.value:
        return "success-strong"
    if value in {RequestStatus.ACCEPTED.value, RequestStatus.DONE.value}:
        return "success"
    # значение по умолчанию
    return "info"
