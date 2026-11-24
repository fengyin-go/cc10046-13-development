"""通用接口契约；模块字段由领域服务持有，不再为每个模块复制一份模型类。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    action: str
    remark: str | None = None
    # 字段映射校对入口可能随标准动作一起提交的样本版本核验信息。
    input_mode: str | None = None
    trial_id: str | None = None
    sample_id: str | None = None
    comparison_id: str | None = None
    diff_id: str | None = None
    sample_version_id: str | None = None
    input_version: str | None = None
    input_hash: str | None = None
    mapped_values: dict[str, Any] | None = None
    mapping_rules: list[dict[str, Any]] | None = None
