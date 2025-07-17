# urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Existing URL
    path('ready-for-retouch/', views.ReadyForRetouchListView.as_view(), name='ready-for-retouch-list'),

    # 1. Get retouchers on work
    path('retouchers/on-work/', views.RetouchersOnWorkListView.as_view(), name='retouchers-on-work-list'),

    # 2. Create RetouchRequest
    path('retouch-requests/create/', views.CreateRetouchRequestView.as_view(), name='retouch-request-create'),
    
    # 3. List RetouchRequests (all or by status)
    path('retouch-requests/', views.RetouchRequestListView.as_view(), name='retouch-request-list-all'),
    path('retouch-requests/status/<int:status_id>/', views.RetouchRequestListView.as_view(), name='retouch-request-list-by-status'),

    # 4. Get RetouchRequest details
    path('retouch-requests/<int:request_number>/details/', views.RetouchRequestDetailView.as_view(), name='retouch-request-detail'),

    # 5. Change Retouch Status of a product
    path('retouch-products/update-status/', views.UpdateRetouchStatusView.as_view(), name='update-retouch-status'),

    # 6. Change SRetouch Status of a product
    path('retouch-products/update-s-status/', views.UpdateSRetouchStatusView.as_view(), name='update-s-retouch-status'),

    # 7. Change RetouchRequest status
    path('retouch-requests/<int:request_number>/update-status/<int:status_id>/', views.UpdateRetouchRequestStatusView.as_view(), name='update-retouch-request-status'),
    
    # 8. Statistics
    path('statistics/retouchers/', views.RetoucherStatisticsView.as_view(), name='retoucher-statistics'),

    # 9. Переназначить ретушера
    path('reassign-retoucher/', views.ReassignRetoucherView.as_view(), name='reassign-retoucher'),
]
