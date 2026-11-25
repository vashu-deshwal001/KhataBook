from django.urls import path
from . import views
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('customers/', views.customer_list, name='customers'),
    path('customers/new/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
    path('customers/<int:pk>/password/', views.customer_password, name='customer_password'),
    path('ledger/', views.ledger, name='ledger'),
    path('ledger/new/', views.entry_create, name='entry_create'),
    path('ledger/<int:pk>/reverse/', views.entry_reverse, name='entry_reverse'),
    path('ledger/<int:pk>/edit/', views.entry_edit, name='entry_edit'),
    path('ledger/<int:pk>/delete/', views.entry_delete, name='entry_delete'),
    path('ledger/export/', views.export_ledger, name='export_ledger'),
    path('products/', views.products, name='products'),
    path('products/new/', views.product_edit, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('categories/new/', views.category_create, name='category_create'),
    path('files/<str:kind>/<int:pk>/', views.media_file, name='media_file'),
]
