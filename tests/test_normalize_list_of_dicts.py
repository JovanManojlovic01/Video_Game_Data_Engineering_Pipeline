import pandas as pd
from transformer import normalize_list_of_dicts


def test_normalize_list_of_dicts_happy_path():
    games = [{"id": 10, "involved_companies": [{"company_id": 5, "is_dev": True}, {"company_id": 6}]}]
    errors = []
    df = normalize_list_of_dicts(games, field="involved_companies",
                                 rename_map={"company_id": "company_id"}, errors=errors)
    assert not df.empty
    assert set(df.columns) >= {"game_id", "company_id"}
    assert df['company_id'].dropna().astype(int).tolist() == [5, 6]
    assert errors == []


def test_normalize_list_of_dicts_non_dict_element():
    games = [{"id": 11, "involved_companies": ["not_a_dict"]}]
    errors = []
    df = normalize_list_of_dicts(games, field="involved_companies",
                                 rename_map={"company_id": "company_id"}, errors=errors)
    assert df.empty
    assert any(e["error_type"] == "type_mismatch" for e in errors)