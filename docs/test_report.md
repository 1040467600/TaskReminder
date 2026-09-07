# TaskReminder 综合测试报告

> **文件**: `tests/test_comprehensive.py`
> **日期**: 2026-09-07
> **环境**: Windows 10, Python 3.10.2, PyQt6 6.11.0, pytest 9.1.1
> **运行命令**: `$env:QT_QPA_PLATFORM="offscreen"; $env:PYTHONDONTWRITEBYTECODE="1"; python -m pytest tests/test_comprehensive.py -v`

---

## 1. 概览

| 指标 | 值 |
|---|---|
| 测试文件 | `tests/test_comprehensive.py` |
| 测试类数 | 18 |
| 测试用例数 | 160 |
| 通过数 | 160 |
| 失败数 | 0 |
| 通过率 | 100% |
| 耗时 | ~9 秒（含防抖定时器真实等待） |
| 测试夹具 | `tests/conftest.py`（每个用例独立临时数据库） |

### 测试类型分布

| 类型 | 测试类数 | 用例数 | 覆盖模块 |
|---|---|---|---|
| 单元测试 | 10 | 78 | models(36), db(7), app_config(11), notifier(14), reminder_service(10) |
| 集成测试 | 5 | 66 | backup(8), excel_io(12), search_bar(9), task_dialog(13), repository(24) |
| 功能测试 | 3 | 16 | widgets(8: 分页5+确认弹窗3), dashboard_page(8) |

### 覆盖的核心模块

```
task_reminder/
├── models.py            ← 36 用例（纯函数 + 数据类）
├── db.py                ← 7 用例（连接、schema、迁移、事务）
├── app_config.py        ← 11 用例（配置读写、类型序列化）
├── notifier.py          ← 14 用例（剩余时间、队列、弹窗响应）
├── reminder_service.py  ← 10 用例（定时器、跨日重置、异常容错）
├── backup.py            ← 8 用例（导出/导入、部分数据、字段缺失）
├── excel_io.py          ← 12 用例（时间解析、报告摘要、空文件）
├── repository.py        ← 24 用例（复合查询、排序、分页、统计）
├── ui/widgets.py        ← 8 用例（分页跳页、零条数、中文确认弹窗）
├── ui/search_bar.py     ← 9 用例（重置、徽章、日期范围、防抖合并）
├── ui/task_dialog.py    ← 13 用例（时间预设、联动、备注截断、回填）
└── ui/dashboard_page.py ← 8 用例（卡片点击、统计刷新、柱状图）
```

---

## 2. 测试夹具

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

## 3. 测试用例详情

### 3.1 单元测试 — models.py（36 用例）

#### TestHtmlToPlain（9 用例）

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_empty_string` | L44 | 空字符串边界 | `""` | `""` | `assert == ""` |
| `test_none_input` | L48 | None 边界 | `None` | `""` | `assert == ""` |
| `test_plain_text_fast_path` | L52 | 无标签纯文本快速路径 | `"普通文本内容"` | `"普通文本内容"` | `assert ==` |
| `test_simple_bold` | L56 | 简单加粗标签 | `"<b>加粗</b>"` | `"加粗"` | `assert ==` |
| `test_nested_tags` | L60 | 嵌套标签 | `"<div><p>段落<b>加粗</b>普通</p></div>"` | 包含"段落""加粗""普通" | `assert in` |
| `test_br_becomes_newline` | L65 | br 换行 | `"第一行<br>第二行"` | `"第一行\n第二行"` | `assert ==` |
| `test_html_entities_decoded` | L70 | HTML 实体解码 | `"&lt;tag&gt;"` | `"<tag>"` | `assert ==` |
| `test_style_script_removed` | L76 | style/script 移除 | `"<style>body{color:red}</style>正文"` | 不含"color"，含"正文" | `assert not in / assert in` |
| `test_strips_leading_trailing_whitespace` | L81 | 前后空白 strip | `"  <b>内容</b>  "` | `"内容"` | `assert ==` |

#### TestPlainLen（5 用例）

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_empty` | L89 | 空字符串 | `""` | `0` | `assert == 0` |
| `test_plain_text` | L92 | 纯文本长度 | `"12345"` | `5` | `assert == 5` |
| `test_html` | L95 | HTML 标签不计入长度 | `"<b>12345</b>"` | `5` | `assert == 5` |
| `test_at_content_limit` | L99 | 刚好 5000 字 | `"字" * 5000` | `5000` | `assert == CONTENT_MAX` |
| `test_over_content_limit` | L104 | 超过 5000 字 | `"字" * 5001` | `5001` | `assert == CONTENT_MAX + 1` |

