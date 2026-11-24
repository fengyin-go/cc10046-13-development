"""业务路由汇总：专用链路先注册，通用资源路由最后兜底。"""
from __future__ import annotations

from app.routers import resource
from app.routers import chains
from app.routers import sample_lab

# sample_lab 中包含 /api/extraction_template/field-diffs 等模块别名，
# 必须位于 resource 的 /api/{module}/{entry_id} 之前，避免被动态路由匹配。
ROUTERS = [sample_lab, chains, resource]
