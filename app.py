import datetime
import iso8601
import json
import requests

from flask import Flask, request, render_template

app = Flask(__name__)
wait_for_completion = False


@app.route('/')
def index():
    return render_template('index.j2')


@app.route('/<int:channel>/<token>', methods=['POST'])
def receive_default(channel, token):
    return receive(channel, token)


@app.route('/<int:channel>/<token>/<flags>', methods=['GET', 'POST'])
def receive(channel, token, flags="chptv"):
    method = request.headers["X-GitHub-Event"] if "X-GitHub-Event" in request.headers else None
    if method is None:
        print("Denying " + request.host + ": no X-GitHub-Event supplied")
        return "", 400
    elif method != "push":
        print("Denying " + request.host + ": only push is implemented")
        return "", 418
    if request.headers['Content-Type'] != "application/json":
        print("Denying " + request.host + ": only JSON is supported")
        return "", 415
    if request.data is None or request.data.decode("UTF-8") == "":
        print("Denying " + request.host + ": no data received")
        return "", 422

    data = json.loads(request.data.decode("UTF-8"))

    # user_agent = request.headers['User-Agent']  # request.user_agent.string
    # if not user_agent.startswith("GitHub-Hookshot"):
    #     print("Denying " + request.host + ": invalid user agent \"" + user_agent + "\"")
    #     return "", 403

    flags = {
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
        if len(title) > 58 and not flags['verbose']:
            title = title[58:] + "..."
        if pusher != commit['committer']:
            title += " - " + pusher
        commits.append(
            ((commit_hash + " ") if flags['hashes'] else "") +
            title +
            (("\n" + description) if description != "" and flags['descriptions'] else "")
        )

    # working with time in programs sucks
    timestamp = iso8601.parse_date(data['head_commit']['timestamp']).astimezone(datetime.timezone.utc).replace(tzinfo=None).isoformat()

    embed = {
        "title": "[" + (data['repository']['name'] if flags['short_name'] else data['repository']['full_name']) + ":" + branch + "] " + str(len(data['commits'])) + " new commits",
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
                if flags['contributor_link'] else
                ("https://github.com/" + data['pusher']['name']),
            "icon_url": "https://avatars1.githubusercontent.com/u/7691988?v=4"
        },
        "fields": []
    }
    if flags['picture']:
        embed['thumbnail'] = {
            "url": data['repository']['owner']['avatar_url']
        }
    if flags['joke']:
        joke = requests.get("https://safe-falls-22549.herokuapp.com/random_joke").json()
        embed['fields'].append({
            "name": joke["setup"],
            "punchline": joke["punchline"],
            "inline": False
        })

    payload = {
        "username": "GitHub",
        "avatar_url": "https://assets-cdn.github.com/images/modules/logos_page/GitHub-Mark.png",
        "embeds": [embed]
    }

    execution = requests.post("https://discordapp.com/api/webhooks/" + str(channel) + "/" + token + "?wait=" + str(wait_for_completion).lower(), json=payload)
    if execution.status_code == 200 or execution.status_code == 204:
        return "", 204
    else:
        return "Discord returned code " + str(execution.status_code) + "\n" + str(execution.json()), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=4834)
