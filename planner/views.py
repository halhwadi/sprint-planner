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
    members = SprintMember.objects.filter(is_active=True).order_by('stream')
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
    members = SprintMember.objects.filter(is_active=True).order_by('stream')
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

    all_members = SprintMember.objects.filter(is_active=True).order_by('stream')

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
    members = SprintMember.objects.filter(is_active=True).order_by('stream')
    sprints = Sprint.objects.all()
    active_sprint = Sprint.objects.filter(is_active=True).first()
    stories = UserStory.objects.prefetch_related('stream_assignments__member').select_related('owner', 'sprint').all()
    all_members = SprintMember.objects.filter(is_active=True).order_by('stream')
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

@login_required
def export_sprint(request, sprint_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from django.http import HttpResponse

    sprint = get_object_or_404(Sprint, id=sprint_id)
    stories = UserStory.objects.filter(sprint=sprint).prefetch_related(
        'stream_assignments__member', 'votes__member'
    ).select_related('owner')

    wb = openpyxl.Workbook()

    # ── Sheet 1: User Stories ──
    ws1 = wb.active
    ws1.title = 'User Stories'

    header_fill = PatternFill('solid', fgColor='4F46E5')
    header_font = Font(bold=True, color='FFFFFF', size=11)
    alt_fill = PatternFill('solid', fgColor='F1F0FF')
    border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC'),
    )

    headers = ['#', 'User Story', 'Description', 'Owner', 'Owner Stream',
               'Involved Streams', 'Vote Average', 'Final SP', 'Voting Status']
    ws1.column_dimensions['A'].width = 5
    ws1.column_dimensions['B'].width = 45
    ws1.column_dimensions['C'].width = 35
    ws1.column_dimensions['D'].width = 20
    ws1.column_dimensions['E'].width = 14
    ws1.column_dimensions['F'].width = 30
    ws1.column_dimensions['G'].width = 14
    ws1.column_dimensions['H'].width = 10
    ws1.column_dimensions['I'].width = 16

    # Sprint info header
    ws1.merge_cells('A1:I1')
    ws1['A1'] = f'Sprint: {sprint.name}'
    ws1['A1'].font = Font(bold=True, size=13, color='1E1B4B')
    ws1['A1'].fill = PatternFill('solid', fgColor='EEF2FF')
    ws1['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws1.row_dimensions[1].height = 28

    if sprint.goal:
        ws1.merge_cells('A2:I2')
        ws1['A2'] = f'Goal: {sprint.goal}'
        ws1['A2'].font = Font(italic=True, color='6366F1')
        ws1['A2'].alignment = Alignment(horizontal='center')

    if sprint.start_date and sprint.end_date:
        ws1.merge_cells('A3:I3')
        ws1['A3'] = f'{sprint.start_date}  →  {sprint.end_date}'
        ws1['A3'].font = Font(color='888888', size=10)
        ws1['A3'].alignment = Alignment(horizontal='center')

    header_row = 5
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=header_row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border
    ws1.row_dimensions[header_row].height = 22

    for i, story in enumerate(stories, 1):
        row = header_row + i
        fill = alt_fill if i % 2 == 0 else None
        values = [
            i,
            story.title,
            story.description or '',
            story.owner.name if story.owner else '—',
            story.owner.stream if story.owner else '—',
            ', '.join(story.involved_streams) if story.involved_streams else '—',
            story.vote_average or '—',
            story.final_sp or '—',
            story.get_voting_status_display(),
        ]
        for col, val in enumerate(values, 1):
            cell = ws1.cell(row=row, column=col, value=val)
            cell.border = border
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            if fill:
                cell.fill = fill
        ws1.row_dimensions[row].height = 18

    # ── Sheet 2: Stream Assignments ──
    ws2 = wb.create_sheet('Stream Assignments')
    ws2.column_dimensions['A'].width = 45
    ws2.column_dimensions['B'].width = 16
    ws2.column_dimensions['C'].width = 22
    ws2.column_dimensions['D'].width = 16
    ws2.column_dimensions['E'].width = 10

    ws2.merge_cells('A1:E1')
    ws2['A1'] = f'Stream SP Assignments — {sprint.name}'
    ws2['A1'].font = Font(bold=True, size=13, color='1E1B4B')
    ws2['A1'].fill = PatternFill('solid', fgColor='EEF2FF')
    ws2['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws2.row_dimensions[1].height = 28

    h2 = ['User Story', 'Stream', 'Assigned To', 'Member Stream', 'SP']
    for col, h in enumerate(h2, 1):
        cell = ws2.cell(row=3, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border

    r = 4
    for story in stories:
        for sa in story.stream_assignments.all():
            fill = alt_fill if r % 2 == 0 else None
            vals = [story.title, sa.stream, sa.member.name, sa.member.stream, sa.sp]
            for col, val in enumerate(vals, 1):
                cell = ws2.cell(row=r, column=col, value=val)
                cell.border = border
                cell.alignment = Alignment(vertical='center')
                if fill:
                    cell.fill = fill
            r += 1

    # ── Sheet 3: Bandwidth Summary ──
    ws3 = wb.create_sheet('Bandwidth Summary')
    ws3.column_dimensions['A'].width = 25
    ws3.column_dimensions['B'].width = 16
    ws3.column_dimensions['C'].width = 14
    ws3.column_dimensions['D'].width = 14
    ws3.column_dimensions['E'].width = 14

    ws3.merge_cells('A1:E1')
    ws3['A1'] = f'Bandwidth Summary — {sprint.name}'
    ws3['A1'].font = Font(bold=True, size=13, color='1E1B4B')
    ws3['A1'].fill = PatternFill('solid', fgColor='EEF2FF')
    ws3['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws3.row_dimensions[1].height = 28

    h3 = ['Member', 'Stream', 'Owned SP', 'Stream SP', 'Total SP']
    for col, h in enumerate(h3, 1):
        cell = ws3.cell(row=3, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border

    members = SprintMember.objects.filter(is_active=True).order_by('stream')
    r = 4
    for m in members:
        owned = sum(us.final_sp or 0 for us in m.owned_stories.filter(final_sp__isnull=False, sprint=sprint))
        assigned = sum(a.sp for a in m.stream_assignments.filter(user_story__sprint=sprint))
        total = owned + assigned
        if total == 0:
            continue
        fill = alt_fill if r % 2 == 0 else None
        over_fill = PatternFill('solid', fgColor='FECACA') if total > 8 else fill
        vals = [m.name, m.stream, owned, assigned, total]
        for col, val in enumerate(vals, 1):
            cell = ws3.cell(row=r, column=col, value=val)
            cell.border = border
            cell.alignment = Alignment(horizontal='center' if col > 2 else 'left', vertical='center')
            if col == 5 and total > 8:
                cell.fill = over_fill
                cell.font = Font(bold=True, color='DC2626')
            elif fill:
                cell.fill = fill
        r += 1

    # Send response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{sprint.name.replace(" ", "_")}_export.xlsx"'
    wb.save(response)
    return response


@login_required
def import_stories(request, sprint_id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    sprint = get_object_or_404(Sprint, id=sprint_id)

    if request.method == 'GET':
        members = SprintMember.objects.filter(is_active=True).order_by('stream')
        return render(request, 'planner/import_stories.html', {
            'sprint': sprint,
            'members': members,
            'streams': [s[0] for s in STREAM_CHOICES],
        })

    # POST — process uploaded file
    import openpyxl
    from io import BytesIO

    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    try:
        wb = openpyxl.load_workbook(BytesIO(excel_file.read()), data_only=True)
        ws = wb.active

        # Read headers from row 1 — normalize to lowercase stripped
        headers = []
        for cell in ws[1]:
            val = str(cell.value).strip().lower() if cell.value else ''
            headers.append(val)

        # Map known column names to indices
        def find_col(candidates):
            for c in candidates:
                for i, h in enumerate(headers):
                    if c in h:
                        return i
            return None

        col_title       = find_col(['title', 'user story', 'story', 'name'])
        col_description = find_col(['description', 'desc', 'detail'])
        col_owner       = find_col(['owner', 'assigned to', 'assignee'])
        col_streams     = find_col(['stream', 'streams', 'involved'])
        col_sp          = find_col(['sp', 'story point', 'points', 'estimate'])

        if col_title is None:
            return JsonResponse({
                'error': 'Could not find a title column. Make sure row 1 has a header like "Title" or "User Story".'
            }, status=400)

        created = 0
        skipped = 0
        errors = []

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            title = row[col_title] if col_title < len(row) else None
            if not title or str(title).strip() == '':
                skipped += 1
                continue

            title = str(title).strip()
            description = ''
            owner = None
            involved_streams = []
            final_sp = None

            if col_description is not None and col_description < len(row):
                val = row[col_description]
                description = str(val).strip() if val else ''

            if col_owner is not None and col_owner < len(row):
                val = row[col_owner]
                if val:
                    owner_name = str(val).strip()
                    try:
                        owner = SprintMember.objects.get(name__iexact=owner_name, is_active=True)
                    except SprintMember.DoesNotExist:
                        errors.append(f'Row {row_num}: Owner "{owner_name}" not found — story created without owner')

            if col_streams is not None and col_streams < len(row):
                val = row[col_streams]
                if val:
                    valid = [s[0] for s in STREAM_CHOICES]
                    raw = [s.strip() for s in str(val).split(',')]
                    involved_streams = [s for s in raw if s in valid]

            if col_sp is not None and col_sp < len(row):
                val = row[col_sp]
                try:
                    final_sp = float(val) if val is not None else None
                except (ValueError, TypeError):
                    final_sp = None

            UserStory.objects.create(
                title=title,
                description=description,
                owner=owner,
                sprint=sprint,
                involved_streams=involved_streams,
                final_sp=final_sp,
                order=UserStory.objects.count(),
            )
            created += 1

        return JsonResponse({
            'ok': True,
            'created': created,
            'skipped': skipped,
            'errors': errors,
            'sprint_name': sprint.name,
        })

    except Exception as e:
        return JsonResponse({'error': f'Failed to read file: {str(e)}'}, status=400)
