import os
import ollama
import requests

GITHUB_API_KEY = os.getenv("GITHUB_TOKEN")

SYSTEM_PROMPT = """You are a project manager and you are helping a user with their GitHub repository. You have access to the GitHub API and can perform actions such as creating issues, closing issues, updating issues, organizing and managing projects. You can only answer from the tools you are given. You will be given a task by the user and you will use the GitHub API to complete that task. You will not make any changes to the repository or project without explicit instructions from the user. You will not make any assumptions about the user's intentions or goals. You will always ask for clarification if you are unsure about what the user wants you to do. You will always provide clear and concise feedback to the user on the status of their task and any errors that may occur."""

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
]

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_API_KEY}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

def list_repos():
    """
    List all of the repositories the user has access to, most recently updated first.

    Returns:
        list: The repositories, each with its full name, description, language and whether it is private.
    """
    repos = []
    for page in range(1, 11):  # GitHub sends 100 per page, so this stops at 1,000
        response = requests.get(
            "https://api.github.com/user/repos",
            headers=GITHUB_HEADERS,
            params={"sort": "updated", "per_page": 100, "page": page},
            timeout=10,
        )

        # Return the error as text so the model can tell the user what went wrong.
        if response.status_code != 200:
            message = response.json().get("message", response.reason)
            return f"GitHub error {response.status_code}: {message}"

        repos += response.json()
        if len(response.json()) < 100:
            break

    # Keep only the fields the model needs to tell the repositories apart.
    return [
        {
            "full_name": repo["full_name"],
            "description": repo["description"],
            "language": repo["language"],
            "private": repo["private"],
        }
        for repo in repos
    ]

def get_repo(repo):
    """
    Get information about a GitHub repository.

    Args:
        repo: The full name 'owner/name', for example 'octocat/Hello-World'. If you only know the name, use list_repos to find the full name.

    Returns:
        dict: The repository information, or text explaining why it could not be found.
    """
    if "/" not in repo:
        return "Use the full name 'owner/name'. Call list_repos to find it."

    response = requests.get(
        f"https://api.github.com/repos/{repo}", headers=GITHUB_HEADERS, timeout=10
    )
    if response.status_code != 200:
        message = response.json().get("message", response.reason)
        return f"GitHub error {response.status_code}: {message}"

    data = response.json()
    return {
        "full_name": data["full_name"],
        "description": data["description"],
        "private": data["private"],
        "language": data["language"],
        "default_branch": data["default_branch"],
        "open_issues": data["open_issues_count"],  # includes pull requests
        "url": data["html_url"],
    }

def get_repo_issues(repo):
    """
    Get the open issues in a GitHub repository.

    Args:
        repo: The full name 'owner/name', for example 'octocat/Hello-World'. If you only know the name, use list_repos to find the full name.

    Returns:
        list: The open issues, each with its number, title, labels and assignees, or text explaining why they could not be found.
    """
    if "/" not in repo:
        return "Use the full name 'owner/name'. Call list_repos to find it."

    response = requests.get(
        f"https://api.github.com/repos/{repo}/issues",
        headers=GITHUB_HEADERS,
        params={"state": "open", "per_page": 30},
        timeout=10,
    )
    if response.status_code != 200:
        message = response.json().get("message", response.reason)
        return f"GitHub error {response.status_code}: {message}"

    # GitHub also lists pull requests as issues, so skip those.
    return [
        {
            "number": issue["number"],
            "title": issue["title"],
            "labels": [label["name"] for label in issue["labels"]],
            "assignees": [user["login"] for user in issue["assignees"]],
        }
        for issue in response.json()
        if "pull_request" not in issue
    ]

##########################################
### Agent Loop
##########################################
TOOLS = {"list_repos": list_repos, "get_repo": get_repo, "get_repo_issues": get_repo_issues}

def run_tool(call):
    """Run one tool call from the model and return the result as text."""
    tool = TOOLS.get(call.function.name)
    if tool is None:
        return f"Unknown tool '{call.function.name}'."

    # Return any error as text so the model can see what went wrong and try again.
    try:
        return str(tool(**call.function.arguments))
    except Exception as error:
        return f"Error calling {call.function.name}: {error}"


def run_agent(user_input):
    messages.append({"role": "user", "content": user_input})

    for _ in range(10):  # stop after 10 rounds so a confused model cannot loop forever
        response = ollama.chat(model="qwen3.5:4b", messages=messages, tools=list(TOOLS.values()), think=False)
        messages.append(response.message)

        # No tool calls means the model has its final answer.
        if not response.message.tool_calls:
            return response.message.content

        # Run every tool the model asked for and add the results to the conversation.
        for call in response.message.tool_calls:
            result = run_tool(call)
            messages.append({"role": "tool", "tool_name": call.function.name, "content": result})

    return "I stopped because this took too many steps."


while True:
    user_input = input("You: ")
    if user_input.strip() == "/bye":
        break
    print("Agent:", run_agent(user_input))