import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
	ConservationZone,
	Incident,
	IncidentLocation,
	UserProfile,
	DATA_ENV_DEMO,
	DATA_ENV_PRODUCTION,
	ROLE_FOREST_OFFICER,
	ROLE_RANGER,
)


class RangerAndMapWorkflowTests(TestCase):
	def setUp(self):
		self.ranger = User.objects.create_user('ranger', password='pass-12345')
		UserProfile.objects.create(user=self.ranger, role=ROLE_RANGER)
		self.officer = User.objects.create_user('officer', password='pass-12345')
		UserProfile.objects.create(user=self.officer, role=ROLE_FOREST_OFFICER)
		self.zone = ConservationZone.objects.create(
			name='Nannaj Reference Zone',
			code='NNJ-REF',
			boundary_geojson=json.dumps([[17.8, 75.8], [17.9, 75.8], [17.9, 75.9]]),
		)

	def test_non_ranger_cannot_open_ranger_report(self):
		self.client.force_login(self.officer)

		response = self.client.get(reverse('report_incident'))

		# With strict isolated role sessions, an officer accessing a ranger route
		# doesn't have an active ranger session, so they are treated as anonymous
		# and redirected to the login page.
		self.assertTrue(response.status_code in [302, 403])

	def test_incident_rejects_out_of_range_coordinates(self):
		self.client.force_login(self.ranger)

		response = self.client.post(reverse('report_incident'), {
			'category': 'BIRD_SIGHTING',
			'description': 'A field observation with invalid coordinates.',
			'latitude': '95',
			'longitude': '75.8',
		})

		self.assertEqual(response.status_code, 200)
		self.assertFalse(Incident.objects.exists())

	def test_public_map_contains_only_verified_production_incidents(self):
		pending = Incident.objects.create(
			category='BIRD_SIGHTING',
			description='Pending operational report',
			reporter=self.ranger,
			data_environment=DATA_ENV_PRODUCTION,
		)
		verified = Incident.objects.create(
			category='BIRD_SIGHTING',
			description='Verified public-safe report',
			reporter=self.ranger,
			status='VERIFIED',
			data_environment=DATA_ENV_PRODUCTION,
		)
		demo = Incident.objects.create(
			category='BIRD_SIGHTING',
			description='Development-only report',
			reporter=self.ranger,
			status='VERIFIED',
			data_environment=DATA_ENV_DEMO,
		)
		for incident, latitude in ((pending, 17.81234), (verified, 17.81234), (demo, 17.81234)):
			IncidentLocation.objects.create(
				incident=incident,
				latitude=latitude,
				longitude=75.85678,
				zone=self.zone,
			)

		response = self.client.get(reverse('api_map_data'))
		markers = response.json()['incidents']

		self.assertEqual([marker['incident_id'] for marker in markers], [verified.incident_id])
		self.assertEqual(markers[0]['latitude'], 17.81)
		self.assertEqual(markers[0]['reporter'], 'Authorized field team')

	def test_staff_map_can_review_pending_production_incidents(self):
		incident = Incident.objects.create(
			category='INJURED_BIRD',
			description='Restricted operational detail',
			reporter=self.ranger,
			data_environment=DATA_ENV_PRODUCTION,
		)
		IncidentLocation.objects.create(
			incident=incident,
			latitude=17.81234,
			longitude=75.85678,
			zone=self.zone,
		)
		self.client.force_login(self.officer)

		markers = self.client.get(reverse('api_map_data')).json()['incidents']

		self.assertEqual(len(markers), 1)
		self.assertEqual(markers[0]['latitude'], 17.81234)
		self.assertEqual(markers[0]['description'], 'Restricted operational detail')

	def test_ranger_cannot_download_medical_report(self):
		self.client.force_login(self.ranger)

		response = self.client.get(reverse('download_pdf_report'), {'type': 'MEDICAL_REPORT'})

		self.assertEqual(response.status_code, 403)
