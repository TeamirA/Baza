#!/bin/bash
# Vercel static build: install deps and collect static files into staticfiles/.
set -e
python3 -m pip install -r requirements.txt
python3 manage.py collectstatic --noinput --clear
