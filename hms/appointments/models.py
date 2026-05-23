from django.db import models
from django.utils import timezone
from accounts.models import User


class AvailabilitySlot(models.Model):
    """
    A single time window that a doctor declares they are available.
    Once booked, is_booked=True and the slot is hidden from other patients.
    """
    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='availability_slots',
        limit_choices_to={'role': 'doctor'},
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']
        # A doctor cannot have two slots with identical date+start_time
        unique_together = ('doctor', 'date', 'start_time')

    @property
    def is_future(self):
        slot_dt = timezone.datetime.combine(self.date, self.start_time)
        slot_dt = timezone.make_aware(slot_dt)
        return slot_dt > timezone.now()

    def __str__(self):
        return f"{self.doctor} | {self.date} {self.start_time}-{self.end_time}"


class Booking(models.Model):
    """
    Records a confirmed appointment between a patient and a doctor's slot.
    """
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    slot = models.OneToOneField(
        AvailabilitySlot,
        on_delete=models.CASCADE,
        related_name='booking',
    )
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookings',
        limit_choices_to={'role': 'patient'},
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)
    booked_at = models.DateTimeField(auto_now_add=True)

    # Google Calendar event IDs (populated after calendar event creation)
    doctor_calendar_event_id = models.CharField(max_length=255, blank=True)
    patient_calendar_event_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-booked_at']

    def __str__(self):
        return f"Booking #{self.pk}: {self.patient} → {self.slot}"
