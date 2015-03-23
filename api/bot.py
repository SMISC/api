from database import db

class Bot(db.Model):
    __tablename__ = "team_bot"

    team_id     = db.Column(db.Integer())
    twitter_id  = db.Column(db.String(32), primary_key=True) # not really a primary key but ok
    screen_name = db.Column(db.String(32))
    type        = db.Column(db.Integer())
    kill_date   = db.Column(db.Integer())
