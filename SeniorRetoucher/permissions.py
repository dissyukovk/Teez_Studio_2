# permissions.py
from rest_framework.permissions import BasePermission

class IsSeniorRetoucher(BasePermission):
    """
    Custom permission to only allow users in the 'Старший ретушер' group.
    """
    def has_permission(self, request, view):
        # Check if the user is authenticated and belongs to the required group.
        return request.user and request.user.is_authenticated and request.user.groups.filter(name='Старший ретушер').exists()
