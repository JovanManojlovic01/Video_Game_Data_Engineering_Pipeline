import logging

from auth import generate_token
from env_config import ensure_env_variables
from exporter import export_results
from igdb_client import fetch_games
from user_input import prompt_for_query_settings

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Main function to run the ETL process for fetching and exporting game data from IGDB.
    :return: None
    """
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
        level=logging.INFO,
        handlers=[logging.StreamHandler(), logging.FileHandler("app.log", encoding="utf-8")],
    )

    ensure_env_variables()
    settings = prompt_for_query_settings()
    token = generate_token()
    if not token:
        logger.critical("Failed to acquire access token.")
        return

    games = fetch_games(settings, token)
    if not games:
        logger.error("No data returned from IGDB.")
        return

    export_results(settings.endpoint, games)


if __name__ == "__main__":
    main()
