from app.clients.soil import parse_table

SAMPLE = {"Table": [
    ["cokey", "compname", "comppct_r", "ph1to1h2o_r"],
    ["25001", "Floridana", "85", "5.8"],
    ["25002", "Placid", "10", None],
]}


def test_parse_table_uses_first_row_as_columns() -> None:
    assert parse_table(SAMPLE) == [
        {"cokey": "25001", "compname": "Floridana", "comppct_r": "85", "ph1to1h2o_r": "5.8"},
        {"cokey": "25002", "compname": "Placid", "comppct_r": "10", "ph1to1h2o_r": None},
    ]


def test_parse_table_missing_or_empty() -> None:
    assert parse_table({}) == []
    assert parse_table({"Table": []}) == []
    assert parse_table({"Table": [["mukey"]]}) == []
