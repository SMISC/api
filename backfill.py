import sys
import database
import logging
import time

from flask import Flask
from ConfigParser import ConfigParser
from tweet import Tweet
from twitter import twitter_from_credentials

config = ConfigParser()
config.read('configuration.ini')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%s:%s@/pacsocial?host=%s' % (config.get('postgresql', 'username'), config.get('postgresql', 'password'), config.get('postgresql', 'socket'))
app.config['SQLALCHEMY_ECHO'] = True
database.db.init_app(app)

class TwitterMultiplexer:
    def __init__(self, apis):
        self.apis = apis

    def request(self, resource, params=None):
        for i in range(len(self.apis)):
            response = self.apis[i].request(resource, params)
            if response.status_code != 429:
                return response

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
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

    start_tweet = 539573958715400193
    tweet_page = 0
    tweets_per_page = 100
    tweet_offset = int(sys.argv[1])

    with app.app_context():
        while True:
            tweets = Tweet.query.filter(Tweet.tweet_id > start_tweet, Tweet.tweet_id % 5 == tweet_offset).order_by(Tweet.tweet_id.asc()).offset(tweet_page*tweets_per_page).limit(tweets_per_page).all()
            if len(tweets) == 0:
                break

            tweet_ids = []
            for tweet in tweets:
                tweet_ids.append(str(tweet.tweet_id))

            logging.info(str(tweet_ids))

            response = multi.request('statuses/lookup', {'id': ','.join(tweet_ids)})

            if response and response.status_code == 200:
                twitter_tweets = response.json
                for tweet in twitter_tweets:
                    retweet_user_id = None
                    retweet_status_id = None

                    if 'retweeted_status' in tweet:
                        retweet_user_id = tweet['retweeted_status']['user']['id']
                        retweet_status_id = tweet['retweeted_status']['id']

                    coordinates = None

                    if 'coordinates' in tweet:
                        coordinates = str(tweet['coordinates'])

                    Tweet.query.filter(Tweet.tweet_id == tweet['id']).update({
                        Tweet.is_retweet: 'retweeted_status' in tweet,
                        Tweet.retweet_user_id: retweet_user_id,
                        Tweet.retweet_status_id: retweet_status_id,
                        Tweet.retweet_count_frozen: tweet['retweet_count'],
                        Tweet.source: tweet['source'],
                        Tweet.in_reply_to_user_id: tweet['in_reply_to_user_id'],
                        Tweet.in_reply_to_status_id: tweet['in_reply_to_status_id'],
                        Tweet.in_reply_to_screen_name: tweet['in_reply_to_screen_name'],
                        Tweet.coordinates: coordinates
                    })

            
                tweet_page += 1
                database.db.session.commit()
            elif response and response.status_code == 429:
                logging.info('over limits. sleeping...')
                time.sleep(10)
            else:
                logging.warn('error page %d (twitter response: %s)', tweet_page, str(response))
                time.sleep(10)
