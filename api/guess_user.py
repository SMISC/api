from database import db

class GuessUser(db.Model):
    __tablename__ = "guess_users"

    id        = db.Column(db.Integer(), primary_key=True)
    guess_id  = db.Column(db.Integer(), db.ForeignKey('guess.id'))
    tuser_id  = db.Column(db.Integer())
