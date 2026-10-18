import json, os, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

KEY = os.environ["YT_API_KEY"]
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"

def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.read()

def api(path, **params):
    params["key"] = KEY
    url = "https://www.googleapis.com/youtube/v3/" + path + "?" + urllib.parse.urlencode(params)
    return json.loads(fetch(url))

handles = json.load(open("creators.json"))
try:
    old = json.load(open("live.json"))
except Exception:
    old = {"creators": []}
known = {c["handle"].lower(): c for c in old.get("creators", [])}

# 1. Look up each channel once (id, name, picture) and remember it
creators = []
for h in handles:
    c = known.get(h.lower())
    if not c or not c.get("id"):
        try:
            items = api("channels", part="snippet", forHandle=h).get("items", [])
        except Exception:
            items = []
        if not items:
            print("Channel not found:", h)
            continue
        s = items[0]["snippet"]
        c = {"handle": h, "id": items[0]["id"], "name": s["title"],
             "avatar": s["thumbnails"]["default"]["url"],
             "live": False, "videoId": None, "title": None}
    c["handle"] = h
    creators.append(c)

# 2. Free check: recent uploads/streams from each channel's public feed
recent = {}
for c in creators:
    try:
        root = ET.fromstring(fetch("https://www.youtube.com/feeds/videos.xml?channel_id=" + c["id"]))
        recent[c["id"]] = [e.find(YT + "videoId").text for e in root.findall(ATOM + "entry")][:8]
    except Exception:
        recent[c["id"]] = None  # feed failed: keep the previous status

# 3. Ask YouTube which of those videos are live right now (1 quota unit per 50 videos)
ids = sorted({v for vs in recent.values() if vs for v in vs})
live_videos = {}
for i in range(0, len(ids), 50):
    for v in api("videos", part="snippet", id=",".join(ids[i:i+50])).get("items", []):
        if v["snippet"].get("liveBroadcastContent") == "live":
            live_videos[v["id"]] = v["snippet"]["title"]

for c in creators:
    vs = recent[c["id"]]
    if vs is None:
        continue
    hit = next((v for v in vs if v in live_videos), None)
    c["live"] = hit is not None
    c["videoId"] = hit
    c["title"] = live_videos.get(hit)

new = {"creators": creators}
if json.dumps(new, sort_keys=True) != json.dumps(old, sort_keys=True):
    json.dump(new, open("live.json", "w"), indent=2)
    print("Updated live.json")
else:
    print("No change")
