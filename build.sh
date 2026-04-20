#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
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
    # Ensure email and active status are set
    user.email      = 'admin@getsprintflow.co'
    user.is_active  = True
    user.first_name = 'Scrum'
    user.last_name  = 'Master'
    user.save()
    print('Superuser updated')

if not Organization.objects.exists():
    org = Organization.objects.create(
        name='SprintFlow Test',
        slug='sprintflow-test',
        owner=user,
        is_test=True,
    )
    Subscription.objects.create(
        organization=org,
        plan='business',
        status='active',
        trial_end=timezone.now() + timedelta(days=36500),
    )
    OrganizationMember.objects.create(
        organization=org,
        user=user,
        role='admin',
    )
    print('Test organization created')
else:
    org = Organization.objects.first()
    if not org.is_test:
        org.is_test = True
        org.save()
        print('Org flagged as test')
    else:
        print('Organization already exists')
"
