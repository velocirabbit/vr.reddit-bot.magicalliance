import time #Time module
import re #Regular expressions module
import os #Miscellaneous OS interface module
import urllib.request #Python URL/HTTP errors class

import nltk #Natural Language Toolkit
import praw #Python Reddit API Wrapper module
import numpy #Numerical Python
import boto #boto's Amazon S3 package
import boto.s3.connection

from config_bot import *
from nltk import word_tokenize
from pprint import pprint #pprint method from PrettyPrint module
from random import randint #to select a random "definition" of what a trick is
from boto.s3.key import Key #S3 Bucket Key object class

c = boto.s3.connect_to_region('us-east-1', calling_format = boto.s3.connection.OrdinaryCallingFormat())
bucket_name = 'vr.reddit-bot.magicalliance'
bucket = c.create_bucket(bucket_name)

s3_commented = Key(bucket)
s3_commented.key = 'docs/comments_replied_to.txt'

#If config_bot.py isn't in the folder
if not os.path.isfile('config_bot.py'):
    pprint("The bot's login config file is missing or messed up. Please create and/or fix it!")
    exit(1) #Or should this be sys.exit()?
    
#Overhead stuff (create instance of reddit and login)
user_agent = "MagicAlliance v2.0 by /u/iforgot120" #Change user agent string when saving test copy

def new_reddit(user_agent):
    try:
        return praw.Reddit(user_agent = user_agent)
    except urllib.error.URLError as e:
        pprint("Encountered error: " + e.code + " when attempting to create a reddit instance. Trying again...")
        time.sleep(time_delay)
        return new_reddit(user_agent)

r = new_reddit(user_agent = user_agent)

def attempt_login():
    try:
        r.login(REDDIT_USERNAME, REDDIT_PASS)
    except urllib.error.URLError as e:
        pprint("Encountered error: " + e.code + " when attempting to login to reddit.")
        time.sleep(time_delay)
        attempt_login()
        
attempt_login()

#If a_trick_is.txt isn't in the folder
if not os.path.isfile(os.path.join('docs', 'a_trick_is.txt')):
    pprint("a_trick_is.txt is missing or messed up! How will I know what a trick is without it? Please fix this issue.")
    a_trick_is = ["something a whore does for cocaine... or candy!", "something a whore does for cocaine.", "something a whore does for candy."]
else:    
    #Open up a_trick_is.txt for reading (mode "r"), and perform everything in the with block before closing the .txt
    with open(os.path.join('docs', 'a_trick_is.txt'), "r") as f:
        #Create an array of strings that describe what a trick is by splitting up the string into an array based on \n, then removing empty elements
        a_trick_is = f.read()
        a_trick_is = a_trick_is.split('\n')

#Check the comments_replied_to.txt to see which posts have been covered already (useful in case of restarts)
if not os.path.isfile(os.path.join('docs', 'comments_replied_to.txt')):
    #If the file doesn't exist, make the array empty. Also creates a text file to write to later
    open(os.path.join('docs', 'comments_replied_to.txt'), 'w').close()
    comments_replied_to = []
else:
    #Open up comments_replied_to.txt for reading (mode "r"), and perform everything in the with block before closing the .txt
    with open(os.path.join('docs', 'comments_replied_to.txt'), 'r') as f:
        #Set the array to the entire contents of the .txt, split the string into an array based on \n, then remove empty elements
        comments_replied_to = f.read()
        comments_replied_to = comments_replied_to.split('\n')

def find_trick_sentences(comment_text):
    """
    Returns a list of strings with each sentence that the word "trick[s]" is used in.
    If none were found, returns an empty Match object.
    """
    reg_ex = re.compile(r'[^.?!]*\btricks?\b[^.?!]*[.?!]*', flags=re.IGNORECASE) #All sentences with 'trick' or 'tricks'
    return nltk.regexp_tokenize(comment_text, reg_ex) #Tokenizes the sentences. Works a bit better than re.findall()
    
