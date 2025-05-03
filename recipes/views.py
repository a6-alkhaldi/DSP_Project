from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import json
from math import floor
import re
from tokenize import Comment
import uuid
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from .forms import BioForm, GroceryListForm, MealPlanForm, MealPlanRecipeForm, RecipeForm, SignUpForm
from django.http import HttpResponse, JsonResponse
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site
from .models import CommentRating, DietaryRestriction, EmailVerification, Follow, GroceryList, MealPlanRecipe, RecipeImage, RecipeRating, SavedRecipe
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import EmailOrUsernameAuthenticationForm  
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import AccountSettingsForm
from .forms import CustomPasswordChangeForm  
from .forms import ProfileDisplayForm
from .models import Recipe  
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from functools import wraps
from django.db.models import F
from django.utils import timezone
from typing import List
from django.db.models import F, Case, When
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from .forms import AccountSettingsForm, DietaryRestrictionsForm, SocialLinksForm, ProfileDisplayForm
from django.shortcuts import render
from django.db.models import F, FloatField, ExpressionWrapper
from .models import Recipe, DietaryRestriction, MealPlan
from django.db.models import Count, Q, Avg
from django.core.paginator import Paginator
from django.views.generic import DetailView
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from django.views.decorators.csrf import csrf_exempt
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

def home(request):
    # Renders the home page with popular and newest recipes, categories, tags, and counts
    # Fetch popular recipes by calculating a popularity score as average_rating * total_ratings
    popular_recipes = Recipe.objects.filter(visibility='public').annotate(
        popularity=ExpressionWrapper(
            F('average_rating') * F('total_ratings'),
            output_field=FloatField()
        )
    ).order_by('-popularity')[:3]  # Limit to top 3 popular recipes

    # Fetch the three most recently created public recipes
    newest_recipes = Recipe.objects.filter(visibility='public').order_by('-created_at')[:3]  # Limit to 3 newest recipes

    # Fetch the top 3 categories based on recipe count
    category_counts = Recipe.objects.filter(visibility='public').values('category').annotate(
        count=Count('id')
    ).order_by('-count')[:3]
    
    # Map category codes to human-readable labels and include counts
    category_choices_dict = dict(Recipe.CATEGORY_CHOICES)
    top_categories = [
        (category['category'], category_choices_dict.get(category['category'], category['category']), category['count'])
        for category in category_counts
    ]

    # Fetch the top 3 dietary restrictions with the most associated recipes
    top_dietary_tags = DietaryRestriction.objects.annotate(
        recipe_count=Count('recipe')
    ).filter(recipe_count__gt=0).order_by('-recipe_count')[:3]

    # Calculate total counts for recipes and meal plans for display statistics
    recipe_count = Recipe.objects.count()
    meal_plan_count = MealPlan.objects.count()

    # Prepare context dictionary for template rendering
    context = {
        'popular_recipes': popular_recipes,
        'newest_recipes': newest_recipes,
        'top_categories': top_categories,
        'top_dietary_tags': top_dietary_tags,
        'recipe_count': recipe_count,
        'meal_plan_count': meal_plan_count,
    }
    return render(request, 'home.html', context)

def login_required(view_func):
    # Custom decorator to restrict access to authenticated users only
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Check if the user is authenticated
        if not request.user.is_authenticated:
            # Display error message and redirect to login if not authenticated
            messages.error(request, "You must be logged in to access this page.")
            return redirect('login')  
        # Call the original view function if authenticated
        return view_func(request, *args, **kwargs)
    return wrapped_view

def signup(request):
    # Handle user registration with email verification
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            # Save the new user
            user = form.save()
            # Create an email verification record for the new user
            email_verification = EmailVerification.objects.create(user=user)
            print(f"EmailVerification created for {user.username}: {email_verification.token}")  # Log verification token
            # Prepare and send verification email
            current_site = get_current_site(request)
            mail_subject = 'Verify your email address'
            html_message = render_to_string('registration/verify_email.html', {
                'user': user,
                'domain': current_site.domain,
                'token': email_verification.token,
            })
            text_message = f"Hi {user.username},\n\nPlease verify your email address by clicking the link below:\n\nhttp://{current_site.domain}{reverse('verify_email', args=[email_verification.token])}\n\nIf you did not create an account, please ignore this email.\n\nBest regards,\nThe Recipe Planner Team"
            email = EmailMultiAlternatives(
                mail_subject,
                text_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email]
            )
            email.attach_alternative(html_message, "text/html")
            email.send()
            # Notify user of successful registration and email sent
            messages.success(request, 'A verification email has been sent to your email address. Please verify your email to complete registration.')
            return redirect('login')
    else:
        # Display empty signup form for GET request
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

def refresh_captcha(request):
    # Generate a new CAPTCHA for form validation
    new_key = CaptchaStore.generate_key()  # Create a new CAPTCHA key
    new_image_url = captcha_image_url(new_key)  # Generate URL for the new CAPTCHA image
    return JsonResponse({'key': new_key, 'image_url': new_image_url})  # Return JSON response with key and URL

def terms(request):
    # Render the terms and conditions page
    return render(request, 'terms.html')

def verify_email(request, token):
    # Verify user's email address using the provided token
    email_verification = get_object_or_404(EmailVerification, token=token)  # Retrieve verification record or 404
    if not email_verification.verified:
        # Mark email as verified if not already done
        email_verification.verified = True
        email_verification.save()
        return render(request, 'registration/verification_success.html')  # Show success page
    else:
        # Warn if email is already verified and redirect to login
        messages.warning(request, 'Your email has already been verified.')
        return redirect('login')

def user_login(request):
    # Handle user login with email or username, requiring email verification
    if request.method == 'POST':
        form = EmailOrUsernameAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()  # Get authenticated user
            email_verification = EmailVerification.objects.filter(user=user).first()  # Check email verification status
            if email_verification and email_verification.verified:
                # Log in user and redirect to next URL or home
                login(request, user)
                next_url = request.POST.get('next', request.GET.get('next', 'home'))  # Handle 'next' parameter
                return redirect(next_url)
            else:
                # Deny login if email not verified
                messages.error(request, 'Please verify your email address to log in.')
                return redirect('login')
        else:
            # Display error for invalid credentials
            messages.error(request, 'Invalid username or password. Please try again.')
    else:
        # Display empty login form for GET request
        form = EmailOrUsernameAuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})

def contact(request):
    # Process contact form submission and send email to support
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        # Validate all fields are filled
        if not all([name, email, subject, message]):
            messages.error(request, 'Please fill out all fields.')
        else:
            # Attempt to send email to support
            try:
                send_mail(
                    subject=f"Contact Form: {subject}",
                    message=f"From: {name} ({email})\n\nMessage:\n{message}",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[settings.EMAIL_HOST_USER],  # Should be replaced with support email
                    fail_silently=False,
                )
                messages.success(request, 'Your message has been sent successfully!')
                return redirect('contact')
            except Exception as e:
                messages.error(request, 'Failed to send your message. Please try again later.')

    return render(request, 'contact.html')

def about(request):
    # Render the about page
    return render(request, 'about.html')

def terms(request):
    # Render the terms and conditions page (duplicate definition, consider removing)
    return render(request, 'terms.html')

def privacy(request):
    # Render the privacy policy page
    return render(request, 'privacy.html')

