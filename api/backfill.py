import sys
import database
import logging
import time

from flask import Flask
from ConfigParser import ConfigParser
from tweet import Tweet
from twitter import twitter_from_credentials

from sqlalchemy import and_

config = ConfigParser()
config.read('configuration.ini')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@/pacsocial?host=%s' % (config.get('postgresql', 'username'), config.get('postgresql', 'password'), config.get('postgresql', 'socket'))
app.config['SQLALCHEMY_ECHO'] = False
database.db.init_app(app)

class TwitterMultiplexer:
    def __init__(self, apis):
        self.apis = apis

    def request(self, resource, params=None):
        response = None
        for i in range(len(self.apis)):
            response = self.apis[i].request(resource, params)
            if response and response.status_code != 429:
                return response
        return response

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger('requests').setLevel(logging.WARN)
    keys = config.get('twitter', 'keys').split("\n")
    secrets = config.get('twitter', 'secrets').split("\n")
    apis = []

    for (key, secret) in zip(keys, secrets):
        try:
            api = twitter_from_credentials(key, secret)
        except Exception as e:
            logging.warn(str(e))
            continue
        apis.append(api)
        
    multi = TwitterMultiplexer(apis)

    start_tweet_id = 0
    tweet_id = start_tweet_id
    tweet_page = 0
    tweets_per_page = 100
    tweet_offset = int(sys.argv[2])
    tweet_modulus = int(sys.argv[1])
    flush_cycles = 10
    flush_cycle = 0
    tweets_updated = 0
    tweets_deleted = 0

    with app.app_context():
        while True:
            tweets = Tweet.query.filter(Tweet.favorites_count == None, Tweet.tweet_id > tweet_id, Tweet.tweet_id % tweet_modulus == tweet_offset).order_by(Tweet.tweet_id.asc()).limit(tweets_per_page).all()

            if len(tweets) == 0:
                break

            tweet_ids = []
            for tweet in tweets:
                tweet_ids.append(str(tweet.tweet_id))

            tweet_id = int(max(tweet_ids))
            max_tweet_id = int(max(tweet_ids))
            min_tweet_id = int(min(tweet_ids))

            response = multi.request('statuses/lookup', {'id': ','.join(tweet_ids), 'map': True})

            if response and response.status_code == 200:
                twitter_tweets = response.json
                for (tweet_id, tweet) in twitter_tweets['id'].items():
                    if tweet is None:
                        Tweet.query.filter(Tweet.tweet_id == tweet_id).update({
                            Tweet.deleted: True
                        }, synchronize_session=False)
                        tweets_deleted += 1
                    else:
                        retweet_user_id = None
                        retweet_status_id = None

                        if 'retweeted_status' in tweet:
                            retweet_user_id = tweet['retweeted_status']['user']['id']
                            retweet_status_id = tweet['retweeted_status']['id']

                        coordinates = None

                        if 'coordinates' in tweet:
                            coordinates = str(tweet['coordinates'])

                        favorites_count = None
                        if 'favorite_count' in tweet:
                            favorites_count = int(tweet['favorite_count'])

                        tweets_updated += 1
                        Tweet.query.filter(Tweet.tweet_id == tweet['id']).update({
                            Tweet.is_retweet: 'retweeted_status' in tweet,
                            Tweet.retweet_user_id: retweet_user_id,
                            Tweet.retweet_status_id: retweet_status_id,
                            Tweet.retweet_count_frozen: tweet['retweet_count'],
                            Tweet.source: tweet['source'],
                            Tweet.in_reply_to_user_id: tweet['in_reply_to_user_id'],
                            Tweet.in_reply_to_status_id: tweet['in_reply_to_status_id'],
                            Tweet.in_reply_to_screen_name: tweet['in_reply_to_screen_name'],
                            Tweet.favorites_count: favorites_count,
                            Tweet.coordinates: coordinates,
                            Tweet.deleted: False
                        }, synchronize_session=False)

                tweet_page += 1
                flush_cycle += 1

            if not response or response.status_code == 429 or flush_cycle >= flush_cycles:
                flush_cycle = 0
                logging.info('node %d flushing %d updates and %d deletions around %d', tweet_offset, tweets_updated, tweets_deleted, int(max(tweet_ids)))
                database.db.session.commit()
                tweets_updated = 0
                tweets_deleted = 0

            if response and response.status_code == 429:
                logging.info('over limits. sleeping around %d', int(max(tweet_ids)))
                time.sleep(10)
            elif not response or response.status_code != 200:
                logging.warn('error page %d (twitter response: %s) around %d', tweet_offset, str(response.headers) + str(response.json), int(max(tweet_ids)))
                time.sleep(10)



        database.db.session.commit()

