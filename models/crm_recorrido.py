import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CrmRecorrido(models.Model):
    _name = "crm.recorrido"
    _description = "Recorrido comercial"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"
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
    start_datetime = fields.Datetime(
        string="Inicio recorrido",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
    )
    end_datetime = fields.Datetime(string="Término recorrido", tracking=True)
    duration = fields.Float(
        string="Duración (horas)",
        compute="_compute_duration",
        digits=(16, 2),
    )
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("in_progress", "En recorrido"),
            ("done", "Finalizado"),
            ("cancelled", "Cancelado"),
        ],
        string="Estado",
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )
    visit_ids = fields.One2many(
        "crm.visita",
        "recorrido_id",
        string="Visitas",
    )
    visit_count = fields.Integer(
        string="N.º visitas",
        compute="_compute_visit_counts",
        store=True,
    )
    client_visit_count = fields.Integer(
        string="Clientes",
        compute="_compute_visit_counts",
        store=True,
    )
    prospect_visit_count = fields.Integer(
        string="Prospectos",
        compute="_compute_visit_counts",
        store=True,
    )
    lead_count = fields.Integer(
        string="Leads/Oportunidades",
        compute="_compute_visit_counts",
        store=True,
    )
    notes = fields.Html(string="Observaciones")

    _sql_constraints = [
        ("name_company_uniq", "unique(name, company_id)", "El número del recorrido debe ser único por compañía."),
    ]

    @api.depends("start_datetime", "end_datetime")
    def _compute_duration(self):
        for recorrido in self:
            if recorrido.start_datetime and recorrido.end_datetime:
                elapsed = recorrido.end_datetime - recorrido.start_datetime
                recorrido.duration = elapsed.total_seconds() / 3600.0
            else:
                recorrido.duration = 0.0

    @api.depends("visit_ids", "visit_ids.is_client", "visit_ids.lead_id")
    def _compute_visit_counts(self):
        for recorrido in self:
            visits = recorrido.visit_ids
            recorrido.visit_count = len(visits)
            recorrido.client_visit_count = len(visits.filtered("is_client"))
            recorrido.prospect_visit_count = len(visits.filtered(lambda visit: not visit.is_client))
            recorrido.lead_count = len(visits.mapped("lead_id"))

    @api.constrains("state", "start_datetime", "end_datetime")
    def _check_datetimes(self):
        for recorrido in self:
            if recorrido.state == "done" and not recorrido.end_datetime:
                raise ValidationError(_("Debe ingresar el término del recorrido antes de finalizarlo."))
            if (
                recorrido.start_datetime
                and recorrido.end_datetime
                and recorrido.end_datetime < recorrido.start_datetime
            ):
                raise ValidationError(_("El término del recorrido no puede ser anterior a su inicio."))

    @api.model_create_multi
    def create(self, vals_list):
        reserved_names = {}
        for vals in vals_list:
            vals.setdefault("start_datetime", fields.Datetime.now())
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                user = self.env["res.users"].browse(vals.get("user_id") or self.env.user.id)
                company_id = vals.get("company_id") or self.env.company.id
                company_reserved_names = reserved_names.setdefault(company_id, set())
                vals["name"] = self._get_available_route_name(
                    user,
                    vals["start_datetime"],
                    company_id,
                    reserved_names=company_reserved_names,
                )
                company_reserved_names.add(vals["name"])
        return super().create(vals_list)

    @api.model
    def _get_seller_initials(self, user):
        normalized_name = unicodedata.normalize("NFKD", user.name or "")
        ascii_name = "".join(char for char in normalized_name if not unicodedata.combining(char))
        name_parts = re.findall(r"[A-Za-z0-9]+", ascii_name)
        if not name_parts:
            return "XX"
        first_initial = name_parts[0][0].upper()
        if len(name_parts) == 1:
            return first_initial
        paternal_lastname = name_parts[-2] if len(name_parts) >= 3 else name_parts[-1]
        return first_initial + paternal_lastname[0].upper()

    @api.model
    def _get_route_name_base(self, user, start_datetime):
        start_datetime = fields.Datetime.to_datetime(start_datetime) or fields.Datetime.now()
        user_with_timezone = user.with_context(tz=user.tz or "America/Santiago")
        route_date = fields.Datetime.context_timestamp(user_with_timezone, start_datetime).date()
        return "REC-%s-%s" % (self._get_seller_initials(user), route_date.strftime("%Y-%m-%d"))

    @api.model
    def _get_available_route_name(
        self,
        user,
        start_datetime,
        company_id,
        exclude_ids=None,
        reserved_names=None,
    ):
        base_name = self._get_route_name_base(user, start_datetime)
        domain = [
            ("company_id", "=", company_id),
            ("name", "=like", "%s%%" % base_name),
        ]
        if exclude_ids:
            domain.append(("id", "not in", exclude_ids))
        used_names = set(self.search(domain).mapped("name"))
        used_names.update(reserved_names or set())
        if base_name not in used_names:
            return base_name
        suffix = 2
        while "%s-%02d" % (base_name, suffix) in used_names:
            suffix += 1
        return "%s-%02d" % (base_name, suffix)

    def write(self, vals):
        should_refresh_name = bool({"user_id", "start_datetime", "company_id"}.intersection(vals))
        result = super().write(vals)
        if should_refresh_name:
            reserved_names = {}
            excluded_ids = self.ids
            for recorrido in self.sorted("id"):
                company_reserved_names = reserved_names.setdefault(recorrido.company_id.id, set())
                new_name = self._get_available_route_name(
                    recorrido.user_id,
                    recorrido.start_datetime,
                    recorrido.company_id.id,
                    exclude_ids=excluded_ids,
                    reserved_names=company_reserved_names,
                )
                super(CrmRecorrido, recorrido).write({"name": new_name})
                company_reserved_names.add(new_name)
        return result

    def action_start(self):
        for recorrido in self:
            if recorrido.state != "draft":
                raise UserError(_("Solo se puede iniciar un recorrido en borrador."))
            values = {"state": "in_progress"}
            if not recorrido.start_datetime:
                values["start_datetime"] = fields.Datetime.now()
            recorrido.write(values)
        return True

    def action_done(self):
        for recorrido in self:
            if recorrido.state != "in_progress":
                raise UserError(_("Solo se puede finalizar un recorrido que está en curso."))
            if not recorrido.end_datetime:
                raise UserError(_("Ingrese el término del recorrido antes de finalizarlo."))
            recorrido.write({"state": "done"})
        return True

    def action_cancel(self):
        for recorrido in self:
            if recorrido.state not in ("draft", "in_progress"):
                raise UserError(_("Solo se puede cancelar un recorrido en borrador o en curso."))
            values = {"state": "cancelled"}
            if recorrido.start_datetime and not recorrido.end_datetime:
                values["end_datetime"] = fields.Datetime.now()
            recorrido.write(values)
        return True

    def action_set_draft(self):
        if not self.env.user.has_group("sales_team.group_sale_manager"):
            raise UserError(_("Solo un jefe comercial puede reabrir un recorrido."))
        self.write({"state": "draft", "end_datetime": False})
        return True

    def action_view_visits(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("zcrm_ajustes.action_crm_visita_all")
        action["domain"] = [("recorrido_id", "=", self.id)]
        action["context"] = {
            "default_recorrido_id": self.id,
            "default_user_id": self.user_id.id,
            "default_company_id": self.company_id.id,
        }
        return action

    def action_view_leads(self):
        self.ensure_one()
        lead_ids = self.visit_ids.mapped("lead_id").ids
        action = {
            "type": "ir.actions.act_window",
            "name": _("Leads/Oportunidades"),
            "res_model": "crm.lead",
            "view_mode": "list,kanban,form",
            "domain": [("id", "in", lead_ids)],
            "context": {"create": False},
        }
        if len(lead_ids) == 1:
            action.update({"view_mode": "form", "res_id": lead_ids[0]})
        return action
