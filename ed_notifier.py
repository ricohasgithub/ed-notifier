import requests
import json
from pathlib import Path
SCRIPT_DIR = str(Path(__file__).parent.absolute())


# ==================================== #
# =========== JSON CONFIG ============ #
# ==================================== #

CONFIG_JSON_FILEPATH = str(Path(SCRIPT_DIR) / "config.json")
CACHE_JSON_FILEPATH = str(Path(SCRIPT_DIR) / "cache.json")

# ==================================== #
# ========== REQUEST CONFIG ========== #
# ==================================== #

SORT = "new"
LIMIT = "20" # must be <= 100


# Read in config json data
with open(CONFIG_JSON_FILEPATH, 'r') as json_file:
    config = json.load(json_file)
    ED_COURSE_ID = config['ed_course_id']
    ED_AUTH_TOKEN = config['ed_auth_token']
    SLACK_WEBHOOK_URLS = config['slack_webhook_urls']

# Read in cached data
try:
    with open(CACHE_JSON_FILEPATH, 'r') as json_file:
        cache = json.load(json_file)
        cached_thread_ids = set(cache['thread_ids'])
except:
    cache = {}
    cached_thread_ids = set()

# Read data from Ed
REQUEST_URL = f"https://us.edstem.org/api/courses/{ED_COURSE_ID}/threads?sort={SORT}&limit={LIMIT}"
REQUEST_HEADERS = {'x-token': ED_AUTH_TOKEN}
response = requests.get(REQUEST_URL, headers=REQUEST_HEADERS)
threads = response.json()['threads']
new_threads = [thread for thread in threads if thread['id'] not in cached_thread_ids]

for thread in new_threads:
    cached_thread_ids.add(thread['id'])

# Write updated cache data to cache json
new_cache = {
    'thread_ids': sorted(cached_thread_ids)
}
with open(CACHE_JSON_FILEPATH, 'w') as json_file:
    json.dump(new_cache, json_file)

# Send slack notifs
if cache != {}:
    for thread in new_threads:
        formatted_title = f"(#{thread['number']}) {thread['title']}"
        author = "Anonymous" if thread['is_anonymous'] else thread['user']['name']
        post_text = thread['document'].strip()
        full_category = thread['category'] + (f": {thread['subcategory']}" if thread['subcategory'] else "")
        thread_url = f"https://edstem.org/us/courses/{thread['course_id']}/discussion/{thread['id']}"

        slack_request_json = {
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

        for slack_webhook_url in SLACK_WEBHOOK_URLS:
            r = requests.post(slack_webhook_url, json=slack_request_json)
            if(r.status_code != 200):
                print(f"Got status {r.status_code} when posting message for Post #{thread['number']}/ID {thread['id']} to Slack Webhook URL {slack_webhook_url}.")
