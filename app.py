import database
import flask
import logging
import time
import json

from datetime import datetime

from flask import Flask
from ConfigParser import ConfigParser
from functools import wraps

from util import TIME_BOT_COMPETITION_START
from util import timeline
from util import cursor
from util import make_json_response
from util import not_implemented
from util import temporal
from util import get_time_anchor
from util import get_current_virtual_time
from util import translate_alpha_time_to_virtual_time
from util import translate_virtual_time_to_alpha_time
from util import disabled_beta
from util import nearest_scan
from util import beta_predicate_tweets
from util import beta_predicate_users

from formatter import UserFormatter, TweetFormatter, GuessFormatter
from search import Search

from detectionteam import DetectionTeam
from guess import Guess
from guess_user import GuessUser
from tuser import TUser
from tweet import Tweet
from scan import Scan

config = ConfigParser()
config.read('configuration.ini')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@/pacsocial?host=%s' % (config.get('postgresql', 'username'), config.get('postgresql', 'password'), config.get('postgresql', 'socket'))
app.config['SQLALCHEMY_ECHO'] = True
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

@app.route('/clock', methods=['GET'], defaults={'vtime': None})
@app.route('/clock/<vtime>', methods=['GET'])
@make_json_response
@temporal
def show_clock(vtime):
    time_str = lambda t: datetime.fromtimestamp(t+(3600*-8)).strftime("%b %d %Y, %I:%M:%S %p PDT")

    virtual = vtime
    anchor = get_time_anchor()
    min_vtime = TIME_BOT_COMPETITION_START

    return json.dumps({
        "now": {
            "alpha": translate_virtual_time_to_alpha_time(vtime),
            "alpha_str":time_str(translate_virtual_time_to_alpha_time(vtime)),
            "virtual": vtime,
            "virtual_str": time_str(vtime)
        },
        "minimum": {
            "alpha": translate_virtual_time_to_alpha_time(min_vtime),
            "alpha_str":time_str(translate_virtual_time_to_alpha_time(min_vtime)),
            "virtual": min_vtime,
            "virtual_str": time_str(min_vtime)
        },
        "anchor": anchor,
        "alpha_str": time_str(anchor)
    })

@app.route('/edges/near/<vtime>/followers/<user_id>', methods=['GET'])
@make_json_response
@cursor
@not_implemented
def timeless_list_followers():
    pass

@app.route('/edges/explore/<vtime>/<from_user>/to/<to_user>', methods=['GET'])
@make_json_response
@cursor
@not_implemented
def timeless_explore_edges():
    pass

@app.route('/user/near/<vtime>', methods=['GET'])
@app.route('/user', methods=['GET'], defaults={'vtime': None})
@make_json_response
@temporal
@cursor
@nearest_scan
def list_users(vtime, cursor_size, offset, max_id, min_id):
    users = beta_predicate_users(TUser.query.filter(
        TUser.id >= min_id,
        TUser.id < max_id
    )).order_by(TUser.id.desc()).limit(cursor_size).offset(offset).all()
    formatter = UserFormatter()
    return json.dumps(formatter.format(users))

@app.route('/user/near/<vtime>/<user_id>', methods=['GET'])
@app.route('/user/<user_id>', methods=['GET'], defaults={'vtime': None})
@make_json_response
@temporal
@nearest_scan
def show_user(vtime, user_id, max_id, min_id):
    users = beta_predicate_users(TUser.query.filter(
        TUser.user_id == user_id, 
        TUser.id >= min_id,
        TUser.id <= max_id
    )).order_by(TUser.id.desc()).limit(1).first()
    formatter = UserFormatter()
    return json.dumps(formatter.format(users))

@app.route('/user/near/<vtime>/<user_id>/tweets', methods=['GET'])
@app.route('/user/<user_id>/tweets', methods=['GET'], defaults={'vtime': None})
@make_json_response
@temporal
@timeline
def list_Tweets_by_user(vtime, max_id, since_id, since_count, user_id):
    tweets = beta_predicate_tweets(Tweet.query.filter(
        Tweet.timestamp >= TIME_BOT_COMPETITION_START,
        Tweet.tweet_id > since_id, 
        Tweet.tweet_id <= max_id, 
        Tweet.timestamp <= vtime, 
        Tweet.user_id == user_id
    )).order_by(Tweet.timestamp.desc()).limit(since_count).all()
    formatter = TweetFormatter()
    return json.dumps(formatter.format(tweets))

@app.route('/tweets/near/<vtime>', methods=['GET'])
@app.route('/tweets', methods=['GET'], defaults={'vtime': None})
@make_json_response
@temporal
@timeline
def list_tweets(vtime, max_id, since_id, since_count):
    Tweets = beta_predicate_tweets(Tweet.query.filter(
        Tweet.timestamp >= TIME_BOT_COMPETITION_START,
        Tweet.tweet_id > since_id, 
        Tweet.tweet_id <= max_id, 
        Tweet.timestamp <= vtime
    )).order_by(Tweet.timestamp.desc()).limit(since_count).all()
    formatter = TweetFormatter()
    return json.dumps(formatter.format(Tweets))

@app.route('/search', methods=['GET', 'POST'])
@make_json_response
@timeline
@not_implemented
def search(max_id, since_id, since_count):
    tweets_query = beta_predicate_tweets(Tweet.query.filter(
        Tweet.timestamp >= TIME_BOT_COMPETITION_START,
        Tweet.timestamp < get_current_virtual_time(), 
        Tweet.tweet_id > since_id, 
        Tweet.tweet_id <= max_id
    )).order_by(Tweet.timestamp.desc()).limit(since_count)

    search = Search(flask.request.values['q'])
    search.apply_filter(tweets_query)

    if 'users' in flask.request.values:
        tweet_query.filter(Tweet.user_id.in_(flask.request.values['users']))

    tweets = tweets_query.all()

    formatter = TweetFormatter()
    return formatter.format(tweets)

@app.route('/guess', methods=['GET'])
@make_json_response
@disabled_beta
@require_passcode
def list_guesses(team_id):
    guesses = Guess.query.filter(Guess.team_id == team_id).order_by(Guess.id.desc()).all()
    formatter = GuessFormatter()
    return formatter.format(guesses)

@app.route('/guess/<guess_id>', methods=['GET'])
@make_json_response
@disabled_beta
@require_passcode
def show_guess(team_id, guess_id):
    guess = Guess.query.filter(Guess.team_id == team_id, Guess.id == guess_id).first()
    formatter = GuessFormatter()
    return formatter.format(guess)

@app.route('/guess', methods=['PUT', 'POST'])
@make_json_response
@disabled_beta
@require_passcode
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
