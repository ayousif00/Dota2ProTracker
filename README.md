# Dota2ProTracker
Python project that uses the public steam web api for Dota 2 to log high MMR games and track professional player's games

**In development!**

## Requirements

- dota2api (pip install dota2api)
- Flask
- SQLAlchemy
- Flask-SQLAlchemy

Tested with Python 3.

## Usage

Run *create_db.py* to create the database. However, a newly created database will be empty and therefore it will not contain hero information like hero avatar urls which will result in an incomplete display of matches. This repository comes with a database that contains players, heroes and matches so you don't need to create a new database.

Run *match_logger.py* to fetch new high MMR games and add them to the database.

Run *app.py* to run the flask server. Open 127.0.0.1:5000/matches to see matches.
