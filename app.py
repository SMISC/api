import database
import flask
import logging
import time

from flask import Flask
from ConfigParser import ConfigParser
from functools import wraps

from util import get_current_virtual_time, timeline, cursor, make_json_response, not_implemented, fill_temporal, translate_time
from formatter import UserFormatter, TweetFormatter, GuessFormatter
from search import Search

from detectionteam import DetectionTeam
from guess import Guess
from guess_user import GuessUser
from tuser import TUser
from tweet import Tweet

config = ConfigParser()
config.read('configuration.ini')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@/pacsocial?host=%s' % (config.get('postgresql', 'username'), config.get('postgresql', 'password'), config.get('postgresql', 'socket'))
database.db.init_app(app)

def require_passcode(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if 'Authorization' not in flask.request.headers:
            return flask.make_response('', 401)

        password = flask.request.headers['Authorization'].replace('Bearer ', '')
        team = DetectionTeam.query.filter(DetectionTeam.password == password).first()

        if team is None:
            return flask.make_response('', 403)

        kwargs['team_id'] = team.id

        return f(*args, **kwargs)
            
    return decorator

@app.route('/edges/near/<time>/followers/<user_id>', methods=['GET'])
@cursor
@not_implemented
@make_json_response
def timeless_list_followers():
    pass

@app.route('/edges/explore/<time>/<from_user>/to/<to_user>', methods=['GET'])
@cursor
@not_implemented
@make_json_response
def timeless_explore_edges():
    pass

@app.route('/user/near/<time>', methods=['GET'])
@app.route('/user', methods=['GET'], defaults={'time': None})
@cursor
@not_implemented
@fill_temporal
@translate_time
@make_json_response
def list_users(time, cursor_size, offset):
    users = TUser.query.filter(
        TUser.timestamp <= time, 
        TUser.timestamp < get_current_virtual_time()
    ).order_by(TUser.id.desc()).limit(cursor_size).offset(offset).all()
    formatter = UserFormatter()
    return formatter.format(users)

@app.route('/user/near/<time>/<user_id>', methods=['GET'])
@app.route('/user/<user_id>', methods=['GET'], defaults={'time': None})
@fill_temporal
@translate_time
@make_json_response
def show_user(time, user_id):
    users = TUser.query.filter(
        TUser.user_id == user_id, 
        TUser.timestamp < get_current_virtual_time()
    ).order_by(TUser.id.desc()).limit(1).first()
    formatter = UserFormatter()
    return formatter.format(users)

@app.route('/user/near/<time>/<user_id>/Tweets', methods=['GET'])
@app.route('/user/<user_id>/Tweets', methods=['GET'], defaults={'time': None})
@fill_temporal
@translate_time
@timeline
@make_json_response
def list_Tweets_by_user(time, max_id, since_id, since_count, user_id):
    tweets = Tweet.query.filter(
        Tweet.tweet_id > since_id, 
        Tweet.tweet_id <= max_id, 
        Tweet.timestamp <= time, 
        Tweet.timestamp < get_current_virtual_time(), 
        Tweet.user_id == user_id
    ).order_by(Tweet.timestamp.desc()).limit(since_count).all()
    formatter = TweetFormatter()
    return formatter.format(tweets)

@app.route('/Tweets/near/<time>', methods=['GET'])
@app.route('/Tweets', methods=['GET'], defaults={'time': None})
@fill_temporal
@translate_time
@timeline
@make_json_response
def list_Tweets(time, max_id, since_id, since_count):
    Tweets = Tweet.query.filter(
        Tweet.tweet_id > since_id, 
        Tweet.tweet_id <= max_id, 
        Tweet.timestamp <= time, 
        Tweet.timestamp < get_current_virtual_time()
    ).order_by(Tweet.timestamp.desc()).limit(since_count).all()
    formatter = TweetFormatter()
    return formatter.format(Tweets)

@app.route('/search', methods=['GET', 'POST'])
@timeline
@not_implemented
@make_json_response
def search(max_id, since_id, since_count):
    tweets_query = Tweet.query.filter(
        Tweet.timestamp < get_current_virtual_time(), 
        Tweet.tweet_id > since_id, 
        Tweet.tweet_id <= max_id
    ).order_by(Tweet.timestamp.desc()).limit(since_count)

    search = Search(flask.request.values['q'])
    search.apply_filter(tweets_query)

    if 'users' in flask.request.values:
        tweet_query.filter(Tweet.user_id.in_(flask.request.values['users']))
    tweets = tweets_query.all()

    formatter = TweetFormatter()
    return formatter.format(tweets)

@app.route('/guess', methods=['GET'])
@require_passcode
@make_json_response
def list_guesses(team_id):
    guesses = Guess.query.filter(Guess.team_id == team_id).order_by(Guess.id.desc()).all()
    formatter = GuessFormatter()
    return formatter.format(guesses)

@app.route('/guess/<guess_id>', methods=['GET'])
@require_passcode
@make_json_response
def show_guess(team_id, guess_id):
    guess = Guess.query.filter(Guess.team_id == team_id, Guess.id == guess_id).first()
    formatter = GuessFormatter()
    return formatter.format(guess)

@app.route('/guess', methods=['PUT', 'POST'])
@require_passcode
@make_json_response
def make_guess(team_id):
    bots = flask.request.values['bots']

    if len(bots):
        guess = Guess(team_id=team_id, timestamp=time.time())
        database.db.session.add(guess)
        database.db.session.commit()

        for bot in bots:
            guess_user = GuessUser(guess_id=guess.id, tuser_id=bot)
            database.db.session.add(guess_user)

        database.db.session.commit()

        guess = Guess.query.filter(Guess.id == guess.id).first()

        formatter = GuessFormatter()
        return formatter.format(guess)

if __name__ == "__main__":
    app.debug = True
    logging.getLogger().setLevel(logging.INFO)
    app.run(host='0.0.0.0')
