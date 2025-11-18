import json
import time
import pandas as pd
import requests
from dotenv import load_dotenv
import os
import logging

logger = logging.getLogger(__name__)

if not load_dotenv('.env'):
    logger.critical("File .env not found or could not be loaded.")

TOKEN_FILE = os.getenv('tokenFile')
if not TOKEN_FILE:
    logger.warning("Environment variable 'tokenFile' not set or does not exist. Will create a new one")


def save_token(token, expires_at):
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump({"access_token": token, "expires_at": expires_at}, f)
            logging.info("Token saved to file.")
    except IOError as e:
        logging.error(f"Error saving token to file: {e}")


def load_token():
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                logging.info("Token loaded from file.")
                return data.get("access_token"), data.get("expires_at")
        return None, 0
    except (IOError, ValueError) as e:
        logging.error(f"Error loading token from file: {e}")
        return None, 0


def generateToken():
    access_token, token_expiration = load_token()

    if access_token and time.time() < token_expiration:
        logging.info("Using cached token")
        return access_token

    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        logging.info("Expired token file removed")

    logging.info("Generating new token")
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": os.getenv('clientID'),
        "client_secret": os.getenv('clientSecret'),
        "grant_type": "client_credentials"
    }

    try:
        response = requests.post(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.Timeout:
        logging.error("API Request timed out.")
        return None
    except requests.exceptions.ConnectionError:
        logging.error("Connection error occurred.")
        return None
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error occurred: {e}")
        if e.response.status_code == 429:
            logging.error("Too many requests. Please try again later.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None
    except ValueError as e:
        logging.error(f"Failed to parse token response JSON: {e}")
        return None

    access_token = data.get("access_token")
    if not access_token:
        logging.error("Token response did not contain 'access_token'.")
        return None

    try:
        expires_in = int(data.get("expires_in", 0))
    except (TypeError, ValueError) as e:
        logging.error(f"Invalid 'expires_in' value: {e}")
        expires_in = 0

    token_expiration = time.time() + expires_in
    save_token(access_token, token_expiration)
    return access_token

def extractData():
    fieldArray = []

    logger.info("Starting data extraction process")

    endpoint = input("Enter the endpoint you wish to gather data from:").strip().lower()
    if not endpoint:
        logging.error("Endpoint cannot be empty.")
        return None

    try:
        fieldNumberOf = int(input("Please enter the number of fields you wish to use:").strip())
        if fieldNumberOf <= 0:
            logging.error("Number of fields must be a positive number.")
            return None
    except ValueError:
        logging.error("Invalid input. Please enter a valid number for the number of fields.")
        return None

    for i in range(fieldNumberOf):
        field = input(f"Enter field number {i + 1}: ").strip()
        fieldArray.append(field)
        print(fieldArray)  #DEBUG

    releaseSort = input("Do you wish to have the release date sorted in ascending or descending order? asc/desc:").strip().lower()
    if releaseSort not in ("asc", "desc"):
        logging.error("Invalid sort order selected. Defaulting to asc")
        releaseSort = "asc"

    try:
        limit = int(input("How many inputs do you wish to gather:").strip())
        if limit <= 0:
            logging.error("Limit must be a positive number.")
            return None
    except ValueError:
        logging.error("Invalid input. Please enter a valid number for the limit.")
        return None

    try:
        offset = int(input("Is there any entries you wish to skip? type 0 if you do not want to skip:").strip())
        if offset < 0:
            logging.error("Offset cannot be negative.")
            return None
    except ValueError:
        logging.error("Invalid input. Please enter a valid number for the offset.")
        return None

    token = generateToken()
    if not token:
        logging.error("Failed to obtain access token.")
        return None

    headers = {
        "Client-ID": os.getenv('clientID'),
        "Authorization": f"Bearer {token}"
    }

    fieldQuery = "fields " + ", ".join(fieldArray) + ";"

    query = (f""
             f"{fieldQuery}"
             "where rating != null;"
             f"limit {limit};"
             f"offset {offset};"
             f"sort release_dates {releaseSort};")

    try:
        response = requests.post(f'https://api.igdb.com/v4/{endpoint}', headers=headers, data=query, timeout=10)
        response.raise_for_status()

    except requests.exceptions.Timeout:
        logging.error("API Request timed out.")
        return None
    except requests.exceptions.ConnectionError:
        logging.error("Connection error occurred.")
        return None
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error occurred: {e}")
        if e.response.status_code == 429:
            logging.error("Too many requests. Please try again later.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


    try:
        games = response.json()
    except ValueError as e:
        logging.error(f"Failed to parse response JSON: {e}")
        return None

    logging.info("Responses Gathered")
    time.sleep(0.25)
    try:
        df = pd.json_normalize(games)
    except Exception as e:
        logging.error(f"Error normalizing JSON data: {e}")
        return None

    logging.info("Creating JSON file of results")
    try:
        df.to_json(f'{endpoint}_data.json', orient='records', indent=4, force_ascii=False)
    except Exception as e:
        logging.error(f"Error writing JSON file: {e}")
        return None
    logging.info("JSON file created")

    time.sleep(0.25)

    logging.info("Creating CSV file of results")
    try:
        df.to_csv(f'{endpoint}_data.csv', index=False, encoding='utf-8')
    except Exception as e:
        logging.error(f"Error writing CSV file: {e}")
        return None
    logging.info("CSV file created")

    time.sleep(0.25)  #Just in case to avoid hitting rate limit of 4 requests/sec
    return games

if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
                        level=logging.INFO,
                        handlers=[logging.StreamHandler(), logging.FileHandler("app.log", encoding="utf-8")])
    games = extractData()
    print(games)  #DEBUG