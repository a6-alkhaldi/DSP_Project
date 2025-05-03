from fractions import Fraction
import re
from django.db import models
from django.contrib.auth.models import User
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# Model to track email verification for users
class EmailVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)  # Unique token for verification
    created_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)  # Whether the email has been verified

    def __str__(self):
        return f"{self.user.email} - {self.verified}"

# Model for dietary restrictions with predefined choices
class DietaryRestriction(models.Model):
    DIET_CHOICES = [
        ('DF', 'Dairy-Free'), ('EF', 'Egg-Free'), ('GF', 'Gluten-Free'),
        ('NF', 'Nut-Free'), ('SF', 'Soy-Free'), ('VG', 'Vegan'),
        ('VT', 'Vegetarian'), ('KF', 'Keto-Friendly'), ('PF', 'Pescatarian'),
        ('LC', 'Low-Carb'), ('LS', 'Low-Sodium'), ('LF', 'Low-FODMAP'),
        ('HL', 'Halal'), ('MD', 'Mediterranean Diet'), ('SU', 'Sugar-Free'),
        ('AF', 'Allium-Free'), ('SH', 'Shellfish-Free'), ('DB', 'Diabetic-Friendly'),
    ]

    name = models.CharField(max_length=2, choices=DIET_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()  # Returns the human-readable name

# Extended user profile with additional fields
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # Social media links
    twitter_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    personal_website = models.URLField(blank=True, null=True)

    # Many-to-many relationship with dietary restrictions
    dietary_restrictions = models.ManyToManyField(DietaryRestriction, blank=True)

    # Boolean fields for controlling what is displayed on the profile
    show_name = models.BooleanField(default=True)
    show_avatar = models.BooleanField(default=True)
    show_social_links = models.BooleanField(default=True)
    show_dietary_restrictions = models.BooleanField(default=True)
    show_recipes = models.BooleanField(default=True)
    show_followers = models.BooleanField(default=True)
    show_following = models.BooleanField(default=True)

    # Methods to get counts of followers and following
    def get_followers_count(self):
        return self.user.followers.count()

    def get_following_count(self):
        return self.user.following.count()

    def __str__(self):
        return f"{self.user.username}'s Profile"

# Signal receivers to create and save profiles automatically
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

# Model for recipes with various fields and properties
class Recipe(models.Model):
    CATEGORY_CHOICES = [
        # Meal Types
        ('BR', 'Breakfast'), ('LU', 'Lunch'), ('DI', 'Dinner'),
        ('SN', 'Snack'), ('DS', 'Dessert'),
        # Cuisine Types
        ('IT', 'Italian'), ('MX', 'Mexican'), ('AS', 'Asian'),
        ('ME', 'Mediterranean'), ('IN', 'Indian'), ('TH', 'Thai'),
        ('CN', 'Chinese'), ('JP', 'Japanese'), ('GR', 'Greek'),
        ('FF', 'Fast Food'),
        # Cooking Styles
        ('BK', 'Baked'), ('GR', 'Grilled'), ('RV', 'Raw Vegan'),
        ('SM', 'Smoothies'), ('SO', 'Soups'), ('ST', 'Stews'),
        # Special Collections
        ('KC', 'Kids-Friendly'), ('QC', 'Quick & Easy'), ('ML', 'Meal Prep'),
        ('CE', 'Comfort Food'),
    ]

    VISIBILITY_CHOICES = [
        ('public', 'Public'), ('followers_only', 'Followers Only'), ('private', 'Private'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipes')
    ingredients = models.TextField()
    instructions = models.TextField(null=True)
    category = models.CharField(max_length=2, choices=CATEGORY_CHOICES)
    cooking_time = models.PositiveIntegerField(help_text="Total cooking time in minutes", null=True)
    calories = models.PositiveIntegerField(null=True, blank=True)
    proteins = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    carbs = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    dietary_tags = models.ManyToManyField(DietaryRestriction, blank=True)
    visibility = models.CharField(max_length=15, choices=VISIBILITY_CHOICES, default='public')
    created_at = models.DateTimeField(auto_now_add=True)
    average_rating = models.FloatField(default=0)
    total_ratings = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']  # Order by creation date, newest first

    # Property to check if the recipe is new (created within the last 7 days)
    @property
    def is_new(self):
        return (timezone.now() - self.created_at).days <= 7

    # Property to check if the recipe is popular (average rating >= 4 and at least 10 ratings)
    @property
    def is_popular(self):
        return self.average_rating >= 4 and self.total_ratings >= 10

    # Property to check if the recipe is a quick meal (cooking time <= 30 minutes)
    @property
    def is_quick_meal(self):
        return self.cooking_time <= 30

# Model for storing images associated with recipes
class RecipeImage(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='recipe_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

# Model for comments on recipes, supporting threaded replies
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', null=True, blank=True, related_name='replies', on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # Newest comments first

    def __str__(self):
        return f"{self.user.username}: {self.text[:50]}"

# Model for liking or disliking comments
class CommentRating(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    like = models.BooleanField(default=False)  # True for like, False for dislike

    class Meta:
        unique_together = ('comment', 'user')  # One rating per user per comment

# Model for rating recipes (1 to 5 stars)
class RecipeRating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'recipe')  # One rating per user per recipe

# Model for saving or favoriting recipes
class SavedRecipe(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_recipes')
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'recipe')  # Prevent duplicate saves

    def __str__(self):
        return f"{self.user.username} saved {self.recipe.title}"

# Model for meal plans
class MealPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meal_plans')
    title = models.CharField(max_length=200, default="Weekly Plan")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    grocery_list = models.OneToOneField(
        'GroceryList',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meal_plan'
    )

    def __str__(self):
        return f"{self.user.username}'s {self.title} starting {self.start_date}"

# Model to assign recipes to specific days and meal types in a meal plan
class MealPlanRecipe(models.Model):
    MEAL_TYPES = [
        ('breakfast', 'Breakfast'), ('lunch', 'Lunch'), ('dinner', 'Dinner'), ('snack', 'Snack'),
    ]

    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name='meal_plan_recipes')
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE)
    day = models.DateField()
    meal_type = models.CharField(max_length=50, choices=MEAL_TYPES)

    class Meta:
        unique_together = ('meal_plan', 'recipe', 'day', 'meal_type')  # Prevent duplicates

    def __str__(self):
        return f"{self.meal_plan} - {self.recipe.title} on {self.day} for {self.meal_type}"

# Model for grocery lists with automatic ingredient merging
class GroceryList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='grocery_lists')
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE, null=True, blank=True)
    ingredients = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200, default="Untitled Grocery List")

    def __str__(self):
        return f"{self.user.username}'s Grocery List - {self.title} ({self.created_at})"

    # Automatically merge similar ingredients when saving
    def save(self, *args, **kwargs):
        if self.ingredients:
            ingredient_lines = [line.strip() for line in self.ingredients.split('\n') if line.strip()]
            merged_ingredients = self.merge_ingredients(ingredient_lines)
            self.ingredients = '\n'.join(merged_ingredients)
        super().save(*args, **kwargs)

    # Helper method to merge ingredients with quantities
    def merge_ingredients(self, ingredient_lines):
        ingredient_dict = {}
        for line in ingredient_lines:
            match = re.match(r'(\d*\.?\d+(?:/\d+)?)\s*(\w*)\s*(.*)', line)
            if match:
                quantity_str, unit, ingredient = match.groups()
                try:
                    if '/' in quantity_str:
                        quantity = float(sum(Fraction(s) for s in quantity_str.split()))
                    else:
                        quantity = float(quantity_str)
                    key = (ingredient.lower().strip(), unit.lower().strip())
                    if key in ingredient_dict:
                        ingredient_dict[key]['quantity'] += quantity
                    else:
                        ingredient_dict[key] = {
                            'quantity': quantity,
                            'unit': unit,
                            'ingredient': ingredient
                        }
                except ValueError:
                    key = (line.lower().strip(), '')
                    ingredient_dict[key] = {'original': line}
            else:
                key = (line.lower().strip(), '')
                ingredient_dict[key] = {'original': line}

        merged = []
        for key, data in ingredient_dict.items():
            if 'original' in data:
                merged.append(data['original'])
            else:
                quantity = data['quantity']
                unit = data['unit']
                ingredient = data['ingredient'].title() if not data['ingredient'].isupper() else data['ingredient']
                merged.append(f"{quantity} {unit} {ingredient}".strip())
        return sorted(merged)

    class Meta:
        ordering = ['-created_at']  # Order by creation date, newest first

# Model for user follow relationships
class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'followed')  # Prevent multiple follows

    def __str__(self):
        return f"{self.follower.username} follows {self.followed.username}"