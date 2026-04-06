from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
# Temporary — kept for views.py compatibility until Task 4
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
# ─────────────────────────────────────────
# ORGANIZATION (Root Tenant)
# ─────────────────────────────────────────

class Organization(models.Model):
    name        = models.CharField(max_length=200)
    slug        = models.SlugField(max_length=200, unique=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='owned_orgs', null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# SUBSCRIPTION (One per Org)
# ─────────────────────────────────────────

class Subscription(models.Model):
    PLAN_CHOICES = [
        ('starter',  'Starter – $12/mo'),
        ('pro',      'Pro – $29/mo'),
        ('business', 'Business – $69/mo'),
    ]
    STATUS_CHOICES = [
        ('trialing',  'Trialing'),
        ('active',    'Active'),
        ('past_due',  'Past Due'),
        ('cancelled', 'Cancelled'),
    ]

    organization           = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='subscription')
    plan                   = models.CharField(max_length=20, choices=PLAN_CHOICES, default='starter')
    status                 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    trial_end              = models.DateTimeField(default=timezone.now)
    paddle_customer_id     = models.CharField(max_length=200, blank=True)
    paddle_subscription_id = models.CharField(max_length=200, blank=True)
    updated_at             = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization.name} — {self.plan} ({self.status})"

    def is_active(self):
        if self.status == 'trialing':
            return timezone.now() < self.trial_end
        return self.status == 'active'

    def is_trial(self):
        return self.status == 'trialing' and timezone.now() < self.trial_end

    def days_left_in_trial(self):
        if self.status != 'trialing':
            return 0
        delta = self.trial_end - timezone.now()
        return max(0, delta.days)


# ─────────────────────────────────────────
# ORGANIZATION MEMBER (User ↔ Org + Role)
# ─────────────────────────────────────────

class OrganizationMember(models.Model):
    ROLE_CHOICES = [
        ('admin',        'Admin'),
        ('scrum_master', 'Scrum Master'),
        ('voter',        'Voter'),
        ('viewer',       'Viewer'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='org_memberships', null=True, blank=True)
    role         = models.CharField(max_length=20, choices=ROLE_CHOICES, default='voter')
    joined_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'user')

    def __str__(self):
        return f"{self.user.email} @ {self.organization.name} ({self.role})"

    def is_admin(self):
        return self.role == 'admin'

    def is_scrum_master(self):
        return self.role in ('admin', 'scrum_master')

    def can_vote(self):
        return self.role in ('admin', 'scrum_master', 'voter')


# ─────────────────────────────────────────
# STREAM (Per-Org, replaces hardcoded list)
# ─────────────────────────────────────────

class Stream(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='streams')
    name         = models.CharField(max_length=50)
    order        = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('organization', 'name')
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.organization.name} / {self.name}"


# ─────────────────────────────────────────
# SPRINT
# ─────────────────────────────────────────

US_STATUS = [
    ('pending', 'Pending'),
    ('voting',  'Voting Open'),
    ('closed',  'Voting Closed'),
]


class Sprint(models.Model):
    models.ForeignKey(
    Organization, on_delete=models.CASCADE, related_name='sprints', null=True, blank=True)
    name         = models.CharField(max_length=100)
    goal         = models.TextField(blank=True)
    start_date   = models.DateField(null=True, blank=True)
    end_date     = models.DateField(null=True, blank=True)
    is_active    = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def total_sp(self):
        return sum(us.final_sp or 0 for us in self.user_stories.filter(final_sp__isnull=False))


# ─────────────────────────────────────────
# SPRINT MEMBER (Participant in a session)
# ─────────────────────────────────────────

class SprintMember(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='sprint_members', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sprint_memberships', null=True, blank=True)
    stream       = models.CharField(max_length=20, blank=True)
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'user')

    def __str__(self):
        stream_name = self.stream.name if self.stream else '—'
        return f"{self.user.get_full_name() or self.user.email} ({stream_name})"

    def total_sp(self, sprint=None):
        owned_qs    = self.owned_stories.filter(final_sp__isnull=False)
        assigned_qs = self.stream_assignments.all()
        if sprint:
            owned_qs    = owned_qs.filter(sprint=sprint)
            assigned_qs = assigned_qs.filter(user_story__sprint=sprint)
        return sum(us.final_sp or 0 for us in owned_qs) + sum(a.sp for a in assigned_qs)


# ─────────────────────────────────────────
# USER STORY
# ─────────────────────────────────────────

class UserStory(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='user_stories', null=True, blank=True)
    sprint          = models.ForeignKey(Sprint, null=True, blank=True, on_delete=models.SET_NULL, related_name='user_stories')
    title           = models.CharField(max_length=300)
    description     = models.TextField(blank=True)
    owner           = models.ForeignKey(SprintMember, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_stories')
    involved_streams = models.JSONField(default=list)
    final_sp        = models.FloatField(null=True, blank=True)
    voting_status   = models.CharField(max_length=20, choices=US_STATUS, default='pending')
    vote_average    = models.FloatField(null=True, blank=True)
    order           = models.PositiveIntegerField(default=0)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title

    def compute_average(self):
        votes = self.votes.all()
        if not votes:
            return None
        return round(sum(v.points for v in votes) / votes.count(), 1)


# ─────────────────────────────────────────
# VOTE
# ─────────────────────────────────────────

class Vote(models.Model):
    user_story = models.ForeignKey(UserStory, on_delete=models.CASCADE, related_name='votes')
    member     = models.ForeignKey(SprintMember, on_delete=models.CASCADE, related_name='votes')
    points     = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_story', 'member')


# ─────────────────────────────────────────
# STREAM ASSIGNMENT
# ─────────────────────────────────────────

class StreamAssignment(models.Model):
    user_story = models.ForeignKey(UserStory, on_delete=models.CASCADE, related_name='stream_assignments')
    stream     = models.CharField(max_length=20)
    member     = models.ForeignKey(SprintMember, on_delete=models.CASCADE, related_name='stream_assignments')
    sp         = models.FloatField()

    class Meta:
        unique_together = ('user_story', 'stream', 'member')
