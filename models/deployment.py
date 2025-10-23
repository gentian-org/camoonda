# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Deployment(models.Model):
    _name = 'camoonda.deployment'
    _description = 'Process Deployment'
    _order = 'deployment_time desc'
    _rec_name = 'name'

    name = fields.Char(string='Deployment Name', required=True)
    deployment_time = fields.Datetime(
        string='Deployment Time',
        default=fields.Datetime.now,
        required=True,
        readonly=True
    )
    
    source = fields.Selection([
        ('modeler', 'Modeler'),
        ('api', 'API'),
        ('upload', 'File Upload'),
        ('system', 'System'),
        ('manual', 'Manual')
    ], string='Source', default='manual', required=True)
    
    deployed_by = fields.Many2one(
        'res.users',
        string='Deployed By',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    # Relations
    process_definition_ids = fields.One2many(
        'camoonda.process.definition',
        'deployment_id',
        string='Process Definitions'
    )
    
    process_definition_count = fields.Integer(
        string='Process Count',
        compute='_compute_process_definition_count'
    )
    
    resource_ids = fields.One2many(
        'camoonda.deployment.resource',
        'deployment_id',
        string='Resources'
    )
    
    resource_count = fields.Integer(
        string='Resource Count',
        compute='_compute_resource_count'
    )
    
    notes = fields.Text(string='Deployment Notes')
    
    @api.depends('process_definition_ids')
    def _compute_process_definition_count(self):
        for record in self:
            record.process_definition_count = len(record.process_definition_ids)
    
    @api.depends('resource_ids')
    def _compute_resource_count(self):
        for record in self:
            record.resource_count = len(record.resource_ids)
    
    def action_view_process_definitions(self):
        """Action to view process definitions in this deployment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Process Definitions',
            'res_model': 'camoonda.process.definition',
            'domain': [('deployment_id', '=', self.id)],
            'view_mode': 'tree,form',
            'context': {'default_deployment_id': self.id}
        }


class DeploymentResource(models.Model):
    _name = 'camoonda.deployment.resource'
    _description = 'Deployment Resource'
    _order = 'resource_name'

    deployment_id = fields.Many2one(
        'camoonda.deployment',
        string='Deployment',
        required=True,
        ondelete='cascade'
    )
    
    resource_name = fields.Char(
        string='Resource Name',
        required=True,
        help="Name of the resource file (e.g., process.bpmn, form.json)"
    )
    
    resource_type = fields.Selection([
        ('bpmn', 'BPMN Process'),
        ('dmn', 'DMN Decision'),
        ('form', 'Form'),
        ('script', 'Script'),
        ('other', 'Other')
    ], string='Resource Type', required=True, default='bpmn')
    
    content = fields.Binary(string='Content', attachment=True)
    content_text = fields.Text(string='Text Content', help="For text-based resources")
    
    mime_type = fields.Char(string='MIME Type', default='application/xml')
    
    size = fields.Integer(string='Size (bytes)', compute='_compute_size', store=True)
    
    @api.depends('content', 'content_text')
    def _compute_size(self):
        for record in self:
            if record.content:
                record.size = len(record.content) if record.content else 0
            elif record.content_text:
                record.size = len(record.content_text.encode('utf-8'))
            else:
                record.size = 0
