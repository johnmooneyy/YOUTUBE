import os, pickle, datetime, html, base64
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# --- CONFIGURATION ---
TALKSPORT_UPLOADS_ID = "UUWw6scNyopJ0yjMu1SyOEyw" 
HISTORY_FILE = 'seen_ids.txt'

PLAYLIST_JOBS = [
    {"name": "Simon Jordan", "id": "PLoJvzSXcA7j_VONfig9ZksTPYN9Nz090V", "must": ["Jordan", "Simon"]},
    {"name": "Darren Bent", "id": "PLoJvzSXcA7j-NvCUml49Ogaa8R49a5rUp", "must": ["Bent", "Darren"]}
]

def get_service():
    # Looks for the secret inside GitHub's secure storage
    pickle_data = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not pickle_data:
        # Fallback for local testing if the secret isn't found
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                return build('youtube', 'v3', credentials=pickle.load(token))
        raise Exception("CRITICAL: No YOUTUBE_TOKEN_PICKLE found. Cannot login.")
    
    # Decodes the secret from GitHub
    creds = pickle.loads(base64.b64decode(pickle_data))
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return build('youtube', 'v3', credentials=creds)

def cleanup(youtube, playlist_id):
    """Deletes videos older than 3 days."""
    try:
        res = youtube.playlistItems().list(part="id,snippet", playlistId=playlist_id, maxResults=50).execute()
        now = datetime.datetime.utcnow()
        for item in res.get('items', []):
            added_at = datetime.datetime.strptime(item['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
            if (now - added_at).days >= 3:
                print(f"  [-] Deleting stale: {item['snippet']['title']}")
                youtube.playlistItems().delete(id=item['id']).execute()
    except Exception as e:
        print(f"  [!] Cleanup Error: {e}")

def main():
    print("--- Starting TalkSport Sync (Cloud Mode) ---")
    youtube = get_service()
    
    # Create history file if missing
    if not os.path.exists(HISTORY_FILE): open(HISTORY_FILE, 'w').close()
    with open(HISTORY_FILE, 'r') as f: seen_ids = set(f.read().splitlines())

    # 1. FETCH UPLOADS (Quota Cost: 1 unit)
    print("Fetching latest uploads...")
    res = youtube.playlistItems().list(
        playlistId=TALKSPORT_UPLOADS_ID, 
        part="snippet,contentDetails", 
        maxResults=50
    ).execute()

    # 2. PROCESS JOBS
    for job in PLAYLIST_JOBS:
        print(f"\nProcessing: {job['name']}")
        cleanup(youtube, job['id'])

        for item in res.get('items', []):
            v_id = item['contentDetails']['videoId']
            title = html.unescape(item['snippet']['title'])
            desc = html.unescape(item['snippet'].get('description', ''))
            
            # Check Title AND Description
            match = any(k.lower() in title.lower() or k.lower() in desc.lower() for k in job['must'])

            if match and v_id not in seen_ids:
                print(f"  [+] Adding: {title}")
                try:
                    youtube.playlistItems().insert(
                        part="snippet",
                        body={"snippet": {"playlistId": job['id'], "resourceId": {"kind": "youtube#video", "videoId": v_id}}}
                    ).execute()
                    with open(HISTORY_FILE, 'a') as f: f.write(v_id + "\n")
                    seen_ids.add(v_id)
                except Exception as e:
                    print(f"  [!] Add Failed: {e}")

    print("\n--- Sync Complete ---")

if __name__ == "__main__":
    main()