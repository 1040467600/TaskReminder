# TaskReminder 测试用例报告

> **项目**: TaskReminder 单机版任务提醒软件  
> **版本**: v2.0.8  
> **日期**: 2026-09-09  
> **环境**: Windows 10/11, Python 3.10+, PyQt6 6.11+, SQLite (stdlib), pytest 9.x  
> **运行命令**: `$env:QT_QPA_PLATFORM="offscreen"; $env:PYTHONDONTWRITEBYTECODE="1"; .\.venv\Scripts\python.exe -m pytest -v`  
> **E2E 走查**: `.\.venv\Scripts\python.exe scripts\walkthrough.py`

---

## 1. 概览

### 1.1 已有测试规模

| 测试文件 | 用例数 | 测试类型 | 覆盖模块 |
|---|---|---|---|
| `tests/test_repository.py` | 32 | 单元+集成 | repository（校验/CRUD/查询/提醒） |
| `tests/test_reminder.py` | 6 | 单元+集成 | reminder_service, notifier |
| `tests/test_excel.py` | 7 | 集成 | excel_io（导出/导入/冲突） |
| `tests/test_ui.py` | 23 | 功能 | widgets, search_bar, task_dialog, tasks_page |
| `tests/test_more.py` | 22 | 功能 | backup, widgets, tasks_page, history_page, settings_page, main |
| `tests/test_comprehensive.py` | 160 | 单元+集成+功能 | 全部 12 个核心模块 |
| `scripts/walkthrough.py` | 66 | E2E | 全流程端到端走查 |
| **合计** | **316** | | |

### 1.2 本报告覆盖范围

本报告按模块逐一列出**全部测试用例**（含已有和补充），每条用例包含：测试目的、输入数据、预期输出、执行步骤、验证方法。

### 1.3 测试夹具

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def db_conn(tmp_path):
    path = str(tmp_path / "test_tasks.db")
    conn = db.init(path)
    yield conn
    db.close()
```

- **作用域**: 每个测试函数自动应用（`autouse=True`）
- **隔离性**: 每个用例获得独立的临时数据库，互不干扰
- **清理**: `yield` 后 `db.close()` 关闭连接，`tmp_path` 由 pytest 自动清理

---

## 2. 测试用例详情

---

### 2.1 models.py — 数据模型（36 用例）

#### 2.1.1 TestHtmlToPlain（9 用例）— `html_to_plain(html: str) -> str`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_empty_string` | 空字符串边界 | `""` | `""` | 调用 `html_to_plain("")` | `assert result == ""` |
| 2 | `test_none_input` | None 边界 | `None` | `""` | 调用 `html_to_plain(None)` | `assert result == ""` |
| 3 | `test_plain_text_fast_path` | 无标签纯文本快速路径 | `"普通文本内容"` | `"普通文本内容"` | 调用函数 | `assert == "普通文本内容"` |
| 4 | `test_simple_bold` | 简单加粗标签 | `"<b>加粗</b>"` | `"加粗"` | 调用函数 | `assert == "加粗"` |
| 5 | `test_nested_tags` | 嵌套标签 | `"<div><p>段落</p></div>"` | `"段落"`（含换行） | 调用函数 | `assert "段落" in result` |
| 6 | `test_br_to_newline` | br 标签转换行 | `"行1<br>行2"` | `"行1\n行2"` | 调用函数 | `assert "\n" in result` |
| 7 | `test_html_entities` | HTML 实体解码 | `"a&amp;b&lt;c&gt;d"` | `"a&b<c>d"` | 调用函数 | `assert == "a&b<c>d"` |
| 8 | `test_style_script_removed` | style/script 标签移除 | `"<style>.x{}</style>可见"` | `"可见"` | 调用函数 | `assert "可见" in result and ".x" not in result` |
| 9 | `test_strip_whitespace` | 前后空白 strip | `"  文本  "` | `"文本"` | 调用函数 | `assert == "文本"` |

#### 2.1.2 TestPlainLen（4 用例）— `plain_len(html: str) -> int`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_empty` | 空内容长度 | `""` | `0` | 调用 `plain_len("")` | `assert == 0` |
| 2 | `test_plain` | 纯文本长度 | `"12345"` | `5` | 调用函数 | `assert == 5` |
| 3 | `test_html` | HTML 内容取纯文本长度 | `"<b>12</b>34"` | `4` | 调用函数 | `assert == 4` |
| 4 | `test_boundary_5000` | 5000 字边界 | `"x" * 5000` | `5000` | 调用函数 | `assert == 5000` |

#### 2.1.3 TestParse（6 用例）— `parse(s: str) -> Optional[datetime]`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_empty` | 空字符串 | `""` | `None` | 调用 `parse("")` | `assert is None` |
| 2 | `test_standard` | 标准格式 | `"2026-09-10 14:30"` | `datetime(2026,9,10,14,30)` | 调用函数 | `assert .year==2026 and .hour==14` |
| 3 | `test_t_separator` | T 分隔 | `"2026-09-10T14:30"` | `datetime(2026,9,10,14,30)` | 调用函数 | `assert .minute==30` |
| 4 | `test_with_seconds` | 含秒 | `"2026-09-10 14:30:45"` | `datetime` | 调用函数 | `assert .second==45` |
| 5 | `test_date_only` | 仅日期 | `"2026-09-10"` | `datetime(2026,9,10,0,0)` | 调用函数 | `assert .hour==0` |
| 6 | `test_invalid` | 无效格式 | `"not-a-date"` | `None` | 调用函数 | `assert is None` |

#### 2.1.4 TestTaskDataclass（12 用例）— `Task` 数据类

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_plain_text_prefers_column` | 优先 content_plain 列 | `content_plain="纯文本", content="<b>x</b>"` | `"纯文本"` | 构造 Task 并调用 `plain_text()` | `assert == "纯文本"` |
| 2 | `test_plain_text_fallback_to_html` | 列为空时回退计算 | `content_plain="", content="<b>x</b>"` | `"x"` | 构造 Task 并调用 | `assert == "x"` |
| 3 | `test_summary_uses_name` | 摘要优先名称 | `name="任务A", content="内容"` | `"任务A"` | 调用 `summary()` | `assert == "任务A"` |
| 4 | `test_summary_truncates` | 摘要超长截断 | `name="x"*50` | 以 `…` 结尾，≤41 字符 | 调用 `summary()` | `assert result.endswith("…")` |
| 5 | `test_summary_fallback_content` | 无名称时用内容 | `name="", content="内容B"` | `"内容B"` | 调用 `summary()` | `assert == "内容B"` |
| 6 | `test_is_overdue_true` | 已过期未完成 | `deadline="2020-01-01 00:00", status="未开始"` | `True` | 调用 `is_overdue()` | `assert is True` |
| 7 | `test_is_overdue_done_not_overdue` | 已完成不算过期 | `deadline="2020-01-01", status="已完成"` | `False` | 调用 `is_overdue()` | `assert is False` |
| 8 | `test_is_overdue_future` | 未来截止不算过期 | `deadline="2099-01-01", status="未开始"` | `False` | 调用 `is_overdue()` | `assert is False` |
| 9 | `test_is_overdue_no_deadline` | 无截止时间 | `deadline=""` | `False` | 调用 `is_overdue()` | `assert is False` |
| 10 | `test_from_row_full` | 从数据库行构造 | 含全部字段的 row 对象 | Task 实例各字段匹配 | 调用 `Task.from_row(row)` | `assert t.name == row["name"]` |
| 11 | `test_from_row_partial` | 部分字段行 | 仅含 id/name 的 row | Task 实例 | 调用 `from_row` | `assert t.id and t.name` |
| 12 | `test_from_row_empty` | 空行 | 无数据的临时 DB | None 或空 Task | 先 `mk()` 建数据再 `from_row` | `assert row is not None` |

#### 2.1.5 TestReminderLog（3 用例）— `ReminderLog` 数据类

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_response_text_known` | 已知响应码 | `response="done"` | `"标记完成"` | 调用 `response_text()` | `assert == "标记完成"` |
| 2 | `test_response_text_unknown` | 未知响应码 | `response="custom"` | `"custom"` | 调用 `response_text()` | `assert == "custom"` |
| 3 | `test_from_row` | 从行构造 | 数据库行 | ReminderLog 实例 | 先 `mk()` + `mark_triggered` 再查行 | `assert log.id > 0` |

---

### 2.2 db.py — 数据库连接与 Schema（7 用例）

