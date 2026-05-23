from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    # Doctor
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/slots/add/', views.add_slot, name='add_slot'),
    path('doctor/slots/<int:slot_id>/edit/', views.edit_slot, name='edit_slot'),
    path('doctor/slots/<int:slot_id>/delete/', views.delete_slot, name='delete_slot'),
    # Patient
    path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('patient/doctors/', views.doctor_list, name='doctor_list'),
    path('patient/doctors/<int:doctor_id>/slots/', views.doctor_slots, name='doctor_slots'),
    path('patient/book/<int:slot_id>/', views.book_slot, name='book_slot'),
]
