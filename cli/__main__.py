"""CLI 入口包入口，支持 python -m cli 直接执行"""

from .main import entry_point

if __name__ == "__main__":
    raise SystemExit(entry_point())