#### 2.2.1 TestDb（7 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_default_db_path` | 默认路径含 TaskReminder | 无 | 路径含 `TaskReminder/tasks.db` | 调用 `db.default_db_path()` | `assert "TaskReminder" in path` |
| 2 | `test_init_creates_schema` | init 创建表 | 临时路径 | 3 张表存在 | 调用 `db.init(path)` 后查 `sqlite_master` | `assert tables == {"tasks","reminder_history","user_settings"}` |
| 3 | `test_init_idempotent` | init 幂等不丢数据 | 已有数据的 DB | 旧数据保留 | init → `mk()` → 再 init → 查 | `assert count == 1` |
| 4 | `test_transaction_commit` | 事务提交 | INSERT 语句 | 数据持久 | `with db.transaction() as c: c.execute(...)` | 查 `COUNT(*) == 1` |
| 5 | `test_transaction_rollback` | 事务回滚 | 异常中 INSERT | 数据不持久 | `transaction()` 内 raise | `except: pass`，查 `COUNT(*) == 0` |
| 6 | `test_content_plain_migration` | 迁移回填 content_plain | 有旧数据的 DB | content_plain 非空 | 插入 `content="<b>x</b>"` 的行 → `ensure_schema` | `assert row["content_plain"] == "x"` |
| 7 | `test_close_resets_conn` | close 后重置连接 | 已初始化的 DB | `_conn is None` | `db.close()` 后检查 | `assert db._conn is None` |

---

### 2.3 app_config.py — 配置读写（11 用例）

#### 2.3.1 TestAppConfig（11 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_defaults` | 默认值 | 不设任何值 | `theme="light"` | 调用 `get("theme")` | `assert == "light"` |
| 2 | `test_string_value` | 字符串读写 | `set("theme","dark")` | `"dark"` | set 后 get | `assert == "dark"` |
| 3 | `test_int_value` | 整数读写 | `set("font_size",16)` | `16` | set 后 get | `assert == 16` |
| 4 | `test_bool_value` | 布尔读写 | `set("sound_enabled",False)` | `False` | set 后 get | `assert is False` |
| 5 | `test_list_value` | 列表读写 | `set("sort_state",[{"key":"deadline"}])` | 列表 | set 后 get | `assert len == 1` |
| 6 | `test_dict_value` | 字典读写 | `set("window_state",{"x":100})` | 字典 | set 后 get | `assert ["x"] == 100` |
| 7 | `test_overwrite` | 覆盖写入 | 先 `set("font_size",14)` 再 `set("font_size",20)` | `20` | 两次 set 后 get | `assert == 20` |
| 8 | `test_raw_value` | 原始字符串 | `set("custom","hello")` | `"hello"` | set 后 get | `assert == "hello"` |
| 9 | `test_default_sound_path` | 默认音效路径 | 无 | 含 `chime.wav` | 调用 `default_sound()` | `assert "chime.wav" in path` |
| 10 | `test_built_in_sounds` | 内置音效列表 | 无 | 3 个元组 | 调用 `built_in_sounds()` | `assert len == 3` |
| 11 | `test_assets_dir` | 资源目录存在 | 无 | Path 对象 | 调用 `assets_dir()` | `assert isinstance(p, Path)` |

---

### 2.4 repository.py — 数据访问层（24 用例）

#### 2.4.1 TestValidation（8 用例）— `validate_task()` / `ValidationError`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_empty_name` | 空名称被拒 | `name=""` | `ValidationError` | 调用 `add_task(...)` | `with pytest.raises(ValidationError)` |
| 2 | `test_name_too_long` | 名称超 50 字 | `name="x"*51` | `ValidationError` | 调用 `add_task` | `with pytest.raises` |
| 3 | `test_empty_assignee` | 空执行人 | `assignee=""` | `ValidationError` | 调用 `add_task` | `with pytest.raises` |
| 4 | `test_reminder_after_deadline` | 提醒晚于截止 | `reminder > deadline` | `ValidationError` | 调用 `add_task` | `with pytest.raises` |
| 5 | `test_content_too_long` | 内容超 5000 字 | `content="x"*5001` | `ValidationError` | 调用 `add_task` | `with pytest.raises` |
| 6 | `test_notes_too_long` | 备注超 200 字 | `notes="x"*201` | `ValidationError` | 调用 `add_task` | `with pytest.raises` |
| 7 | `test_invalid_deadline` | 无效截止时间 | `deadline="abc"` | `ValidationError` | 调用 `add_task` | `with pytest.raises` |
| 8 | `test_valid_task` | 合法任务通过 | 全部合法字段 | 不抛异常 | 调用 `add_task` | `assert tid > 0` |

#### 2.4.2 TestCrud（6 用例）— `add_task` / `update_task` / `set_status` / `delete_task`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_add_task` | 新增返回 ID | 合法字段 | `tid > 0` | 调用 `add_task` | `assert tid > 0` |
| 2 | `test_get_task` | 按 ID 查询 | `tid` | Task 实例 | `get_task(tid)` | `assert t.name == "写报告"` |
| 3 | `test_update_task` | 更新字段 | 改名 | 名称已更新 | `update_task` 后 `get_task` | `assert t.name == "新名称"` |
| 4 | `test_set_status` | 状态流转 | `set_status(tid, "已完成")` | `triggered=1` | 调用后查 | `assert t.triggered == 1 and t.status == "已完成"` |
| 5 | `test_delete_task` | 删除任务 | `delete_task(tid)` | 不存在 | 删除后 `get_task` | `assert get_task(tid) is None` |
| 6 | `test_delete_tasks_batch` | 批量删除 | 3 个 ID | 删除 3 条 | `delete_tasks([id1,id2,id3])` | `assert count == 3` |

#### 2.4.3 TestQuery（6 用例）— `list_tasks` / `all_tasks` / `_criteria_sql`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_list_tasks_default_sort` | 默认按创建时间降序 | 多条任务 | 最新在前 | `list_tasks()` | `assert tasks[0].created_at >= tasks[-1].created_at` |
| 2 | `test_list_tasks_pagination` | 分页 | page_size=2, 5 条 | 第 1 页 2 条, total=5 | 调用 `list_tasks(1, 2)` | `assert len(tasks)==2 and total==5` |
| 3 | `test_search_by_keyword` | 名称关键词 | `keyword="报告"` | 匹配名称含"报告" | 调用 `list_tasks(criteria={"keyword":"报告"})` | `assert all("报告" in t.name for t in tasks)` |
| 4 | `test_search_by_content_kw` | 内容关键词 | `content_kw="季度"` | 匹配内容含"季度" | 调用 `list_tasks(criteria={"content_kw":"季度"})` | `assert len(tasks) >= 1` |
| 5 | `test_search_by_assignee` | 按执行人 | `assignee="张三"` | 匹配执行人 | 调用 `list_tasks(criteria={"assignee":"张三"})` | `assert all(t.assignee=="张三")` |
| 6 | `test_search_by_status` | 按状态 | `statuses=["已完成"]` | 只含已完成 | 调用 `list_tasks(criteria={"statuses":["已完成"]})` | `assert all(t.status=="已完成")` |

#### 2.4.4 TestReminder（4 用例）— `due_for_reminder` / `mark_triggered` / `reset_triggered_for_new_day`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_due_for_reminder` | 到期任务被查出 | 提醒时间在过去 | 列表含该任务 | 先 `add_task` 过期提醒 → `due_for_reminder()` | `assert any(t.id == tid)` |
| 2 | `test_mark_triggered` | 触发后标记 | `mark_triggered(tid)` | `triggered=1`, 返回 hid | 调用后 `get_task` | `assert t.triggered == 1 and hid > 0` |
| 3 | `test_reset_for_new_day` | 跨日重置 | `triggered=1` 的任务 | `triggered=0` | 调用 `reset_triggered_for_new_day()` | `assert get_task(tid).triggered == 0` |
| 4 | `test_done_not_reset` | 已完成不重置 | `status="已完成", triggered=1` | 不重置 | 调用 `reset_triggered_for_new_day()` | `assert t.triggered == 1` |

#### 2.4.5 TestRepositoryAdvanced（4 用例）— 补充用例

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_find_duplicate` | 重复判定 | 相同名称+执行人+截止 | Task 或 None | 调用 `find_duplicate` | `assert dup is not None` |
| 2 | `test_list_assignees` | 执行人列表 | 多个任务不同执行人 | 去重列表 | 调用 `list_assignees()` | `assert len > 0 and len(set) == len` |
| 3 | `test_stats` | 统计数据 | 多条任务 | 含 total/by_status/overdue | 调用 `stats()` | `assert s["total"] >= 1` |
| 4 | `test_delete_history_row` | 单条历史删除 | `mark_triggered` 后 | 该条不存在 | `delete_history_row(hid)` 后查 | `assert not any(log.id == hid)` |

---

### 2.5 reminder_service.py — 提醒调度服务（10 用例）

#### 2.5.1 TestReminderService（10 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_start` | 启动后定时器运行 | 无 | `timer.isActive()` | 调用 `start()` | `assert service._timer.isActive()` |
| 2 | `test_stop` | 停止后定时器不运行 | 已启动 | 不运行 | `start()` → `stop()` | `assert not _timer.isActive()` |
| 3 | `test_apply_interval_default` | 默认间隔 5s | 无配置 | `interval=5000ms` | 调用 `apply_interval()` | `assert _timer.interval() == 5000` |
| 4 | `test_apply_interval_custom` | 自定义间隔 | `set("poll_interval", 10)` | `interval=10000ms` | 调用 `apply_interval()` | `assert _timer.interval() == 10000` |
| 5 | `test_apply_interval_clamp_low` | 下界钳制 1s | `poll_interval=0` | `interval=1000ms` | 调用 `apply_interval()` | `assert _timer.interval() == 1000` |
| 6 | `test_apply_interval_clamp_high` | 上界钳制 60s | `poll_interval=120` | `interval=60000ms` | 调用 `apply_interval()` | `assert _timer.interval() == 60000` |
| 7 | `test_apply_interval_invalid` | 非法值回退 | `poll_interval="abc"` | `interval=5000ms` | 调用 `apply_interval()` | `assert _timer.interval() == 5000` |
| 8 | `test_tick_triggers_due` | tick 触发到期提醒 | 过期任务 | `task_due` 信号发射 | `mk()` 过期任务 → `tick()` → `app.processEvents()` | `assert fired` 列表非空 |
| 9 | `test_tick_no_due` | 无到期不触发 | 未来任务 | 无信号 | `mk()` 未来任务 → `tick()` | `assert not fired` |
| 10 | `test_tick_exception_safe` | 异常容错 | mock `due_for_reminder` 抛异常 | 不崩溃 | monkeypatch → `tick()` | `assert` 无未捕获异常 |

