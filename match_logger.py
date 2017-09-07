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


# def get_matchid(steamid):
#     url = 'https://api.steampowered.com/IDOTA2MatchStats_570/GetRealtimeStats/v1/?key={}&server_steam_id={}'.format(API_KEY,steamid)
#     attempts = 0
#     while attempts < 3:
#         try:
#             data = urllib.request.urlopen(url).read().decode()
#             data = json.loads(data)
#             mid = data['match']['matchid']
#             return mid
#         except:
#             logger.warning('Failed attempt #{} to get match id from server_steam_id {}'.format(attempts+1, steamid))
#             attempts += 1
#             time.sleep(1)
#     return None

def get_match_id(server_steam_id, max_attempts = 3, sleep = 1):
    url = 'https://api.steampowered.com/IDOTA2MatchStats_570/GetRealtimeStats/v1/?key={}&server_steam_id={}'.format(API_KEY, server_steam_id)
    # print (url)
    attempts = 0
    while attempts < max_attempts:
        try:
            data = urllib.request.urlopen(url).read().decode()
            data = json.loads(data)
            mid = data['match']['matchid']
            return int(mid)
        except:
            attempts += 1
            time.sleep(sleep)
    return None

def get_player_info(id):
    try:
        player = api.get_player_summaries(id)['players'][0]
        name = player['personaname']
        steam_id = player['steamid']
    except:
        name = None
        steam_id = None

    return name, steam_id


def load(name):
    with open(name, 'r') as fp:
        return json.load(fp)



def number_heroes_picked(api_game):
    try:
        heroes = [player['hero_id'] for player in api_game['players']]
        heroes = set(heroes)
        if 0 in heroes:
            heroes.remove(0)
        return len(heroes)
    except:
        return 0

def ten_heros_picked(api_game):
    try:
        heroes = [player['hero_id'] for player in api_game['players']]
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

def parse_api_game(api_game, continue_if_db = True):

    if not hasattr(api_game, 'get'):
        return None

    lobby_id = api_game.get('lobby_id')
    server_steam_id  = api_game.get('server_steam_id')
    players = api_game.get('players', [])
    hero_ids = [player.get('hero_id', 0) for player in players]

    match = {
        'is_in_db' : False,
        'number_heroes_picked' : number_heroes_picked(api_game),
        'match' : {
            'average_mmr' : api_game.get('average_mmr', 0),
            'server_steam_id': server_steam_id,
            'lobby_id': lobby_id,
            'match_id': None,
            'activate_time' : api_game.get('activate_time', 0),
            'players' : [],
            'heroes' : [],
        }

    }

    # Use lobby_id to check if game is already in the database
    if Game.query.filter_by(lobby_id=lobby_id).first() is not None:
        match['is_in_db'] = True
        if not continue_if_db:
            return match

    match['match']['match_id'] = get_match_id(server_steam_id, 3, 0)
    # Check for players whether they are in the database or not

    if players is not None:
        for player in players:
            account_id = player.get('account_id')
            hero_id = player.get('hero_id', 0)
            player_name, player_steam_id = get_player_info(account_id)
            p = {
                'is_in_db' : False,
                'player' : {
                    'name': player_name,
                    'account_id': account_id,
                    'steam_id': player_steam_id,
                    'hero_id' : hero_id,
                }
            }
            if Player.query.filter_by(account_id=account_id).first() is not None:
                p['is_in_db'] = True

            match['match']['players'].append(p)

    return match



while True:

    api_games = get_top_live_games()
    if api_games is None:
        # Sometimes getting top live games from the api just fails, so we try againa fter a 5 second break
        time.sleep(5)
        continue

    for api_game in api_games:

        match = parse_api_game(api_game, continue_if_db=False)
        if match is None:
            continue

        if match['match']['lobby_id'] is None:
            logger.info('No lobby id found for match.')
            continue

        if match['is_in_db']:
            logger.info('{} : Match already in db'.format(match['match']['lobby_id']))
            continue

        if match['number_heroes_picked'] < 10:
            logger.info('{} : Still drafting.'.format(match['match']['lobby_id']))
            continue

        if match['match']['server_steam_id'] is None:
            logger.info('{} : No steam id found'.format(match['match']['lobby_id']))
            continue
        else:
            logger.info('{} : Found server_steam_id {}'.format(match['match']['lobby_id'],match['match']['server_steam_id']))


        if match['match']['match_id'] is None:
            logger.info('{} : No match id found'.format(match['match']['lobby_id']))
            continue
        else:
            logger.info('{} : Found match_id {}'.format(match['match']['lobby_id'],match['match']['match_id']))


        # At this point hopefully everything we would like to add does exist.

        account_ids = [p['player']['account_id'] for p in match['match']['players']]
        hero_ids = [p['player']['hero_id'] for p in match['match']['players']]


        for player in match['match']['players']:

            if player['is_in_db']:
                continue

            logger.info('{} : Adding player {} ({}) '.format(
                match['match']['lobby_id'],
                player['player']['name'],
                player['player']['account_id'])
            )

            player_obj = Player(
                name = player['player']['name'],
                account_id = player['player']['account_id'],
                steam_id = player['player']['steam_id'],
            )
            db.session.add(player_obj)


        match_obj = Game(
            mmr = match['match']['average_mmr'],
            server_steam_id = match['match']['server_steam_id'],
            match_id = match['match']['match_id'],
            lobby_id = match['match']['lobby_id'],
            activate_time=match['match']['activate_time'],
            players = str(account_ids),
            heroes = str(hero_ids),
        )

        db.session.add(match_obj)
        db.session.commit()


    logger.info('Updated. Waiting {} seconds'.format(t_wait))
    time.sleep(t_wait)
