class Formatter:
    def format(self, what):
        if isinstance(what, list):
            return self.format_many(what)
        elif what is None:
            return []
        else:
            return self.format_one(what)

    def format_many(self, things):
        rv = []
        for thing in things:
            rv.append(self.format_one(thing))
        return rv

class UserFormatter(Formatter):
    def format_one(self, user):
        return {
            "id": user.id,
            "user_id": int(user.user_id),
            "screen_name": user.screen_name,
            "full_name": user.full_name,
            "bio": user.bio,
            "followers": int(user.followers),
            "total_tweets": int(user.total_tweets),
            "timestamp": None, # account creation time intentionally redacted
            "following": int(user.following),
            "location": user.location,
            "website": user.website,
            "profile_image_url": user.profile_image_url,
            "profile_banner_url": user.profile_banner_url,
            "protected": bool(user.protected)
        }

class TweetFormatter(Formatter):
    def format_one(self, tweet):
        return {
            "id": int(tweet.tweet_id),
            "user_id": int(tweet.user_id),
            "timestamp": int(tweet.timestamp),
            "text": tweet.text
        }

class GuessFormatter(Formatter):
    def format_one(self, guess):
        return {
            "guess_id": guess.id,
            "guesses": [],
            "scores": []
        }
