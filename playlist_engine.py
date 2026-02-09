import os, pickle, datetime, html
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# --- SYSTEM SETTINGS ---
# UU ID is the low-cost "Uploads" feed (1 unit vs 100 for search)
TALKSPORT_UPLOADS_ID = "UUWw6scNyopJ0yjMu1SyOEyw" 
CLIENT_SECRETS = 'client_secret_2_386425100288-hgrghjhsugnq2vm2j4650tr4gv23m1r0.apps.googleusercontent.com.json'
TOKEN_FILE = 'token.pickle'
HISTORY_FILE = 'seen_ids.txt'
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# --- LOGIC CONFIGURATION ---
PURGE_DAYS = 3
SCAN_LIMIT = 50

PLAYLIST_JOBS = [
    {"name": "Simon Jordan", "id": "PLoJvzSXcA7j_VONfig9ZksTPYN9Nz090V", "must": ["Jordan", "Simon"]},
    {"name": "Darren Bent", "id": "PLoJvzSXcA7j-NvCUml49Ogaa8R49a5rUp", "must": ["Bent", "Darren"]}
]

def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as t: creds = pickle.load(t)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as t: pickle.dump(creds, t)
    return build('youtube', 'v3', credentials=creds)

def purge_old_items(youtube, playlist_id):
    """Cleans up the playlist. Removes anything added over 3 days ago."""
    res = youtube.playlistItems().list(part="id,snippet", playlistId=playlist_id, maxResults=50).execute()
    now = datetime.datetime.utcnow()
    for item in res.get('items', []):
        added_at = datetime.datetime.strptime(item['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
        if (now - added_at).days >= PURGE_DAYS:
            print(f"  [-] Purging: {item['snippet']['title']}")
            youtube.playlistItems().delete(id=item['id']).execute()

def main():
    youtube = get_service()
    
    # Init history
    if not os.path.exists(HISTORY_FILE): open(HISTORY_FILE, 'w').close()
    with open(HISTORY_FILE, 'r') as f: seen_ids = set(f.read().splitlines())

    # Fetch TalkSport feed (Costs only 1 quota unit)
    print("Scraping TalkSport official uploads...")
    uploads = youtube.playlistItems().list(
        playlistId=TALKSPORT_UPLOADS_ID, 
        part="snippet,contentDetails", 
        maxResults=SCAN_LIMIT
    ).execute()

    for job in PLAYLIST_JOBS:
        print(f"\n--- SYNCING: {job['name']} ---")
        purge_old_items(youtube, job['id'])

        for item in uploads.get('items', []):
            v_id = item['contentDetails']['videoId']
            title = html.unescape(item['snippet']['title'])
            desc = html.unescape(item['snippet'].get('description', ''))
            
            # PRO-MODE: Check Title + Description for match
            match = any(k.lower() in title.lower() or k.lower() in desc.lower() for k in job['must'])

            if match and v_id not in seen_ids:
                print(f"  [+] Adding Hit: {title}")
                try:
                    youtube.playlistItems().insert(
                        part="snippet",
                        body={"snippet": {"playlistId": job['id'], "resourceId": {"kind": "youtube#video", "videoId": v_id}}}
                    ).execute()
                    with open(HISTORY_FILE, 'a') as f: f.write(v_id + "\n")
                    seen_ids.add(v_id)
                except Exception as e:
                    print(f"  [!] API Error: {e}")

    print("\nBatch Complete.")

if __name__ == "__main__":
    main()