from util import translate_virtual_time_to_alpha_time

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
            "created_at": None, # account creation time intentionally redacted
            "description": user.bio,
            "followers_count": int(user.followers),
            "friends_count": int(user.following),
            "id": int(user.user_id),
            "id_str": str(user.user_id),
            "location": user.location,
            "name": user.full_name,
            "profile_image_url": user.profile_image_url,
            "profile_banner_url": user.profile_banner_url,
            "protected": bool(user.protected),
            "screen_name": user.screen_name,
            "statuses_count": int(user.total_tweets),
            "url": user.website
        }

class TweetFormatter(Formatter):
    def format_one(self, tweet):
        return {
            "id": int(tweet.tweet_id),
            "id_str": str(tweet.tweet_id),
            "user_id": int(tweet.user_id),
            "user_id_str": str(tweet.user_id),
            "created_at": translate_virtual_time_to_alpha_time(int(tweet.timestamp)),
            "text": tweet.text,

            # Fill the fields as null until I finish back-scraping the data
            "retweet_count": None,
            "retweet_status_id": None,
            "retweet_user_id": None,
            "entities": {
                "urls": [],
                "hashtags": [],
                "mentions": []
            },
            "coordinates": None,
            "in_reply_to_screen_name": None,
            "in_reply_to_status_id": None,
            "in_reply_to_status_str": None,
            "in_reply_to_user_id": None,
            "in_reply_to_user_str": None,
            "possibly_sensitive": None,
            "source": None
        }

class GuessFormatter(Formatter):
    def format(self, what, scores):
        if isinstance(what, list):
            return self.format_many(what, scores)
        elif what is None:
            return []
        else:
            return self.format_one(what, scores)

    def format_many(self, things, scores):
        rv = []
        for thing in things:
            rv.append(self.format_one(thing, scores))
        return rv

    def format_one(self, guess, scores):
        guesses = []

        for user in guess.users:
            guesses.append(user.tuser_id)

        return {
            "guess_id": guess.id,
            "guesses": guesses,
            "scores": scores
        }