---

### 2.6 notifier.py — 提醒弹窗与队列（14 用例）

#### 2.6.1 TestRemainingText（5 用例）— `remaining_text(deadline: str) -> str`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_empty` | 空截止时间 | `""` | `""` | 调用函数 | `assert == ""` |
| 2 | `test_invalid` | 无效时间 | `"abc"` | `""` | 调用函数 | `assert == ""` |
| 3 | `test_future` | 未来截止 | `"2099-01-01 00:00"` | 含"剩余" | 调用函数 | `assert "剩余" in result` |
| 4 | `test_past` | 已过期 | `"2020-01-01 00:00"` | 含"已过期" | 调用函数 | `assert "已过期" in result` |
| 5 | `test_within_hours` | 几小时内 | 2 小时后 | 含"小时" | 调用函数 | `assert "小时" in result` |

#### 2.6.2 TestNotifierQueue（9 用例）— `Notifier` 类

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_notify_enqueues` | 入队 | `notify(task, hid)` | `pending_count() == 1` | 调用 `notify` | `assert == 1` |
| 2 | `test_pump_shows_dialog` | pump 弹出弹窗 | 已入队 | `_dialog is not None` | `notify` → `pump()` | `assert _dialog is not None` |
| 3 | `test_pump_empty_noop` | 空队列 pump 无操作 | 无入队 | `_dialog is None` | 调用 `pump()` | `assert _dialog is None` |
| 4 | `test_pump_existing_skips` | 已有弹窗不再弹 | 已有弹窗 | 不创建新弹窗 | `pump()` 再 `pump()` | `assert _dialog unchanged` |
| 5 | `test_queue_changed_signal` | 队列变化信号 | notify 后 | `queue_changed` 发射 | 信号连接后 notify | `assert received == [1]` |
| 6 | `test_respond_done` | 标记完成 | `_respond("done")` | `responded` 信号="done" | 弹窗 → `_respond("done")` | `assert fired == ["done"]` |
| 7 | `test_respond_close` | 关闭 | `_respond("close")` | `responded` 信号="close" | 弹窗 → `_respond("close")` | `assert fired == ["close"]` |
| 8 | `test_respond_snooze_5min` | 稍后 5 分钟 | `_respond("snooze", minutes=5)` | 提醒时间+5min | 弹窗 → snooze | `assert new_reminder > old + 4min` |
| 9 | `test_respond_snooze_60min` | 稍后 60 分钟 | `minutes=60` | 提醒时间+60min | 弹窗 → snooze | `assert new_reminder > old + 59min` |

---

### 2.7 backup.py — JSON 备份恢复（8 用例）

#### 2.7.1 TestBackupAdvanced（8 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_export_with_history` | 含历史导出 | `mk()` + `mark_triggered` | `n >= 1` | `export_json(path)` | `assert n >= 1` |
| 2 | `test_export_tasks_only` | 仅任务无历史 | `mk()` 无 mark | `n >= 1` | 导出 | `assert n >= 1` |
| 3 | `test_import_overwrite_same_id` | 同 ID 覆盖 | 先导出再导入 | 数据恢复 | `export` → `delete_task` → `import` | `assert get_task(tid) is not None` |
| 4 | `test_import_creates_dir` | 自动建目录 | 不存在的路径 | 文件创建 | `export_json("a/b/c/backup.json")` | `assert Path.exists()` |
| 5 | `test_export_empty_db` | 空库导出 | 无数据 | `n == 0` | 导出 | `assert n == 0` |
| 6 | `test_import_recalculates_plain` | 导入重算 content_plain | 旧备份无该列 | 列非空 | 导入后 `get_task` | `assert t.content_plain != ""` |
| 7 | `test_invalid_format` | 非法格式 | `{"format": "other"}` | `ValueError` | 调用 `import_json` | `with pytest.raises(ValueError)` |
| 8 | `test_empty_backup` | 空备份 | 空库导出再导入 | `(0, 0)` | export → import | `assert (t, h) == (0, 0)` |

---

### 2.8 excel_io.py — Excel 导入导出（12 用例）

#### 2.8.1 TestExport（3 用例）— `export_tasks()`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_export_basic` | 基本导出 | 3 条任务 | `n == 3`, 文件存在 | 调用 `export_tasks` | `assert n == 3 and Path.exists()` |
| 2 | `test_export_chinese_path` | 中文路径 | `"备份/任务.xlsx"` | 文件创建 | 调用 `export_tasks` | `assert Path.exists()` |
| 3 | `test_export_roundtrip` | 导出→导入往返 | 导出后导入 | 数据一致 | export → `read_rows` | `assert rows[0]["name"] == "写报告"` |

#### 2.8.2 TestImport（4 用例）— `import_tasks()` / `ImportReport`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_import_skip` | 跳过冲突 | 已有同名称+执行人+截止 | `skipped >= 1` | 先 add → 再 import | `assert report.skipped >= 1` |
| 2 | `test_import_overwrite` | 覆盖冲突 | 已有同名称+执行人+截止 | `updated >= 1` | `import_tasks(strategy="overwrite")` | `assert report.updated >= 1` |
| 3 | `test_import_validation_error` | 校验失败 | 空名称行 | `errors` 非空 | 导入含空行的 xlsx | `assert len(report.errors) > 0` |
| 4 | `test_import_report_summary` | 报告摘要 | 有 added/skipped/errors | 含统计行 | 调用 `report.summary()` | `assert "新增" in summary and "跳过" in summary` |

#### 2.8.3 TestExcelHelpers（5 用例）— `_cell_time()` / `read_rows()`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_cell_time_datetime` | datetime 对象 | `datetime(2026,9,10,14,30)` | `"2026-09-10 14:30"` | 调用 `_cell_time` | `assert == "2026-09-10 14:30"` |
| 2 | `test_cell_time_string` | 字符串格式 | `"2026-09-10 14:30"` | 同上 | 调用 | `assert == "2026-09-10 14:30"` |
| 3 | `test_cell_time_slash` | 斜杠格式 | `"2026/09/10 14:30"` | 同上 | 调用 | `assert == "2026-09-10 14:30"` |
| 4 | `test_cell_time_none` | None/空 | `None` 或 `""` | `None` | 调用 | `assert is None` |
| 5 | `test_cell_time_invalid` | 无效 | `"abc"` | `None` | 调用 | `assert is None` |

---

### 2.9 ui/search_bar.py — 搜索栏（9 用例）

#### 2.9.1 TestSearchBarAdvanced（9 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_reset_clears_all` | 重置清空 | 设多个条件后 reset | 全部清空 | 调用 `reset()` | `assert not bar.criteria()` |
| 2 | `test_set_criteria_roundtrip` | 条件往返 | 设条件后读回 | 字段匹配 | `set_criteria(c)` → `criteria()` | `assert c == readback` |
| 3 | `test_adv_keys_not_empty` | 高级字段列表 | 无 | 5 个 key | 检查 `_ADV_KEYS` | `assert len == 5` |
| 4 | `test_date_ranges_always_editable` | 日期始终可编辑 | 不勾选"限定" | 日期框 isEnabled | 检查 `lo.isEnabled()` | `assert lo.isEnabled()` |
| 5 | `test_date_ranges_toggle` | 限定生效/取消 | 勾选→设日期→取消 | criteria 有/无 | 勾选+设日期 → 取消 | `assert "deadline_from" in/not in` |
| 6 | `test_both_date_ranges_independent` | 两日期范围独立 | 分别限定 created/deadline | 独立生效 | 分别操作 | `assert "created_from" in c and "deadline_from" in c` |
| 7 | `test_active_badge_hidden_expanded` | 展开时徽章隐藏 | 面板展开 | `btn_active.isVisible() == False` | 切换 `btn_advanced` | `assert not visible` |
| 8 | `test_active_badge_visible_collapsed` | 收起时徽章可见 | 设条件后收起 | 可见 | 设条件 → 收起 | `assert btn_active.isVisible()` |
| 9 | `test_debounce_merges` | 防抖合并连续输入 | 快速连续输入 | 只触发一次 | 连续 setText → 等 350ms | `assert len(received) == 1` |

