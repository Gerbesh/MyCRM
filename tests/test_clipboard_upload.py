from io import BytesIO
from pathlib import Path

from models import Attachment, Contractor, Object, Request


def test_clipboard_upload_saves_attachment(app, db, admin_client, admin_user, tmp_path):
    """Проверяет загрузку файла, созданного из буфера обмена."""
    app.config["UPLOAD_FOLDER"] = str(tmp_path)

    obj = Object(name="Объект")
    contractor = Contractor(name="Подрядчик")
    db.session.add_all([obj, contractor])
    db.session.commit()

    req = Request(object_id=obj.id, manufacturers="Пульсар", created_by=admin_user.id)
    req.contractor_id = contractor.id
    db.session.add(req)
    db.session.commit()

    image_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc``\x00\x00\x00\x04\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    data = {
        "contractor_id": str(contractor.id),
        "manufacturers[]": ["Пульсар"],
        "screenshots[]": (BytesIO(image_data), "clip.png"),
    }
    resp = admin_client.post(
        f"/requests/process/submit_process_request/{req.id}",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    attachments = Attachment.query.all()
    assert len(attachments) == 1
    att = attachments[0]
    assert att.manufacturer == "Пульсар"
    file_path = (
        Path(app.config["UPLOAD_FOLDER"]) / str(req.id) / Path(att.screenshot).name
    )
    assert file_path.exists()
