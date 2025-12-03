import pytest
import yaml
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def sample_games():
    return [
        {"id": 1, "name": "Alpha", "rating": 85, "aggregated_rating": 82, "first_release_date": 1609459200,
         "genres": [10, 20], "platforms": [100], "involved_companies": [{"company_id": 500}]},
        {"id": 2, "name": "Beta", "rating": None, "aggregated_rating": None, "first_release_date": None,
         "genres": [], "platforms": [], "involved_companies": []},
    ]


@pytest.fixture
def sample_config(tmp_path: Path):
    config = {
        "tables": {
            "games": {"fields": ["id", "name", "rating", "aggregated_rating", "first_release_date", "release_year",
                                 "has_rating", "has_aggregated_rating", "genre_count", "platform_count"]},
            "genres": {"source_field": "genres", "output_column": "genre_id"},
            "platforms": {"source_field": "platforms", "output_column": "platform_id"},
            "involved_companies": {"source_field": "involved_companies", "output_column": "company_id"},
        },
        "defaults": {"rating": 0.0, "aggregated_rating": 0.0, "genres": [], "platforms": [], "involved_companies": []},
        "deduplication": {"strategy": "keep_first"},
    }

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    return config_path
