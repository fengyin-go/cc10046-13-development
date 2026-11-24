"""模板样本差异与字段校对接口。

除了一组语义稳定的 /api/template-lab 接口外，也提供按前端业务模块命名的
别名，方便从抽取模板和字段映射两个入口调用同一套不可变证据。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.services.sample_lab import SampleLabError, sample_lab

router = APIRouter(prefix="/api", tags=["模板样本对照与字段校对"])


def _bad_request(exc: SampleLabError) -> HTTPException:
    message = str(exc)
    status = 404 if "不存在" in message else 400
    return HTTPException(status_code=status, detail=message)


@router.post("/template-lab/reset")
def reset_lab() -> dict[str, Any]:
    sample_lab.reset_state()
    return {"ok": True, "message": "模板样本实验数据已重置", "state": lab_state()}


@router.get("/template-lab/state")
def lab_state() -> dict[str, Any]:
    context = sample_lab.field_context()
    return {
        "samples": sample_lab.list_samples(),
        "templates": sample_lab.list_templates(),
        "comparisons": sample_lab.list_comparisons(),
        "selection": sample_lab.selection,
        "proofreads": sample_lab.list_proofreads(),
        "context": context,
        "defaults": {
            "sample_id": sample_lab.SAMPLE_ID,
            "old_template_id": sample_lab.OLD_TEMPLATE_ID,
            "new_template_id": sample_lab.NEW_TEMPLATE_ID,
        },
    }


@router.get("/template-lab/samples")
@router.get("/web-samples")
def list_samples() -> list[dict[str, Any]]:
    return sample_lab.list_samples()


@router.get("/template-lab/samples/{sample_id}")
@router.get("/web-samples/{sample_id}")
def get_sample(sample_id: str) -> dict[str, Any]:
    try:
        return sample_lab.sample_detail(sample_id)
    except SampleLabError as exc:
        raise _bad_request(exc) from exc


@router.post("/template-lab/samples/{sample_id}/correct-source")
@router.post("/web-samples/{sample_id}/correct")
def correct_source(sample_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    try:
        return {
            "ok": True,
            "message": "来源原文已更正；旧样本版本和旧对照证据保持不变",
            "sample": sample_lab.correct_source(
                sample_id,
                values=payload.get("values"),
                raw=payload.get("raw"),
                color=payload.get("color"),
                note=str(payload.get("note", "")),
            ),
        }
    except SampleLabError as exc:
        raise _bad_request(exc) from exc


@router.post("/template-lab/samples/{sample_id}/refresh-confirm")
@router.post("/web-samples/{sample_id}/refresh-confirm")
def refresh_confirm(sample_id: str) -> dict[str, Any]:
    try:
        sample = sample_lab.refresh_and_confirm(sample_id)
        return {"ok": True, "message": "已刷新并确认新的网页原文版本", "sample": sample}
    except SampleLabError as exc:
        raise _bad_request(exc) from exc


@router.get("/template-lab/templates")
def list_lab_templates() -> list[dict[str, Any]]:
    return sample_lab.list_templates()


@router.get("/template-lab/diffs")
@router.get("/template-lab/comparisons")
@router.get("/template-field-diffs")
@router.get("/extraction_template/field-diffs")
@router.get("/extraction_template/comparisons")
def list_diffs() -> list[dict[str, Any]]:
    return sample_lab.list_comparisons()


@router.post("/template-lab/diffs")
@router.post("/template-lab/compare")
@router.post("/template-field-diffs")
@router.post("/template-diffs/compare")
@router.post("/extraction_template/field-diffs")
@router.post("/extraction_template/compare")
@router.post("/extraction_template/compare-fields")
@router.post("/extraction_template/sample-diff")
def compare_templates(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    try:
        return sample_lab.compare_templates(
            sample_id=str(payload.get("sample_id") or payload.get("sampleId") or sample_lab.SAMPLE_ID),
            old_template_id=str(
                payload.get("old_template_id")
                or payload.get("oldTemplateId")
                or payload.get("old_template")
                or sample_lab.OLD_TEMPLATE_ID
            ),
            new_template_id=str(
                payload.get("new_template_id")
                or payload.get("newTemplateId")
                or payload.get("new_template")
                or sample_lab.NEW_TEMPLATE_ID
            ),
            sample_version_id=payload.get("sample_version_id") or payload.get("sampleVersionId"),
        )
    except SampleLabError as exc:
        raise _bad_request(exc) from exc


@router.get("/template-lab/diffs/{diff_id}")
@router.get("/template-field-diffs/{diff_id}")
@router.get("/extraction_template/field-diffs/{diff_id}")
def get_diff(diff_id: str) -> dict[str, Any]:
    try:
        return sample_lab.get_comparison(diff_id)
    except SampleLabError as exc:
        raise _bad_request(exc) from exc


@router.post("/template-lab/diffs/{diff_id}/select")
@router.post("/template-field-diffs/{diff_id}/select")
@router.post("/extraction_template/field-diffs/{diff_id}/select")
def select_diff(diff_id: str) -> dict[str, Any]:
    try:
        context = sample_lab.select_for_mapping(diff_id)
        return {"ok": True, "message": "已确认该网页样本，字段映射将读取此具体版本", "context": context}
    except SampleLabError as exc:
        raise _bad_request(exc) from exc


@router.get("/template-lab/field-context")
@router.get("/field-mapper/proofread-context")
@router.get("/field_mapper/proofread-context")
@router.get("/field-mapper/context")
@router.get("/field_mapper/context")
@router.get("/field-mapper/proofreading-context")
@router.get("/field_mapper/proofreading-context")
def field_context(mapping_id: str | None = None) -> dict[str, Any]:
    return sample_lab.field_context(mapping_id)


@router.post("/template-lab/mapping/trial")
@router.post("/field-mapper/trial")
@router.post("/field_mapper/trial")
@router.post("/field-mapper/proofread-trial")
@router.post("/field_mapper/proofread-trial")
@router.post("/field-mapper/proofreading/trial")
@router.post("/field_mapper/proofreading/trial")
def trial_mapping(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    try:
        return sample_lab.trial_mapping(payload)
    except SampleLabError as exc:
        raise _bad_request(exc) from exc


@router.post("/template-lab/proofreads")
@router.post("/field-mapper/proofread")
@router.post("/field_mapper/proofread")
@router.post("/field-mapper/proofreads")
@router.post("/field_mapper/proofreads")
@router.post("/field_mapper/submit-proofread")
@router.post("/field-mapper/proofreading")
@router.post("/field_mapper/proofreading")
@router.post("/field-mapper/proofreading/submit")
@router.post("/field_mapper/proofreading/submit")
def submit_proofread(payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    try:
        return sample_lab.submit_proofread(payload)
    except SampleLabError as exc:
        raise _bad_request(exc) from exc


@router.get("/template-lab/proofreads")
@router.get("/field-mapper/proofreads")
@router.get("/field_mapper/proofreads")
@router.get("/field-mapper/proofreading/records")
@router.get("/field_mapper/proofreading/records")
def list_proofreads() -> list[dict[str, Any]]:
    return sample_lab.list_proofreads()


@router.get("/template-lab/proofreads/{record_id}")
def get_proofread(record_id: str) -> dict[str, Any]:
    try:
        return sample_lab.get_proofread(record_id)
    except SampleLabError as exc:
        raise _bad_request(exc) from exc
