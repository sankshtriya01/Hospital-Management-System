from django import forms
from django.utils import timezone
from .models import AvailabilitySlot


class AvailabilitySlotForm(forms.ModelForm):
    class Meta:
        model = AvailabilitySlot
        fields = ['date', 'start_time', 'end_time']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned = super().clean()
        date = cleaned.get('date')
        start = cleaned.get('start_time')
        end = cleaned.get('end_time')

        if date and date < timezone.now().date():
            raise forms.ValidationError('Slot date must be in the future.')

        if start and end and end <= start:
            raise forms.ValidationError('End time must be after start time.')

        return cleaned
