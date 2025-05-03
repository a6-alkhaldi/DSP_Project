# recipes/tests.py
from datetime import date
import json
from django.contrib.messages import get_messages
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Follow, Recipe, RecipeRating
from recipes import models
from django.db.models import Avg
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.test import TestCase
from .forms import MealPlanForm, RecipeForm, SignUpForm
from django.contrib.auth.models import User
from .models import EmailVerification
from .models import Recipe, SavedRecipe
from django.urls import reverse
from .models import MealPlan, MealPlanRecipe, GroceryList

class AuthTests(TestCase):
    def test_password_reset_flow(self):
        # Create user with known password
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='oldpass'
        )
        
        # Step 1: Request password reset
        response = self.client.post(
            reverse('password_reset'),
            {'email': 'test@example.com'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        
        # Step 2: Generate token and UID
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Step 3: Access password reset confirm page (follow redirects)
        reset_url = reverse('password_reset_confirm', args=[uid, token])
        response = self.client.get(reset_url, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Get the final redirected URL (e.g., /reset/set-password/)
        if response.redirect_chain:
            final_url = response.redirect_chain[-1][0]
        else:
            final_url = reset_url
        
        # Step 4: Submit new password to the final URL
        response = self.client.post(
            final_url,
            {
                'new_password1': 'NewSecurePass123!',
                'new_password2': 'NewSecurePass123!'
            },
            follow=True
        )
        self.assertRedirects(response, reverse('password_reset_complete'))
        
        # Step 5: Verify password update
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewSecurePass123!'))
        
        # Step 6: Test login with new password
        self.assertTrue(
            self.client.login(username='testuser', password='NewSecurePass123!')
        )

class RecipeModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            cooking_time=30,
            visibility='public'
        )

    def test_recipe_creation(self):
        self.assertEqual(self.recipe.title, 'Test Recipe')
        self.assertEqual(self.recipe.author.username, 'testuser')

    def test_is_new_property(self):
        # Test if recipe is considered "new" (created within 7 days)
        self.recipe.created_at = timezone.now() - timezone.timedelta(days=6)
        self.assertTrue(self.recipe.is_new)
        self.recipe.created_at = timezone.now() - timezone.timedelta(days=8)
        self.assertFalse(self.recipe.is_new)

    def test_is_popular_property(self):
        # Create 10 unique users to rate the recipe
        for i in range(10):
            user = User.objects.create_user(
                username=f'testuser{i}',
                password=f'testpass{i}'
            )
            RecipeRating.objects.create(
                user=user,
                recipe=self.recipe,
                rating=5
            )
        
        # Manually update recipe stats (replace with signals in production)
        ratings = self.recipe.ratings.all()
        self.recipe.total_ratings = ratings.count()
        self.recipe.average_rating = ratings.aggregate(Avg('rating'))['rating__avg']  # Fixed
        self.recipe.save()
        
        self.assertTrue(self.recipe.is_popular)

        

class SignUpFormTest(TestCase):
    def test_email_uniqueness_validation(self):
        # Create a user with existing email
        User.objects.create_user(username='existing', email='existing@example.com', password='testpass123')
        form_data = {
            'username': 'newuser',
            'email': 'existing@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'agree_to_terms': True
        }
        form = SignUpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)  # Check for email validation error



class SignUpFormTest(TestCase):
    def test_email_uniqueness_validation(self):
        # Create a user with existing email
        User.objects.create_user(username='existing', email='existing@example.com', password='testpass123')
        form_data = {
            'username': 'newuser',
            'email': 'existing@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'agree_to_terms': True
        }
        form = SignUpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)  # Check for email validation error

class HomeViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.recipe = Recipe.objects.create(
            title='Public Recipe',
            author=self.user,
            visibility='public'
        )

    def test_home_view_returns_popular_and_new_recipes(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Public Recipe')
        self.assertIn('popular_recipes', response.context)
        self.assertIn('newest_recipes', response.context)


class LoginTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Create unverified email entry
        EmailVerification.objects.create(user=self.user, verified=False)

    def test_login_with_unverified_email(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'test@example.com', 'password': 'testpass123'},
            follow=True  # Follow redirects
        )
        # Check message in redirected response
        messages = list(response.context['messages'])
        self.assertIn('Please verify your email address', str(messages[0]))



class ToggleSaveRecipeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            visibility='public'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_toggle_save_recipe(self):
        # First request saves the recipe
        response = self.client.post(
            reverse('toggle_save_recipe', args=[self.recipe.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json()['action'], 'saved')
        # Second request unsaves it
        response = self.client.post(
            reverse('toggle_save_recipe', args=[self.recipe.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json()['action'], 'unsaved')


class MealPlanIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            ingredients='Salt\nPepper',
            visibility='public'
        )
        self.client.login(username='testuser', password='testpass123')

    def test_meal_plan_creates_grocery_list(self):
        # Create meal plan
        meal_plan = MealPlan.objects.create(
            user=self.user,
            title='Test Plan',
            start_date=date.today(),
            end_date=date.today()
        )
        # Add recipe to meal plan
        MealPlanRecipe.objects.create(
            meal_plan=meal_plan,
            recipe=self.recipe,
            day=date.today(),
            meal_type='lunch'
        )
        # Check if grocery list is created with ingredients
        grocery_list = GroceryList.objects.get(meal_plan=meal_plan)
        self.assertIn('Salt', grocery_list.ingredients)
        self.assertIn('Pepper', grocery_list.ingredients)


class FollowTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='test123')
        self.user2 = User.objects.create_user(username='user2', password='test123')
        self.client.login(username='user1', password='test123')

    def test_follow_user(self):
        response = self.client.post(
            reverse('follow_user', args=['user2']),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Follow.objects.filter(follower=self.user1, followed=self.user2).exists())

    def test_unfollow_user(self):
        Follow.objects.create(follower=self.user1, followed=self.user2)
        response = self.client.post(
            reverse('unfollow_user', args=['user2']),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Follow.objects.filter(follower=self.user1, followed=self.user2).exists())

    def test_private_followers_list(self):
        # Set user2's followers list to private
        profile = self.user2.profile
        profile.show_followers = False
        profile.save()
        
        response = self.client.get(reverse('api_followers', args=['user2']))
        self.assertIn('error', response.json())

class MealPlanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='test123')
        self.recipe = Recipe.objects.create(
            title='Test Recipe',
            author=self.user,
            ingredients='Salt\nPepper',
            cooking_time=20,  
            visibility='public'
        )
        self.client.login(username='testuser', password='test123')

    def test_meal_plan_creation(self):
        response = self.client.post(reverse('create_meal_plan'), {
            'title': 'Test Plan',
            'start_date': '2030-01-01',  # Future date
            'end_date': '2030-01-07',
            'description': 'Test description',  # Add if required
            'selected_recipes_data': json.dumps([{
                'id': self.recipe.id,
                'day': '2030-01-01',
                'meal_type': 'lunch'
            }])
        })
        self.assertRedirects(response, reverse('meal_plan_detail', args=[MealPlan.objects.first().pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MealPlan.objects.filter(title='Test Plan').exists())
        self.assertTrue(MealPlanRecipe.objects.count(), 1)

    def test_grocery_list_auto_update(self):
        meal_plan = MealPlan.objects.create(
            user=self.user,
            title='Test Plan',
            start_date='2024-01-01',
            end_date='2024-01-07'
        )
        MealPlanRecipe.objects.create(
            meal_plan=meal_plan,
            recipe=self.recipe,
            day='2024-01-01',
            meal_type='lunch'
        )
        grocery_list = GroceryList.objects.get(meal_plan=meal_plan)
        self.assertIn('Salt', grocery_list.ingredients)

class RecipeVisibilityTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='author', password='test123')
        self.user = User.objects.create_user(username='user', password='test123')
        self.recipe = Recipe.objects.create(
            title='Private Recipe',
            author=self.author,
            instructions="Test instructions", 
            visibility='private'
        )

    def test_private_recipe_access(self):
        self.client.login(username='user', password='test123')
        response = self.client.get(reverse('recipe_detail', args=[self.recipe.id]), follow=True)
        
        # Check message content
        messages = list(response.context['messages'])
        self.assertIn('This recipe is private', str(messages[0]))

    def test_followers_only_access(self):
        self.recipe.visibility = 'followers_only'
        self.recipe.save()
        self.client.login(username='user', password='test123')
        
        # User cannot access before following
        response = self.client.get(reverse('recipe_detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 302)
        
        # User follows author
        Follow.objects.create(follower=self.user, followed=self.author)
        response = self.client.get(reverse('recipe_detail', args=[self.recipe.id]))
        self.assertEqual(response.status_code, 200)

class FormValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='test123')

    def test_meal_plan_form_invalid_dates(self):
        form_data = {
            'title': 'Invalid Dates',
            'start_date': '2030-01-10',  # Future date
            'end_date': '2030-01-01'     # End before start
        }
        form = MealPlanForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('End date cannot be before start date', form.errors['__all__'][0])

    def test_recipe_form_missing_required_fields(self):
        form_data = {
            'title': 'Incomplete Recipe',
            'category': 'BR'  
        }
        form = RecipeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('ingredients', form.errors)

class EdgeCaseTests(TestCase):
    def test_recipe_without_images(self):
        user = User.objects.create_user(username='testuser', password='test123')
        self.client.login(username='testuser', password='test123')
        response = self.client.post(reverse('add_recipe'), {
            'title': 'No Images Recipe',
            'ingredients': 'Salt',
            'instructions': 'Mix',
            'category': 'BR',
            'visibility': 'public'
        })
        self.assertEqual(response.status_code, 200)  # Form fails due to missing images
        self.assertIn('images', response.context['form'].errors)


    def test_duplicate_saved_recipe(self):
        user = User.objects.create_user(username='testuser', password='test123')
        recipe = Recipe.objects.create(title='Test Recipe', author=user)
        SavedRecipe.objects.create(user=user, recipe=recipe)
        
        # Log in the user
        self.client.login(username='testuser', password='test123')
        
        response = self.client.post(
            reverse('toggle_save_recipe', args=[recipe.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json()['action'], 'unsaved') # Should unsave instead

