import os, json, pickle, datetime, html, base64
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

# --- CONFIGURATION ---
HISTORY_FILE = 'seen_ids.txt'
DATABASE_FILE = 'jobs.json'
LOG_FILE = 'latest.log'

# Logging Buffer
log_buffer = []

def log(message):
    """Prints to console AND saves to memory."""
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    log_buffer.append(entry)

def get_service():
    pickle_data = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not pickle_data:
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                return build('youtube', 'v3', credentials=pickle.load(token))
        log("CRITICAL: No Login Token Found.")
        raise Exception("No Token")
    creds = pickle.loads(base64.b64decode(pickle_data))
    if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
    return build('youtube', 'v3', credentials=creds)

def process_job(youtube, job, seen_ids):
    log(f"--- JOB: {job['name']} ---")
    
    # Cleanup
    try:
        res = youtube.playlistItems().list(part="id,snippet", playlistId=job['target_playlist'], maxResults=50).execute()
        now = datetime.datetime.utcnow()
        count = 0
        for item in res.get('items', []):
            if (now - datetime.datetime.strptime(item['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")).days >= job.get('purge_after_days', 7):
                youtube.playlistItems().delete(id=item['id']).execute()
                count += 1
        if count > 0: log(f"    Cleaned {count} old videos.")
    except: pass

    # Scan & Add
    try:
        res = youtube.playlistItems().list(playlistId=job['source_uu_id'], part="snippet,contentDetails", maxResults=20).execute()
    except Exception as e: 
        log(f"    Error scanning source: {e}")
        return

    new_count = 0
    for item in res.get('items', []):
        vid = item['contentDetails']['videoId']
        title = html.unescape(item['snippet']['title'])
        keywords = job.get('keywords', [])
        match = True if not keywords or "" in keywords else any(k.lower() in title.lower() for k in keywords)
        
        if match and vid not in seen_ids:
            try:
                youtube.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": job['target_playlist'], "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
                with open(HISTORY_FILE, 'a') as f: f.write(vid + "\n")
                seen_ids.add(vid)
                log(f"    [+] ADDED: {title[:40]}...")
                new_count += 1
            except Exception as e: log(f"    [!] Failed to add: {e}")
    
    if new_count == 0: log("    No new matching videos found.")

def main():
    log("=== ENGINE STARTED ===")
    try:
        with open(DATABASE_FILE, 'r') as f: jobs = json.load(f)
    except:
        log("ERROR: jobs.json missing.")
        return

    try:
        youtube = get_service()
        if not os.path.exists(HISTORY_FILE): open(HISTORY_FILE, 'w').close()
        with open(HISTORY_FILE, 'r') as f: seen_ids = set(f.read().splitlines())

        for job in jobs: process_job(youtube, job, seen_ids)
    except Exception as e:
        log(f"FATAL ERROR: {e}")

    log("=== BATCH COMPLETE ===")
    
    # Save Log to File
    with open(LOG_FILE, 'w') as f:
        f.write("\n".join(log_buffer))

if __name__ == "__main__":
    main()