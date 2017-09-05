from flask import Flask, render_template
from models import app, DB, Game, Hero, Identity, Player
import datetime

#app = Flask(__name__)
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://{}'.format(DB)
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
            hero_name, hero_img = hero_result.localized_name, hero_result.url_small_portrait
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
            'hero_img_url': hero_img
        }
        if i < 5:
            radiant.append(player)
        else:
            dire.append(player)

    match_dict['radiant'] = radiant
    match_dict['dire'] = dire

    return match_dict




@app.route('/matches')
def matches():
    matches = Game.query.order_by(Game.activate_time.desc()).limit(20).all()
    processed_matches = [get_match_from_db(match) for match in matches]

    return render_template('index.html', games = processed_matches, title='Matches')

@app.route('/player/<pname>')
def player(pname):
    account_id = Identity.query.filter_by(identity = pname).first().account_id
    matches = Game.query.filter(Game.players.contains(str(account_id))).order_by(Game.activate_time.desc()).all()
    processed_matches = [get_match_from_db(match) for match in matches]

    return render_template('index.html', games = processed_matches, title='{}\'s matches'.format(pname))

@app.route('/pros/<num>')
def pros(num):
    matches = Game.query.order_by(Game.activate_time.desc()).all()
    processed_matches = [get_match_from_db(match) for match in matches]
    processed_matches = [b for b in processed_matches if b['pros_count'] >= int(num)]
    return render_template('index.html', games = processed_matches, title='Pros')


if __name__ == '__main__':
    app.run()
