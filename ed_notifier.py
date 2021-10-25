#!/usr/bin/python3

import argparse
import sys
import requests
import json
from pathlib import Path
SCRIPT_DIR = str(Path(__file__).parent.absolute())


# ==================================== #
# ========== REQUEST CONFIG ========== #
# ==================================== #

SORT = "new"
LIMIT = "30" # must be <= 100

# ==================================== #
# ======== SLACK NOTIF CONFIG ======== #
# ==================================== #

SLACK_MAX_TEXT_LENGTH = 3000
SLACK_MAX_TEXT_MSG = "\n\n(...)"


# Arg parser
parser = argparse.ArgumentParser(description="Sends notifications for new Ed posts to Slack channel(s)")
parser.add_argument('config', nargs=1, type=str, help='path to config json containing Ed + Slack config')
parser.add_argument('tokens', nargs=1, type=str, help='path to token json containing x-tokens for accessing Ed')
parser.add_argument('cache', nargs=1, type=str, help='path to cache json for Ed posts')
args = parser.parse_args()

CONFIG_JSON_FILEPATH = str(Path(args.config[0]).absolute())
TOKEN_JSON_FILEPATH = str(Path(args.tokens[0]).absolute())
CACHE_JSON_FILEPATH = str(Path(args.cache[0]).absolute())

if not Path(CONFIG_JSON_FILEPATH).is_file():
    print(f"ERROR: passed config json file '{args.config[0]}' not found")
    sys.exit(1)

# Read in config json data
with open(CONFIG_JSON_FILEPATH, 'r') as json_file:
    config = json.load(json_file)
    ED_COURSE_ID = config['ed_course_id']
    TOKEN_JSON = config['token_json']
    SLACK_AUTH_TOKEN = config['slack_auth_token']
    CHANNEL_IDS = config['channel_ids']

# Read auth token for this course from token json file
try:
    with open(TOKEN_JSON_FILEPATH, 'r') as token_json_file:
        token_json = json.load(token_json_file)
        ED_AUTH_TOKEN = token_json[ED_COURSE_ID]
except FileNotFoundError:
    print(f"ERROR: token json file '{TOKEN_JSON_FILEPATH}' not found")
    sys.exit(1)
except KeyError:
    print(f"ERROR: auth token for course {ED_COURSE_ID} not found in token json file ('{TOKEN_JSON_FILEPATH}')")
    sys.exit(1)

# Combine course ID and thread ID to get unique ID
def get_unique_id(thread):
    return f"{ED_COURSE_ID}/{thread['id']}"

# Read in cached data
CACHE_EXISTS = True
try:
    with open(CACHE_JSON_FILEPATH, 'r') as json_file:
        cache = json.load(json_file)
        if len(cache) == 0:
            raise ValueError
except (FileNotFoundError, ValueError):
    CACHE_EXISTS = False
    cache = {}

# Get all current threads from Ed - EXCLUDES deleted threads
REQUEST_URL = f"https://us.edstem.org/api/courses/{ED_COURSE_ID}/threads"
REQUEST_HEADERS = {'x-token': ED_AUTH_TOKEN}
current_threads = requests.get(REQUEST_URL, headers=REQUEST_HEADERS, params={'sort': SORT, 'limit': LIMIT})
threads = current_threads.json()['threads']

# Get deleted threads from Ed and append to list of all threads
deleted_threads = requests.get(REQUEST_URL, headers=REQUEST_HEADERS, params={'sort': SORT, 'limit': LIMIT, 'filter': 'deleted'})
threads.extend(deleted_threads.json()['threads'])

# Sort threads by number, ascending
threads.sort(key=lambda thread: thread['number'])

