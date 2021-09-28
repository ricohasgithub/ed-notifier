# ed-notifier
A Slack Bot notification service for Ed, written in Python

Requirements:
- An Ed (edstem.org) account enrolled in a course
  - In order to get Slack notifications for all posts, even those which are private, the account must have elevated permissions (e.g. "instructor"-level access).

Installation:
1) `git clone https://github.com/rajkundu/ed-notifier.git` and `cd ed-notifier` (or wherever you cloned to)
2) Edit `config.json` as follows:
```
{
    "ed_course_id": "0000",
    "ed_auth_token": "YOUR_ED_AUTH_TOKEN_HERE",
    "slack_auth_token": "YOUR_SLACK_BOT_AUTH_TOKEN_HERE",
    "channel_ids": [
        "YOUR_SLACK_CHANNEL_IDS_HERE"
    ]
}
```
  - `ed_course_id`: replace `0000` with your four-digit course code in Ed. This is found by navigating to your Ed course in a web browser and looking at the URL, which should look like `https://edstem.org/us/courses/####/...`, where `####` is the four-digit course code.
  - `ed_auth_token: this authentication token is obtained by analyzing your network traffic when connected to Ed. Look for an HTTPS request to `https://us.edstem.org/api/courses/####/threads...`, and expand the *request body* (NOT response body) information. Look for the `x-token` property. This is your Ed authentication token.
  - `slack_auth_token`: add your Slack Bot's OAuth 2.0 v2 token here. If you're using it through Raj, he will do this for you.
  - `channel_ids`: an array of Slack channel IDs to which messages will be posted. The bot must be added to the channels specified for this to work.
3) To run the script, use `/usr/bin/python3 ed_notifier.py config.json cache.json`
  - `/usr/bin/python3` should be the path to your Python 3 installation on your computer
  - `ed_notifier.py` should be the path to the Python script in this repository, which may need to be changed to an absolute path if the CWD is not the repository (e.g., running from `crontab`).
  - `config.json` should be the path (or absolute path, as described just above) to the configuration JSON file. In the simplest case, this is `config.json` which you modified in Step 2 after cloning in Step 1.
  - `cache.json` should be the path to the cache file which the script will use to keep track of "old" Ed posts (so that it knows which are new). **This file will be automatically created by the script if it doesn't exist already.**
