import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import SprintMember, UserStory, Vote, StreamAssignment, STREAM_CHOICES

BANDWIDTH_LIMIT = 8


def home(request):
    return redirect('board')


def sm_login(request):
    error = ''
    if request.method == 'POST':
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user and user.is_staff:
            login(request, user)
            # Redirect to member pick so SM can also vote
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

    stories = UserStory.objects.prefetch_related('votes', 'stream_assignments', 'stream_assignments__member').select_related('owner').all()
    all_members = SprintMember.objects.filter(is_active=True).order_by('stream', 'name')

    # bandwidth
    bandwidth = []
    for m in all_members:
        total = m.total_sp()
        bandwidth.append({'member': m, 'total': total, 'over': total > BANDWIDTH_LIMIT})

    return render(request, 'planner/board.html', {
        'stories': stories,
        'member': member,
        'is_sm': is_sm,
        'bandwidth': bandwidth,
        'streams': [s[0] for s in STREAM_CHOICES],
        'all_members': all_members,
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

    return JsonResponse({
        'status': story.voting_status,
        'members': members_status,
        'average': story.vote_average,
        'final_sp': story.final_sp,
        'total_members': all_members.count(),
        'voted_count': len(votes),
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
    stories = UserStory.objects.prefetch_related('stream_assignments__member').select_related('owner').all()
    all_members = SprintMember.objects.filter(is_active=True).order_by('stream', 'name')
    bandwidth = []
    for m in all_members:
        total = m.total_sp()
        bandwidth.append({'member': m, 'total': total, 'over': total > BANDWIDTH_LIMIT})
    return render(request, 'planner/sm_panel.html', {
        'members': members,
        'stories': stories,
        'streams': [s[0] for s in STREAM_CHOICES],
        'all_members': all_members,
        'bandwidth': bandwidth,
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
def add_story(request):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    data = json.loads(request.body)
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    owner_id = data.get('owner_id')
    involved_streams = data.get('involved_streams', [])
    if not title:
        return JsonResponse({'error': 'Title required'}, status=400)
    owner = None
    if owner_id:
        owner = get_object_or_404(SprintMember, id=owner_id)
    story = UserStory.objects.create(
        title=title,
        description=description,
        owner=owner,
        involved_streams=involved_streams,
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
        if data['owner_id']:
            story.owner = get_object_or_404(SprintMember, id=data['owner_id'])
        else:
            story.owner = None
    if 'involved_streams' in data:
        story.involved_streams = data['involved_streams']
    if 'final_sp' in data:
        story.final_sp = data['final_sp']
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
    
    # assign final SP to story (goes to owner)
    if 'final_sp' in data:
        story.final_sp = data['final_sp']
        story.save()

    # assign stream SPs: [{stream, member_id, sp}, ...]
    if 'stream_assignments' in data:
        # clear existing for this story
        story.stream_assignments.all().delete()
        for sa in data['stream_assignments']:
            member = get_object_or_404(SprintMember, id=sa['member_id'])
            StreamAssignment.objects.create(
                user_story=story,
                stream=sa['stream'],
                member=member,
                sp=sa['sp']
            )

    return JsonResponse({'ok': True})


@login_required
@require_POST
def edit_stream_assignment(request, us_id):
    """Edit a single stream assignment SP"""
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
            'id': sa.id,
            'stream': sa.stream,
            'member_id': sa.member_id,
            'member_name': sa.member.name,
            'sp': sa.sp,
        })
    return JsonResponse({
        'id': story.id,
        'title': story.title,
        'description': story.description,
        'owner_id': story.owner_id,
        'owner_name': story.owner.name if story.owner else None,
        'involved_streams': story.involved_streams,
        'final_sp': story.final_sp,
        'voting_status': story.voting_status,
        'vote_average': story.vote_average,
        'stream_assignments': assignments,
    })
