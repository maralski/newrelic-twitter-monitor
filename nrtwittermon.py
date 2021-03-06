import tweepy
import os
import sys
import yaml
import re
import atexit
import signal
import logging
from logging.config import fileConfig
from newrelic_telemetry_sdk import (
    LogClient, Harvester
)
from newrelic_telemetry_sdk.batch import LogBatch

PROVIDER = 'nrtwittermon'
DEFAULT_NEW_RELIC_HARVEST_INTERVAL = 5
DEFAULT_IGNORE_SENSITIVE_TWEETS = False
DEFAULT_RUN_SENTIMENT_ANALYSIS = True

class Twittermon(tweepy.StreamingClient):

    def __init__(self, bearer_token=None, nr_log_batch=None, rules=[],
                 ignore_sensitive=None,
                 sentiment_analysis=None):
        self.bearer_token = bearer_token
        super().__init__(bearer_token=self.bearer_token, wait_on_rate_limit=True)
        self.nr_log_batch = nr_log_batch
        self.sentiment_analysis = sentiment_analysis
        self.ignore_sensitive = ignore_sensitive

        if self.sentiment_analysis:
            logger.info('Sentiment analysis activated')
            from flair.models import TextClassifier
            from flair.data import Sentence
            self.classifier = TextClassifier.load('en-sentiment')
            self.sentence = Sentence
        else:
            logger.info('Sentiment analysis deactivated')

        self.update_rules(rules)

    def update_rules(self, rules):
        current_rules = self.get_rules()
        if current_rules.data != None:
            self.delete_rules([i.id for i in current_rules.data])
        tweet_rules = []
        for rule in rules:
            tag, value = rule.popitem()
            tweet_rules.append(tweepy.StreamRule(value=value, tag=tag))
    
        results = self.add_rules(tweet_rules, dry_run=False)

        logger.info("Rule update results")
        logger.info(results)

    def on_connect(self):
        logger.info("Connected to twitter API")

    def on_errors(self, error):
        logger.error("Received error from twitter API")
        logger.error(error)

    def on_response(self, resp):
        if len(resp.errors):
            logger.error(resp.errors)
            return

        if not isinstance(resp.data, tweepy.tweet.Tweet):
            logger.debug(f"Received instance of type {type(resp.data)}")
            return

        if not resp.data.text:
            logger.debug(f"No text received in tweet")
            return

        if not self.ignore_sensitive:
            if resp.data.possibly_sensitive == True:
                logger.debug(f"Ignoring sensitive tweet {resp.data.id}")
                return

        if self.sentiment_analysis:
            message = self.sentence(" ".join(re.sub("(@[A-Za-z0-9]+)|(^RT )|(https?://\S+)"," ", resp.data.text).split()))
            if message:
                self.classifier.predict(message)
                sentiment_label = message.labels[0].value
                sentiment_score = message.labels[0].score
            else:
                sentiment_label = "UNKNOWN"

            if sentiment_label == 'POSITIVE':
                face = '????'
                score = 0.5 + (0.5 * sentiment_score)
            elif sentiment_label == 'NEGATIVE':
                face = '????'
                score = 0.5 - (0.5 * sentiment_score)
            else:
                face = '????'
                score = 0.5

        for rule in resp.matching_rules:
            record_tweet = {
                'timestamp': int(resp.data.created_at.timestamp()*1000),
                'message': resp.data.text,
                'lang': resp.data.lang,
                'possibly_sensitive': resp.data.possibly_sensitive,
                'retweet_count': resp.data.public_metrics['retweet_count'],
                'reply_count': resp.data.public_metrics['reply_count'],
                'like_count': resp.data.public_metrics['like_count'],
                'quote_count': resp.data.public_metrics['quote_count'],
                'matching_rule': rule.tag,
                'provider': PROVIDER
            }
            if self.sentiment_analysis:
                record_tweet['sentiment'] = face
                record_tweet['score'] = round(score, 2)

            for user in resp.includes['users']:
                if user.id == resp.data.author_id:
                    record_tweet['name'] = user.name
                    record_tweet['username'] = user.username
                    record_tweet['url'] = f"https://twitter.com/{user.username}/status/{resp.data.id}"
                    break
        
            logger.debug(f"Sending tweet to New Relic {resp.data.id}")
            self.nr_log_batch.record(record_tweet)