def try_get_parent(comment):
    try:
        return r.get_info(thing_id = comment.parent_id)
    except urllib.error.URLError as e:
        pprint("Encountered error: " + e.code + "when attempting to check parent comment of ID " + comment.id + ". Trying again...")
        time.sleep(time_delay)
        return try_get_parent(comment)

def okay_to_reply(reddit_comment, trick_found):
    commented = reddit_comment.id in comments_replied_to
    parented = False
    if not reddit_comment.is_root:
        parent = try_get_parent(reddit_comment)
        parented = parent.id in comments_replied_to
        if not parented and not parent.is_root:
            grandparent = try_get_parent(parent)
            parented = grandparent.id in comments_replied_to
    return not commented and trick_found and not parented
    
def try_reply(reddit_comment, trick_found):
    try:
        return okay_to_reply(reddit_comment, trick_found)
    except urllib.error.URLError as e:
        pprint("Encountered error: " + e.code + " when attempting to reply to a comment.")
        time.sleep(time_delay)
        r.send_message('iforgot120', 'MagicAlliance has encountered an HTTPERROR', 'Error ' + e.code + '\n\nCheck to see if it\'s shut down or something.')
        return try_reply(reddit_comment, trick_found)
        
def get_reddit_comments(sub, limit):
    try:
        return r.get_comments(sub, limit = limit)
    except urllib.error.URLError as e:
        pprint("Encountered error: " + e.code + " when attempting to retrieve reddit comments.")
        time.sleep(time_delay)
        return get_reddit_comments(sub, limit = limit)
        
def reply_comment(comment, to_reply):
    try:
        comment.reply(to_reply)
    except urllib.error.URLError as e:
        pprint("Encountered error: " + e.code + " when attempting to reply to a comment.")
        time.sleep(time_delay)
        reply_comment(comment, to_reply)
    except (praw.errors.LoginOrScopeRequired, praw.errors.LoginRequired) as e:
        attempt_login()
        comment.reply(to_reply)
        
def get_author(comment):
    try:
        return comment.author.name
    except urllib.error.URLError as e:
        pprint("Encountered error: " + e.code + " when attempting retrieve a comment author's username.")
        time.sleep(time_delay)
        return get_author(comment)

def main():
    try:
        while True:
            #Looking at all new posts
            for comment in get_reddit_comments('all', limit=get_limits):
                #List of strings with each sentence containing the word (if any)
                num_replied_to = 0
                my_reply = ""
                trick_sentences = find_trick_sentences(comment.body)
                plural = False
                for sentence in trick_sentences:
                        sentence = sentence.replace('\n', ' ').strip()
                        def_num = randint(0, len(a_trick_is) - 1)
                        tokenized = nltk.pos_tag(word_tokenize(sentence))
                        if ('trick', 'NN') in tokenized or ('tricks', 'NNS') in tokenized:
                            plural = ('tricks', 'NNS') in tokenized if not plural else plural
                            my_reply += "> " + sentence + "\n\n"
                reply_okay = try_reply(comment, trick_sentences)
                if reply_okay and my_reply != "":
                    my_reply += "Illusion" + ("s" if plural else "") + ", /u/" + get_author(comment) + ". " + ("Tricks are " if plural else "A trick is ") + a_trick_is[def_num]
                    reply_comment(comment, my_reply)
                    pprint("Comment ID: " + comment.id + "\n" + my_reply + "\n\n----------")
                    num_replied_to += 1
                    comments_replied_to.append(comment.id)
                    with open (os.path.join('docs', 'comments_replied_to.txt'), 'a') as f:
                        f.write(comment.id + '\n')
                    s3_commented.set_contents_from_filename(os.path.join('docs', 'comments_replied_to.txt'))
                pprint("Number of comments replied to in that cycle: " + str(num_replied_to))
            time.sleep(time_delay) #make sleep time larger once it's actually on a server
    except urllib.error.URLError as e:
        pprint("Encountered error: " + e.code + " while running main loop.")
        time.sleep(time_delay * 1200)
        main()

if __name__ == '__main__':
  main()