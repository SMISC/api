from tweet_entity import TweetEntity
from tuser import TUser

from database import db

class Tweet(db.Model):
    __tablename__ = "tweet"

    id                      = db.Column(db.Integer(), primary_key=True)
    tweet_id                = db.Column(db.Integer())
    user_id                 = db.Column(db.String(32), db.ForeignKey('tuser.user_id'))
    timestamp               = db.Column(db.Integer())
    text                    = db.Column(db.String(256))
    in_reply_to_screen_name = db.Column(db.Text())
    in_reply_to_status_id   = db.Column(db.Integer())
    in_reply_to_user_id     = db.Column(db.Integer())
    source                  = db.Column(db.Text())
    is_retweet              = db.Column(db.Boolean())
    retweet_user_id         = db.Column(db.Integer())
    retweet_status_id       = db.Column(db.Integer())
    retweet_count_frozen    = db.Column(db.Integer())
    coordinates             = db.Column(db.Text())
    favorites_count         = db.Column(db.Integer())

    user                    = db.relationship('TUser')
    entities                = db.relationship('TweetEntity', lazy='joined')
