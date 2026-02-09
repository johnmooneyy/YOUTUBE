import os, pickle, datetime, html, base64
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

# --- CONTROL PANEL ---
# To get a Source ID: Take a Channel ID (e.g. UUCezIgC97WyCr...) and replace 'UC' with 'UU'
JOBS = [
    {
        "name": "TalkSport - Simon/Jordan",
        "source_uu_id": "UUWw6scNyopJ0yjMu1SyOEyw",  # TalkSport Uploads
        "target_playlist": "PLoJvzSXcA7j_VONfig9ZksTPYN9Nz090V",
        "keywords": ["Jordan", "Simon"],
        "purge_after_days": 3
    },
    {
        "name": "TalkSport - Darren Bent",
        "source_uu_id": "UUWw6scNyopJ0yjMu1SyOEyw",
        "target_playlist": "PLoJvzSXcA7j-NvCUml49Ogaa8R49a5rUp",
        "keywords": ["Bent", "Darren"],
        "purge_after_days": 3
    },
    
    # 1. WHISTLINDIESEL
    # Strategy: He uploads rarely. Get EVERYTHING.
    # Cost: 1 unit to check. 50 units if he actually posts (rare).
    {
        "name": "WhistlinDiesel",
        "source_uu_id": "UUdadyNDkeGg5J12qBsqjGz1g", 
        "target_playlist": "PLoJvzSXcA7j_wyNY5w2sVihebIit2ma-H", 
        "keywords": [""], # Empty string = Matches EVERYTHING he posts
        "purge_after_days": 14 # Keep his stuff longer
    },

    # 2. I DID A THING
    # Strategy: Rare uploader. Get EVERYTHING.
    {
        "name": "I Did A Thing",
        "source_uu_id": "UUJLZe_NoiG0hT7QCX_9vmQA", 
        "target_playlist": "PLoJvzSXcA7j_wyNY5w2sVihebIit2ma-H", 
        "keywords": [""], # Empty string = Match All
        "purge_after_days": 14
    },

    # 3. THE BOYSCAST (Ryan Long)
    # Strategy: He posts a lot of clips. ONLY get full episodes or specific topics.
    # Cost: 1 unit to check. 0 units if no match found.
    {
        "name": "The Boyscast",
        "source_uu_id": "UUzKFvBRI6VT3jYJq6a820nA", 
        "target_playlist": "PLoJvzSXcA7j_wyNY5w2sVihebIit2ma-H", 
        "keywords": ["Episode",], # ONLY adds if title has these words
        "purge_after_days": 3
    }

    # EXAMPLE: Add a new channel like this:
    # {
    #     "name": "Joe Rogan - MMA",
    #     "source_uu_id": "UUzQUP1qoWDoEbmsQxvdjxgQ", # JRE Uploads
    #     "target_playlist": "PL_Your_Playlist_ID_Here",
    #     "keywords": ["MMA", "UFC", "Dana"],
    #     "purge_after_days": 7
    # }
]

HISTORY_FILE = 'seen_ids.txt'

def get_service():
    """Authenticates using GitHub Secrets."""
    pickle_data = os.environ.get("YOUTUBE_TOKEN_PICKLE")
    if not pickle_data:
        # Local fallback
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                return build('youtube', 'v3', credentials=pickle.load(token))
        raise Exception("CRITICAL: No Login Token Found.")
    
    creds = pickle.loads(base64.b64decode(pickle_data))
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return build('youtube', 'v3', credentials=creds)

def clean_playlist(youtube, playlist_id, days):
    """Removes old videos to keep the playlist fresh."""
    try:
        res = youtube.playlistItems().list(part="id,snippet", playlistId=playlist_id, maxResults=50).execute()
        now = datetime.datetime.utcnow()
        for item in res.get('items', []):
            published = item['snippet'].get('publishedAt')
            if not published: continue
            added_at = datetime.datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
            if (now - added_at).days >= days:
                print(f"    [-] Pruning: {item['snippet']['title'][:30]}...")
                youtube.playlistItems().delete(id=item['id']).execute()
    except HttpError as e:
        print(f"    [!] Cleanup skipped (Empty or Error): {e}")

def process_job(youtube, job, seen_ids):
    print(f"\n[JOB] {job['name']}")
    
    # 1. Maintenance
    clean_playlist(youtube, job['target_playlist'], job['purge_after_days'])
    
    # 2. Scan Source (Cost: 1 Unit)
    try:
        res = youtube.playlistItems().list(
            playlistId=job['source_uu_id'],
            part="snippet,contentDetails",
            maxResults=50
        ).execute()
    except HttpError as e:
        print(f"    [!] Failed to scan source: {e}")
        return

    # 3. Filter & Add
    for item in res.get('items', []):
        vid = item['contentDetails']['videoId']
        title = html.unescape(item['snippet']['title'])
        desc = html.unescape(item['snippet'].get('description', ''))
        
        # Match Logic
        match = any(k.lower() in title.lower() or k.lower() in desc.lower() for k in job['keywords'])
        
        if match and vid not in seen_ids:
            print(f"    [+] Adding: {title[:40]}...")
            try:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": job['target_playlist'],
                            "resourceId": {"kind": "youtube#video", "videoId": vid}
                        }
                    }
                ).execute()
                # Update history immediately
                with open(HISTORY_FILE, 'a') as f: f.write(vid + "\n")
                seen_ids.add(vid)
            except HttpError as e:
                print(f"    [!] Add Failed: {e}")

def main():
    print("--- UNIVERSAL PLAYLIST ENGINE STARTING ---")
    youtube = get_service()
    
    if not os.path.exists(HISTORY_FILE): open(HISTORY_FILE, 'w').close()
    with open(HISTORY_FILE, 'r') as f: seen_ids = set(f.read().splitlines())

    for job in JOBS:
        process_job(youtube, job, seen_ids)

    print("\n--- BATCH COMPLETE ---")

if __name__ == "__main__":
    main()