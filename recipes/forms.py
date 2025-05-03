from datetime import date
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm, AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from captcha.fields import CaptchaField
from django.contrib.auth import get_user_model
from .models import GroceryList, MealPlan, MealPlanRecipe, Profile, DietaryRestriction, Recipe
from django.forms.widgets import ClearableFileInput

# Custom user creation form with additional fields and validation
class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Enter a valid email address.')
    first_name = forms.CharField(max_length=30, required=True, help_text='Optional.')
    last_name = forms.CharField(max_length=30, required=True, help_text='Optional.')
    agree_to_terms = forms.BooleanField(required=True, label='I agree to the terms and conditions.')
    captcha = CaptchaField()  # CAPTCHA field for spam prevention

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', 'agree_to_terms', 'captcha')

    # Ensure the email is unique
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use. Please use a different email.")
        return email

# Get the user model dynamically
UserModel = get_user_model()

# Custom password reset form to check if the email belongs to an active user
class CustomPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data["email"]
        if not UserModel.objects.filter(email=email, is_active=True).exists():
            self.add_error('email', "There is no active user associated with this email address.")
        return email

# Authentication form that allows login with username or email
class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="Username or Email", max_length=254)

# Form for editing user account settings
class AccountSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']
        help_texts = {
            'username': "",  # Remove default help text for username
        }

    # Ensure the email is unique, excluding the current user
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    # Save the user and handle avatar upload if provided
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            if 'avatar' in self.files:
                profile = user.profile
                profile.avatar = self.files['avatar']
                profile.save()
        return user

# Form for selecting dietary restrictions
class DietaryRestrictionsForm(forms.ModelForm):
    dietary_restrictions = forms.ModelMultipleChoiceField(
        queryset=DietaryRestriction.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    class Meta:
        model = Profile
        fields = ['dietary_restrictions']

# Form for updating social media links
class SocialLinksForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['twitter_url', 'instagram_url', 'personal_website']

# Form for managing profile avatar, including removal option
class ProfileAvatarForm(forms.ModelForm):
    remove_avatar = forms.BooleanField(required=False, label="Remove current avatar")

    class Meta:
        model = Profile
        fields = ['avatar']

    # Handle avatar removal or update
    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.cleaned_data.get('remove_avatar'):
            profile.avatar = None  # Clear the avatar
        if commit:
            profile.save()
        return profile

# Form for controlling what profile information is displayed publicly
class ProfileDisplayForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'show_name',
            'show_avatar',
            'show_social_links',
            'show_dietary_restrictions',
            'show_followers',
            'show_following',
        ]

# Form for updating the user's bio
class BioForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

# Custom password change form to prevent reusing the current password
class CustomPasswordChangeForm(PasswordChangeForm):
    def clean_new_password1(self):
        new_password1 = self.cleaned_data.get('new_password1')
        if self.user.check_password(new_password1):
            raise forms.ValidationError("The new password cannot be the same as your current password.")
        return new_password1

# Custom set password form to prevent reusing the current password
class CustomSetPasswordForm(SetPasswordForm):
    def clean_new_password1(self):
        password1 = self.cleaned_data.get('new_password1')
        if self.user.check_password(password1):
            raise forms.ValidationError("The new password cannot be the same as your current password.")
        return password1

# Custom widget for handling multiple file uploads
class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True

# Custom field for handling multiple file uploads
class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    # Clean and validate multiple files
    def clean(self, data, initial=None):
        files = self._get_files_list(data)
        if not files and self.required:
            raise ValidationError("Please upload at least one file.")
        for f in files:
            if f.size > 2 * 1024 * 1024:
                raise ValidationError(f"{f.name} exceeds 2MB limit")
        return files

    # Helper method to handle different data formats for files
    def _get_files_list(self, data):
        if isinstance(data, list):
            return data
        elif data:
            return [data]
        return []

