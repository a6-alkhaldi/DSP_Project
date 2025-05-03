Recipe Planner
Recipe Planner is a web application built with Django that allows users to create, share, and manage recipes, meal plans, and grocery lists. It provides features such as user profiles, following other users, and managing dietary restrictions.
Features

User authentication and profiles
Recipe creation, sharing, and management
Meal planning with date ranges and meal types
Grocery list generation and management
Dietary restrictions and tags
Following other users and viewing their recipes
Commenting and rating recipes
Recommendations based on saved recipes

Setup

Ensure you have Python 3.8 or higher installed.


Clone the repository:
git clone https://github.com/a6-alkhaldi/DSP_Project.git
cd recipe-planner


Create a virtual environment and activate it:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


Install the dependencies:
pip install -r requirements.txt


Set up the database:

Ensure MySQL is installed and running.
Create a database named recipe_planner.
Update the database settings in settings.py if necessary.


Apply migrations:
python manage.py migrate


During migration, a superuser with username "admin" and password "admin123" is created automatically.


Run the development server:
python manage.py runserver


Access the application at http://127.0.0.1:8000/

Log in to the admin interface at http://127.0.0.1:8000/admin/ using "admin" and "admin123".


Configuration

Email Settings: Configure email settings in settings.py for email verification and password reset. Update EMAIL_HOST_USER and EMAIL_HOST_PASSWORD with your credentials.
CAPTCHA: Configure CAPTCHA settings in settings.py if needed.

Usage

Home Page: View popular and newest recipes.
Browse Recipes: Filter recipes by category, dietary tags, etc.
Create Recipe: Fill in recipe details, upload images, select tags, and set visibility.
Meal Plans: Create plans with dates and assign recipes to meal types.
Grocery Lists: Generate from meal plans or create manually.
Profile: Update bio, avatar, social links, and privacy settings.
Follow Users: Follow others to see their recipes.
Recommendations: View suggested recipes based on saved recipes.

Project Structure

recipes: Main app with models, views, forms, templates.
templates: HTML templates.
static: CSS, JS, images.
media: User-uploaded files.
