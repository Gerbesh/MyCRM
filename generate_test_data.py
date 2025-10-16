#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для генерации тестовых данных в базе данных CRM системы.
Создает:
- 100 подрядчиков
- 400 объектов
- 4000 заявок с различными комбинациями подрядчиков и объектов
- Случайные комментарии и статусы
"""

import os
import random
import sys
from datetime import datetime, timedelta

try:
    from faker import Faker
except ImportError:
    print("Пакет faker не установлен. Установите его: pip install faker")
    sys.exit(1)

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from werkzeug.security import generate_password_hash

from app import app, db
from models import Comment, Contractor, Object, Request, User

# нициализация Faker с русской локалью
fake = Faker("ru_RU")

# Константы для генерации данных
CONTRACTORS_COUNT = 100
OBJECTS_COUNT = 400
REQUESTS_COUNT = 4000

# Списки для реалистичных данных
MANUFACTURING_COMPANIES = [
    "Apple",
    "Samsung",
    "LG",
    "Sony",
    "Panasonic",
    "Bosch",
    "Siemens",
    "Schneider Electric",
    "ABB",
    "Legrand",
    "Philips",
    "Osram",
    "General Electric",
    "Honeywell",
    "Johnson Controls",
    "Carrier",
    "Daikin",
    "Mitsubishi",
    "Hitachi",
    "Toshiba",
    "Fujitsu",
    "Canon",
    "Epson",
    "HP",
    "Dell",
    "Cisco",
    "Huawei",
    "Xiaomi",
    "Haier",
    "Midea",
    "Gree",
    "TCL",
    "Hisense",
    "Skyworth",
    "Changhong",
    "Konka",
    "Sharp",
    "JVC",
    "Pioneer",
    "Yamaha",
    "Denon",
    "Marantz",
    "Onkyo",
    "Technics",
]

REQUEST_STATUSES = [
    "не обработано",
    "в процессе",
    "завершено",
    "отклонено",
    "требует уточнения",
]

OBJECT_TYPES = [
    "Торговый центр",
    "Офисное здание",
    "Жилой комплекс",
    "Производственное здание",
    "Склад",
    "Медицинский центр",
    "Школа",
    "Детский сад",
    "Спортивный комплекс",
    "Гостиница",
]

CONTRACTOR_SPECIALIZATIONS = [
    "Электромонтажные работы",
    "Системы вентиляции",
    "Охранные системы",
    "Пожарная безопасность",
    "Системы кондиционирования",
    "Слаботочные системы",
    "Системы видеонаблюдения",
    "Контроль доступа",
    "Сетевые технологии",
    "Автоматизация зданий",
]

CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Челябинск",
    "Самара",
    "Омск",
    "Ростов-на-Дону",
    "Уфа",
    "Красноярск",
    "Воронеж",
    "Пермь",
    "Волгоград",
    "Краснодар",
    "Саратов",
    "Тюмень",
    "Тольятти",
]


def generate_inn():
    """Генерирует валидный НН для юридического лица (10 цифр)"""
    return "".join([str(random.randint(0, 9)) for _ in range(10)])


def generate_phone():
    """Генерирует российский номер телефона"""
    return f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"


def create_contractors():
    """Создает подрядчиков"""
    print(f"Создание {CONTRACTORS_COUNT} подрядчиков...")

    contractors = []
    used_inns = set()

    # Получаем существующие НН
    existing_contractors = Contractor.query.all()
    for contractor in existing_contractors:
        if contractor.inn:
            used_inns.add(contractor.inn)

    for i in range(CONTRACTORS_COUNT):
        # Генерируем уникальный НН
        attempts = 0
        while attempts < 100:
            inn = generate_inn()
            if inn not in used_inns:
                used_inns.add(inn)
                break
            attempts += 1

        if attempts >= 100:
            inn = f"9999{random.randint(100000, 999999)}"

        specialization = random.choice(CONTRACTOR_SPECIALIZATIONS)
        company_name = f"{fake.company()} ({specialization})"

        contractor = Contractor(
            name=company_name,
            inn=inn,
            contact_person=fake.name(),
            phone=generate_phone(),
            email=fake.email(),
            created_at=fake.date_time_between(start_date="-2y", end_date="now"),
        )

        contractors.append(contractor)

        if (i + 1) % 20 == 0:
            print(f"  Создано {i + 1}/{CONTRACTORS_COUNT} подрядчиков")

    # Сохраняем пакетами
    batch_size = 20
    saved_count = 0
    for i in range(0, len(contractors), batch_size):
        batch = contractors[i : i + batch_size]
        try:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            saved_count += len(batch)
        except Exception as e:
            print(f"  Ошибка при сохранении пакета {i // batch_size + 1}: {e}")
            db.session.rollback()
            # Пробуем сохранить по одному
            for contractor in batch:
                try:
                    db.session.add(contractor)
                    db.session.commit()
                    saved_count += 1
                except Exception as e2:
                    print(f"    Пропущен подрядчик: {contractor.name} - {e2}")
                    db.session.rollback()

    print(f"✓ Создано {saved_count} подрядчиков")

    return Contractor.query.all()


def create_objects():
    """Создает объекты"""
    print(f"Создание {OBJECTS_COUNT} объектов...")

    objects = []
    used_names = set()

    # Получаем существующие имена объектов
    existing_objects = Object.query.all()
    for obj in existing_objects:
        used_names.add(obj.name)

    for i in range(OBJECTS_COUNT):
        city = random.choice(CITIES)
        object_type = random.choice(OBJECT_TYPES)

        # Генерируем уникальное название объекта
        attempts = 0
        while attempts < 100:  # Максимум 100 попыток генерации уникального имени
            if object_type == "Торговый центр":
                name = (
                    f"ТЦ {fake.word().title()}-"
                    f"{random.choice(['Plaza', 'Mall', 'Center', 'Park'])}-"
                    f"{random.randint(1, 999)}"
                )
            elif object_type == "Офисное здание":
                name = (
                    f"БЦ {fake.word().title()}-"
                    f"{random.choice(['Tower', 'City', 'Plaza', 'Center'])}-"
                    f"{random.randint(1, 999)}"
                )
            elif object_type == "Жилой комплекс":
                name = (
                    f"ЖК {fake.word().title()}-"
                    f"{random.choice(['Парк', 'Сити', 'Плаза', 'Дом'])}-"
                    f"{random.randint(1, 999)}"
                )
            else:
                name = f"{object_type} {fake.word().title()}-{random.randint(1, 999)}"

            if name not in used_names:
                used_names.add(name)
                break
            attempts += 1

        if attempts >= 100:
            name = f"{object_type} №{i + 1}-{fake.uuid4()[:8]}"

        obj = Object(
            name=name,
            address=f"{city}, {fake.street_address()}",
            customer=fake.company(),
            phone=generate_phone(),
            created_at=fake.date_time_between(start_date="-1y", end_date="now"),
        )

        objects.append(obj)

        if (i + 1) % 50 == 0:
            print(f"  Создано {i + 1}/{OBJECTS_COUNT} объектов")

    # Сохраняем пакетами для избежания проблем с уникальностью
    batch_size = 50
    saved_count = 0
    for i in range(0, len(objects), batch_size):
        batch = objects[i : i + batch_size]
        try:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            saved_count += len(batch)
        except Exception as e:
            print(f"  Ошибка при сохранении пакета {i // batch_size + 1}: {e}")
            db.session.rollback()
            # Пробуем сохранить по одному
            for obj in batch:
                try:
                    db.session.add(obj)
                    db.session.commit()
                    saved_count += 1
                except Exception as e2:
                    print(f"    Пропущен объект: {obj.name} - {e2}")
                    db.session.rollback()

    print(f"✓ Создано {saved_count} объектов")

    return Object.query.all()


def create_requests(contractors, objects, users):
    """Создает заявки"""
    print(f"Создание {REQUESTS_COUNT} заявок...")

    requests = []

    contractor_ids = [c.id for c in contractors]
    object_ids = [o.id for o in objects]
    user_ids = [u.id for u in users]

    for i in range(REQUESTS_COUNT):
        # Случайный выбор объекта
        object_id = random.choice(object_ids)

        # Случайный выбор 1-5 подрядчиков
        num_contractors = random.randint(1, 5)
        selected_contractors = random.sample(contractor_ids, num_contractors)
        contractor_ids_str = ",".join(map(str, selected_contractors))

        # Случайный выбор 1-4 производителей
        num_manufacturers = random.randint(1, 4)
        manufacturers = random.sample(MANUFACTURING_COMPANIES, num_manufacturers)
        manufacturers_str = ",".join(manufacturers)

        # Случайный статус (большинство "не обработано")
        status = random.choices(
            REQUEST_STATUSES,
            weights=[50, 25, 15, 5, 5],  # Больше необработанных заявок
        )[0]

        if status not in REQUEST_STATUSES:
            raise ValueError(f"Недопустимый статус: {status}")

        # Время создания в последние 6 месяцев
        created_at = fake.date_time_between(start_date="-6M", end_date="now")

        # Создатель заявки
        created_by = random.choice(user_ids)

        # Обработчик (если заявка в процессе или завершена)
        processed_by = None
        processed_at = None
        processed_manufacturers = ""

        if status in ["в процессе", "завершено", "отклонено"]:
            processed_by = random.choice(user_ids)
            processed_at = fake.date_time_between(start_date=created_at, end_date="now")

            if processed_by not in user_ids:
                raise ValueError(f"Некорректный обработчик: {processed_by}")

            # Для завершенных заявок добавляем обработанных производителей
            if status == "завершено":
                processed_count = random.randint(1, len(manufacturers))
                processed_manufacturers = ",".join(
                    random.sample(manufacturers, processed_count)
                )

        request = Request(
            object_id=object_id,
            contractor_ids=contractor_ids_str,
            manufacturers=manufacturers_str,
            status=status,
            created_by=created_by,
            processed_by=processed_by,
            created_at=created_at,
            processed_at=processed_at,
            processed_manufacturers=processed_manufacturers,
        )

        requests.append(request)

        if (i + 1) % 500 == 0:
            print(f"  Создано {i + 1}/{REQUESTS_COUNT} заявок")

    # Сохраняем пакетами для лучшей производительности
    batch_size = 500
    for i in range(0, len(requests), batch_size):
        batch = requests[i : i + batch_size]
        db.session.bulk_save_objects(batch)
        db.session.commit()

    print(f"✓ Создано {len(requests)} заявок")

    return requests


def create_comments(requests, users):
    """Создает случайные комментарии к заявкам"""
    print("Создание комментариев...")

    comments = []
    user_ids = [u.id for u in users]

    # Получаем созданные заявки из БД чтобы у них были ID
    all_requests = Request.query.all()

    # Добавляем комментарии к 30% заявок
    requests_with_comments = random.sample(
        all_requests, min(int(len(all_requests) * 0.3), len(all_requests))
    )

    comment_templates = [
        "Заявка принята в работу",
        "Требуется дополнительная информация от заказчика",
        "Связались с подрядчиком, ожидаем ответ",
        "Получены предложения от всех подрядчиков",
        "Заявка выполнена, документы отправлены",
        "Требуется уточнение по техническим характеристикам",
        "Подрядчик запросил дополнительное время",
        "Все документы получены и проверены",
        "Заявка закрыта по требованию заказчика",
        "Переданы контакты ответственного лица",
    ]

    for request in requests_with_comments:
        # От 1 до 5 комментариев на заявку
        num_comments = random.randint(1, 5)

        last_comment_time = request.created_at

        for j in range(num_comments):
            content = random.choice(comment_templates)

            # Комментарии должны быть после создания заявки
            comment_time = fake.date_time_between(
                start_date=last_comment_time, end_date="now"
            )

            comment = Comment(
                request_id=request.id,  # Явно указываем request_id
                user_id=random.choice(user_ids),
                content=content,
                created_at=comment_time,
            )

            comments.append(comment)
            last_comment_time = comment_time

    # Сохраняем пакетами
    batch_size = 100
    saved_count = 0
    for i in range(0, len(comments), batch_size):
        batch = comments[i : i + batch_size]
        try:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            saved_count += len(batch)
        except Exception as e:
            print(f"  Ошибка при сохранении комментариев: {e}")
            db.session.rollback()
            # Пробуем сохранить по одному
            for comment in batch:
                try:
                    db.session.add(comment)
                    db.session.commit()
                    saved_count += 1
                except Exception as e2:
                    print(f"    Пропущен комментарий: {e2}")
                    db.session.rollback()

    print(f"✓ Создано {saved_count} комментариев")


def ensure_test_users():
    """Создает тестовых пользователей если их нет"""
    users = User.query.all()

    if len(users) < 5:  # Создаем минимум 5 пользователей
        print("Создание дополнительных тестовых пользователей...")

        test_users = []

        # Администратор
        if not User.query.filter_by(username="admin").first():
            admin = User(
                username="admin",
                password=generate_password_hash("admin"),
                role="admin",
                created_at=datetime.utcnow() - timedelta(days=365),
            )
            test_users.append(admin)

        # Обычные пользователи
        user_names = ["manager1", "manager2", "operator1", "operator2"]
        for username in user_names:
            if not User.query.filter_by(username=username).first():
                user = User(
                    username=username,
                    password=generate_password_hash("password"),
                    role="user" if "operator" in username else "manager",
                    created_at=fake.date_time_between(start_date="-1y", end_date="now"),
                )
                test_users.append(user)

        if test_users:
            db.session.bulk_save_objects(test_users)
            db.session.commit()
            print(f"✓ Создано {len(test_users)} пользователей")

    return User.query.all()


def print_statistics():
    """Выводит статистику созданных данных"""
    print("\n" + "=" * 60)
    print("СТАТСТКА СОЗДАННЫХ ДАННЫХ")
    print("=" * 60)

    users_count = User.query.count()
    contractors_count = Contractor.query.count()
    objects_count = Object.query.count()
    requests_count = Request.query.count()
    comments_count = Comment.query.count()

    print(f"Пользователи:     {users_count:4d}")
    print(f"Подрядчики:       {contractors_count:4d}")
    print(f"Объекты:          {objects_count:4d}")
    print(f"Заявки:           {requests_count:4d}")
    print(f"Комментарии:      {comments_count:4d}")

    # Статистика по статусам заявок
    print("\nРаспределение заявок по статусам:")
    for status in REQUEST_STATUSES:
        count = Request.query.filter_by(status=status).count()
        percentage = (count / requests_count * 100) if requests_count > 0 else 0
        print(f"  {status:20s}: {count:4d} ({percentage:5.1f}%)")

    print("\n" + "=" * 60)


def main():
    """Основная функция генерации тестовых данных"""
    print("ГЕНЕРАЦЯ ТЕСТОВЫХ ДАННЫХ ДЛЯ CRM ССТЕМЫ")
    print("=" * 60)

    with app.app_context():
        try:
            # Проверяем текущее состояние БД
            existing_requests = Request.query.count()
            existing_contractors = Contractor.query.count()
            existing_objects = Object.query.count()

            print("Текущее состояние БД:")
            print(f"  Заявки: {existing_requests}")
            print(f"  Подрядчики: {existing_contractors}")
            print(f"  Объекты: {existing_objects}")

            if existing_requests > 1000:
                response = input(
                    f"\nВ БД уже есть {existing_requests} заявок. Продолжить? (y/N): "
                )
                if response.lower() != "y":
                    print("Генерация отменена.")
                    return

            print("\nНачинаем генерацию тестовых данных...")
            start_time = datetime.now()

            # 1. Создаем/проверяем пользователей
            users = ensure_test_users()

            # 2. Создаем подрядчиков
            contractors = create_contractors()

            # 3. Создаем объекты
            objects = create_objects()

            # 4. Создаем заявки
            requests = create_requests(contractors, objects, users)

            # 5. Создаем комментарии
            create_comments(requests, users)

            end_time = datetime.now()
            duration = end_time - start_time

            print("\n✓ Генерация завершена успешно!")
            print(f"Время выполнения: {duration.total_seconds():.1f} секунд")

            # Выводим статистику
            print_statistics()

        except Exception as e:
            print(f"\n❌ Ошибка при генерации данных: {str(e)}")
            db.session.rollback()
            raise


if __name__ == "__main__":
    main()
