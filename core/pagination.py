# pagination.py (например, можно создать этот файл для кастомной пагинации)
from rest_framework.pagination import PageNumberPagination

class NofotoPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 999999
