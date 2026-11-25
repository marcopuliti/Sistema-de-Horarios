from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from horarios.views import CambiarPasswordView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='horarios/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password/', CambiarPasswordView.as_view(), name='password_change'),
    path('', include('horarios.urls')),
]
