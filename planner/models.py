import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─────────────────────────────────────────
# ORGANIZATION
# ─────────────────────────────────────────

class Organization(models.Model):
    name       = models.CharField(max_length=200)
    slug       = models.SlugField(max_length=200, unique=True)
    owner      = models.ForeignKey(User, on_delete=models.PROTECT, related_name='owned_orgs')
    is_test    = models.BooleanField(default=False)  # test accounts bypass billing
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# SUBSCRIPTION
# ─────────────────────────────────────────

class Subscription(models.Model):
    PLAN_CHOICES = [
        ('starter',  'Starter'),
        ('pro',      'Pro'),
        ('business', 'Business'),
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
    trial_end              = models.DateTimeField()
    paddle_customer_id     = models.CharField(max_length=200, blank=True)
    paddle_subscription_id = models.CharField(max_length=200, blank=True)
    ai_calls_used          = models.PositiveIntegerField(default=0)  # resets monthly
    ai_calls_reset_at      = models.DateTimeField(default=timezone.now)
    updated_at             = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization.name} — {self.plan} ({self.status})"

    def is_active(self):
        if self.organization.is_test:
            return True
        if self.status == 'trialing':
            return timezone.now() < self.trial_end
        return self.status == 'active'

    def is_trial(self):
        return self.status == 'trialing' and timezone.now() < self.trial_end

    def days_left_in_trial(self):
        if self.status != 'trialing':
            return 0
        return max(0, (self.trial_end - timezone.now()).days)

    def ai_calls_limit(self):
        """Monthly AI call limit per plan. 0 = not available."""
        limits = {'starter': 0, 'pro': 0, 'business': 500}
        if self.organization.is_test:
            return 99999
        return limits.get(self.plan, 0)

    def ai_calls_remaining(self):
        # Reset counter if new month
        from datetime import timedelta
        if timezone.now() > self.ai_calls_reset_at + timedelta(days=30):
            self.ai_calls_used = 0
            self.ai_calls_reset_at = timezone.now()
            self.save(update_fields=['ai_calls_used', 'ai_calls_reset_at'])
        return max(0, self.ai_calls_limit() - self.ai_calls_used)

    def can_use_ai(self):
        return self.ai_calls_remaining() > 0


# ─────────────────────────────────────────
# ORGANIZATION MEMBER
# ─────────────────────────────────────────

