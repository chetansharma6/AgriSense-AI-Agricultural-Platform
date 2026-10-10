from app.crops import load_crops

EXPECTED_IDS = {
    "peanut", "cotton", "field_corn", "soybean", "sugarcane", "tomato", "watermelon",
    "strawberry", "potato", "sweet_corn", "snap_bean", "bell_pepper", "cabbage",
}


def test_crops_table_has_all_13_crops() -> None:
    crops = load_crops()
    assert set(crops) == EXPECTED_IDS
    for crop in crops.values():
        assert crop.fl_windows
        assert crop.ph[0] < crop.ph[1]
        assert all(link.url.startswith("https://edis.ifas.ufl.edu/") for link in crop.extension_links)
        assert "general_guidance" not in crop.requirements()
