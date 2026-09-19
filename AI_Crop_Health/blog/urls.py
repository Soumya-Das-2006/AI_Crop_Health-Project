from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.blog_list, name='list'),
    path('search/', views.blog_search, name='search'),
    path('<int:blog_id>/', views.blog_detail, name='detail'),
    path('faq/', views.faq, name='faq'),
    path('blog/faq/', views.legacy_faq, name='legacy_faq'),
    path('<int:blog_id>/comment/', views.add_comment, name='add_comment'),
    path('category/<slug:category_slug>/', views.category_detail, name='category_detail'),
    path('tag/<path:tag_slug>/', views.tag_detail, name='tag_detail'),
    path('user-panel/', views.user_panel, name='user_panel'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
]
