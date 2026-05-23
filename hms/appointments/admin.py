from django.contrib import admin
from .models import AvailabilitySlot, Booking

@admin.register(AvailabilitySlot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'date', 'start_time', 'end_time', 'is_booked')
    list_filter = ('is_booked', 'date')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('pk', 'patient', 'slot', 'status', 'booked_at')
    list_filter = ('status',)
