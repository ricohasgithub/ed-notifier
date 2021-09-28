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
LIMIT = "50" # must be <= 100

# ==================================== #
# ======== SLACK NOTIF CONFIG ======== #
# ==================================== #

SLACK_MAX_TEXT_LENGTH = 3000
SLACK_MAX_TEXT_MSG = "\n\n(...)"


# Arg parser
parser = argparse.ArgumentParser(description="Sends notifications for new Ed posts to Slack channel(s)")
parser.add_argument('config', nargs=1, type=str, help='path to config json containing Ed + Slack config')
parser.add_argument('cache', nargs=1, type=str, help='path to cache json for Ed posts')
args = parser.parse_args()

CACHE_JSON_FILEPATH = str(Path(args.cache[0]).absolute())
CONFIG_JSON_FILEPATH = str(Path(args.config[0]).absolute())
if not Path(CONFIG_JSON_FILEPATH).is_file():
    print(f"ERROR: passed config json file '{args.config[0]}' not found")
    sys.exit(1)

# Read in config json data
with open(CONFIG_JSON_FILEPATH, 'r') as json_file:
    config = json.load(json_file)
    ED_COURSE_ID = config['ed_course_id']
    ED_AUTH_TOKEN = config['ed_auth_token']
    SLACK_AUTH_TOKEN = config['slack_auth_token']
    CHANNEL_IDS = config['channel_ids']

# Combine course ID and thread ID to get unique ID
def get_unique_id(thread):
    return f"{ED_COURSE_ID}/{thread['id']}"

# Read in cached data
CACHE_EXISTS = True
try:
    with open(CACHE_JSON_FILEPATH, 'r') as json_file:
        cache = json.load(json_file)
except FileNotFoundError:
    CACHE_EXISTS = False
    cache = {}

# Read data from Ed
REQUEST_URL = f"https://us.edstem.org/api/courses/{ED_COURSE_ID}/threads?sort={SORT}&limit={LIMIT}"
REQUEST_HEADERS = {'x-token': ED_AUTH_TOKEN}
response = requests.get(REQUEST_URL, headers=REQUEST_HEADERS)
threads = response.json()['threads']

# Sort threads by number
threads.sort(key=lambda thread: thread['number'])

def send_slack_react(notif_msg, slack_auth_token, reaction_name):
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
    response = requests.post(url="https://slack.com/api/reactions.add", headers=slack_request_header, json=slack_request_body)
    return response.status_code == 200 and response.json()['ok']

def send_slack_notif(cache, thread, slack_auth_token, channel_ids):
    formatted_title = f"(#{thread['number']}) {thread['title']}"
    author = "Anonymous" if thread['is_anonymous'] else thread['user']['name']
    post_text = thread['document'].strip()
    if(len(post_text) > SLACK_MAX_TEXT_LENGTH):
        post_text = post_text[0:SLACK_MAX_TEXT_LENGTH - len(SLACK_MAX_TEXT_MSG)] + SLACK_MAX_TEXT_MSG
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

        response = requests.post(url="https://slack.com/api/chat.postMessage", headers=slack_request_header, json=slack_request_body)
        if response.status_code == 200:
            cached_thread = cache[get_unique_id(thread)]
            if("ed_notifier" not in cached_thread.keys()):
                cached_thread['ed_notifier'] = {}
            # only keep the following response data (to avoid keeping the entire original message sent to Slack in the json!)
            cache_response_data = {}
            cache_response_data['ok'] = response.json()['ok']
            cache_response_data['channel'] = response.json()['channel']
            cache_response_data['ts'] = response.json()['ts']
            notif_msgs.append(cache_response_data)
        else:
            print(f"Got status {response.status_code} when posting message for Post #{thread['number']} (ID {thread['id']}) to Slack Channel {channel_id}")
    
    cached_thread['ed_notifier']['notif_msgs'] = notif_msgs

def cache_thread(cache, thread):
    cached_thread = cache[get_unique_id(thread)] if get_unique_id(thread) in cache.keys() else {}
    cached_thread['id'] = thread['id']
    cached_thread['number'] = thread['number']
    cached_thread['is_answered'] = thread['is_answered']
    cache[get_unique_id(thread)] = cached_thread

# Iterate through threads (sorted by number)
for thread in threads:

    # Add new threads to cache & send slack notif
    if get_unique_id(thread) not in cache.keys():
        cache_thread(cache, thread)
        if CACHE_EXISTS:
            send_slack_notif(cache, thread, SLACK_AUTH_TOKEN, CHANNEL_IDS)
    
    # Check old threads to see if "answered" status changed
    else:
        if thread['is_answered'] and not cache[get_unique_id(thread)]['is_answered']:
            cached_thread = cache[get_unique_id(thread)]
            if "ed_notifier" not in cached_thread.keys() or "notif_msgs" not in cached_thread['ed_notifier'].keys():
                continue
            notif_msgs = cached_thread['ed_notifier']['notif_msgs']
            for notif_msg in notif_msgs:
                send_slack_react(notif_msg, SLACK_AUTH_TOKEN, "white_check_mark")
        cache_thread(cache, thread)

# Only send slack notifs if cache file exists already
if not CACHE_EXISTS:
    print("Cache file was empty: successfully populated cache. No Slack notifications sent.")

# Update cache
with open(CACHE_JSON_FILEPATH, 'w') as json_file:
    json.dump(cache, json_file)
