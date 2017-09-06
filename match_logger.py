import dota2api
import time
import json
import urllib
import logging
from config import API_KEY, DB
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db, Hero, Player, Identity, Game

FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format = FORMAT, level=logging.INFO)
logger = logging.getLogger()
api = dota2api.Initialise(API_KEY)

def get_top_live_games():
    try:
        results = api.get_top_live_games()
        api_games = results['game_list']
        return api_games
    except:
        return None


def log(game):
    logger.info('{} : added - MMR={}, match_id={}'.format(game['lobby_id'],game['mmr'],game['match_id']))


def get_matchid(steamid):
    url = 'https://api.steampowered.com/IDOTA2MatchStats_570/GetRealtimeStats/v1/?key={}&server_steam_id={}'.format(API_KEY,steamid)
    attempts = 0
    while attempts < 3:
        try:
            data = urllib.request.urlopen(url).read().decode()
            data = json.loads(data)
            mid = data['match']['matchid']
            return mid
        except:
            logger.warning('Failed attempt #{} to get match id from server_steam_id {}'.format(attempts+1, steamid))
            attempts += 1
            time.sleep(1)
    return None

def get_player_info(id):
    if type(id) is str:
        id = int(id)

    player = api.get_player_summaries(id)['players'][0]
    name = player['personaname']
    steamid = player['steamid']

    return name, steamid


def load(name):
    with open(name, 'r') as fp:
        return json.load(fp)


def ten_heros_picked(game):
    try:
        heroes = [player['hero_id'] for player in game['players']]
    except:
        return False

    if len(set(heroes)) < 10:
        return False

    elif 0 in heroes or '0' in heroes:
        return False

    else:
        return True

#Games = check_games(Games)

#ids = {str(v): k for k, v in identities.items()}

t_wait = 60

while True:

    api_games = get_top_live_games()
    if api_games is None:
        time.sleep(5)
        continue

    for api_game in api_games:

        server_steam_id = api_game['server_steam_id']
        lobby_id = api_game['lobby_id']

        # Use lobby_id to check if game is already in the database
        if Game.query.filter_by(lobby_id=lobby_id).first() is not None:
            continue

        # We wait until the draft has finished before adding a match to the database
        if not ten_heros_picked(api_game):
            logger.info('{} : Still drafting'.format(lobby_id))
            continue


        logger.info('{} : adding...'.format(lobby_id))

        # Separate API call to receive match_id as it is not provided by GetTopLiveGames
        match_id = get_matchid(server_steam_id)

        if match_id is None:
            logger.warning('{} : No match id found for server_steam_id {}'.format(lobby_id, server_steam_id))
            match_id = 0
        else:
            logger.info('{} : Found match id: {}'.format(lobby_id, match_id))

        # Check for players whether they are in the database or not
        for player in api_game['players']:
            if Player.query.filter_by(account_id = player['account_id']).first() is None:
                logger.info('{}: Found new account id: {}'.format(lobby_id, player['account_id']))
                try:
                    player_name, player_steam_id = get_player_info(player['account_id'])
                except:
                    player_name, player_steam_id = 'Unknown', 0
                    logger.warning('{}: Could not identify account id {}'.format(lobby_id, player['account_id']))

                p = Player(
                    name = player_name,
                    account_id = player['account_id'],
                    steam_id = player_steam_id
                )
                db.session.add(p)

        players_list = [player['account_id'] for player in api_game['players']]

        new_game = Game(
                mmr = api_game['average_mmr'],
                server_steam_id = int(server_steam_id),
                match_id = int(match_id),
                lobby_id = int(lobby_id),
                activate_time = api_game['activate_time'],
                players = str(players_list),
                heroes = str([player['hero_id'] for player in api_game['players']])
        )


        db.session.add(new_game)
        db.session.commit()

        #log(new_game)


    logger.info('Updated. Waiting {} seconds'.format(t_wait))
    time.sleep(t_wait)