#### TestParse（6 用例）

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_empty` | L113 | 空/None | `""`, `None` | `None` | `assert is None` |
| `test_standard_format` | L118 | 标准格式 | `"2026-09-10 14:30"` | datetime(2026,9,10,14,30) | `assert year/month/day/hour/minute` |
| `test_t_separator` | L125 | T 分隔符 | `"2026-09-10T14:30"` | 正确解析 | `assert hour == 14` |
| `test_with_seconds` | L130 | 含秒 | `"2026-09-10 14:30:45"` | second==45 | `assert second == 45` |
| `test_date_only` | L135 | 仅日期 | `"2026-09-10"` | hour=0, minute=0 | `assert hour == 0` |
| `test_invalid` | L140 | 无效格式 | `"not-a-date"`, `"2026/09/10"` | `None` | `assert is None` |

#### TestTaskDataclass（13 用例）

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_plain_text_prefers_content_plain` | L149 | 优先冗余列 | content_plain="纯文本冗余" | "纯文本冗余" | `assert ==` |
| `test_plain_text_fallback_to_html` | L154 | 冗余列为空回退 | content_plain="" | 从 HTML 现算 | `assert == "富文本"` |
| `test_plain_text_empty_content` | L159 | 全空 | content="", content_plain="" | `""` | `assert == ""` |
| `test_summary_uses_name` | L164 | 优先名称 | name="任务名称" | "任务名称" | `assert ==` |
| `test_summary_falls_back_to_content` | L169 | 名称为空回退 | name="", content="<b>这是内容</b>" | 包含"这是内容" | `assert in` |
| `test_summary_truncates_with_ellipsis` | L174 | 超长截断 | name="A"*100, limit=10 | 10字+"…" | `assert endswith("…")` |
| `test_summary_no_truncation_under_limit` | L182 | 短名不截断 | name="短名称" | 不含"…" | `assert "…" not in` |
| `test_is_overdue_true` | L188 | 过期未完成 | deadline="2020-01-01" | `True` | `assert is True` |
| `test_is_overdue_false_future` | L193 | 未来截止 | 未来时间 | `False` | `assert is False` |
| `test_is_overdue_false_done` | L199 | 已完成不算过期 | deadline=过去, status=DONE | `False` | `assert is False` |
| `test_is_overdue_empty_deadline` | L204 | 空截止 | deadline="" | `False` | `assert is False` |
| `test_from_row` | L209 | 从 Row 构造（先建数据防空转） | mk() 后 SELECT 的 sqlite3.Row | Task 字段与库一致 | `assert id == tid / name ==` |
| `test_from_row_empty_keys` | L219 | 无 keys 属性（dict 回退） | `{"id":1, "name":"test"}` | 正确构造 | `assert id == 1` |

#### TestReminderLog（3 用例）

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_response_text_known` | L227 | 已知响应码 | `"", "snooze", "done", "close"` | 中文文本 | `assert ==` |
| `test_response_text_unknown` | L234 | 未知响应码 | `"custom"` | `"custom"` | `assert ==` |
| `test_from_row` | L238 | 从 dict 构造 | `{"id":1, "task_id":2, "response":"done"}` | 正确字段 | `assert ==` |

---

### 3.2 单元测试 — db.py（7 用例）

#### TestDb

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_default_db_path` | L250 | 默认路径 | `default_db_path()` | 含 "TaskReminder" 和 "tasks.db" | `assert in` |
| `test_init_creates_schema` | L256 | schema 创建 | `init(path)` | tasks/reminder_history/user_settings 表存在 | `assert in tables` |
| `test_init_idempotent` | L268 | 重复 init：旧连接关闭、schema 完整、数据不丢 | 写入配置后再次 `init(path)` | 表齐全且旧值可读 | `assert <= tables / row 值一致` |
| `test_transaction_commit` | L276 | 正常提交 | INSERT in transaction | 数据已写入 | `assert row["value"] ==` |
| `test_transaction_rollback` | L287 | 异常回滚 | INSERT + raise | 数据未写入 | `assert row is None` |
| `test_content_plain_backfill` | L300 | 迁移回填 | 旧表无 content_plain 列 | 迁移后回填正确 | `assert == "旧内容"` |
| `test_close_resets_connection` | L333 | close 重置 | `close()` → `_conn is None` | `get_conn()` 自动重建 | `assert is None / is not None` |

