from statsd import statsd

import logging
import time
import json
import flask

from functools import wraps

from tweet import Tweet
from tuser import TUser
from scan import Scan
from tuser import TwitterUser

from database import db

TIME_DETECTION_START = 1424149200       # Feb 17, 2015 at Midnight EST
TIME_BETA_START = 1422230400            # Jan 26, 2015 at Midnight UTC
#TIME_BETA_START = 1417996800           # Dec 8,  2014 at Midnight UTC
TIME_BOT_COMPETITION_START = 1417996800 # Dec 8,  2014 at Midnight UTC
TIME_BOT_COMPETITION_END = 1420675200   # Jan 8,  2015 at Midnight UTC

GENEROUS_CURSOR_UPPER_BOUND = 15000
DEFAULT_CURSOR_SIZE = 500

def get_time_anchor():
    now = time.time()

    if we_are_out_of_beta():
        return TIME_DETECTION_START
    else:
        return TIME_BETA_START

def we_are_out_of_beta():
    return (time.time() >= TIME_DETECTION_START)

def translate_alpha_time_to_virtual_time(alpha_time):
    return alpha_time - (get_time_anchor() - TIME_BOT_COMPETITION_START)

def translate_virtual_time_to_alpha_time(virtual_time):
    return virtual_time + (get_time_anchor() - TIME_BOT_COMPETITION_START)

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

        return f(*args, **kwargs)

    return decorator

def cursor(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        cursor = None

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

        kwargs['cursor_size'] = cursor_size
        kwargs['offset'] = offset

        @flask.after_this_request
        def add_header(response):
            if offset > 0:
                prev_cursor = str(offset - cursor_size) + '-' + str(cursor_size)
                response.headers['X-Cursor-Previous'] = prev_cursor

            response.headers['X-Cursor-Next'] = next_cursor

            if cursor is not None:
                response.headers['X-Cursor-Current'] = cursor

            return response

        return f(*args, **kwargs)

    return decorator

def make_json_response(f):
    @wraps(f)
    def decorator(*args, **kwargs):

        @flask.after_this_request
        def add_header(response):
            if (len(response.response) == 0 or response.response[0] == '[]') and response.status_code == 200:
                response.status_code = 204

            response.headers['Content-Type'] = 'application/json'
            return response

        return f(*args, **kwargs)
    return decorator

def not_implemented(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        return flask.make_response('', 501)

    return decorator

def temporal(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if kwargs['vtime'] is None:
            kwargs['vtime'] = time.time()
        
        # Prevent someone from grabbing things before the social competition began, or the current virtual competition time.
        # It has to be at least the start of the bot competition,
        # It has to be at most the current time in the detection competition
        kwargs['vtime'] = max(TIME_BOT_COMPETITION_START, min(get_current_virtual_time(), translate_alpha_time_to_virtual_time(int(kwargs['vtime']))))

        return f(*args, **kwargs)
            
    return decorator

def disabled_beta(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        if not we_are_out_of_beta():
            return flask.make_response('', 429)
    return decorator

def beta_predicate_observations(query):
    return query.filter(TUser.interesting == (not we_are_out_of_beta()))

def beta_predicate_users(query):
    return query.filter(TwitterUser.beta == (not we_are_out_of_beta()))

def beta_predicate_tweets(query):
    interesting_users_query = db.session.query(TwitterUser.twitter_id).filter(TwitterUser.beta == (not we_are_out_of_beta())).subquery()
    return query.filter(Tweet.user_id.in_(interesting_users_query))

def nearest_scan(scan_type):
    def deco(f):
        @wraps(f)
        def decorator(*args, **kwargs):
            vtime = kwargs['vtime']

            nearest_scan_result = Scan.query.filter(
                Scan.end <= vtime,
                Scan.type == scan_type
            ).order_by(Scan.id.desc()).first()

            if nearest_scan_result is not None:
                if nearest_scan_result.ref_start is not None:
                    kwargs['min_scan_id'] = int(nearest_scan_result.ref_start)
                else:
                    kwargs['min_scan_id'] = None

                if nearest_scan_result.ref_end is not None:
                    kwargs['max_scan_id'] = int(nearest_scan_result.ref_end)
                else:
                    kwargs['max_scan_id'] = None

                @flask.after_this_request
                def add_header(response):
                    response.headers['X-Observed-Min'] = int(nearest_scan_result.start)
                    response.headers['X-Observed-Max'] = int(nearest_scan_result.end)
                    return response
            else:
                logging.info('did not find scan around %d', vtime)
                kwargs['min_scan_id'] = 0
                kwargs['max_scan_id'] = 0

            return f(*args, **kwargs)

        return decorator
    return deco

def get_tags():
    tags = ['env:' + flask.request.remote_addr]

    if 'REMOTE_ADDR' in flask.request.environ:
        ip = flask.request.environ['REMOTE_ADDR']
        tags.append('ip:' + ip)

    return tags

def timed(metric):
    def deco(f):
        @wraps(f)
        def decorator(*args, **kwargs):
            start = time.time()
            result = f(*args, **kwargs)
            statsd.timing(metric, time.time() - start, tags=get_tags(), sample_rate=1)
            return result
        return decorator
    return deco

def track_pageview(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        statsd.increment('page', tags=get_tags())
        return f(*args, **kwargs)
            
    return decorator
