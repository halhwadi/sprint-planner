from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('join/', views.join, name='join'),
    path('board/', views.board, name='board'),
    path('login/', views.sm_login, name='sm_login'),
    path('logout/', views.sm_logout, name='sm_logout'),
    path('vote/<int:us_id>/', views.vote_room, name='vote_room'),
    path('vote/<int:us_id>/status/', views.vote_status, name='vote_status'),
    path('vote/<int:us_id>/submit/', views.submit_vote, name='submit_vote'),
    # SM
    path('sm/pick-member/', views.sm_pick_member, name='sm_pick_member'),
    path('sm/members/add/', views.add_member, name='add_member'),
    path('sm/members/<int:member_id>/remove/', views.remove_member, name='remove_member'),
    path('sm/stories/add/', views.add_story, name='add_story'),
    path('sm/stories/<int:us_id>/edit/', views.edit_story, name='edit_story'),
    path('sm/stories/<int:us_id>/delete/', views.delete_story, name='delete_story'),
    path('sm/stories/<int:us_id>/trigger-voting/', views.trigger_voting, name='trigger_voting'),
    path('sm/stories/<int:us_id>/close-voting/', views.close_voting, name='close_voting'),
    path('sm/stories/<int:us_id>/assign-sp/', views.assign_sp, name='assign_sp'),
    path('sm/stories/<int:us_id>/edit-stream-assignment/', views.edit_stream_assignment, name='edit_stream_assignment'),
    path('api/stories/<int:us_id>/', views.get_story_detail, name='story_detail'),
]