@login_required
def profile(request):
    # Manage user profile updates for dietary restrictions, social links, and bio
    profile_obj = request.user.profile  # Get user's profile object

    if request.method == 'POST':
        # Handle different form submissions based on hidden input
        if 'diet_form_submitted' in request.POST:
            diet_form = DietaryRestrictionsForm(request.POST, instance=profile_obj)
            social_form = SocialLinksForm(instance=profile_obj)  
            if diet_form.is_valid():
                diet_form.save()  # Save updated dietary restrictions
                messages.success(request, "Dietary restrictions updated successfully.")
                return redirect('profile')  # Post-Redirect-Get pattern
            else:
                messages.error(request, "There was an error updating your dietary restrictions.")
        elif 'social_form_submitted' in request.POST:
            social_form = SocialLinksForm(request.POST, instance=profile_obj)
            diet_form = DietaryRestrictionsForm(instance=profile_obj)
            if social_form.is_valid():
                social_form.save()  # Save updated social links
                messages.success(request, "Social links updated successfully.")
                return redirect('profile')  # Post-Redirect-Get pattern
            else:
                messages.error(request, "There was an error updating your social links.")
        elif 'bio_form_submitted' in request.POST:  
            bio_form = BioForm(request.POST, instance=profile_obj)
            if bio_form.is_valid():
                bio_form.save()  # Save updated bio
                messages.success(request, "Bio updated successfully.")
                return redirect('profile')
            else:
                messages.error(request, "Error updating bio.")
        return redirect('profile')

    else:
        # Initialize forms with current profile data for GET request
        diet_form = DietaryRestrictionsForm(instance=profile_obj)
        social_form = SocialLinksForm(instance=profile_obj)
        bio_form = BioForm(instance=profile_obj) 

    # Prepare context for template
    context = {
        'profile_user': request.user,
        'profile_obj': profile_obj,
        'diet_form': diet_form,
        'social_form': social_form,
        'bio_form': bio_form,  
    }
    return render(request, 'profile.html', context)

@login_required
def account_settings(request):
    # Allow users to update account info and change password
    user = request.user
    profile = user.profile  # Not used in this function, consider removing

    # Initialize forms with current user data
    user_form = AccountSettingsForm(instance=user)
    password_form = CustomPasswordChangeForm(user=user)
    show_password_modal = False  # Flag to show password modal on error

    if request.method == 'POST':
        if 'save_changes' in request.POST:
            user_form = AccountSettingsForm(request.POST, instance=user)
            if user_form.is_valid():
                # Check if any changes were made
                if not user_form.changed_data:
                    messages.info(request, "No changes were made.")
                    return redirect('account_settings')
                user_form.save()  # Save updated account info
                messages.success(request, "Account info updated successfully.")
                return redirect('account_settings')
            else:
                messages.error(request, "Please correct the errors in the form.")
        elif 'change_password' in request.POST:
            password_form = CustomPasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()  # Save new password
                update_session_auth_hash(request, user)  # Keep user logged in
                messages.success(request, "Password changed successfully.")
                return redirect('account_settings')
            else:
                show_password_modal = True  # Show modal on error

    # Prepare context for template
    context = {
        'user_form': user_form,
        'password_form': password_form,
        'show_password_modal': show_password_modal,
    }
    return render(request, 'account_settings.html', context)

@login_required
def my_grocery_lists(request):
    # Display user's grocery lists with pagination
    grocery_lists = GroceryList.objects.filter(user=request.user).order_by('-created_at')  # Fetch user's lists, newest first
    paginator = Paginator(grocery_lists, 12)  # Paginate with 12 items per page
    page_number = request.GET.get('page')  # Get current page number
    page_obj = paginator.get_page(page_number)  # Get paginated objects
    
    return render(request, 'my_grocery_lists.html', {
        'grocery_lists': page_obj,
        'page_obj': page_obj,
    })

@login_required
def my_recipes(request):
    # Display user's created recipes with pagination
    recipes = Recipe.objects.filter(author=request.user).order_by('-created_at')  # Fetch user's recipes, newest first
    paginator = Paginator(recipes, 12)  # Paginate with 12 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    saved_recipe_ids = list(SavedRecipe.objects.filter(user=request.user).values_list('recipe_id', flat=True))  # Get IDs of saved recipes
    
    return render(request, 'my_recipes.html', {
        'recipes': page_obj,
        'page_obj': page_obj,
        'saved_recipe_ids': saved_recipe_ids,
    })

@login_required
def delete_recipe(request, pk):
    # Delete a recipe if the user is the author
    if request.method == 'POST':
        recipe = get_object_or_404(Recipe, pk=pk, author=request.user)  # Fetch recipe or 404
        recipe.delete()  # Delete the recipe
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def my_saved_recipes(request):
    # Display user's saved recipes with pagination
    saved_recipes = SavedRecipe.objects.filter(user=request.user).select_related('recipe').order_by('-saved_at')  # Fetch saved recipes, newest first
    paginator = Paginator(saved_recipes, 12)  # Paginate with 12 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'my_saved_recipes.html', {
        'saved_recipes': page_obj,
        'page_obj': page_obj,
    })

@login_required
def my_meal_plans(request):
    # Display user's meal plans with pagination and progress stats
    meal_plans = MealPlan.objects.filter(user=request.user).order_by('-created_at')  # Fetch user's meal plans, newest first
    paginator = Paginator(meal_plans, 12)  # Paginate with 12 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate progress for each meal plan
    meal_plan_data = []
    for meal_plan in page_obj:
        planned = meal_plan.meal_plan_recipes.count()  # Number of planned meals
        end_date = meal_plan.end_date or meal_plan.start_date  # Use start date if end date is None
        days = (end_date - meal_plan.start_date).days + 1  # Calculate total days
        total_slots = days * 4  # 4 meal types per day (breakfast, lunch, dinner, snack)
        progress_percentage = (planned / total_slots * 100) if total_slots > 0 else 0  # Calculate progress
        meal_plan_data.append({
            'meal_plan': meal_plan,
            'planned': planned,
            'days': days,
            'total_slots': total_slots,
            'progress_percentage': progress_percentage,
        })
    
    return render(request, 'my_meal_plans.html', {
        'meal_plan_data': meal_plan_data,
        'page_obj': page_obj,
    })

@login_required
def my_comments(request):
    # Display user's comments with pagination
    comments = Comment.objects.filter(user=request.user).select_related('recipe').order_by('-created_at')  # Fetch user's comments, newest first
    paginator = Paginator(comments, 12)  # Paginate with 12 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'my_comments.html', {
        'comments': page_obj,
        'page_obj': page_obj,
    })