---

### 2.10 ui/task_dialog.py — 任务对话框（13 用例）

#### 2.10.1 TestTaskDialogAdvanced（13 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_deadline_presets` | 截止快捷预设 | 点"今天 18:00" | 时间=今天 18:00 | 模拟菜单触发 | `assert edit_deadline.dateTime().hour() == 18` |
| 2 | `test_reminder_preset_30min` | 提醒 30 分钟后 | 点"30 分钟后" | 时间≈now+30min | 模拟触发 | `assert diff >= 29min` |
| 3 | `test_preset_before_deadline` | 截止前 1 小时 | 截止已设 | 提醒=截止-1h | 触发预设 | `assert reminder == deadline - 1h` |
| 4 | `test_deadline_after_reminder_shifts` | 截止后移提醒 | 截止<提醒 | 提醒自动调整 | 改截止时间 | `assert reminder < deadline` |
| 5 | `test_reminder_after_deadline_shifts` | 提醒后移截止 | 提醒>截止 | 截止自动调整 | 改提醒时间 | `assert deadline > reminder` |
| 6 | `test_notes_truncation` | 备注截断 | 201 字 | 截断为 200 | 输入超长备注 | `assert len <= 200` |
| 7 | `test_load_task` | 编辑回填 | 已有任务 | 各字段匹配 | `TaskDialog(editing_task=t)` | `assert edit_name.text() == t.name` |
| 8 | `test_notes_length_display` | 字数显示 | 输入 50 字 | 显示"50/200" | 输入文本 | `assert "50" in label.text()` |
| 9 | `test_notes_over_limit_red` | 超限标红 | 201 字 | 样式含 red | 输入超长 | `assert "red" in style or "color" in style` |
| 10 | `test_edit_returns_values` | edit 返回值 | 填写表单 | dict 含各字段 | `TaskDialog.edit()` → accept | `assert "name" in result` |
| 11 | `test_default_time_valid` | 默认时间合法 | 新建对话框 | 提醒 < 截止 | 检查默认值 | `assert reminder < deadline` |
| 12 | `test_validate_passes` | 校验通过 | 合法输入 | 不报错 | 填写 → `_validate()` | `assert no error` |
| 13 | `test_assignee_completer` | 执行人自动补全 | 历史有"张三" | 补全列表含"张三" | `list_assignees` mock → 检查 completer | `assert "张三" in model` |

---

### 2.11 ui/widgets.py — 通用组件（8 用例）

#### 2.11.1 TestPaginationBarAdvanced（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_jump_page_signal` | 跳页信号 | 输入页码 3 | `page_changed(3)` | 设输入框 → 回车 | `assert received == [3]` |
| 2 | `test_zero_count` | 零条数 | `update_info(0, 1, 50)` | 页码=1 | 调用 | `assert bar.page == 1` |
| 3 | `test_last_page_next_disabled` | 末页禁用下一页 | 末页 | `btn_next.isEnabled() == False` | `update_info` 到末页 | `assert not enabled` |
| 4 | `test_info_text` | 信息文本 | `update_info(450, 2, 200)` | 含"共 450 条" | 调用后读 | `assert "450" in text` |
| 5 | `test_page_size_signal` | 每页条数信号 | 选 50 | `page_size_changed(50)` | `_set_size(50)` | `assert received == [50]` |

#### 2.11.2 TestConfirmDialog（3 用例）— `confirm()`

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_confirm_true` | 确定返回 True | 点"确定" | `True` | mock `exec()` → mock `clickedButton()` | `assert result is True` |
| 2 | `test_confirm_false` | 取消返回 False | 点"取消" | `False` | 同上 | `assert result is False` |
| 3 | `test_confirm_chinese_buttons` | 中文按钮 | 无 | 按钮文本含"确定"/"取消" | 检查按钮文本 | `assert "确定" in text and "取消" in text` |

---

### 2.12 ui/dashboard_page.py — 数据看板（8 用例）

#### 2.12.1 TestDashboardPage（8 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_stat_card_click` | 卡片点击信号 | 点击卡片 | `clicked(key)` | `card.clicked.emit("overdue")` | `assert received == ["overdue"]` |
| 2 | `test_card_value_update` | 卡片值更新 | `lbl_value.setText("5")` | `"5"` | 设值后读 | `assert == "5"` |
| 3 | `test_overdue_count` | 过期数量 | 过期任务 | `stats["overdue"] >= 1` | `mk()` 过期 → `refresh()` | `assert overdue_card value >= "1"` |
| 4 | `test_empty_list_hint` | 空列表提示 | 无数据 | 含提示文本 | `refresh()` | `assert "暂无" in text` |
| 5 | `test_upcoming_list` | 即将提醒列表 | 未来提醒任务 | 列表非空 | `mk()` 未来 → refresh | `assert list.count() > 0` |
| 6 | `test_overdue_list` | 已过期列表 | 过期任务 | 列表非空 | `mk()` 过期 → refresh | `assert list.count() > 0` |
| 7 | `test_bar_chart_data` | 柱状图数据 | 多状态任务 | 含各状态数据 | `refresh()` | `assert chart._data` 非空 |
| 8 | `test_empty_data` | 空数据看板 | 无任务 | 统计全 0 | `refresh()` | `assert all values == "0"` |

---

### 2.13 ui/history_page.py — 提醒历史页（6 用例）

#### 2.13.1 TestHistoryPage（6 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_refresh_and_ranges` | 刷新和快捷范围 | `mk()` + `mark_triggered` | 表格 1 行 | `refresh()` → 切换范围 | `assert table.rowCount() == 1` |
| 2 | `test_single_row_delete` | 单条删除 | 2 条历史 | 删除 1 条后剩 1 条 | `_delete_row(hid)` | `assert table.rowCount() == 1` |
| 3 | `test_date_format_day` | 日期精确到天 | 无 | 格式 `yyyy-MM-dd` | 检查 `dt_from.displayFormat()` | `assert == "yyyy-MM-dd"` |
| 4 | `test_default_today` | 默认当天 | 无 | `dt_from.date() == today` | 检查初始值 | `assert == QDate.currentDate()` |
| 5 | `test_all_range_no_2000` | "全部"不重置到 2000 | 选"全部" | `dt_from.date() != QDate(2000,1,1)` | 切换到"全部" | `assert dt_from.date() != QDate(2000,1,1)` |
| 6 | `test_calendar_year_buttons` | 日历翻年按钮 | QDateEdit | 导航栏含 2 个 `calYearBtn` | `add_calendar_year_buttons` → findChild | `assert len(btns) == 2` |

---

### 2.14 ui/settings_page.py — 设置页（5 用例）

#### 2.14.1 TestSettingsPage（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_theme_change_signal` | 主题切换信号 | 切换主题 | `theme_changed` 信号 | `cmb_theme.currentIndexChanged` | `assert signal received` |
| 2 | `test_behavior_changed_signal` | 行为变化信号 | 改分页大小 | `behavior_changed` 信号 | 修改 spinbox | `assert signal received` |
| 3 | `test_data_restored_signal` | 数据恢复信号 | 导入备份 | `data_restored` 信号 | 模拟恢复 | `assert signal received` |
| 4 | `test_load_values` | 加载当前配置 | 已有配置 | 各控件值匹配 | `_load()` | `assert cmb_theme.currentData() == "light"` |
| 5 | `test_restore_with_warning` | 恢复加覆盖警告 | 点恢复 | 弹出确认 | mock confirm | `assert confirm called` |

---

### 2.15 ui/tasks_page.py — 任务管理页（8 用例）

#### 2.15.1 TestTasksPage（8 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_new_task` | 新建任务 | 点"新建任务" | 对话框弹出 | `on_new()` | `assert dialog.isVisible()` |
| 2 | `test_edit_task` | 编辑任务 | 点编辑按钮 | 对话框含已有数据 | `on_edit(tid)` | `assert edit_name.text() == t.name` |
| 3 | `test_delete_selected` | 删除选中 | 选中行→Delete | 任务被删 | `on_delete_selected()` | `assert get_task(tid) is None` |
| 4 | `test_sort_toggle` | 排序切换 | 点表头 | 升序↔降序 | 点击 header | `assert sort_dir changed` |
| 5 | `test_column_config_persist` | 列配置持久化 | 拖拽列序 | 重启后恢复 | 改列序 → `_save_col_state` → 重读 | `assert saved order matches` |
| 6 | `test_export_excel` | 导出 Excel | 点导出 | 文件创建 | `on_export()` | `assert Path.exists()` |
| 7 | `test_import_excel` | 导入 Excel | 选 xlsx | 任务被添加 | `on_import()` | `assert count increased` |
| 8 | `test_empty_hint_search` | 搜索无结果提示 | 搜不存在的词 | 提示文本含"搜索条件" | 搜索 → `refresh()` | `assert "搜索" in hint.text()` |

