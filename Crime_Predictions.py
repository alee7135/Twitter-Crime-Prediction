
# coding: utf-8

import pandas as pd
import json
import matplotlib.pyplot as plt
import time
import tweepy
import re
import operator
import string
import emoji
import time
import jsonpickle
import stateplane
from datetime import datetime
from dateutil import tz
from collections import Counter, defaultdict
from nltk.tokenize import word_tokenize
from nltk.tokenize import TweetTokenizer
from nltk.corpus import stopwords
from nltk import bigrams
from tweepy import OAuthHandler
from tweepy import Stream
from tweepy.streaming import StreamListener
get_ipython().magic(u'matplotlib inline')



# Read in json file with stored api keys stored on local drive
def load_apikeys(filepath):
    '''
    Input: filepath where your personal twitter keys are stored
    Output: keys dictionary
    '''
    with open(filepath) as key_file:
        keys = json.load(key_file)
    return keys
keys = load_apikeys('../twitter_keys.json')


## Streaming API

# Create the oauth accessors
auth = OAuthHandler(keys['consumer_key'], keys['consumer_secret']) # only gives 180 requests
auth.set_access_token(keys['access_token'], keys['access_secret'])

# create a basic listener that encapsulates StreamListener object; that just prints received tweets to text file
class Streamgetter(StreamListener):
    def __init__(self):
        self.counter = 0
        self.error = 0
    def on_data(self, data):
        '''
        Input: live streaming data from Twitter API
        Output: N/A
        '''
        try:
            file = open("data/stream.txt", 'a')
            file.write(data)
            file.close()
            self.counter += 1
            print "Downloaded: %d tweets" %(self.counter)
            return True
        except Exception as e:
            print 'failed ondata,', str(e)
            time.sleep(5)
            pass
    def on_error(self, status):
        '''
        Input: status direct from Twitter API
        Output: N/A
        '''
        self.error += 1
        print 'ALERT: Error Count: ', self.error
        if status == 420:
            print 'status: Rate Limited ', status
            time.sleep(self.error * 60000)
        else:
            print 'status: other HTTP error ', status
            time.sleep(10000)
        return False
# dir(StreamListener)

# Initialize the stream listener
listener = Streamgetter()
stream = Stream(auth, listener)

# begin capturing Twitter Streams by keywords but in this case, I left track blank
print "Downloading tweets with Streaming API... "
stream.filter(stall_warnings=True, locations=[-118.9448, 32.8007, -117.6462, 34.8233])



# In order to build features, we need to create good tokens
emojis_str = emoji.get_emoji_regexp().pattern[1:-1] # store all emoji regular expressions

# build regex string for each type of entity, I could have also used the entities field in the json file
regex_str = [
    emojis_str,
    r'<[^>]+>', # HTML tags
    r'(?:@[\w_]+)', # @-mentions
    r"(?:\#+[\w_]+[\w\'_\-]*[\w_]+)", # hash-tags
    r'http[s]?://(?:[a-z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-f][0-9a-f]))+', # URLs

    r'(?:(?:\d+,?)+(?:\.?\d+)?)', # numbers
    r"(?:[a-z][a-z'\-_]+[a-z])", # words with - and '
    r'(?:[\w_]+)', # other words
    r'(?:\S)' # anything else
]

# recompile the regexp
tokens_re = re.compile(r'('+'|'.join(regex_str)+')', re.VERBOSE | re.IGNORECASE)
emoticon_re = re.compile(r'^'+emojis_str+'$', re.VERBOSE | re.IGNORECASE)



# Create some stopwords because they are unlikely very informative
punctuation = list(string.punctuation)
mystopwords = stopwords.words('english') + punctuation

def mytokenizer(s):
    '''
    Input: Tweet text
    Output: list of tokens or words
    '''
    # find all the matching tokens according to our set of twitter elements
    tokens = tokens_re.findall(s)
    # lets standardize text by lowercasing for everything except emoticons
    tokens = [token if emoticon_re.search(token) else token.lower() for token in tokens]
    return [token for token in tokens if token not in mystopwords]


# class to help us build a coocurrance matrix
class build_cooccurence(object):
    def __init__(self):
        self.cooccurence = defaultdict(lambda:defaultdict(int))
    def update_cooccurence(self, terms):
        '''
        Input: list of tokens
        Output: N/A
        '''
        for i in xrange(len(terms)-1): # we want to leave subtract last index so we can compare later
            for j in xrange(i+1,len(terms)):
                w1, w2 = sorted([terms[i], terms[j]]) # must sort or else we will have duplicates AB, BA
                if w1 != w2:
                    self.cooccurence[w1][w2] += 1
    def max_cooccurence(self, top):
        '''
        Input: number of top n occurences to reveal
        Output: list of top n occurences
        '''
        cooccurence_max = []
        for w1 in self.cooccurence: # for each key
            for w2 in self.cooccurence[w1]:
                cooccurence_max.append( ((w1, w2), self.cooccurence[w1][w2]))
        terms_max = sorted(cooccurence_max, key=operator.itemgetter(1), reverse=True)[:top]
        return terms_max


