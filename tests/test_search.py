from models import Object


def test_search_objects_pagination(admin_client, db):
    # создаём 15 объектов с похожими именами
    for i in range(15):
        db.session.add(Object(name=f"Obj{i}"))
    db.session.commit()
    resp1 = admin_client.get("/search/search_objects?query=Obj&page=1")
    data1 = resp1.get_json()
    assert data1["has_next"] is True
    assert len(data1["items"]) == 10
    resp2 = admin_client.get("/search/search_objects?query=Obj&page=2")
    data2 = resp2.get_json()
    assert data2["has_next"] is False
    assert len(data2["items"]) == 5
