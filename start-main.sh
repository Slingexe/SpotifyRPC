#!/bin/bash

# This script starts the Spotify RPC application and logs output to a file
# I (Sling) use this script to run the program automatically with systemd
# This may not work for you. (ex: I have to run it in a python virtual environment, you may not)

source venv/bin/activate

echo "--------------------------" >> ./logs/rpc.log
echo "Script started at $(date)" >> ./logs/rpc.log
echo "--------------------------" >> ./logs/rpc.log
python -u main.py >> ./logs/rpc.log 2>&1
