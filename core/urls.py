from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from . import views
from .views import (
    product_list, 
    STRequestViewSet, 
    InvoiceViewSet, 
    UserViewSet,  
    StatusesListView, 
    bulk_upload_products, 
    strequest_list,  
    InvoiceListView,
    user_list,  
    get_requests,  
    create_request,  
    update_request, 
    invoice_list,  
    accept_products,
    send_products,
    check_barcode,  # Новый импорт для проверки штрихкода
    get_order_for_barcode,  # Новый импорт для получения заказа по штрихкоду
    ProductOperationCRUDViewSet,
    ProductOperationListView,
    add_product_operation,
    OrderListView,
    get_last_request,
    update_product_statuses,
    create_invoice,
    mark_as_defective,
    get_product_by_barcode,
    log_defect_operation,
    create_draft_request,
    finalize_request,
    order_list,
    request_details,  # Получение деталей заявки
    barcode_details,  # Получение деталей штрихкода
    update_request,    # Обновление заявки: добавление и удаление штрихкодов
    get_photographers,
    assign_photographer,
    update_request_status,
    get_retouchers,
    assign_retoucher,
    RetouchStatusListView,
    update_retouch_statuses_and_links,
    get_request_statuses,
    search_orders_by_barcode,
    OrderStatusListView,
    order_details,
    update_order_status,
    get_invoice_details,
    check_barcodes,
    create_order,
    upload_products_batch,
    get_history_by_barcode,
    move_statuses,
    stockman_list,
    ProductCategoryViewSet,
    upload_categories,
    CategoryListView,
    categories_list,
    defect_operations_list,
    PhotographerStatsView,
    RetoucherStatsView,
    ManagerProductStatsView,
    StockmanListView,
    ReadyPhotosView,
    UserURLsViewSet,
    STRequestHistoryViewSet,
    accepted_products_by_category,
    NofotoListView,
    update_product_info,
    add_blocked_barcodes,
    order_product_list,
    GetNextAPIKeyView,
    GetUserWorkStatusView,
    ToggleUserWorkStatusView
)

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_data = {
            'id':user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'groups': [group.name for group in user.groups.all()]
        }
        return Response(user_data)

# Роутер для CRUD операций
router = DefaultRouter()
router.register(r'strequests', STRequestViewSet, basename='strequest')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'users', UserViewSet, basename='user')
router.register(r'operations/crud', ProductOperationCRUDViewSet)
router.register(r'user-urls', UserURLsViewSet)
router.register('strequest-history', STRequestHistoryViewSet)