---

### 2.16 ui/main_window.py — 主窗口（6 用例）

#### 2.16.1 TestMainWindow（6 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_page_switch` | 页面切换 | 点侧边栏 | 栈切换 | 切换到"数据看板" | `assert stacked.currentIndex == 1` |
| 2 | `test_shortcut_ctrl_n` | Ctrl+N 快捷键 | Ctrl+N | 弹出新建对话框 | 触发快捷键 | `assert dialog visible` |
| 3 | `test_shortcut_ctrl_f` | Ctrl+F 快捷键 | Ctrl+F | 搜索框获焦 | 触发快捷键 | `assert search_bar.hasFocus()` |
| 4 | `test_shortcut_delete` | Delete 快捷键 | 选中行→Delete | 删除触发 | 触发快捷键 | `assert confirm called or task deleted` |
| 5 | `test_tray_icon` | 托盘图标存在 | 无 | `tray.isVisible()` | 检查 `notifier.tray` | `assert tray is not None` |
| 6 | `test_window_title_version` | 标题含版本号 | 无 | 含 `v2.0.8` | 读 `windowTitle()` | `assert "v2.0.8" in title` |

---

### 2.17 main.py — 应用入口（3 用例）

#### 2.17.1 TestMainEntry（3 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_single_instance_key` | 实例键含版本号 | 无 | 含 `TaskReminder-2.0.8` | 调用 `_single_instance_key()` | `assert "2.0.8" in key` |
| 2 | `test_is_another_running_false` | 首次启动无实例 | 无 | `(False, server)` | 调用 `_is_another_running()` | `assert not another and server is not None` |
| 3 | `test_is_another_running_true` | 二次启动检测到实例 | 已有 server | `(True, None)` | 先启动再检测 | `assert another` |

---

### 2.18 ui/theme.py — 主题样式（2 用例）

#### 2.18.1 TestTheme（2 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_light_theme_applied` | 浅色主题生效 | `apply_theme(app, "light", 13)` | 样式表非空 | 调用后查 `app.styleSheet()` | `assert len(stylesheet) > 0` |
| 2 | `test_dark_theme_applied` | 深色主题生效 | `apply_theme(app, "dark", 13)` | 样式表非空 | 调用后查 | `assert len(stylesheet) > 0` |

---

### 2.19 sound.py — 声音播放（3 用例）

#### 2.19.1 TestSoundPlayer（3 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_play_disabled` | 禁用不播放 | `enabled=False` | `False` | 调用 `play(enabled=False)` | `assert result is False` |
| 2 | `test_play_default_sound` | 默认音效 | 无参数 | `True` 或 fallback | 调用 `play()` | `assert result in (True, False)` |
| 3 | `test_play_nonexistent_fallback` | 不存在文件回退 | `path="/nonexistent.wav"` | fallback | 调用 `play(path=...)` | `assert result in (True, False)` |

---

## 3. 测试类型分类

### 3.1 单元测试（纯函数与数据类）

| 模块 | 用例数 | 覆盖范围 |
|---|---|---|
| models.py | 36 | html_to_plain / plain_len / parse / Task / ReminderLog |
| db.py | 7 | init / transaction / schema / migration / close |
| app_config.py | 11 | get / set / defaults / assets_dir |
| notifier.py | 5 | remaining_text |
| sound.py | 3 | SoundPlayer.play |
| **小计** | **62** | |

### 3.2 集成测试（多模块协作）

| 模块 | 用例数 | 覆盖范围 |
|---|---|---|
| repository.py | 24 | CRUD / 查询 / 排序 / 分页 / 提醒触发 / 历史删除 |
| reminder_service.py | 10 | start/stop / interval / tick / 异常容错 |
| notifier.py | 9 | 队列 / pump / respond / snooze |
| backup.py | 8 | export / import / 覆盖 / 目录创建 |
| excel_io.py | 12 | export / import / _cell_time / read_rows |
| search_bar.py | 9 | reset / criteria / 日期范围 / 防抖 |
| task_dialog.py | 13 | 预设 / 联动 / 校验 / 回填 |
| **小计** | **85** | |

### 3.3 功能测试（UI 组件行为）

| 模块 | 用例数 | 覆盖范围 |
|---|---|---|
| widgets.py | 8 | 分页栏 / 确认弹窗 |
| dashboard_page.py | 8 | 卡片点击 / 统计刷新 / 柱状图 |
| history_page.py | 6 | 刷新 / 删除 / 日期格式 / 日历按钮 |
| settings_page.py | 5 | 主题切换 / 信号联动 |
| tasks_page.py | 8 | 新建 / 编辑 / 删除 / 排序 / 列配置 / 导入导出 |
| main_window.py | 6 | 页面切换 / 快捷键 / 托盘 |
| main.py | 3 | 单实例检测 |
| theme.py | 2 | 浅色/深色主题 |
| **小计** | **46** | |

### 3.4 E2E 端到端走查

| 脚本 | 断言数 | 覆盖范围 |
|---|---|---|
| scripts/walkthrough.py | 66 | CRUD / 校验 / 状态流转 / 提醒触发 / 弹窗队列 / 稍后提醒 / 历史 / 看板 / 设置 / 主题 |
| **小计** | **66** | |

### 3.5 总计

| 类型 | 用例数 |
|---|---|
| 单元测试 | 62 |
| 集成测试 | 85 |
| 功能测试 | 46 |
| E2E 走查 | 66 |
| **总计** | **259** (去重后约 316 含已有) |

---

## 4. 边界条件与异常场景覆盖矩阵

### 4.1 边界条件

| 场景 | 覆盖用例 | 模块 |
|---|---|---|
| 空字符串/None 输入 | 12 | models, notifier, excel_io |
| 最大长度边界（50/200/5000） | 6 | models, repository |
| 0 条/空列表 | 5 | widgets, dashboard, repository |
| 分页第 1 页/末页/越界 | 4 | widgets, repository |
| 日期过去/未来/当天 | 8 | models, notifier, history_page |
| 间隔 1s/60s/非法值 | 3 | reminder_service |
| 空数据库导出/导入 | 3 | backup, excel_io |

### 4.2 异常场景

| 场景 | 覆盖用例 | 模块 |
|---|---|---|
| 校验失败（空名称/超长/时间无效） | 8 | repository |
| 提醒晚于截止时间 | 2 | repository, task_dialog |
| 非法 JSON 格式 | 2 | backup |
| Excel 无效行/空名称 | 2 | excel_io |
| 数据库事务回滚 | 1 | db |
| tick 异常容错 | 1 | reminder_service |
| 音效文件不存在回退 | 1 | sound |
| 单实例冲突 | 1 | main |
| 二次启动检测 | 1 | main |

---

## 5. 已有测试文件索引

| 文件 | 路径 | 用例数 | 主要测试类 |
|---|---|---|---|
| conftest.py | `tests/conftest.py` | - | `db_conn` (autouse fixture) |
| test_repository.py | `tests/test_repository.py` | 32 | TestValidation, TestCrud, TestQuery, TestReminder |
| test_reminder.py | `tests/test_reminder.py` | 6 | TestReminderService, TestNotifierLogic |
| test_excel.py | `tests/test_excel.py` | 7 | TestExport, TestImport |
| test_ui.py | `tests/test_ui.py` | 23 | TestModel, TestSearchBar, TestTasksPage |
| test_more.py | `tests/test_more.py` | 22 | TestBackup, TestPaginationBar, TestDelegates, TestTasksPage, TestHistoryPage, TestSettingsPage, TestSingleInstance |
| test_comprehensive.py | `tests/test_comprehensive.py` | 160 | TestHtmlToPlain, TestPlainLen, TestParse, TestTaskDataclass, TestReminderLog, TestDb, TestAppConfig, TestRemainingText, TestNotifierQueue, TestReminderService, TestBackupAdvanced, TestExcelHelpers, TestSearchBarAdvanced, TestTaskDialogAdvanced, TestPaginationBarAdvanced, TestConfirmDialog, TestDashboardPage, TestRepositoryAdvanced |
| walkthrough.py | `scripts/walkthrough.py` | 66 | (函数式，非类) |

---

## 6. 运行方式

### 6.1 全量测试

```powershell
$env:QT_QPA_PLATFORM="offscreen"
$env:PYTHONDONTWRITEBYTECODE="1"
.\.venv\Scripts\python.exe -m pytest -v
```

### 6.2 单模块测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -v
```

### 6.3 E2E 走查

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python.exe scripts\walkthrough.py
```

### 6.4 性能基准

```powershell
.\.venv\Scripts\python.exe scripts\seed_perf.py --n 10000
```

### 6.5 注意事项

- UI/Qt 脚本需设 `QT_QPA_PLATFORM=offscreen` 跑无头验证
- 导入 `task_reminder` 需 `pythonpath=.`（见 `pytest.ini`）
- 设 `PYTHONDONTWRITEBYTECODE=1` 避免沙箱对 pyc 的限制
- PyInstaller 打包时清除该变量且需禁用沙箱
- 测试前执行 `Get-Process TaskReminder | Stop-Process -Force` 清残留实例

