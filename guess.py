from database import db

class Guess(db.Model):
    __tablename__ = "guess"

    id          = db.Column(db.Integer(), primary_key=True)
    team_id     = db.Column(db.Integer())
    timestamp   = db.Column(db.Integer())
