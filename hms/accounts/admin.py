from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, DoctorProfile, PatientProfile

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('role',)
    fieldsets = UserAdmin.fieldsets + (
        ('HMS Role', {'fields': ('role', 'phone', 'google_access_token', 'google_refresh_token', 'google_token_expiry')}),
    )

admin.site.register(DoctorProfile)
admin.site.register(PatientProfile)
