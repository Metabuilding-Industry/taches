from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_http_methods
from .models import FicheSuivi, Atelier, Etape, Tache, Incident, RetourExperience, MesureComposants, MelangeMortier
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
import csv
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django import forms
import json

# Create your views here.

class CustomUserCreationForm(UserCreationForm):
    ROLE_CHOICES = (
        ("operateur", "Opérateur"),
        ("controleur", "Contrôleur"),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, label="Rôle souhaité")
    email = forms.EmailField(required=True, label="Adresse email")

    class Meta:
        model = User
        fields = ("username", "email", "role", "password1", "password2")


@login_required
def accueil(request):
    fiches = FicheSuivi.objects.filter(operateur=request.user)
    return render(request, 'checklist/accueil.html', {'fiches': fiches})


@login_required
def nouvelle_fiche(request):
    ateliers = Atelier.objects.all()
    controleurs = User.objects.filter(is_active=True, first_name="controleur")
    if request.method == 'POST':
        atelier_id = request.POST.get('atelier')
        controleur_id = request.POST.get('controleur')
        if atelier_id and controleur_id:
            fiche = FicheSuivi.objects.create(
                operateur=request.user,
                atelier_id=atelier_id,
                controleur_id=controleur_id
            )
            return redirect('checklist:fiche_detail', fiche.id)
    return render(request, 'checklist/nouvelle_fiche.html', {'ateliers': ateliers, 'controleurs': controleurs})


