import os
from flask import Flask, request
from github import Github, GithubIntegration

app = Flask(__name__)

app_id = ''

# Read the bot certificate
with open(
        os.path.normpath(os.path.expanduser('test-bot-umons.pem')),
        'r'
) as cert_file:
    app_key = cert_file.read()

# Create an GitHub integration instance
git_integration = GithubIntegration(
    app_id,
    app_key,
)


def issue_opened_event(repo, payload):
    issue = repo.get_issue(number=payload['issue']['number'])
    author = issue.user.login


def add_label(repo, payload, label):
    issue = repo.get_issue(number=payload['issue']['number'])
    author = issue.user.login
    issue.add_to_labels(label)

    response = f"Thanks for opening this issue, @{author}! " \
               f"The repository maintainers will look into it ASAP! :speech_balloon:"
    issue.create_comment(f"{response}")


def create_issue(repo, payload, title, body):
    issue = repo.create_issue(title=title, body=body)
    issue.add_to_labels('pending')


# create issue when pull request is closed
def create_other_issue(repo, payload):
    issue = repo.get_issue(number=payload['issue']['number'])
    response = f"Thanks for opening this issue, @{issue.user.login}! "
    issue.create_comment(f"{response}")


# a pull request has been merged, remove branch
def remove_branch(repo, payload):
    branch = repo.get_git_ref(f"heads/{payload['pull_request']['head']['ref']}")
    print(branch)
    branch.delete()


#  set pull request to success
def set_pull_request_success(repo, payload):
    pull = repo.get_pull(number=payload['number'])
    pull.create_status(state='pending', description='Pull request is in progress',
                       context='continuous-integration/travis-ci/pr')
    pull.get_commits().reversed[0].create_status(
        state='pending',
        description='Work in progress',
        context='WIP')


@app.route("/", methods=['POST'])
def bot():
    payload = request.json

    if not 'repository' in payload.keys():
        return "", 204

    owner = payload['repository']['owner']['login']
    repo_name = payload['repository']['name']

    git_connection = Github(
        login_or_token=git_integration.get_access_token(
            git_integration.get_installation(owner, repo_name).id
        ).token
    )
    repo = git_connection.get_repo(f"{owner}/{repo_name}")

    # Check if the event is a GitHub issue creation event
    if all(k in payload.keys() for k in ['action', 'issue']) and payload['action'] == 'opened':
        add_label(repo, payload, 'pending')

    elif all(k in payload.keys() for k in ['action', 'issue']) and payload['action'] == 'closed':
        add_label(repo, payload, 'closed')

    elif all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'closed':
        remove_branch(repo, payload)

    elif all(k in payload.keys() for k in ['action', 'pull_request']) and all(
            i in payload['pull_request']['title'] for i in ["wip", "work in progress", "do not merge"]):
        # https://pygithub.readthedocs.io/en/latest/examples/Commit.html#create-commit-status-check
        set_pull_request_success(repo, payload)

    # check merge is true or false
    elif all(k in payload.keys() for k in ['pull_request']) and payload["pull_request"]['merged'] == 'true':
        create_other_issue(repo, payload)

    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=5000)
