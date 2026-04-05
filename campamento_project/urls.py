"""
URL configuration for campamento_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from campamento import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.lista_campistas, name='lista_campistas'),
    path('campistas-data/', views.campistas_data, name='campistas_data'),
    path('agregar/', views.agregar_campista, name='agregar_campista'),
    path('editar/<int:campista_id>/', views.editar_campista, name='editar_campista'),
    path('agregar_pago/<int:campista_id>/', views.agregar_pago, name='agregar_pago'),
    path('eliminar/<int:campista_id>/', views.eliminar_campista, name='eliminar'),
    path('subsidiado/<int:campista_id>/', views.marcar_subsidiado, name='marcar_subsidiado'),
]
