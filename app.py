import atexit
import functools
import gc
import socket
import database
import flask
import logging
import time
import json
import sys

from logging.handlers import SysLogHandler
from logging import StreamHandler

from datetime import datetime
from statsd import statsd

from flask import Flask
from ConfigParser import ConfigParser
from functools import wraps
from cassandra.cluster import Cluster as CassandraCluster
from cassandra.auth import PlainTextAuthProvider

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
from util import we_are_out_of_beta
from util import timed
from util import track_pageview

from formatter import UserFormatter, TweetFormatter, GuessFormatter, EdgeFormatter
from search import Search

from detectionteam import DetectionTeam
from guess import Guess
from guess_user import GuessUser
from tuser import TUser
from tuser import TwitterUser
from tweet import Tweet
from scan import Scan
from bot import Bot
from tweet_entity import TweetEntity

config = ConfigParser()
config.read('configuration.ini')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@/pacsocial?host=%s' % (config.get('postgresql', 'username'), config.get('postgresql', 'password'), config.get('postgresql', 'socket'))
app.config['SQLALCHEMY_ECHO'] = False
database.db.init_app(app)

def cassandrafied(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        cluster = CassandraCluster([config.get('cassandra', 'contact')], auth_provider=PlainTextAuthProvider(username=config.get('cassandra', 'username'), password=config.get('cassandra', 'password')), executor_threads=50)
        session = cluster.connect('smisc')
        kwargs['cassandra_cluster'] = session
        try:
            return f(*args, **kwargs)
        finally:
            session.shutdown()
            cluster.shutdown()
            # grumble grumble grumble, cassandra people caused memory leaks by assuming atexit is called
            for ext in atexit.__dict__['_exithandlers']:
                (handler, args, kwargs) = ext
                if isinstance(handler, functools.partial) and len(handler.args) > 0 and isinstance(handler.args[0], CassandraCluster) and handler.func.func_name == '_shutdown_cluster':
                    atexit.__dict__['_exithandlers'].remove(ext)
            gc.collect()


    return decorator

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
@timed('page.clock.render')
@make_json_response
@temporal
@track_pageview
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
@app.route('/edges/followers/<user_id>', methods=['GET'], defaults={'vtime': None})
@timed('page.edges_followers.render')
@make_json_response
@temporal
@timeline
@nearest_scan(Scan.SCAN_TYPE_FOLLOWERS)
@cassandrafied
@track_pageview
def timeless_list_followers(cassandra_cluster, vtime, user_id, max_id, since_id, since_count, max_scan_id, min_scan_id):
    user = beta_predicate_users(TwitterUser.query.filter(TwitterUser.twitter_id == user_id)).first()

    if user is not None:
        id_condition = ""
        ids = []

        wanted_min_id = since_id+1
        wanted_max_id = max_id+1

        if min_scan_id is not None and max_scan_id is not None:
            wanted_min_id = max(since_id+1, min_scan_id)
            wanted_max_id = min(max_id+1, max_scan_id)
        elif min_scan_id is not None and max_scan_id is None:
            wanted_min_id = max(since_id+1, min_scan_id)
        elif min_scan_id is None and max_scan_id is not None:
            wanted_max_id = min(max_id+1, max_scan_id)

        conds = [user_id]

        id_condition = 'id >= %s'
        conds.append(wanted_min_id)

        if wanted_max_id != float('+inf'):
            id_condition += ' and id < %s'
            conds.append(wanted_max_id)

        rows = cassandra_cluster.execute("SELECT id, to_user, from_user, \"timestamp\" FROM tuser_tuser WHERE to_user = %s AND " + id_condition + " ORDER BY id DESC LIMIT " + str(since_count), tuple(conds))
        formatter = EdgeFormatter()
        return json.dumps(formatter.format(rows))
    else:
        return flask.make_response('', 404)

@app.route('/edges/explore/<vtime>/<from_user>/to/<to_user>', methods=['GET'])
@timed('page.edges_explore.render')
@make_json_response
@temporal
@timeline
@nearest_scan(Scan.SCAN_TYPE_FOLLOWERS)
@cassandrafied
@track_pageview
def timeless_explore_edges(cassandra_cluster, vtime, from_user, to_user, max_id, since_id, since_count, max_scan_id, min_scan_id):
    to_user = beta_predicate_users(TUser.query.filter(TUser.user_id == to_user)).first()

    if to_user is not None:
        id_condition = ""
        ids = []

        wanted_min_id = since_id
        wanted_max_id = max_id+1

        if max_scan_id is not None:
            wanted_max_id = min(max_id+1, max_scan_id)
        elif max_scan_id is not None:
            wanted_max_id = min(max_id+1, max_scan_id)

        conds = [to_user.user_id, from_user]

        id_condition = 'id > %s'
        conds.append(wanted_min_id)

        if wanted_max_id != float('+inf'):
            id_condition += ' and id < %s'
            conds.append(wanted_max_id)

        logging.info(id_condition)
        logging.info(conds)

        rows = cassandra_cluster.execute("SELECT id, to_user, from_user, \"timestamp\" FROM tuser_tuser_inspect WHERE to_user = %s AND from_user = %s AND " + id_condition + " ORDER BY id DESC LIMIT " + str(since_count), tuple(conds))
        formatter = EdgeFormatter()
        return json.dumps(formatter.format(rows))
    else:
        return flask.make_response('', 404)

@app.route('/user/near/<vtime>', methods=['GET'])
@app.route('/user', methods=['GET'], defaults={'vtime': None})
@timed('page.user_list.render')
@make_json_response
@temporal
@cursor
@nearest_scan(Scan.SCAN_TYPE_USER)
@track_pageview
def list_users(vtime, cursor_size, offset, max_scan_id, min_scan_id):
    users = beta_predicate_users(TUser.query.filter(
        TUser.id >= min_scan_id,
        TUser.id <= max_scan_id
    )).order_by(TUser.id.desc()).limit(cursor_size).offset(offset).all()
    formatter = UserFormatter()
    return json.dumps(formatter.format(users))

@app.route('/user/near/<vtime>/<user_id>', methods=['GET'])
@app.route('/user/<user_id>', methods=['GET'], defaults={'vtime': None})
@timed('page.user_get.render')
@make_json_response
@temporal
@nearest_scan(Scan.SCAN_TYPE_USER)
@track_pageview
def show_user(vtime, user_id, max_scan_id, min_scan_id):
    user = beta_predicate_users(TUser.query.filter(
        TUser.user_id == user_id, 
        TUser.id >= min_scan_id,
        TUser.id <= max_scan_id
    )).order_by(TUser.id.desc()).limit(1).first()

    if user is None:
        return flask.make_response('', 404)
    else:
        formatter = UserFormatter()
        return json.dumps(formatter.format(user))

@app.route('/user/near/<vtime>/<user_id>/tweets', methods=['GET'])
@app.route('/user/<user_id>/tweets', methods=['GET'], defaults={'vtime': None})
@timed('page.user_tweets.render')
@make_json_response
@temporal
@timeline
@track_pageview
def list_tweets_by_user(vtime, max_id, since_id, since_count, user_id):
    user = beta_predicate_users(TUser.query.filter(
        TUser.user_id == user_id
    )).limit(1).first()

    if user is None:
        return flask.make_response('', 404)
    else:
        tweets = beta_predicate_tweets(Tweet.query.filter(
            Tweet.timestamp >= TIME_BOT_COMPETITION_START,
            Tweet.tweet_id > since_id, 
            Tweet.tweet_id <= max_id, 
            Tweet.timestamp <= vtime, 
            Tweet.user_id == user_id
        )).order_by(Tweet.tweet_id.desc()).limit(since_count).all()
        formatter = TweetFormatter()
        return json.dumps(formatter.format(tweets))

@app.route('/tweets/near/<vtime>', methods=['GET'])
@app.route('/tweets', methods=['GET'], defaults={'vtime': None})
@timed('page.tweets.render')
@make_json_response
@temporal
@timeline
@track_pageview
def list_tweets(vtime, max_id, since_id, since_count):
    tweets = beta_predicate_tweets(Tweet.query.filter(
        Tweet.timestamp >= TIME_BOT_COMPETITION_START,
        Tweet.tweet_id > since_id, 
        Tweet.tweet_id <= max_id, 
        Tweet.timestamp <= vtime
    )).order_by(Tweet.tweet_id.desc()).limit(int(since_count)).all()
    formatter = TweetFormatter()
    return json.dumps(formatter.format(tweets))

@app.route('/search', methods=['GET', 'POST'])
@timed('page.search.render')
@make_json_response
@timeline
@track_pageview
def search(max_id, since_id, since_count):
    tweets_query = beta_predicate_tweets(Tweet.query.filter(
        Tweet.timestamp >= TIME_BOT_COMPETITION_START,
        Tweet.timestamp < get_current_virtual_time(), 
        Tweet.tweet_id > since_id, 
        Tweet.tweet_id <= max_id
    )).order_by(Tweet.tweet_id.desc())

    debug = []
    search = Search(flask.request.values['q'], debug)
    tree = search.parse()
    ors = search.apply(tweets_query, tree)

    if 'users' in flask.request.values:
        tweet_query.filter(Tweet.user_id.in_(flask.request.values['users']))

    tweets = tweets_query.filter(ors).limit(since_count).all()

    formatter = TweetFormatter()
    resp = json.dumps(formatter.format(tweets))

    if 'X-Debug' in flask.request.headers:
        return flask.make_response(resp, 200, {'Debug': debug})
    else:
        return resp

@app.route('/guess/<guess_id>', methods=['GET'])
@timed('page.guess_get.render')
@make_json_response
@require_passcode
@track_pageview
def show_guess(team_id, guess_id):
    guess = Guess.query.filter(Guess.team_id == team_id, Guess.id == guess_id).first()

    if guess is None:
        return flask.make_response('', 404)
    
    scores = dict()
    for user in guess.users:
        scores[user.tuser_id] = -0.25

    bots_found = Bot.query.filter(Bot.twitter_id.in_(scores.keys()))

    if we_are_out_of_beta():
        for bot in bots_found:
            scores[bot.twitter_id] = 1

    formatter = GuessFormatter()
    return json.dumps(formatter.format(guess, scores))

@app.route('/guess', methods=['GET'])
@timed('page.guess_list.render')
@make_json_response
@require_passcode
@track_pageview
def list_guesses(team_id):
    guesses = Guess.query.filter(Guess.team_id == team_id).all()

    scores = dict()
    for guess in guesses:
        scores[guess.id] = dict()

    if len(guesses):
        for guess in guesses:
            for user in guess.users:
                scores[guess.id][user.tuser_id] = -0.25

            bots_found = Bot.query.filter(Bot.twitter_id.in_(scores[guess.id].keys()))

            if we_are_out_of_beta():
                for bot in bots_found:
                    scores[guess.id][bot.twitter_id] = 1

    formatter = GuessFormatter()
    return json.dumps(formatter.format(guesses, scores))

@app.route('/guess', methods=['PUT', 'POST'])
@timed('page.guess_make.render')
@make_json_response
@require_passcode
@track_pageview
def make_guess(team_id):
    if 'bots' in flask.request.values:
        bot_guesses = flask.request.values.getlist('bots')

    if 'bots' not in flask.request.values or not len(bot_guesses):
        return flask.make_response('', 400)

    guess = Guess(team_id=team_id, timestamp=time.time(), beta=(not we_are_out_of_beta()))
    database.db.session.add(guess)
    database.db.session.commit()

    for bot in bot_guesses:
        guess_user = GuessUser(guess_id=guess.id, tuser_id=bot)
        database.db.session.add(guess_user)

    database.db.session.commit()

    bots_found = Bot.query.filter(Bot.twitter_id.in_(bot_guesses))
    scores = dict()

    for twitter_id in bot_guesses:
        scores[twitter_id] = -0.25

    if we_are_out_of_beta():
        for bot in bots_found:
            scores[bot.twitter_id] = 1

    guess = Guess.query.filter(Guess.id == guess.id).first()

    formatter = GuessFormatter()
    return json.dumps(formatter.format(guess, scores))

syslog = SysLogHandler('/dev/log', SysLogHandler.LOG_DAEMON, socket.SOCK_STREAM)
syslog.setLevel(logging.DEBUG)
app.logger.addHandler(syslog)

if __name__ == "__main__":
    app.debug = True
    app.logger.addHandler(StreamHandler(sys.stdout))
    app.run(host='0.0.0.0')
