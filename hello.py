import time
import database
import json
import flask
import flask.json

from flask import Flask
from ConfigParser import ConfigParser
from tuser import tuser

config = ConfigParser()
config.read('configuration.ini')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@/pacsocial?host=%s' % (config.get('postgresql', 'username'), config.get('postgresql', 'password'), config.get('postgresql', 'socket'))
database.db.init_app(app)

TIME_DETECTION_START = 1422950400 # Tuesday, Feb 3, 2015 at Midnight PDT
# TIME_BETA_START = 1422259200 # Jan 26, 2015 at Midnight PDT
TIME_BETA_START = 1422172800 # Jan 25, 2015 at Midnight PDT
TIME_COMPETITION_START = 1420704000 # Monday, Jan 8, 2015 at Midnight PDT

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

@app.route('/user', methods=['GET'])
def list_all_users():
    users = tuser.query.filter(tuser.id > since_id).filter(tuser.timestamp < get_current_virtual_time()).order_by(tuser.id.desc()).limit(2).all()
    rv = []

    for user in users:
        rv.append({
            "id": user.id,
            "user_id": user.user_id,
            "screen_name": user.screen_name,
            "full_name": user.full_name,
            "bio": user.bio,
            "followers": user.followers,
            "total_tweets": user.total_tweets,
            "timestamp": None, # account creation time intentionally redacted
            "following": user.following,
            "location": user.location,
            "website": user.website,
            "profile_image_url": user.profile_image_url,
            "profile_banner_url": user.profile_banner_url,
            "protected": user.protected
        })
    
    return json.dumps(rv)

if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0')
