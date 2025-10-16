import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from models import Object, OpComment, OpFile, OpKPCategory


def test_migration_creates_tables(db):
    module = importlib.import_module("migrations.op_module_init")
    conn = db.engine.connect()
    ctx = MigrationContext.configure(conn)
    op = Operations(ctx)
    module.op = op
    for tbl in ("op_comment", "op_file", "op_kp_category"):
        if inspect(db.engine).has_table(tbl):
            db.session.execute(sa.text(f"DROP TABLE {tbl}"))
    db.session.commit()
    module.upgrade()
    conn.commit()
    conn.close()

    inspector = inspect(db.engine)
    assert inspector.has_table("op_comment")
    assert inspector.has_table("op_file")
    assert inspector.has_table("op_kp_category")


def test_models_and_default_categories(db, admin_user):
    obj = Object(name="Test")
    db.session.add(obj)
    db.session.commit()

    cats = OpKPCategory.for_object(obj.id, admin_user.id)
    assert len(cats) == 12
    # Повторный вызов не должен добавлять новые записи
    OpKPCategory.for_object(obj.id, admin_user.id)
    assert OpKPCategory.query.filter_by(object_id=obj.id).count() == 12

    comment = OpComment(object_id=obj.id, user_id=admin_user.id, content="С‚РµСЃС‚")
    file = OpFile(
        object_id=obj.id,
        user_id=admin_user.id,
        filename="f.txt",
        original_name="f.txt",
    )
    db.session.add_all([comment, file])
    db.session.commit()

    assert OpComment.query.count() == 1
    assert OpFile.query.count() == 1
