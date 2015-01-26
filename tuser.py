from database import db

class tuser(db.Model):
    __tablename__ = "tuser"

    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.String(32))
    screen_name = db.Column(db.String(32))
    full_name = db.Column(db.String(32))
    bio = db.Column(db.Text())
    followers = db.Column(db.Integer())
    total_tweets = db.Column(db.Integer())
    timestamp = db.Column(db.Integer())
    following = db.Column(db.Integer())
    interesting = db.Column(db.Binary())
    location = db.Column(db.Text())
    website = db.Column(db.Text())
    profile_image_url = db.Column(db.Text())
    profile_banner_url = db.Column(db.Text())
    protected = db.Column(db.Binary())
