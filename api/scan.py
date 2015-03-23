from database import db

class Scan(db.Model):
    SCAN_TYPE_USER = 'info'
    SCAN_TYPE_FOLLOWERS = 'followers_wide'

    __tablename__ = "scan"

    id                  = db.Column(db.Integer(), primary_key=True)
    type                = db.Column(db.String(50))
    start               = db.Column(db.Integer())
    end                 = db.Column(db.Integer())
    ref_start           = db.Column(db.String(32))
    ref_end             = db.Column(db.String(32))