@login_required
def delete_comment(request, pk):
    # Delete a comment if the user is the author
    if request.method == 'POST':
        comment = get_object_or_404(Comment, pk=pk, user=request.user)  # Fetch comment or 404
        comment.delete()  # Delete the comment
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@login_required
def edit_comment(request, pk):
    # Edit a comment if the user is the author
    comment = get_object_or_404(Comment, pk=pk, user=request.user)  # Fetch comment or 404
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment.text = content  # Update comment text
            comment.save()
            return JsonResponse({'success': True, 'content': content})
        return JsonResponse({'success': False, 'error': 'Comment cannot be empty'}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

def public_profile(request, username):
    # Display a user's public profile with visibility-based recipe access
    viewed_user = get_object_or_404(User, username=username)  # Fetch user or 404
    profile_obj = viewed_user.profile

    is_following = False
    if request.user.is_authenticated:
        is_following = Follow.objects.filter(follower=request.user, followed=viewed_user).exists()  # Check follow status

    # Determine which recipes to show based on visibility and follow status
    if request.user == viewed_user:
        recipes = viewed_user.recipes.filter(visibility__in=['public', 'followers_only'])  # Owner sees public and followers-only
    else:
        recipes = viewed_user.recipes.filter(visibility='public')  # Non-owner sees public only
        if is_following:
            followers_only_recipes = viewed_user.recipes.filter(visibility='followers_only')
            recipes = recipes | followers_only_recipes  # Add followers-only if following

    # Determine visibility of followers and following lists
    show_followers = profile_obj.show_followers
    show_following = profile_obj.show_following

    if request.user.is_authenticated and request.user == viewed_user:
        show_followers = True  # Owner always sees their own lists
        show_following = True
    elif request.user.is_authenticated and not is_following:
        show_followers = profile_obj.show_followers  # Non-followers respect privacy settings
        show_following = profile_obj.show_following

    # Prepare context for template
    context = {
        'viewed_user': viewed_user,
        'profile_obj': profile_obj,
        'is_following': is_following,
        'recipes': recipes,
        'show_followers': show_followers,
        'show_following': show_following,
    }
    return render(request, 'public_profile.html', context)

@login_required
def privacy_settings(request):
    # Allow users to update their privacy settings
    user = request.user
    profile_obj = user.profile

    if request.method == 'POST':
        display_form = ProfileDisplayForm(request.POST, instance=profile_obj)
        if display_form.is_valid():
            display_form.save()  # Save privacy settings
            return redirect('profile')
    else:
        display_form = ProfileDisplayForm(instance=profile_obj)  # Initialize form with current settings

    return render(request, 'privacy_settings.html', {
        'display_form': display_form,
        'profile_obj': profile_obj,
    })

@login_required
def remove_avatar(request):
    # Remove user's avatar
    if request.method == 'POST':
        profile_obj = request.user.profile
        profile_obj.avatar = None  # Clear avatar field
        profile_obj.save()
        return redirect('profile')
    return redirect('profile')

@login_required
def upload_avatar(request):
    # Upload a new avatar for the user
    if request.method == 'POST':
        profile_obj = request.user.profile
        uploaded_file = request.FILES.get('avatar')  # Get uploaded file

        if uploaded_file:
            profile_obj.avatar = uploaded_file  # Set new avatar
            profile_obj.save()
            messages.success(request, 'Avatar uploaded successfully!')
        else:
            messages.warning(request, 'No file selected. Please choose an image before clicking upload.')

        return redirect('profile')

    return redirect('profile')

def follow_user(request, username):
    # Allow authenticated user to follow another user
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")  # Redirect to login if not authenticated

    user_to_follow = get_object_or_404(User, username=username)  # Fetch user to follow or 404

    if request.user == user_to_follow:
        # Prevent self-following
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': "You cannot follow yourself."}, status=400)
        messages.error(request, "You cannot follow yourself.")
        return redirect('public_profile', username=username)

    if Follow.objects.filter(follower=request.user, followed=user_to_follow).exists():
        # Handle already following case
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': f"You are already following {username}."}, status=400)
        messages.warning(request, f"You are already following {username}.")
        return redirect('public_profile', username=username)

    # Create new follow relationship
    Follow.objects.create(follower=request.user, followed=user_to_follow)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': f"You are now following {username}.", 'is_following': True})
    messages.success(request, f"You are now following {username}.")
    return redirect('public_profile', username=username)

def unfollow_user(request, username):
    # Allow authenticated user to unfollow another user
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    user_to_unfollow = get_object_or_404(User, username=username)

    if request.user == user_to_unfollow:
        # Prevent self-unfollowing
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': "You cannot unfollow yourself."}, status=400)
        messages.error(request, "You cannot unfollow yourself.")
        return redirect('public_profile', username=username)

    follow_relationship = Follow.objects.filter(follower=request.user, followed=user_to_unfollow).first()
    if follow_relationship:
        # Remove follow relationship
        follow_relationship.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f"You have unfollowed {username}.", 'is_following': False})
        messages.success(request, f"You have unfollowed {username}.")
        return redirect('public_profile', username=username)
    else:
        # Handle not following case
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': f"You are not following {username}."}, status=400)
        messages.warning(request, f"You are not following {username}.")
        return redirect('public_profile', username=username)

def api_followers(request, username):
    # API endpoint to fetch a user's followers, respecting privacy settings
    viewed_user = get_object_or_404(User, username=username)
    profile_obj = viewed_user.profile

    followers_count = Follow.objects.filter(followed=viewed_user).count()  # Total followers
    is_owner = request.user.is_authenticated and request.user == viewed_user
    
    if not profile_obj.show_followers and not is_owner:
        # Return count only if list is private and user is not owner
        return JsonResponse({
            'followers_count': followers_count,
            'error': 'This user has made their followers list private.',
            'private': True
        }, status=200)

    # Fetch followers with details
    followers = Follow.objects.filter(followed=viewed_user).select_related('follower')
    followers_list = [
        {
            'username': follow.follower.username,
            'avatar': follow.follower.profile.avatar.url if follow.follower.profile.avatar else None,
            'is_following': request.user.is_authenticated and Follow.objects.filter(follower=request.user, followed=follow.follower).exists() and follow.follower != request.user
        }
        for follow in followers
    ]
    return JsonResponse({'followers': followers_list, 'followers_count': followers_count})

def api_following(request, username):
    # API endpoint to fetch a user's following list, respecting privacy settings
    viewed_user = get_object_or_404(User, username=username)
    profile_obj = viewed_user.profile

    following_count = Follow.objects.filter(follower=viewed_user).count()  # Total following
    is_owner = request.user.is_authenticated and request.user == viewed_user
    
    if not profile_obj.show_following and not is_owner:
        # Return count only if list is private and user is not owner
        return JsonResponse({
            'following_count': following_count,
            'error': 'This user has made their following list private.',
            'private': True
        }, status=200)

    # Fetch following with details
    following = Follow.objects.filter(follower=viewed_user).select_related('followed')
    following_list = [
        {
            'username': follow.followed.username,
            'avatar': follow.followed.profile.avatar.url if follow.followed.profile.avatar else None,
            'is_following': request.user.is_authenticated and Follow.objects.filter(follower=request.user, followed=follow.followed).exists() and follow.followed != request.user
        }
        for follow in following
    ]
    return JsonResponse({'following': following_list, 'following_count': following_count})

@login_required
def following_recipes(request):
    # Display recipes from followed users with filtering and sorting
    followed_users = User.objects.filter(followers__follower=request.user)  # Get followed users
    recipes = Recipe.objects.filter(
        author__in=followed_users,
        visibility__in=['public', 'followers_only']  # Show public and followers-only recipes
    )

    # Apply filters from GET parameters
    query = request.GET.get('q')
    category = request.GET.get('category')
    dietary_tag = request.GET.get('dietary_tags')
    sort = request.GET.get('sort', 'newest')

    if query:
        # Filter by search query in title, description, or ingredients
        recipes = recipes.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(ingredients__icontains=query)
        )

    if category:
        recipes = recipes.filter(category=category)  # Filter by category

    if dietary_tag:
        recipes = recipes.filter(dietary_tags__id=dietary_tag).distinct()  # Filter by dietary tag

    # Apply sorting options
    if sort == 'highest_rating':
        recipes = recipes.order_by('-average_rating')
    elif sort == 'popular':
        recipes = recipes.annotate(
            popularity=ExpressionWrapper(
                F('average_rating') * F('total_ratings'),
                output_field=FloatField()
            )
        ).order_by('-popularity')
    elif sort == 'quickest':
        recipes = recipes.order_by('cooking_time')
    else:  # Default to newest
        recipes = recipes.order_by('-created_at')

    # Paginate results
    paginator = Paginator(recipes, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    saved_recipe_ids = list(SavedRecipe.objects.filter(user=request.user).values_list('recipe_id', flat=True))  # Get saved recipe IDs

    # Handle AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'following_recipes.html', {
            'recipes': page_obj,
            'page_obj': page_obj,
            'saved_recipe_ids': saved_recipe_ids,
            'category_choices': Recipe.CATEGORY_CHOICES,
            'dietary_tags': DietaryRestriction.objects.all(),
            'request': request,
        })

    # Prepare context for regular request
    context = {
        'recipes': page_obj,
        'page_obj': page_obj,
        'saved_recipe_ids': saved_recipe_ids,
        'category_choices': Recipe.CATEGORY_CHOICES,
        'dietary_tags': DietaryRestriction.objects.all(),
        'request': request,
    }
    return render(request, 'following_recipes.html', context)

