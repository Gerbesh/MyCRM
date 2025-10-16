from __future__ import annotations

from datetime import datetime

from database import db


class OpComment(db.Model):
    """Комментарий к объекту."""

    __tablename__ = "op_comment"

    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(
        db.Integer, db.ForeignKey("object.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )


class OpFile(db.Model):
    """Метаданные загруженного файла."""

    __tablename__ = "op_file"

    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(
        db.Integer, db.ForeignKey("object.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(255))
    size = db.Column(db.Integer)
    uploaded_at = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )


class OpKPCategory(db.Model):
    """Категория КП (OV/VK)."""

    __tablename__ = "op_kp_category"

    id = db.Column(db.Integer, primary_key=True)
    object_id = db.Column(db.Integer, db.ForeignKey("object.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    side = db.Column(db.String(2), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    is_extra = db.Column(db.Boolean, default=False, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    invoice_number = db.Column(db.String(50))

    __table_args__ = (
        db.Index("ix_op_kp_category_object_id", "object_id"),
        db.Index("ix_op_kp_category_object_side_pos", "object_id", "side", "position"),
    )

    @classmethod
    def ensure_base(cls, object_id: int, user_id: int) -> None:
        """Создаёт 6 базовых категорий при первом обращении."""

        if cls.query.filter_by(object_id=object_id).count() > 0:
            return

        names = [f"Категория {i}" for i in range(1, 7)]
        for side in ("OV", "VK"):
            for pos, name in enumerate(names, start=1):
                db.session.add(
                    cls(
                        object_id=object_id,
                        user_id=user_id,
                        side=side,
                        name=name,
                        position=pos,
                        is_extra=False,
                    )
                )
        db.session.commit()

    @classmethod
    def for_object(cls, object_id: int, user_id: int) -> list["OpKPCategory"]:
        """Возвращает категории объекта, создавая базовые при необходимости."""

        cls.ensure_base(object_id, user_id)
        return (
            cls.query.filter_by(object_id=object_id)
            .order_by(cls.side, cls.position)
            .all()
        )
