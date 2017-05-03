#!/usr/bin/python3
import re
from time import sleep

import praw
import pyrebase
import requests
from bs4 import BeautifulSoup

from config import firebase, reddit

# Subreddits to monitor, separated by '+'
SUBREDDITS = 'uoft+dcs_uoft+utsc+utm+skule'

# Regex constants
COURSE_NAME_REGEX = re.compile(r'[!]{1}[a-zA-Z]{3}\d{3}[h|H|y|Y]*[1]*')
COURSE_INFO_REGEX = re.compile(r'[a-zA-Z]{3}\d{3}[h|H|y|Y]{1}[1]{1}')

# Firebase initialization
fb = pyrebase.initialize_app(firebase)
db = fb.database()


def main():
    # Log in once
    r = login()

    # Every minute, scan subreddits and comments for matches and act accordingly
    while True:
        try:
            run(r)
        except:
            pass
        sleep(60)


# Reddit bot login, returns reddit object used to reply with this account
def login():
    r = praw.Reddit(username=reddit["username"],
                    password=reddit["password"],
                    client_id=reddit["client_id"],
                    client_secret=reddit["client_secret"],
                    user_agent='CourseBot v0.1')
    return r


# Scan subreddits and comments for matches and act accordingly
def run(r):
    subreddits = r.subreddit(SUBREDDITS)
    subreddit_comments = subreddits.comments()
    subreddit_submissions = subreddits.new(limit=25)
    for comment in subreddit_comments:
        check_item(comment)
    for submission in subreddit_submissions:
        check_item(submission)


# Check submissions and comments for course names and reply accordingly
def check_item(item):
    skip = False
    try:
        course_mentioned = re.findall(COURSE_NAME_REGEX, item.title)
        lower_title = item.title.lower()
        if 'grade' in lower_title or 'mark' in lower_title:
            skip = True
    except AttributeError:
        course_mentioned = re.findall(COURSE_NAME_REGEX, item.body)
    if len(course_mentioned) == 1 and not is_serviced(item.id) and not item.author.name == "CourseBot" and not skip:
        course_code = course_mentioned[0][1:]
        reply = get_course_info(course_code.lower())
        if reply:
            reply += '\n\n'
            pre = '###' + course_code.upper() + ' - '
            post = '[Source Code](https://github.com/zuhayrx/coursebot)'
            reply = pre + reply + post
            try:
                item.reply(reply)
            except Exception as e:
                print(e)
                sleep(1)
                return
            print(reply)
        update_serviced(item.id)
        sleep(1)


# Update firebase 'serviced' with <item_id> to avoid multiple comments by bot
def update_serviced(item_id):
    payload = {item_id: True}
    db.child("serviced").update(payload)


# Check if <item_id> has already been replied to by bot
def is_serviced(item_id):
    request = db.child("serviced").child(item_id).get().val()
    return bool(request)


# Replaces course names in descriptions with links to course pages
def replace_name_with_link(matchobj):
    course_code = matchobj.group(0)
    return '[' + course_code + ']' + '(http://calendar.artsci.utoronto.ca/crs_' + \
           course_code[:3].lower() + '.htm#' + course_code + ')'


# Returns the course description to be used in the bot reply
def get_course_info(course_code):
    url = 'http://calendar.artsci.utoronto.ca/crs_' + course_code[:3] + '.htm'
    try:
        request = requests.get(url)
    except:
        return ''
    html_content = request.text
    soup = BeautifulSoup(html_content, 'lxml')
    for item in soup.find_all('a'):
        try:
            if item['name'][:6] == course_code.upper():
                name = item.find_next_sibling('span').text.strip()
                name = ' '.join(name.split()[1:]).split('[')[0]
                info = item.find_next_sibling('p').text
                info = re.sub(COURSE_INFO_REGEX, replace_name_with_link, info)
                return name + ':\n\n' + info
        except KeyError:
            pass
    return ''


if __name__ == "__main__":
    main()
