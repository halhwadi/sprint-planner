import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import Sprint, SprintMember, UserStory, Vote, StreamAssignment, STREAM_CHOICES

BANDWIDTH_LIMIT = 8


def home(request):
    return redirect('board')


def sm_login(request):
    error = ''
    if request.method == 'POST':
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user and user.is_staff:
            login(request, user)
            return redirect('sm_pick_member')
        error = 'Invalid credentials or not a Scrum Master.'
    return render(request, 'planner/login.html', {'error': error})


def sm_logout(request):
    logout(request)
    request.session.flush()
    return redirect('join')


@login_required
def sm_pick_member(request):
    """After SM login, SM picks which team member they are so they can vote."""
    if not request.user.is_staff:
        return redirect('board')
    error = ''
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        if member_id == 'skip':
            return redirect('sm_panel')
        try:
            member = SprintMember.objects.get(id=member_id, is_active=True)
            request.session['member_id'] = member.id
            request.session['member_name'] = member.name
            return redirect('sm_panel')
        except SprintMember.DoesNotExist:
            error = 'Please select a valid team member.'
    members = SprintMember.objects.filter(is_active=True).order_by('stream', 'name')
    return render(request, 'planner/sm_pick_member.html', {'members': members, 'error': error})


def join(request):
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        try:
            member = SprintMember.objects.get(id=member_id, is_active=True)
            request.session['member_id'] = member.id
            request.session['member_name'] = member.name
            return redirect('board')
        except SprintMember.DoesNotExist:
            pass
    members = SprintMember.objects.filter(is_active=True).order_by('stream', 'name')
    return render(request, 'planner/join.html', {'members': members})


def board(request):
    member_id = request.session.get('member_id')
    is_sm = request.user.is_authenticated and request.user.is_staff
    if not member_id and not is_sm:
        return redirect('join')

    member = None
    if member_id:
        try:
            member = SprintMember.objects.get(id=member_id)
        except SprintMember.DoesNotExist:
            return redirect('join')

    # Sprint filter
    sprints = Sprint.objects.all()
    active_sprint = Sprint.objects.filter(is_active=True).first()
    
    sprint_id = request.GET.get('sprint')
    selected_sprint = None
    if sprint_id:
        selected_sprint = get_object_or_404(Sprint, id=sprint_id)
    elif active_sprint:
        selected_sprint = active_sprint

    stories_qs = UserStory.objects.prefetch_related(
        'votes', 'stream_assignments', 'stream_assignments__member'
    ).select_related('owner', 'sprint')

    if selected_sprint:
        stories = stories_qs.filter(sprint=selected_sprint)
    else:
        stories = stories_qs.all()

    all_members = SprintMember.objects.filter(is_active=True).order_by('stream', 'name')

    bandwidth = []
    for m in all_members:
        total = m.total_sp(sprint=selected_sprint)
        bandwidth.append({'member': m, 'total': total, 'over': total > BANDWIDTH_LIMIT})

    return render(request, 'planner/board.html', {
        'stories': stories,
        'member': member,
        'is_sm': is_sm,
        'bandwidth': bandwidth,
        'streams': [s[0] for s in STREAM_CHOICES],
        'all_members': all_members,
        'sprints': sprints,
        'selected_sprint': selected_sprint,
        'active_sprint': active_sprint,
    })


def vote_room(request, us_id):
    story = get_object_or_404(UserStory, id=us_id)
    member_id = request.session.get('member_id')
    is_sm = request.user.is_authenticated and request.user.is_staff

    if not member_id and not is_sm:
        return redirect('join')

    member = None
    if member_id:
        try:
            member = SprintMember.objects.get(id=member_id)
        except SprintMember.DoesNotExist:
            return redirect('join')

    all_members = SprintMember.objects.filter(is_active=True)
    fibonacci = [1, 2, 3, 5, 8, 13]

    my_vote = None
    if member:
        try:
            my_vote = Vote.objects.get(user_story=story, member=member)
        except Vote.DoesNotExist:
            pass

    return render(request, 'planner/vote.html', {
        'story': story,
        'member': member,
        'is_sm': is_sm,
        'fibonacci': fibonacci,
        'my_vote': my_vote,
        'all_members': all_members,
        'streams': [s[0] for s in STREAM_CHOICES],
    })


