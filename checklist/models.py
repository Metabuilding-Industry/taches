from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Atelier(models.Model):
    nom = models.CharField(max_length=100)
    
    def __str__(self):
        return self.nom

class Incident(models.Model):
    description = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Incident du {self.date.strftime('%d/%m/%Y %H:%M')}"

class RetourExperience(models.Model):
    commentaire = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Retour du {self.date.strftime('%d/%m/%Y %H:%M')}"

class FicheSuivi(models.Model):
    operateur = models.ForeignKey(User, related_name='fiches_operateur', on_delete=models.CASCADE)
    atelier = models.ForeignKey(Atelier, on_delete=models.CASCADE)
    controleur = models.ForeignKey(User, related_name='fiches_controleur', on_delete=models.CASCADE)
    incidents = models.ManyToManyField(Incident, blank=True)
    retour_experience = models.OneToOneField(RetourExperience, null=True, blank=True, on_delete=models.SET_NULL)
    date_creation = models.DateTimeField(auto_now_add=True)
    # Validation globale
    valide_par_operateur = models.ForeignKey(User, null=True, blank=True, related_name='fiches_validees_operateur', on_delete=models.SET_NULL)
    date_validation_operateur = models.DateTimeField(null=True, blank=True)
    valide_par_controleur = models.ForeignKey(User, null=True, blank=True, related_name='fiches_validees_controleur', on_delete=models.SET_NULL)
    date_validation_controleur = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Fiche {self.id} - {self.atelier}"

class Etape(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    consignes = models.TextField(blank=True)
    ordre = models.PositiveIntegerField()
    
    def __str__(self):
        return f"{self.ordre}. {self.nom}"

class Tache(models.Model):
    fiche = models.ForeignKey(FicheSuivi, on_delete=models.CASCADE, related_name='taches')
    etape = models.ForeignKey(Etape, on_delete=models.CASCADE)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_pause = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    validation = models.CharField(max_length=20, choices=[('conforme', 'Conforme'), ('non_conforme', 'Non conforme'), ('en_attente', 'En attente')], default='en_attente')
    observations = models.TextField(blank=True)
    duree = models.DurationField(null=True, blank=True)
    signature_operateur = models.ImageField(upload_to='signatures/', null=True, blank=True)
    signature_controleur = models.ImageField(upload_to='signatures/', null=True, blank=True)
    # Validation opérateur/contrôleur pour l'étape
    valide_par_operateur = models.ForeignKey(User, null=True, blank=True, related_name='taches_validees_operateur', on_delete=models.SET_NULL)
    date_validation_operateur = models.DateTimeField(null=True, blank=True)
    valide_par_controleur = models.ForeignKey(User, null=True, blank=True, related_name='taches_validees_controleur', on_delete=models.SET_NULL)
    date_validation_controleur = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Tâche: {self.etape.nom} (Fiche {self.fiche.id})"

class MesureComposants(models.Model):
    fiche = models.OneToOneField(FicheSuivi, on_delete=models.CASCADE, related_name="mesure_composants")
    ciment = models.FloatField(null=True, blank=True)
    sable = models.FloatField(null=True, blank=True)
    agent_moussant = models.FloatField(null=True, blank=True)
    fibre_verre = models.FloatField(null=True, blank=True)
    dsp_xl = models.FloatField(null=True, blank=True)
    hdr = models.FloatField(null=True, blank=True)
    eau = models.FloatField(null=True, blank=True)
    commentaires = models.TextField(blank=True)
    date_saisie = models.DateTimeField(auto_now=True)
    valide = models.BooleanField(default=False)
    date_validation = models.DateTimeField(null=True, blank=True)
    valide_par = models.ForeignKey(User, null=True, blank=True, related_name='mesures_validees', on_delete=models.SET_NULL)
    # Champs pour le suivi du temps
    date_debut = models.DateTimeField(null=True, blank=True)
    date_pause = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    duree = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"Mesure composants fiche {self.fiche.id}"

class MelangeMortier(models.Model):
    fiche = models.OneToOneField(FicheSuivi, on_delete=models.CASCADE, related_name="melange_mortier")
    commentaires = models.TextField(blank=True)
    densite = models.FloatField(null=True, blank=True)
    date_saisie = models.DateTimeField(auto_now=True)
    valide = models.BooleanField(default=False)
    date_validation = models.DateTimeField(null=True, blank=True)
    valide_par = models.ForeignKey(User, null=True, blank=True, related_name='melanges_valides', on_delete=models.SET_NULL)
    date_debut = models.DateTimeField(null=True, blank=True)
    date_pause = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    duree = models.DurationField(null=True, blank=True)
    
    # Étapes du processus
    etape_verser_eau = models.BooleanField(default=False)
    etape_ajouter_fibre = models.BooleanField(default=False)
    etape_melanger_1min = models.BooleanField(default=False)
    etape_verser_ciment = models.BooleanField(default=False)
    etape_ajuster_eau = models.BooleanField(default=False)
    etape_mesurer_densite = models.BooleanField(default=False)

    def __str__(self):
        return f"Mélange mortier fiche {self.fiche.id}"