@login_required
def fiche_detail(request, fiche_id):
    fiche = FicheSuivi.objects.get(id=fiche_id, operateur=request.user)
    taches = fiche.taches.select_related('etape').order_by('etape__ordre')
    incidents = fiche.incidents.order_by('-date')
    retour_experience = fiche.retour_experience
    mesure_composants = None
    melange_mortier = None
    try:
        mesure_composants = fiche.mesure_composants
    except MesureComposants.DoesNotExist:
        pass
    try:
        melange_mortier = fiche.melange_mortier
    except MelangeMortier.DoesNotExist:
        pass
    # Pour la création initiale, générer les tâches si elles n'existent pas
    if taches.count() == 0:
        for etape in Etape.objects.order_by('ordre'):
            Tache.objects.create(fiche=fiche, etape=etape)
        taches = fiche.taches.select_related('etape').order_by('etape__ordre')
    # Gestion séquentielle : verrouillage des étapes non atteintes
    etape_active = None
    for tache in taches:
        if tache.validation != 'conforme':
            etape_active = tache
            break
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Vérifier si c'est une requête AJAX
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Ajout d'un incident
        if action == 'add_incident':
            description = request.POST.get('incident_description')
            if description:
                incident = Incident.objects.create(description=description)
                fiche.incidents.add(incident)
            return redirect('checklist:fiche_detail', fiche.id)
        # Ajout ou modification du retour d'expérience
        if action == 'add_retour':
            commentaire = request.POST.get('retour_commentaire')
            if commentaire:
                if retour_experience:
                    retour_experience.commentaire = commentaire
                    retour_experience.save()
                else:
                    retour_experience = RetourExperience.objects.create(commentaire=commentaire)
                    fiche.retour_experience = retour_experience
                    fiche.save()
            return redirect('checklist:fiche_detail', fiche.id)
        # Validation globale opérateur
        if action == 'valider_fiche_operateur' and fiche.valide_par_operateur is None and request.user == fiche.operateur:
            fiche.valide_par_operateur = request.user
            fiche.date_validation_operateur = timezone.now()
            fiche.save()
            return redirect('checklist:fiche_detail', fiche.id)
        # Validation globale contrôleur
        if action == 'valider_fiche_controleur' and fiche.valide_par_controleur is None and request.user == fiche.controleur:
            fiche.valide_par_controleur = request.user
            fiche.date_validation_controleur = timezone.now()
            fiche.save()
            return redirect('checklist:fiche_detail', fiche.id)
        # Validation opérateur sur une étape
        if action and action.startswith('valider_tache_operateur_'):
            tache_id = action.replace('valider_tache_operateur_', '')
            try:
                tache = Tache.objects.get(id=tache_id, fiche=fiche)
                if tache.valide_par_operateur is None and request.user == fiche.operateur:
                    tache.valide_par_operateur = request.user
                    tache.date_validation_operateur = timezone.now()
                    tache.save()
            except Tache.DoesNotExist:
                pass
            return redirect('checklist:fiche_detail', fiche.id)
        # Validation contrôleur sur une étape
        if action and action.startswith('valider_tache_controleur_'):
            tache_id = action.replace('valider_tache_controleur_', '')
            try:
                tache = Tache.objects.get(id=tache_id, fiche=fiche)
                if tache.valide_par_controleur is None and request.user == fiche.controleur:
                    tache.valide_par_controleur = request.user
                    tache.date_validation_controleur = timezone.now()
                    tache.save()
            except Tache.DoesNotExist:
                pass
            return redirect('checklist:fiche_detail', fiche.id)
        # Gestion des étapes fixes
        if action == 'save_mesure_composants':
            data = {
                'fiche': fiche,
                'ciment': request.POST.get('ciment') or None,
                'sable': request.POST.get('sable') or None,
                'agent_moussant': request.POST.get('agent_moussant') or None,
                'fibre_verre': request.POST.get('fibre_verre') or None,
                'dsp_xl': request.POST.get('dsp_xl') or None,
                'hdr': request.POST.get('hdr') or None,
                'eau': request.POST.get('eau') or None,
                'commentaires': request.POST.get('commentaires_mesure', ''),
            }
            MesureComposants.objects.update_or_create(fiche=fiche, defaults=data)
            return redirect('checklist:fiche_detail', fiche.id)
        
        if action == 'valider_mesure_composants':
            try:
                mesure = fiche.mesure_composants
                
                # Récupérer et sauvegarder les données du formulaire
                if 'ciment' in request.POST and request.POST.get('ciment'):
                    mesure.ciment = float(request.POST.get('ciment'))
                if 'sable' in request.POST and request.POST.get('sable'):
                    mesure.sable = float(request.POST.get('sable'))
                if 'agent_moussant' in request.POST and request.POST.get('agent_moussant'):
                    mesure.agent_moussant = float(request.POST.get('agent_moussant'))
                if 'fibre_verre' in request.POST and request.POST.get('fibre_verre'):
                    mesure.fibre_verre = float(request.POST.get('fibre_verre'))
                if 'dsp_xl' in request.POST and request.POST.get('dsp_xl'):
                    mesure.dsp_xl = float(request.POST.get('dsp_xl'))
                if 'hdr' in request.POST and request.POST.get('hdr'):
                    mesure.hdr = float(request.POST.get('hdr'))
                if 'eau' in request.POST and request.POST.get('eau'):
                    mesure.eau = float(request.POST.get('eau'))
                if 'commentaires_mesure' in request.POST:
                    mesure.commentaires = request.POST.get('commentaires_mesure')
                
                mesure.save()
                
                # Vérifier que tous les champs sont remplis
                if not all([
                    mesure.ciment is not None,
                    mesure.sable is not None,
                    mesure.agent_moussant is not None,
                    mesure.fibre_verre is not None,
                    mesure.dsp_xl is not None,
                    mesure.hdr is not None,
                    mesure.eau is not None,
                    mesure.commentaires
                ]):
                    error_message = "Tous les champs doivent être remplis avant de valider cette étape."
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_message})
                    messages.error(request, error_message)
                    return redirect('checklist:fiche_detail', fiche.id)
                
                # Si tout est ok, valider l'étape
                mesure.valide = True
                mesure.date_validation = timezone.now()
                mesure.valide_par = request.user
                mesure.save()
                
                success_message = "Étape de mesure des composants validée avec succès."
                if is_ajax:
                    return JsonResponse({'success': True, 'message': success_message})
                messages.success(request, success_message)
            except MesureComposants.DoesNotExist:
                error_message = "Vous devez d'abord saisir les données de mesure des composants."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                messages.error(request, error_message)
            except ValueError:
                error_message = "Les valeurs saisies ne sont pas valides. Veuillez vérifier vos données."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                messages.error(request, error_message)
            
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'save_melange_mortier':
            try:
                melange = fiche.melange_mortier
            except MelangeMortier.DoesNotExist:
                melange = MelangeMortier.objects.create(fiche=fiche)
                
            # Enregistrer les données du formulaire
            melange.commentaires = request.POST.get('commentaires_melange', '')
            if request.POST.get('densite'):
                melange.densite = float(request.POST.get('densite'))
                
            # Enregistrer l'état des étapes
            melange.etape_verser_eau = 'etape_verser_eau' in request.POST
            melange.etape_ajouter_fibre = 'etape_ajouter_fibre' in request.POST
            melange.etape_melanger_1min = 'etape_melanger_1min' in request.POST
            melange.etape_verser_ciment = 'etape_verser_ciment' in request.POST
            melange.etape_ajuster_eau = 'etape_ajuster_eau' in request.POST
            melange.etape_mesurer_densite = 'etape_mesurer_densite' in request.POST
                
            melange.save()
            messages.success(request, "Données du mélange du mortier enregistrées avec succès.")
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'valider_melange_mortier':
            try:
                # Vérifier que l'étape précédente est validée
                if not fiche.mesure_composants.valide:
                    error_message = "Vous devez d'abord valider l'étape de mesure des composants."
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_message})
                    messages.error(request, error_message)
                    return redirect('checklist:fiche_detail', fiche.id)
                    
                melange = fiche.melange_mortier
                
                # Récupérer et sauvegarder les données du formulaire
                if 'densite' in request.POST and request.POST.get('densite'):
                    melange.densite = float(request.POST.get('densite'))
                if 'commentaires_melange' in request.POST:
                    melange.commentaires = request.POST.get('commentaires_melange')
                
                # Sauvegarder l'état des cases à cocher
                melange.etape_verser_eau = 'etape_verser_eau' in request.POST
                melange.etape_ajouter_fibre = 'etape_ajouter_fibre' in request.POST
                melange.etape_melanger_1min = 'etape_melanger_1min' in request.POST
                melange.etape_verser_ciment = 'etape_verser_ciment' in request.POST
                melange.etape_ajuster_eau = 'etape_ajuster_eau' in request.POST
                melange.etape_mesurer_densite = 'etape_mesurer_densite' in request.POST
                
                melange.save()
                
                # Vérifier que tous les champs sont remplis
                if not all([
                    melange.densite is not None,
                    melange.commentaires,
                    melange.etape_verser_eau,
                    melange.etape_ajouter_fibre,
                    melange.etape_melanger_1min,
                    melange.etape_verser_ciment,
                    melange.etape_ajuster_eau,
                    melange.etape_mesurer_densite
                ]):
                    error_message = "Tous les champs doivent être remplis et toutes les étapes doivent être cochées avant de valider cette étape."
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': error_message})
                    messages.error(request, error_message)
                    return redirect('checklist:fiche_detail', fiche.id)
                
                # Si tout est ok, valider l'étape
                melange.valide = True
                melange.date_validation = timezone.now()
                melange.valide_par = request.user
                melange.save()
                
                success_message = "Étape de mélange du mortier validée avec succès."
                if is_ajax:
                    return JsonResponse({'success': True, 'message': success_message})
                messages.success(request, success_message)
            except MesureComposants.DoesNotExist:
                error_message = "Vous devez d'abord compléter et valider l'étape de mesure des composants."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                messages.error(request, error_message)
            except MelangeMortier.DoesNotExist:
                error_message = "Vous devez d'abord saisir les données de mélange du mortier."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                messages.error(request, error_message)
            except ValueError:
                error_message = "Les valeurs saisies ne sont pas valides. Veuillez vérifier vos données."
                if is_ajax:
                    return JsonResponse({'success': False, 'error': error_message})
                messages.error(request, error_message)
            
            return redirect('checklist:fiche_detail', fiche.id)
            
        # Gestion séquentielle : verrouillage des étapes non atteintes
        if action == 'valider_etape_fixe':
            etape_id = request.POST.get('etape_id')
            try:
                etape = Etape.objects.get(id=etape_id)
                if not etape.valide:
                    etape.valide = True
                    etape.date_validation = timezone.now()
                    etape.valide_par = request.user
                    etape.save()
            except Etape.DoesNotExist:
                pass
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'save_etape_fixe':
            etape_id = request.POST.get('etape_id')
            try:
                etape = Etape.objects.get(id=etape_id)
                data = {
                    'fiche': fiche,
                    'commentaires': request.POST.get('commentaires_etape', ''),
                }
                etape.objects.update_or_create(fiche=fiche, defaults=data)
            except Etape.DoesNotExist:
                pass
            return redirect('checklist:fiche_detail', fiche.id)
            
        # --- Gestion du temps pour l'étape Mesure des composants ---
        if action == 'start_mesure_composants':
            try:
                mesure = fiche.mesure_composants
                if not mesure.date_debut:
                    mesure.date_debut = timezone.now()
                    mesure.save()
            except MesureComposants.DoesNotExist:
                # Créer l'objet s'il n'existe pas encore
                mesure = MesureComposants.objects.create(fiche=fiche, date_debut=timezone.now())
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'action': 'start_mesure_composants',
                    'status': 'En cours',
                    'has_pause': True,
                    'has_finish': True,
                    'has_start': False,
                    'has_resume': False,
                    'duree': str(mesure.duree) if mesure.duree else None
                })
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'pause_mesure_composants':
            try:
                mesure = fiche.mesure_composants
                if mesure.date_debut and not mesure.date_fin and not mesure.date_pause:
                    mesure.date_pause = timezone.now()
                    mesure.save()
            except MesureComposants.DoesNotExist:
                pass
                
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'action': 'pause_mesure_composants',
                    'status': 'En pause',
                    'has_pause': False,
                    'has_finish': True,
                    'has_start': False,
                    'has_resume': True,
                    'duree': str(mesure.duree) if mesure.duree else None
                })
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'resume_mesure_composants':
            try:
                mesure = fiche.mesure_composants
                if mesure.date_pause:
                    # Calculer le temps passé en pause et ajuster la date de début
                    pause_duration = timezone.now() - mesure.date_pause
                    mesure.date_debut += pause_duration
                    mesure.date_pause = None
                    mesure.save()
            except MesureComposants.DoesNotExist:
                pass
                
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'action': 'resume_mesure_composants',
                    'status': 'En cours',
                    'has_pause': True,
                    'has_finish': True,
                    'has_start': False,
                    'has_resume': False,
                    'duree': str(mesure.duree) if mesure.duree else None
                })
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'finish_mesure_composants':
            try:
                mesure = fiche.mesure_composants
                if mesure.date_debut and not mesure.date_fin:
                    mesure.date_fin = timezone.now()
                    # Calculer la durée totale
                    if mesure.date_pause:
                        # Si en pause, calculer jusqu'au moment de la pause
                        mesure.duree = mesure.date_pause - mesure.date_debut
                    else:
                        mesure.duree = mesure.date_fin - mesure.date_debut
                    mesure.save()
            except MesureComposants.DoesNotExist:
                pass
                
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'action': 'finish_mesure_composants',
                    'status': 'Terminé',
                    'has_pause': False,
                    'has_finish': False,
                    'has_start': False,
                    'has_resume': False,
                    'duree': str(mesure.duree) if mesure.duree else None
                })
            return redirect('checklist:fiche_detail', fiche.id)
            
        # --- Gestion du temps pour l'étape Mélange du mortier ---
        if action == 'start_melange_mortier':
            # Vérifier que l'étape précédente est validée
            try:
                if not fiche.mesure_composants.valide:
                    messages.error(request, "Vous devez d'abord valider l'étape de mesure des composants.")
                    if is_ajax:
                        return JsonResponse({"error": "Vous devez d'abord valider l'étape de mesure des composants."}, status=400)
                    return redirect('checklist:fiche_detail', fiche.id)
            except MesureComposants.DoesNotExist:
                messages.error(request, "Vous devez d'abord compléter et valider l'étape de mesure des composants.")
                if is_ajax:
                    return JsonResponse({"error": "Vous devez d'abord compléter et valider l'étape de mesure des composants."}, status=400)
                return redirect('checklist:fiche_detail', fiche.id)
                
            try:
                melange = fiche.melange_mortier
                if not melange.date_debut:
                    melange.date_debut = timezone.now()
                    melange.save()
            except MelangeMortier.DoesNotExist:
                # Créer l'objet s'il n'existe pas encore
                melange = MelangeMortier.objects.create(fiche=fiche, date_debut=timezone.now())
                
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'action': 'start_melange_mortier',
                    'status': 'En cours',
                    'has_pause': True,
                    'has_finish': True,
                    'has_start': False,
                    'has_resume': False,
                    'duree': str(melange.duree) if melange.duree else None
                })
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'pause_melange_mortier':
            try:
                melange = fiche.melange_mortier
                if melange.date_debut and not melange.date_fin and not melange.date_pause:
                    melange.date_pause = timezone.now()
                    melange.save()
            except MelangeMortier.DoesNotExist:
                pass
                
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'action': 'pause_melange_mortier',
                    'status': 'En pause',
                    'has_pause': False,
                    'has_finish': True,
                    'has_start': False,
                    'has_resume': True,
                    'duree': str(melange.duree) if melange.duree else None
                })
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'resume_melange_mortier':
            try:
                melange = fiche.melange_mortier
                if melange.date_pause:
                    # Calculer le temps passé en pause et ajuster la date de début
                    pause_duration = timezone.now() - melange.date_pause
                    melange.date_debut += pause_duration
                    melange.date_pause = None
                    melange.save()
            except MelangeMortier.DoesNotExist:
                pass
                
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'action': 'resume_melange_mortier',
                    'status': 'En cours',
                    'has_pause': True,
                    'has_finish': True,
                    'has_start': False,
                    'has_resume': False,
                    'duree': str(melange.duree) if melange.duree else None
                })
            return redirect('checklist:fiche_detail', fiche.id)
            
        if action == 'finish_melange_mortier':
            try:
                melange = fiche.melange_mortier
                if melange.date_debut and not melange.date_fin:
                    melange.date_fin = timezone.now()
                    # Calculer la durée totale
                    if melange.date_pause:
                        # Si en pause, calculer jusqu'au moment de la pause
                        melange.duree = melange.date_pause - melange.date_debut
                    else:
                        melange.duree = melange.date_fin - melange.date_debut
                    melange.save()
            except MelangeMortier.DoesNotExist:
                pass
                
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'action': 'finish_melange_mortier',
                    'status': 'Terminé',
                    'has_pause': False,
                    'has_finish': False,
                    'has_start': False,
                    'has_resume': False,
                    'duree': str(melange.duree) if melange.duree else None
                })
            return redirect('checklist:fiche_detail', fiche.id)
            
    return render(request, 'checklist/fiche_detail.html', {
        'fiche': fiche,
        'taches': taches,
        'etape_active': etape_active,
        'incidents': incidents,
        'retour_experience': retour_experience,
        'mesure_composants': mesure_composants,
        'melange_mortier': melange_mortier,
    })