def vote_status(request, us_id):
    story = get_object_or_404(UserStory, id=us_id)
    all_members = SprintMember.objects.filter(is_active=True)
    votes = {v.member_id: v.points for v in story.votes.all()}

    members_status = []
    for m in all_members:
        members_status.append({
            'id': m.id,
            'name': m.name,
            'stream': m.stream,
            'voted': m.id in votes,
            'points': votes.get(m.id) if story.voting_status == 'closed' else None,
        })

    # Per-stream averages (only streams that have at least one vote)
    stream_averages = []
    if story.voting_status == 'closed' and votes:
        from collections import defaultdict
        stream_votes = defaultdict(list)
        for m in all_members:
            if m.id in votes:
                stream_votes[m.stream].append(votes[m.id])
        for stream, points in sorted(stream_votes.items()):
            stream_averages.append({
                'stream': stream,
                'average': round(sum(points) / len(points), 1),
                'votes': len(points),
            })

    return JsonResponse({
        'status': story.voting_status,
        'members': members_status,
        'average': story.vote_average,
        'final_sp': story.final_sp,
        'total_members': all_members.count(),
        'voted_count': len(votes),
        'stream_averages': stream_averages,
    })


@require_POST
def submit_vote(request, us_id):
    story = get_object_or_404(UserStory, id=us_id)
    member_id = request.session.get('member_id')
    if not member_id:
        return JsonResponse({'error': 'Not identified'}, status=403)
    if story.voting_status != 'voting':
        return JsonResponse({'error': 'Voting not open'}, status=400)

    data = json.loads(request.body)
    points = int(data.get('points'))
    if points not in [1, 2, 3, 5, 8, 13]:
        return JsonResponse({'error': 'Invalid points'}, status=400)

    member = get_object_or_404(SprintMember, id=member_id)
    Vote.objects.update_or_create(user_story=story, member=member, defaults={'points': points})
    return JsonResponse({'ok': True})


# ---- SM VIEWS ----

@login_required
def sm_panel(request):
    if not request.user.is_staff:
        return redirect('board')
    members = SprintMember.objects.filter(is_active=True).order_by('stream', 'name')
    sprints = Sprint.objects.all()
    active_sprint = Sprint.objects.filter(is_active=True).first()
    stories = UserStory.objects.prefetch_related('stream_assignments__member').select_related('owner', 'sprint').all()
    all_members = SprintMember.objects.filter(is_active=True).order_by('stream', 'name')
    bandwidth = []
    for m in all_members:
        total = m.total_sp(sprint=active_sprint)
        bandwidth.append({'member': m, 'total': total, 'over': total > BANDWIDTH_LIMIT})
    return render(request, 'planner/sm_panel.html', {
        'members': members,
        'stories': stories,
        'streams': [s[0] for s in STREAM_CHOICES],
        'all_members': all_members,
        'bandwidth': bandwidth,
        'sprints': sprints,
        'active_sprint': active_sprint,
    })


