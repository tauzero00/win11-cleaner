"""Cleaner 抽象基类与 CleanItem 数据模型。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from core.scanner import dir_size

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"


@dataclass
class CleanItem:
    """一个可清理项。"""

    path: str
    cleaner_id: str
    label: str
    size: int = 0
    file_count: int = 0
    risk: str = RISK_LOW
    allowed_prefixes: tuple[str, ...] = ()
    to_recycle: bool = False
    checked: bool = True
    delete_contents_only: bool = False


class Cleaner:
    """所有清理类别的基类。子类实现 scan()。"""

    id: str = "base"
    display_name: str = "未命名"

    def __init__(self, root_overrides: dict[str, str] | None = None):
        """root_overrides：逻辑键 → 路径，测试时覆盖真实路径用。"""
        self.root_overrides = root_overrides or {}

    def p(self, key: str, env: str | None = None) -> str | None:
        """取路径：先查 root_overrides[key]，再查环境变量 env。"""
        if key in self.root_overrides:
            return self.root_overrides[key]
        if env:
            return os.environ.get(env)
        return None

    def scan(self) -> list[CleanItem]:
        raise NotImplementedError


def make_dir_item(
    path: str,
    cleaner_id: str,
    label: str,
    risk: str,
    to_recycle: bool,
    delete_contents_only: bool = False,
) -> Optional[CleanItem]:
    """把目录包装为 CleanItem；目录不存在或没有任何文件时返回 None。"""
    if not os.path.isdir(path):
        return None
    size, count = dir_size(path)
    if count == 0:
        return None
    return CleanItem(
        path=path,
        cleaner_id=cleaner_id,
        label=label,
        size=size,
        file_count=count,
        risk=risk,
        allowed_prefixes=(path,),
        to_recycle=to_recycle,
        delete_contents_only=delete_contents_only,
    )
