from django.urls import path
from . import views

app_name = 'checklist'

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('nouvelle/', views.nouvelle_fiche, name='nouvelle_fiche'),
    path('fiche/<int:fiche_id>/', views.fiche_detail, name='fiche_detail'),
    path('export/pdf/<int:fiche_id>/', views.export_pdf, name='export_pdf'),
    path('export/csv/<int:fiche_id>/', views.export_csv, name='export_csv'),
    path('signup/', views.signup, name='signup'),
    path('ateliers/', views.atelier_list, name='atelier_list'),
    path('ateliers/ajouter/', views.ajouter_atelier, name='ajouter_atelier'),
    path('ateliers/<int:atelier_id>/modifier/', views.modifier_atelier, name='modifier_atelier'),
    path('ateliers/<int:atelier_id>/supprimer/', views.supprimer_atelier, name='supprimer_atelier'),
]
