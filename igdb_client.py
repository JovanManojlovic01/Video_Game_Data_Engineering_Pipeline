import logging
import os
from typing import Any, List
import requests
from user_input import QuerySettings
from json.decoder import JSONDecodeError

logger = logging.getLogger(__name__)
BASE_URL = "https://api.igdb.com/v4"
REQUEST_TIMEOUT = 10


def fetch_games(settings: QuerySettings, token: str) -> List[Any]:
    """
    Fetch games from the IGDB API based on the provided settings and token.
    :param:
        settings: The query settings from QuerySettings that were generated in user_input.py for the IGDB request.
        token: The access token for IGDB API.
    :return:
        A list of game data returned from the IGDB API.
    """
    headers = {
        "Client-ID": os.getenv("clientID", ""),
        "Authorization": f"Bearer {token}",
    }

    if not headers["Client-ID"]:
        logger.error("Environment variable 'clientID' is missing.")
        return []

    clauses = [
        f"fields {', '.join(settings.fields)};" if settings.fields else "fields *;",
        f"limit {settings.limit};",
        f"offset {settings.offset};",
        f"sort release_dates {settings.release_sort};",
    ]
    payload = "".join(clauses)

    try:
        response = requests.post(
            f"{BASE_URL}/{settings.endpoint}",
            headers=headers,
            data=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "") # IGDB should return JSON
        if "application/json" not in content_type.lower():
            logger.error("Unexpected content type from IGDB: %s", content_type)
            return []

        try:
            return response.json()
        except JSONDecodeError as exc:
            logger.error("Failed to decode IGDB JSON response: %s", exc)
            return []

    except requests.exceptions.Timeout:
        logger.error("IGDB request timed out.")
    except requests.exceptions.ConnectionError:
        logger.error("IGDB connection error.")
    except requests.exceptions.HTTPError as exc:
        logger.error("IGDB HTTP error: %s", exc)
    except (ValueError, requests.exceptions.RequestException) as exc:
        logger.error("IGDB request failed: %s", exc)
    return []