@login_required
def add_recipe(request):
    # Allow users to create and save a new recipe
    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            recipe = form.save(commit=False)  # Save form without committing to DB yet
            recipe.author = request.user  # Set current user as author
            recipe.save()
            form.save_m2m()  # Save many-to-many relationships (e.g., dietary tags)
            
            # Handle multiple image uploads, up to 5
            images = request.FILES.getlist('images')
            for image in images[:5]:
                RecipeImage.objects.create(recipe=recipe, image=image)
                
            messages.success(request, "Recipe published successfully!")
            return redirect('recipe_detail', pk=recipe.pk)
    else:
        form = RecipeForm()  # Display empty form for GET request
    
    return render(request, 'add_recipe.html', {
        'form': form,
        'categories': Recipe.CATEGORY_CHOICES
    })

class RecipeDetailView(DetailView):
    # Detailed view of a recipe with comments, ratings, and meal plan options
    model = Recipe
    template_name = 'recipe_detail.html'
    context_object_name = 'recipe'

    def get(self, request, *args, **kwargs):
        # Handle GET request with visibility checks
        recipe = self.get_object()
        user = request.user

        # Check recipe visibility and remove from meal plan if inaccessible
        if recipe.visibility == 'private' and recipe.author != user:
            messages.error(self.request, "This recipe is private and has been removed from your meal plan.")
            MealPlanRecipe.objects.filter(meal_plan__user=user, recipe=recipe).delete()
            return redirect('home')

        if recipe.visibility == 'followers_only' and (not user.is_authenticated or not Follow.objects.filter(follower=user, followed=recipe.author).exists()):
            messages.error(self.request, "This recipe is for followers only and has been removed from your meal plan.")
            MealPlanRecipe.objects.filter(meal_plan__user=user, recipe=recipe).delete()
            return redirect('home')

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # Add additional context for template rendering
        context = super().get_context_data(**kwargs)
        recipe = self.get_object()
        user = self.request.user

        # Calculate star ratings for display
        average_rating = recipe.average_rating
        full_stars = floor(average_rating)
        decimal_part = average_rating - full_stars
        stars = []
        for i in range(1, 6):  # 5-star system
            if i <= full_stars:
                stars.append('full')
            elif i == full_stars + 1 and decimal_part >= 0.5:
                stars.append('half')
            else:
                stars.append('empty')
        context['stars'] = stars

        # Fetch all comments with like/dislike counts
        all_comments = recipe.comments.all() \
            .annotate(
                like_count=Count('ratings', filter=Q(ratings__like=True)),
                dislike_count=Count('ratings', filter=Q(ratings__like=False))
            ) \
            .order_by('-created_at')

        # Attach user's ratings to comments if authenticated
        if user.is_authenticated:
            user_ratings = CommentRating.objects.filter(comment__in=all_comments, user=user).values('comment_id', 'like')
            rating_dict = {r['comment_id']: r['like'] for r in user_ratings}
            for c in all_comments:
                c.user_rating = rating_dict.get(c.id, None)

        # Organize comments into parent-child structure
        replies_dict = defaultdict(list)
        for c in all_comments:
            if c.parent_id:
                replies_dict[c.parent_id].append(c)

        top_level_comments = [c for c in all_comments if c.parent_id is None]  # Get parent comments

        # Paginate top-level comments
        page_number = self.request.GET.get('page')
        paginator = Paginator(top_level_comments, 5)  # 5 per page
        page_obj = paginator.get_page(page_number)

        # Attach up to 3 replies per parent comment
        MAX_REPLIES_PREVIEW = 3
        for parent_comment in page_obj:
            children = replies_dict.get(parent_comment.id, [])
            parent_comment.child_replies = children[:MAX_REPLIES_PREVIEW]
            parent_comment.total_replies = len(children)

        context['comments'] = page_obj
        context['page_obj'] = page_obj
        context['paginator'] = paginator

        # Add user's rating if authenticated
        if user.is_authenticated:
            rating = RecipeRating.objects.filter(user=user, recipe=recipe).first()
            context['user_rating'] = rating.rating if rating else 0
        else:
            context['user_rating'] = None

        # Process ingredients and instructions into lists
        if '\n' in recipe.ingredients:
            context['ingredients_list'] = [i.strip() for i in recipe.ingredients.split('\n') if i.strip()]
        else:
            context['ingredients_list'] = [i.strip() for i in recipe.ingredients.split() if i.strip()]

        if '\n' in recipe.instructions:
            context['instructions_list'] = [i.strip() for i in recipe.instructions.split('\n') if i.strip()]
        else:
            context['instructions_list'] = [
                i.strip()
                for i in re.split(r'(?=\d+\.\s|\d+\)\s)', recipe.instructions)
                if i.strip()
            ]
        return context

    def post(self, request, *args, **kwargs):
        # Handle POST actions like adding comments or meal plan entries
        recipe = self.get_object()
        if not request.user.is_authenticated:
            return redirect('login')
        
        if 'comment' in request.POST:
            comment_text = request.POST.get('comment')
            if comment_text:
                Comment.objects.create(user=request.user, recipe=recipe, text=comment_text)  # Add new comment
                messages.success(request, "Comment posted successfully!")
            else:
                messages.error(request, "Comment cannot be empty.")
        elif 'add_to_meal_plan' in request.POST:
            meal_plan, created = MealPlan.objects.get_or_create(user=request.user, week_of=date.today())  # Get or create meal plan
            meal_plan.recipes.add(recipe)  # Add recipe to meal plan
            messages.success(request, f"{recipe.title} added to your meal plan!")

        return redirect('recipe_detail', pk=recipe.pk)

@login_required
def get_user_meal_plans(request):
    # Return JSON list of user's meal plans
    meal_plans = MealPlan.objects.filter(user=request.user).values('id', 'title', 'start_date', 'end_date')
    return JsonResponse(list(meal_plans), safe=False)

