# python
import argparse
import json
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Union
from datetime import datetime
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class DataQualityMetrics:
    processed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0

    def log_progress(self):
        logger.info("Progress: processed: %d, skipped: %d, errors: %d",
                    self.processed_count, self.skipped_count, self.error_count)


def load_config(config_path: Union[str, Path] = "config.yaml") -> Dict:
    """
    Load configuration from a YAML file.
    :param:
        config_path: Path to the YAML configuration file.
    :return:
        A dictionary with the configuration data.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info("Configuration loaded from %s", path)
    return config


def save_error_log(errors: List[Dict], output_dir: Path) -> None:
    if not errors:
        return

    error_log_path = output_dir / f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    with error_log_path.open("w", encoding="utf-8") as f:
        json.dump(errors, f, indent=4, ensure_ascii=False)

    logger.info(" Error log saved to %s", error_log_path)


def normalize_list_of_values(games: List[Dict], field: str, out_col: str, errors: List[Dict]) -> pd.DataFrame:
    """
    Normalize a list of values from the specified field in the "games" data.
    :param: games: list of game records (dictionaries).
            field: source field containing list of values.
            out_col: specified output column name.
    :return:
        A DataFrame with game_id and the specified output column.
    """
    if errors is None:
        errors = []

    rows = []
    metrics = DataQualityMetrics()
    for g in games:
        gid = g.get("id")
        try:
            vals = g.get(field, []) or []
            if vals is None or (isinstance(vals, list) and len(vals) == 0):
                logger.warning("Game ID %s has empty or null field %s", gid, field)
            if isinstance(vals, list):
                for v in vals:
                    rows.append({"game_id": gid, out_col: v})
                    metrics.processed_count += 1
            else:
                logger.warning("Expected list for field %s in game ID %s, got %s",
                               field, gid, type(vals).__name__)
                errors.append({
                    "game_id": gid,
                    "field": field,
                    "error_type": "type_mismatch",
                    "expected_type": "list",
                    "actual_type": type(vals).__name__,
                    "value": str(g.get(field))
                })
        except Exception as e:
            logger.error("Error processing game ID %s field '%s': %s (value=%s)",
                         gid, field, e, g.get(field))
            metrics.error_count += 1
            errors.append({
                "game_id": gid,
                "field": field,
                "error_type": "exception",
                "error": str(e),
                "value": str(g.get(field))
            })
            continue
    metrics.log_progress()
    return pd.DataFrame(rows, columns=["game_id", out_col])


def normalize_list_of_dicts(games: List[Dict], field: str, rename_map: Dict[str, str],
                            errors: List[Dict]) -> pd.DataFrame:
    """
    Normalize a list of dictionaries from the specified field in the "games" data.
    :param: games: list of game records (dictionaries).
            field: source field containing list of dictionaries.
            rename_map: mapping of old field names to new column names.
    :return:
        A DataFrame with game_id and the renamed columns.
    """
    if errors is None:
        errors = []

    rows = []
    metrics = DataQualityMetrics()
    for g in games:
        gid = g.get("id")
        try:
            items = g.get(field, []) or []
            if items is None or (isinstance(items, list) and len(items) == 0):
                logger.warning("Game ID %s has empty or null field %s", gid, field)
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict):
                    rec = {"game_id": gid}
                    rec.update({new: it.get(old) for old, new in rename_map.items()})
                    rows.append(rec)
                    metrics.processed_count += 1
                else:
                    logger.warning("Expected dict in list for field %s in game ID %s, got %s",
                                   field, gid, type(it).__name__)
                    errors.append({
                        "game_id": gid,
                        "field": field,
                        "error_type": "type_mismatch",
                        "expected_type": "dict",
                        "actual_type": type(it).__name__,
                        "value": str(g.get(field))
                    })
        except Exception as e:
            logger.error("Error processing game ID %s field '%s': %s (items=%s)",
                         gid, field, e, g.get(field))
            metrics.error_count += 1
            errors.append({
                "game_id": gid,
                "field": field,
                "error_type": "exception",
                "error": str(e),
                "value": str(g.get(field))
            })
            continue
    metrics.log_progress()
    cols = ["game_id", *rename_map.values()]
    return pd.DataFrame(rows, columns=cols)


def transform_games(games: List[Dict], config: Dict) -> pd.DataFrame:
    """
    Transform the games data into a normalized DataFrame.
    :param:
        games: list of game records (dictionaries).
        config: configuration dictionary.
    :return:
        A DataFrame with selected game fields.
    """
    try:
        df = pd.json_normalize(games)
        keep = config.get("tables", {}).get("games", {}).get("fields", [])
        existing = [c for c in keep if c in df.columns]
        return df[existing] if existing else pd.DataFrame(columns=keep)
    except Exception as e:
        logger.error("Error normalizing games data: %s", e)
        return pd.DataFrame(columns=config.get("tables", {}).get("games", {}).get("fields", []))


def validate_structure(data: any, source_path: Path) -> None:
    """
    Validate the structure of the loaded data.
    :param:
        data: Loaded data to validate.
        source_path: Path to the source file for error messages.
    :return:
        None
    """
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of game records in {source_path}, got {type(data).__name__}.")

    if not data:
        logger.warning("No records found in %s.", source_path)
        return

    non_dict_items = [i for i, item in enumerate(data) if not isinstance(item, dict)]
    if non_dict_items:
        raise ValueError(f"Expected each game record to be a dictionary in {source_path}, "
                         f"but found non-dictionary items at indices: {non_dict_items}.")


def validate_required_fields(games: List[Dict], config: Dict) -> None:
    """
    Validate that required fields are present in the game records.
    :param:
        games: list of game records (dictionaries).
        config: configuration dictionary.
    :return:
        None
    """
    validation = config.get("validation", {})
    required = validation.get("required_fields", ['id', 'name'])
    recommended = validation.get("recommended_fields", [])
    min_values = validation.get("min_values", {})
    max_values = validation.get("max_values", {})
    sample_size = validation.get("sample_size", 10)
    sample = games[:min(sample_size, len(games))]

    for i, game in enumerate(sample):  # Required fields
        missing = [field for field in required if field not in game]
        if missing:
            raise ValueError(f"Game record at index {i} is missing required fields: {missing}")

    for i, game in enumerate(sample):  # Recommended fields
        missing_recommended = [field for field in recommended if field not in game]
        if missing_recommended:
            logger.warning("Record %d is missing recommended fields: %s", i, missing_recommended)

    for i, game in enumerate(sample):  # Minimum values
        for field, min_count in min_values.items():
            if field in game and game[field] is not None:
                if game[field] < min_count:
                    logger.warning("Record %d: %s=%s is below minimum %s", i, field, game[field], min_count)

    for i, game in enumerate(sample):  # Maximum values
        for field, max_count in max_values.items():
            if field in game and game[field] is not None:
                if game[field] > max_count:
                    logger.warning("Record %d: %s=%s exceeds maximum %s", i, field, game[field], max_count)


def validate_input_file(raw_json_path: Union[str, Path], config_path: Union[str, Path] = "config.yaml") -> bool:
    """
    Validate the input JSON file structure and required fields.
    :param:
        raw_json_path: Path to the raw JSON file.
    :return:
        True if validation passes, False otherwise.
    """
    config = load_config(config_path)

    src = Path(raw_json_path)
    if not src.exists():
        logger.error(f"Input file not found: {src}")
        return False

    try:
        games = load_exported_games(src)
        validate_required_fields(games, config)
        logger.info("✓ Validation passed: %s (%d records)", src, len(games))
        return True
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("✗ Validation failed: %s", e)
        return False


def load_exported_games(path: Path) -> List[Dict]:
    """
    Load exported games from a JSON file.
    :param:
        path: Path to the JSON file.
    :return:
        A list of game records (dictionaries).
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        validate_structure(data, path)
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON syntax in {path}: {e}")


