from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth.LogoutView.as_view(), name='logout'),
    path('accounts/password/', auth.PasswordChangeView.as_view(template_name='book/form.html', success_url='/'), name='password_change'),
    path('', include('book.urls')),
]
