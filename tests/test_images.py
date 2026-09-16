"""佐证图片（任务完成凭证）功能测试 —— v2.1.0。"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta

import pytest
from PyQt6.QtCore import QDateTime

from task_reminder import backup, db, repository as repo
from task_reminder.models import fmt

# 1x1 像素合法 PNG
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLv"
    "AAAAAElFTkSuQmCC")


@pytest.fixture
def image_file(tmp_path):
    p = tmp_path / "p1.png"
    p.write_bytes(PNG_BYTES)
    return p


def _task():
    now = datetime.now()
    return repo.add_task("图片任务", "张三", "内容",
                         fmt(now + timedelta(days=1)), fmt(now + timedelta(hours=1)))


class TestImageCRUD:
    def test_add_and_list(self, image_file):
        tid = _task()
        img = repo.add_task_image(tid, str(image_file))
        assert img.id > 0
        assert img.filename == "p1.png"
        assert img.task_id == tid
        stored = repo.image_path(img)
        assert stored.is_file()
        assert stored.read_bytes() == PNG_BYTES
        imgs = repo.list_task_images(tid)
        assert len(imgs) == 1
        assert imgs[0].stored_name == img.stored_name

    def test_add_multiple(self, tmp_path):
        tid = _task()
        for i in range(3):
            p = tmp_path / f"p{i}.png"
            p.write_bytes(PNG_BYTES)
            repo.add_task_image(tid, str(p))
        assert len(repo.list_task_images(tid)) == 3

    def test_bad_extension(self, tmp_path):
        tid = _task()
        f = tmp_path / "x.txt"
        f.write_text("not image", encoding="utf-8")
        with pytest.raises(repo.ImageError):
            repo.add_task_image(tid, str(f))

    def test_missing_file(self):
        tid = _task()
        with pytest.raises(repo.ImageError):
            repo.add_task_image(tid, "Z:/no/such/path.png")

    def test_missing_task(self, image_file):
        with pytest.raises(repo.ImageError):
            repo.add_task_image(99999, str(image_file))

    def test_size_limit(self, image_file, monkeypatch):
        monkeypatch.setattr(repo, "IMAGE_MAX_BYTES", 10)
        tid = _task()
        with pytest.raises(repo.ImageError):
            repo.add_task_image(tid, str(image_file))

    def test_delete_image_removes_row_and_file(self, image_file):
        tid = _task()
        img = repo.add_task_image(tid, str(image_file))
        stored = repo.image_path(img)
        assert repo.delete_task_image(img.id) is True
        assert not stored.exists()
        assert repo.list_task_images(tid) == []
        assert repo.delete_task_image(img.id) is False   # 再删返回 False

    def test_delete_task_cascades_image(self, image_file):
        tid = _task()
        img = repo.add_task_image(tid, str(image_file))
        stored = repo.image_path(img)
        repo.delete_task(tid)
        assert not stored.exists()

    def test_delete_tasks_cascades_images(self, tmp_path):
        ids, storeds = [], []
        for i in range(2):
            tid = _task()
            ids.append(tid)
            f = tmp_path / f"q{i}.png"
            f.write_bytes(PNG_BYTES)
            img = repo.add_task_image(tid, str(f))
            storeds.append(repo.image_path(img))
        assert repo.delete_tasks(ids) == 2
        assert all(not p.exists() for p in storeds)


class TestImageBackup:
    def test_backup_roundtrip(self, tmp_path, image_file):
        tid = _task()
        repo.add_task_image(tid, str(image_file))
        bj = tmp_path / "backup.json"
        backup.export_json(str(bj))
        data = json.loads(bj.read_text(encoding="utf-8"))
        assert data["version"] == 3
        assert len(data["images"]) == 1
        assert data["images"][0]["data_b64"]

        # 切换到全新数据库恢复：图片记录与文件都应还原
        db.close()
        db.init(str(tmp_path / "second" / "tasks.db"))
        n_t, n_h = backup.import_json(str(bj))
        assert n_t == 1 and n_h == 0
        imgs = repo.list_task_images(tid)
        assert len(imgs) == 1
        assert imgs[0].filename == "p1.png"
        assert repo.image_path(imgs[0]).read_bytes() == PNG_BYTES

    def test_old_v2_backup_imports_without_images(self, tmp_path):
        """旧版（v2，无 images 字段）备份仍可正常导入。"""
        bj = tmp_path / "old.json"
        bj.write_text(json.dumps({
            "format": "task_reminder_backup",
            "version": 2,
            "exported_at": fmt(datetime.now()),
            "tasks": [],
            "history": [],
        }, ensure_ascii=False), encoding="utf-8")
        assert backup.import_json(str(bj)) == (0, 0)


class TestImageDialog:
    def test_new_task_saves_pending_images(self, qtbot, image_file):
        from task_reminder.ui.task_dialog import TaskDialog
        dlg = TaskDialog(None)
        qtbot.addWidget(dlg)
        dlg.edit_name.insert("带图新任务")
        dlg.edit_assignee.insert("李四")
        now = datetime.now()
        dlg.dt_reminder.setDateTime(
            QDateTime.fromString(fmt(now + timedelta(hours=1)), "yyyy-MM-dd HH:mm"))
        dlg.dt_deadline.setDateTime(
            QDateTime.fromString(fmt(now + timedelta(hours=2)), "yyyy-MM-dd HH:mm"))
        dlg._pending_images.append(str(image_file))
        dlg._on_save()
        imgs = repo.list_task_images(dlg.task_id)
        assert len(imgs) == 1
        assert imgs[0].filename == "p1.png"
        assert repo.image_path(imgs[0]).read_bytes() == PNG_BYTES

    def test_edit_dialog_loads_existing_images(self, qtbot, image_file):
        from task_reminder.ui.task_dialog import TaskDialog
        tid = _task()
        repo.add_task_image(tid, str(image_file))
        dlg = TaskDialog(None, editing_task=repo.get_task(tid))
        qtbot.addWidget(dlg)
        assert len(dlg._images) == 1
        assert dlg._images[0].filename == "p1.png"

    def test_remove_saved_image_from_dialog(self, qtbot, image_file):
        from task_reminder.ui.task_dialog import TaskDialog
        tid = _task()
        img = repo.add_task_image(tid, str(image_file))
        dlg = TaskDialog(None, editing_task=repo.get_task(tid))
        qtbot.addWidget(dlg)
        dlg._remove_image("saved", img)
        assert repo.list_task_images(tid) == []
        assert not repo.image_path(img).exists()
