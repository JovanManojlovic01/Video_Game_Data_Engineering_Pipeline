import pandas as pd
from transformer import normalize_list_of_values


def test_normalize_list_of_values_happy_path(sample_games):
    errors = []
    df = normalize_list_of_values(sample_games, field="genres", out_col="genre_id", errors=errors)
    assert not df.empty
    assert set(df.columns) == {"game_id", "genre_id"}
    assert df['game_id'].dropna().astype(int).tolist() == [1, 1]
    assert errors == []


def test_normalize_list_of_values_type_mismatch(sample_games):
    bad = [{"id": 3, "name": "Gamma", "genres": "action"}]
    errors = []
    df = normalize_list_of_values(bad, field="genres", out_col="genre_id", errors=errors)
    assert df.empty
    assert any(e["error_type"] == "type_mismatch" for e in errors)