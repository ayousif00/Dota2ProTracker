from flask import Flask, render_template
from models import app, DB, Game, Hero, Identity, Player
import datetime
import dota2api
from config import API_KEY, HOST
import pprint
api = dota2api.Initialise(API_KEY)
import urllib
import json
import time

def get_match_from_db(match):

    try:
        timestamp = datetime.datetime.fromtimestamp(int(match.activate_time)).strftime('%d.%m.%Y %H:%M:%S')
    except:
        timestamp = 'Unknown'

    match_dict = {
        'mmr' : match.mmr,
        'match_id' : match.match_id,
        'activate_time' : timestamp,
        'pros_count' : 0 # game contains pros?
    }

    radiant, dire = [], []
    players = eval(match.players)
    heroes = eval(match.heroes)
    for i, (account_id, hero_id) in enumerate(zip(players,heroes)):

        try:
            hero_result = Hero.query.filter_by(hero_id = hero_id).first()
            hero_name, hero_img = hero_result.localized_name, hero_result.url_large_portrait
        except:
            # ToDo: make this better
            hero_name = 'Hero 0'
            hero_img = ''

        try:
            player_name = Identity.query.filter_by(account_id=account_id).first().identity
            is_pro = True
            match_dict['pros_count'] += 1
        except:
            is_pro = False
            try:
                player_name = Player.query.filter_by(account_id=account_id).first().name
            except:
                player_name = None

        player = {
            'name': player_name,
            'is_pro': is_pro,
            'hero' : hero_name,
            'account_id': account_id,
            # 'hero_img_url': hero_img.replace('_sb.png', '_vert.jpg')
            'hero_img_url': hero_img
        }
        if i < 5:
            radiant.append(player)
        else:
            dire.append(player)

    match_dict['radiant'] = radiant
    match_dict['dire'] = dire

    return match_dict



def get_match_live_stats(steamid):
    '''
    Use server_steam_id to get realtime stats for the sidebar.

    Sometimes this fails on the first try so we give it 3 attempts.
    '''
    if steamid is None:
        return None

    url = 'https://api.steampowered.com/IDOTA2MatchStats_570/GetRealtimeStats/v1/?key={}&server_steam_id={}'.format(API_KEY,steamid)
    attempts = 0
    while attempts < 3:
        try:
            data = urllib.request.urlopen(url).read().decode()
            data = json.loads(data)
            return data
        except:
            #logger.warning('Failed attempt #{} to get match id from server_steam_id {}'.format(attempts+1, steamid))
            attempts += 1
            time.sleep(1)
    return None


def get_live_pro_games():

    '''

    Things that can go wrong:
    - no 'game_list

    :return:
    '''

    top_live_matches = api.get_top_live_games()
    identity_ids = [identity.account_id for identity in Identity.query.all()]

    try:
        match_list = top_live_matches['game_list']
    except:
        return [], identity_ids


    show_games = []

    for match in match_list:
        try:
            player_ids = [p['account_id'] for p in match['players']]
        except:
            continue

        # Checking whether the match contains any known pros
        if not set(player_ids).isdisjoint(identity_ids):
            show_games.append(match)

    for i, match in enumerate(show_games):
        try:
            server_steam_id = match['server_steam_id']
        except:
            server_steam_id = None

        live_stats = get_match_live_stats(server_steam_id)
        if live_stats is None:
            continue

        player_ids = [p['account_id'] for p in match['players']]
        pros_in_game = set(player_ids) & set(identity_ids)
        pros = []
        for pro in pros_in_game:
            name = Identity.query.filter_by(account_id = pro).first().identity
            identity_ids.remove(pro)

            try:
                teams = live_stats['teams']
            except:
                continue

            for team in teams:

                try:
                    players = team['players']
                except:
                    continue

                for player in players:

                    try:
                        account_id = player['accountid']
                    except:
                        continue

                    if account_id == int(pro):

                        try:
                            hero_name = Hero.query.filter_by(hero_id = player['heroid']).first().localized_name
                        except:
                            hero_name = 'Not picked'

                        try:
                            hero_img_url = Hero.query.filter_by(hero_id=player['heroid']).first().url_small_portrait.replace('_sb.png', '_vert.jpg')
                        except:
                            hero_img_url = '/static/images/hero_0.png'

                        pros.append(
                            {
                                'account_id' : pro,
                                'identity' : name,
                                'kills' : player['kill_count'],
                                'deaths' : player['death_count'],
                                'assists' : player['assists_count'],
                                'level' : player['level'],
                                'hero_name' : hero_name,
                                'hero_img_url': hero_img_url
                            }
                        )

        t = match['game_time']
        m, s = divmod(t, 60)
        if m > 59:
            h, m = divmod(m, 60)
            match['game_time'] = "%d:%02d:%02d" % (h, m, s)
        else:
            match['game_time'] = "%02d:%02d" % (m, s)
        match['pros_in_game'] = pros
        show_games[i] = match

    offline = []
    for pro in identity_ids:
        offline.append(
            {
                'account_id' : pro,
                'identity' :  Identity.query.filter_by(account_id = pro).first().identity
            }
        )
    # pprint.pprint(show_games)

    offline = sorted(offline, key=lambda pro: pro['identity'])

    return show_games, offline


@app.route('/player/<pname>')
def player(pname):
    live_games, offline = get_live_pro_games()
    account_id = Identity.query.filter_by(identity = pname).first().account_id
    matches = Game.query.filter(Game.players.contains(str(account_id))).order_by(Game.activate_time.desc()).all()
    processed_matches = [get_match_from_db(match) for match in matches]

    meta = {
        'title' : "{}'s recent matches".format(pname),
        'right_hl' : "{}'s recent matches".format(pname)
    }

    return render_template('ui.html', offline=offline, live=live_games, matches=processed_matches, meta = meta)

@app.route('/')
def live():
    live_games, offline = get_live_pro_games()
    matches = Game.query.order_by(Game.activate_time.desc()).limit(20).all()
    processed_matches = [get_match_from_db(match) for match in matches]

    meta = {
        'title' : "Dota2ProTracker",
        'right_hl' : "Recent & Ongoing High MMR Pub Games"
    }

    return render_template('ui.html', meta=meta, offline = offline, live = live_games, matches = processed_matches)
    # return render_template('ui.html', meta=meta, offline = offline, live = [], matches = processed_matches)

if __name__ == '__main__':
    app.run(host = HOST, threaded = True)