@login_required
def add_recipe_to_meal_plan(request):
    # Add a recipe to a specific meal plan slot
    if request.method == 'POST':
        meal_plan_id = request.POST.get('meal_plan')
        recipe_id = request.POST.get('recipe_id')
        day = request.POST.get('day')
        meal_type = request.POST.get('meal_type')
        
        try:
            meal_plan = MealPlan.objects.get(id=meal_plan_id, user=request.user)  # Fetch meal plan
            recipe = Recipe.objects.get(id=recipe_id)  # Fetch recipe
            day_date = datetime.strptime(day, '%Y-%m-%d').date()  # Parse day
            end_date = meal_plan.end_date or meal_plan.start_date
            if meal_plan.start_date <= day_date <= end_date:
                # Check for existing assignment
                if not MealPlanRecipe.objects.filter(meal_plan=meal_plan, recipe=recipe, day=day, meal_type=meal_type).exists():
                    MealPlanRecipe.objects.create(meal_plan=meal_plan, recipe=recipe, day=day, meal_type=meal_type)  # Create new assignment
                    return JsonResponse({'success': True})
                else:
                    return JsonResponse({'success': False, 'error': 'Recipe already assigned to this day and meal type.'})
            else:
                return JsonResponse({'success': False, 'error': 'Selected day is not within the meal plan\'s date range.'})
        except (MealPlan.DoesNotExist, Recipe.DoesNotExist):
            return JsonResponse({'success': False, 'error': 'Invalid meal plan or recipe.'})
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid date format.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@login_required
def toggle_save_recipe(request, recipe_id):
    # Toggle saving or unsaving a recipe
    if request.method == 'POST':
        recipe = get_object_or_404(Recipe, id=recipe_id)
        saved_recipe = SavedRecipe.objects.filter(user=request.user, recipe=recipe).first()
        if saved_recipe:
            saved_recipe.delete()  # Unsave recipe
            action = 'unsaved'
        else:
            SavedRecipe.objects.create(user=request.user, recipe=recipe)  # Save recipe
            action = 'saved'
        return JsonResponse({'success': True, 'action': action})
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@csrf_exempt
def get_replies(request, comment_id):
    # Fetch replies to a specific comment
    if request.method == 'GET':
        try:
            parent_comment = Comment.objects.get(pk=comment_id)  # Fetch parent comment
        except Comment.DoesNotExist:
            return JsonResponse({'error': 'Parent comment does not exist'}, status=404)

        # Fetch and annotate replies with like/dislike counts
        child_replies = parent_comment.replies.all() \
            .annotate(
                like_count=Count('ratings', filter=Q(ratings__like=True)),
                dislike_count=Count('ratings', filter=Q(ratings__like=False))
            ) \
            .order_by('created_at')

        # Prepare reply data
        data = []
        for reply in child_replies:
            data.append({
                'id': reply.id,
                'username': reply.user.username,
                'text': reply.text,
                'created_at': reply.created_at.strftime('%b %d, %Y'),
                'like_count': reply.like_count or 0,
                'dislike_count': reply.dislike_count or 0,
            })

        return JsonResponse({'replies': data}, status=200)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
@login_required
def add_comment(request, recipe_id):
    # Add a new comment or reply to a recipe
    if request.method == 'POST':
        try:
            recipe = Recipe.objects.get(pk=recipe_id)  # Fetch recipe
            text = request.POST.get('comment', '').strip()
            parent_id = request.POST.get('parent_id', None)
            
            if not text:
                return JsonResponse({'success': False, 'error': 'Comment cannot be empty'})
            
            parent = None
            if parent_id:
                parent = Comment.objects.get(pk=parent_id)  # Fetch parent comment if replying
            
            # Create new comment
            comment = Comment.objects.create(
                recipe=recipe,
                user=request.user,
                text=text,
                parent=parent
            )
            return JsonResponse({
                'success': True,
                'comment_text': comment.text,
                'username': request.user.username,
                'comment_id': comment.id,
                'parent_id': parent_id
            })
        except Recipe.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Recipe not found'})
        except Comment.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Parent comment not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
@login_required
def rate_comment(request, comment_id):
    # Rate a comment with like or dislike
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            intended_like = data.get('like')  # True for like, False for dislike
            comment = Comment.objects.get(pk=comment_id)

            # Prevent self-rating
            if request.user == comment.user:
                return JsonResponse({'success': False, 'error': 'You cannot rate your own comment'})

            rating = CommentRating.objects.filter(comment=comment, user=request.user).first()
            if rating:
                if rating.like == intended_like:
                    rating.delete()  # Remove rating if same action repeated
                    action = 'removed'
                else:
                    rating.like = intended_like  # Switch rating
                    rating.save()
                    action = 'updated'
            else:
                CommentRating.objects.create(comment=comment, user=request.user, like=intended_like)  # Create new rating
                action = 'added'

            # Update like/dislike counts
            likes = comment.ratings.filter(like=True).count()
            dislikes = comment.ratings.filter(like=False).count()
            user_rating = 'like' if intended_like and action != 'removed' else 'dislike' if not intended_like and action != 'removed' else None

            return JsonResponse({
                'success': True,
                'likes': likes,
                'dislikes': dislikes,
                'action': action,
                'user_rating': user_rating
            })
        except Comment.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Comment not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def rate_recipe(request, pk):
    # Rate a recipe or remove rating
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            rating = data.get('rating')
            
            if rating is None:
                return JsonResponse({'success': False, 'error': 'Rating is required'}, status=400)
            
            rating = int(rating)
            
            if rating == 0:
                RecipeRating.objects.filter(user=request.user, recipe=recipe).delete()  # Remove rating
            elif not 1 <= rating <= 5:
                return JsonResponse({'success': False, 'error': 'Rating must be between 1 and 5'}, status=400)
            else:
                # Update or create rating
                obj, created = RecipeRating.objects.update_or_create(
                    user=request.user,
                    recipe=recipe,
                    defaults={'rating': rating}
                )
            
            # Update recipe rating stats
            ratings = recipe.ratings.all()
            recipe.total_ratings = ratings.count()
            recipe.average_rating = ratings.aggregate(Avg('rating'))['rating__avg'] or 0
            recipe.save()
            
            return JsonResponse({
                'success': True,
                'average_rating': recipe.average_rating,
                'total_ratings': recipe.total_ratings,
                'user_rating': rating if rating != 0 else 0
            })
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Rating must be an integer'}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

@login_required
def save_grocery_list(request):
    # Save a grocery list from selected ingredients
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            recipe_id = data.get('recipe_id')
            ingredients = data.get('ingredients', [])
            
            if not ingredients:
                return JsonResponse({'success': False, 'error': 'No ingredients selected'}, status=400)
            
            recipe = Recipe.objects.get(pk=recipe_id) if recipe_id else None  # Fetch recipe if provided
            # Create new grocery list
            grocery_list = GroceryList.objects.create(
                user=request.user,
                recipe=recipe,
                ingredients='\n'.join(ingredients),
                title=f"Grocery List for {recipe.title}" if recipe else "Custom Grocery List"
            )
            return JsonResponse({'success': True, 'message': 'Saved successfully to your grocery list!'})
        except Recipe.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Recipe not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

