from database import db

class Target(db.Model):
    __tablename__ = "targets"

    twitter_id  = db.Column(db.String(32), primary_key=True)
