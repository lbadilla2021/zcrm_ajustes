from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRecorridosComerciales(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.user = cls.env.user
        cls.user.name = "Claudio Uribe Carrasco"
        cls.user.tz = "America/Santiago"
        cls.start_datetime = fields.Datetime.to_datetime("2026-08-31 15:00:00")
        cls.chile = cls.env.ref("base.cl")
        cls.biobio = cls.env.ref("base.state_cl_08")
        cls.city_los_angeles = cls.env["hr.city"].create(
            {
                "name": "Los Ángeles",
                "country_id": cls.chile.id,
                "state_id": cls.biobio.id,
            }
        )
        cls.route = cls.env["crm.recorrido"].create(
            {
                "user_id": cls.user.id,
                "company_id": cls.company.id,
                "start_datetime": cls.start_datetime,
            }
        )

    def _create_visit(self, **extra_values):
        values = {
            "recorrido_id": self.route.id,
            "visit_type": "prospecting",
            "project_name": "Condominio Los Robles",
        }
        values.update(extra_values)
        return self.env["crm.visita"].create(values)

    def test_01_route_with_five_visits(self):
        self.assertEqual(
            self.route._get_route_name_base(self.user, self.route.start_datetime),
            "REC-CU-2026-08-31",
        )
        self.assertRegex(self.route.name, r"^REC-CU-2026-08-31(?:-\d{2})?$")
        self.route.action_start()
        visits = self.env["crm.visita"]
        for index in range(5):
            visits |= self._create_visit(project_name="Proyecto %s" % index)
        self.route.end_datetime = self.route.start_datetime + timedelta(hours=1)
        self.route.action_done()

        self.assertEqual(self.route.state, "done")
        self.assertEqual(self.route.visit_count, 5)
        self.assertEqual(len(visits), 5)
        self.assertGreaterEqual(self.route.duration, 0.0)

    def test_02_unknown_project_does_not_require_partner(self):
        visit = self._create_visit(
            visit_type="construction",
            construction_company_name="Constructora ABC",
            project_amount=2_500_000_000,
            city_id=self.city_los_angeles.id,
            is_client=False,
        )
        self.assertFalse(visit.partner_id)
        self.assertEqual(visit.project_amount, 2_500_000_000)
        self.assertEqual(visit.city, "Los Ángeles")
        self.assertEqual(visit.state_id, self.biobio)
        self.assertEqual(visit.country_id, self.chile)

    def test_03_contact_data_can_be_added_later(self):
        visit = self._create_visit()
        visit.write(
            {
                "contact_name": "Ana Silva",
                "contact_phone": "+56 43 200 0000",
                "contact_email": "ana@example.com",
            }
        )
        self.assertEqual(visit.contact_name, "Ana Silva")
        self.assertEqual(visit.contact_email, "ana@example.com")

    def test_04_create_crm_and_reuse_it_on_second_visit(self):
        first_visit = self._create_visit(
            construction_company_name="Constructora ABC",
            project_amount=2_500_000_000,
            contact_name="Ana Silva",
            contact_email="ana@example.com",
        )
        first_visit.action_create_lead()
        second_visit = self._create_visit(
            project_name="Condominio Los Robles - seguimiento",
            lead_id=first_visit.lead_id.id,
        )

        self.assertTrue(first_visit.lead_id)
        self.assertEqual(first_visit.state, "converted")
        self.assertEqual(second_visit.lead_id, first_visit.lead_id)
        self.assertEqual(first_visit.lead_id.visit_count, 2)

    def test_05_discard_without_crm(self):
        visit = self._create_visit(state="discarded")
        self.assertFalse(visit.lead_id)
        self.assertEqual(visit.state, "discarded")

    def test_06_business_constraints(self):
        with self.assertRaises(ValidationError):
            self.route.write(
                {
                    "start_datetime": fields.Datetime.now(),
                    "end_datetime": fields.Datetime.now() - timedelta(hours=1),
                }
            )
        with self.assertRaises(ValidationError):
            self._create_visit(state="converted")

    def test_07_actions_preserve_manual_datetimes(self):
        start_datetime = fields.Datetime.to_datetime("2026-08-11 17:00:00")
        end_datetime = fields.Datetime.to_datetime("2026-08-11 18:00:00")
        self.route.write(
            {
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            }
        )

        self.route.action_start()
        self.assertEqual(self.route.start_datetime, start_datetime)
        self.route.action_done()

        self.assertEqual(self.route.end_datetime, end_datetime)
        self.assertEqual(self.route.duration, 1.0)

    def test_08_route_name_suffix_and_refresh(self):
        expected_name = self.env["crm.recorrido"]._get_available_route_name(
            self.user,
            self.start_datetime,
            self.company.id,
        )
        second_route = self.env["crm.recorrido"].create(
            {
                "user_id": self.user.id,
                "company_id": self.company.id,
                "start_datetime": self.start_datetime,
            }
        )
        self.assertEqual(second_route.name, expected_name)

        expected_refreshed_name = self.env["crm.recorrido"]._get_available_route_name(
            self.user,
            fields.Datetime.to_datetime("2026-09-01 15:00:00"),
            self.company.id,
            exclude_ids=second_route.ids,
        )
        second_route.start_datetime = fields.Datetime.to_datetime("2026-09-01 15:00:00")
        self.assertEqual(second_route.name, expected_refreshed_name)

    def test_09_end_datetime_is_required_to_finish(self):
        self.route.action_start()
        with self.assertRaises(UserError):
            self.route.action_done()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.route.state = "done"
        self.route.invalidate_recordset(["state"])

        self.route.end_datetime = self.route.start_datetime + timedelta(hours=1)
        self.route.action_done()
        self.assertEqual(self.route.state, "done")
