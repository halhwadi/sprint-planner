#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py makemigrations planner --noinput
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py shell -c "
from django.contrib.auth.models import User
from planner.models import Organization, Subscription, OrganizationMember
from django.utils import timezone
from datetime import timedelta

if not User.objects.filter(username='scrummaster').exists():
    user = User.objects.create_superuser(
        username='scrummaster',
        email='admin@getsprintflow.co',
        password='Sprint@2024',
        first_name='Scrum',
        last_name='Master',
        is_active=True,
    )
    print('Superuser created')
else:
    user = User.objects.get(username='scrummaster')
    print('Superuser already exists')

if not Organization.objects.exists():
    org = Organization.objects.create(
        name='SprintFlow',
        slug='sprintflow',
        owner=user,
    )
    Subscription.objects.create(
        organization=org,
        plan='pro',
        status='trialing',
        trial_end=timezone.now() + timedelta(days=14),
    )
    OrganizationMember.objects.create(
        organization=org,
        user=user,
        role='admin',
    )
    print('Default organization created')
else:
    print('Organization already exists')
"
