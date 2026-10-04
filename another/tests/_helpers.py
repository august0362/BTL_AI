"""Tiện ích dùng chung cho test."""

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def require_module(name: str) -> ModuleType:
    """Import module `name`; bỏ qua (skip) cả file test nếu module CHƯA ĐƯỢC TẠO.

    Chỉ skip khi file module không tồn tại. Nếu module có nhưng import lỗi
    (thiếu thư viện, lỗi cú pháp...), lỗi vẫn được báo bình thường để không bị che giấu.
    """
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        pytest.skip(f"{name} chưa được triển khai", allow_module_level=True)
    return importlib.import_module(name)