# store tweets in a variable
def save_tweets(filepath):
    tweets = []
    '''
    Input: filepath where the stream tweet data exists
    Output: N/A
    '''
    tweets_file = open(filepath, "r")
    for line in tweets_file:
        tweet = json.loads(line)
        # filter only geotagged tweets
        if tweet['coordinates']:
            tweets.append(json.loads(line))
    return tweets
tweets = save_tweets('data/stream.txt')
print tweets[0]


## Explore the what the top tweets are about
tstart = time.time()
tweets_data_path = 'data/stream.txt'
tweets_file = open(tweets_data_path, "r")

# initialize counter for the tweet texts
count_all = Counter()
count_hash = Counter()
count_mentions = Counter()
count_nothashmention = Counter()
count_bigrams = Counter()
bc = build_cooccurence()

for line in tweets_file:
    # loads takes a single line in the file and converts it into a dictionary
    tweet = json.loads(line)
    # create a list of tokens for each new tweet with our tokenizer function
    terms_all = [term for term in mytokenizer(tweet['text'])]
    # hash-tages only
    terms_hash = [term for term in mytokenizer(tweet['text']) if term.startswith('#')]
    # @ mentions
    terms_mentions = [term for term in mytokenizer(tweet['text']) if term.startswith('@')]
    # words
    terms_nothashmention = [term for term in mytokenizer(tweet['text']) if not term.startswith(('@','#'))]
    # bigrams
    terms_bigrams = bigrams(terms_nothashmention)

    # update the counter dictionary
    count_all.update(terms_all)
    count_hash.update(terms_hash)
    count_mentions.update(terms_mentions)
    count_nothashmention.update(terms_nothashmention)
    count_bigrams.update(terms_bigrams)
    bc.update_cooccurence(terms_nothashmention) # co-occurrence
#     bc.max_cooccurence(5)

tweets_file.close()
tend = time.time()
print "Took seconds: ", tend - tstart


# Lets see some results
print count_all.most_common(10)
print count_hash.most_common(10)
print count_mentions.most_common(10)
print count_nothashmention.most_common(10)
print count_bigrams.most_common(10)
print bc.max_cooccurence(4)


def convert_date_time(date):
    '''
    Input: Twitter UTC datetime
    Output: Local datetime
    '''
    from_zone = tz.gettz('UTC')
    to_zone = tz.gettz('America/Los_Angeles')
    utc = datetime.strptime(date,'%a %b %d %H:%M:%S +0000 %Y')
    utc = utc.replace(tzinfo=from_zone)
    # Convert time zone
    pacific = utc.astimezone(to_zone)
    return datetime.strftime(pacific, '%Y-%m-%d %H:%M:%S')


# Check the date pull range
create_at = map(lambda x: convert_date_time(x[u'created_at']), tweets)
print 'first tweet pulled: ', min(create_at)
print 'last tweet pulled: ', max(create_at)


## REST API

auth = tweepy.AppAuthHandler(keys['consumer_key'], keys['consumer_secret']) # 450 requests
# Officially authorize api connection: api variable is now the entry point for most operations with Twitter
api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)


# set parameters for the REST API search
tweetsPerQuery = 100
geocode = "34.0522,-118.2437,50mi"
until = u'2016-05-01'
max_id = 726941826570051584 # int(sorted(map(lambda x: x[u'id_str'], tweets))[0])
result_type = 'recent'


def search_tweets(filepath, tweetsPerQuery, geocode, until, max_id, result_type):
    '''
    Input: filepath to store the search data
    Output: N/A
    '''
    tweetCount = 0
    maxTweets = 1000000
    print "Downloading tweets with Search API... "
    tweets_search_path = filepath # 'data/search.txt'

    with open(tweets_search_path, "a") as tweets_file:
        while tweetCount < maxTweets:
            try:
                new_tweets = api.search(q='kobe', geocode=geocode, count=tweetsPerQuery,
                                        max_id=str(max_id-1), until=until, result_type=result_type)
                if not new_tweets:
                    print "No more tweets found"
                    break
                for tweet in new_tweets:
                    tweets_file.write(jsonpickle.encode(tweet._json, unpicklable=False)+'\n')
                    tweetCount += 1
                print "Downloaded %d tweets" %(tweetCount)
                max_id = new_tweets[-1].id
            except tweepy.TweepError as e:
                print "Error: " + str(e)
                break


search_tweets('data/search.txt', tweetsPerQuery, geocode, until, max_id, result_type)


search_tweets = save_tweets('data/search.txt')


# Combine REST + Stream Tweets
all_tweets = tweets + search_tweets


## Crime Data

crime_data = pd.read_csv("data/PART_I_AND_II_CRIMES.csv")

crime_data.head()
# x,y coordinates seem to be State Plane 5 meters
# need to project the Twitter data


tweet_coord = map(lambda x:
                   stateplane.from_lonlat(x['coordinates']['coordinates'][0],
                                          x['coordinates']['coordinates'][1],
                                          epsg='26945'), all_tweets) # state plane 5


# Tweet aggregation
