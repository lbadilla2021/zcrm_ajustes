from odoo import _, api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    visit_ids = fields.One2many(
        "crm.visita",
        "lead_id",
        string="Visitas en terreno",
    )
    visit_count = fields.Integer(
        string="N.º visitas",
        compute="_compute_visit_count",
    )

    @api.depends("visit_ids")
    def _compute_visit_count(self):
        for lead in self:
            lead.visit_count = len(lead.visit_ids)

    def action_view_field_visits(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("zcrm_ajustes.action_crm_visita_all")
        action["domain"] = [("lead_id", "=", self.id)]
        action["context"] = {
            "default_lead_id": self.id,
            "default_user_id": self.user_id.id,
            "default_company_id": self.company_id.id,
        }
        if self.visit_count == 1:
            action.update({"view_mode": "form", "res_id": self.visit_ids.id})
        return action
