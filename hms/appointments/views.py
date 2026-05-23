import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User
from notifications.service import trigger_email

from .calendar_service import create_calendar_event
from .forms import AvailabilitySlotForm
from .models import AvailabilitySlot, Booking

logger = logging.getLogger(__name__)


# ─── Role guards ──────────────────────────────────────────────────────────────

def doctor_required(view_func):
    """Decorator: only allows users with role=doctor."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_doctor:
            messages.error(request, 'Access denied — doctors only.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def patient_required(view_func):
    """Decorator: only allows users with role=patient."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_patient:
            messages.error(request, 'Access denied — patients only.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── Shared dashboard ─────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    if request.user.is_doctor:
        return redirect('doctor_dashboard')
    return redirect('patient_dashboard')


# ─── Doctor views ─────────────────────────────────────────────────────────────

@doctor_required
def doctor_dashboard(request):
    slots = AvailabilitySlot.objects.filter(doctor=request.user).order_by('date', 'start_time')
    return render(request, 'appointments/doctor_dashboard.html', {'slots': slots})


@doctor_required
def add_slot(request):
    if request.method == 'POST':
        form = AvailabilitySlotForm(request.POST)
        if form.is_valid():
            slot = form.save(commit=False)
            slot.doctor = request.user
            slot.save()
            messages.success(request, f'Slot {slot.date} {slot.start_time}–{slot.end_time} added.')
            return redirect('doctor_dashboard')
    else:
        form = AvailabilitySlotForm()
    return render(request, 'appointments/slot_form.html', {'form': form, 'action': 'Add'})


@doctor_required
def edit_slot(request, slot_id):
    slot = get_object_or_404(AvailabilitySlot, pk=slot_id, doctor=request.user)
    if slot.is_booked:
        messages.error(request, 'Cannot edit a booked slot.')
        return redirect('doctor_dashboard')
    if request.method == 'POST':
        form = AvailabilitySlotForm(request.POST, instance=slot)
        if form.is_valid():
            form.save()
            messages.success(request, 'Slot updated.')
            return redirect('doctor_dashboard')
    else:
        form = AvailabilitySlotForm(instance=slot)
    return render(request, 'appointments/slot_form.html', {'form': form, 'action': 'Edit', 'slot': slot})


@doctor_required
@require_POST
def delete_slot(request, slot_id):
    slot = get_object_or_404(AvailabilitySlot, pk=slot_id, doctor=request.user)
    if slot.is_booked:
        messages.error(request, 'Cannot delete a booked slot.')
    else:
        slot.delete()
        messages.success(request, 'Slot deleted.')
    return redirect('doctor_dashboard')


# ─── Patient views ────────────────────────────────────────────────────────────

@patient_required
def patient_dashboard(request):
    my_bookings = Booking.objects.filter(
        patient=request.user,
        status=Booking.STATUS_CONFIRMED,
    ).select_related('slot', 'slot__doctor')
    return render(request, 'appointments/patient_dashboard.html', {'my_bookings': my_bookings})


@patient_required
def doctor_list(request):
    doctors = User.objects.filter(role=User.ROLE_DOCTOR)
    return render(request, 'appointments/doctor_list.html', {'doctors': doctors})


@patient_required
def doctor_slots(request, doctor_id):
    """Show a specific doctor's future, unbooked slots."""
    doctor = get_object_or_404(User, pk=doctor_id, role=User.ROLE_DOCTOR)
    from django.utils import timezone
    today = timezone.now().date()
    slots = AvailabilitySlot.objects.filter(
        doctor=doctor,
        is_booked=False,
        date__gte=today,
    ).order_by('date', 'start_time')
    # Filter out slots in the past on today's date
    now_time = timezone.now().time()
    slots = [s for s in slots if not (s.date == today and s.start_time <= now_time)]
    return render(request, 'appointments/doctor_slots.html', {'doctor': doctor, 'slots': slots})


@patient_required
@require_POST
def book_slot(request, slot_id):
    """
    Race-condition-safe booking using SELECT FOR UPDATE inside a transaction.

    Design decision: we use DB-level row locking (select_for_update) rather
    than application-level optimistic locking. This guarantees exactly-once
    booking even under concurrent requests, at the cost of a slightly longer
    DB transaction. See README for full rationale.
    """
    with transaction.atomic():
        # Lock the row so concurrent requests wait here, not race past it
        slot = get_object_or_404(
            AvailabilitySlot.objects.select_for_update(),
            pk=slot_id,
        )

        if slot.is_booked:
            messages.error(request, 'Sorry — that slot was just booked by someone else.')
            return redirect('doctor_slots', doctor_id=slot.doctor_id)

        # Mark booked and create Booking record atomically
        slot.is_booked = True
        slot.save(update_fields=['is_booked'])

        booking = Booking.objects.create(slot=slot, patient=request.user)

    # ── Post-booking side effects (outside transaction so DB isn't held) ──

    # 1. Google Calendar events
    doctor = slot.doctor
    patient = request.user

    doctor_event_id = _safe_create_event(
        doctor,
        title=f'Appointment with {patient.get_full_name() or patient.username}',
        slot=slot,
    )
    patient_event_id = _safe_create_event(
        patient,
        title=f'Appointment with Dr. {doctor.get_full_name() or doctor.username}',
        slot=slot,
    )

    if doctor_event_id or patient_event_id:
        Booking.objects.filter(pk=booking.pk).update(
            doctor_calendar_event_id=doctor_event_id or '',
            patient_calendar_event_id=patient_event_id or '',
        )

    # 2. Confirmation email via serverless function
    trigger_email('BOOKING_CONFIRMATION', {
        'patient_email': patient.email,
        'patient_name': patient.get_full_name() or patient.username,
        'doctor_name': f'Dr. {doctor.get_full_name() or doctor.username}',
        'date': str(slot.date),
        'start_time': str(slot.start_time),
        'end_time': str(slot.end_time),
    })

    messages.success(
        request,
        f'Booking confirmed with Dr. {doctor.get_full_name()} on {slot.date} at {slot.start_time}.'
    )
    return redirect('patient_dashboard')


def _safe_create_event(user, title, slot):
    """Create a Google Calendar event, return event ID or empty string on failure."""
    try:
        return create_calendar_event(user, title, slot)
    except Exception as exc:
        logger.warning('Calendar event creation failed for %s: %s', user, exc)
        return ''
