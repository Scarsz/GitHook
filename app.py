import datetime
import iso8601
import json
import requests

from flask import Flask, request, render_template

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.j2')


@app.route('/<int:channel>/<token>', methods=['POST'])
def receive_default(channel, token):
    return push(channel, token, "chptv")


@app.route('/<int:channel>/<token>/<flags>', methods=['POST'])
def receive(channel, token, flags):
    return push(channel, token, flags)


def push(channel, token, flags):
    remote = request.headers['X-Forwarded-For'] if 'X-Forwarded-For' in request.headers else str(request.host)

    if request.headers['Content-Type'] != "application/json":
        print("Denying " + remote + ": only JSON is supported")
        return "", 415
    if request.data is None or request.data.decode("UTF-8") == "":
        print("Denying " + remote + ": no data received")
        return "", 422
    data = json.loads(request.data.decode("UTF-8"))

    method = request.headers["X-GitHub-Event"] if "X-GitHub-Event" in request.headers else None
    if method is None:
        print("Denying " + remote + ": no X-GitHub-Event supplied")
        return "", 400
    elif method == "ping":
        print("Received ping for " +
              (("repository " + data['repository']['full_name'])
               if "repository" in data else
               ("organization " + data['organization']['login'])) +
              ": " + data['zen'])
        return "", 204
    elif method != "push":
        print("Denying " + remote + ": only push is implemented")
        return "", 418

    user_agent = request.headers['User-Agent']
    if not user_agent.startswith("GitHub-Hookshot"):
        print("Denying " + remote + ": invalid user agent \"" + user_agent + "\"")
        return "", 403

    f = {
        'contributor_link': True if 'c' in flags else False,
        'descriptions': True if 'd' in flags else False,
        'files': True if 'f' in flags else False,
        'hashes': True if 'h' in flags else False,
        'joke': True if 'j' in flags else False,
        'picture': True if 'p' in flags else False,
        'short_name': True if 's' in flags else False,
        'time': True if 't' in flags else False,
        'verbose': True if 'v' in flags else False
    }

    branch = str(data['ref']).replace("refs/heads/", "")
    pusher = data['pusher']['name']

    commits = []
    for commit in data['commits']:
        url = commit['url']
        commit_hash = "[`" + commit['id'][:7] + "`](" + url + ")"
        title = str(commit['message']).split("\n")[0]
        description = "\n".join(filter(None, str(commit['message']).split("\n")[1:]))
        if len(title) > 58 and not f['verbose']:
            title = title[58:] + "..."
        if pusher != commit['committer']['name']:
            title += " - " + pusher
        commits.append(
            ((commit_hash + " ") if f['hashes'] else "") +
            title +
            (("\n" + description) if description != "" and f['descriptions'] else "")
        )

    # working with time in programs sucks
    timestamp = iso8601\
        .parse_date(data['head_commit']['timestamp'])\
        .astimezone(datetime.timezone.utc)\
        .replace(tzinfo=None)\
        .isoformat()

    embed = {
        "title": "[" + (data['repository']['name']
                        if f['short_name'] else
                        data['repository']['full_name']) + ":" + branch + "] " +
                 str(len(data['commits'])) + " new commits",
        "url": data['compare'],
        "description": "\n".join(commits),
        "color": 16777215,
        "timestamp": timestamp,
        "footer": {
            "icon_url": "https://assets-cdn.github.com/images/modules/logos_page/GitHub-Mark.png",
            "text": "GitHook"
        },
        "author": {
            "name": data['pusher']['name'],
            "url":
                (data['repository']['html_url'] + "/commits?author=" + data['pusher']['name'])
                if f['contributor_link'] else
                ("https://github.com/" + data['pusher']['name']),
            "icon_url": data['sender']['avatar_url']
        },
        "fields": {}
    }
    if f['picture']:
        embed['thumbnail'] = {
            "url": data['repository']['owner']['avatar_url']
        }
    if f['joke']:
        joke = requests.get("https://safe-falls-22549.herokuapp.com/random_joke").json()
        embed['fields'].append({
            "name": joke["setup"],
            "value": joke["punchline"]
        })

    payload = {
        "username": "GitHub",
        "avatar_url": "https://assets-cdn.github.com/images/modules/logos_page/GitHub-Mark.png",
        "embeds": [embed]
    }

    execution = requests.post("https://discordapp.com/api/webhooks/" + str(channel) + "/" + token, json=payload)
    if execution.status_code == 200 or execution.status_code == 204:
        return "", 204
    else:
        return "Discord returned code " + str(execution.status_code) + "\n" + str(execution.json()), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=4834)