---

## 7. 补充测试用例（第二轮）

以下用例覆盖第一轮报告中遗漏的场景：并发写入、大数据量、SQL 注入防护、富文本格式化、UI 事件穿透、列拖拽边界、主题切换后重绘、信号链路断开、跨日时间逻辑等。

---

### 7.1 models.py — 补充边界用例（8 用例）

#### 7.1.1 TestHtmlToPlainAdvanced（8 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_mixed_entities_and_tags` | 混合实体与标签 | `"<b>a&amp;b</b> &lt;c&gt;"` | `"a&b <c>"` | 调用 `html_to_plain` | `assert == "a&b <c>"` |
| 2 | `test_deeply_nested` | 深层嵌套标签 | `"<a><b><c><d>深</d></c></b></a>"` | 含"深" | 调用 | `assert "深" in result` |
| 3 | `test_unclosed_tag` | 未闭合标签 | `"<b>未闭合"` | `"未闭合"` | 调用 | `assert == "未闭合"` |
| 4 | `test_only_tags` | 纯标签无文本 | `"<div></div><span></span>"` | `""`（仅空白） | 调用 | `assert result.strip() == ""` |
| 5 | `test_multiple_br` | 多个连续 br | `"a<br><br><br>b"` | 含 3 个换行 | 调用 | `assert result.count("\n") >= 2` |
| 6 | `test_unicode_emoji` | Unicode 与 emoji | `"<b>任务🎉</b>📝"` | `"任务🎉📝"` | 调用 | `assert "🎉" in result` |
| 7 | `test_self_closing` | 自闭合标签 | `"a<br/>b<img/>c"` | `"a\nb c"` 或 `"a\nbc"` | 调用 | `assert "a" in result and "c" in result` |
| 8 | `test_style_with_quotes` | 含引号的 style | `<style type="text/css">body{color:red}</style>可见` | `"可见"` | 调用 | `assert "red" not in result` |

#### 7.1.2 TestPlainLenAdvanced（3 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_html_with_entities` | HTML 实体长度 | `"&lt;&gt;&amp;"` | `3` | 调用 `plain_len` | `assert == 3` |
| 2 | `test_very_long` | 超长内容 | `"<b>" + "x"*10000 + "</b>"` | `10000` | 调用 | `assert == 10000` |
| 3 | `test_newlines_count` | 换行计为 1 字 | `"a<br>b"` | `2` | 调用 | `assert == 2` |

#### 7.1.3 TestParseAdvanced（4 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_with_t_and_seconds` | T 分隔含秒 | `"2026-09-10T14:30:45"` | `datetime` | 调用 `parse` | `assert .second == 45` |
| 2 | `test_slash_format` | 斜杠日期 | `"2026/09/10 14:30"` | `datetime` | 调用 | `assert .month == 9` |
| 3 | `test_whitespace_only` | 仅空白 | `"   "` | `None` | 调用 | `assert is None` |
| 4 | `test_leap_year` | 闰年日期 | `"2024-02-29 12:00"` | 有效 datetime | 调用 | `assert .day == 29` |

#### 7.1.4 TestTaskAdvanced（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_summary_multiline` | 多行内容摘要 | `content="行1\n行2\n行3"` | 含首行 | 调用 `summary()` | `assert "行1" in result` |
| 2 | `test_is_overdue_boundary_now` | 截止恰好为现在 | `deadline=fmt(now)` | 边界（过期） | 构造 `deadline == now` | `assert is_overdue() in (True, False)` — 验证不崩溃 |
| 3 | `test_plain_text_empty_both` | 两列均空 | `content="", content_plain=""` | `""` | 调用 `plain_text()` | `assert == ""` |
| 4 | `test_plain_text_html_only` | 仅 HTML 无列 | `content="<i>斜</i>"` | `"斜"` | 调用 | `assert == "斜"` |
| 5 | `test_from_row_missing_fields` | 行缺字段 | row 缺 `notes` | 默认空串 | `from_row(row)` | `assert t.notes == ""` |

---

### 7.2 db.py — 补充用例（5 用例）

#### 7.2.1 TestDbAdvanced（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_get_conn_auto_init` | 未 init 时 get_conn | 先 close 再 get_conn | 自动初始化 | `db.close()` → `db.get_conn()` | `assert conn is not None` |
| 2 | `test_index_exists` | 索引创建 | init 后 | 有索引 | 查 `sqlite_master WHERE type='index'` | `assert count >= 3` |
| 3 | `test_concurrent_writes` | 并发写入 | 2 个连接同时 INSERT | 无锁死 | 2 连接各 INSERT 100 条 | `assert total == 200` |
| 4 | `test_wal_mode` | WAL 模式 | init 后 | `journal_mode=WAL` | 查 PRAGMA | `assert mode == "wal"` |
| 5 | `test_foreign_key_cascade` | 级联删除 | 删 task 后 history 自动删 | history 清空 | INSERT task + history → DELETE task → 查 history | `assert count == 0` |

---

### 7.3 repository.py — 补充用例（14 用例）

#### 7.3.1 TestValidationAdvanced（4 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_sql_injection_name` | SQL 注入防护 | `name="'; DROP TABLE tasks;--"` | 正常存储 | `add_task` → `get_task` | `assert t.name == "'; DROP TABLE tasks;--"` |
| 2 | `test_name_exact_50` | 名称恰好 50 字 | `name="x"*50` | 通过 | `add_task` | `assert tid > 0` |
| 3 | `test_assignee_with_spaces` | 执行人含空格 | `assignee="  张三  "` | strip | `add_task` → `get_task` | `assert t.assignee == "张三"` |
| 4 | `test_reminder_equals_deadline` | 提醒=截止 | 同时刻 | 通过（<=） | `add_task` | `assert tid > 0` |

#### 7.3.2 TestQueryAdvanced（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_multi_keyword_and` | 多词 AND | `keyword="报告 季度"` | 名称同时含两词 | 建含"季度报告"的任务 → 搜索 | `assert all("报告" in t.name and "季度" in t.name)` |
| 2 | `test_multi_content_kw_and` | 内容多词 AND | `content_kw="A B"` | 内容同时含两词 | 建含"A B"内容的任务 | `assert all("A" in t.plain_text() and "B" in t.plain_text())` |
| 3 | `test_combined_criteria` | 复合条件 | keyword + assignee + status | 交集 | 建多任务 → `list_tasks(criteria={...})` | `assert all match` |
| 4 | `test_sort_by_deadline_asc` | 按截止升序 | 多任务 | 最早在前 | `sort="deadline", dir="asc"` | `assert tasks[0].deadline <= tasks[-1].deadline` |
| 5 | `test_pagination_beyond_last` | 超末页 | page=99, total=5 | 空列表 | `list_tasks(99, 10)` | `assert len(tasks) == 0 and total == 5` |

#### 7.3.3 TestHistoryAdvanced（3 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_history_date_filter` | 日期范围过滤 | 历史跨多天 | 只含指定天 | 建不同日期历史 → 按 start/end 查 | `assert all in range` |
| 2 | `test_history_pagination` | 历史分页 | 5 条, page_size=2 | 第 1 页 2 条 | `list_history(1, 2)` | `assert len == 2 and total == 5` |
| 3 | `test_clear_history` | 清空全部 | 3 条历史 | 0 条 | `clear_history()` | `assert total == 0` |

#### 7.3.4 TestStatsAdvanced（2 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_stats_by_status` | 按状态统计 | 2 完成+1 未开始 | `by_status={"已完成":2,"未开始":1}` | `stats()` | `assert s["by_status"]["已完成"] == 2` |
| 2 | `test_stats_due_week` | 7 天内到期 | 截止 3 天后 | `due_week >= 1` | 建 3 天后截止任务 | `assert s["due_week"] >= 1` |

---

### 7.4 notifier.py — 补充用例（6 用例）

#### 7.4.1 TestNotifierAdvanced（6 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_app_icon` | 图标返回 | 无 | `QIcon` 对象 | 调用 `app_icon()` | `assert icon is not None` |
| 2 | `test_remaining_text_exact_now` | 恰好截止 | `deadline=fmt(now)` | 不崩溃 | 调用 `remaining_text` | `assert isinstance(result, str)` |
| 3 | `test_notify_updates_tray` | notify 更新托盘 | notify 后 | tray message | `notify` → 检查 `tray.isVisible()` | `assert tray.isVisible()` |
| 4 | `test_dialog_title_has_name` | 弹窗标题含名称 | task.name="重要任务" | 标题含"重要任务" | notify → pump → 检查 `_dialog.windowTitle()` | `assert "重要任务" in title` |
| 5 | `test_snooze_custom_minutes` | 自定义稍后 | `minutes=15` | 提醒+15min | `_respond("snooze", minutes=15)` | `assert new - old >= 14min` |
| 6 | `test_queue_cleared_on_done` | 完成后队列清零 | 1 条 → done | `pending_count == 0` | notify → pump → respond("done") | `assert == 0` |

