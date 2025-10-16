from models import Object, Request


def test_add_comment_returns_html(admin_client, db, admin_user):
    obj = Object(name="Объект")
    db.session.add(obj)
    db.session.commit()
    req = Request(object_id=obj.id, manufacturers="Test", created_by=admin_user.id)
    db.session.add(req)
    db.session.commit()

    resp = admin_client.post(
        f"/requests/comment/add_comment/{req.id}",
        data={"content": "Привет"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "rendered_html" in data
    rendered_html = data["rendered_html"]
    assert "delete-comment-btn" in rendered_html
    assert "title=\"Удалить комментарий\"" in rendered_html
