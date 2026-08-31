{
    "name": "Recorridos Comerciales",
    "summary": "Recorridos, visitas en terreno e integración con CRM",
    "description": """
Recorridos Comerciales
======================

Gestiona jornadas de vendedores, visitas en terreno, datos de obras,
ubicación, adjuntos y su vinculación opcional con clientes y CRM.
""",
    "version": "18.0.1.5.0",
    "category": "Sales/CRM",
    "author": "Personalizado",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail", "crm", "contacts", "zhr_ajustes"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/hr_city_views.xml",
        "views/crm_recorrido_views.xml",
        "views/crm_visita_views.xml",
        "views/crm_lead_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "zcrm_ajustes/static/src/js/save_parent_x2many_field.js",
        ],
    },
    "application": False,
    "installable": True,
}
