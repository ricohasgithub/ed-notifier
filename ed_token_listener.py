#!/usr/bin/python3

import argparse
from flask import Flask, request, jsonify
import json
import requests
from pathlib import Path
SCRIPT_DIR = str(Path(__file__).parent.absolute())

# Arg parser
parser = argparse.ArgumentParser(description="Accepts Ed x-tokens via POST request, checks them for validity, and stores them in json file")
parser.add_argument('port', nargs=1, type=int, help='port on which to run token listening service')
parser.add_argument('token_json', nargs=1, type=str, help='path to json file in which to store Ed x-tokens')
args = parser.parse_args()

HOST = "127.0.0.1"
PORT = args.port[0]
TOKEN_JSON_FILEPATH = args.token_json[0]

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

if __name__ == "__main__":
	# Launch Flask app
	app.run(host=HOST, port=PORT)
