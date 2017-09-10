import dota2api
import time
import json
import urllib
import logging
from config import API_KEY, DB
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db, Hero, Player, Identity, Game
from jinja2 import Environment, FileSystemLoader

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


def get_match_id(server_steam_id, max_attempts = 3, sleep = 1):
    url = 'https://api.steampowered.com/IDOTA2MatchStats_570/GetRealtimeStats/v1/?key={}&server_steam_id={}'.format(API_KEY, server_steam_id)
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


t_wait = 30

def get_match_live_stats(steamid, max_attempts = 3, sleep = 0):
    '''
    Use server_steam_id to get realtime stats for the sidebar.

    Sometimes this fails on the first try so we give it 3 attempts.
    '''
    if steamid is None:
        return None


    url = 'https://api.steampowered.com/IDOTA2MatchStats_570/GetRealtimeStats/v1/?key={}&server_steam_id={}'.format(API_KEY,steamid)
    attempts = 0
    while attempts < max_attempts:
        try:
            data = urllib.request.urlopen(url).read().decode()
            data = json.loads(data)
            return data
        except:
            #logger.warning('Failed attempt #{} to get match id from server_steam_id {}'.format(attempts+1, steamid))
            attempts += 1
            time.sleep(sleep)
    return None

def get_pro_stats_from_live_game(live_stats, account_id):
    p = {
       'kills' : 0,
        'deaths' : 0,
        'assists' : 0,
        'level' : 0,
    }
    try:
        teams = live_stats.get('teams', [])
        for team in teams:
            players = team.get('players', [])
            for player in players:
                if player['accountid'] == account_id:
                    hero_id = player.get('heroid', 0)
                    if hero_id != 0:
                        hero = Hero.query.filter_by(hero_id = hero_id).first()
                        hero_name = hero.localized_name
                        hero_img_url = hero.url_small_portrait.replace('_sb.png', '_vert.jpg')
                    else:
                        hero_name = 'Not picked'
                        hero_img_url = '/static/images/hero_0.png'

                    p['kills'] = player.get('kill_count', 0)
                    p['deaths'] = player.get('death_count', 0)
                    p['assists'] = player.get('assists_count', 0)
                    p['level'] = player.get('level', 0)
                    p['hero_name'] = hero_name
                    p['hero_img_url'] = hero_img_url
                    return p
    except:
        return None



def pros_in_match(match, identity_ids):
    players = match.get('players', [])
    account_ids = [p['account_id'] for p in players]
    pro_account_ids = set(account_ids) & set(identity_ids)
    return pro_account_ids

def formatted_game_time(game_time):
    assert type(game_time) is int
    m, s = divmod(game_time, 60)
    if m > 59:
        h, m = divmod(m, 60)
        fgt = "%d:%02d:%02d" % (h, m, s)
    else:
        fgt = "%02d:%02d" % (m, s)
    return fgt

def parse_api_game(api_game, continue_if_db = True, continue_if_no_pro = True):

    if not hasattr(api_game, 'get'):
        return None

    lobby_id = api_game.get('lobby_id')
    server_steam_id  = api_game.get('server_steam_id')
    players = api_game.get('players', [])
    hero_ids = [player.get('hero_id', 0) for player in players]
    has_pros = False
    identity_ids = [identity.account_id for identity in Identity.query.all()]

    match = {
        'is_in_db' : False,
        'has_pros' : False,
        'number_heroes_picked' : number_heroes_picked(api_game),
        'live_stats' : None, # ToDo: don't keep this, throw it out later
        'match' : {
            'average_mmr' : api_game.get('average_mmr', 0),
            'server_steam_id': server_steam_id,
            'lobby_id': lobby_id,
            'match_id': None,
            'activate_time' : api_game.get('activate_time', 0),
            'players' : [],
            'heroes' : [],
            'radiant_score' : api_game.get('radiant_score', 0),
            'dire_score' : api_game.get('dire_score', 0),
            'game_time' : formatted_game_time(api_game.get('game_time', 0))
        }
    }

    # Quick check if game has pros
    pro_account_ids = pros_in_match(api_game, identity_ids)
    has_pros = len(pro_account_ids) > 0
    match['has_pros'] = has_pros
    if not has_pros:
        if not continue_if_no_pro:
            return match




    # Use lobby_id to check if game is already in the database.
    # If the game is already in the database we only continue
    # if continue_if_db == True or there is a pro in the game.
    if Game.query.filter_by(lobby_id=lobby_id).first() is not None:
        match['is_in_db'] = True
        if not continue_if_db and not has_pros:
            return match

    match['match']['match_id'] = get_match_id(server_steam_id, 3, 0)

    # Check for players whether they are in the database or not

    if players is not None:
        for player in players:
            is_pro = False
            identity = None
            player_live_stats = None
            account_id = player.get('account_id')

            #####
            if account_id in pro_account_ids:
                # player is a pro
                is_pro = True
                identity = Identity.query.filter_by(account_id = account_id).first().identity
                # ToDo: Cache identities before loop

                # in case of multiple in the same match we might have tried to get live stats alrdy
                if match['live_stats'] is None:
                    live_stats = get_match_live_stats(server_steam_id)
                    match['live_stats'] = live_stats
                else:
                    live_stats = match['live_stats']

                player_live_stats = get_pro_stats_from_live_game(live_stats, account_id)
                # ToDo: instead of doing this for every player, do it once and use results here
                # because we have nested loops in get_pro_stats_...
            #####

            hero_id = player.get('hero_id', 0)

            player_db = Player.query.filter_by(account_id=account_id).first()
            if player_db is not None:
                is_in_db = True
                player_name = player_db.name
                player_steam_id = player_db.steam_id
            else:
                is_in_db = False
                player_name, player_steam_id = get_player_info(account_id)
            p = {
                'is_in_db' : is_in_db,
                'is_pro' : is_pro,
                'player' : {
                    'name': player_name,
                    'account_id': account_id,
                    'steam_id': player_steam_id,
                    'hero_id' : hero_id,
                    'identity': identity,
                }
            }
            if player_live_stats is not None:
                p['player'].update(player_live_stats)

            match['match']['players'].append(p)


    match['live_stats'] = None

    return match



while True:

    api_games = get_top_live_games()
    if api_games is None:
        # Sometimes getting top live games from the api just fails, so we try again after a 5 second break
        time.sleep(5)
        continue

    livegames = []

    for api_game in api_games:

        match = parse_api_game(api_game, continue_if_db=False)
        if match is None:
            continue

        if match['match']['lobby_id'] is None:
            logger.info('No lobby id found for match.')
            continue

        if match['has_pros']:
            logger.info('{} : Match has pro players in it'.format(match['match']['lobby_id']))
            livegames.append(match)

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

    logger.info('Updated. Caching live games now.')
    with open("cached_livegames.json", "w") as fh:
        json.dump(livegames, fh, indent=4)

    logger.info('Cached. Waiting {} seconds'.format(t_wait))
    time.sleep(t_wait)
