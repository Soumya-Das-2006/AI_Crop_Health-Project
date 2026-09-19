from django.urls import path
from . import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('category/<slug:category>/', views.catalog, name='category'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/<slug:slug>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<slug:slug>/', views.update_cart, name='update_cart'),
    path('cart/remove/<slug:slug>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.my_orders, name='orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
]