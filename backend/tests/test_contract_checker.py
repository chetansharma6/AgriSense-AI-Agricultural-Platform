"""The manual judge contract checker must accept the current API contract."""

import pytest

from app import config, service
from scripts import check_contract


@pytest.mark.parametrize("farm", list(config.DEMO_FARMS))
def test_manual_checker_accepts_recommendation_and_crop_detail(monkeypatch, farm) -> None:
    monkeypatch.setattr(config, "DEMO_MODE", True)
    lat, lon = config.DEMO_FARMS[farm]
    recommendation = service.recommend(lat, lon)
    detail = service.crop_detail(recommendation["crops"][0]["id"], lat, lon)
    assert check_contract.shape_errors(recommendation, check_contract.RECOMMEND, "recommend") == []
    assert check_contract.shape_errors(detail, check_contract.DETAIL, "detail") == []
    report = check_contract.Report()
    check_contract.check_common(report, farm, recommendation)
    for crop in recommendation["crops"]:
        check_contract.check_crop(report, farm, crop, check_contract.CROP)
    check_contract.check_crop(report, farm, detail, check_contract.DETAIL)
    assert all(ok for _, _, ok, _ in report.rows), [row for row in report.rows if not row[2]]
