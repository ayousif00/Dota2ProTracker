from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import API_KEY, DB

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://{}'.format(DB)
db = SQLAlchemy(app)

class Hero(db.Model):
    #__tablename__ = 'heroes'
    id = db.Column(db.Integer, primary_key=True)
    hero_id = db.Column(db.Integer, unique=True)
    localized_name = db.Column(db.String)
    url_small_portrait = db.Column(db.String)
    url_large_portrait = db.Column(db.String)
    url_full_portrait = db.Column(db.String)


class Player(db.Model):
    #__tablename__ = 'player'
    # Here we define columns for the table person
    # Notice that each column is also a normal Python instance attribute.
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    account_id = db.Column(db.String(250), nullable=False, unique=True)
    steam_id = db.Column(db.String(250), nullable=False, unique=True)
    #identity_id = db.Column(db.Integer, db.ForeignKey('identity.id'))
    #identity = db.relationship('Identity', backref='player')


class Identity(db.Model):
    #__tablename__ = 'identities'
    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(db.String)
    account_id = db.Column(db.Integer, unique=True)
    #player = db.relationship('Player', backref=db.backref('identity'))

    # def __init__(self, name, account_id):
    #     self.name = name
    #     self.account_id = account_id


class Game(db.Model):
    #__tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    mmr = db.Column(db.Integer)
    server_steam_id = db.Column(db.Integer)
    match_id = db.Column(db.Integer)
    lobby_id = db.Column(db.Integer)
    activate_time = db.Column(db.Integer)
    players = db.Column(db.String)
    heroes = db.Column(db.String)