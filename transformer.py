"""
MISSING VALUE HANDLING STRATEGY
================================

Critical Fields (records are SKIPPED if missing):
- id: Unique game identifier (cannot be null or empty)
- name: Game title (cannot be null or empty)

Optional Fields with Default Values:
- rating: Defaults to 0.0 if missing or None (empty lists [] are preserved)
- aggregated_rating: Defaults to 0.0 if missing or None
- first_release_date: Defaults to None (unknown release)
- genres: Defaults to empty list [] if missing or None
- platforms: Defaults to empty list [] if missing or None
- involved_companies: Defaults to empty list [] if missing or None

Note: Empty strings "" are treated as missing for string fields.
      Empty lists [] are NOT replaced with defaults (only None or missing fields).

Recommended Fields (WARNING logged if missing):
- summary: Game description
- storyline: Game narrative

Validation Process:
1. Load raw JSON data
2. Filter out records missing critical fields (logged to errors)
3. Apply default values to optional fields
4. Validate remaining records against schema
5. Transform into normalized tables
6. Generate missing value report

All skipped records and missing values are logged to error_log_YYYYMMDD_HHMMSS.json
"""

import argparse
import json
import ijson
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Union, Literal, cast, Generator
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


def process_in_batches(games_generator, batch_size: int):
    """
    Process games in batches from a generator.
    :param:
        games_generator: Generator yielding game records.
        batch_size: Size of each batch.
    :return:
        A generator yielding lists of game records in batches.
    """
    batch = []
    for game in games_generator:
        batch.append(game)
        if len(batch) >= batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


def save_error_log(errors: List[Dict], output_dir: Path) -> None:
    if not errors:
        return

    error_log_path = output_dir / f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    with error_log_path.open("w", encoding="utf-8") as f:
        json.dump(errors, f, indent=4, ensure_ascii=False)

    logger.info(" Error log saved to %s", error_log_path)


def filter_valid_games(games: List[Dict], errors: List[Dict]) -> List[Dict]:
    """
    Filter out invalid game records missing critical fields.

    STRATEGY:
    - Critical fields (id, name) must exist, records are SKIPPED if missing
    - All skipped records are logged to the errors list with context
    - Valid games are returned for further processing

    :param:
        games: list of game records (dictionaries).
        errors: list to append error records to.
    :return:
        A list of valid game records.
    """
    valid_games = []
    skipped_count = 0
    for idx, game in enumerate(games):
        if not game.get("id"):
            errors.append({
                "index": idx,
                "error_type": "missing_critical_field",
                "field": "id",
                "game_data": str(game)
            })
            logger.error("Skipping game at index %d due to missing 'id' field.", idx)
            skipped_count += 1
            continue

        if not game.get("name"):
            errors.append({
                "index": idx,
                "game_id": game.get("id"),
                "error_type": "missing_critical_field",
                "field": "name",
                "game_data": str(game)
            })
            logger.error("Skipping game ID %s due to missing 'name' field.", game.get("id"))
            skipped_count += 1
            continue

        valid_games.append(game)

    logger.info("Filtered %d valid games out of %d total; (skipped %d)",
                len(valid_games), len(games), skipped_count)
    return valid_games


def apply_default_values(games: List[Dict], config: Dict) -> List[Dict]:
    """
    Apply default values to missing fields in game records.

    Default values:
    - rating: 0.0 (no rating available)
    - aggregated_rating: 0.0 (no aggregated rating)
    - genres: [] (no genres specified)
    - platforms: [] (no platforms specified)
    - involved_companies: [] (no companies involved)

    :param:
        games: list of game records (dictionaries).
        config: configuration dictionary.
    :return:
        A list of game records with defaults applied.
    """
    defaults = config.get("defaults", {
        "rating": 0.0,
        "aggregated_rating": 0.0,
        "genres": [],
        "platforms": [],
        "involved_companies": []
    })

    if not defaults:
        logger.warning("No default values specified in configuration.")
        return games

    applied_count = 0
    for game in games:
        for field, default_value in defaults.items():
            if field not in game or game[field] is None:
                game[field] = default_value
                logger.debug("Applied default for game ID %s: %s=%s", game.get("id"), field, default_value)
                applied_count += 1

    logger.info("Applied default values to %d fields across %d games.", applied_count, len(games))
    return games


