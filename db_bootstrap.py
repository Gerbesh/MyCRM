import os
import shutil
from datetime import datetime

from sqlalchemy import MetaData, create_engine, inspect, text

from database import db


def bootstrap_db(app):
    """Переносит данные из SQLite в MySQL при первом запуске."""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not uri.startswith("mysql"):
        app.logger.info("спользуется не MySQL, перенос не требуется")
        return

    sqlite_path = os.path.join(app.instance_path, "app.db")
    if not os.path.exists(sqlite_path):
        app.logger.info("Файл SQLite не найден, пропускаем перенос")
        return

    mysql_engine = db.engine
    if inspect(mysql_engine).get_table_names():
        app.logger.info("MySQL уже содержит таблицы, пропускаем перенос")
        return

    backup_dir = os.path.join(app.instance_path, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_name = f"app-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    backup_path = os.path.join(backup_dir, backup_name)
    shutil.copy2(sqlite_path, backup_path)
    app.logger.info(f"Создан бэкап SQLite: {backup_path}")

    app.logger.info("Создание схемы БД в MySQL")
    db.create_all()

    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
    mysql_meta = MetaData()
    mysql_meta.reflect(bind=mysql_engine)
    sqlite_meta = MetaData()
    sqlite_meta.reflect(bind=sqlite_engine)

    with sqlite_engine.connect() as s_conn, mysql_engine.begin() as m_conn:
        m_conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in sqlite_meta.sorted_tables:
            if table.name == "alembic_version":
                continue
            target = mysql_meta.tables.get(table.name)
            if target is None:
                app.logger.warning(f"Таблица {table.name} отсутствует в MySQL")
                continue
            app.logger.info(f"Перенос таблицы {table.name}")
            result = s_conn.execute(table.select())
            while True:
                rows = result.fetchmany(1000)
                if not rows:
                    break
                m_conn.execute(target.insert(), [dict(row._mapping) for row in rows])
        m_conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    sqlite_engine.dispose()
    mysql_engine.dispose()

    os.remove(sqlite_path)
    app.logger.info("Перенос завершён, файл SQLite удалён")
