from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class SimpleUserCreationForm(UserCreationForm):
    """
    A relaxed registration form suitable for a game:
    - Only requires username & password
    - Allows short usernames
    - Allows simple passwords (min 4 chars)
    - Still checks password confirmation
    """
    class Meta:
        model = User
        fields = ("username",)

    def clean_username(self):
        username = self.cleaned_data.get("username")

        if len(username) < 3:
            raise forms.ValidationError("Username must be at least 3 characters.")

        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 != password2:
            raise forms.ValidationError("Passwords do not match.")

        if len(password1) < 4:
            raise forms.ValidationError("Password must be at least 4 characters.")

        return password2
