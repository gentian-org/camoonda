# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProcessDefinition(models.Model):
    _name = 'camoonda.process.definition'
    _description = 'Process Definition (BPMN)'
    _order = 'name, version desc'

    name = fields.Char(string='Name', required=True)
    key = fields.Char(string='Process Key', required=True, help="Unique identifier for this process type")
    version = fields.Integer(string='Version', default=1, required=True)
    
    # Deployment relationship
    deployment_id = fields.Many2one(
        'camoonda.deployment',
        string='Deployment',
        ondelete='set null',
        help="The deployment that created this process definition"
    )
    
    resource_name = fields.Char(
        string='Resource Name',
        help="BPMN file name (e.g., order-process.bpmn)"
    )
    
    bpmn_xml = fields.Text(string='BPMN XML', help="BPMN 2.0 XML definition")
    description = fields.Text(string='Description')
    
    # BPMN module integration (optional - only works if BPMN module is installed)
    bpmn_process_id = fields.Many2one(
        'bpmn.process',
        string='BPMN Diagram',
        help="Link to the visual BPMN diagram in the BPMN module",
        ondelete='set null',
        # This field will be inactive if bpmn module is not installed
        # but won't cause errors
    )
    
    active = fields.Boolean(string='Active', default=True)
    is_latest_version = fields.Boolean(
        string='Latest Version',
        compute='_compute_is_latest_version',
        store=True,
        help="Automatically computed based on version number"
    )
    
    category = fields.Selection([
        ('sales', 'Sales Process'),
        ('purchase', 'Purchase Process'),
        ('hr', 'HR Process'),
        ('finance', 'Finance Process'),
        ('custom', 'Custom Process')
    ], string='Category')
    
    # Relations
    instance_ids = fields.One2many('camoonda.process.instance', 'process_definition_id', string='Process Instances')
    instance_count = fields.Integer(string='Instance Count', compute='_compute_instance_count')
    
    element_ids = fields.One2many(
        'process.element',
        'process_definition_id',
        string='Process Elements'
    )
    
    flow_ids = fields.One2many(
        'sequence.flow',
        'process_definition_id',
        string='Sequence Flows'
    )
    
    element_implementation_ids = fields.One2many(
        'camoonda.element.implementation', 
        'process_id', 
        string='Element Implementations'
    )
    
    _sql_constraints = [
        ('unique_key_version', 'unique(key, version)', 'Process key and version must be unique!')
    ]
    
    @api.depends('instance_ids')
    def _compute_instance_count(self):
        for record in self:
            record.instance_count = len(record.instance_ids)
    
    @api.depends('key', 'version')
    def _compute_is_latest_version(self):
        """Compute if this is the latest version of the process"""
        for record in self:
            if not record.key:
                record.is_latest_version = False
                continue
            
            latest = self.search([
                ('key', '=', record.key),
                ('active', '=', True)
            ], order='version desc', limit=1)
            
            record.is_latest_version = (record == latest)
    
    def action_start_instance(self):
        """
        Action to start a new process instance from this definition.
        Opens a wizard to provide initial variables.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Start Process Instance',
            'res_model': 'camoonda.process.instance',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_process_definition_id': self.id,
                'default_state': 'active',
            }
        }
    
    def start_instance(self, variables=None, business_key=None, simulation_mode=False):
        """
        Programmatic method to start a process instance.
        
        Args:
            variables: Dict of initial process variables (optional)
            business_key: Business identifier for this instance (optional)
            simulation_mode: If True, don't execute real operations (optional)
            
        Returns:
            camoonda.process.instance record
        """
        from ..services.execution_engine import ExecutionEngine
        
        engine = ExecutionEngine(self.env)
        return engine.start_process(
            process_definition_id=self.id,
            variables=variables,
            business_key=business_key,
            simulation_mode=simulation_mode
        )
