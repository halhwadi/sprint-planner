from django.db import models

STREAM_CHOICES = [
    ('CRM', 'CRM'),
    ('EIP', 'EIP'),
    ('Website', 'Website'),
    ('Mobile', 'Mobile'),
    ('DevOps', 'DevOps'),
    ('SiteCore', 'SiteCore'),
    ('UX', 'UX'),
    ('QA', 'QA'),
]

US_STATUS = [
    ('pending', 'Pending'),
    ('voting', 'Voting Open'),
    ('closed', 'Voting Closed'),
]


class Sprint(models.Model):
    name = models.CharField(max_length=100)  # e.g. "Sprint 42"
    goal = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def total_sp(self):
        return sum(us.final_sp or 0 for us in self.user_stories.filter(final_sp__isnull=False))


class SprintMember(models.Model):
    name = models.CharField(max_length=100, unique=True)
    stream = models.CharField(max_length=20, choices=STREAM_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.stream})"

    def total_sp(self, sprint=None):
        owned_qs = self.owned_stories.filter(final_sp__isnull=False)
        assigned_qs = self.stream_assignments.all()
        if sprint:
            owned_qs = owned_qs.filter(sprint=sprint)
            assigned_qs = assigned_qs.filter(user_story__sprint=sprint)
        return sum(us.final_sp or 0 for us in owned_qs) + sum(a.sp for a in assigned_qs)


class UserStory(models.Model):
    sprint = models.ForeignKey(Sprint, null=True, blank=True, on_delete=models.SET_NULL, related_name='user_stories')
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
