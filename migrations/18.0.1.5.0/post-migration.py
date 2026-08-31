from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    routes = (
        env["crm.recorrido"]
        .with_context(active_test=False)
        .search([], order="company_id, start_datetime, user_id, id")
    )

    for route in routes:
        route.with_context(tracking_disable=True).write(
            {"name": "REC-MIGRACION-%s" % route.id}
        )

    reserved_names = {}
    for route in routes:
        company_reserved_names = reserved_names.setdefault(route.company_id.id, set())
        new_name = route._get_available_route_name(
            route.user_id,
            route.start_datetime,
            route.company_id.id,
            exclude_ids=routes.ids,
            reserved_names=company_reserved_names,
        )
        route.with_context(tracking_disable=True).write({"name": new_name})
        company_reserved_names.add(new_name)

    cr.execute("ALTER TABLE crm_recorrido DROP COLUMN IF EXISTS date")