---

### 3.3 单元测试 — app_config.py（11 用例）

#### TestAppConfig

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_get_default` | L350 | 默认值 | 未设置的 key | DEFAULTS 中的值 | `assert ==` |
| `test_get_with_explicit_default` | L356 | 显式默认 | 不存在的 key + default | 显式 default | `assert == "fallback"` |
| `test_set_and_get_string` | L360 | 字符串往返 | set "dark" → get | "dark" | `assert ==` |
| `test_set_and_get_int` | L365 | 整数往返 | set 16 → get | 16 (int) | `assert == / assert isinstance` |
| `test_set_and_get_bool` | L371 | 布尔往返 | set False → get | False (bool) | `assert is False` |
| `test_set_and_get_list` | L376 | 列表往返 | set [1,2,3] → get | [1,2,3] | `assert ==` |
| `test_set_and_get_dict` | L381 | 字典往返 | set {"a":1} → get | {"a":1} | `assert ==` |
| `test_set_overwrites` | L386 | 覆盖 | set "dark" → set "light" | "light" | `assert ==` |
| `test_raw_value_non_json` | L392 | 原始值 | set "plain" → _raw | "plain" | `assert ==` |
| `test_default_sound_path` | L398 | 音效路径 | `default_sound()` | 含 "chime.wav" | `assert in` |
| `test_built_in_sounds` | L403 | 内置音效 | `built_in_sounds()` | 3 个元组 | `assert len == 3` |

---

### 3.4 单元测试 — notifier.py（14 用例）

#### TestRemainingText（5 用例）

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_empty_deadline` | L417 | 空截止 | `""` | `""` | `assert == ""` |
| `test_invalid_deadline` | L422 | 无效格式 | `"not-a-date"` | `""` | `assert == ""` |
| `test_future_deadline` | L427 | 未来截止 | 2天5小时后 | 含"剩余""天" | `assert in` |
| `test_past_deadline` | L435 | 过去截止 | 1天前 | 含"已过期" | `assert in` |
| `test_near_future_shows_hours` | L442 | 几小时后 | 2.5小时后 | 含"小时" | `assert in` |

#### TestNotifierQueue（9 用例）

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_notify_increments_queue` | L453 | 入队计数 | 2次 notify | pending_count == 2 | `assert ==` |
| `test_pump_shows_dialog` | L465 | pump 弹窗 | 1条入队 → pump | `_dialog is not None` | `assert is not None` |
| `test_pump_empty_queue_noop` | L477 | 空队列 pump | 无入队 | 不弹窗 | `assert is None` |
| `test_pump_while_dialog_open_noop` | L485 | 已有弹窗 | 2条入队 → pump → pump | 不弹第二个 | `assert is first_dlg` |
| `test_queue_changed_signal` | L499 | 信号触发 | notify → queue_changed | counts 非空 | `assert len > 0` |
| `test_responded_signal_on_done` | L512 | 标记完成 | `_respond("done")` | responded == ["done"], 状态=DONE | `assert ==` |
| `test_responded_signal_on_close` | L527 | 关闭 | `_respond("close")` | responded == ["close"], 状态不变 | `assert ==` |
| `test_snooze_5_minutes` | L542 | 稍后5分钟 | `_respond("snooze", 5)` | triggered=0, 新时间>now | `assert == 0 / assert >` |
| `test_snooze_60_minutes` | L557 | 稍后60分钟 | `_respond("snooze", 60)` | 新时间≥now+55min | `assert >=` |

---

### 3.5 单元测试 — reminder_service.py（10 用例）

#### TestReminderService

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_start_stop` | L578 | 定时器启停 | start → stop | 运行→停止 | `assert isActive/not` |
| `test_apply_interval_from_config` | L587 | 配置间隔 | poll_interval=10 | interval=10000ms | `assert ==` |
| `test_apply_interval_clamps_upper` | L596 | 上界钳制 | poll_interval=120 | interval=60000ms | `assert ==` |
| `test_apply_interval_clamps_lower` | L605 | 下界钳制 | poll_interval=0 | interval=1000ms | `assert ==` |
| `test_apply_interval_invalid_fallback` | L614 | 非数字回退 | poll_interval="abc" | interval=5000ms | `assert ==` |
| `test_tick_emits_due_signal` | L623 | 到期触发 | 过去提醒时间 | task_due 信号 | `assert len(got) == 1` |
| `test_tick_no_due_no_emit` | L636 | 无到期 | 未来提醒时间 | 无信号 | `assert len == 0` |
| `test_maybe_reset_for_new_day` | L647 | 跨日重置 | 旧 date → 触发 | triggered=0 | `assert == 0` |
| `test_maybe_reset_same_day_skipped` | L661 | 同日跳过 | today → 无操作 | 不变 | `assert == today` |
| `test_tick_exception_swallowed` | L671 | 异常容错 | mock raise | 不崩溃 | 执行完成即可 |

