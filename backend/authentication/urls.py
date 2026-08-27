from django.urls import path

from authentication import views

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='auth-login'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('me/', views.CurrentAdminView.as_view(), name='auth-me'),
]
