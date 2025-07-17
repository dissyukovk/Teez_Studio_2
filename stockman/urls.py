from django.urls import path
from . import views

urlpatterns = [
    path('orders/', views.OrderListView.as_view(), name='order-list'),
    path('order-statuses/', views.OrderStatusListView.as_view(), name='order-status-list'),
    path('order-detail/<int:order_number>/', views.OrderDetailAPIView.as_view(), name='order-detail'),
    path('OrderAcceptStart/<int:ordernumber>/', views.order_accept_start, name='order_accept_start'),
    path('OrderCheckProduct/<int:ordernumber>/<str:barcode>/', views.order_check_product, name='order_check_product'),
    path('OrderAcceptProduct/<int:ordernumber>/', views.order_accept_product, name='order_accept_product'),
    path('strequest-create/', views.strequest_create, name='strequest_create'),
    path('strequest-create-barcodes/', views.strequest_create_barcodes, name='strequest_create_barcodes'),
    path('strequest-search/', views.STRequestSearchListView.as_view(), name='strequest_search'),
    path('strequest-detail/<str:STRequestNumber>/', views.STRequestDetailView.as_view(), name='strequest_detail'),
    path('strequest-statuses/', views.STRequestStatusListView.as_view(), name='strequest_status_list'),
    path('strequest-add-barcode/<str:STRequestNumber>/<str:Barcode>/', views.strequest_add_product, name='strequest_add_product'),
    path('strequest-delete-barcode/<str:STRequestNumber>/<str:Barcode>/', views.strequest_delete_barcode, name='strequest_delete_barcode'),
    path('order-accept-end/<int:OrderNumber>/', views.order_accept_end, name='order_accept_end'),
    path('invoices/', views.InvoiceListView.as_view(), name='invoice-list'),
    path('invoice-detail/<invoceNumber>/', views.InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoice-check-barcode/', views.InvoiceCheckBarcodeView.as_view(), name='invoice-check-barcode'),
    path('invoice-create/', views.InvoiceCreateView.as_view(), name='invoice-create'),
    path('product-mark-defect/<barcode>/', views.ProductMarkDefectView.as_view(), name='product-mark-defect'),
    path('product-mark-opened/<barcode>/', views.ProductMarkOpenedView.as_view(), name='product-mark-opened'),
    path('current-products/', views.PublicCurrentProducts.as_view(), name='current-products'),
    path('orderproducts/', views.OrderProductListAPIView.as_view(), name='orderproducts-list'),
    path('export_order_products/', views.export_order_products, name='export-order-products'),
    #Принятые без заявок
    path('problematic-products-1/', views.ProblematicProduct1ListView.as_view(), name='problematic-product-list-1'),
    #дубликаты в заявках
    path('problematic-products-2/', views.ProblematicProduct2ListView.as_view(), name='problematic-product-list-2'),
    #отснятые более суток назад, не отправленные
    path('problematic-products-3/', views.ProblematicProduct3ListView.as_view(), name='problematic-product-list-3'),
    #печать шк
    path('BarcodePrint/<str:barcode>/', views.BarcodePrintView.as_view(), name='barcode-print'),
    #Вручную меняем STRequestType
    path('change-request-type/<int:RequestNumber>/<int:strequest_type_id>/', views.manual_set_strequest_type, name='manual-set-strequest-type'),
]
