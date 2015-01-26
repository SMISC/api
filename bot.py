from database import db

class Bot(db.Model):
    __tablename__ = "bot"

    id          = db.Column(db.Integer(), primary_key=True)
    bot_id      = db.Column(db.String(32))
