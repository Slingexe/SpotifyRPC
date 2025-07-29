# Sling's Simple SpotifyRPC  
  
Make a new app on the [Spotify Dev Portal](https://developer.spotify.com/dashboard)  
Copy and paste the ClientID and Secret to the .env file.  
Make sure the app has the Redirect URL in the .env file.  
  
Go to the [Discord Dev Portal](https://discord.com/developers/applications)  
Make a new app, goto the OAuth tab then copy paste the ClientID  
  
Install requirements.txt  
`pip install -r ./requirements.txt`  
  
Run the python script  
`python main.py`  
  
Look at your discord activity :D

## The RPC in action
![Playing from liked songs](https://github.com/Slingexe/SpotifyRPC/blob/main/.github/readme-screenshots/playing1.png)
![Paused from liked songs](https://github.com/Slingexe/SpotifyRPC/blob/main/.github/readme-screenshots/paused1.png)
![Playing from album](https://github.com/Slingexe/SpotifyRPC/blob/main/.github/readme-screenshots/playing-album.png)
![Playing from playlist](https://github.com/Slingexe/SpotifyRPC/blob/main/.github/readme-screenshots/playing-playlist.png)

## Server
When you enable the server, the track data that the application collects will be available at http://localhost:62011/  
  
Example Data from server  
```
{
  "title": "blue",
  "artist": "yung kai",
  "uri": "spotify:track:3be9ACTxtcL6Zm4vJRUiPG",
  "artURL": "https://i.scdn.co/image/ab67616d0000b273373c63a4666fb7193febc167",
  "duration_ms": 214000.0,
  "progress_ms": 200000.0,
  "context_type": "user_collection",
  "context_uri": "spotify:user:kvk5kbs1fav3zndeztxlaeubr:collection",
  "context_name": "Liked Songs"
}
```