# Form for creating or editing recipes, including multiple image uploads
class RecipeForm(forms.ModelForm):
    images = MultipleFileField(
        required=True,
        help_text="Upload 1-5 images (max 2MB each)."
    )
    dietary_tags = forms.ModelMultipleChoiceField(
        queryset=DietaryRestriction.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Recipe
        fields = [
            'title', 'description', 'ingredients', 'instructions',
            'category', 'cooking_time', 'calories', 'proteins', 'carbs',
            'dietary_tags', 'visibility'
        ]
        widgets = {
            'ingredients': forms.Textarea(attrs={'rows': 4, 'placeholder': 'e.g., 2 cups flour\n1 tsp salt'}),
            'instructions': forms.Textarea(attrs={'rows': 6, 'placeholder': 'e.g., 1. Preheat oven to 350°F.\n2. Mix dry ingredients.'}),
            'category': forms.Select(attrs={'class': 'select2'}),
        }
        help_texts = {
            'title': "Give your recipe a catchy, descriptive name.",
            'description': "A short summary to entice others to try your recipe.",
            'category': "Choose the best fit for your recipe.",
            'visibility': "Decide who can see your recipe."
        }

    # Initialize form with default values and enforce required fields
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial['category'] = ''
        self.fields['category'].required = True
        self.fields['instructions'].required = True
        self.fields['cooking_time'].required = True

# Form for creating or editing meal plans with date validation
class MealPlanForm(forms.ModelForm):
    class Meta:
        model = MealPlan
        fields = ['title', 'start_date', 'end_date', 'description']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Add notes or goals for your meal plan'}),
        }
        labels = {
            'title': 'Meal Plan Title',
            'start_date': 'Start Date',
            'end_date': 'End Date',
            'description': 'Description'
        }

    # Validate that dates are logical and required fields are filled
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        title = cleaned_data.get('title')

        if not title:
            raise ValidationError("Title is required.")
        if not start_date:
            raise ValidationError("Start date is required.")
        if start_date and start_date < date.today():
            raise ValidationError("Start date cannot be in the past.")
        if end_date and start_date and end_date < start_date:
            raise ValidationError("End date cannot be before start date.")

        return cleaned_data

# Form for assigning recipes to meal plans with validation
class MealPlanRecipeForm(forms.ModelForm):
    recipe_id = forms.CharField(widget=forms.HiddenInput(), required=True)

    class Meta:
        model = MealPlanRecipe
        fields = ['recipe_id', 'day', 'meal_type']
        widgets = {
            'day': forms.DateInput(attrs={'type': 'date'}),
            'meal_type': forms.Select(choices=MealPlanRecipe.MEAL_TYPES),
        }

    # Initialize form with meal plan constraints
    def __init__(self, *args, **kwargs):
        self.meal_plan = kwargs.pop('meal_plan', None)
        super().__init__(*args, **kwargs)
        if self.meal_plan:
            self.fields['day'].widget.attrs['min'] = self.meal_plan.start_date.isoformat()
            if self.meal_plan.end_date:
                self.fields['day'].widget.attrs['max'] = self.meal_plan.end_date.isoformat()

    # Validate recipe existence, date range, and uniqueness
    def clean(self):
        cleaned_data = super().clean()
        recipe_id = cleaned_data.get('recipe_id')
        day = cleaned_data.get('day')
        meal_type = cleaned_data.get('meal_type')

        if not self.meal_plan:
            raise ValidationError("Meal plan is required.")
        if recipe_id:
            try:
                cleaned_data['recipe'] = Recipe.objects.get(id=recipe_id)
            except Recipe.DoesNotExist:
                raise ValidationError("Selected recipe does not exist.")
        else:
            raise ValidationError("Recipe is required.")
        if day:
            if day < self.meal_plan.start_date:
                raise ValidationError("Day cannot be before the meal plan's start date.")
            if self.meal_plan.end_date and day > self.meal_plan.end_date:
                raise ValidationError("Day cannot be after the meal plan's end date.")
        if cleaned_data.get('recipe') and day and meal_type:
            if MealPlanRecipe.objects.filter(
                meal_plan=self.meal_plan,
                recipe=cleaned_data['recipe'],
                day=day,
                meal_type=meal_type
            ).exists():
                raise ValidationError("This recipe is already assigned to this day and meal type.")

        return cleaned_data

    # Save the MealPlanRecipe instance with the selected recipe
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.recipe = self.cleaned_data['recipe']
        if commit:
            instance.save()
        return instance

# Form for creating or editing grocery lists with ingredient validation
class GroceryListForm(forms.ModelForm):
    class Meta:
        model = GroceryList
        fields = ['title', 'ingredients']
        widgets = {
            'ingredients': forms.Textarea(attrs={'rows': 10, 'placeholder': 'Enter one ingredient per line'}),
        }
        labels = {
            'title': 'List Title',
            'ingredients': 'Ingredients (one per line)',
        }

    # Ensure ingredients are not empty
    def clean_ingredients(self):
        ingredients = self.cleaned_data.get('ingredients')
        if not ingredients.strip():
            raise forms.ValidationError("Ingredients cannot be empty.")
        return ingredients