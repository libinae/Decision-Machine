"""多人格决策机日志系统

提供统一的日志配置和工具函数
"""

import logging
import sys
from pathlib import Path

# 日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "decision_machine",
    level: int = logging.INFO,
    log_file: Path | str | None = None,
    console_output: bool = False,
) -> logging.Logger:
    """配置并返回日志器

    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件路径（可选）
        console_output: 是否输出到控制台（默认 False，不影响 UI）

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 文件输出
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # 控制台输出（可选，默认不开启以免干扰 UI）
    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# 全局日志器实例
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """获取全局日志器实例"""
    global _logger
    if _logger is None:
        _logger = setup_logger(console_output=False)
    return _logger


def log_info(message: str) -> None:
    """记录 INFO 级别日志"""
    get_logger().info(message)


def log_warning(message: str) -> None:
    """记录 WARNING 级别日志"""
    get_logger().warning(message)


def log_error(message: str, exc_info: bool = False) -> None:
    """记录 ERROR 级别日志

    Args:
        message: 日志消息
        exc_info: 是否包含异常信息
    """
    get_logger().error(message, exc_info=exc_info)


def log_debug(message: str) -> None:
    """记录 DEBUG 级别日志"""
    get_logger().debug(message)


__all__ = [
    "setup_logger",
    "get_logger",
    "log_info",
    "log_warning",
    "log_error",
    "log_debug",
]
