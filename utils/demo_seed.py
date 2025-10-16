"""Генерация демо-данных для CRM."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from database import db
from models import Comment, Contractor, Object, Request, User
from utils.constants import MANUFACTURERS
from utils.statuses import RequestStatus
from werkzeug.security import generate_password_hash


@dataclass(slots=True)
class DemoSeedResult:
    """Результат генерации демо-данных."""

    created_contractors: int = 0
    created_objects: int = 0
    created_requests: int = 0
    created_comments: int = 0
    skipped: bool = False
    reason: str = ""


class DemoDataGenerator:
    """Генератор тестовой БД с случайными сущностями."""

    def __init__(
        self,
        target_contractors: int,
        target_objects: int,
        target_requests: int,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.target_contractors = max(0, int(target_contractors))
        self.target_objects = max(0, int(target_objects))
        self.target_requests = max(0, int(target_requests))
        self.logger = logger or logging.getLogger(__name__)

        if self.target_requests <= 0:
            raise ValueError("Количество заявок должно быть больше нуля")

    def run(self) -> DemoSeedResult:
        """Запускает генерацию демо-данных."""

        current_requests = Request.query.count()
        if current_requests >= self.target_requests:
            self.logger.info(
                "Пропускаем генерацию демо-данных: %s заявок уже есть",
                current_requests,
            )
            return DemoSeedResult(skipped=True, reason="enough_requests")

        self._ensure_users_exist()

        result = DemoSeedResult()
        result.created_contractors = self._ensure_contractors()
        result.created_objects = self._ensure_objects()
        created_requests, created_comments = self._create_requests()
        result.created_requests = created_requests
        result.created_comments = created_comments
        return result

    def _ensure_users_exist(self) -> None:
        """Создаёт базовых пользователей, если их нет."""

        if User.query.count() > 0:
            return

        now = datetime.utcnow()
        admin = User(
            username="demo_admin",
            password=generate_password_hash("demo_admin"),
            role="admin",
            created_at=now,
        )

        db.session.add(admin)
        db.session.commit()
        self.logger.info("Создан базовый администратор demo_admin для демо-данных")

    def _ensure_contractors(self) -> int:
        """Создаёт недостающих подрядчиков."""

        existing = Contractor.query.count()
        to_create = max(0, self.target_contractors - existing)
        if to_create == 0:
            return 0

        created = 0
        batch: list[Contractor] = []
        now = datetime.utcnow()
        for idx in range(to_create):
            seq = existing + idx + 1
            contractor = Contractor(
                name=f"Подрядчик №{seq}",
                inn=f"{7000000000 + seq:010d}",
                contact_person=f"Контакт {seq}",
                phone=f"+7{9000000000 + seq:010d}",
                email=f"contractor{seq}@demo.local",
                created_at=now - timedelta(days=random.randint(0, 120)),
            )
            batch.append(contractor)
            if len(batch) >= 200:
                db.session.add_all(batch)
                db.session.commit()
                created += len(batch)
                batch.clear()

        if batch:
            db.session.add_all(batch)
            db.session.commit()
            created += len(batch)

        self.logger.info("Создано подрядчиков: %s", created)
        return created

    def _ensure_objects(self) -> int:
        """Создаёт недостающие объекты."""

        existing = Object.query.count()
        to_create = max(0, self.target_objects - existing)
        if to_create == 0:
            return 0

        created = 0
        batch: list[Object] = []
        now = datetime.utcnow()
        cities = [
            "Москва",
            "Санкт-Петербург",
            "Казань",
            "Новосибирск",
            "Екатеринбург",
            "Краснодар",
            "Самара",
            "Воронеж",
        ]

        for idx in range(to_create):
            seq = existing + idx + 1
            city = random.choice(cities)
            obj = Object(
                name=f"Объект №{seq}",
                address=f"{city}, улица {seq}",
                customer=f"Заказчик {seq}",
                phone=f"+7{8000000000 + seq:010d}",
                created_at=now - timedelta(days=random.randint(0, 180)),
            )
            batch.append(obj)
            if len(batch) >= 200:
                db.session.add_all(batch)
                db.session.commit()
                created += len(batch)
                batch.clear()

        if batch:
            db.session.add_all(batch)
            db.session.commit()
            created += len(batch)

        self.logger.info("Создано объектов: %s", created)
        return created

    def _create_requests(self) -> tuple[int, int]:
        """Создаёт заявки и связанные комментарии."""

        contractors = Contractor.query.order_by(Contractor.id).all()
        objects = Object.query.order_by(Object.id).all()
        users = User.query.order_by(User.id).all()

        if not contractors or not objects or not users:
            raise RuntimeError("Для генерации заявок нужны пользователи, подрядчики и объекты")

        existing_requests = Request.query.count()
        to_create = max(0, self.target_requests - existing_requests)
        if to_create == 0:
            return 0, 0

        statuses = list(RequestStatus.all())
        processed_statuses = {
            RequestStatus.IN_PROGRESS.value,
            RequestStatus.ACCEPTED.value,
            RequestStatus.ASSIGNED.value,
            RequestStatus.DONE.value,
            RequestStatus.REJECTED.value,
        }
        now = datetime.utcnow()
        created_requests = 0
        created_comments = 0
        comment_templates = [
            "Заявка взята в работу",
            "Ожидаем подтверждение от подрядчика",
            "Получены обновлённые данные от клиента",
            "Подготовлены документы",
            "Заявка завершена",
        ]

        batch_size = 200
        pending: list[Request] = []

        for idx in range(to_create):
            created_at = now - timedelta(days=random.randint(0, 180), minutes=random.randint(0, 1440))
            manufacturers = random.sample(
                MANUFACTURERS,
                k=min(len(MANUFACTURERS), random.randint(1, min(4, len(MANUFACTURERS)))),
            )
            status = random.choice(statuses)
            request = Request(
                object_id=random.choice(objects).id,
                manufacturers=",".join(manufacturers),
                status=status,
                created_by=random.choice(users).id,
                created_at=created_at,
            )

            if status in processed_statuses:
                request.processed_by = random.choice(users).id
                processed_at = created_at + timedelta(days=random.randint(0, 60), minutes=random.randint(0, 720))
                request.processed_at = min(processed_at, now)
                if status == RequestStatus.DONE.value:
                    processed = random.sample(manufacturers, k=random.randint(1, len(manufacturers)))
                    request.processed_manufacturers = ",".join(processed)

            contractor_count = random.randint(1, min(3, len(contractors)))
            request.contractors = random.sample(contractors, k=contractor_count)

            db.session.add(request)
            created_requests += 1
            pending.append(request)

            if random.random() < 0.3:
                last_time = created_at
                for _ in range(random.randint(1, 3)):
                    delta = timedelta(hours=random.randint(1, 72))
                    comment_time = min(last_time + delta, now)
                    comment = Comment(
                        request=request,
                        user_id=random.choice(users).id,
                        content=random.choice(comment_templates),
                        created_at=comment_time,
                    )
                    db.session.add(comment)
                    created_comments += 1
                    last_time = comment_time

            if len(pending) >= batch_size:
                db.session.flush()
                db.session.commit()
                pending.clear()

        if pending:
            db.session.flush()
            db.session.commit()

        self.logger.info(
            "Созданы заявки: %s, комментарии: %s",
            created_requests,
            created_comments,
        )
        return created_requests, created_comments


def generate_demo_data(
    contractors: int,
    objects: int,
    requests: int,
    *,
    logger: logging.Logger | None = None,
) -> DemoSeedResult:
    """Создаёт тестовую БД согласно заданным лимитам."""

    generator = DemoDataGenerator(
        contractors,
        objects,
        requests,
        logger=logger,
    )
    return generator.run()

