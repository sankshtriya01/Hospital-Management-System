from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup_choose, name='signup_choose'),
    path('signup/doctor/', views.doctor_signup, name='doctor_signup'),
    path('signup/patient/', views.patient_signup, name='patient_signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('google/authorize/', views.google_authorize, name='google_authorize'),
    path('oauth2callback/', views.google_oauth_callback, name='google_oauth_callback'),
]
