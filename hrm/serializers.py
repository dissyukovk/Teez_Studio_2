# hrm/serializers.py

# ... другие импорты ...
from rest_framework import serializers
from django.contrib.auth.models import User

# Финальная версия этого сериалайзера
class UserFullNameSerializer(serializers.ModelSerializer):
    """
    Сериализатор для пользователя, выводящий всю основную информацию,
    включая данные из HRM.
    """
    groups = serializers.StringRelatedField(many=True)
    
    # Данные из UserProfile
    telegram_name = serializers.CharField(source='profile.telegram_name', read_only=True)
    telegram_id = serializers.CharField(source='profile.telegram_id', read_only=True)
    phone_number = serializers.CharField(source='profile.phone_number', read_only=True)
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)
    
    # Данные о должности из HRM
    position = serializers.StringRelatedField(source='profile.position', read_only=True)
    department = serializers.StringRelatedField(source='profile.position.department', read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email', 
            'groups', 'avatar', 'position', 'department',
            'telegram_name', 'telegram_id', 'phone_number',
        )