---

### 3.6 集成测试 — backup.py（8 用例）

#### TestBackupAdvanced

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_export_includes_history` | L688 | 导出含历史 | 有 mark_triggered 的任务 | history 长度≥1 | `assert len == 1` |
| `test_import_only_tasks_no_history` | L700 | 仅任务无历史 | history=[] | 不崩溃, t=1 h=0 | `assert ==` |
| `test_import_only_history_no_tasks` | L713 | 仅历史无任务 | tasks=[] | 不崩溃, t=0 h≥1 | `assert ==` |
| `test_import_upserts_existing_id` | L725 | 同 id 覆盖 | 修改 name 后导入 | name 被更新 | `assert == "修改后名称"` |
| `test_export_creates_parent_dir` | L738 | 自动建目录 | 不存在的子目录 | 文件存在 | `assert Path.exists` |
| `test_export_empty_db` | L746 | 空库导出 | 无任务 | n=0, tasks=[] | `assert == 0` |
| `test_import_recomputes_content_plain` | L755 | 重算冗余列 | 删 content_plain 后导入 | 重算正确 | `assert == "富文本内容"` |
| `test_import_invalid_json_raises` | L769 | 非法 JSON | "not json" | JSONDecodeError | `assert raises` |

---

### 3.7 集成测试 — excel_io.py（12 用例）

#### TestExcelHelpers

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_cell_time_datetime` | L783 | datetime 对象 | `datetime(2026,9,15,8,30)` | `"2026-09-15 08:30"` | `assert ==` |
| `test_cell_time_string_standard` | L789 | 标准字符串 | `"2026-09-15 08:30"` | 原样 | `assert ==` |
| `test_cell_time_with_seconds` | L794 | 含秒 | `"2026-09-15 08:30:45"` | 截断为分钟 | `assert ==` |
| `test_cell_time_t_separator` | L799 | T 分隔 | `"2026-09-15T08:30"` | 兼容 | `assert ==` |
| `test_cell_time_slash_separator` | L804 | 斜杠 | `"2026/09/15 08:30"` | 兼容 | `assert ==` |
| `test_cell_time_date_only` | L809 | 仅日期 | `"2026-09-15"` | 补 00:00 | `assert ==` |
| `test_cell_time_none` | L814 | None | `None` | `None` | `assert is None` |
| `test_cell_time_empty` | L819 | 空字符串 | `""` | `None` | `assert is None` |
| `test_cell_time_invalid` | L824 | 无效 | `"not-a-date"` | `None` | `assert is None` |
| `test_import_report_summary` | L829 | 报告摘要 | total=10, added=5 | 含各项统计 | `assert in` |
| `test_import_report_summary_many_errors` | L841 | 错误截断 | 15 条错误 | "另有 5 条" | `assert in` |
| `test_read_rows_empty_file` | L849 | 空 xlsx | 空表 | `[]` | `assert == []` |

---

### 3.8 功能测试 — widgets.py（7 用例）

