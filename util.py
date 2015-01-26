import time
import json
import flask

from functools import wraps

TIME_DETECTION_START = 1422950400       # Tuesday, Feb 3, 2015 at Midnight PDT
# TIME_BETA_START = 1422259200           # Jan 26, 2015 at Midnight PDT
TIME_BETA_START = 1422172800            # Jan 25, 2015 at Midnight PDT
TIME_COMPETITION_START = 1420704000     # Monday, Jan 8, 2015 at Midnight PDT
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

        kwargs['cursor_size'] = cursor_size
        kwargs['offset'] = offset

        response = f(*args, **kwargs)

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
        if response is None or isinstance(response, list) and len(response) == 0:
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
