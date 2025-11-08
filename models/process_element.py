# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProcessElement(models.Model):
    _name = 'process.element'
    _description = 'Process Element Definition'
    _order = 'sequence, element_id'

    process_definition_id = fields.Many2one(
        'camoonda.process.definition',
        string='Process Definition',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    element_id = fields.Char(
        string='Element ID',
        required=True,
        help="Element ID from BPMN XML (e.g., Task_1, Gateway_2)"
    )
    
    element_name = fields.Char(
        string='Element Name',
        help="Display name of the element"
    )
    
    element_type = fields.Selection([
        ('startEvent', 'Start Event'),
        ('endEvent', 'End Event'),
        ('task', 'Task'),
        ('userTask', 'User Task'),
        ('serviceTask', 'Service Task'),
        ('scriptTask', 'Script Task'),
        ('manualTask', 'Manual Task'),
        ('businessRuleTask', 'Business Rule Task'),
        ('sendTask', 'Send Task'),
        ('receiveTask', 'Receive Task'),
        ('callActivity', 'Call Activity'),
        ('subProcess', 'Sub-Process'),
        ('exclusiveGateway', 'Exclusive Gateway (XOR)'),
        ('parallelGateway', 'Parallel Gateway (AND)'),
        ('inclusiveGateway', 'Inclusive Gateway (OR)'),
        ('eventBasedGateway', 'Event-Based Gateway'),
        ('intermediateCatchEvent', 'Intermediate Catch Event'),
        ('intermediateThrowEvent', 'Intermediate Throw Event'),
        ('boundaryEvent', 'Boundary Event'),
    ], string='Element Type', required=True, index=True)
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Display order"
    )
    
    # Execution configuration
    execution_type = fields.Selection([
        ('none', 'No Action'),
        ('service', 'Call Odoo Method'),
        ('user_task', 'Open Form'),
        ('script', 'Python Code'),
        ('stoodio', 'Stoodio Module'),
        ('auto', 'Auto (Pass Through)'),
    ], string='Execution Type', default='none', required=True)
    
    # Odoo model/method integration
    odoo_model = fields.Char(
        string='Odoo Model',
        help="e.g., sale.order, res.partner"
    )
    
    odoo_method = fields.Char(
        string='Method Name',
        help="e.g., action_confirm, create, write"
    )
    
    # Stoodio integration
    stoodio_module_id = fields.Many2one(
        'stoodio.module',
        string='Stoodio Module',
        help="Link to a Stoodio module for execution",
        ondelete='set null'
    )
    
    # Form/UI integration
    form_view_id = fields.Many2one(
        'ir.ui.view',
        string='Form View',
        domain=[('type', '=', 'form')],
        help="Specific form view to open for user tasks"
    )
    
    form_mode = fields.Selection([
        ('new', 'Create New Record'),
        ('edit', 'Edit Existing Record'),
        ('readonly', 'View Only'),
    ], string='Form Mode', default='new')
    
    # Script execution
    python_code = fields.Text(
        string='Python Code',
        help="Python code to execute. Available variables: env, variables, token, instance"
    )
    
    # Variable mapping
    input_mapping = fields.Text(
        string='Input Mapping',
        help="Map process variables to method parameters (JSON format)"
    )
    
    output_mapping = fields.Text(
        string='Output Mapping',
        help="Map method result to process variables (JSON format)"
    )
    
    # Context
    context_expression = fields.Text(
        string='Context Expression',
        help="Python dict expression for context"
    )
    
    # Gateway conditions
    condition_expression = fields.Text(
        string='Condition Expression',
        help="Python expression for gateway conditions (should return True/False)"
    )
    
    # Advanced options
    async_execution = fields.Boolean(
        string='Async Execution',
        default=False,
        help="Execute in background job queue"
    )
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=3,
        help="Number of retries on failure"
    )
    
    timeout_seconds = fields.Integer(
        string='Timeout (seconds)',
        default=300,
        help="Maximum execution time"
    )
    
    # User task assignment
    assigned_user_ids = fields.Many2many(
        'res.users',
        'process_element_user_rel',
        'element_id',
        'user_id',
        string='Assigned Users',
        help="Users who can complete this task"
    )
    
    assigned_group_ids = fields.Many2many(
        'res.groups',
        'process_element_group_rel',
        'element_id',
        'group_id',
        string='Assigned Groups',
        help="Groups whose members can complete this task"
    )
    
    # Relationships
    incoming_flow_ids = fields.One2many(
        'sequence.flow',
        'target_element_id',
        string='Incoming Flows'
    )
    
    outgoing_flow_ids = fields.One2many(
        'sequence.flow',
        'source_element_id',
        string='Outgoing Flows'
    )
    
    # Status
    active = fields.Boolean(string='Active', default=True)
    is_configured = fields.Boolean(
        string='Is Configured',
        compute='_compute_is_configured',
        store=True,
        help="Whether this element has execution configuration"
    )
    
    notes = fields.Text(string='Notes')
    
    _sql_constraints = [
        ('unique_element_per_definition', 
         'unique(process_definition_id, element_id)',
         'Element ID must be unique within a process definition!')
    ]
    
    @api.depends('execution_type', 'odoo_model', 'odoo_method', 'stoodio_module_id', 
                 'form_view_id', 'python_code', 'condition_expression')
    def _compute_is_configured(self):
        """Determine if element has meaningful execution configuration"""
        for record in self:
            if record.execution_type == 'none':
                record.is_configured = False
            elif record.execution_type == 'service':
                record.is_configured = bool(record.odoo_model and record.odoo_method)
            elif record.execution_type == 'user_task':
                record.is_configured = bool(record.odoo_model or record.form_view_id)
            elif record.execution_type == 'script':
                record.is_configured = bool(record.python_code)
            elif record.execution_type == 'stoodio':
                record.is_configured = bool(record.stoodio_module_id)
            elif record.execution_type == 'auto':
                record.is_configured = True
            else:
                record.is_configured = False
    
    def name_get(self):
        """Display element name with ID"""
        result = []
        for record in self:
            name = f"{record.element_id}"
            if record.element_name:
                name = f"{record.element_name} ({record.element_id})"
            result.append((record.id, name))
        return result
