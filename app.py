import os
import threading
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()
app = App(token=os.getenv("SLACK_BOT_TOKEN"))

CHANNEL_ID = "C0819J5AFPS"
USERGROUP_ID ="S08AXRM7BGE"
CANVAS_ID ="F0BS3TXKSSE"

def add_to_usergroup(client, user_id):
    current = client.usergroups_users_list(usergroup=USERGROUP_ID)
    if not current["ok"]:
        print(f"[usergroups_users_list failed] {current}")
        return
    
    member_ids = current["users"]

    if user_id in member_ids:
        print(f"{user_id} is already in the usergroup, skipping")
        return

    member_ids.append(user_id)
    result = client.usergroups_users_update(usergroup=USERGROUP_ID, users=member_ids)

    if not result["ok"]:
        print(f"[usergroup_users_list failed] {result}")
    else:
        print(f"added {user_id} to usergroup {USERGROUP_ID}")

@app.event("member_joined_channel")
def welcome(event, client):
    channel = event["channel"]

    if channel != CHANNEL_ID:
        return

    user_id = event["user"]
    add_to_usergroup(client, user_id)
    text = f"wahhhh! welcome <@{user_id}> :D"

    client.chat_postMessage(
        channel=channel,
        text=text,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text,
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "clicky",
                            "emoji": True
                        },
                        "action_id": "send_emojis"
                    }
                ]
            }
        ]
    )

@app.action("send_emojis")
def send_emojis(ack, body, client):
    ack()

    channel = body["channel"]["id"]
    ts = body["message"]["ts"]

    client.chat_postMessage(
        channel=channel,
        thread_ts=ts,
        text=":red-pikmin:"
    )

def fetch_canvas_markdown(client):
    info = client.files_info(file=CANVAS_ID)
    if not info["ok"]:
        print(f"files_info failed {info}")
        return None

    download_url = info["file"]["url_private_download"]
    bot_token = os.getenv("SLACK_BOT_TOKEN")

    resp = requests.et(download_url, headers={"Authorization": f"Bearer {bot_token}"})
    if resp.status_code != 200:
        print(f"[canvas download failed] status={resp.status_code} body={resp.text[:300]}")
        return None
    return resp.text

def extract_bullets(markdown_text, heading_text):
    lines = markdown_text.split("\n")
    bullets = []
    in_section = False

    for line in lines:
        stripped = line.strip()
        clean_heading = stripped.lstrip("#").strip().lower()

        if not in_section:
            if clean_heading == heading_text.lower():
                in_section = True
            continue

        if stripped == "":
            continue

        if stripped.startswitch("*") or stripped.startswitch("-"):
            item = stripped.lstrip("*-").strip()

            if item.startswitch("[") and "]" in item:
                item = item.split("]", 1)[1].strip()
            bullets.append(item)
        else:
            break

    return bullets
            

if __name__ == "__main__":
    print("bot is running!")
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()