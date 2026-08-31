from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


class CrmVisita(models.Model):
    _name = "crm.visita"
    _description = "Visita comercial"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "visit_datetime desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
        index="trigram",
    )
    active = fields.Boolean(default=True)
    recorrido_id = fields.Many2one(
        "crm.recorrido",
        string="Recorrido",
        required=True,
        ondelete="cascade",
        check_company=True,
        tracking=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Vendedor",
        required=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    visit_datetime = fields.Datetime(
        string="Fecha y hora",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
    )
    visit_type = fields.Selection(
        [
            ("client", "Cliente"),
            ("construction", "Obra / Proyecto"),
            ("prospecting", "Prospección"),
            ("verification", "Verificación"),
            ("followup", "Seguimiento"),
            ("other", "Otro"),
        ],
        string="Tipo de visita",
        required=True,
        default="prospecting",
        tracking=True,
        index=True,
    )
    is_client = fields.Boolean(string="Es cliente", tracking=True, index=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente / Contacto",
        check_company=True,
        tracking=True,
        index=True,
    )
    project_name = fields.Char(string="Proyecto / Obra", index="trigram")
    construction_company_name = fields.Char(string="Constructora", index="trigram")
    construction_partner_id = fields.Many2one(
        "res.partner",
        string="Constructora registrada",
        check_company=True,
    )
    project_amount = fields.Monetary(
        string="Monto proyecto",
        currency_field="currency_id",
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    street = fields.Char(string="Dirección")
    city_id = fields.Many2one(
        "hr.city",
        string="Ciudad",
        domain=(
            "[('country_id', '=', country_id), "
            "'|', ('state_id', '=', state_id), ('state_id', '=', False)]"
        ),
        tracking=True,
        index=True,
    )
    city = fields.Char(string="Ciudad anterior", index=True)
    state_id = fields.Many2one(
        "res.country.state",
        string="Región",
        domain="[('country_id', '=', country_id)]",
        index=True,
    )
    country_id = fields.Many2one(
        "res.country",
        string="País",
        default=lambda self: self.env.ref("base.cl"),
    )
    contact_name = fields.Char(string="Nombre contacto")
    contact_phone = fields.Char(string="Teléfono")
    contact_mobile = fields.Char(string="Móvil")
    contact_email = fields.Char(string="Correo electrónico")
    contact_position = fields.Char(string="Cargo")
    information_source = fields.Selection(
        [
            ("field", "Terreno"),
            ("internet", "Internet"),
            ("referral", "Referido"),
            ("client", "Cliente"),
            ("database", "Base de datos"),
            ("other", "Otro"),
        ],
        string="Fuente de información",
        default="field",
    )
    source_reference = fields.Char(string="Referencia de la fuente")
    state = fields.Selection(
        [
            ("new", "Nuevo"),
            ("reviewed", "Revisado"),
            ("qualified", "Calificado"),
            ("discarded", "Descartado"),
            ("converted", "Vinculado a CRM"),
        ],
        string="Estado",
        required=True,
        default="new",
        tracking=True,
        index=True,
    )
    description = fields.Html(string="Observaciones")
    lead_id = fields.Many2one(
        "crm.lead",
        string="Lead / Oportunidad",
        ondelete="restrict",
        check_company=True,
        tracking=True,
        index=True,
    )
    visit_measure = fields.Integer(string="Visitas", default=1, readonly=True)
    client_measure = fields.Integer(
        string="Visitas a clientes",
        compute="_compute_analysis_measures",
        store=True,
    )
    lead_measure = fields.Integer(
        string="Visitas con CRM",
        compute="_compute_analysis_measures",
        store=True,
    )

    _sql_constraints = [
        ("name_company_uniq", "unique(name, company_id)", "El número de la visita debe ser único por compañía."),
        ("project_amount_positive", "CHECK(project_amount >= 0)", "El monto del proyecto no puede ser negativo."),
    ]

    @api.depends("is_client", "lead_id")
    def _compute_analysis_measures(self):
        for visit in self:
            visit.client_measure = int(visit.is_client)
            visit.lead_measure = int(bool(visit.lead_id))

    @api.onchange("recorrido_id")
    def _onchange_recorrido_id(self):
        if self.recorrido_id:
            self.user_id = self.recorrido_id.user_id
            self.company_id = self.recorrido_id.company_id
            self.currency_id = self.recorrido_id.company_id.currency_id
            if not self.country_id:
                self.country_id = self.env.ref("base.cl")

    @api.onchange("country_id")
    def _onchange_country_id(self):
        if self.state_id and self.state_id.country_id != self.country_id:
            self.state_id = False
        if (
            self.city_id
            and self.city_id.country_id
            and self.city_id.country_id != self.country_id
        ):
            self.city_id = False
            self.city = False

    @api.onchange("state_id")
    def _onchange_state_id(self):
        if self.city_id and self.city_id.state_id and self.city_id.state_id != self.state_id:
            self.city_id = False
            self.city = False

    @api.onchange("city_id")
    def _onchange_city_id(self):
        if self.city_id:
            if self.city_id.country_id:
                self.country_id = self.city_id.country_id
            if self.city_id.state_id:
                self.state_id = self.city_id.state_id
            self.city = self.city_id.name
        else:
            self.city = False

    @api.onchange("visit_type")
    def _onchange_visit_type(self):
        if self.visit_type == "client":
            self.is_client = True

    @api.constrains("state", "lead_id")
    def _check_converted_has_lead(self):
        for visit in self:
            if visit.state == "converted" and not visit.lead_id:
                raise ValidationError(_("Una visita vinculada a CRM debe conservar su lead u oportunidad."))

    @api.constrains("city_id", "state_id", "country_id")
    def _check_city_location(self):
        for visit in self:
            if visit.city_id and (
                (visit.city_id.country_id and visit.city_id.country_id != visit.country_id)
                or (visit.city_id.state_id and visit.city_id.state_id != visit.state_id)
            ):
                raise ValidationError(_("La ciudad debe pertenecer al país y a la región seleccionados."))

    @api.model_create_multi
    def create(self, vals_list):
        recorrido_model = self.env["crm.recorrido"]
        partner_model = self.env["res.partner"]
        city_model = self.env["hr.city"]
        chile = self.env.ref("base.cl")
        for vals in vals_list:
            recorrido = recorrido_model.browse(vals.get("recorrido_id")).exists()
            if recorrido:
                vals.setdefault("user_id", recorrido.user_id.id)
                vals.setdefault("company_id", recorrido.company_id.id)
                vals.setdefault("currency_id", recorrido.company_id.currency_id.id)
                vals.setdefault("country_id", chile.id)
                self._check_recorrido_accepts_visits(recorrido)
            else:
                vals.setdefault("country_id", chile.id)
            city = city_model.browse(vals.get("city_id")).exists()
            if city:
                vals["city"] = city.name
                if city.country_id:
                    vals.setdefault("country_id", city.country_id.id)
                if city.state_id:
                    vals.setdefault("state_id", city.state_id.id)
            if vals.get("lead_id"):
                vals["state"] = "converted"
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                sequence_datetime = fields.Datetime.to_datetime(vals.get("visit_datetime")) or fields.Datetime.now()
                sequence_date = fields.Date.to_date(sequence_datetime)
                sequence = (
                    self.env["ir.sequence"]
                    .with_context(ir_sequence_date=sequence_date)
                    .next_by_code("crm.visita")
                    or _("Nuevo")
                )
                reference = vals.get("project_name") or vals.get("construction_company_name")
                if not reference and vals.get("partner_id"):
                    reference = partner_model.browse(vals["partner_id"]).display_name
                vals["name"] = "%s - %s" % (sequence, reference) if reference else sequence
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("recorrido_id"):
            recorrido = self.env["crm.recorrido"].browse(vals["recorrido_id"]).exists()
            self._check_recorrido_accepts_visits(recorrido)
        if "city_id" in vals:
            city = self.env["hr.city"].browse(vals.get("city_id")).exists()
            vals["city"] = city.name if city else False
            if city:
                if city.country_id:
                    vals.setdefault("country_id", city.country_id.id)
                if city.state_id:
                    vals.setdefault("state_id", city.state_id.id)
        if vals.get("lead_id") and "state" not in vals:
            vals["state"] = "converted"
        return super().write(vals)

    def _check_recorrido_accepts_visits(self, recorrido):
        if (
            recorrido
            and recorrido.state in ("done", "cancelled")
            and not self.env.user.has_group("sales_team.group_sale_manager")
        ):
            raise UserError(_("No puede agregar visitas a un recorrido finalizado o cancelado."))

    def action_create_lead(self):
        self.ensure_one()
        if self.lead_id:
            return self.action_open_lead()

        lead_type = "lead" if self.env.user.has_group("crm.group_use_lead") else "opportunity"
        lead_name = (
            self.project_name
            or self.construction_company_name
            or self.partner_id.display_name
            or self.name
        )
        expected_revenue = self.project_amount
        if self.currency_id != self.company_id.currency_id:
            expected_revenue = self.currency_id._convert(
                self.project_amount,
                self.company_id.currency_id,
                self.company_id,
                fields.Date.to_date(self.visit_datetime),
            )
        values = {
            "name": lead_name,
            "type": lead_type,
            "user_id": self.user_id.id,
            "company_id": self.company_id.id,
            "partner_id": self.partner_id.id,
            "partner_name": self.construction_company_name if not self.partner_id else False,
            "expected_revenue": expected_revenue,
            "contact_name": self.contact_name,
            "phone": self.contact_phone,
            "mobile": self.contact_mobile,
            "email_from": self.contact_email,
            "street": self.street,
            "city": self.city_id.name or self.city,
            "state_id": self.state_id.id,
            "country_id": self.country_id.id,
            "description": self.description,
        }
        lead = self.env["crm.lead"].create(values)
        self.write({"lead_id": lead.id, "state": "converted"})
        self.message_post(
            body=Markup("%s <a href='#' data-oe-model='crm.lead' data-oe-id='%s'>%s</a>")
            % (_("Registro CRM creado:"), lead.id, lead.display_name)
        )
        return self.action_open_lead()

    def action_open_lead(self):
        self.ensure_one()
        if not self.lead_id:
            raise UserError(_("La visita todavía no tiene un lead u oportunidad asociado."))
        return {
            "type": "ir.actions.act_window",
            "name": self.lead_id.display_name,
            "res_model": "crm.lead",
            "view_mode": "form",
            "res_id": self.lead_id.id,
        }

    def _find_partner_duplicates(self):
        self.ensure_one()
        candidate_domains = []
        if self.contact_email:
            candidate_domains.append([("email", "=ilike", self.contact_email.strip())])
        for phone in (self.contact_phone, self.contact_mobile):
            if phone:
                candidate_domains.append(
                    expression.OR(
                        [
                            [("phone", "=ilike", phone.strip())],
                            [("mobile", "=ilike", phone.strip())],
                        ]
                    )
                )
        partner_name = self.construction_company_name or self.contact_name
        if partner_name:
            candidate_domains.append([("name", "=ilike", partner_name.strip())])
        if not candidate_domains:
            return self.env["res.partner"]
        domain = expression.AND(
            [
                [("company_id", "in", [False, self.company_id.id])],
                expression.OR(candidate_domains),
            ]
        )
        return self.env["res.partner"].with_context(active_test=False).search(domain, limit=5)

    def action_create_contact(self):
        self.ensure_one()
        if self.partner_id:
            raise UserError(_("La visita ya tiene un cliente o contacto asociado."))
        company_name = (self.construction_company_name or "").strip()
        contact_name = (self.contact_name or "").strip()
        if not company_name and not contact_name:
            raise UserError(_("Ingrese al menos el nombre de la empresa o del contacto."))

        duplicates = self._find_partner_duplicates()
        if duplicates:
            names = "\n• ".join(duplicates.mapped("display_name"))
            raise UserError(
                _(
                    "Se encontraron posibles contactos duplicados. Revise y seleccione uno antes de crear otro:\n• %s",
                    names,
                )
            )

        partner_values = {
            "name": company_name or contact_name,
            "is_company": bool(company_name),
            "company_id": self.company_id.id,
            "phone": self.contact_phone,
            "mobile": self.contact_mobile,
            "email": self.contact_email,
            "street": self.street,
            "city": self.city_id.name or self.city,
            "state_id": self.state_id.id,
            "country_id": self.country_id.id,
        }
        if company_name and contact_name and company_name.casefold() != contact_name.casefold():
            partner_values["child_ids"] = [
                Command.create(
                    {
                        "name": contact_name,
                        "type": "contact",
                        "function": self.contact_position,
                        "phone": self.contact_phone,
                        "mobile": self.contact_mobile,
                        "email": self.contact_email,
                    }
                )
            ]
        partner = self.env["res.partner"].create(partner_values)
        values = {"partner_id": partner.id}
        if company_name:
            values["construction_partner_id"] = partner.id
        self.write(values)
        self.message_post(body=_("Contacto creado: %s", partner.display_name))
        return {
            "type": "ir.actions.act_window",
            "name": partner.display_name,
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": partner.id,
        }