@login_required
@require_POST
def add_member(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    name = request.POST.get('name', '').strip()
    stream = request.POST.get('stream', '')
    if not name or stream not in [s[0] for s in STREAM_CHOICES]:
        return JsonResponse({'error': 'Invalid data'}, status=400)
    member, created = SprintMember.objects.get_or_create(name=name, defaults={'stream': stream})
    if not created:
        member.stream = stream
        member.is_active = True
        member.save()
    return JsonResponse({'ok': True, 'id': member.id, 'name': member.name, 'stream': member.stream})


@login_required
@require_POST
def remove_member(request, member_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    member = get_object_or_404(SprintMember, id=member_id)
    member.is_active = False
    member.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def add_sprint(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Sprint name required'}, status=400)
    sprint = Sprint.objects.create(
        name=name,
        goal=data.get('goal', ''),
        start_date=data.get('start_date') or None,
        end_date=data.get('end_date') or None,
        is_active=data.get('is_active', False),
    )
    # if set as active, deactivate others
    if sprint.is_active:
        Sprint.objects.exclude(id=sprint.id).update(is_active=False)
    return JsonResponse({'ok': True, 'id': sprint.id, 'name': sprint.name})


@login_required
@require_POST
def edit_sprint(request, sprint_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    sprint = get_object_or_404(Sprint, id=sprint_id)
    data = json.loads(request.body)
    if 'name' in data:
        sprint.name = data['name']
    if 'goal' in data:
        sprint.goal = data['goal']
    if 'start_date' in data:
        sprint.start_date = data['start_date'] or None
    if 'end_date' in data:
        sprint.end_date = data['end_date'] or None
    if 'is_active' in data:
        sprint.is_active = data['is_active']
        if sprint.is_active:
            Sprint.objects.exclude(id=sprint.id).update(is_active=False)
    sprint.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def delete_sprint(request, sprint_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    sprint = get_object_or_404(Sprint, id=sprint_id)
    sprint.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def add_story(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body)
    title = data.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'Title required'}, status=400)
    owner = None
    if data.get('owner_id'):
        owner = get_object_or_404(SprintMember, id=data['owner_id'])
    sprint = None
    if data.get('sprint_id'):
        sprint = get_object_or_404(Sprint, id=data['sprint_id'])
    story = UserStory.objects.create(
        title=title,
        description=data.get('description', ''),
        owner=owner,
        sprint=sprint,
        involved_streams=data.get('involved_streams', []),
        order=UserStory.objects.count()
    )
    return JsonResponse({'ok': True, 'id': story.id})


@login_required
@require_POST
def edit_story(request, us_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    story = get_object_or_404(UserStory, id=us_id)
    data = json.loads(request.body)
    if 'title' in data:
        story.title = data['title']
    if 'description' in data:
        story.description = data['description']
    if 'owner_id' in data:
        story.owner = get_object_or_404(SprintMember, id=data['owner_id']) if data['owner_id'] else None
    if 'involved_streams' in data:
        story.involved_streams = data['involved_streams']
    if 'final_sp' in data:
        story.final_sp = data['final_sp']
    if 'sprint_id' in data:
        story.sprint = get_object_or_404(Sprint, id=data['sprint_id']) if data['sprint_id'] else None
    story.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def delete_story(request, us_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    story = get_object_or_404(UserStory, id=us_id)
    story.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def trigger_voting(request, us_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    story = get_object_or_404(UserStory, id=us_id)
    story.voting_status = 'voting'
    story.votes.all().delete()
    story.vote_average = None
    story.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def close_voting(request, us_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    story = get_object_or_404(UserStory, id=us_id)
    story.voting_status = 'closed'
    story.vote_average = story.compute_average()
    story.save()
    return JsonResponse({'ok': True, 'average': story.vote_average})


@login_required
@require_POST
def assign_sp(request, us_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    story = get_object_or_404(UserStory, id=us_id)
    data = json.loads(request.body)
    if 'final_sp' in data:
        story.final_sp = data['final_sp']
        story.save()
    if 'stream_assignments' in data:
        story.stream_assignments.all().delete()
        for sa in data['stream_assignments']:
            member = get_object_or_404(SprintMember, id=sa['member_id'])
            StreamAssignment.objects.create(
                user_story=story, stream=sa['stream'], member=member, sp=sa['sp']
            )
    return JsonResponse({'ok': True})


@login_required
@require_POST
def edit_stream_assignment(request, us_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body)
    sa = get_object_or_404(StreamAssignment, id=data['assignment_id'])
    sa.sp = data['sp']
    sa.save()
    return JsonResponse({'ok': True})


def get_story_detail(request, us_id):
    story = get_object_or_404(UserStory, id=us_id)
    assignments = []
    for sa in story.stream_assignments.select_related('member').all():
        assignments.append({
            'id': sa.id, 'stream': sa.stream,
            'member_id': sa.member_id, 'member_name': sa.member.name, 'sp': sa.sp,
        })
    return JsonResponse({
        'id': story.id, 'title': story.title, 'description': story.description,
        'owner_id': story.owner_id, 'owner_name': story.owner.name if story.owner else None,
        'involved_streams': story.involved_streams, 'final_sp': story.final_sp,
        'voting_status': story.voting_status, 'vote_average': story.vote_average,
        'sprint_id': story.sprint_id, 'stream_assignments': assignments,
    })