@login_required
def export_pdf(request, fiche_id):
    from xhtml2pdf import pisa  # Utilisation de xhtml2pdf qui fonctionne mieux sur Windows
    from io import BytesIO
    
    fiche = FicheSuivi.objects.get(id=fiche_id)
    taches = fiche.taches.select_related('etape').order_by('etape__ordre')
    incidents = fiche.incidents.order_by('-date')
    retour_experience = fiche.retour_experience
    
    # Générer le HTML
    html_string = render_to_string('checklist/export_pdf.html', {
        'fiche': fiche,
        'taches': taches,
        'incidents': incidents,
        'retour_experience': retour_experience,
    })
    
    # Créer un fichier PDF à partir du HTML
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result)
    
    # Vérifier si la création du PDF a réussi
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="fiche_{fiche.id}.pdf"'
        return response
    
    # En cas d'erreur, renvoyer un message d'erreur
    return HttpResponse("Erreur lors de la génération du PDF", status=500)


@login_required
def export_csv(request, fiche_id):
    fiche = FicheSuivi.objects.get(id=fiche_id)
    taches = fiche.taches.select_related('etape').order_by('etape__ordre')
    incidents = fiche.incidents.order_by('-date')
    retour_experience = fiche.retour_experience
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="fiche_{fiche.id}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Atelier', fiche.atelier.nom])
    writer.writerow(['Opérateur', fiche.operateur.get_full_name()])
    writer.writerow(['Contrôleur', fiche.controleur.get_full_name()])
    writer.writerow(['Date création', fiche.date_creation])
    writer.writerow([])
    writer.writerow(['Étape', 'Consignes', 'Début', 'Fin', 'Durée', 'Validation', 'Observations'])
    for t in taches:
        writer.writerow([
            t.etape.nom, t.etape.consignes, t.date_debut, t.date_fin, t.duree, t.get_validation_display(), t.observations
        ])
    writer.writerow([])
    writer.writerow(['Incidents'])
    for i in incidents:
        writer.writerow([i.date, i.description])
    writer.writerow([])
    writer.writerow(['Retour d\'expérience'])
    if retour_experience:
        writer.writerow([retour_experience.commentaire, retour_experience.date])
    return response


