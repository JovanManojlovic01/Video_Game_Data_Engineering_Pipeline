import logging
import os
import time
from typing import Optional
import requests
from env_config import get_token_file_path
from token_store import load_token, save_token

logger = logging.getLogger(__name__)
TOKEN_ENDPOINT = "https://id.twitch.tv/oauth2/token"
TOKEN_TIMEOUT = 5


def generate_token() -> Optional[str]:
    """
    Generate or retrieve a cached access token.
    :return:
        The access token string or None if generation failed.
    """
    token_path = get_token_file_path()
    access_token, expires_at = load_token(token_path)

    if access_token and time.time() < expires_at:
        logger.info("Using cached token")
        return access_token

    if os.path.exists(token_path):
        try:
            os.remove(token_path)
            logger.info("Expired token removed: %s", token_path)
        except OSError as exc:
            logger.error("Unable to remove expired token: %s", exc)

    params = {
        "client_id": os.getenv("clientID"),
        "client_secret": os.getenv("clientSecret"),
        "grant_type": "client_credentials",
    }

    try:
        response = requests.post(TOKEN_ENDPOINT, params=params, timeout=TOKEN_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        logger.error("Token request timed out.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Token request connection error.")
        return None
    except requests.exceptions.HTTPError as exc:
        logger.error("Token request failed: %s", exc)
        return None
    except (ValueError, requests.exceptions.RequestException) as exc:
        logger.error("Unexpected token request error: %s", exc)
        return None

    access_token = data.get("access_token")
    if not access_token:
        logger.error("Token response missing 'access_token'.")
        return None

    try:
        expires_in = int(data.get("expires_in", 0))
    except (TypeError, ValueError):
        expires_in = 0

    new_expiration = time.time() + max(expires_in, 0)
    save_token(token_path, access_token, new_expiration)
    return access_token