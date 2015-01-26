import time
import database
import json
import flask
import logging
import flask.json

from flask import Flask
from ConfigParser import ConfigParser
from functools import wraps

from formatter import UserFormatter, TweetFormatter
from search import Search

from tuser import tuser
from tweet import tweet

config = ConfigParser()
config.read('configuration.ini')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@/pacsocial?host=%s' % (config.get('postgresql', 'username'), config.get('postgresql', 'password'), config.get('postgresql', 'socket'))
database.db.init_app(app)

TIME_DETECTION_START = 1422950400 # Tuesday, Feb 3, 2015 at Midnight PDT
# TIME_BETA_START = 1422259200 # Jan 26, 2015 at Midnight PDT
TIME_BETA_START = 1422172800 # Jan 25, 2015 at Midnight PDT
TIME_COMPETITION_START = 1420704000 # Monday, Jan 8, 2015 at Midnight PDT
GENEROUS_CURSOR_UPPER_BOUND = 15000
DEFAULT_CURSOR_SIZE = 2

def get_time_anchor():
    now = time.time()

    if now >= TIME_DETECTION_START:
        return TIME_DETECTION_START
    else:
        return TIME_BETA_START

def translate_alpha_time_to_virtual_time(wall_time):
    return wall_time - (get_time_anchor() - TIME_COMPETITION_START)

def translate_virtual_time_to_alpha_time(virtual_time):
    return virtual_time + (get_time_anchor() - TIME_COMPETITION_START)

def get_current_virtual_time():
    return translate_alpha_time_to_virtual_time(time.time())

def timeline(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if 'X-Since-ID' in flask.request.headers:
            since_id = int(flask.request.headers['X-Since-ID'])
        else:
            since_id = 0

        if 'X-Max-ID' in flask.request.headers:
            max_id = int(flask.request.headers['X-Max-ID'])
        else:
            max_id = float('inf')

        if 'X-Since-Count' in flask.request.headers:
            since_size = min(GENEROUS_CURSOR_UPPER_BOUND, int(flask.request.headers['X-Since-Count']))
        else:
            since_size = DEFAULT_CURSOR_SIZE

        kwargs['since_id'] = since_id
        kwargs['since_count'] = since_size
        kwargs['max_id'] = max_id

        return flask.make_response(f(*args, **kwargs))

    return decorator

def cursor(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if 'X-Cursor' in flask.request.headers:
            cursor = flask.request.headers['X-Cursor']
            (offset, cursor_size) = cursor.split('-')
            offset = int(offset)
            cursor_size = int(cursor_size)

        elif 'X-Cursor-Size' in flask.request.headers:
            cursor_size = min(GENEROUS_CURSOR_UPPER_BOUND, int(flask.request.headers['X-Cursor-Size']))
            offset = 0
        else:
            cursor_size = DEFAULT_CURSOR_SIZE
            offset = 0

        next_cursor = str(offset + cursor_size) + '-' + str(cursor_size)

        response = f(cursor_size, offset, *args, **kwargs)

        if offset > 0:
            prev_cursor = str(offset - cursor_size) + '-' + str(cursor_size)
            response.headers['X-Cursor-Previous'] = prev_cursor

        response.headers['X-Cursor-Next'] = next_cursor

        return response

    return decorator

def make_json_response(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        response = f(*args, **kwargs)
        flask_response = flask.make_response(json.dumps(response))
        if isinstance(response, list) and len(response) == 0:
            flask_response.status_code = 204
        return flask_response
    return decorator

def not_implemented(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        return flask.make_response('', 501)

    return decorator

def fill_temporal(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if kwargs['time'] is None:
            kwargs['time'] = time.time()
        return f(*args, **kwargs)
            
    return decorator

def translate_time(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        kwargs['time'] = translate_alpha_time_to_virtual_time(int(kwargs['time']))
        return f(*args, **kwargs)
            
    return decorator

@app.route('/edges/near/<time>/followers/<user_id>', methods=['GET'])
@not_implemented
@make_json_response
def timeless_list_followers():
    pass

@app.route('/edges/explore/<time>/<from_user>/to/<to_user>', methods=['GET'])
@not_implemented
@make_json_response
def timeless_explore_edges():
    pass

@app.route('/user/near/<time>', methods=['GET'])
@app.route('/user', methods=['GET'], defaults={'time': None})
@not_implemented
@fill_temporal
@translate_time
@make_json_response
def list_users(time):
    users = tuser.query.filter(tuser.timestamp <= time, tuser.timestamp < get_current_virtual_time()).order_by(tuser.id.desc()).limit(2).all()
    formatter = UserFormatter()
    return formatter.format(users)

@app.route('/user/near/<time>/<user_id>', methods=['GET'])
@app.route('/user/<user_id>', methods=['GET'], defaults={'time': None})
@fill_temporal
@translate_time
@make_json_response
def show_user(time, user_id):
    users = tuser.query.filter(tuser.user_id == user_id, tuser.timestamp < get_current_virtual_time()).order_by(tuser.id.desc()).limit(1).first()
    formatter = UserFormatter()
    return formatter.format(users)

@app.route('/user/near/<time>/<user_id>/tweets', methods=['GET'])
@app.route('/user/<user_id>/tweets', methods=['GET'], defaults={'time': None})
@fill_temporal
@translate_time
@timeline
@make_json_response
def list_tweets_by_user(time, max_id, since_id, since_count, user_id):
    logging.info('listing tweets ')
    tweets = tweet.query.filter(tweet.tweet_id > since_id, tweet.tweet_id <= max_id, tweet.timestamp <= time, tweet.timestamp < get_current_virtual_time(), tweet.user_id == user_id).order_by(tweet.timestamp.desc()).limit(since_count).all()
    formatter = TweetFormatter()
    return formatter.format(tweets)

@app.route('/tweets/near/<time>', methods=['GET'])
@app.route('/tweets', methods=['GET'], defaults={'time': None})
@fill_temporal
@translate_time
@timeline
@make_json_response
def list_tweets(time, max_id, since_id, since_count):
    tweets = tweet.query.filter(tweet.tweet_id > since_id, tweet.tweet_id <= max_id, tweet.timestamp <= time, tweet.timestamp < get_current_virtual_time()).order_by(tweet.timestamp.desc()).limit(since_count).all()
    formatter = TweetFormatter()
    return formatter.format(tweets)

@app.route('/search', methods=['GET', 'POST'])
@timeline
@not_implemented
@make_json_response
def search(max_id, since_id, since_count):
    tweets_query = tweet.query.filter(tweet.timestamp < get_current_virtual_time(), tweet.tweet_id > since_id, tweet.tweet_id <= max_id).order_by(tweet.timestamp.desc()).limit(since_count)
    search = Search(flask.request.values['q'])
    search.apply_filter(tweets_query)

    if 'users' in flask.request.values:
        tweet_query.filter(tweet.user_id.in_(flask.request.values['users']))
    tweets = tweets_query.all()

    formatter = TweetFormatter()
    return formatter.format(tweets)

if __name__ == "__main__":
    app.debug = True
    logging.getLogger().setLevel(logging.INFO)
    app.run(host='0.0.0.0')
