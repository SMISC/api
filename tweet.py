from database import db

class Tweet(db.Model):
    __tablename__ = "tweet"

    id          = db.Column(db.Integer(), primary_key=True)
    tweet_id    = db.Column(db.Integer())
    user_id     = db.Column(db.String(32), db.ForeignKey('tuser.user_id'))
    timestamp   = db.Column(db.Integer())
    text        = db.Column(db.String(256))

    user        = db.relationship('TUser')
    entities    = db.relationship('TweetEntity', lazy='joined')
