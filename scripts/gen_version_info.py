"""生成 Windows 版本资源文件（build/version_info.txt / version_info_setup.txt）。

任务管理器「详细信息」、文件属性中显示的 文件描述/产品名/版本号 来自该资源；
无版本资源时进程名只能显示 EXE 文件名。由 build_windows.ps1 在 PyInstaller 前调用。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from task_reminder import APP_NAME, __version__  # noqa: E402

TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({ver_tuple}),
    prodvers=({ver_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404B0',
        [StringStruct('CompanyName', '彭城派出所'),
         StringStruct('FileDescription', '{desc}'),
         StringStruct('FileVersion', '{ver}'),
         StringStruct('InternalName', 'TaskReminder'),
         StringStruct('LegalCopyright', ''),
         StringStruct('OriginalFilename', '{filename}'),
         StringStruct('ProductName', '{product}'),
         StringStruct('ProductVersion', '{ver}')])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""


def write_version_file(path: Path, desc: str, product: str, filename: str) -> None:
    parts = (__version__.split(".") + ["0", "0", "0"])[:4]
    ver_tuple = ", ".join(parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        TEMPLATE.format(ver_tuple=ver_tuple, ver=__version__,
                        desc=desc, product=product, filename=filename),
        encoding="utf-8",
    )
    print(f"[ok] {path.name}: {desc} v{__version__}")


def main() -> int:
    build = ROOT / "build"
    write_version_file(build / "version_info.txt", APP_NAME, APP_NAME, f"{APP_NAME}.exe")
    write_version_file(build / "version_info_setup.txt", f"{APP_NAME}安装包",
                       f"{APP_NAME}安装包", f"{APP_NAME}安装包.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