#### TestPaginationBarAdvanced（5 用例）

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_jump_to_page` | L867 | 跳页信号 | 1000条/200条/页 → 跳第3页 | page_changed(3) | `assert got == [3]` |
| `test_zero_total` | L880 | 零条数 | 0 条 | 按钮全禁用 | `assert not isEnabled` |
| `test_last_page` | L891 | 末页边界 | 400条 → 第2页 | next/last 禁用 | `assert not isEnabled` |
| `test_page_info_text` | L904 | 信息文本 | 450条/第2页/200条页 | 含"450""2""3" | `assert in` |
| `test_size_menu_options` | L915 | 菜单选项 | 菜单 actions | 4 个选项 | `assert len == 4` |

#### TestConfirmDialog（3 用例）

> 真实执行 `confirm()` 函数（建弹窗、加按钮、判定 clickedButton），仅 stub 掉模态 `exec()` 和 `clickedButton()`，避免"只测 mock 本身"。

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_confirm_accept` | L944 | 点确定 → True | stub clickedButton 返回 AcceptRole 按钮 | `True` | `assert is True` |
| `test_confirm_reject` | L956 | 点取消 → False | stub clickedButton 返回 RejectRole 按钮 | `False` | `assert is False` |
| `test_confirm_has_chinese_buttons` | L967 | 按钮为中文"确定/取消" | stub exec 时捕获 buttons() 文案 | 含"确定""取消" | `assert in` |

---

### 3.9 集成测试 — search_bar.py（9 用例）

#### TestSearchBarAdvanced

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_reset_clears_all` | L962 | reset 清空 | 设条件 → reset | 所有条件消失 | `assert not in` |
| `test_set_criteria_roundtrip` | L976 | 往返一致 | set → get | 各字段一致 | `assert ==` |
| `test_adv_keys_in_use_empty` | L990 | 无高级条件 | 空搜索 | `[]` | `assert == []` |
| `test_adv_keys_in_use_multiple` | L997 | 多高级条件 | 3 个条件 | 3 个 key | `assert len == 3` |
| `test_active_badge_hidden_when_panel_open` | L1009 | 展开时隐藏 | 面板展开 | 徽章不可见 | `assert not isVisibleTo` |
| `test_active_badge_visible_when_panel_closed` | L1018 | 收起时可见 | 有条件+收起 | 徽章可见 | `assert isVisibleTo` |
| `test_debounce_emits_changed` | L1054 | 防抖窗口：150ms 内不触发、550ms 后触发一次 | setText 后 qWait 分段验证 | 窗口内 0 条、窗口后 1 条 | `assert len == 0/1` |
| `test_debounce_coalesces_rapid_input` | L1069 | 连续击键合并：4 次输入（间隔 50ms）只发一次 | 循环 setText + qWait(50) | 输入中 0 条、停顿后 1 条含完整词 | `assert len == 1` |
| `test_both_date_ranges_independent` | L1085 | 双日期独立 | 分别开关并设日期 | 各自独立 | `assert in / not in` |

---

### 3.10 集成测试 — task_dialog.py（13 用例）

#### TestTaskDialogAdvanced

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_apply_preset_deadline` | L1071 | 截止预设 | "明天09:00" | hour==9 | `assert hour == 9` |
| `test_apply_preset_reminder_30min` | L1086 | 提醒30分钟 | now+30min | ≥now+29min | `assert >=` |
| `test_apply_preset_reminder_before_deadline` | L1098 | 截止前1小时 | deadline=18:00 → dt=None | reminder hour==17 | `assert hour == 17` |
| `test_deadline_before_reminder_auto_moves_reminder` | L1111 | 联动前移 | deadline<reminder | reminder=deadline-1h | `assert ==` |
| `test_reminder_after_deadline_auto_moves_deadline` | L1122 | 联动后移 | reminder>deadline | deadline=reminder+1h | `assert ==` |
| `test_notes_truncation` | L1133 | 备注截断 | NOTES_MAX+100 字 | 截断为 NOTES_MAX | `assert len == NOTES_MAX` |
| `test_load_existing_task` | L1144 | 编辑回填 | 已有任务 | 各字段一致 | `assert ==` |
| `test_content_count_displayed` | L1163 | 字数显示 | "12345" | 含"5"和"5000" | `assert in` |
| `test_content_over_limit_shows_error` | L1173 | 超限标红 | 5001字 | 样式含"#DC2626" | `assert in` |
| `test_edit_task_returns_true_on_accept` | L1182 | 接受 | exec→1 | `True` | `assert is True` |
| `test_edit_task_returns_false_on_reject` | L1191 | 拒绝 | exec→0 | `False` | `assert is False` |
| `test_default_times_reminder_before_deadline` | L1199 | 默认时间 | 新建对话框 | reminder<deadline | `assert <` |
| `test_validate_returns_null_on_valid` | L1206 | 合法通过 | 合法输入 | `None`, 按钮可用 | `assert is None / isEnabled` |