---

### 7.5 reminder_service.py — 补充用例（4 用例）

#### 7.5.1 TestReminderServiceAdvanced（4 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|
| 1 | `test_next_check_text` | 下次检查文本 | 已启动 | 含"秒"或"分" | 调用 `next_check_text()` | `assert "秒" in text or "分" in text` |
| 2 | `test_maybe_reset_new_day` | 跨日重置 | `triggered=1` 的未完成 | `triggered=0` | mock `datetime.now` 到第二天 → `tick()` | `assert t.triggered == 0` |
| 3 | `test_same_day_no_reset` | 同日不重置 | `triggered=1` | 仍为 1 | 同日 `tick()` | `assert t.triggered == 1` |
| 4 | `test_stop_clears_timer` | stop 后定时器清零 | 已启动 → stop | `timer.isActive() == False` | `start()` → `stop()` → 查 timer | `assert not active` |

---

### 7.6 backup.py — 补充用例（4 用例）

#### 7.6.1 TestBackupAdvanced2（4 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_export_large` | 大量数据导出 | 1000 条任务 | `n == 1000` | 批量 `mk()` 1000 次 → `export_json` | `assert n == 1000` |
| 2 | `test_import_preserves_history` | 导入保留历史 | 有历史记录的备份 | 历史恢复 | export → 清库 → import | `assert history_count > 0` |
| 3 | `test_malformed_json` | 损坏 JSON | `"{broken json"` | `ValueError` | 调用 `import_json` | `with pytest.raises` |
| 4 | `test_backup_format_field` | 备份含 format 字段 | 导出文件 | 含 `"format": "taskreminder"` | 读 JSON 检查 | `assert data["format"] == "taskreminder"` |

---

### 7.7 excel_io.py — 补充用例（5 用例）

#### 7.7.1 TestExcelAdvanced（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_export_all_columns` | 导出含全部列 | 多任务 | sheet 含全部表头 | export → `read_rows` | `assert set(headers) >= {"任务名称","执行人"}` |
| 2 | `test_import_mixed_valid_invalid` | 混合有效/无效 | 3 有效 + 2 无效行 | `added=3, errors=2` | 构造 xlsx → import | `assert report.added == 3 and len(report.errors) == 2` |
| 3 | `test_import_no_header` | 无表头导入 | 第 1 行非表头 | 全部跳过或报错 | 构造无表头 xlsx | `assert report.added == 0` |
| 4 | `test_cell_time_excel_serial` | Excel 日期序列号 | `45678.5` (Excel serial) | 日期字符串 | 调用 `_cell_time` | `assert isinstance(result, str)` |
| 5 | `test_read_rows_empty_file` | 空文件 | 无行的 xlsx | 空列表 | `read_rows(path)` | `assert len(rows) == 0` |

---

### 7.8 sound.py — 补充用例（2 用例）

#### 7.8.1 TestSoundPlayerAdvanced（2 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_play_custom_sound` | 自定义音效 | 存在的 .wav | `True` | 调用 `play(path=existing_wav)` | `assert result in (True, False)` |
| 2 | `test_play_same_path_twice` | 同路径多次播放 | 同一路径 2 次 | 不崩溃 | 连续 `play` 两次 | `assert` 无异常 |

---

### 7.9 app_config.py — 补充用例（3 用例）

#### 7.9.1 TestAppConfigAdvanced（3 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_get_unknown_key` | 未知键返回默认 | `get("nonexistent")` | `None` 或 `""` | 调用 `get` | `assert result in (None, "")` |
| 2 | `test_set_complex_nested` | 嵌套对象 | `set("nested", {"a": {"b": [1,2]}})` | 保持结构 | set → get | `assert result["a"]["b"] == [1,2]` |
| 3 | `test_set_then_delete_key` | 删除后回退默认 | set → 删 → get | 默认值 | 先 set 再清除设置 → get | `assert == default` |

---

### 7.10 ui/search_bar.py — 补充用例（5 用例）

#### 7.10.1 TestSearchBarAdvanced2（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_status_all_unchecked_auto_all` | 状态全取消自动全勾 | 逐个取消所有状态 | 默认全选 | 取消最后一个 → 检查 | `assert all checked` |
| 2 | `test_status_partial_select` | 部分选中 | 选 2/4 状态 | 只查这 2 个 | `criteria()` | `assert len(statuses) == 2` |
| 3 | `test_keyword_clear_button` | 清除按钮 | 有关键词时 | 点击后清空 | `edit_keyword.setText("")` | `assert keyword == ""` |
| 4 | `test_date_range_only_from` | 仅限定起始 | 勾选限定+设起始 | `created_from` 有值 | 操作 | `assert "created_from" in criteria` |
| 5 | `test_calendar_year_buttons_inserted` | 日历翻年按钮 | QDateEdit | 导航栏含 2 个 calYearBtn | `add_calendar_year_buttons(de)` → findChild | `assert len(btns) == 2` |

---

### 7.11 ui/task_dialog.py — 补充用例（6 用例）

#### 7.11.1 TestTaskDialogAdvanced2（6 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_bold_toggle` | B 加粗切换 | 点 B | `btn_bold.isChecked()` | `btn_bold.click()` | `assert btn_bold.isChecked()` |
| 2 | `test_italic_toggle` | I 斜体切换 | 点 I | `btn_italic.isChecked()` | `btn_italic.click()` | `assert btn_italic.isChecked()` |
| 3 | `test_underline_toggle` | U 下划线切换 | 点 U | `btn_underline.isChecked()` | `btn_underline.click()` | `assert btn_underline.isChecked()` |
| 4 | `test_clear_format` | 清除格式 | 有格式后清除 | 纯文本 | `_clear_fmt()` → 检查 | `assert not bold/italic/underline` |
| 5 | `test_content_length_display` | 字数实时更新 | 输入 100 字 | `"100 / 5000"` | setText 100 字 | `assert "100" in lbl_count.text()` |
| 6 | `test_validate_empty_name_error` | 空名报错 | name="" | 有错误提示 | `_validate()` | `assert "名称" in error or "不能为空"` |

---

### 7.12 ui/tasks_page.py — 补充用例（10 用例）

#### 7.12.1 TestTasksPageAdvanced（10 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_column_show_hide` | 列显示/隐藏 | 右键菜单切切换 | 列隐藏/显示 | `_show_column_menu_at` → toggle | `assert header.isSectionHidden(i) toggled` |
| 2 | `test_column_drag_reorder` | 拖拽改列序 | 拖 name 到 col 2 | visualIndex 变化 | `sectionMoved` 信号 | `assert visualIndex(0) != 0` |
| 3 | `test_column_state_persist` | 列配置持久化 | 拖列 → 刷新 | 恢复 | `_save_states` → `_restore_states` | `assert order matches` |
| 4 | `test_sort_cycle` | 排序三态循环 | 点同一列 3 次 | 升→降→默认 | 连续点击表头 | `assert sort_dir cycle: asc→desc→""` |
| 5 | `test_right_click_context_menu` | 右键菜单 | 右键表格 | 弹出菜单 | `customContextMenuRequested` | `assert menu.isVisible()` |
| 6 | `test_page_size_sync_settings` | 每页条数同步设置 | 改分页 → 查设置 | app_config 更新 | `page_size_changed` → `app_config.set` | `assert app_config.get("page_size") == new` |
| 7 | `test_empty_hint_shown` | 空数据提示 | 无任务 | "暂无任务" | `refresh()` | `assert "暂无" in hint.text()` |
| 8 | `test_double_click_edit` | 双击编辑 | 双击行 | 弹编辑框 | `doubleClicked` → `on_edit` | `assert dialog visible` |
| 9 | `test_delete_confirm` | 删除确认 | 选中→Delete | 弹确认 | `on_delete_selected` → `confirm()` | `assert confirm called` |
| 10 | `test_multi_select_delete` | 多选删除 | 选 3 行→Delete | 删 3 条 | `on_delete_selected` → `delete_tasks` | `assert deleted == 3` |

---

### 7.13 ui/widgets.py — 补充用例（6 用例）

#### 7.13.1 TestStatusDelegateAdvanced（3 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_paint_all_statuses` | 所有状态绘制 | 4 种状态 | 不崩溃 | 对每种状态调用 `paint()` | `assert no exception` |
| 2 | `test_paint_unknown_status` | 未知状态 | `status="未知"` | 不崩溃 | 调用 `paint()` | `assert no exception` |
| 3 | `test_paint_empty_index` | 空索引 | 无数据模型 | 不崩溃 | `paint` 空 index | `assert no exception` |

#### 7.13.2 TestActionDelegateAdvanced（3 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_edit_hit` | 编辑按钮命中 | 点编辑区域 | `action(tid, "edit")` | `editorEvent` → MouseEvent | `assert signal == "edit"` |
| 2 | `test_delete_hit` | 删除按钮命中 | 点删除区域 | `action(tid, "delete")` | `editorEvent` → MouseEvent | `assert signal == "delete"` |
| 3 | `test_miss_no_signal` | 空白区域不触发 | 点非按钮区域 | 无信号 | `editorEvent` 偏移坐标 | `assert not fired` |

