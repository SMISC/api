from database import db

class DetectionTeam(db.Model):
    __tablename__ = "detection_team"

    id       = db.Column(db.Integer(), primary_key=True)
    name     = db.Column(db.String(32))
    password = db.Column(db.String(32))