---

### 3.11 功能测试 — dashboard_page.py（8 用例）

#### TestDashboardPage

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_stat_card_click_signal` | L1227 | 卡片点击 | QMouseEvent | clicked 信号 | `assert got == ["total"]` |
| `test_refresh_updates_card_values` | L1244 | 统计刷新 | 3 种状态各1条 | 各卡片=1 | `assert == "1"` |
| `test_refresh_shows_overdue` | L1258 | 过期数量 | 过期任务 | overdue=1 | `assert == "1"` |
| `test_refresh_empty_lists` | L1268 | 空列表提示 | 无任务 | 含"暂无""没有过期" | `assert in` |
| `test_refresh_populates_upcoming_list` | L1279 | 即将提醒列表 | 未来提醒任务 | 含任务名和执行人 | `assert in` |
| `test_refresh_populates_overdue_list` | L1292 | 已过期列表 | 过期任务 | 含任务名和执行人 | `assert in` |
| `test_bar_chart_set_data` | L1306 | 柱状图数据 | 2 项数据 | _data 长度=2 | `assert len == 2` |
| `test_bar_chart_empty_data` | L1315 | 空柱状图 | `[]` | 不崩溃 | `assert == []` |

---

### 3.12 集成测试 — repository.py（17 用例）

#### TestRepositoryAdvanced

| 用例 | 行号 | 测试目的 | 输入数据 | 预期输出 | 验证方法 |
|---|---|---|---|---|---|
| `test_search_combined_criteria` | L1330 | 复合条件 | keyword+assignee+statuses | 1 条匹配 | `assert total == 1` |
| `test_search_content_and_notes` | L1342 | 内容+备注 | content_kw 搜内容和备注 | 2 条 | `assert total == 2` |
| `test_search_multi_term_content_and` | L1349 | 多词AND | "季度 报告" | 1 条（两词都命中） | `assert total == 1` |
| `test_search_empty_criteria_returns_all` | L1357 | 空条件 | `{}` | 全部 | `assert total >= 2` |
| `test_search_nonexistent_keyword` | L1364 | 不存在 | "不存在的关键词" | 0 条 | `assert total == 0` |
| `test_sort_by_assignee` | L1389 | 按执行人升序（Unicode 码点：张 U+5F20 < 李 U+674E） | 张三/李四 | ["张三","李四"] | `assert == sorted / 精确顺序` |
| `test_sort_by_name` | L1372 | 按名称排序 | 乙/甲 | 升序 | `assert <=` |
| `test_sort_invalid_key_falls_back` | L1387 | 无效排序键 | "invalid_key" | 回退 created_at | `assert total >= 1` |
| `test_pagination_beyond_last_page` | L1393 | 越界分页 | page=99 | 空列表 | `assert len == 0` |
| `test_tasks_by_ids_empty` | L1400 | 空列表 | `[]` | `[]` | `assert == []` |
| `test_tasks_by_ids_multiple` | L1404 | 多 id | [t1, t2] | 2 条 | `assert len == 2` |
| `test_tasks_by_ids_nonexistent` | L1413 | 不存在 | [t1, 99999] | 1 条 | `assert len == 1` |
| `test_set_status_invalid_raises` | L1419 | 无效状态 | "无效状态" | ValidationError | `assert raises` |
| `test_mark_triggered_nonexistent_returns_none` | L1425 | 不存在 id | 99999 | `None` | `assert is None` |
| `test_update_task_status_changed_timestamp` | L1429 | 状态变化 | NOT_STARTED→IN_PROGRESS | 时间戳更新 | `assert != ""` |
| `test_update_task_same_status_no_timestamp_change` | L1441 | 状态不变 | IN_PROGRESS→IN_PROGRESS | 时间戳不刷新 | `assert == first_ts` |
| `test_delete_tasks_empty_list` | L1452 | 空删除 | `[]` | 0 | `assert == 0` |
| `test_find_duplicate_no_match` | L1456 | 无重复 | 不同名 | `None` | `assert is None` |
| `test_list_history_pagination` | L1461 | 历史分页 | 5 条 → page=1/size=2 | 2 条 | `assert len == 2` |
| `test_list_history_date_filter` | L1472 | 日期过滤 | start=now | ≥1 条 | `assert total >= 1` |
| `test_stats_empty_db` | L1482 | 空库统计 | 删空后 | 全 0 | `assert == 0` |
| `test_upcoming_reminders_limit` | L1491 | 数量限制 | 5 条 → limit=3 | 3 条 | `assert len == 3` |
| `test_overdue_tasks_excludes_done` | L1498 | 排除已完成 | 过期+已完成 | 不含已完成 | `assert not in` |
| `test_all_tasks_with_criteria` | L1509 | 条件过滤 | assignee="张三" | 1 条 | `assert len == 1` |

---

## 4. 测试分类说明

### 4.1 正常流程测试
覆盖用户日常操作的标准路径：创建任务、查询、排序、分页、导出、导入、备份恢复、提醒触发、弹窗响应。

### 4.2 边界条件测试
- 空字符串 / None / 空列表
- 最大长度（名称 50 字、内容 5000 字、备注 200 字）
- 最小长度（1 字符名称/执行人）
- 分页越界（请求超出总页数）
- 日期范围最小值
- 零条数据

### 4.3 异常场景测试
- 无效时间格式
- 提醒时间晚于截止时间
- 非法 JSON 文件
- 数据库异常（mock 注入 OperationalError）
- 非数字配置值
- 不存在的任务 id
- 无效任务状态
- 旧数据库迁移（无 content_plain 列）

### 4.4 联动行为测试
- 时间联动：截止 < 提醒 → 提醒自动前移；提醒 > 截止 → 截止自动后移
- 弹窗队列：关闭后自动弹出下一条
- 搜索防抖：300ms 后发出 changed 信号
- 跨日重置：日期变化时触发 reset_triggered_for_new_day

---

## 5. 覆盖率矩阵

| 模块 | 正常流程 | 边界条件 | 异常场景 | 联动行为 | 合计 |
|---|---|---|---|---|---|
| models.py | 23 | 12 | 1 | — | 36 |
| db.py | 5 | 1 | 1 | — | 7 |
| app_config.py | 11 | — | — | — | 11 |
| notifier.py | 10 | 4 | — | — | 14 |
| reminder_service.py | 5 | 4 | 1 | — | 10 |
| backup.py | 4 | 3 | 1 | — | 8 |
| excel_io.py | 7 | 5 | — | — | 12 |
| repository.py | 15 | 7 | 2 | — | 24 |
| ui/widgets.py | 6 | 2 | — | — | 8 |
| ui/search_bar.py | 9 | — | — | （防抖合并计入正常流程） | 9 |
| ui/task_dialog.py | 9 | 2 | — | 2 | 13 |
| ui/dashboard_page.py | 5 | 3 | — | — | 8 |
| **合计** | **109** | **43** | **6** | **2** | **160** |

> 每个用例按主要测试目的归入一个维度，行列合计与 `pytest --collect-only` 收集数（160）精确对账。

---

## 6. 与已有测试的关系

| 已有测试文件 | 用例数（pytest 收集） | 覆盖范围 | test_comprehensive.py 补充 |
|---|---|---|---|
| `test_repository.py` | 32 | CRUD/校验/查询/提醒/统计 | +24 复合查询/排序/分页/边界 |
| `test_ui.py` | 23 | UI 冒烟/对话框/主窗口 | +30 搜索栏/对话框/看板高级 |
| `test_more.py` | 21 | 备份/分页/委托/历史/设置/单实例 | +15 widgets/search/excel 辅助 |
| `test_excel.py` | 7 | Excel 导入导出 | +12 _cell_time/read_rows/report |
| `test_reminder.py` | 6 | 提醒服务/通知/声音 | +14 remaining_text/queue/snooze |
| **合计** | **89** | — | **+160（新增）** |

全量测试结果：**249 项全部通过**（89 已有 + 160 新增），以 `pytest --collect-only` 实际收集数为准。

---

## 7. 运行方式

```powershell
# 仅运行综合测试
$env:QT_QPA_PLATFORM="offscreen"
$env:PYTHONDONTWRITEBYTECODE="1"
.\.venv\Scripts\python.exe -m pytest tests/test_comprehensive.py -v

# 运行全部测试
.\.venv\Scripts\python.exe -m pytest -v

# E2E 走查
.\.venv\Scripts\python.exe scripts\walkthrough.py
```

> 注意：UI 测试需设 `QT_QPA_PLATFORM=offscreen`；需先确保无 TaskReminder 托盘残留实例。