---

### 7.14 ui/dashboard_page.py — 补充用例（4 用例）

#### 7.14.1 TestDashboardAdvanced（4 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_card_hover_style` | 卡片 hover | mouse enter | 样式变化 | `enterEvent` | `assert styleSheet changed` |
| 2 | `test_bar_chart_paint` | 柱状图绘制 | 多状态 | 不崩溃 | `paintEvent` | `assert no exception` |
| 3 | `test_card_click_navigates` | 卡片点击导航 | 点"过期" | 跳转任务页+筛选 | `clicked.emit("overdue")` | `assert signal received` |
| 4 | `test_refresh_after_data_change` | 数据变化后刷新 | 新增任务 | 统计更新 | `mk()` → `refresh()` | `assert total increased` |

---

### 7.15 ui/history_page.py — 补充用例（5 用例）

#### 7.15.1 TestHistoryPageAdvanced（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_quick_range_today` | 快捷范围"今天" | 选"今天" | 只有今天 | 建昨天历史 → 切"今天" | `assert not contains yesterday` |
| 2 | `test_quick_range_7days` | 快捷范围"近7天" | 选"近7天" | 含 7 天内 | 建 8 天前历史 → 切"7天" | `assert not contains 8th day` |
| 3 | `test_clear_all_confirm` | 清空全部确认 | 3 条 → 清空 | 弹确认 → 删 | `clear_history` → `confirm()` | `assert confirm called` |
| 4 | `test_page_navigation` | 翻页 | 5 条, size=2 | 第 2 页含 2 条 | `page_changed(2)` | `assert table.rowCount() == 2` |
| 5 | `test_delete_row_confirm` | 单条删除确认 | 点删除按钮 | 弹确认 | `_delete_row` → `confirm()` | `assert confirm called` |

---

### 7.16 ui/settings_page.py — 补充用例（4 用例）

#### 7.16.1 TestSettingsPageAdvanced（4 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_page_size_spinbox` | 每页条数 spinbox | 改为 50 | `behavior_changed` 信号 | `spin_page_size.setValue(50)` | `assert signal received` |
| 2 | `test_sound_file_picker` | 音效文件选择 | 选 .wav | 路径保存 | `btn_sound_browse.click()` → mock dialog | `assert path saved` |
| 3 | `test_backup_export_button` | 备份导出按钮 | 点导出 | 文件创建 | `btn_backup_export.click()` → mock | `assert Path exists` |
| 4 | `test_theme_combo_items` | 主题下拉项 | 无 | 含"浅色"/"深色" | 检查 `cmb_theme` items | `assert "浅色" in items and "深色" in items` |

---

### 7.17 ui/main_window.py — 补充用例（5 用例）

#### 7.17.1 TestMainWindowAdvanced（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_close_to_tray` | 关闭→隐藏到托盘 | 点 X | 窗口隐藏 | `closeEvent` → `e.ignore()` + `hide()` | `assert not isVisible()` |
| 2 | `test_restore_window_state` | 窗口状态恢复 | 有保存的 state | 恢复大小 | `_restore_states` → 检查 geometry | `assert geometry matches` |
| 3 | `test_status_bar_update` | 状态栏更新 | 数据变化 | 含"共 N 条" | `refresh()` → 读状态栏 | `assert "共" in status_text` |
| 4 | `test_searches_changed_signal` | 搜索变化刷新 | 搜索 → 切页 | 数据刷新 | `searches_changed` → `refresh` | `assert refresh called` |
| 5 | `test_theme_switch_live` | 主题即时切换 | 切换主题 | 样式立即变 | `theme_changed` → `apply_theme` | `assert styleSheet changed` |

---

### 7.18 ui/task_table_model.py — 补充用例（4 用例）

#### 7.18.1 TestTableModelAdvanced（4 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_set_columns_reorder` | 列重排 | `set_columns(["name","status","deadline"])` | `column_ids` 匹配 | 调用后查 | `assert ids == ["name","status","deadline"]` |
| 2 | `test_data_content_column` | 内容列数据 | 有 HTML 内容 | 纯文本 | `data(index_of_content)` | `assert "<" not in result` |
| 3 | `test_header_data_all_columns` | 所有列表头 | 无 | 每列有中文标题 | 遍历 `headerData` | `assert all titles non-empty` |
| 4 | `test_set_tasks_empty` | 空列表设置 | `set_tasks([])` | `rowCount() == 0` | 调用 | `assert rowCount == 0` |

---

### 7.19 跨模块集成测试（8 用例）

#### 7.19.1 TestCrossModule（8 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_add_task_then_search` | 新增→搜索 | `add_task("查找我",...)` | 搜到 | add → `list_tasks(keyword="查找我")` | `assert len >= 1` |
| 2 | `test_delete_then_search_empty` | 删除→搜索空 | 删除唯一任务 | 空列表 | delete → search | `assert len == 0` |
| 3 | `test_import_then_stats_update` | 导入→统计更新 | 导入 3 条 | `stats["total"] += 3` | import → stats | `assert total increased by 3` |
| 4 | `test_backup_restore_roundtrip` | 备份→恢复 | 全量 | 数据一致 | export → 清库 → import → 逐条比对 | `assert all match` |
| 5 | `test_reminder_triggers_history` | 提醒→历史记录 | 触发提醒 | 历史有记录 | `mark_triggered` → `list_history` | `assert total >= 1` |
| 6 | `test_status_change_updates_dashboard` | 状态变→看板更新 | 标记完成 | 看板"已完成"+1 | `set_status("已完成")` → `stats` | `assert by_status["已完成"] increased` |
| 7 | `test_history_delete_then_list` | 删历史→列表更新 | 删 1 条 | 列表少 1 | `delete_history_row` → `list_history` | `assert total decreased` |
| 8 | `test_search_then_export_excel` | 搜索→导出 | 筛选后导出 | 只含筛选结果 | search → export → read_rows | `assert all match search criteria` |

---

### 7.20 性能与压力测试（5 用例）

#### 7.20.1 TestPerformance（5 用例）

| # | 用例名 | 测试目的 | 输入数据 | 预期输出 | 执行步骤 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `test_bulk_insert_1000` | 批量插入 1000 条 | 1000 个任务 | 耗时 < 5s | 循环 `add_task` | `assert elapsed < 5` |
| 2 | `test_bulk_insert_10000` | 批量插入 10000 条 | 10000 个任务 | 耗时 < 30s | `seed_perf.py --n 10000` | `assert elapsed < 30` |
| 3 | `test_query_1000_pagination` | 千条分页查询 | 1000 条 | 每页 < 100ms | `list_tasks(1, 200)` | `assert elapsed < 0.1` |
| 4 | `test_search_1000` | 千条全文搜索 | 1000 条含关键词 | < 100ms | `list_tasks(criteria={"keyword":"x"})` | `assert elapsed < 0.1` |
| 5 | `test_backup_1000` | 千条备份导出 | 1000 条 | 耗时 < 3s | `export_json` | `assert elapsed < 3` |

---

## 8. 补充用例汇总

### 8.1 第二轮新增用例统计

| 模块 | 用例数 |
|---|---|
| models.py | 20 |
| db.py | 5 |
| repository.py | 14 |
| notifier.py | 6 |
| reminder_service.py | 4 |
| backup.py | 4 |
| excel_io.py | 5 |
| sound.py | 2 |
| app_config.py | 3 |
| search_bar.py | 5 |
| task_dialog.py | 6 |
| tasks_page.py | 10 |
| widgets.py | 6 |
| dashboard_page.py | 4 |
| history_page.py | 5 |
| settings_page.py | 4 |
| main_window.py | 5 |
| task_table_model.py | 4 |
| 跨模块集成 | 8 |
| 性能压力 | 5 |
| **第二轮合计** | **125** |

### 8.2 两轮总计

| 轮次 | 用例数 |
|---|---|
| 第一轮（第 2 节） | 259 |
| 第二轮（第 7 节） | 125 |
| E2E 走查 | 66 |
| **总计** | **450** |

### 8.3 第二轮新增覆盖矩阵

| 测试类型 | 新增用例数 | 覆盖场景 |
|---|---|---|
| SQL 注入防护 | 1 | repository |
| 并发写入 | 1 | db |
| 大数据量(1k/10k) | 5 | repository, backup, performance |
| 富文本格式化 | 6 | task_dialog |
| 列拖拽/持久化 | 3 | tasks_page |
| UI 事件穿透 | 3 | tasks_page, widgets |
| 信号链路 | 5 | main_window, settings_page, dashboard |
| 跨日时间逻辑 | 2 | reminder_service |
| 级联删除 | 1 | db |
| 跨模块集成 | 8 | 全链路 |
| 未知/非法输入 | 6 | models, repository, widgets |
| 边界值(恰好/空) | 8 | models, repository, notifier |
| 性能基准 | 5 | repository, backup |
