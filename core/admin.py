from django.contrib import admin
from .models import (
    UserProfile, ConservationZone, TourismRestriction, Bustard,
    BustardMovement, BreedingRecord, BirthRecord, DeathRecord, MissingBirdRecord,
    Incident, IncidentLocation, IncidentImage, PatrolAssignment,
    MedicalCase, MedicalTreatment, MedicalEquipment,
    Notification, ActivityLog, Complaint
)

admin.site.register(UserProfile)
admin.site.register(ConservationZone)
admin.site.register(TourismRestriction)
admin.site.register(Bustard)
admin.site.register(BustardMovement)
admin.site.register(BreedingRecord)
admin.site.register(BirthRecord)
admin.site.register(DeathRecord)
admin.site.register(MissingBirdRecord)
admin.site.register(Incident)
admin.site.register(IncidentLocation)
admin.site.register(IncidentImage)
admin.site.register(PatrolAssignment)
admin.site.register(MedicalCase)
admin.site.register(MedicalTreatment)
admin.site.register(MedicalEquipment)
admin.site.register(Notification)
admin.site.register(ActivityLog)
admin.site.register(Complaint)

admin.site.site_header = "BUSTARD BEACON — Administration"
admin.site.site_title = "Bustard Beacon Admin"
admin.site.index_title = "Conservation System Administration"
