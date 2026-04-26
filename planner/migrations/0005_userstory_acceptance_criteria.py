from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0004_org_voting_scale'),
    ]

    operations = [
        migrations.AddField(
            model_name='userstory',
            name='acceptance_criteria',
            field=models.TextField(blank=True),
        ),
    ]