def browse_recipes(request):
    # Browse public recipes with filtering, sorting, and pagination
    get_params = request.GET.copy()
    if request.user.is_authenticated:
        followed_users = Follow.objects.filter(follower=request.user).values_list('followed', flat=True)
        recipes = Recipe.objects.filter(
            Q(visibility='public') |
            Q(visibility='followers_only', author__in=followed_users)  # Include followers-only for followed users
        )
    else:
        recipes = Recipe.objects.filter(visibility='public')  # Public only for unauthenticated users

    # Clean empty GET parameters and redirect if changed
    for key in list(get_params.keys()):
        if not get_params[key]:
            del get_params[key]
    if get_params != request.GET:
        return redirect(f"{request.path}?{get_params.urlencode()}")

    # Default to public recipes sorted by creation date
    recipes = Recipe.objects.filter(visibility='public').order_by('-created_at')

    # Apply filters
    selected_categories = request.GET.getlist('category', [])
    selected_dietary_tags = request.GET.getlist('dietary_tags', [])
    
    valid_categories = [c[0] for c in Recipe.CATEGORY_CHOICES]
    selected_categories = [c for c in selected_categories if c in valid_categories]
    
    valid_dietary_tag_ids = DietaryRestriction.objects.values_list('id', flat=True)
    selected_dietary_tags = [
        str(tag_id) for tag_id in request.GET.getlist('dietary_tags', [])
        if str(tag_id) in map(str, valid_dietary_tag_ids)
    ]

    q = request.GET.get('q')
    if q:
        recipes = recipes.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(ingredients__icontains=q)
        )

    # Apply sorting
    sort = request.GET.get('sort', 'newest')
    if sort == 'highest_rating':
        recipes = recipes.order_by('-average_rating')
    elif sort == 'popular':
        recipes = recipes.annotate(
            popularity=(F('average_rating') * F('total_ratings'))
        ).order_by('-popularity')
    elif sort == 'quickest':
        recipes = recipes.order_by('cooking_time')
    else:
        recipes = recipes.order_by('-created_at')

    # Apply time filter
    max_time = request.GET.get('time')
    if max_time and max_time.isdigit():
        recipes = recipes.filter(cooking_time__lte=int(max_time))

    # Apply quick filters
    if 'new' in request.GET:
        one_week_ago = timezone.now() - timedelta(days=7)
        recipes = recipes.filter(created_at__gte=one_week_ago)
    if 'popular' in request.GET:
        recipes = recipes.filter(average_rating__gte=4, total_ratings__gte=10)
    if 'quick' in request.GET:
        recipes = recipes.filter(cooking_time__lte=30)

    if selected_categories:
        recipes = recipes.filter(category__in=selected_categories)
    
    if selected_dietary_tags:
        recipes = recipes.filter(dietary_tags__in=selected_dietary_tags).distinct()

    # Apply nutrition filters
    calories_min = request.GET.get('calories_min')
    calories_max = request.GET.get('calories_max')
    if calories_min and calories_min.isdigit():
        recipes = recipes.filter(calories__gte=int(calories_min))
    if calories_max and calories_max.isdigit():
        recipes = recipes.filter(calories__lte=int(calories_max))

    proteins_min = request.GET.get('proteins_min')
    proteins_max = request.GET.get('proteins_max')
    if proteins_min and proteins_min.isdigit():
        recipes = recipes.filter(proteins__gte=int(proteins_min))
    if proteins_max and proteins_max.isdigit():
        recipes = recipes.filter(proteins__lte=int(proteins_max))

    # Paginate results
    paginator = Paginator(recipes, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get saved recipe IDs
    if request.user.is_authenticated:
        saved_recipe_ids = list(SavedRecipe.objects.filter(user=request.user).values_list('recipe_id', flat=True))
    else:
        saved_recipe_ids = []

    # Prepare context
    context = {
        'recipes': page_obj,
        'saved_recipe_ids': saved_recipe_ids,
        'dietary_tags': DietaryRestriction.objects.all(),
        'category_choices': Recipe.CATEGORY_CHOICES,
        'request': request,
        'selected_categories': selected_categories,
        'selected_dietary_tags': selected_dietary_tags,
        'page_obj': page_obj,
    }
    return render(request, 'browse_recipes.html', context)

def recipe_quick_view(request, pk):
    # Provide a quick view of a recipe's details
    recipe = get_object_or_404(Recipe, pk=pk)

    # Split ingredients into list
    if '\n' in recipe.ingredients:
        ingredients_list = [i.strip() for i in recipe.ingredients.split('\n') if i.strip()]
    else:
        ingredients_list = [i.strip() for i in recipe.ingredients.split() if i.strip()]
    
    context = {
        'recipe': recipe,
        'ingredients_list': ingredients_list,
    }
    return render(request, 'partials/quick_view.html', context)

@login_required
def create_meal_plan(request):
    # Create a new meal plan with selected recipes
    if request.method == 'POST':
        form = MealPlanForm(request.POST)
        if form.is_valid():
            meal_plan = form.save(commit=False)
            meal_plan.user = request.user  # Set current user
            meal_plan.save()

            # Process selected recipes from JSON data
            selected_recipes_data = request.POST.get('selected_recipes_data', '[]')
            try:
                selected_recipes = json.loads(selected_recipes_data)
            except json.JSONDecodeError:
                selected_recipes = []
                messages.warning(request, "Invalid recipe data provided.")

            # Validate recipe accessibility
            followed_users = Follow.objects.filter(follower=request.user).values_list('followed', flat=True)
            accessible_recipes = Recipe.objects.filter(
                Q(visibility='public') |
                Q(visibility='followers_only', author__in=followed_users) |
                Q(visibility='private', author=request.user)
            ).values_list('id', flat=True)

            for recipe_data in selected_recipes:
                recipe_id = recipe_data.get('id')
                day = recipe_data.get('day')
                meal_type = recipe_data.get('meal_type')
                if recipe_id and day and meal_type:
                    try:
                        recipe_id = int(recipe_id)
                        if recipe_id not in accessible_recipes:
                            messages.warning(request, f"Recipe with ID {recipe_id} is not accessible and was not added.")
                            continue
                        recipe = Recipe.objects.get(id=recipe_id)
                        MealPlanRecipe.objects.create(
                            meal_plan=meal_plan,
                            recipe=recipe,
                            day=day,
                            meal_type=meal_type
                        )
                    except Recipe.DoesNotExist:
                        messages.warning(request, f"Recipe with ID {recipe_id} could not be added.")
                    except ValueError as e:
                        messages.warning(request, f"Invalid data for recipe {recipe_id}: {str(e)}")

            messages.success(request, f"Meal plan '{meal_plan.title}' created successfully!")
            return redirect('meal_plan_detail', pk=meal_plan.pk)
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = MealPlanForm()

    # Fetch recipe suggestions
    followed_users = Follow.objects.filter(follower=request.user).values_list('followed', flat=True)
    accessible_recipes = Recipe.objects.filter(
        Q(visibility='public') |
        Q(visibility='followers_only', author__in=followed_users) |
        Q(visibility='private', author=request.user)
    )

    popular_recipes = accessible_recipes.annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings')
    ).filter(avg_rating__gte=4, rating_count__gte=10).order_by('-avg_rating')[:3]

    quick_recipes = accessible_recipes.filter(cooking_time__lte=30).order_by('cooking_time')[:3]

    suggestions = list(set(popular_recipes) | set(quick_recipes))[:5]  # Combine and limit to 5

    return render(request, 'create_meal_plan.html', {
        'form': form,
        'suggestions': suggestions
    })

@login_required
def meal_plan_detail(request, pk):
    # Display details of a meal plan with nutritional summary
    meal_plan = get_object_or_404(MealPlan, pk=pk, user=request.user)
    
    # Remove inaccessible recipes
    mprs = MealPlanRecipe.objects.filter(meal_plan=meal_plan)
    removed_count = 0
    for mpr in mprs:
        recipe = mpr.recipe
        if recipe.visibility == 'private' and recipe.author != request.user:
            mpr.delete()
            removed_count += 1
        elif recipe.visibility == 'followers_only' and not Follow.objects.filter(follower=request.user, followed=recipe.author).exists():
            mpr.delete()
            removed_count += 1
    
    if removed_count > 0:
        messages.info(request, f"{removed_count} recipe(s) have been removed from your meal plan due to access restrictions.")
    
    # Fetch remaining recipes
    meal_plan_recipes = MealPlanRecipe.objects.filter(meal_plan=meal_plan).order_by('day', 'meal_type')
    
    # Calculate progress
    days = (meal_plan.end_date - meal_plan.start_date).days + 1 if meal_plan.end_date else 1
    total_slots = days * len(MealPlanRecipe.MEAL_TYPES)
    planned_meals = meal_plan_recipes.count()
    progress_percentage = (planned_meals / total_slots * 100) if total_slots > 0 else 0

    # Calculate daily nutrition
    daily_nutrition = {}
    meal_plan_date_range = [
        meal_plan.start_date + timedelta(days=x)
        for x in range(days)
    ] if meal_plan.start_date else []
    
    for day in meal_plan_date_range:
        day_recipes = meal_plan_recipes.filter(day=day)
        daily_nutrition[day.strftime('%Y-%m-%d')] = {
            'calories': sum(r.recipe.calories or 0 for r in day_recipes),
            'proteins': float(sum(r.recipe.proteins or 0 for r in day_recipes)),
            'carbs': float(sum(r.recipe.carbs or 0 for r in day_recipes)),
        }

    return render(request, 'meal_plan_detail.html', {
        'meal_plan': meal_plan,
        'meal_plan_recipes': meal_plan_recipes,
        'progress_percentage': progress_percentage,
        'planned_meals': planned_meals,
        'total_slots': total_slots,
        'daily_nutrition': json.dumps(daily_nutrition),
        'meal_plan_date_range': meal_plan_date_range,
    })