def detect_duplicate_game_ids(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect duplicate game IDs in the DataFrame and log warnings.
    :param:
        df: DataFrame containing game records.
    :return:
        A DataFrame with duplicate game records.
    """
    duplicates = df[df.duplicated(subset=['id'], keep=False)]
    if not duplicates.empty:
        logger.warning("Found %d duplicate game IDs.", len(duplicates['id'].unique()))
        for game_id in duplicates['id'].unique():
            logger.warning("Game ID %d appears %d times",
                           game_id, len(df[df['id'] == game_id]))
    return duplicates


def apply_deduplication_strategy(df: pd.DataFrame, key_col: List[str], strategy: str) -> pd.DataFrame:
    before_count = len(df)

    if strategy == 'keep_first':
        result = df.drop_duplicates(subset=key_col, keep='first')
    elif strategy == 'keep_last':
        result = df.drop_duplicates(subset=key_col, keep='last')
    elif strategy == 'merge':
        if 'rating' in df.columns and 'name' in df.columns:
            aggregated_dict = {}
            if 'rating' in df.columns:
                aggregated_dict['rating'] = 'mean'
            if 'name' in df.columns:
                aggregated_dict['name'] = 'first'
            if 'aggregated_rating' in df.columns:
                aggregated_dict['aggregated_rating'] = 'mean'
            if 'first_release_date' in df.columns:
                aggregated_dict['first_release_date'] = 'min'

            result = df.groupby(key_col, as_index=False).agg(aggregated_dict)
        else:
            result = df.drop_duplicates(subset=key_col, keep='first')
    else:
        raise ValueError(f"Unknown deduplication strategy: {strategy}")

    duplicates_removed = before_count - len(result)
    if duplicates_removed > 0:
        logger.info("Removed %d duplicate records using strategy '%s' (keys: %s)",
                    duplicates_removed, strategy, key_col)
    return result


def log_duplicates_stats(tables: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    stats = {}

    if 'games' in tables:  # Games table checking since it is the main table
        games_duplicates = tables['games'].duplicated(subset=['id'], ).sum()
        stats['games_duplicates'] = games_duplicates
        logger.info("Games table duplicates found: %d", games_duplicates)

    table_keys = {
        'genres': ['game_id', 'genre_id'],
        'platforms': ['game_id', 'platform_id'],
        'involved_companies': ['game_id', 'company_id']
                    }

    for table_name, key_col in table_keys.items():
        if table_name in tables:
            df = tables[table_name]
            duplicates = df.duplicated(subset=key_col).sum()
            stats[f'{table_name}_duplicates'] = duplicates
            logger.info("%s table duplicates found: %d", table_name.capitalize(), duplicates)

    return stats


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
    df = pd.DataFrame(rows, columns=["game_id", out_col])
    if 'game_id' in df.columns:
        df['game_id'] = pd.to_numeric(df['game_id'], errors='coerce').astype('Int64')
    return df


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
    df = pd.DataFrame(rows, columns=["game_id", *rename_map.values()])
    if 'game_id' in df.columns:
        df['game_id'] = pd.to_numeric(df['game_id'], errors='coerce').astype('Int64')
    if 'company_id' in df.columns:
        df['company_id'] = pd.to_numeric(df['company_id'], errors='coerce').astype('Int64')
    return df


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
        detect_duplicate_game_ids(df)
        keep = config.get("tables", {}).get("games", {}).get("fields", [])
        if 'first_release_date' in df.columns:  # Convert timestamp to datetime
            df['release_year'] = pd.to_datetime(df['first_release_date'], unit='s', errors='coerce').dt.year
        if 'id' in df.columns:  # Ensure 'id' is integer type
            df['id'] = pd.to_numeric(df['id'], errors='coerce').astype('Int64')
        for rating in ['rating', 'aggregated_rating']:
            if rating in df.columns:  # Ensure ratings are float type
                df[rating] = pd.to_numeric(df[rating], errors='coerce').astype('Float64')
                df['has_rating'] = (df['rating'].notna() & (df['rating'] > 0)).astype('boolean')
            if 'aggregated_rating' in df.columns:
                df['has_aggregated_rating'] = (df['aggregated_rating'].notna() & (df['aggregated_rating'] > 0)).astype('boolean')
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
        games = list(load_exported_games(src))
        validate_required_fields(games, config)
        logger.info("✓ Validation passed: %s (%d records)", src, len(games))
        return True
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("✗ Validation failed: %s", e)
        return False


def load_exported_games(path: Path) -> Generator[Dict, None, None]:
    """
    Load exported games from a JSON file.
    :param:
        path: Path to the JSON file.
    :return:
        A list of game records (dictionaries).
    """
    try:
        with path.open("rb") as fh:
            for game in ijson.items(fh, "item"):
                yield game
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

    valid_orients = ["split", "records", "index", "columns", "values", "table"]
    orient_value = output_config.get("orient", "records")
    if orient_value not in valid_orients:
        raise ValueError(f"Invalid JSON orient '{orient_value}'. Valid options are: {valid_orients}")
    orient = cast(Literal["split", "records", "index", "columns", "values", "table"], orient_value)

    indent = output_config.get("indent", 2)
    force_ascii = output_config.get("force_ascii", False)
    df.to_json(path.as_posix(), orient=orient, indent=indent, force_ascii=force_ascii)
    logger.info("Wrote %s (rows=%d)", path, len(df))


# noinspection PyDictCreation
def normalize_exported_file(raw_json_path: Union[str, Path], output_dir: Union[str, Path] = "normalized",
                            batch_size: int = 1000, config_path: Union[str, Path] = "config.yaml") -> None:
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
    deduplication_config = config.get("deduplication", {})
    valid_strategies = ['keep_first', 'keep_last', 'merge']
    strategy = deduplication_config.get("strategy", "keep_first")
    if strategy not in valid_strategies:
        raise ValueError(f"Invalid deduplication strategy '{strategy}'. Valid options are: {valid_strategies}")
    logger.info("Using deduplication strategy: %s", strategy)
    errors = []

    src = Path(raw_json_path)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {src}")
    games_generator = load_exported_games(src)
    all_games = []

    for batch in process_in_batches(games_generator, batch_size):
        filtered_batch = filter_valid_games(batch, errors)
        batch_with_defaults = apply_default_values(filtered_batch, config)
        all_games.extend(batch_with_defaults)

    if not all_games:
        logger.warning("No records in %s; nothing to normalize.", src)

    validate_required_fields(all_games, config)
    games = all_games

    table_configs = config.get("tables", {})
    tables = {}

    tables["games"] = transform_games(games, config)  # Games table

    tables["games"] = apply_deduplication_strategy(tables["games"],
                                                   key_col=['id'],
                                                   strategy=strategy)

    if "genres" in table_configs:  # Genres table
        genres_cfg = table_configs["genres"]
        tables["genres"] = normalize_list_of_values(games,
                                                    genres_cfg["source_field"],
                                                    genres_cfg["output_column"],
                                                    errors)
        tables["genres"] = apply_deduplication_strategy(tables["genres"],
                                                        key_col=['game_id', 'genre_id'],
                                                        strategy=strategy)

    if "genres" in tables and not tables["genres"].empty:
        genre_counts = tables["genres"].groupby("game_id").size().reset_index(name="genre_count")
        tables["games"] = tables["games"].merge(genre_counts, left_on="id", right_on="game_id", how="left")
        tables["games"]["genre_count"] = tables["games"]["genre_count"].fillna(0).astype("Int64")
        tables["games"].drop(columns=["game_id"], inplace=True, errors='ignore')

    if "platforms" in table_configs:  # Platforms table
        platforms_cfg = table_configs["platforms"]
        tables["platforms"] = normalize_list_of_values(games,
                                                       platforms_cfg["source_field"],
                                                       platforms_cfg["output_column"],
                                                       errors)
        tables["platforms"] = apply_deduplication_strategy(tables["platforms"],
                                                           key_col=['game_id', 'platform_id'],
                                                           strategy=strategy)

    if "platforms" in tables and not tables["platforms"].empty:
        platform_counts = tables["platforms"].groupby("game_id").size().reset_index(name="platform_count")
        tables["games"] = tables["games"].merge(platform_counts, left_on="id", right_on="game_id", how="left")
        tables["games"]["platform_count"] = tables["games"]["platform_count"].fillna(0).astype("Int64")
        tables["games"].drop(columns=["game_id"], inplace=True, errors='ignore')


    if "involved_companies" in table_configs:  # Involved Companies table
        involved_companies_cfg = table_configs["involved_companies"]
        tables["involved_companies"] = normalize_list_of_values(games,
                                                                involved_companies_cfg["source_field"],
                                                                involved_companies_cfg["output_column"],
                                                                errors)
        tables["involved_companies"] = apply_deduplication_strategy(tables["involved_companies"],
                                                                    key_col=['game_id', 'company_id'],
                                                                    strategy=strategy)

        for bool_field in ['is_dev', 'is_publisher']:  # Convert boolean fields
            if bool_field in tables["involved_companies"].columns:
                tables["involved_companies"][bool_field] = tables["involved_companies"][bool_field].astype('boolean')

    out_dir = Path(output_dir)
    output_config = config.get("output", {})
    schemas = config.get("schemas", {})

    for name, df in tables.items():
        if name in schemas:  # Validate schema if defined
            try:
                validate_schema(df, schemas[name])
                logger.info("✓ Schema validation passed for table '%s'.", name)
            except ValueError as e:
                logger.error("✗ Schema validation failed for table '%s': %s", name, e)
                raise
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
        genre_counts = tables["genres"].groupby("genre_id").size().sort_values(ascending=False)
        logger.info(" Genres: %d unique, top 5:", len(genre_counts))
        for genre_id, count in genre_counts.head(5).items():
            logger.info("   %s: %d games", genre_id, count)

    if "platforms" in tables and not tables["platforms"].empty:  # Platforms statistics
        platform_counts = tables["platforms"].groupby("platform_id").size().sort_values(ascending=False)
        logger.info(" Platforms: %d unique, top 5:", len(platform_counts))
        for platform_id, count in platform_counts.head(5).items():
            logger.info("   %s: %d games", platform_id, count)

    logger.info("=" * 60)

    logger.info("Duplicate Records Statistics:")
    duplicate_stats = log_duplicates_stats(tables)
    if not duplicate_stats:
        logger.info(" No duplicate statistics available.")

    if "games_duplicates" in duplicate_stats:
        logger.info(" Games table duplicates: %d", duplicate_stats["games_duplicates"])
    if "genres_duplicates" in duplicate_stats:
        logger.info(" Genres table duplicates: %d", duplicate_stats["genres_duplicates"])
    if "platforms_duplicates" in duplicate_stats:
        logger.info(" Platforms table duplicates: %d", duplicate_stats["platforms_duplicates"])
    if "involved_companies_duplicates" in duplicate_stats:
        logger.info(" Involved Companies table duplicates: %d", duplicate_stats["involved_companies_duplicates"])

    logger.info("=" * 60)


def validate_schema(df: pd.DataFrame, expected_schema: Dict[str, str]) -> bool:
    """
    Validate the DataFrame against the expected schema.
    :param:
        df: DataFrame to validate.
        expected_schema: Dictionary mapping column names to expected data types.
    :return:
        True if the DataFrame matches the expected schema, raises ValueError otherwise.
    """
    for col, expected_type in expected_schema.items():
        if col not in df.columns:
            continue
        actual_type = df[col].dtype
        if expected_type == 'datetime' and not pd.api.types.is_datetime64_any_dtype(actual_type):
            raise ValueError(f"Column {col}: expected datetime, got {actual_type}")
        elif expected_type == 'int' and not pd.api.types.is_integer_dtype(actual_type):
            raise ValueError(f"Column {col}: expected int, got {actual_type}")
        elif expected_type == 'bool' and not pd.api.types.is_bool_dtype(actual_type):
            raise ValueError(f"Column {col}: expected bool, got {actual_type}")
        elif expected_type == 'float' and not pd.api.types.is_float_dtype(actual_type):
            raise ValueError(f"Column {col}: expected float, got {actual_type}")
    return True


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
    p.add_argument("--batch-size", type=int, default=1000, help="Batch size for processing (default: 1000).")
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()

    if args.validate_only:
        success = validate_input_file(args.input, args.config)
        exit(0 if success else 1)
    else:
        normalize_exported_file(args.input, args.out_dir, batch_size=args.batch_size, config_path=args.config)
