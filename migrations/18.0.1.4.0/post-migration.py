import unicodedata

from odoo import SUPERUSER_ID, api


def _normalized_name(value):
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", (value or "").strip().casefold())
        if not unicodedata.combining(character)
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    chile = env.ref("base.cl")
    known_states = {
        "los angeles": env.ref("base.state_cl_08"),
    }

    city_model = env["hr.city"].with_context(active_test=False)
    cities_by_name = {}
    for city in city_model.search([]):
        normalized_name = _normalized_name(city.name)
        values = {}
        if not city.country_id:
            values["country_id"] = chile.id
        known_state = known_states.get(normalized_name)
        if known_state and not city.state_id:
            values["state_id"] = known_state.id
        if values:
            city.write(values)
        cities_by_name.setdefault(normalized_name, city)

    visits = env["crm.visita"].with_context(active_test=False).search([("city", "!=", False)])
    for visit in visits:
        normalized_name = _normalized_name(visit.city)
        city = cities_by_name.get(normalized_name)
        if not city:
            city = city_model.create(
                {
                    "name": visit.city.strip(),
                    "country_id": chile.id,
                    "state_id": visit.state_id.id
                    or known_states.get(normalized_name, env["res.country.state"]).id,
                }
            )
            cities_by_name[normalized_name] = city
        elif not city.state_id and visit.state_id:
            city.state_id = visit.state_id

        values = {"city_id": city.id, "country_id": chile.id}
        if city.state_id:
            values["state_id"] = city.state_id.id
        visit.with_context(tracking_disable=True).write(values)
