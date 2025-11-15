import requests
from dotenv import load_dotenv
import os

load_dotenv('.env')

def generateToken():
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": os.getenv('CLIENTID'),
        "client_secret": os.getenv('CLIENTSECRET'),
        "grant_type": "client_credentials"
    }

    response = requests.post(url, params=params)
    access_token = response.json().get("access_token")
    return access_token

def extractData():
    url = 'https://api.igdb.com/v4/games' # url for getting 'games' data

    headers = {
        "Client-ID": os.getenv('clientID'),
        "Authorization": f"Bearer {generateToken()}"
    }

    data = "fields name, release_dates, rating, aggregated_rating;"

    response = requests.post(url, headers=headers, data=data)
    games = response.json()
    return games

if __name__ == "__main__":
    games = extractData()
    print(games)