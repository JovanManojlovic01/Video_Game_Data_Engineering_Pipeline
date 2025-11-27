# python
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Union

import pandas as pd

logger = logging.getLogger(__name__)


def normalize_list_of_values(games: List[Dict], field: str, out_col: str) -> pd.DataFrame:
    """
    Normalize a list of values from the specified field in the games data.
    :param: games: list of game records (dictionaries).
            field: source field containing list of values.
            out_col: specified output column name.
    :return:
        A DataFrame with game_id and the specified output column.
    """
    rows = []
    for g in games:
        gid = g.get("id")
        vals = g.get(field, []) or []
        if isinstance(vals, list):
            for v in vals:
                rows.append({"game_id": gid, out_col: v})
    return pd.DataFrame(rows, columns=["game_id", out_col])


def normalize_list_of_dicts(games: List[Dict], field: str, rename_map: Dict[str, str]) -> pd.DataFrame:
    """
    Normalize a list of dictionaries from the specified field in the games data.
    :param: games: list of game records (dictionaries).
            field: source field containing list of dictionaries.
            rename_map: mapping of old field names to new column names.
    :return:
        A DataFrame with game_id and the renamed columns.
    """
    rows = []
    for g in games:
        gid = g.get("id")
        items = g.get(field, []) or []
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict):
                rec = {"game_id": gid}
                rec.update({new: it.get(old) for old, new in rename_map.items()})
                rows.append(rec)
    cols = ["game_id", *rename_map.values()]
    return pd.DataFrame(rows, columns=cols)


def transform_games(games: List[Dict]) -> pd.DataFrame:
    """
    Transform the games data into a normalized DataFrame.
    :param:
        games: list of game records (dictionaries).
    :return:
        A DataFrame with selected game fields.
    """
    df = pd.json_normalize(games)
    keep = ["id", "name", "rating", "aggregated_rating", "first_release_date"]
    existing = [c for c in keep if c in df.columns]
    return df[existing] if existing else pd.DataFrame(columns=keep)


def load_exported_games(path: Path) -> List[Dict]:
    """
    Load exported games from a JSON file.
    :param:
        path: Path to the JSON file.
    :return:
        A list of game records (dictionaries).
    """
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_normalized_table(df: pd.DataFrame, path: Path) -> None:
    """
    Dump the normalized DataFrame to a JSON file.
    :param:
        df: DataFrame to dump.
        path: Path to the output JSON file.
    :return:
        None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_json(path.as_posix(), orient="records", indent=2, force_ascii=False)
    logger.info("Wrote %s (rows=%d)", path, len(df))


def normalize_exported_file(raw_json_path: Union[str, Path], output_dir: Union[str, Path] = "normalized") -> None:
    """
    Normalize the exported JSON file into tidy tables.
    :param:
        raw_json_path: Path to the raw JSON file.
        output_dir: Output directory for normalized tables.
    :return:
        None
    """
    src = Path(raw_json_path)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {src}")
    games = load_exported_games(src)
    if not games:
        logger.warning("No records in %s; nothing to normalize.", src)
        return

    tables = {
        "games": transform_games(games),
        "genres": normalize_list_of_values(games, "genres", "genre_id"),
        "platforms": normalize_list_of_values(games, "platforms", "platform_id"),
        "release_dates": normalize_list_of_dicts(games, "release_dates", {"date": "release_date", "platform": "platform_id"}),
        "involved_companies": normalize_list_of_dicts(
            games,
            "involved_companies",
            {"company": "company_id", "developer": "is_dev", "publisher": "is_publisher"},
        ),
    }

    out_dir = Path(output_dir)
    for name, df in tables.items():
        dump_normalized_table(df, out_dir / f"{name}.json")


def _parse_args():
    """
    Parse command-line arguments.
    :return:
        Parsed arguments.
    """
    p = argparse.ArgumentParser(description="Normalize JSON produced by exporter.py into tidy tables.")
    p.add_argument("input", nargs="?", default="games_data.json", help="Path to raw JSON (default: `games_data.json`).")
    p.add_argument("--out-dir", default="normalized", help="Output directory (default: `normalized`).")
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    normalize_exported_file(args.input, args.out_dir)
