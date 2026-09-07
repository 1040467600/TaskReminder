"""通过 GitHub REST API 创建 Release 并上传附件（令牌取自 git credential manager，
不落盘、不打印）。

用法：
    python scripts/upload_release.py v2.0.4

前置：git push 凭据已存入 Windows 凭据管理器（credential.helper=manager）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "1040467600/TaskReminder"
API = "https://api.github.com"
UPLOAD = "https://uploads.github.com"
TIMEOUT = 600
MB = 1024 * 1024

RELEASE_NOTES = """## v2.0.5 质量保障

- **新增 160 项综合测试**（`tests/test_comprehensive.py`）：覆盖 12 个核心模块的正常流程、边界条件、异常场景与联动行为
  - 单元测试：models（富文本转换/时间解析/数据类）、db（迁移回填/事务回滚）、app_config（类型序列化）、notifier（提醒队列/稍后提醒多档）、reminder_service（间隔钳制/跨日重置/异常容错）
  - 集成测试：backup（部分数据/字段缺失兼容）、excel_io（时间解析/导入报告）、search_bar（条件往返/防抖合并）、task_dialog（时间预设/自动联动）、repository（复合查询/排序/分页越界）
  - 功能测试：分页栏跳页与零条数、中文确认弹窗、看板卡片点击与统计刷新
- 全量测试 **249 项全部通过**（pytest junit 证据：0 失败 / 0 错误），E2E 走查 64 项通过
- 新增测试报告文档 `docs/test_report.md`（用例明细、覆盖率矩阵、与已有测试的关系）
- 新增 Release 自动上传脚本 `scripts/upload_release.py`（REST API，令牌不落盘，幂等重试）
- 应用功能代码与 v2.0.4 一致，未做改动

**附件**：`TaskReminderSetup.exe` 为安装包（推荐），`TaskReminder.exe` 为单文件便携版。
"""


def get_token() -> str:
    p = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
    )
    cred = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
    token = cred.get("password") or ""
    if not token:
        raise SystemExit("未从 git credential manager 取到令牌，请先确认 git push 凭据已保存")
    return token


def api(method: str, url: str, token: str, body=None, content_type="application/json"):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "taskreminder-release",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("message", detail)
        except json.JSONDecodeError:
            pass
        return e.code, {"_error": detail}


def main(tag: str) -> int:
    root = Path(__file__).resolve().parent.parent
    assets = [root / "dist" / "TaskReminderSetup.exe", root / "dist" / "TaskReminder.exe"]
    for a in assets:
        if not a.exists():
            raise SystemExit(f"缺少附件：{a}")

    token = get_token()

    # 1. 找到或创建 Release
    st, rel = api("GET", f"{API}/repos/{REPO}/releases/tags/{tag}", token)
    if st == 404:
        print(f"Release {tag} 不存在，创建中 ...")
        st, rel = api("POST", f"{API}/repos/{REPO}/releases", token, {
            "tag_name": tag,
            "name": f"任务提醒助手 {tag}",
            "body": RELEASE_NOTES,
            "draft": False,
            "prerelease": False,
        })
    if st not in (200, 201):
        print(f"Release 获取/创建失败：HTTP {st} {rel.get('_error')}")
        return 1
    rel_id = rel["id"]
    print(f"Release 就绪：{rel['html_url']}（id={rel_id}）")

    # 2. 逐个附件：同名且大小一致则跳过，否则删旧传新
    existing = {a["name"]: a for a in rel.get("assets", [])}
    for path in assets:
        local_size = path.stat().st_size
        name = path.name
        old = existing.get(name)
        if old and old["state"] == "uploaded" and old["size"] == local_size:
            print(f"[skip] {name} 已存在且大小一致（{local_size/MB:.1f} MB）")
            continue
        if old:
            print(f"[replace] 删除旧附件 {name}（{old['size']/MB:.1f} MB）")
            st, _ = api("DELETE", f"{API}/repos/{REPO}/releases/assets/{old['id']}", token)
            if st not in (204, 200):
                print(f"删除旧附件失败：HTTP {st}")
                return 1
        print(f"[upload] {name}（{local_size/MB:.1f} MB）上传中 ...")
        q = urllib.parse.urlencode({"name": name})
        st, res = api("POST",
                      f"{UPLOAD}/repos/{REPO}/releases/{rel_id}/assets?{q}",
                      token, body=path.read_bytes(),
                      content_type="application/octet-stream")
        if st != 201:
            print(f"上传失败：HTTP {st} {res.get('_error')}")
            return 1
        if res.get("size") != local_size or res.get("state") != "uploaded":
            print(f"上传校验异常：state={res.get('state')} size={res.get('size')}")
            return 1
        print(f"[ok] {name} 上传完成，state=uploaded，size={res['size']}")

    # 3. 回读核对（机器可验证证据）
    st, rel = api("GET", f"{API}/repos/{REPO}/releases/{rel_id}", token)
    print("\n===== Release 最终状态 =====")
    print(f"url: {rel['html_url']}")
    print(f"draft: {rel['draft']}  prerelease: {rel['prerelease']}  published: {rel.get('published_at')}")
    for a in rel.get("assets", []):
        print(f"  - {a['name']}: {a['size']/MB:.1f} MB, state={a['state']}, downloads={a['download_count']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("用法：python scripts/upload_release.py vX.Y.Z")
    raise SystemExit(main(sys.argv[1]))