@login_required
def edit_meal_plan(request, pk):
    # Edit an existing meal plan by adding or modifying recipes
    meal_plan = get_object_or_404(MealPlan, id=pk, user=request.user)

    # Remove inaccessible recipes
    mprs = MealPlanRecipe.objects.filter(meal_plan=meal_plan)
    removed_count = 0
    for mpr in mprs:
        recipe = mpr.recipe
        if recipe.visibility == 'private' and recipe.author != request.user:
            mpr.delete()
            removed_count += 1
        elif recipe.visibility == 'followers_only' and not Follow.objects.filter(follower=request.user, followed=recipe.author).exists():
            mpr.delete()
            removed_count += 1
    
    if removed_count > 0:
        messages.info(request, f"{removed_count} recipe(s) have been removed from your meal plan due to access restrictions.")

    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = json.loads(request.body)
            form = MealPlanRecipeForm(data, meal_plan=meal_plan)
            if form.is_valid():
                meal_plan_recipe = form.save(commit=False)
                meal_plan_recipe.meal_plan = meal_plan
                meal_plan_recipe.save()
                return JsonResponse({
                    'success': True,
                    'recipe_title': meal_plan_recipe.recipe.title,
                })
            return JsonResponse({'success': False, 'error': form.errors.as_text()}, status=400)
        else:
            form = MealPlanRecipeForm(request.POST, meal_plan=meal_plan)
            if form.is_valid():
                meal_plan_recipe = form.save(commit=False)
                meal_plan_recipe.meal_plan = meal_plan
                meal_plan_recipe.save()
                messages.success(request, f"'{meal_plan_recipe.recipe.title}' added to '{meal_plan.title}'!")
                return redirect('edit_meal_plan', pk=pk)
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field.capitalize()}: {error}")

    else:
        form = MealPlanRecipeForm(meal_plan=meal_plan)

    # Fetch recipe suggestions
    if request.user.is_authenticated:
        followed_users = Follow.objects.filter(follower=request.user).values_list('followed', flat=True)
        suggestions = Recipe.objects.filter(
            Q(visibility='public') |
            Q(visibility='followers_only', author__in=followed_users) |
            Q(visibility='private', author=request.user)
        )
    else:
        suggestions = Recipe.objects.filter(visibility='public')

    # Apply filters to suggestions
    search_query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    dietary_tag = request.GET.get('dietary_tag', '')

    if search_query:
        suggestions = suggestions.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    if category:
        suggestions = suggestions.filter(category=category)
    if dietary_tag:
        suggestions = suggestions.filter(dietary_tags__name=dietary_tag)

    # Paginate suggestions
    paginator = Paginator(suggestions, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Fetch current meal plan recipes
    meal_plan_recipes = MealPlanRecipe.objects.filter(meal_plan=meal_plan).order_by('day', 'meal_type')
    meal_plan_date_range = [
        (meal_plan.start_date + timedelta(days=x))
        for x in range((meal_plan.end_date - meal_plan.start_date).days + 1)
    ] if meal_plan.end_date else [meal_plan.start_date]

    return render(request, 'edit_meal_plan.html', {
        'meal_plan': meal_plan,
        'form': form,
        'suggestions': page_obj,
        'meal_plan_recipes': meal_plan_recipes,
        'meal_plan_date_range': meal_plan_date_range,
        'meal_types': MealPlanRecipe.MEAL_TYPES,
        'search_query': search_query,
        'category': category,
        'dietary_tag': dietary_tag,
        'categories': Recipe.CATEGORY_CHOICES,
        'dietary_tags': DietaryRestriction.objects.all(),
        'page_obj': page_obj,
    })

@csrf_exempt
@login_required
def remove_recipe_from_meal_plan(request, pk):
    # Remove a recipe from a meal plan
    meal_plan = get_object_or_404(MealPlan, id=pk, user=request.user)
    if request.method == 'POST':
        data = json.loads(request.body)
        recipe_id = data.get('recipe_id')
        day = data.get('day')
        meal_type = data.get('meal_type')
        try:
            meal_plan_recipe = MealPlanRecipe.objects.get(
                meal_plan=meal_plan,
                recipe_id=recipe_id,
                day=day,
                meal_type=meal_type
            )
            meal_plan_recipe.delete()  # Remove assignment
            return JsonResponse({
                'success': True,
                'message': 'Recipe removed from meal plan and grocery list updated.'
            })
        except MealPlanRecipe.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Recipe assignment not found'}, status=404)
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)

@csrf_exempt
@login_required
def delete_meal_plan(request, pk):
    # Delete a meal plan and its associated grocery list
    meal_plan = get_object_or_404(MealPlan, id=pk, user=request.user)
    if request.method == 'POST':
        if meal_plan.grocery_list:
            meal_plan.grocery_list.delete()  # Delete associated grocery list
            messages.info(request, "The associated grocery list has been deleted along with the meal plan.")
        meal_plan.delete()  # Delete meal plan
        messages.success(request, "Meal plan deleted successfully.")
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)



@receiver(post_save, sender=MealPlanRecipe)
def update_grocery_list(sender, instance, created, **kwargs):
    # Update grocery list when a recipe is added to a meal plan
    if created:  # Trigger only on creation
        meal_plan = instance.meal_plan
        user = meal_plan.user

        # Get or create grocery list
        if meal_plan.grocery_list:
            grocery_list = meal_plan.grocery_list
        else:
            grocery_list = GroceryList.objects.create(
                user=user,
                title=f"Grocery List for {meal_plan.title}",
                ingredients="",
            )
            meal_plan.grocery_list = grocery_list
            meal_plan.save()

        # Aggregate ingredients from all recipes
        meal_plan_recipes = MealPlanRecipe.objects.filter(meal_plan=meal_plan)
        all_ingredients = []
        for mpr in meal_plan_recipes:
            recipe = mpr.recipe
            if '\n' in recipe.ingredients:
                ingredients = [i.strip() for i in recipe.ingredients.split('\n') if i.strip()]
            else:
                ingredients = [i.strip() for i in recipe.ingredients.split() if i.strip()]
            all_ingredients.extend(ingredients)

        # Update grocery list
        grocery_list.ingredients = '\n'.join(all_ingredients)
        grocery_list.save()

