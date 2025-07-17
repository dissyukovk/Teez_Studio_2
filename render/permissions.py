# В файле permissions.py вашего приложения
from rest_framework.permissions import BasePermission
from django.contrib.auth.models import Group

class IsModeratorUser(BasePermission):
    """
    Allows access only to users in the 'Moderator' group.
    """
    message = "Вы не модератор." # Сообщение об ошибке

    def has_permission(self, request, view):
        # Проверяем, аутентифицирован ли пользователь
        if not request.user or not request.user.is_authenticated:
            return False

        # Проверяем, существует ли группа "Moderator"
        try:
            moderator_group = Group.objects.get(name='Moderator')
        except Group.DoesNotExist:
            # Если группа не найдена, можно либо запретить доступ,
            # либо логировать ошибку конфигурации.
            # В данном случае запрещаем доступ.
            self.message = "Группа 'Moderator' не найдена в системе."
            return False

        # Проверяем, состоит ли пользователь в группе "Moderator"
        return request.user.groups.filter(name='Moderator').exists()
