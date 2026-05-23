#!/bin/bash

# Start email service in background tab
konsole --new-tab -e bash -c "cd $(pwd)/email-service && npm install && npx serverless offline; exec bash" &

sleep 3

# Start Django
cd "$(dirname "$0")/hms"
source venv/bin/activate
set -a; source ../.env; set +a
python manage.py runserver
