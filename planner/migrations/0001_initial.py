from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='owned_orgs', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plan', models.CharField(choices=[('starter', 'Starter'), ('pro', 'Pro'), ('business', 'Business')], default='starter', max_length=20)),
                ('status', models.CharField(choices=[('trialing', 'Trialing'), ('active', 'Active'), ('past_due', 'Past Due'), ('cancelled', 'Cancelled')], default='trialing', max_length=20)),
                ('trial_end', models.DateTimeField()),
                ('paddle_customer_id', models.CharField(blank=True, max_length=200)),
                ('paddle_subscription_id', models.CharField(blank=True, max_length=200)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to='planner.organization')),
            ],
        ),
        migrations.CreateModel(
            name='OrganizationMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('admin', 'Admin'), ('scrum_master', 'Scrum Master'), ('voter', 'Voter'), ('viewer', 'Viewer')], default='voter', max_length=20)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='planner.organization')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='org_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('organization', 'user')},
            },
        ),
        migrations.CreateModel(
            name='Stream',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('order', models.PositiveIntegerField(default=0)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='streams', to='planner.organization')),
            ],
            options={
                'ordering': ['order', 'name'],
                'unique_together': {('organization', 'name')},
            },
        ),
        migrations.CreateModel(
            name='SprintMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sprint_members', to='planner.organization')),
                ('stream', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='members', to='planner.stream')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sprint_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('organization', 'user')},
            },
        ),
        migrations.CreateModel(
            name='Sprint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('goal', models.TextField(blank=True)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sprints', to='planner.organization')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UserStory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('involved_streams', models.JSONField(default=list)),
                ('final_sp', models.FloatField(blank=True, null=True)),
                ('voting_status', models.CharField(choices=[('pending', 'Pending'), ('voting', 'Voting Open'), ('closed', 'Voting Closed')], default='pending', max_length=20)),
                ('vote_average', models.FloatField(blank=True, null=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_stories', to='planner.organization')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_stories', to='planner.sprintmember')),
                ('sprint', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_stories', to='planner.sprint')),
            ],
            options={
                'ordering': ['order', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='Vote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='planner.sprintmember')),
                ('user_story', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='planner.userstory')),
            ],
            options={
                'unique_together': {('user_story', 'member')},
            },
        ),
        migrations.CreateModel(
            name='StreamAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sp', models.FloatField()),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stream_assignments', to='planner.sprintmember')),
                ('stream', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='planner.stream')),
                ('user_story', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stream_assignments', to='planner.userstory')),
            ],
            options={
                'unique_together': {('user_story', 'stream', 'member')},
            },
        ),
        migrations.CreateModel(
            name='EmailVerificationToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='verification_token', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='PasswordResetToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='password_reset_token', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
