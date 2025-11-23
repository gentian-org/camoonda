# -*- coding: utf-8 -*-
{
    'name': 'Camoonda',
    'version': '1.0.0',
    'category': 'Technical',
    'summary': 'Camunda-style BPMN Process Execution Engine for Odoo',
    'description': """
Camoonda - Process Execution Engine
====================================

A Camunda-inspired BPMN process execution engine for Odoo.

Features:
---------
* Process Definitions (BPMN 2.0)
* Process Instances (Runtime Execution)
* Token-based Execution
* Process Variables
* Execution History
* Integration with Odoo Models
    """,
    'author': 'Your Name',
    'website': 'https://github.com/gentian-org/camoonda',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/process_topology_views.xml',
        'views/deployment_views.xml',
        'views/process_instance_views.xml',
        'views/process_incident_views.xml',
        'wizard/start_instance_wizard_views.xml',
        'views/process_definition_views.xml',
        'views/camoonda_menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
