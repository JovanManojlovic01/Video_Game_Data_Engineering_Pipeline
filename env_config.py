import logging
import os
import sys
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
_REQUIRED_ENV_VARS = ("clientID", "clientSecret", "tokenFile")
_DOTENV_LOADED = False


def _ensure_dotenv_loaded() -> None:
    """
    Ensure that the .env file is loaded only once.
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    if not load_dotenv(".env"):
        logger.critical("File .env not found or could not be loaded.")
        sys.exit(1)
    _DOTENV_LOADED = True


def ensure_env_variables() -> None:
    """
    Ensure that all required environment variables are set.
    """
    _ensure_dotenv_loaded()
    missing = [var for var in _REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        logger.critical("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)


def get_token_file_path() -> str:
    """
    Get the path to the token file from environment variables or use default.
    """
    _ensure_dotenv_loaded()
    token_file = os.getenv("tokenFile")
    if not token_file:
        token_file = "token.json"
        logger.warning("Environment variable 'tokenFile' missing; defaulting to %s", token_file)
    return token_file
