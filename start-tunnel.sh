#!/bin/bash

# This script starts a Cloudflared Tunnel for the Extras application and logs output to a file
# I (Sling) use this script to run the program automatically with systemd
# This may not work for you. (ex: I have to run it in a python virtual environment, you may not)

cd SpotifyRPC-Extra/

echo "--------------------------" >> ./../logs/tunnel.log
echo "Script started at $(date)" >> ./../logs/tunnel.log
echo "--------------------------" >> ./../logs/tunnel.log
npm run tunnel >> ./../logs/tunnel.log 2>&1
