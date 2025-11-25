import logging
from typing import Any, List

import pandas as pd

logger = logging.getLogger(__name__)


def export_results(endpoint: str, games: List[Any]) -> None:
    """
    Export the fetched game data to JSON and CSV files.
    :param:
        endpoint: The IGDB endpoint used for the query.
        games: The list of game data fetched from IGDB.
    :return: None
    """
    if not games:
        logger.warning("No data to export for endpoint %s.", endpoint)
        return

    try:
        df = pd.json_normalize(games)
    except Exception as exc:
        logger.error("Failed to normalize IGDB payload: %s", exc)
        return

    json_path = f"{endpoint}_data.json"
    csv_path = f"{endpoint}_data.csv"

    try:
        df.to_json(json_path, orient="records", indent=4, force_ascii=False)
        logger.info("JSON export written to %s", json_path)
    except OSError as exc:
        logger.error("Failed to write JSON export: %s", exc)

    try:
        df.to_csv(csv_path, index=False, encoding="utf-8")
        logger.info("CSV export written to %s", csv_path)
    except OSError as exc:
        logger.error("Failed to write CSV export: %s", exc)
