# telegram_bot/auth_logic.py
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from core.models import UserProfile

@sync_to_async
def check_user_credentials(username, password) -> bool:
    """
    Проверяет учетные данные пользователя в синхронном мире Django.
    Использует @sync_to_async для безопасного вызова из асинхронного кода.
    """
    user = authenticate(username=username, password=password)
    return user is not None

@sync_to_async
def update_user_telegram_profile(username, telegram_id, telegram_name) -> bool:
    """
    Находит пользователя по логину и обновляет/создает его UserProfile.
    """
    try:
        user = User.objects.get(username=username)
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.telegram_id = str(telegram_id)
        profile.telegram_name = telegram_name
        profile.save()
        return True
    except User.DoesNotExist:
        return False
    except Exception as e:
        print(f"Error updating profile for {username}: {e}")
        return False
