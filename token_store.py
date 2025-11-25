import json
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def load_token(path: str) -> Tuple[Optional[str], float]:
    """
    Load the token from a JSON file.
    :param:
        path: The file path to load the token from.
    :return:
        A tuple of the access token and its expiration timestamp.
    """
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
                logger.info("Token loaded from %s", path)
                return data.get("access_token"), float(data.get("expires_at", 0))
    except (OSError, ValueError) as exc:
        logger.error("Failed to load token: %s", exc)
    return None, 0.0


def save_token(path: str, token: str, expires_at: float) -> None:
    """
    Save the token to a JSON file.
    :param:
        path: The file path to save the token to.
        token: The access token to save.
        expires_at: The expiration timestamp of the token.
    """
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump({"access_token": token, "expires_at": expires_at}, file)
            logger.info("Token saved to %s", path)
    except OSError as exc:
        logger.error("Failed to save token: %s", exc)
