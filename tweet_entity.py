from database import db

class TweetEntity(db.Model):
    __tablename__ = "tweet_entity"

    id          = db.Column(db.Integer(), primary_key=True)
    tweet_id    = db.Column(db.Integer(), db.ForeignKey('tweet.tweet_id'))
    type        = db.Column(db.String(20))
    text        = db.Column(db.Text())
