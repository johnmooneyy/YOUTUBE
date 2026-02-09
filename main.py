import os, json, pickle, datetime, html, base64
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

# --- CONFIGURATION ---
HISTORY_FILE = 'seen_ids.txt'
DATABASE_FILE = 'jobs.json'

def get_service():
    pickle_data = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not pickle_data:
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                return build('youtube', 'v3', credentials=pickle.load(token))
        raise Exception("CRITICAL: No Login Token Found.")
    creds = pickle.loads(base64.b64decode(pickle_data))
    if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
    return build('youtube', 'v3', credentials=creds)

def process_job(youtube, job, seen_ids):
    print(f"\n[JOB] {job['name']}")
    # Cleanup (Optional: handle errors silently)
    try:
        res = youtube.playlistItems().list(part="id,snippet", playlistId=job['target_playlist'], maxResults=50).execute()
        now = datetime.datetime.utcnow()
        for item in res.get('items', []):
            if (now - datetime.datetime.strptime(item['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")).days >= job.get('purge_after_days', 7):
                youtube.playlistItems().delete(id=item['id']).execute()
    except: pass

    # Scan & Add
    try:
        res = youtube.playlistItems().list(playlistId=job['source_uu_id'], part="snippet,contentDetails", maxResults=20).execute()
    except: return

    for item in res.get('items', []):
        vid = item['contentDetails']['videoId']
        title = html.unescape(item['snippet']['title'])
        # If keywords is empty or contains empty string, match everything
        keywords = job.get('keywords', [])
        match = True if not keywords or "" in keywords else any(k.lower() in title.lower() for k in keywords)
        
        if match and vid not in seen_ids:
            print(f"    [+] Adding: {title[:40]}...")
            try:
                youtube.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": job['target_playlist'], "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
                with open(HISTORY_FILE, 'a') as f: f.write(vid + "\n")
                seen_ids.add(vid)
            except: pass

def main():
    print("--- ENGINE STARTED ---")
    try:
        with open(DATABASE_FILE, 'r') as f: jobs = json.load(f)
    except FileNotFoundError:
        print("ERROR: jobs.json not found.")
        return

    youtube = get_service()
    if not os.path.exists(HISTORY_FILE): open(HISTORY_FILE, 'w').close()
    with open(HISTORY_FILE, 'r') as f: seen_ids = set(f.read().splitlines())

    for job in jobs: process_job(youtube, job, seen_ids)

if __name__ == "__main__":
    main()