def set_slack_react(notif_msg, reaction_name, mode, slack_auth_token):
    if not notif_msg['ok']:
        return False

    slack_request_header = {
        "Authorization": f"Bearer {slack_auth_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # Use the original channel and timestamp of the notification message to react to it
    slack_request_body = {
        "channel": notif_msg['channel'],
        "name": reaction_name,
        "timestamp": notif_msg['ts']
    }
    response = requests.post(url=f"https://slack.com/api/reactions.{mode}", headers=slack_request_header, json=slack_request_body)
    return response

def slack_react_if(conditions, reaction_name, cache, thread, slack_auth_token):
    try:
        cached_thread = cache[get_unique_id(thread)]
        notif_msgs = cached_thread['ed_notifier']['notif_msgs']
    except KeyError:
        return
    
    all_conditions_satisfied = True
    for attr, check in conditions.items():
        if not check(thread[attr]):
            all_conditions_satisfied = False
    
    if "reactions" not in cached_thread['ed_notifier'].keys():
        cached_thread['ed_notifier']['reactions'] = []
    new_conditions = set(cached_thread['ed_notifier']['reactions'])

    for notif_msg in notif_msgs:
        if all_conditions_satisfied ^ (reaction_name in cached_thread['ed_notifier']['reactions']):
            if(all_conditions_satisfied):
                response = set_slack_react(notif_msg, reaction_name, "add", slack_auth_token)
                if(response.status_code == 200 and response.json()['ok']):
                    new_conditions.add(reaction_name)
            else:
                response = set_slack_react(notif_msg, reaction_name, "remove", slack_auth_token)
                if(response.status_code == 200 and response.json()['ok'] and reaction_name in new_conditions):
                    new_conditions.remove(reaction_name)
    
    cached_thread['ed_notifier']['reactions'] = list(new_conditions)

    return all_conditions_satisfied

def send_slack_notif(cache, thread, slack_auth_token, channel_ids):
    formatted_title = f"(#{thread['number']}) {thread['title']}"
    author = "Anonymous" if thread['is_anonymous'] else thread['user']['name']
    post_text = thread['document'].strip()
    if(len(post_text) > SLACK_MAX_TEXT_LENGTH):
        post_text = post_text[0:SLACK_MAX_TEXT_LENGTH - len(SLACK_MAX_TEXT_MSG)] + SLACK_MAX_TEXT_MSG
    if(len(post_text) == 0):
        post_text = "{post body has no text}"
    full_category = thread['category'] + (f": {thread['subcategory']}" if thread['subcategory'] else "")
    thread_url = f"https://edstem.org/us/courses/{thread['course_id']}/discussion/{thread['id']}"

    notif_msgs = []
    for channel_id in channel_ids:
        slack_request_header = {
            "Authorization": f"Bearer {slack_auth_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        slack_request_body = {
            "channel": channel_id,
            "text": formatted_title + ": " + post_text,
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": formatted_title,
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": post_text,
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"🗂️ *Category:*\n{full_category}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"👤 *Posted by:*\n{author}"
                        }
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🔗 Open in Ed",
                                "emoji": True
                            },
                            "url": thread_url
                        }
                    ]
                }
            ]
        }

        try:
            response = requests.post(url="https://slack.com/api/chat.postMessage", headers=slack_request_header, json=slack_request_body)
            if response.json()['ok']:
                cached_thread = cache[get_unique_id(thread)]
                # only keep the following response data (to avoid keeping the entire original message sent to Slack in the json!)
                cache_response_data = {}
                cache_response_data['ok'] = response.json()['ok']
                cache_response_data['channel'] = response.json()['channel']
                cache_response_data['ts'] = response.json()['ts']
                notif_msgs.append(cache_response_data)
            else:
                raise RuntimeError()
        except RuntimeError as e:
            print(response.json())
            cached_thread = cache[get_unique_id(thread)]
            print(f"Got status {response.status_code} when posting message for Post #{thread['number']} (ID {thread['id']}) to Slack Channel {channel_id}")
    
    if("ed_notifier" not in cached_thread.keys()):
        cached_thread['ed_notifier'] = {}
    cached_thread['ed_notifier']['notif_msgs'] = notif_msgs

# Modify this function to change what data is cached for each thread
def cache_thread(cache, thread):
    cached_thread = cache[get_unique_id(thread)] if get_unique_id(thread) in cache.keys() else {}
    cached_thread['id'] = thread['id']
    cached_thread['number'] = thread['number']
    cached_thread['is_answered'] = thread['is_answered']
    cached_thread['deleted_at'] = thread['deleted_at']
    cached_thread['is_private'] = thread['is_private']
    cached_thread['is_qa'] = thread['category'] == "LIVE Lecture Q&A"
    cache[get_unique_id(thread)] = cached_thread

# Iterate through threads (sorted)
for thread in threads:

    # Add new threads to cache & send slack notif
    if get_unique_id(thread) not in cache.keys():
        cache_thread(cache, thread)
        if not CACHE_EXISTS:
            continue
        else:
            send_slack_notif(cache, thread, SLACK_AUTH_TOKEN, CHANNEL_IDS)
    
    deleted = slack_react_if(
        {
            "deleted_at": (lambda attr: attr is not None)
        },
        "x",
        cache, thread, SLACK_AUTH_TOKEN
    )

    slack_react_if(
        {
            "is_private": (lambda attr: not deleted and attr == True)
        },
        "lock",
        cache, thread, SLACK_AUTH_TOKEN
    )
    slack_react_if(
        {
            "is_answered": (lambda attr: not deleted and attr == True),
        },
        "white_check_mark",
        cache, thread, SLACK_AUTH_TOKEN
    )
    
    cache_thread(cache, thread)

# Update cache
with open(CACHE_JSON_FILEPATH, 'w') as json_file:
    json.dump(cache, json_file)

# Only send slack notifs if cache file exists already
if not CACHE_EXISTS:
    print("Cache file was empty: successfully populated cache. No Slack notifications sent.")
