# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ElementImplementation(models.Model):
    _name = 'camoonda.element.implementation'
    _description = 'BPMN Element Implementation Mapping'
    _order = 'element_id'

    process_id = fields.Many2one('camoonda.process.definition', string='Process Definition', required=True, ondelete='cascade')
    element_id = fields.Char(string='BPMN Element ID', required=True, help="Element ID from BPMN XML")
    element_name = fields.Char(string='Element Name', help="Display name of the element")
    
    element_type = fields.Selection([
        ('task', 'Task'),
        ('service_task', 'Service Task'),
        ('user_task', 'User Task'),
        ('script_task', 'Script Task'),
        ('gateway', 'Gateway'),
        ('exclusive_gateway', 'Exclusive Gateway'),
        ('parallel_gateway', 'Parallel Gateway'),
        ('event', 'Event'),
        ('start_event', 'Start Event'),
        ('end_event', 'End Event'),
        ('timer_event', 'Timer Event')
    ], string='Element Type', required=True)
    
    # Implementation details
    implementation_type = fields.Selection([
        ('python', 'Python Code'),
        ('method', 'Odoo Method'),
        ('none', 'No Implementation')
    ], string='Implementation Type', default='none', required=True)
    
    python_code = fields.Text(string='Python Code', help="Python code to execute")
    odoo_module = fields.Char(string='Odoo Module')
    odoo_model = fields.Char(string='Odoo Model', help="e.g., sale.order")
    odoo_method = fields.Char(string='Odoo Method', help="e.g., action_confirm")
    
    # For user tasks
    assigned_user_ids = fields.Many2many('res.users', string='Assigned Users')
    assigned_group_ids = fields.Many2many('res.groups', string='Assigned Groups')
    
    # For gateways
    condition_expression = fields.Text(string='Condition Expression', help="Python expression for gateway conditions")
    
    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('unique_element_per_process', 'unique(process_id, element_id)', 
         'Element ID must be unique within a process!')
    ]
