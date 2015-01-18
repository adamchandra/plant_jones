# #!/usr/bin/env python
import asyncore
import csv
import socket
import threading
import time
import random

from twython import Twython, TwythonError
from twython import TwythonStreamer
from sentiment_analysis.sentiment_analysis_model import load_serial, create_vectors


# post a tweet to @plant_jones
def send_tweet(tweet_str):
    twitter = Twython(keys['apiKey'], keys['apiSecret'], keys['accessToken'], keys['accessTokenSecret'])
    twitter.update_status(status=tweet_str)
    print "Tweeted: " + tweet_str


def respond_to_mentions():
    # keep track of the last response id so we know where we left off
    with open('.last_response', 'r') as response_file:
        last_response_id = response_file.readline()[:-1]
    new_response_id = False

    twitter = Twython(keys['apiKey'], keys['apiSecret'], keys['accessToken'], keys['accessTokenSecret'])
    mentions = twitter.get_mentions_timeline(
        since_id=last_response_id) if last_response_id else twitter.get_mentions_timeline()
    if mentions:
        for mention in mentions:
            who = mention['user']['screen_name']
            mention_id_string = mention['id_str']
            mention_text = mention['text']
            response_count = user_response_counts[who] if who in user_response_counts.keys() else 0
            print who, mention_id_string, mention_text

            # save the newest message id so we can start at that point next time
            if not new_response_id:
                new_response_id = True
                with open('.last_response', 'w') as response_file:
                    response_file.write(str(mention_id_string) + "\n")
            try:
                # respond to first mention, or second mention if it contains a '?'
                if response_count is 0 or (response_count is 1 and '?' in mention_text):
                    # choose correct response and append 3 random emojis
                    message = u'@' + who + responses[response_count] + \
                              u''.join([emoji_dict[random.choice(emoji_dict.keys())] for i in range(3)])
                    print 'Responding to ' + who + ' with message : ' + message
                    twitter.update_status(status=message, in_reply_to_status_id=mention_id_string)
                    user_response_counts[who] = response_count + 1

            except:
                pass

    # file keeping track of how many responses each user has gotten
    with open(".responded_users", 'w') as responded_user_file:
        responded_user_file.writelines(
            [user + ',' + str(count) + '\n' for (user, count) in user_response_counts.iteritems()])


# grab a random tweet
def random_tweet_from_stream(sentiment_code):
    # initialize stream using secret keys
    stream = MyStreamer(keys['apiKey'], keys['apiSecret'], keys['accessToken'], keys['accessTokenSecret'])
    stream.target_sentiment = "\"" + ('positive' if sentiment_code == "1" else 'negative') + "\""
    print("Looking for tweets with " + stream.target_sentiment + " sentiment")
    # we only want english tweets that contain the word water
    stream.statuses.filter(track='water', language='en')


# class to handle streaming random tweets
class MyStreamer(TwythonStreamer):
    target_sentiment = '\"negative\"'

    def on_success(self, data):
        try:
            if 'text' in data:
                ascii_tweet = data['text']
                utf_tweet = ascii_tweet.encode('utf-8')
                vectors = create_vectors(
                    [utf_tweet], word_vectorizer, char_vectorizer, lexicons)
                # estimate the sentiment of the tweet
                tweet_sentiment = str(model.predict(vectors)[0])
                if tweet_sentiment == self.target_sentiment:
                    if True not in [w in filter_set for w in utf_tweet.split(' ')]:
                        print (utf_tweet + '\t' + tweet_sentiment + '\n')
                        send_tweet(utf_tweet)
                        # Want to disconnect after the first result?
                        self.disconnect()
        except:
            pass

    def on_error(self, status_code, data):
        print status_code, data


# message handle for the twitter server
class MessageHandler(asyncore.dispatcher_with_send):
    def handle_read(self):
        data = self.recv(8192)
        if data:
            print data
            random_tweet_from_stream(data)


# socket server
class TwitterServer(asyncore.dispatcher):
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)
        # run this in its own thread so socket is not blocking
        loop_thread = threading.Thread(target=asyncore.loop, name="Socket Server Loop")
        loop_thread.start()

    def handle_close(self):
        self.close()

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            print 'Incoming connection from %s' % repr(addr)
            handler = MessageHandler(sock)


# main loop running the server
def mention_check_loop():
    while True:
        print "Checking for mentions"
        respond_to_mentions()
        # only check mentions after delay random between [30 min, 1 hour]
        time.sleep(random.randrange(1800, 3600))


####### initializing things ########

## read in secret keys -> create a csv with your twitter secret keys
with open(".secret_keys", 'r') as f:
    keys = {key: value for (key, value) in csv.reader(f, delimiter=',')}

## filter offensive words so plant jones isn't a racist
with open(".filter_words", 'r') as f:
    filter_set = set([word[:-1] for word in f])

## read in user response counts so we dont spam people
with open(".responded_users", 'r') as f:
    user_response_counts = {key: int(value) for (key, value) in csv.reader(f, delimiter=',')}

## dict of emojis plant jones randomly responds with, need to pad utf with zeroes
emoji_dict = {'droplet': u'\U0001F4A7', 'sprout': u'\U0001F331', 'splash': u'\U0001F4A6', 'sep': u'\U0001F4AA',
              'pute': u'\U0001F4BB',
              'palmtree': u'\U0001F334', 'cactus': u'\U0001F335', 'witness': u'\U0001F64C', 'sunwater': u'\U0001F305'}

## responses if people reply to plant_jones
responses = [u" Hi! I'm an artificially intelligent plant. "
             u"I send negative tweets about water when I'm thirsty and positive ones when I'm not.",
             u" I'm a plant, remember to drink your water."]

## sentiment analysis model
model, char_vectorizer, word_vectorizer, lexicons = load_serial()

## start the server
server = TwitterServer('localhost', 6969)
mention_check_loop()