# ftback/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Маршрут для WebSocket-соединений, например, для отслеживания прогресса задач
    re_path(r'ws/task_progress/(?P<user_id>\d+)/$', consumers.TaskProgressConsumer.as_asgi()),
    # Вы можете добавить другие маршруты по мере необходимости
]