urlpatterns = [
    # CRUD операции
    path('requests/', get_requests, name='requests_list'),
    path('requests/create/', create_request, name='create_request'),
    path('api/invoices/', InvoiceViewSet.as_view({'get': 'list', 'post': 'create'}), name='invoice-crud'),
    path('api/invoices/create/', create_invoice, name='create_invoice'),
    path('api/create-request/', create_request, name='api_create_request'),
    path('', include(router.urls)),  # Для CRUD операций
    path('product-operations/', add_product_operation, name='add_product_operation'),
    path('update-product-statuses/', update_product_statuses, name='update_product_statuses'),
    path('api/products/<str:barcode>/', get_product_by_barcode, name='get_product_by_barcode'),
    path('api/photographers/', get_photographers, name='get_photographers'),
    path('api/request-statuses/', get_request_statuses, name='get_request_statuses'),
    path('api/order-statuses/', OrderStatusListView.as_view(), name='order-statuses'),
    path('orders/<str:orderNumber>/update-status/', update_order_status, name='update_order_status'),
    path('api/invoices/<str:invoice_number>/details/', get_invoice_details, name='get-invoice-details'),
    path('api/check-barcodes/', check_barcodes, name='check_barcodes'),    
    path('api/orders/create/', create_order, name='create_order'),
    path('api/upload-batch/', upload_products_batch, name='upload-products-batch'),
    path('api/product-history/<str:barcode>/', get_history_by_barcode, name='history_by_barcode'),
    path('api/upload-categories/', upload_categories, name='upload-categories'),
    path('public/defect-operations/', defect_operations_list, name='defect-operations-list'),
    path('api/photographer-stats/', PhotographerStatsView.as_view(), name='photographer-stats'),
    path('api/retoucher-stats/', RetoucherStatsView.as_view(), name='retouch-stats'),
    path('', include(router.urls)),
    path('api/category-counts/', accepted_products_by_category, name='category-counts'),
    path('nofoto_list/', NofotoListView.as_view(), name='nofoto_list'),
    path('products/update-info/', update_product_info, name='update_product_info'),
    path('blocked-barcodes/add/', add_blocked_barcodes, name='add_blocked_barcodes'),
    path('api/get-next-google-key/', GetNextAPIKeyView.as_view(), name='get_next_google_key'),

    # Основные API
    path('api/products/', product_list, name='product-list'),
    path('api/', include(router.urls)),
    path('api/accept-products/', accept_products, name='accept-products'),
    path('api/send-products/', send_products, name='send-products'),
    path('operations/', ProductOperationListView.as_view(), name='product_operation_list'),  # Для просмотра операций с пагинацией и фильтрацией
    path('order-list/', order_list, name='order-list'),
    path('get-last-request/<str:barcode>/', get_last_request, name='get_last_request'),
    path('api/products/mark-as-defective/', mark_as_defective, name='mark_as_defective'),
    path('api/log-defect/', log_defect_operation, name='log-defect'),
    path('api/create-draft-request/', create_draft_request, name='create_draft_request'),
    path('api/finalize-request/', finalize_request, name='finalize_request'),
    path('requests/<str:request_number>/assign-photographer/', assign_photographer, name='assign-photographer'),
    path('requests/<str:request_number>/update-status/', update_request_status, name='update-request-status'),
    path('api/retouchers/', get_retouchers, name='get_retouchers'),
    path('api/requests/<str:request_number>/assign-retoucher/', assign_retoucher, name='assign_retoucher'),
    path('api/orders/search-by-barcode/', search_orders_by_barcode, name='search_orders_by_barcode'),
    path('orders/<str:orderNumber>/details/', order_details, name='order_details'),
    path('api/move-statuses/', move_statuses, name='move_statuses'),
    path('api/stockman/', stockman_list, name='stockman_list'),
    path('api/categories/', categories_list, name='categories_list'),
    path('api/manager-product-stats/', ManagerProductStatsView.as_view(), name='manager-product-stats'),
    path('api/stockman-list/', StockmanListView.as_view(), name='stockman-list'),
    path('public/ready-photos/', ReadyPhotosView.as_view(), name='ready-photos'),
    path('assembly-start/<str:order_number>/', views.start_assembly, name='start_assembly'),
    path('assembly/<str:order_number>/<str:product_barcode>/', views.assemble_product, name='assemble_product'),
    path('accept-start/<str:order_number>/', views.start_acceptance, name='start_acceptance'),
    path('accept-order/<str:order_number>/', views.accept_order_products, name='accept_products'),
    path('accepted-order/<str:order_number>/<int:new_status>/', views.update_order_status, name='update_order_status'),
    path('orders/check/<str:order_number>/', views.check_order_status, name='check_order_status'),
    path('api/mark-as-opened/', views.mark_as_opened, name='mark_as_opened'),
       
    # Путь для получения деталей заявки
    path('requests/<int:request_number>/details/', request_details, name='request_details'),

    # Путь для получения деталей штрихкода
    path('barcode/<str:barcode>/details/', barcode_details, name='barcode_details'),

    # Путь для обновления заявки: добавление/удаление штрихкодов
    path('requests/<str:request_number>/update/', update_request, name='update_request'),
    path('api/retouch-statuses/', RetouchStatusListView.as_view(), name='retouch-statuses'),
    path('requests/<str:request_number>/update-retouch-statuses/', update_retouch_statuses_and_links, name='update-retouch-statuses'),

    # Новый маршрут для проверки штрихкода
    path('api/check-barcode/<str:barcode>/', check_barcode, name='check-barcode'),
    
    # Новый маршрут для получения заказа по штрихкоду
    path('api/get-order/<str:barcode>/', get_order_for_barcode, name='get-order'),
    
    # Статусы и накладные
    path('api/statuses/', StatusesListView.as_view(), name='statuses-list'),
    path('api/products/bulk-upload/', bulk_upload_products, name='bulk-upload'),
    path('api/invoices-list/filter/', invoice_list, name='invoice-list-filter'),
    
    # Фильтрация заявок и пользователей
    path('api/strequests-list/filter/', strequest_list, name='strequest-filter'),  
    path('api/users/', user_list, name='user-list'),
    
    # Данные о пользователе
    path('api/user/', UserDetailView.as_view(), name='user_detail'),
    path('order-products/', order_product_list, name='order_product_list'),

    #on_work
    path('user/work-status/', GetUserWorkStatusView.as_view(), name='get_user_work_status'),
    path('user/toggle-work-status/', ToggleUserWorkStatusView.as_view(), name='toggle_user_work_status'),
]
