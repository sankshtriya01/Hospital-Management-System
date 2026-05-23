from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, DoctorProfile, PatientProfile


class DoctorSignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    email = forms.EmailField(required=True)
    specialization = forms.CharField(max_length=100, required=False)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'specialization', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.ROLE_DOCTOR
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            DoctorProfile.objects.create(
                user=user,
                specialization=self.cleaned_data.get('specialization', '')
            )
        return user


class PatientSignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.ROLE_PATIENT
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            PatientProfile.objects.create(user=user)
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput())
