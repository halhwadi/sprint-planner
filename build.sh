#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
# Create superuser if not exists
python manage.py shell << PYEOF
from django.contrib.auth.models import User
if not User.objects.filter(username='scrummaster').exists():
    User.objects.create_superuser('scrummaster', '', 'Sprint@2024')
    print('Superuser created')
else:
    print('Superuser already exists')
PYEOF
