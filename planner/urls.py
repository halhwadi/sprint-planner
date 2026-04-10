from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('join/', RedirectView.as_view(pattern_name='sm_login'), name='join'),  # legacy redirect
    path('login/', views.sm_login, name='sm_login'),
    path('logout/', views.sm_logout, name='sm_logout'),
    path('board/', views.board, name='board'),
    path('vote/<int:us_id>/', views.vote_room, name='vote_room'),
    path('vote/<int:us_id>/status/', views.vote_status, name='vote_status'),
    path('vote/<int:us_id>/submit/', views.submit_vote, name='submit_vote'),
    # SM
    path('sm/panel/', views.sm_panel, name='sm_panel'),
    path('sm/members/add/', views.add_member, name='add_member'),
    path('sm/members/<int:member_id>/remove/', views.remove_member, name='remove_member'),
    path('sm/streams/add/', views.add_stream, name='add_stream'),
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
