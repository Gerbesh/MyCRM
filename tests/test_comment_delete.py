from models import Comment, Object, Request


def test_delete_comment_admin(admin_client, db, admin_user):
    obj = Object(name="Объект")
    db.session.add(obj)
    db.session.commit()
    req = Request(object_id=obj.id, manufacturers="Test", created_by=admin_user.id)
    db.session.add(req)
    db.session.commit()
    comment = Comment(request_id=req.id, user_id=admin_user.id, content="Тест")
    db.session.add(comment)
    db.session.commit()

    resp = admin_client.post(
        f"/requests/comment/delete_comment/{comment.id}",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert Comment.query.get(comment.id) is None
