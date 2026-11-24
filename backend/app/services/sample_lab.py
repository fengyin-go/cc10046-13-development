"""模板样本对照与字段校对领域服务。

这里刻意保存不可变的样本版本和对照记录：来源网页后续被更正时，旧对照、
旧证据和按旧版本提交的校对回执仍然可以原样查询。
"""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.compute import content_hash
from app.services.field_mapper import FieldMapperService
from app.store import store


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _digest(raw: str) -> str:
    return content_hash(raw, "sha256")


INITIAL_RAW = """
<article class="product-sample" data-sample="WEB-PRODUCT-001">
  <h1>示例商品：纯棉圆领 T 恤</h1>
  <div class="attrs">
    <span class="attr spec" data-field="规格">规格：S</span>
    <span class="attr color" data-field="颜色">颜色：蓝色</span>
  </div>
</article>
""".strip()


class SampleLabError(ValueError):
    """可直接展示给调用方的业务错误。"""


class SampleLabService:
    """维护网页样本版本、模板差异、选择状态和字段校对回执。"""

    SAMPLE_ID = "WEB-PRODUCT-001"
    OLD_TEMPLATE_ID = "TPL-OLD-SPEC"
    NEW_TEMPLATE_ID = "TPL-NEW-COLOR"

    def __init__(self) -> None:
        self.mapper = FieldMapperService()
        self._ensure_resource_rows()
        self.reset_state()

    def _ensure_resource_rows(self) -> None:
        """把场景模板和映射方案登记到通用资源表，使列表页也能找到同一对象。"""
        template_rows = store.rows("extraction_template")
        template_seed = [
            {
                "模板标识": f"{self.OLD_TEMPLATE_ID}｜旧模板（仅规格）",
                "适用站点": "samples.example.invalid/products/WEB-PRODUCT-001",
                "列表选择器": ".product-sample .attrs",
                "分页参数": "page=1",
                "详情链接": "/products/WEB-PRODUCT-001",
                "去重字段": "规格",
                "增量字段": "无",
                "输出格式": "JSON",
                "status": "已发布",
            },
            {
                "模板标识": f"{self.NEW_TEMPLATE_ID}｜新模板（规格 + 颜色）",
                "适用站点": "samples.example.invalid/products/WEB-PRODUCT-001",
                "列表选择器": ".product-sample .attrs",
                "分页参数": "page=1",
                "详情链接": "/products/WEB-PRODUCT-001",
                "去重字段": "规格,颜色",
                "增量字段": "颜色",
                "输出格式": "JSON",
                "status": "已发布",
            },
        ]
        for seed in template_seed:
            if not any(row.get("模板标识") == seed["模板标识"] for row in template_rows):
                entry_id = max((int(row.get("id", 0)) for row in template_rows), default=0) + 1
                template_rows.append({
                    "id": entry_id,
                    "pending": False,
                    "abnormal": False,
                    **seed,
                })

        mapper_rows = store.rows("field_mapper")
        mapper_identifier = "FM-WEB-001｜规格颜色标准映射"
        if not any(row.get("方案标识") == mapper_identifier for row in mapper_rows):
            entry_id = max((int(row.get("id", 0)) for row in mapper_rows), default=0) + 1
            mapper_rows.append({
                "id": entry_id,
                "status": "草稿",
                "pending": True,
                "abnormal": False,
                "方案标识": mapper_identifier,
                "来源字段": "规格、颜色",
                "目标字段": "spec、color",
                "转换函数": "原样映射",
                "默认取值": "颜色缺省时留空",
                "映射版本": "FM-v1",
                "适用站点": "samples.example.invalid",
                "依赖字段": "规格,颜色",
            })

    def reset_state(self) -> None:
        blue_hash = _digest(INITIAL_RAW)
        self.templates: dict[str, dict[str, Any]] = {
            self.OLD_TEMPLATE_ID: {
                "template_id": self.OLD_TEMPLATE_ID,
                "id": self.OLD_TEMPLATE_ID,
                "name": "旧模板（仅规格）",
                "template_name": "旧模板（仅规格）",
                "template_version": "v1",
                "fields": ["规格"],
                "selectors": {"规格": ".spec"},
                "status": "已发布",
            },
            self.NEW_TEMPLATE_ID: {
                "template_id": self.NEW_TEMPLATE_ID,
                "id": self.NEW_TEMPLATE_ID,
                "name": "新模板（规格 + 颜色）",
                "template_name": "新模板（规格 + 颜色）",
                "template_version": "v2",
                "fields": ["规格", "颜色"],
                "selectors": {"规格": ".spec", "颜色": ".color"},
                "status": "已发布",
            },
        }
        self.samples: dict[str, dict[str, Any]] = {
            self.SAMPLE_ID: {
                "sample_id": self.SAMPLE_ID,
                "id": self.SAMPLE_ID,
                "name": "商品详情页原始样本",
                "url": "https://samples.example.invalid/products/WEB-PRODUCT-001",
                "current_raw": INITIAL_RAW,
                "current_values": {"规格": "S", "颜色": "蓝色"},
                "source_corrected": False,
                "correction_count": 0,
                "latest_version_id": "SV-001",
                "confirmed_version_id": "SV-001",
                "versions": [
                    {
                        "version_id": "SV-001",
                        "version": 1,
                        "version_label": "SV-001 · 已核对旧样本（蓝色）",
                        "status": "已核对",
                        "confirmed": True,
                        "evidence": True,
                        "captured_at": "2026-11-24T09:30:00+08:00",
                        "confirmed_at": "2026-11-24T09:31:00+08:00",
                        "raw": INITIAL_RAW,
                        "raw_hash": blue_hash,
                        "values": {"规格": "S", "颜色": "蓝色"},
                    }
                ],
                "corrections": [],
            }
        }
        self.comparisons: list[dict[str, Any]] = []
        self.selection: dict[str, Any] | None = None
        self.trials: list[dict[str, Any]] = []
        self.proofreads: list[dict[str, Any]] = []
        self._diff_seq = 0
        self._trial_seq = 0
        self._proofread_seq = 0
        # 预置一份蓝色旧证据，使用户再次进入采样对照时立刻能查到。
        self.compare_templates(
            sample_id=self.SAMPLE_ID,
            old_template_id=self.OLD_TEMPLATE_ID,
            new_template_id=self.NEW_TEMPLATE_ID,
            sample_version_id="SV-001",
        )

    # ---------- 查询辅助 ----------

    def list_samples(self) -> list[dict[str, Any]]:
        return [self.sample_detail(sid) for sid in sorted(self.samples)]

    def sample_detail(self, sample_id: str) -> dict[str, Any]:
        sample = self.samples.get(sample_id)
        if sample is None:
            raise SampleLabError(f"网页样本 {sample_id} 不存在")
        data = deepcopy(sample)
        selected_version = self._find_version(sample, sample["confirmed_version_id"])
        current_hash = _digest(sample["current_raw"])
        data["current_hash"] = current_hash
        data["confirmed_version"] = deepcopy(selected_version)
        data["source_has_update"] = current_hash != selected_version["raw_hash"]
        data["source_status"] = (
            "来源已更正，当前原文尚未刷新确认"
            if data["source_has_update"]
            else "当前来源与已核对版本一致"
        )
        return data

    def list_templates(self) -> list[dict[str, Any]]:
        return deepcopy(list(self.templates.values()))

    def _find_version(self, sample: dict[str, Any], version_id: str | None) -> dict[str, Any]:
        if not version_id:
            version_id = sample["confirmed_version_id"]
        for version in sample["versions"]:
            if version["version_id"] == version_id or str(version["version"]) == str(version_id):
                return version
        raise SampleLabError(f"样本版本 {version_id} 不存在")

    @staticmethod
    def _extract_values(raw: str, fields: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        for field in fields:
            pattern = re.escape(field) + r"\s*[：:]\s*([^<\n\r]+)"
            match = re.search(pattern, raw)
            values[field] = match.group(1).strip() if match else ""
        return values

    def parse_with_template(self, template_id: str, raw: str) -> dict[str, str]:
        template = self.templates.get(template_id)
        if template is None:
            raise SampleLabError(f"抽取模板 {template_id} 不存在")
        return self._extract_values(raw, template["fields"])

    # ---------- 来源更正与新版本 ----------

    def correct_source(
        self,
        sample_id: str,
        *,
        values: dict[str, Any] | None = None,
        raw: str | None = None,
        color: str | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        sample = self.samples.get(sample_id)
        if sample is None:
            raise SampleLabError(f"网页样本 {sample_id} 不存在")

        old_raw = sample["current_raw"]
        new_raw = raw
        changes: dict[str, dict[str, str]] = {}

        if new_raw is None:
            new_raw = old_raw
            update_values = dict(values or {})
            if color is not None:
                update_values["颜色"] = color
            for field, new_value in update_values.items():
                old_value = sample["current_values"].get(field, "")
                # 优先替换 data-field 节点中的可见文本，避免误改属性里的字段名。
                node_pattern = re.compile(
                    r'(data-field="' + re.escape(field) + r'"[^>]*>\s*'
                    + re.escape(field) + r'\s*[：:]\s*)[^<]+'
                )
                new_raw, replaced_count = node_pattern.subn(
                    lambda match: match.group(1) + str(new_value), new_raw, count=1
                )
                if not replaced_count:
                    text_pattern = re.compile(
                        r'(' + re.escape(field) + r'\s*[：:]\s*)[^<\n\r]+'
                    )
                    new_raw, replaced_count = text_pattern.subn(
                        lambda match: match.group(1) + str(new_value), new_raw, count=1
                    )
                if not replaced_count:
                    new_raw = new_raw.replace(
                        "</div>",
                        f'<span data-field="{field}">{field}：{new_value}</span></div>',
                        1,
                    )
                if old_value != str(new_value):
                    changes[field] = {"before": old_value, "after": str(new_value)}
        else:
            changed_values = self._extract_values(new_raw, ["规格", "颜色"])
            for key, value in changed_values.items():
                old_value = sample["current_values"].get(key, "")
                if value and old_value != value:
                    changes[key] = {"before": old_value, "after": value}

        sample["current_raw"] = new_raw
        sample["current_values"] = self._extract_values(new_raw, ["规格", "颜色"])
        sample["source_corrected"] = True
        sample["correction_count"] += 1
        sample["corrections"].append({
            "corrected_at": _now(),
            "note": note or "来源页面已更正",
            "changes": changes,
            "raw_hash": _digest(new_raw),
        })
        return self.sample_detail(sample_id)

    def refresh_and_confirm(self, sample_id: str) -> dict[str, Any]:
        sample = self.samples.get(sample_id)
        if sample is None:
            raise SampleLabError(f"网页样本 {sample_id} 不存在")
        raw = sample["current_raw"]
        raw_hash = _digest(raw)
        confirmed = self._find_version(sample, sample["confirmed_version_id"])
        if raw_hash == confirmed["raw_hash"]:
            return self.sample_detail(sample_id)

        next_number = max(int(v["version"]) for v in sample["versions"]) + 1
        values = self._extract_values(raw, ["规格", "颜色"])
        version = {
            "version_id": f"SV-{next_number:03d}",
            "version": next_number,
            "version_label": f"SV-{next_number:03d} · 刷新并确认的新原文"
            + (f"（{values.get('颜色')}）" if values.get("颜色") else ""),
            "status": "已核对",
            "confirmed": True,
            "evidence": True,
            "captured_at": _now(),
            "confirmed_at": _now(),
            "raw": raw,
            "raw_hash": raw_hash,
            "values": values,
        }
        sample["versions"].append(version)
        sample["latest_version_id"] = version["version_id"]
        sample["confirmed_version_id"] = version["version_id"]
        return self.sample_detail(sample_id)

    # ---------- 模板字段差异 ----------

    def compare_templates(
        self,
        *,
        sample_id: str,
        old_template_id: str,
        new_template_id: str,
        sample_version_id: str | None = None,
    ) -> dict[str, Any]:
        sample = self.samples.get(sample_id)
        if sample is None:
            raise SampleLabError(f"网页样本 {sample_id} 不存在")
        old_template = self.templates.get(old_template_id)
        new_template = self.templates.get(new_template_id)
        if old_template is None or new_template is None:
            raise SampleLabError("新旧模板必须都是已登记的抽取模板")

        version = self._find_version(sample, sample_version_id or sample["confirmed_version_id"])
        raw = version["raw"]
        old_values = self.parse_with_template(old_template_id, raw)
        new_values = self.parse_with_template(new_template_id, raw)

        field_order: list[str] = []
        for field in [*old_template["fields"], *new_template["fields"]]:
            if field not in field_order:
                field_order.append(field)

        rows: list[dict[str, Any]] = []
        differences: list[dict[str, Any]] = []
        for field in field_order:
            old_value = old_values.get(field, "")
            new_value = new_values.get(field, "")
            if not old_value and new_value:
                status, label = "added", "新增覆盖"
            elif old_value and not new_value:
                status, label = "removed", "新模板未覆盖"
            elif old_value != new_value:
                status, label = "changed", "内容不一致"
            elif old_value:
                status, label = "unchanged", "一致"
            else:
                status, label = "empty", "均未取到"
            row = {
                "field": field,
                "field_name": field,
                "old_value": old_value,
                "new_value": new_value,
                "old_template_value": old_value,
                "new_template_value": new_value,
                "status": status,
                "change_type": label,
                "different": status in {"added", "removed", "changed"},
            }
            rows.append(row)
            if row["different"]:
                differences.append(deepcopy(row))

        self._diff_seq += 1
        diff_id = f"DIFF-{self._diff_seq:04d}"
        result = {
            "id": diff_id,
            "diff_id": diff_id,
            "sample_id": sample_id,
            "sample_name": sample["name"],
            "sample_version_id": version["version_id"],
            "input_version": version["version_id"],
            "input_version_number": version["version"],
            "input_version_label": version["version_label"],
            "aligned_to_same_raw": True,
            "alignment": {
                "same_sample": True,
                "same_raw_version": True,
                "sample_id": sample_id,
                "sample_version_id": version["version_id"],
                "raw_hash": version["raw_hash"],
                "message": "新旧模板已对齐同一份网页原文，可比较实际覆盖差异",
            },
            "raw": raw,
            "raw_hash": version["raw_hash"],
            "old_template": deepcopy(old_template),
            "new_template": deepcopy(new_template),
            "old_values": old_values,
            "new_values": new_values,
            "old_parse_result": old_values,
            "new_parse_result": new_values,
            "fields": rows,
            "field_diffs": rows,
            "items": rows,
            "differences": differences,
            "difference_items": differences,
            "difference_count": len(differences),
            "coverage": {
                "old_fields": old_template["fields"],
                "new_fields": new_template["fields"],
                "added_fields": [r["field"] for r in differences if r["status"] == "added"],
                "removed_fields": [r["field"] for r in differences if r["status"] == "removed"],
                "changed_fields": [r["field"] for r in differences if r["status"] == "changed"],
            },
            "created_at": _now(),
            "immutable": True,
        }
        self.comparisons.append(result)
        return deepcopy(result)

    def list_comparisons(self) -> list[dict[str, Any]]:
        # 列表不返回大段 raw，避免噪声；详情仍完整保留。
        return [{k: v for k, v in item.items() if k != "raw"} for item in reversed(self.comparisons)]

    def get_comparison(self, diff_id: str) -> dict[str, Any]:
        for item in self.comparisons:
            if item["diff_id"] == diff_id or str(item.get("id")) == str(diff_id):
                return deepcopy(item)
        raise SampleLabError(f"模板对照 {diff_id} 不存在")

    def select_for_mapping(self, diff_id: str) -> dict[str, Any]:
        diff = self.get_comparison(diff_id)
        self.selection = {
            "confirmed": True,
            "selected_at": _now(),
            "comparison_id": diff["diff_id"],
            "diff_id": diff["diff_id"],
            "sample_id": diff["sample_id"],
            "sample_version_id": diff["sample_version_id"],
            "input_version": diff["sample_version_id"],
            "raw_hash": diff["raw_hash"],
        }
        return self.field_context()

    # ---------- 字段映射上下文、试跑、校对 ----------

    @staticmethod
    def default_mapping_rules() -> list[dict[str, str]]:
        return [
            {"source_field": "规格", "source": "规格", "target_field": "spec", "target": "spec", "transform": "", "default": ""},
            {"source_field": "颜色", "source": "颜色", "target_field": "color", "target": "color", "transform": "", "default": ""},
        ]

    def field_context(self, mapping_id: Any | None = None) -> dict[str, Any]:
        sample = self.sample_detail(self.SAMPLE_ID)
        selected = deepcopy(self.selection) if self.selection else None
        selected_diff = None
        if selected:
            try:
                selected_diff = self.get_comparison(selected["comparison_id"])
            except SampleLabError:
                selected_diff = None
        return {
            "selection_confirmed": selected is not None,
            "selection": selected,
            "selected_comparison": selected_diff,
            "sample": sample,
            "versions": deepcopy(sample["versions"]),
            "mapping_id": mapping_id or "FM-WEB-001",
            "mapping_entry_id": 1,
            "mapping_rules": self.default_mapping_rules(),
            "source_has_update": sample["source_has_update"],
            "source_status": sample["source_status"],
            "proofreads": list(reversed(self.proofreads)),
        }

    def _resolve_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        sample_id = str(
            payload.get("sample_id")
            or payload.get("sampleId")
            or payload.get("selected_sample_id")
            or self.SAMPLE_ID
        )
        sample = self.samples.get(sample_id)
        if sample is None:
            raise SampleLabError(f"网页样本 {sample_id} 不存在")

        diff_id = (
            payload.get("comparison_id")
            or payload.get("diff_id")
            or payload.get("diffId")
            or payload.get("template_diff_id")
        )
        diff: dict[str, Any] | None = None
        if diff_id:
            diff = self.get_comparison(str(diff_id))
            sample_id = diff["sample_id"]
            sample = self.samples[sample_id]

        selection = self.selection or {}
        version_id = (
            payload.get("sample_version_id")
            or payload.get("sampleVersionId")
            or payload.get("input_version")
            or payload.get("inputVersion")
            or payload.get("version")
            or payload.get("selected_sample_version")
            or (diff or {}).get("sample_version_id")
            or selection.get("sample_version_id")
        )
        mode = str(payload.get("input_mode") or payload.get("mode") or "").strip()
        if not mode and (payload.get("refresh") is True or payload.get("use_latest") is True):
            mode = "refresh_confirm"

        if mode in {"refresh", "latest", "current", "new", "green", "refresh_confirm", "refresh_and_confirm"}:
            sample_detail = self.refresh_and_confirm(sample_id)
            version_id = sample_detail["confirmed_version_id"]
            mode = "refresh_confirm"
            mode_label = "已刷新并确认新原文"
        else:
            mode = "checked_snapshot"
            mode_label = "使用已核对的旧样本/固定证据版本"
            if not version_id:
                version_id = sample["confirmed_version_id"]

        version = self._find_version(sample, str(version_id))
        expected_hash = (
            payload.get("input_hash")
            or payload.get("raw_hash")
            or payload.get("hash")
            or payload.get("inputHash")
        )
        hash_verified = expected_hash is None or str(expected_hash) == version["raw_hash"]
        if not hash_verified:
            raise SampleLabError(
                f"本次输入哈希不一致：请求 {expected_hash}，服务端样本版本 {version['raw_hash']}"
            )

        raw = version["raw"]
        old_values = self.parse_with_template(self.OLD_TEMPLATE_ID, raw)
        new_values = self.parse_with_template(self.NEW_TEMPLATE_ID, raw)
        input_info = {
            "mode": mode,
            "input_mode": mode,
            "mode_label": mode_label,
            "sample_id": sample_id,
            "sample_name": sample["name"],
            "sample_version_id": version["version_id"],
            "input_version": version["version_id"],
            "input_version_number": version["version"],
            "input_version_label": version["version_label"],
            "captured_at": version["captured_at"],
            "confirmed_at": version.get("confirmed_at"),
            "raw_hash": version["raw_hash"],
            "input_hash": version["raw_hash"],
            "input_hash_verified": True,
            "input_verified": True,
            "source_values": deepcopy(version["values"]),
            "raw": raw,
            "old_template_values": old_values,
            "new_template_values": new_values,
        }
        return input_info

    def _normalize_rules(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rules = (
            payload.get("mapping_rules")
            or payload.get("rules")
            or payload.get("mappings")
            or self.default_mapping_rules()
        )
        normalized: list[dict[str, Any]] = []
        for rule in rules:
            normalized.append({
                "source": rule.get("source", rule.get("source_field", "")),
                "target": rule.get("target", rule.get("target_field", "")),
                "default": rule.get("default", rule.get("default_value", "")),
                "transform": rule.get("transform", rule.get("transform_function", "")),
            })
        return normalized

    def _mapping_details(
        self,
        rules: list[dict[str, Any]],
        source_values: dict[str, Any],
        mapped_values: dict[str, Any],
    ) -> list[dict[str, Any]]:
        details: list[dict[str, Any]] = []
        for rule in rules:
            source_field = str(rule.get("source", ""))
            target_field = str(rule.get("target", ""))
            details.append({
                "source_field": source_field,
                "target_field": target_field,
                "source_value": source_values.get(source_field, rule.get("default", "")),
                "mapped_value": mapped_values.get(target_field),
                "transform": rule.get("transform", ""),
            })
        return details

    def trial_mapping(self, payload: dict[str, Any]) -> dict[str, Any]:
        input_info = self._resolve_input(payload)
        rules = self._normalize_rules(payload)
        mapped = self.mapper.domain_map_fields(input_info["source_values"], rules)
        self._trial_seq += 1
        trial_id = f"TRIAL-{self._trial_seq:04d}"
        result = {
            "ok": True,
            "trial_id": trial_id,
            "tried_at": _now(),
            "mapping_id": payload.get("mapping_id") or "FM-WEB-001",
            "mapping_entry_id": payload.get("mapping_entry_id", 1),
            "mapping_rules": rules,
            "mapping_details": self._mapping_details(rules, input_info["source_values"], mapped),
            "mapped_values": mapped,
            "actual_mapping_values": deepcopy(mapped),
            "actual_input": deepcopy(input_info["source_values"]),
            **{k: v for k, v in input_info.items() if k != "raw"},
        }
        self.trials.append(deepcopy(result))
        return result

    def submit_proofread(self, payload: dict[str, Any]) -> dict[str, Any]:
        trial_id = payload.get("trial_id")
        trial: dict[str, Any] | None = None
        if trial_id:
            trial = next((item for item in reversed(self.trials) if item["trial_id"] == trial_id), None)
            if trial is None:
                raise SampleLabError(f"试跑记录 {trial_id} 不存在")
            # 以 trial 中的版本为线索，但服务端重新读取不可变版本并重算映射。
            payload = {
                **payload,
                "input_mode": "trial_version",
                "sample_id": trial["sample_id"],
                "sample_version_id": trial["sample_version_id"],
                "input_hash": trial["input_hash"],
                "mapping_rules": trial["mapping_rules"],
            }

        input_info = self._resolve_input(payload)
        if trial is not None:
            input_info["input_mode"] = trial.get("input_mode", input_info["input_mode"])
            input_info["mode_label"] = trial.get("mode_label", input_info["mode_label"])
        rules = self._normalize_rules(payload)
        mapped = self.mapper.domain_map_fields(input_info["source_values"], rules)

        # 如果调用方带回了试跑映射值，核验其是否与服务端按实际版本计算的一致。
        client_mapped = payload.get("mapped_values") or payload.get("actual_mapping_values")
        mapping_verified = client_mapped is None or client_mapped == mapped

        self._proofread_seq += 1
        record_id = f"PR-{self._proofread_seq:04d}"
        receipt_id = f"RCPT-{record_id}"
        submitted_at = _now()
        receipt = {
            "receipt_id": receipt_id,
            "record_id": record_id,
            "ok": True,
            "verified": mapping_verified and input_info["input_hash_verified"],
            "input_verified": input_info["input_verified"],
            "input_hash_verified": input_info["input_hash_verified"],
            "mapping_values_verified": mapping_verified,
            "verification": (
                "服务端已读取实际样本版本原文，重算输入摘要与映射值；"
                "回执中的输入版本、原文值和映射值互相对得上。"
            ),
            "submitted_at": submitted_at,
            "mapping_id": payload.get("mapping_id") or (trial or {}).get("mapping_id") or "FM-WEB-001",
            "mapping_entry_id": payload.get("mapping_entry_id", (trial or {}).get("mapping_entry_id", 1)),
            "sample_id": input_info["sample_id"],
            "sample_version_id": input_info["sample_version_id"],
            "input_version": input_info["input_version"],
            "input_version_number": input_info["input_version_number"],
            "input_version_label": input_info["input_version_label"],
            "input_mode": input_info["input_mode"],
            "mode_label": input_info["mode_label"],
            "input_hash": input_info["input_hash"],
            "source_values": input_info["source_values"],
            "actual_input": input_info["source_values"],
            "old_template_values": input_info["old_template_values"],
            "new_template_values": input_info["new_template_values"],
            "mapped_values": mapped,
            "actual_mapping_values": deepcopy(mapped),
            "mapping_details": self._mapping_details(rules, input_info["source_values"], mapped),
            "trial_id": trial_id,
        }
        record = {**deepcopy(receipt), "status": "已提交", "remark": payload.get("remark", "")}
        self.proofreads.append(record)
        self._write_audit(record)
        return {
            "ok": True,
            "message": "字段校对已提交，服务端回执已核验本次输入",
            **deepcopy(receipt),
            "receipt": deepcopy(receipt),
            "server_receipt": deepcopy(receipt),
            "verification_receipt": deepcopy(receipt),
            "record": deepcopy(record),
        }

    def list_proofreads(self) -> list[dict[str, Any]]:
        return list(reversed(self.proofreads))

    def get_proofread(self, record_id: str) -> dict[str, Any]:
        for item in self.proofreads:
            if item["record_id"] == record_id or item["receipt_id"] == record_id:
                return deepcopy(item)
        raise SampleLabError(f"字段校对记录 {record_id} 不存在")

    def _write_audit(self, record: dict[str, Any]) -> None:
        rows = store.rows("crawl_audit")
        next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        source_text = "，".join(f"{k}={v}" for k, v in record["source_values"].items())
        mapped_text = "，".join(f"{k}={v}" for k, v in record["mapped_values"].items())
        rows.append({
            "id": next_id,
            "status": "已记录",
            "pending": False,
            "abnormal": False,
            "记录标识": record["record_id"],
            "操作类型": "字段校对",
            "操作对象": f"字段映射/{record['mapping_id']}",
            "操作时间": record["submitted_at"],
            "操作人": "数据工程组",
            "变更前值": f"{record['input_version']} 原文：{source_text}",
            "变更后值": f"映射值：{mapped_text}",
            "审计摘要": (
                f"按实际样本版本 {record['input_version']} 提交；"
                f"输入摘要 {record['input_hash']}；回执 {record['receipt_id']}"
            ),
        })


sample_lab = SampleLabService()
