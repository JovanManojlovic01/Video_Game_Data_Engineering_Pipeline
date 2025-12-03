import pandas as pd
import yaml
from transformer import transform_games

def test_transform_games_types_and_fields(sample_games, sample_config):
    config = yaml.safe_load(sample_config.read_text(encoding="utf-8"))
    df = transform_games(sample_games, config)

    assert "id" in df.columns
    assert df.loc[df['id'] == 1, 'name'].iloc[0] == "Alpha"
    assert "rating" in df.columns
    assert "first_release_date" in df.columns
    assert "release_year" in df.columns