@receiver(post_delete, sender=MealPlanRecipe)
def remove_from_grocery_list(sender, instance, **kwargs):
    # Update grocery list when a recipe is removed from a meal plan
    meal_plan = instance.meal_plan
    if meal_plan.grocery_list:
        meal_plan_recipes = MealPlanRecipe.objects.filter(meal_plan=meal_plan)
        all_ingredients = []
        for mpr in meal_plan_recipes:
            recipe = mpr.recipe
            if '\n' in recipe.ingredients:
                ingredients = [i.strip() for i in recipe.ingredients.split('\n') if i.strip()]
            else:
                ingredients = [i.strip() for i in recipe.ingredients.split() if i.strip()]
            all_ingredients.extend(ingredients)
        meal_plan.grocery_list.ingredients = '\n'.join(all_ingredients)
        meal_plan.grocery_list.save()



@login_required
def grocery_list_detail(request, pk):
    # Display and manage a grocery list with PDF and email options
    grocery_list = get_object_or_404(GroceryList, pk=pk, user=request.user)
    
    # Categorize ingredients
    categories = {
        'Produce': ['vegetable', 'fruit', 'tomato', 'onion', 'lettuce', 'carrot', 'apple', 'banana'],
        'Dairy': ['milk', 'cheese', 'butter', 'yogurt', 'cream'],
        'Pantry': ['flour', 'sugar', 'oil', 'rice', 'pasta', 'cereal', 'bread'],
        'Protein': ['chicken', 'beef', 'fish', 'egg', 'tofu', 'pork', 'shrimp'],
        'Spices': ['salt', 'pepper', 'cumin', 'paprika', 'oregano', 'basil'],
        'Other': []
    }
    categorized_ingredients = {cat: [] for cat in categories}
    
    ingredients = [i.strip() for i in grocery_list.ingredients.split('\n') if i.strip()]
    for item in ingredients:
        categorized = False
        for category, keywords in categories.items():
            if any(keyword in item.lower() for keyword in keywords):
                categorized_ingredients[category].append(item)
                categorized = True
                break
        if not categorized:
            categorized_ingredients['Other'].append(item)
    
    categorized_ingredients = {k: v for k, v in categorized_ingredients.items() if v}  # Remove empty categories
    
    # Handle PDF download
    if 'download_pdf' in request.GET:
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        p.setFont("Helvetica", 16)
        y = 750
        p.drawString(100, y, f"Grocery List: {grocery_list.title}")
        y -= 30
        p.setFont("Helvetica", 12)
        p.drawString(100, y, f"Created: {grocery_list.created_at.strftime('%B %d, %Y, %I:%M %p')}")
        y -= 30
        
        for category, items in categorized_ingredients.items():
            p.setFont("Helvetica-Bold", 14)
            p.drawString(100, y, category)
            y -= 20
            p.setFont("Helvetica", 12)
            for item in items:
                if y < 50:
                    p.showPage()
                    y = 750
                p.drawString(120, y, f"- {item}")
                y -= 20
            y -= 10
        
        p.showPage()
        p.save()
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="grocery_list_{grocery_list.id}.pdf"'
        return response
    
    # Handle email sending
    if 'email_list' in request.POST:
        try:
            subject = f"Your Grocery List: {grocery_list.title}"
            html_content = render_to_string('grocery_list_email.html', {
                'grocery_list': grocery_list,
                'categorized_ingredients': categorized_ingredients,
                'user': request.user,
            })
            text_content = f"Your Grocery List: {grocery_list.title}\n\n"
            for category, items in categorized_ingredients.items():
                text_content += f"{category}:\n"
                for item in items:
                    text_content += f"- {item}\n"
                text_content += "\n"
            
            email = EmailMultiAlternatives(
                subject,
                text_content,
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
            messages.success(request, "Grocery list sent to your email!")
        except Exception as e:
            messages.error(request, f"Failed to send email: {str(e)}")
        return redirect('grocery_list_detail', pk=pk)
    
    return render(request, 'grocery_list_detail.html', {
        'grocery_list': grocery_list,
        'categorized_ingredients': categorized_ingredients,
    })

@login_required
def grocery_list_edit(request, pk):
    # Edit an existing grocery list
    grocery_list = get_object_or_404(GroceryList, pk=pk, user=request.user)
    if request.method == 'POST':
        form = GroceryListForm(request.POST, instance=grocery_list)
        if form.is_valid():
            form.save()  # Save updates
            messages.success(request, "Grocery list updated successfully.")
            return redirect('grocery_list_detail', pk=pk)
    else:
        form = GroceryListForm(instance=grocery_list)  # Initialize form with current data
    return render(request, 'grocery_list_edit.html', {
        'grocery_list': grocery_list,
        'form': form,
    })

@csrf_exempt
@login_required
def delete_grocery_list(request, pk):
    # Delete a grocery list
    if request.method == 'POST':
        try:
            grocery_list = get_object_or_404(GroceryList, pk=pk, user=request.user)
            grocery_list.delete()  # Delete the list
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

@login_required
def recommend_recipes(request):
    # Display recipe recommendations based on user's saved recipes
    recommended_recipes = recommend_for(request.user)  # Get recommendations
    
    paginator = Paginator(recommended_recipes, 12)  # Paginate with 12 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    saved_recipe_ids = list(SavedRecipe.objects.filter(user=request.user).values_list('recipe_id', flat=True))  # Get saved IDs
    
    return render(request, 'recommendations.html', {
        'recommended_recipes': page_obj,
        'page_obj': page_obj,
        'saved_recipe_ids': saved_recipe_ids,
    })

def _popularity_queryset():
    # Helper function to get public recipes sorted by popularity
    return (
        Recipe.objects.filter(visibility="public")
        .annotate(pop_score=F("average_rating") * F("total_ratings"))
        .order_by("-pop_score")
    )

def recommend_for(user, k: int = 10):
    # Recommend recipes using TF-IDF similarity or popularity fallback
    recipes_qs = Recipe.objects.filter(visibility="public")  # Get all public recipes
    recipe_list: List[Recipe] = list(recipes_qs)

    saved_ids = list(SavedRecipe.objects.filter(user=user).values_list("recipe_id", flat=True))  # Get user's saved recipes

    if saved_ids:
        # Use TF-IDF for recommendations if user has saved recipes
        texts = [f"{r.title} {r.description} {r.ingredients}" for r in recipe_list]
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(texts)

        saved_idx = [idx for idx, r in enumerate(recipe_list) if r.id in saved_ids]
        if saved_idx:
            user_profile = tfidf_matrix[saved_idx].mean(axis=0)  # Create user profile
            user_profile = np.asarray(user_profile)
            sims = cosine_similarity(user_profile, tfidf_matrix)[0]  # Calculate similarities

            # Score and sort recipes by similarity
            scored = [
                (recipe_list[i].id, sims[i])
                for i in range(len(recipe_list))
                if recipe_list[i].id not in saved_ids
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            top_ids = [rid for rid, _ in scored[:k]]

            # Return ordered recipes
            ordering = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(top_ids)])
            return Recipe.objects.filter(pk__in=top_ids).order_by(ordering)

    # Fallback to popularity if no saved recipes
    return _popularity_queryset()[:k]


def custom_400(request, exception=None):
    # Custom handler for 400 Bad Request errors
    return render(request, 'error_pages/400.html', status=400)

def custom_403(request, exception=None):
    # Custom handler for 403 Forbidden errors
    return render(request, 'error_pages/403.html', status=403)

def custom_404(request, exception=None):
    # Custom handler for 404 Not Found errors
    return render(request, 'error_pages/404.html', status=404)

def custom_405(request, exception=None):
    # Custom handler for 405 Method Not Allowed errors
    return render(request, 'error_pages/405.html', status=405)

def custom_500(request):
    # Custom handler for 500 Internal Server errors
    return render(request, 'error_pages/500.html', status=500)