@login_required
def atelier_list(request):
    ateliers = Atelier.objects.all()
    return render(request, "checklist/atelier_list.html", {"ateliers": ateliers})


@login_required
@require_http_methods(["GET", "POST"])
def ajouter_atelier(request):
    if request.method == "POST":
        nom = request.POST.get("nom")
        if nom:
            Atelier.objects.create(nom=nom)
            messages.success(request, "Atelier ajouté avec succès.")
            return redirect("checklist:atelier_list")
        else:
            messages.error(request, "Le nom de l'atelier est obligatoire.")
    return render(request, "checklist/ajouter_atelier.html")


@login_required
@require_http_methods(["GET", "POST"])
def modifier_atelier(request, atelier_id):
    atelier = Atelier.objects.get(pk=atelier_id)
    if request.method == "POST":
        nom = request.POST.get("nom")
        if nom:
            atelier.nom = nom
            atelier.save()
            messages.success(request, "Atelier modifié avec succès.")
            return redirect("checklist:atelier_list")
        else:
            messages.error(request, "Le nom de l'atelier est obligatoire.")
    return render(request, "checklist/modifier_atelier.html", {"atelier": atelier})


@login_required
@require_http_methods(["POST"])
def supprimer_atelier(request, atelier_id):
    atelier = Atelier.objects.get(pk=atelier_id)
    atelier.delete()
    messages.success(request, "Atelier supprimé avec succès.")
    return redirect("checklist:atelier_list")


def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # désactive le compte jusqu'à validation admin
            user.email = form.cleaned_data["email"]
            user.first_name = form.cleaned_data["role"]  # Stocke le rôle AVANT le save
            user.save()
            messages.success(request, "Votre demande de compte a été envoyée. Un administrateur doit valider votre inscription.")
            return redirect("login")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/signup.html", {"form": form})
