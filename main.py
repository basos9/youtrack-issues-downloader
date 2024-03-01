from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import requests
import time


# User configuration:
PROJECT_ID = "Data requests"
ID_PAD_LENGTH = 3  # Pads issue numbers for folder names, ensuring order. Increase if >999 issues in your project.
# User configuration ends

load_dotenv()
YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")
BASE_YOUTRACK_URL = "https://ferryhoppers.myjetbrains.com"


def clean_folder_name(
    name: str, replace_space: bool = True, space_replacement: str = "_"
) -> str:
    """
    Cleans a string to make it a valid folder name for both Linux and Windows.

    Args:
        name (str): The original folder name string.
        replace_space (bool, optional): Flag to replace spaces with a specific character. Defaults to True.
        space_replacement (str, optional): The character to replace spaces with. Defaults to '_'.

    Returns:
        str: The cleaned folder name.
    """
    # Characters not allowed in Windows and Linux file names
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "")

    # Replace spaces if required
    if replace_space:
        name = name.replace(" ", space_replacement)

    # Avoid names that are reserved in Windows or start with a dot (hidden in Linux)
    reserved_names = [
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    ]
    if name.upper() in reserved_names or name.startswith("."):
        name = "_" + name  # Prefix with an underscore to make it valid

    return name


def download_attachments(attachments, issue_id, headers):
    """Download attachments for a given issue.

    Args:
        attachments (list): A list of attachments to download.
        issue_id (str): The issue ID for folder naming.
        headers (dict): The headers including authorization to use for requests.
    """
    for attachment in attachments:
        attachment_url = BASE_YOUTRACK_URL + attachment["url"]
        response = requests.get(attachment_url, headers=headers, stream=True)
        if response.status_code == 200:
            attachment_path = os.path.join(issue_id, attachment["name"])
            with open(attachment_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)


def get_issues(permanent_token: str, project_id: str, full_refresh: bool = False):
    """Download all tickets for a given project, including descriptions, comments, and attachments.

    Args:
        permanent_token (str): Your YouTrack permanent token.
        project_id (str): The YouTrack project ID.
        full_refresh (bool, optional): Flag to force a full refresh of all issues in case the folder already exists. Defaults to False; will skip existing folders.
    """
    headers = {"Authorization": f"Bearer {permanent_token}"}
    params = {
        "fields": "idReadable,numberInProject,summary,created,description,wikifiedDescription,comments(author(name),created,deleted,text,reactions(author(name),reaction)),attachments(name,url),project(id,shortName)",
        "query": f"project:{{{project_id}}} sort by: {{issue id}} desc",
    }
    issues_endpoint = f"{BASE_YOUTRACK_URL}/youtrack/api/issues"

    response = requests.get(issues_endpoint, headers=headers, params={**params})
    if response.status_code != 200:
        print("Failed to fetch issues:", response.text)
        return
    issues = response.json()

    for issue in issues:
        issue_id = issue["idReadable"]
        issue_number_in_project = issue["numberInProject"]
        issue_summary = issue["summary"]
        project_short_name = issue["project"]["shortName"]

        issue_target_path = os.path.join(
            "exports",
            f"{project_short_name}-{str(issue_number_in_project).zfill(ID_PAD_LENGTH)}-{clean_folder_name(issue_summary)}",
        )

        if not full_refresh and os.path.exists(issue_target_path):
            print(f"Skipping {issue_target_path} as it already exists.")
            continue

        print(f"Processing {issue_target_path}")
        os.makedirs(issue_target_path, exist_ok=True)

        # Save issue details
        with open(os.path.join(issue_target_path, "content.txt"), "w") as f:
            f.write(f"# {issue_id} - {issue['summary']}\n\n")
            f.write(f"{issue.get('description', 'No description')}\n\n")
            f.write(f"\n# Comments")
            for comment in issue.get("comments", []):
                comment_timestamp_obj = datetime.fromtimestamp(
                    comment["created"] / 1000, tz=timezone.utc
                )
                comment_timestamp = comment_timestamp_obj.isoformat(timespec="seconds")
                comment_section_title = (
                    f"Comment by {comment['author']['name']} at {comment_timestamp}"
                )
                f.write(f"\n\n---\n---\n{comment_section_title}\n")
                f.write(f"Deleted: {comment['deleted']}\n")
                f.write(f"Reactions:\n")
                for reaction in comment["reactions"]:
                    f.write(
                        f"    {reaction['author']['name']}: {reaction['reaction']}\n"
                    )
                f.write(f"\n{comment['text']}\n")

        # Download attachments
        if "attachments" in issue and issue["attachments"]:
            download_attachments(issue["attachments"], issue_target_path, headers)


if __name__ == "__main__":
    permanent_token = YOUTRACK_TOKEN
    get_issues(permanent_token, project_id=PROJECT_ID, full_refresh=False)