from django.urls import path
from . import views
from .views import verify_email
from django.contrib.auth import views as auth_views
from .forms import CustomPasswordResetForm
from .forms import CustomSetPasswordForm


urlpatterns = [
    path('', views.home, name='home'), 
    path('signup/', views.signup, name='signup'),
    path('refresh-captcha/', views.refresh_captcha, name='refresh_captcha'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('verify-email/<uuid:token>/', verify_email, name='verify_email'),
    path('login/', views.user_login, name='login'),
    path(
        'password_reset/', 
        auth_views.PasswordResetView.as_view(
            template_name='registration/custom_password_reset_form.html',
            form_class=CustomPasswordResetForm
        ), 
        name='password_reset'
    ),
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='registration/custom_password_reset_done.html'), 
         name='password_reset_done'),
    path(
        'reset/<uidb64>/<token>/', 
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/custom_password_reset_confirm.html',
            form_class=CustomSetPasswordForm
        ), 
        name='password_reset_confirm'
    ),
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/custom_password_reset_complete.html'), 
         name='password_reset_complete'),
    path('profile/', views.profile, name='profile'),
    path('profile/settings/', views.account_settings, name='account_settings'),

    path('profile/my-recipes/', views.my_recipes, name='my_recipes'),
    path('profile/my-saved-recipes/', views.my_saved_recipes, name='my_saved_recipes'),
    path('profile/my-meal-plans/', views.my_meal_plans, name='my_meal_plans'),
    path('profile/my-grocery-lists/', views.my_grocery_lists, name='my_grocery_lists'),
    path('profile/my-comments/', views.my_comments, name='my_comments'),
    path('comments/<int:pk>/delete/', views.delete_comment, name='delete_comment'),
    path('comments/<int:pk>/edit/', views.edit_comment, name='edit_comment'),
    path('users/<str:username>/', views.public_profile, name='public_profile'),
    path('profile/upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('profile/remove-avatar/', views.remove_avatar, name='remove_avatar'),
    path('profile/privacy/', views.privacy_settings, name='privacy_settings'),
    path('following-recipes/', views.following_recipes, name='following_recipes'),
    path('follow/<str:username>/', views.follow_user, name='follow_user'),
    path('unfollow/<str:username>/', views.unfollow_user, name='unfollow_user'),
    path('add-recipe/', views.add_recipe, name='add_recipe'),
    path('recommendations/', views.recommend_recipes, name='recommendations'),
    path('public_profile/<str:username>/', views.public_profile, name='public_profile'),
    path('api/followers/<str:username>/', views.api_followers, name='api_followers'),
    path('api/following/<str:username>/', views.api_following, name='api_following'),
    path('follow_user/<str:username>/', views.follow_user, name='follow_user'),
    path('unfollow_user/<str:username>/', views.unfollow_user, name='unfollow_user'),
    path('recipes/<int:pk>/', views.RecipeDetailView.as_view(), name='recipe_detail'),
    path('recipes/<int:recipe_id>/add_comment/', views.add_comment, name='add_comment'),
    path('comments/<int:comment_id>/rate/', views.rate_comment, name='rate_comment'),
    path('comments/<int:comment_id>/get_replies/', views.get_replies, name='get_replies'),
    path('recipes/<int:pk>/rate/', views.rate_recipe, name='rate_recipe'),
    path('save-grocery-list/', views.save_grocery_list, name='save_grocery_list'),
    path('browse/', views.browse_recipes, name='browse-recipes'),
    path('recipes/<int:pk>/quick-view/', views.recipe_quick_view, name='recipe-quick-view'),
    path('recipes/<int:pk>/', views.RecipeDetailView.as_view(), name='recipe-detail'),
    path('meal-plans/', views.my_meal_plans, name='my_meal_plans'),
    path('meal-plans/create/', views.create_meal_plan, name='create_meal_plan'),
    path('meal-plans/<int:pk>/', views.meal_plan_detail, name='meal_plan_detail'),
    path('meal-plans/<int:pk>/remove-recipe/', views.remove_recipe_from_meal_plan, name='remove_recipe_from_meal_plan'),
    path('meal-plans/<int:pk>/edit/', views.edit_meal_plan, name='edit_meal_plan'),
    path('meal-plans/<int:pk>/remove-recipe/', views.remove_recipe_from_meal_plan, name='remove_recipe_from_meal_plan'),
    path('meal-plans/<int:pk>/delete/', views.delete_meal_plan, name='delete_meal_plan'),
    path('grocery-lists/<int:pk>/', views.grocery_list_detail, name='grocery_list_detail'),
    path('grocery-lists/<int:pk>/edit/', views.grocery_list_edit, name='grocery_list_edit'),
    path('grocery-lists/<int:pk>/delete/', views.delete_grocery_list, name='delete_grocery_list'),
    path('get-user-meal-plans/', views.get_user_meal_plans, name='get_user_meal_plans'),
    path('add-recipe-to-meal-plan/', views.add_recipe_to_meal_plan, name='add_recipe_to_meal_plan'),
    path('recipes/<int:recipe_id>/save/', views.toggle_save_recipe, name='toggle_save_recipe'),
    path('recipes/<int:pk>/delete/', views.delete_recipe, name='delete_recipe'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),

    
    
]