def readconfig():
    logger.info(f"Reading configuration from {rules_filename}")
    with open(rules_filename) as f:
        rules = yaml.load(f, Loader=yaml.FullLoader)
    return rules
        
def rereadconfig(signalnum, frame):
    logger.info(f"Re-reading configuration from {rules_filename}")
    rules = readconfig()
    twitter.update_rules(rules)


if __name__ == '__main__':
    fileConfig('logging.ini')
    logger = logging.getLogger(PROVIDER)
    logger.info('Started')
    rules_filename = 'rules.yaml'

    try:
        from config import TWITTER_BEARER_TOKEN
    except ImportError:
        logger.error("TWITTER_BEARER_TOKEN should be defined in config module.")
        sys.exit(1)
    except ModuleNotFoundError:
        try:
            TWITTER_BEARER_TOKEN = os.environ['TWITTER_BEARER_TOKEN']
        except KeyError:
            logger.error("Environment variable for TWITTER_BEARER_TOKEN must be supplied.")
            sys.exit(1)

    try:
        from config import NEW_RELIC_INSERT_KEY
    except ImportError:
        logger.error("NEW_RELIC_INSERT_KEY should be defined in config module.")
        sys.exit(1)
    except ModuleNotFoundError:
        try:
            NEW_RELIC_INSERT_KEY = os.environ['NEW_RELIC_INSERT_KEY']
        except KeyError:
            logger.error("Environment variable for NEW_RELIC_INSERT_KEY must be supplied.")
            sys.exit(1)

    try:
        from config import NEW_RELIC_HARVEST_INTERVAL
    except:
        try:
            NEW_RELIC_HARVEST_INTERVAL = os.environ['NEW_RELIC_HARVEST_INTERVAL']
        except KeyError:
            NEW_RELIC_HARVEST_INTERVAL = DEFAULT_NEW_RELIC_HARVEST_INTERVAL

    try:
        from config import IGNORE_SENSITIVE_TWEETS
    except:
        try:
            IGNORE_SENSITIVE_TWEETS = os.environ['IGNORE_SENSITIVE_TWEETS']
        except KeyError:
            IGNORE_SENSITIVE_TWEETS = DEFAULT_IGNORE_SENSITIVE_TWEETS

    try:
        from config import RUN_SENTIMENT_ANALYSIS
    except:
        try:
            RUN_SENTIMENT_ANALYSIS = os.environ['RUN_SENTIMENT_ANALYSIS']
        except KeyError:
            RUN_SENTIMENT_ANALYSIS = DEFAULT_RUN_SENTIMENT_ANALYSIS

    nr_log_client = LogClient(NEW_RELIC_INSERT_KEY)
    nr_log_batch = LogBatch()

    harvester = Harvester(nr_log_client, nr_log_batch, harvest_interval=NEW_RELIC_HARVEST_INTERVAL)
    atexit.register(harvester.stop)
    harvester.start()
    rules = readconfig()

    twitter = Twittermon(bearer_token=TWITTER_BEARER_TOKEN, nr_log_batch=nr_log_batch, rules=rules,
                         ignore_sensitive=IGNORE_SENSITIVE_TWEETS, sentiment_analysis=RUN_SENTIMENT_ANALYSIS)

    signal.signal(signal.SIGHUP,rereadconfig)

    twitter.filter(
        tweet_fields = ['id', 'text', 'created_at', 'lang', 'possibly_sensitive', 'public_metrics'],
        expansions = ['author_id']
    )

    harvester.stop()