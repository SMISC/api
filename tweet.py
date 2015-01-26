from database import db

class tweet(db.Model):
    __tablename__ = "tweet"

    id          = db.Column(db.Integer(), primary_key=True)
    tweet_id    = db.Column(db.Integer())
    user_id     = db.Column(db.String(32))
    timestamp   = db.Column(db.Integer())
    text        = db.Column(db.String(256))
