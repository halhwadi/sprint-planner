from django.db import models

STREAM_CHOICES = [
    ('CRM', 'CRM'),
    ('EIP', 'EIP'),
    ('Website', 'Website'),
    ('Mobile', 'Mobile'),
    ('DevOps', 'DevOps'),
    ('SiteCore', 'SiteCore'),
    ('UX', 'UX'),
]

US_STATUS = [
    ('pending', 'Pending'),
    ('voting', 'Voting Open'),
    ('closed', 'Voting Closed'),
]


class SprintMember(models.Model):
    name = models.CharField(max_length=100, unique=True)
    stream = models.CharField(max_length=20, choices=STREAM_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.stream})"

    def total_sp(self):
        owned = sum(us.final_sp or 0 for us in self.owned_stories.filter(final_sp__isnull=False))
        stream_assigned = sum(a.sp for a in self.stream_assignments.all())
        return owned + stream_assigned


class UserStory(models.Model):
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(SprintMember, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_stories')
    involved_streams = models.JSONField(default=list)
    final_sp = models.FloatField(null=True, blank=True)
    voting_status = models.CharField(max_length=20, choices=US_STATUS, default='pending')
    vote_average = models.FloatField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title

    def compute_average(self):
        votes = self.votes.all()
        if not votes:
            return None
        return round(sum(v.points for v in votes) / votes.count(), 1)


class Vote(models.Model):
    user_story = models.ForeignKey(UserStory, on_delete=models.CASCADE, related_name='votes')
    member = models.ForeignKey(SprintMember, on_delete=models.CASCADE, related_name='votes')
    points = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_story', 'member')


class StreamAssignment(models.Model):
    user_story = models.ForeignKey(UserStory, on_delete=models.CASCADE, related_name='stream_assignments')
    stream = models.CharField(max_length=20, choices=STREAM_CHOICES)
    member = models.ForeignKey(SprintMember, on_delete=models.CASCADE, related_name='stream_assignments')
    sp = models.FloatField()

    class Meta:
        unique_together = ('user_story', 'stream', 'member')
