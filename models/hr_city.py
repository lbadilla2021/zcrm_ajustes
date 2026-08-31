from odoo import api, fields, models


class HrCity(models.Model):
    _inherit = "hr.city"

    country_id = fields.Many2one(
        "res.country",
        string="País",
        default=lambda self: self.env.ref("base.cl"),
        ondelete="restrict",
        index=True,
    )
    state_id = fields.Many2one(
        "res.country.state",
        string="Región",
        domain="[('country_id', '=', country_id)]",
        ondelete="restrict",
        index=True,
    )

    @api.onchange("country_id")
    def _onchange_country_id(self):
        if self.state_id and self.state_id.country_id != self.country_id:
            self.state_id = False

