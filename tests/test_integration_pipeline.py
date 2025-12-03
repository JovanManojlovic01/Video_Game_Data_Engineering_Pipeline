import json
import yaml
from pathlib import Path
from transformer import normalize_exported_file


def test_integration_pipeline(tmp_path: Path, sample_games, sample_config):
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(sample_games), encoding="utf-8")

    output_dir = tmp_path / "out"
    normalize_exported_file(str(raw_path), output_dir=output_dir, batch_size=2,
                            config_path=sample_config, output_format="json")

    assert (output_dir / "games.json").exists()
    assert (output_dir / "genres.json").exists()
    assert (output_dir / "platforms.json").exists()

    assert any(p.name.startswith("transformation_report_") for p in output_dir.iterdir())
    assert any(p.name.startswith("schema_") and p.suffix == ".yaml" for p in output_dir.iterdir())