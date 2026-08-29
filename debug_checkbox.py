import os
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from slack_bolt import App

load_dotenv()
CANVAS_ID = "F0BS3TXKSSE"
bot_token = os.getenv("SLACK_BOT_TOKEN")
app = App(token=bot_token)
info = app.client.files_info(file=CANVAS_ID)
download_url = info["file"]["url_private_download"]
resp = requests.get(download_url, headers={"Authorization":f"Bearer {bot_token}"})
soup = BeautifulSoup(resp.text, "html.parser")
container = soup.find(class_="quip-canvas-content") or soup

in_section = False
for child in container.children:
    name = getattr(child, "name", None)
    if name is None:
        continue
    if name in ("h1", "h2", "h3"):
        heading = child.get_text(strip=True).lower()
        if in_section:
            break
        if heading == "to do(doing/urgent)":
            in_section = True
        continue
    if in_section and name == "div":
        print(child.prettify())