import os
import json
import threading
import requests
import time
import datetime
from bs4 import BeautifulSoup
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

NIGHT_HOUR = 0
NIGHT_MINUTE = 0

STREAK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streak_data.json")

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
        text=":nodnod:"
    )

def fetch_canvas_html(client):
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

def extract_checklists(html_text, heading_text):
    soup = BeautifulSoup(html_text, "html.parser")
    container = soup.find(class_= "quip-canvas-content") or soup

    items = []
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
                classes = li.get("class") or []
                checked = "checked" in classes
                items.append((li.get_text(strip=True), checked))

    return items

def post_todo_summary(client):
    html_text = fetch_canvas_html(client)
    if html_text is None:
        return

    items = extract_checklists(html_text, TODO_HEADING)
    bullets = [text for text, checked in items]

    if not bullets:
        print("the list is empty! :D")
        return

    bullet_lines = "\n".join(f"\u2022 {b}" for b in bullets)
    text = f"wakey wakey <@U07SX29CECA>\n*today's to-dos:*\n{bullet_lines}"

    client.chat_postMessage(channel=CHANNEL_ID, text=text)
    print(f"posted {len(bullets)} to-do bullets")


def load_streak_data():
    if not os.path.exists(STREAK_FILE):
        return {"streak": 0, "last_date": None}
    with open(STREAK_FILE) as f:
        return json.load(f)

def save_streak_data(data):
    with open(STREAK_FILE, "w") as f:
        json.dump(data, f)

def post_night_summary(client):
    data = load_streak_data()
    today_streak = datetime.date.today().isoformat()

    if data.get("last_date") == today_streak:
        print("summary already posted today, skipping")
        return

    html_text = fetch_canvas_html(client)
    if html_text is None:
        return

    items = extract_checklists(html_text, TODO_HEADING)
    checked_items = [text for text, checked in items if checked]

    if checked_items:
        new_streak = data.get("streak", 0) + 1
        bullet_lines = "\n".join(f"\u2022 {t}" for t in checked_items)
        text = (
            f"yippie!!! you did a couple of things today!!\n\n"
            f"{bullet_lines}\n\n"
            f"*streak: {new_streak} day{'s' if new_streak != 1 else ''}*"
        )
    else:
        new_streak = 0
        text = f"aw... nothing done today? you should lock in :c\n\n *streak: {new_streak} days*"

    client.chat_postMessage(channel=CHANNEL_ID, text = text)
    save_streak_data({"streak": new_streak, "last_date": today_streak})
    print(f"posted summary, streak = {new_streak}")

def seconds_until_next_post(hour, minute):
    now = datetime.datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()

def todo_scheduler_loop(client):
    while True:
        wait_seconds = seconds_until_next_post(POST_HOUR, POST_MINUTE)
        print(f"next to-do post in {int(wait_seconds)} seconds")
        time.sleep(wait_seconds)
        post_todo_summary(client)

def night_scheduler_loop(client):
    while True:
        wait_seconds = seconds_until_next_post(NIGHT_HOUR, NIGHT_MINUTE)
        print(f"next summary in {int(wait_seconds)} seconds")
        time.sleep(wait_seconds)
        post_night_summary(client)


if __name__ == "__main__":
    print("bot is running!")
    post_todo_summary(app.client) 
    threading.Thread(target=todo_scheduler_loop, args=(app.client,), daemon=True).start()
    threading.Thread(target=night_scheduler_loop, args=(app.client,), daemon=True).start()
    SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN")).start()