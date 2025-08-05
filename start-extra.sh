#!/bin/bash

# This script starts the Spotify RPC Extras application and logs output to a file
# I (Sling) use this script to run the program automatically with systemd
# This may not work for you. (ex: I have to run it in a python virtual environment, you may not)

cd SpotifyRPC-Extra/

echo "--------------------------" >> ./../logs/site.log
echo "Script started at $(date)" >> ./../logs/site.log
echo "--------------------------" >> ./../logs/site.log
npm run start >> ./../logs/site.log 2>&1
