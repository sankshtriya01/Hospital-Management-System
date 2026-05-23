from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_DOCTOR = 'doctor'
    ROLE_PATIENT = 'patient'
    ROLE_CHOICES = [
        (ROLE_DOCTOR, 'Doctor'),
        (ROLE_PATIENT, 'Patient'),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True)

    # Google OAuth tokens for Calendar integration
    google_access_token = models.TextField(blank=True)
    google_refresh_token = models.TextField(blank=True)
    google_token_expiry = models.DateTimeField(null=True, blank=True)

    @property
    def is_doctor(self):
        return self.role == self.ROLE_DOCTOR

    @property
    def is_patient(self):
        return self.role == self.ROLE_PATIENT

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"


class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    specialization = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"


class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    date_of_birth = models.DateField(null=True, blank=True)
    medical_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Patient: {self.user.get_full_name() or self.user.username}"
