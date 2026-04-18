import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0002_team_invitetoken'),
    ]

    operations = [
        # is_test on Organization
        migrations.AddField(
            model_name='organization',
            name='is_test',
            field=models.BooleanField(default=False),
        ),

        # AI tracking on Subscription
        migrations.AddField(
            model_name='subscription',
            name='ai_calls_used',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='subscription',
            name='ai_calls_reset_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),

        # Tag model
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('color', models.CharField(choices=[('indigo','Indigo'),('violet','Violet'),('green','Green'),('amber','Amber'),('red','Red'),('blue','Blue'),('pink','Pink'),('gray','Gray')], default='indigo', max_length=20)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='planner.organization')),
            ],
            options={'ordering': ['name'], 'unique_together': {('organization', 'name')}},
        ),

        # Epic model
        migrations.CreateModel(
            name='Epic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('draft','Draft'),('in_progress','In Progress'),('done','Done'),('cancelled','Cancelled')], default='draft', max_length=20)),
                ('priority', models.CharField(choices=[('critical','Critical'),('high','High'),('medium','Medium'),('low','Low')], default='medium', max_length=20)),
                ('status_changed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='epics', to='planner.organization')),
                ('team', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='epics', to='planner.team')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owned_epics', to='planner.sprintmember')),
                ('tags', models.ManyToManyField(blank=True, related_name='epics', to='planner.tag')),
            ],
            options={'ordering': ['-created_at']},
        ),

        # Add new fields to UserStory
        migrations.AddField(
            model_name='userstory',
            name='epic',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_stories', to='planner.epic'),
        ),
        migrations.AddField(
            model_name='userstory',
            name='priority',
            field=models.CharField(choices=[('critical','Critical'),('high','High'),('medium','Medium'),('low','Low')], default='medium', max_length=20),
        ),
        migrations.AddField(
            model_name='userstory',
            name='status',
            field=models.CharField(choices=[('draft','Draft'),('ready','Ready'),('pending','Pending Estimation'),('voting','Voting Open'),('estimated','Estimated'),('in_progress','In Progress'),('in_review','In Review'),('done','Done'),('cancelled','Cancelled')], default='draft', max_length=20),
        ),
        migrations.AddField(
            model_name='userstory',
            name='status_changed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userstory',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='userstory',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='user_stories', to='planner.tag'),
        ),

        # Task model
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('task_type', models.CharField(choices=[('backend','Backend'),('frontend','Frontend'),('qa','QA'),('devops','DevOps'),('design','Design'),('other','Other')], default='other', max_length=20)),
                ('status', models.CharField(choices=[('todo','To Do'),('in_progress','In Progress'),('in_review','In Review'),('done','Done'),('blocked','Blocked'),('cancelled','Cancelled')], default='todo', max_length=20)),
                ('priority', models.CharField(choices=[('critical','Critical'),('high','High'),('medium','Medium'),('low','Low')], default='medium', max_length=20)),
                ('story_points', models.FloatField(blank=True, null=True)),
                ('acceptance_criteria', models.TextField(blank=True)),
                ('is_ai_generated', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('status_changed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='planner.organization')),
                ('user_story', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='planner.userstory')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_tasks', to='planner.sprintmember')),
                ('tags', models.ManyToManyField(blank=True, related_name='tasks', to='planner.tag')),
            ],
            options={'ordering': ['order', 'created_at']},
        ),

        # Bug model
        migrations.CreateModel(
            name='Bug',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('steps_to_reproduce', models.TextField(blank=True)),
                ('expected_behavior', models.TextField(blank=True)),
                ('actual_behavior', models.TextField(blank=True)),
                ('severity', models.CharField(choices=[('critical','Critical'),('high','High'),('medium','Medium'),('low','Low')], default='medium', max_length=20)),
                ('priority', models.CharField(choices=[('critical','Critical'),('high','High'),('medium','Medium'),('low','Low')], default='medium', max_length=20)),
                ('status', models.CharField(choices=[('open','Open'),('in_progress','In Progress'),('in_review','In Review'),('resolved','Resolved'),('verified','Verified'),('closed','Closed'),('wont_fix',"Won't Fix")], default='open', max_length=20)),
                ('status_changed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bugs', to='planner.organization')),
                ('user_story', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bugs', to='planner.userstory')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_bugs', to='planner.sprintmember')),
                ('reported_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reported_bugs', to='planner.sprintmember')),
                ('tags', models.ManyToManyField(blank=True, related_name='bugs', to='planner.tag')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
