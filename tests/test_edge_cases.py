import pytest
from transformer import normalize_list_of_values, normalize_list_of_dicts, validate_structure


def test_empty_inputs(sample_games):
    errors = []
    empty = []
    df_values = normalize_list_of_values(empty, field="genres", out_col="genre_id", errors=errors)
    df_dicts = normalize_list_of_dicts(empty, field="involved_companies",
                                       rename_map={"company_id": "company_id"}, errors=errors)
    assert df_values.empty
    assert df_dicts.empty


def test_validate_structure_raise_on_malformed():
    with pytest.raises(ValueError):
        validate_structure({"not": "a list"}, source_path="dummy.json")
    with pytest.raises(ValueError):
        validate_structure([1, 2, "str"], source_path="dummy.json")