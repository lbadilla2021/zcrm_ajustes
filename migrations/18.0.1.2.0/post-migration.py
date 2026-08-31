from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    routes = env["crm.recorrido"].with_context(active_test=False).search([], order="company_id, date, user_id, id")
    excluded_ids = routes.ids
    reserved_names = {}
    for route in routes:
        company_reserved_names = reserved_names.setdefault(route.company_id.id, set())
        new_name = route._get_available_route_name(
            route.user_id,
            route.date,
            route.company_id.id,
            exclude_ids=excluded_ids,
            reserved_names=company_reserved_names,
        )
        route.write({"name": new_name})
        company_reserved_names.add(new_name)

    obsolete_sequence = env.ref("zcrm_ajustes.seq_crm_recorrido", raise_if_not_found=False)
    if obsolete_sequence:
        obsolete_sequence.unlink()
