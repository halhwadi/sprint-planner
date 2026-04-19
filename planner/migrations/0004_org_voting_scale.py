from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0003_epic_task_bug_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='voting_scale',
            field=models.CharField(
                choices=[
                    ('fibonacci', 'Fibonacci (1,2,3,5,8,13,21)'),
                    ('modified_fibonacci', 'Modified Fibonacci (1,2,3,5,8,13,21,34,55,89)'),
                    ('powers_of_2', 'Powers of 2 (1,2,4,8,16,32)'),
                ],
                default='fibonacci',
                max_length=30,
            ),
        ),
    ]
