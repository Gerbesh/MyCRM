from datetime import datetime

from flask_login import UserMixin

from database import db
from utils.statuses import RequestStatus

from .op import OpComment, OpFile, OpKPCategory  # noqa: F401

# Определяем таблицу-ассоциацию ДО моделей
request_contractor = db.Table(
    "request_contractor",
    db.Column("request_id", db.Integer, db.ForeignKey("request.id"), primary_key=True),
    db.Column(
        "contractor_id", db.Integer, db.ForeignKey("contractor.id"), primary_key=True
    ),
)


class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(50), unique=True, nullable=False, index=True
    )  # ндекс для поиска
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(10), nullable=False, default="user", index=True
    )  # ндекс для фильтрации
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, index=True
    )  # ндекс для сортировки
    requests_created = db.relationship(
        "Request", foreign_keys="Request.created_by", backref="creator", lazy=True
    )
    requests_processed = db.relationship(
        "Request", foreign_keys="Request.processed_by", backref="processor", lazy=True
    )
    comments = db.relationship("Comment", backref="user", lazy=True)

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


class Object(db.Model):
    __tablename__ = "object"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)  # ндекс для поиска
    address = db.Column(db.String(300), index=True)  # ндекс для поиска по адресу
    customer = db.Column(db.String(200), index=True)  # ндекс для поиска по заказчику
    phone = db.Column(db.String(20))  # Телефон заказчика
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, index=True
    )  # ндекс для сортировки

    def __repr__(self):
        return f"<Object {self.name}>"


class Contractor(db.Model):
    __tablename__ = "contractor"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)  # Уже есть индекс
    inn = db.Column(db.String(12), unique=True, index=True)  # НН (с индексом)
    contact_person = db.Column(db.String(200))  # Контактное лицо
    phone = db.Column(db.String(20), index=True)  # Телефон (с индексом)
    email = db.Column(db.String(100), index=True)  # Email (с индексом)
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, index=True
    )  # ндекс для сортировки

    def __repr__(self):
        return f"<Contractor {self.name}>"


class Request(db.Model):
    __tablename__ = "request"
    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(
        db.Integer, db.ForeignKey("object.id"), nullable=False, index=True
    )  # ндекс FK
    # legacy field removed by migration 9c2e5d7810ba
    # contractor_ids = db.Column(db.String(255), nullable=True)
    manufacturers = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255))
    status = db.Column(
        db.String(20), default=RequestStatus.OPEN.value, index=True
    )  # ндекс для фильтрации
    created_by = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )  # ндекс FK
    processed_by = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=True
    )  # ндекс FK
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, index=True
    )  # ндекс для сортировки
    processed_at = db.Column(db.DateTime, index=True)  # ндекс для сортировки
    processed_manufacturers = db.Column(db.String(500), default="")
    comments = db.relationship("Comment", backref="request", lazy=True)
    object = db.relationship("Object", backref=db.backref("requests", lazy="dynamic"))
    # Many-to-many: associated contractors for this request
    # backref: Contractor.requests
    contractors = db.relationship(
        "Contractor",
        secondary=request_contractor,
        lazy="selectin",
        backref=db.backref("requests", lazy="selectin"),
    )

    @property
    def processed_manufacturers_list(self):
        return (self.processed_manufacturers or "").split(",")

    @property
    def manufacturers_list(self):
        return self.manufacturers.split(",")

    @property
    def contractor_id(self) -> int | None:
        """Back-compat: first contractor id via M2M relation."""
        if not self.contractors:
            return None
        return self.contractors[0].id if len(self.contractors) > 0 else None

    @contractor_id.setter
    def contractor_id(self, value: int | None):
        """Back-compat setter: set single contractor by id."""
        from models import Contractor

        if value is None:
            self.contractors = []
            return
        cid = int(value)
        cont = Contractor.query.get(cid)
        self.contractors = [cont] if cont else []

    @property
    def contractor_ids_list(self):
        """Back-compat: list of contractor IDs based on M2M relation."""
        return [c.id for c in (self.contractors or [])]


class Attachment(db.Model):
    __tablename__ = "attachment"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("request.id"), nullable=False, index=True
    )  # ндекс FK
    contractor_id = db.Column(
        db.Integer, db.ForeignKey("contractor.id"), nullable=False, index=True
    )  # ндекс FK
    manufacturer = db.Column(
        db.String(100), nullable=False, index=True
    )  # ндекс для поиска
    screenshot = db.Column(db.String(200), nullable=False)
    uploaded_by = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )  # ндекс FK
    uploaded_at = db.Column(
        db.DateTime, default=datetime.utcnow, index=True
    )  # ндекс для сортировки

    # Связи
    request = db.relationship("Request", backref="attachments")
    contractor = db.relationship("Contractor", backref="attachments")
    uploader = db.relationship("User")

    # Составной индекс для оптимизации частых запросов
    __table_args__ = (
        db.Index("idx_request_contractor", "request_id", "contractor_id"),
        db.Index("idx_request_manufacturer", "request_id", "manufacturer"),
    )


class Comment(db.Model):
    __tablename__ = "comment"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("request.id"), nullable=False, index=True
    )  # ндекс FK
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )  # ндекс FK
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, index=True
    )  # ндекс для сортировки


# Нормализация contractor_ids перед вставкой/обновлением
# legacy normalization removed; M2M relation is authoritative
