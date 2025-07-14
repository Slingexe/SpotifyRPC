#!/bin/bash

# This script starts the Spotify RPC application and logs output to a file
# I (Sling) use this script to run the program automatically
# This may not work for you. (ex: I have to run it in a python virtual environment, you may not)

echo "--------------------------" >> output.log
echo "Script started at $(date)" >> output.log
echo "--------------------------" >> output.log

source venv/bin/activate

python -u main.py >> output.log 2>&1
