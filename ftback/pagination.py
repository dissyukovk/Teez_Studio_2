from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 2000

class SRReadyProductsPagination(PageNumberPagination):
    # Стандартный размер страницы
    page_size = 50
    # Параметр, через который можно изменить page_size
    page_size_query_param = 'page_size'
    max_page_size = 2000

class RetouchRequestPagination(PageNumberPagination):
    page_size = 50             # По умолчанию 50
    page_size_query_param = 'page_size'
    max_page_size = 2000

class ReadyPhotosPagination(PageNumberPagination):
    page_size = 100             # дефолт
    page_size_query_param = 'page_size'
    max_page_size = 200000     # максимальный размер
