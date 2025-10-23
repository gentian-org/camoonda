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
    instance_ids = fields.One2many('camoonda.process.instance', 'process_id', string='Process Instances')
    instance_count = fields.Integer(string='Instance Count', compute='_compute_instance_count')
    
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