def dump_normalized_table(df: pd.DataFrame, path: Path, output_config: Dict) -> None:
    """
    Dump the normalized DataFrame to a JSON file.
    :param:
        df: DataFrame to dump.
        path: Path to the output JSON file.
        output_config: Configuration for JSON output (orient, indent, force_ascii).
    :return:
        None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    orient = output_config.get("orient", "records")
    indent = output_config.get("indent", 2)
    force_ascii = output_config.get("force_ascii", False)
    df.to_json(path.as_posix(), orient=orient, indent=indent, force_ascii=force_ascii)
    logger.info("Wrote %s (rows=%d)", path, len(df))


def normalize_exported_file(raw_json_path: Union[str, Path], output_dir: Union[str, Path] = "normalized",
                            config_path: Union[str, Path] = "config.yaml") -> None:
    """
    Normalize the exported JSON file into tidy tables.
    :param:
        raw_json_path: Path to the raw JSON file.
        output_dir: Output directory for normalized tables.
        config_path: Path to the YAML configuration file.
    :return:
        None
    """
    config = load_config(config_path)
    errors = []

    src = Path(raw_json_path)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {src}")
    games = load_exported_games(src)
    if not games:
        logger.warning("No records in %s; nothing to normalize.", src)
        return

    validate_required_fields(games, config)

    table_configs = config.get("tables", {})
    tables = {}

    tables["games"] = transform_games(games, config)  # Games table

    if "genres" in table_configs:  # Genres table
        genres_cfg = table_configs["genres"]
        tables["genres"] = normalize_list_of_values(games,
                                                    genres_cfg["source_field"],
                                                    genres_cfg["output_column"],
                                                    errors)

    if "platforms" in table_configs:  # Platforms table
        platforms_cfg = table_configs["platforms"]
        tables["platforms"] = normalize_list_of_values(games,
                                                       platforms_cfg["source_field"],
                                                       platforms_cfg["output_column"],
                                                       errors)

    out_dir = Path(output_dir)
    output_config = config.get("output", {})
    for name, df in tables.items():
        dump_normalized_table(df, out_dir / f"{name}.json", output_config)

    save_error_log(errors, out_dir)
    logger.info("=" * 60)
    logger.info("Data Quality Summary:")
    logger.info(" Total games processed: %d", len(games))
    logger.info(" Total errors encountered: %d", len(errors))
    for name, df in tables.items():
        logger.info(" Table '%s': %d records", name.capitalize(), len(df))
    logger.info("=" * 60)

    logger.info("Summary Statistics:")

    if "games" in tables and not tables["games"].empty:  # Games statistics
        games_df = tables["games"]
        logger.info(" Games table:")
        if "released" in games_df.columns:
            logger.info("   Released dates: %d unique values", games_df["released"].nunique())
        if "rating" in games_df.columns:
            logger.info("   Average rating: %.2f", games_df["rating"].mean())
            logger.info("   Rating range: %.2f - %.2f", games_df["rating"].min(), games_df["rating"].max())

    if "genres" in tables and not tables["genres"].empty:  # Genres statistics
        genre_counts = tables["genres"].groupby("genre").size().sort_values(ascending=False)
        logger.info(" Genres: %d unique, top 5:", len(genre_counts))
        for genre, count in genre_counts.head(5).items():
            logger.info("   %s: %d games", genre, count)

    if "platforms" in tables and not tables["platforms"].empty:  # Platforms statistics
        platform_counts = tables["platforms"].groupby("platform").size().sort_values(ascending=False)
        logger.info(" Platforms: %d unique, top 5:", len(platform_counts))
        for platform, count in platform_counts.head(5).items():
            logger.info("   %s: %d games", platform, count)

    logger.info("=" * 60)


def _parse_args():
    """
    Parse command-line arguments.
    :return:
        Parsed arguments.
    """
    p = argparse.ArgumentParser(description="Normalize JSON produced by exporter.py into tidy tables.")
    p.add_argument("input", nargs="?", default="games_data.json", help="Path to raw JSON (default: `games_data.json`).")
    p.add_argument("--out-dir", default="normalized", help="Output directory (default: `normalized`).")
    p.add_argument("--validate-only", action="store_true", help="Only validate the input file without transforming.")
    p.add_argument("--config", default="config.yaml", help="Path to YAML configuration file (default: `config.yaml`).")
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()

    if args.validate_only:
        success = validate_input_file(args.input, args.config)
        exit(0 if success else 1)
    else:
        normalize_exported_file(args.input, args.out_dir, args.config)
