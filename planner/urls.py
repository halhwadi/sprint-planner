from django.urls import path
from django.views.generic import RedirectView
from . import views
from . import auth_views

urlpatterns = [
    # ── Auth ──
    path('signup/', auth_views.signup, name='signup'),
    path('login/', auth_views.user_login, name='user_login'),
    path('logout/', auth_views.user_logout, name='user_logout'),
    path('verify-email/sent/', auth_views.verify_email_sent, name='verify_email_sent'),
    path('verify-email/<uuid:token>/', auth_views.verify_email, name='verify_email'),
    path('onboarding/', auth_views.onboarding, name='onboarding'),
    path('password-reset/', auth_views.password_reset_request, name='password_reset_request'),
    path('password-reset/<uuid:token>/', auth_views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/done/', auth_views.password_reset_done, name='password_reset_done'),

    # ── Legacy redirects ──
    path('', RedirectView.as_view(pattern_name='user_login'), name='home'),
    path('join/', RedirectView.as_view(pattern_name='user_login'), name='join'),
    path('sm_login/', RedirectView.as_view(pattern_name='user_login'), name='sm_login'),
    path('sm/pick-member/', RedirectView.as_view(pattern_name='sm_panel'), name='sm_pick_member'),
    path('sm/logout/', RedirectView.as_view(pattern_name='user_logout'), name='sm_logout'),

    # In auth section
    path('select-org/', auth_views.select_org, name='select_org'),
    
    # In invites section
    path('invite/<uuid:token>/', invite_views.accept_invite, name='accept_invite'),
    path('sm/invites/', invite_views.list_invites, name='list_invites'),
    path('sm/invites/send/', invite_views.send_invite, name='send_invite'),
    path('sm/invites/<int:invite_id>/cancel/', invite_views.cancel_invite, name='cancel_invite'),

    # ── App ──
    path('board/', views.board, name='board'),
    path('vote/<int:us_id>/', views.vote_room, name='vote_room'),
    path('vote/<int:us_id>/status/', views.vote_status, name='vote_status'),
    path('vote/<int:us_id>/submit/', views.submit_vote, name='submit_vote'),

    # ── SM ──
    path('sm/panel/', views.sm_panel, name='sm_panel'),
    path('sm/members/add/', views.add_member, name='add_member'),
    path('sm/members/<int:member_id>/remove/', views.remove_member, name='remove_member'),
    path('sm/members/<int:member_id>/role/', views.change_member_role, name='change_member_role'),
    path('sm/streams/add/', views.add_stream, name='add_stream'),
    path('sm/streams/<int:stream_id>/delete/', views.delete_stream, name='delete_stream'),
    path('sm/sprints/add/', views.add_sprint, name='add_sprint'),
    path('sm/sprints/<int:sprint_id>/edit/', views.edit_sprint, name='edit_sprint'),
    path('sm/sprints/<int:sprint_id>/delete/', views.delete_sprint, name='delete_sprint'),
    path('sm/sprints/<int:sprint_id>/export/', views.export_sprint, name='export_sprint'),
    path('sm/sprints/<int:sprint_id>/import/', views.import_stories, name='import_stories'),
    path('sm/stories/add/', views.add_story, name='add_story'),
    path('sm/stories/<int:us_id>/edit/', views.edit_story, name='edit_story'),
    path('sm/stories/<int:us_id>/delete/', views.delete_story, name='delete_story'),
    path('sm/stories/<int:us_id>/trigger-voting/', views.trigger_voting, name='trigger_voting'),
    path('sm/stories/<int:us_id>/close-voting/', views.close_voting, name='close_voting'),
    path('sm/stories/<int:us_id>/assign-sp/', views.assign_sp, name='assign_sp'),
    path('sm/stories/<int:us_id>/edit-stream-assignment/', views.edit_stream_assignment, name='edit_stream_assignment'),
    path('api/stories/<int:us_id>/', views.get_story_detail, name='story_detail'),
]
