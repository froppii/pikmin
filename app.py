import os
import threading
import requests
import time
import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()
app = App(token=os.getenv("SLACK_BOT_TOKEN"))

CHANNEL_ID = "C0819J5AFPS"
USERGROUP_ID ="S08AXRM7BGE"
CANVAS_ID ="F0BS3TXKSSE"
TODO_HEADING = "to do(doing/urgent)"

POST_HOUR = 10
POST_MINUTE = 0

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

    resp = requests.get(download_url, headers={"Authorization": f"Bearer {bot_token}"})
    if resp.status_code != 200:
        print(f"[canvas download failed] status={resp.status_code} body={resp.text[:300]}")
        return None
    return resp.text

from bs4 import BeautifulSoup

def extract_bullets(html_text, heading_text):
    soup = BeautifulSoup(html_text, "html.parser")
    container = soup.find(class_= "quip-canvas-content") or soup

    bullets = []
    in_section = False

    for child in container.children:
        name = getattr(child, "name", None)
        if name is None:
            continue

        if name in ("h1", "h2", "h3"):
            heading = child.get_text(strip=True).lower()
            if in_section:
                break
            if heading == heading_text.lower():
                in_section = True
            continue

        if in_section and name == "div":
            for li in child.find_all("li"):
                bullets.append(li.get_text(strip=True))

    if not bullets:
        print("raw html")
        print(html_text[:2000])
        print("debug end")

    return bullets

def post_todo_summary(client):
    markdown_text = fetch_canvas_markdown(client)
    if markdown_text is None:
        return

    bullets = extract_bullets(markdown_text, TODO_HEADING)

    if not bullets:
        print("the list is empty! :D")
        return

    bullet_lines = "\n".join(f"\u2022 {b}" for b in bullets)
    text = f"wakey wakey <@U07SX29CECA>\n*today's to-dos:*\n{bullet_lines}"

    client.chat_postMessage(channel=CHANNEL_ID, text=text)
    print(f"posted {len(bullets)} to-do bullets")

def seconds_until_next_post():
    now = datetime.datetime.now()
    target = now.replace(hour=POST_HOUR, minute=POST_MINUTE, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()

def scheduler_loop(client):
    while True:
        wait_seconds = seconds_until_next_post()
        print(f"next to-do post in {int(wait_seconds)} seconds")
        time.sleep(wait_seconds)
        post_todo_summary(client)

if __name__ == "__main__":
    print("bot is running!")
    post_todo_summary(app.client) 
    threading.Thread(target=scheduler_loop, args=(app.client,), daemon=True).start()
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()