class OrganizationMember(models.Model):
    ROLE_CHOICES = [
        ('admin',        'Admin'),
        ('scrum_master', 'Scrum Master'),
        ('voter',        'Voter'),
        ('viewer',       'Viewer'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='org_memberships')
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
# STREAM
# ─────────────────────────────────────────

class Stream(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='streams')
    name         = models.CharField(max_length=50)
    order        = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('organization', 'name')
        ordering        = ['order', 'name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# TEAM
# ─────────────────────────────────────────

class Team(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='teams')
    name         = models.CharField(max_length=100)
    description  = models.TextField(blank=True)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_teams')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'name')
        ordering        = ['name']

    def __str__(self):
        return f"{self.organization.name} / {self.name}"


# ─────────────────────────────────────────
# SPRINT MEMBER
# ─────────────────────────────────────────

class SprintMember(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='sprint_members')
    team         = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sprint_memberships')
    stream       = models.ForeignKey(Stream, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'user')

    def __str__(self):
        name        = self.user.get_full_name() or self.user.username
        stream_name = self.stream.name if self.stream else '—'
        return f"{name} ({stream_name})"

    def display_name(self):
        return self.user.get_full_name() or self.user.username

    def total_sp(self, sprint=None):
        owned_qs    = self.owned_stories.filter(final_sp__isnull=False)
        assigned_qs = self.stream_assignments.all()
        if sprint:
            owned_qs    = owned_qs.filter(sprint=sprint)
            assigned_qs = assigned_qs.filter(user_story__sprint=sprint)
        return (
            sum(us.final_sp or 0 for us in owned_qs) +
            sum(a.sp for a in assigned_qs)
        )


# ─────────────────────────────────────────
# TAG
# ─────────────────────────────────────────

class Tag(models.Model):
    COLOR_CHOICES = [
        ('indigo', 'Indigo'),
        ('violet', 'Violet'),
        ('green',  'Green'),
        ('amber',  'Amber'),
        ('red',    'Red'),
        ('blue',   'Blue'),
        ('pink',   'Pink'),
        ('gray',   'Gray'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='tags')
    name         = models.CharField(max_length=50)
    color        = models.CharField(max_length=20, choices=COLOR_CHOICES, default='indigo')

    class Meta:
        unique_together = ('organization', 'name')
        ordering        = ['name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────
# SPRINT
# ─────────────────────────────────────────

class Sprint(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='sprints')
    team         = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='sprints')
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
# EPIC
# ─────────────────────────────────────────

class Epic(models.Model):
    STATUS_CHOICES = [
        ('draft',       'Draft'),
        ('in_progress', 'In Progress'),
        ('done',        'Done'),
        ('cancelled',   'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high',     'High'),
        ('medium',   'Medium'),
        ('low',      'Low'),
    ]

    organization      = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='epics')
    team              = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='epics')
    title             = models.CharField(max_length=300)
    description       = models.TextField(blank=True)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority          = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    owner             = models.ForeignKey(SprintMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_epics')
    tags              = models.ManyToManyField(Tag, blank=True, related_name='epics')
    status_changed_at = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            old = Epic.objects.filter(pk=self.pk).values('status').first()
            if old and old['status'] != self.status:
                self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────
# USER STORY
# ─────────────────────────────────────────

class UserStory(models.Model):
    STATUS_CHOICES = [
        ('draft',       'Draft'),
        ('ready',       'Ready'),
        ('pending',     'Pending Estimation'),
        ('voting',      'Voting Open'),
        ('estimated',   'Estimated'),
        ('in_progress', 'In Progress'),
        ('in_review',   'In Review'),
        ('done',        'Done'),
        ('cancelled',   'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high',     'High'),
        ('medium',   'Medium'),
        ('low',      'Low'),
    ]

    organization      = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='user_stories')
    epic              = models.ForeignKey(Epic, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_stories')
    sprint            = models.ForeignKey(Sprint, null=True, blank=True, on_delete=models.SET_NULL, related_name='user_stories')
    title             = models.CharField(max_length=300)
    description       = models.TextField(blank=True)
    owner             = models.ForeignKey(SprintMember, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_stories')
    priority          = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    involved_streams  = models.JSONField(default=list)
    final_sp          = models.FloatField(null=True, blank=True)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    # kept for backward compat with voting views — mirrors status for voting states
    voting_status     = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('voting',  'Voting Open'),
        ('closed',  'Voting Closed'),
    ], default='pending')
    vote_average      = models.FloatField(null=True, blank=True)
    tags              = models.ManyToManyField(Tag, blank=True, related_name='user_stories')
    order             = models.PositiveIntegerField(default=0)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            old = UserStory.objects.filter(pk=self.pk).values('status').first()
            if old and old['status'] != self.status:
                self.status_changed_at = timezone.now()
        # Keep voting_status in sync with status
        if self.status == 'voting':
            self.voting_status = 'voting'
        elif self.status in ('estimated', 'in_progress', 'in_review', 'done'):
            self.voting_status = 'closed'
        else:
            self.voting_status = 'pending'
        super().save(*args, **kwargs)

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
    stream     = models.ForeignKey(Stream, on_delete=models.CASCADE, related_name='assignments')
    member     = models.ForeignKey(SprintMember, on_delete=models.CASCADE, related_name='stream_assignments')
    sp         = models.FloatField()

    class Meta:
        unique_together = ('user_story', 'stream', 'member')


# ─────────────────────────────────────────
# TASK
# ─────────────────────────────────────────

class Task(models.Model):
    STATUS_CHOICES = [
        ('todo',        'To Do'),
        ('in_progress', 'In Progress'),
        ('in_review',   'In Review'),
        ('done',        'Done'),
        ('blocked',     'Blocked'),
        ('cancelled',   'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high',     'High'),
        ('medium',   'Medium'),
        ('low',      'Low'),
    ]
    TYPE_CHOICES = [
        ('backend',  'Backend'),
        ('frontend', 'Frontend'),
        ('qa',       'QA'),
        ('devops',   'DevOps'),
        ('design',   'Design'),
        ('other',    'Other'),
    ]

    organization      = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='tasks')
    user_story        = models.ForeignKey(UserStory, on_delete=models.CASCADE, related_name='tasks')
    title             = models.CharField(max_length=300)
    description       = models.TextField(blank=True)
    task_type         = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other')
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority          = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    assignee          = models.ForeignKey(SprintMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    story_points      = models.FloatField(null=True, blank=True)
    acceptance_criteria = models.TextField(blank=True)
    is_ai_generated   = models.BooleanField(default=False)
    tags              = models.ManyToManyField(Tag, blank=True, related_name='tasks')
    order             = models.PositiveIntegerField(default=0)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            old = Task.objects.filter(pk=self.pk).values('status').first()
            if old and old['status'] != self.status:
                self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────
# BUG
# ─────────────────────────────────────────

class Bug(models.Model):
    STATUS_CHOICES = [
        ('open',        'Open'),
        ('in_progress', 'In Progress'),
        ('in_review',   'In Review'),
        ('resolved',    'Resolved'),
        ('verified',    'Verified'),
        ('closed',      'Closed'),
        ('wont_fix',    "Won't Fix"),
    ]
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high',     'High'),
        ('medium',   'Medium'),
        ('low',      'Low'),
    ]
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high',     'High'),
        ('medium',   'Medium'),
        ('low',      'Low'),
    ]

    organization      = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='bugs')
    user_story        = models.ForeignKey(UserStory, on_delete=models.CASCADE, related_name='bugs')
    title             = models.CharField(max_length=300)
    description       = models.TextField(blank=True)
    steps_to_reproduce = models.TextField(blank=True)
    expected_behavior = models.TextField(blank=True)
    actual_behavior   = models.TextField(blank=True)
    severity          = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    priority          = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    assignee          = models.ForeignKey(SprintMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bugs')
    reported_by       = models.ForeignKey(SprintMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_bugs')
    tags              = models.ManyToManyField(Tag, blank=True, related_name='bugs')
    status_changed_at = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            old = Bug.objects.filter(pk=self.pk).values('status').first()
            if old and old['status'] != self.status:
                self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────
# EMAIL VERIFICATION TOKEN
# ─────────────────────────────────────────

class EmailVerificationToken(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='verification_token')
    token      = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(hours=24)


# ─────────────────────────────────────────
# PASSWORD RESET TOKEN
# ─────────────────────────────────────────

class PasswordResetToken(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_reset_token')
    token      = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(hours=1)


# ─────────────────────────────────────────
# INVITE TOKEN
# ─────────────────────────────────────────

class InviteToken(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('expired',  'Expired'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='invites')
    invited_by   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invites')
    email        = models.EmailField()
    role         = models.CharField(max_length=20, choices=OrganizationMember.ROLE_CHOICES, default='voter')
    team         = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='invites')
    token        = models.UUIDField(default=uuid.uuid4, unique=True)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'email')

    def is_expired(self):
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(days=7)

    def __str__(self):
        return f"Invite to {self.email} @ {self.organization.name}"
