"""模板样本差异、版本快照与字段校对回执测试。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.sample_lab import SampleLabError, SampleLabService


def test_same_raw_version_produces_field_coverage_diff():
    svc = SampleLabService()
    diff = svc.compare_templates(
        sample_id=svc.SAMPLE_ID,
        old_template_id=svc.OLD_TEMPLATE_ID,
        new_template_id=svc.NEW_TEMPLATE_ID,
        sample_version_id="SV-001",
    )

    assert diff["aligned_to_same_raw"] is True
    assert diff["old_values"] == {"规格": "S"}
    assert diff["new_values"] == {"规格": "S", "颜色": "蓝色"}
    color_row = next(row for row in diff["fields"] if row["field"] == "颜色")
    assert color_row["old_value"] == ""
    assert color_row["new_value"] == "蓝色"
    assert color_row["status"] == "added"


def test_old_blue_evidence_and_receipt_survive_green_correction():
    svc = SampleLabService()
    diff_id = svc.comparisons[0]["diff_id"]
    svc.select_for_mapping(diff_id)

    svc.correct_source(svc.SAMPLE_ID, color="绿色")

    snapshot_receipt = svc.submit_proofread({"input_mode": "checked_snapshot"})
    assert snapshot_receipt["verified"] is True
    assert snapshot_receipt["input_version"] == "SV-001"
    assert snapshot_receipt["source_values"]["颜色"] == "蓝色"
    assert snapshot_receipt["mapped_values"]["color"] == "蓝色"
    assert snapshot_receipt["input_hash_verified"] is True

    refreshed_receipt = svc.submit_proofread({"input_mode": "refresh_confirm"})
    assert refreshed_receipt["input_version"] == "SV-002"
    assert refreshed_receipt["source_values"]["颜色"] == "绿色"
    assert refreshed_receipt["mapped_values"]["color"] == "绿色"

    old_diff = svc.get_comparison(diff_id)
    assert old_diff["new_values"]["颜色"] == "蓝色"
    assert "颜色：蓝色" in old_diff["raw"]
    assert "绿色" not in old_diff["raw"]


def test_receipt_rejects_stale_input_hash():
    svc = SampleLabService()
    try:
        svc.submit_proofread({
            "sample_version_id": "SV-001",
            "input_hash": "stale-hash",
        })
    except SampleLabError as exc:
        assert "哈希不一致" in str(exc)
    else:
        raise AssertionError("stale input hash must be rejected")
