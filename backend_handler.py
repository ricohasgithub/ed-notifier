#!/usr/bin/python3

import argparse
import sys
from flask import Flask, request, jsonify
import json
import requests
from pathlib import Path
SCRIPT_DIR = str(Path(__file__).parent.absolute())

# Arg parser
parser = argparse.ArgumentParser(description="Handles backend HTTP requests for Ed Notifier Bot, e.g., accepting Ed X-Tokens, completing Slack OAuth Flow, etc.")
parser.add_argument('port', nargs=1, type=int, help='port on which to run backend http service')
parser.add_argument('tokens', nargs=1, type=str, help='path to json file in which to store Ed x-tokens')
parser.add_argument('slack_auth', nargs=1, type=str, help='path to json file containing Slack App authorizations (Client ID & Client Secret)')
args = parser.parse_args()

HOST = "127.0.0.1"
PORT = args.port[0]
TOKEN_JSON_FILEPATH = str(Path(args.tokens[0]).absolute())
SLACK_AUTH_JSON_FILEPATH = str(Path(args.slack_auth[0]).absolute())
SLACK_OAUTH_REDIRECT_URI = "SLACK_APP_OAUTH_REDIRECT_URI_HERE"

# Read slack auth data from slack_auth json file
try:
	with open(SLACK_AUTH_JSON_FILEPATH, 'r') as slack_json_file:
		slack_json = json.load(slack_json_file)
		SLACK_CLIENT_ID = slack_json['slack_client_id']
		SLACK_CLIENT_SECRET = slack_json['slack_client_secret']
except FileNotFoundError:
	print(f"ERROR: slack auth json file '{SLACK_AUTH_JSON_FILEPATH}' not found")
	sys.exit(1)
except KeyError:
	print(f"ERROR: Slack Client ID and/or Client Secret not found in slack auth json file ('{SLACK_AUTH_JSON_FILEPATH}')")
	sys.exit(1)

app = Flask(__name__)

def test_token(ed_course_id, xtoken):
	headers = {'x-token': xtoken}
	response = requests.get(f"https://us.edstem.org/api/courses/{ed_course_id}/threads", headers=headers, params={'sort': 'new', 'limit': 30})
	return response.status_code == 200

@app.route("/tokens/ed/submit", methods=["POST"])
def process_token():
	ed_course_id, xtoken = str(request.json['course_id']), str(request.json['x-token'])
	if(test_token(ed_course_id, xtoken)):
		try:
			with open(TOKEN_JSON_FILEPATH, 'r') as token_json_file:
				tokens = json.load(token_json_file)
				if len(tokens) == 0:
					raise ValueError()
		except (FileNotFoundError, ValueError):
			tokens = {}
		with open(TOKEN_JSON_FILEPATH, 'w') as token_json_file:
			tokens[ed_course_id] = xtoken
			json.dump(tokens, token_json_file)
		return '', 200
	return '', 422

@app.route("/tokens/slack/oauth", methods=["GET"])
def process_oauth_initiation():
	code = request.args.get('code')
	args = {
		"client_id": SLACK_CLIENT_ID,
		"client_secret": SLACK_CLIENT_SECRET,
		"code": code,
		"redirect_uri": SLACK_OAUTH_REDIRECT_URI
	}
	response = requests.post("https://slack.com/api/oauth.v2.access", data=args)
	print(response.json())
	return {"ok": response.json()['ok']}, response.status_code

if __name__ == "__main__":
	# Launch Flask app
	app.run(host=HOST, port=PORT)
