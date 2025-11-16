import json
import time
import pandas as pd
import requests
from dotenv import load_dotenv
import os

load_dotenv('.env')
TOKEN_FILE = os.getenv('tokenFile')

def save_token(token, expires_at):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": token, "expires_at": expires_at}, f)

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            return data["access_token"], data["expires_at"]
    return None, 0

def generateToken():
    access_token, token_expiration = load_token()

    if access_token and time.time() < token_expiration:
        print("Using cached token")
        return access_token

    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

    print("Generating new token")
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": os.getenv('clientID'),
        "client_secret": os.getenv('clientSecret'),
        "grant_type": "client_credentials"
    }

    response = requests.post(url, params=params)
    data = response.json()
    access_token = data.get("access_token")
    expires_in = data.get("expires_in", 0)

    token_expiration = time.time() + expires_in
    save_token(access_token, token_expiration)
    return access_token

def extractData():
    fieldArray = []

    endpoint = input("Enter the endpoint you wish to gather data from:").strip()
    fieldNumberOf = int(input("Please enter the number of fields you wish to use:"))
    for i in range(fieldNumberOf):
        field = input(f"Enter field number {i+1}: ")
        fieldArray.append(field)
        print(fieldArray)#DEBUG
    releaseSort = input("Do you wish to have the release date sorted in ascending or descending order? asc/desc:")
    limit = input("How many inputs do you wish to gather:").strip()
    offset = input("Is there any entries you wish to skip? type 0 if you do not want to skip:")

    headers = {
        "Client-ID": os.getenv('clientID'),
        "Authorization": f"Bearer {generateToken()}"
    }

    fieldQuery = "fields " + ", ".join(fieldArray) + ";"

    query = (f""
             f"{fieldQuery}"
             "where rating != null;"
             f"limit {limit};"
             f"offset {offset};"
             f"sort release_dates {releaseSort};")

    response = requests.post(f'https://api.igdb.com/v4/{endpoint}', headers=headers, data=query)
    games = response.json()
    print("Responses Gathered")
    time.sleep(0.25)
    df = pd.json_normalize(games)

    print("Creating JSON file of results")
    df.to_json(f'{endpoint}_data.json', orient='records', indent=4, force_ascii=False)
    print("JSON file created")
    time.sleep(0.25)
    print("Creating CSV file of results")
    df.to_csv(f'{endpoint}_data.csv', index=False, encoding='utf-8')
    print("CSV file created")

    time.sleep(0.25) #Just in case to avoid hitting rate limit of 4 requests/sec
    return games

if __name__ == "__main__":
    games = extractData()
    print(games)#DEBUG
