from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend that allows authentication with either a username or an email.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)

        # Try to find a user matching the username
        try:
            user = UserModel.objects.get(username=username)
        except UserModel.DoesNotExist:
            # If no user found with username, try email
            try:
                user = UserModel.objects.get(email=username)
            except UserModel.DoesNotExist:
                return None

        # Check password and if user is allowed to authenticate
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
