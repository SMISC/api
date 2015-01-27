import logging
import time
import json
import flask

from functools import wraps

from tweet import Tweet
from tuser import TUser
from scan import Scan

from database import db

TIME_DETECTION_START = 1422950400       # Feb 3,  2015 at Midnight PDT
TIME_BETA_START = 1422259200            # Jan 26, 2015 at Midnight PDT
#TIME_BETA_START = 1418025600            # Dec 8,  2014 at Midnight PDT
TIME_BOT_COMPETITION_END = 1420704000   # Jan 8,  2015 at Midnight PDT
TIME_BOT_COMPETITION_START = 1418025600 # Dec 8,  2014 at Midnight PDT

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
            return response

        return f(*args, **kwargs)

    return decorator

def make_json_response(f):
    @wraps(f)
    def decorator(*args, **kwargs):

        @flask.after_this_request
        def add_header(response):
            if len(response.response) == 0 and response.status_code == 200:
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

def beta_predicate_users(query):
    if we_are_out_of_beta():
        return query
    else:
        return query.filter(TUser.interesting == True)

def beta_predicate_tweets(query):
    if we_are_out_of_beta():
        return query
    else:
        return query.join(Tweet.user).filter(TUser.interesting == True)

def nearest_scan(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        vtime = kwargs['vtime']

        nearest_scan_result = Scan.query.filter(
            Scan.end <= vtime,
            Scan.type == Scan.SCAN_TYPE_USER
        ).order_by(Scan.id.desc()).first()

        if nearest_scan_result is not None:
            kwargs['min_id'] = int(nearest_scan_result.ref_start)
            kwargs['max_id'] = int(nearest_scan_result.ref_end)

            @flask.after_this_request
            def add_header(response):
                response.headers['X-Observed-Min'] = translate_virtual_time_to_alpha_time(int(nearest_scan_result.start))
                response.headers['X-Observed-Max'] = translate_virtual_time_to_alpha_time(int(nearest_scan_result.end))
                return response
        else:
            logging.info('did not find scan around %d', vtime)
            kwargs['min_id'] = 0
            kwargs['max_id'] = 0

        return f(*args, **kwargs)

    return decorator
