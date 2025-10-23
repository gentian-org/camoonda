# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProcessInstance(models.Model):
    _name = 'camoonda.process.instance'
    _description = 'Process Instance (Execution)'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    name = fields.Char(string='Instance Name', required=True)
    business_key = fields.Char(
        string='Business Key',
        index=True,
        help="User-defined identifier for this process instance. Used for correlating process instances with business entities."
    )
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    process_id = fields.Many2one('camoonda.process.definition', string='Process Definition', required=True, ondelete='restrict')
    process_key = fields.Char(related='process_id.key', string='Process Key', store=True)
    
    state = fields.Selection([
        ('ready', 'Ready'),
        ('running', 'Running'),
        ('suspended', 'Suspended'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string='State', default='ready', required=True, tracking=True)
    
    # Process variables (stored as JSON)
    variables = fields.Json(string='Process Variables', default={})
    
    # Link to business object
    res_model = fields.Char(string='Related Model')
    res_id = fields.Integer(string='Related Record ID')
    res_name = fields.Char(string='Related Record Name', compute='_compute_res_name')
    
    # Execution tracking
    started_by = fields.Many2one('res.users', string='Started By', default=lambda self: self.env.user)
    started_date = fields.Datetime(string='Started Date')
    completed_date = fields.Datetime(string='Completed Date')
    
    # Relations
    token_ids = fields.One2many('camoonda.process.token', 'instance_id', string='Tokens')
    active_token_ids = fields.One2many(
        'camoonda.process.token', 
        'instance_id', 
        string='Active Tokens',
        domain=[('state', '=', 'active')]
    )
    execution_history_ids = fields.One2many('camoonda.execution.history', 'instance_id', string='Execution History')
    
    # Incident tracking
    incident_ids = fields.One2many('camoonda.process.incident', 'instance_id', string='Incidents')
    incident_count = fields.Integer(string='Incident Count', compute='_compute_incident_count', store=True)
    has_incidents = fields.Boolean(string='Has Incidents', compute='_compute_incident_count', store=True)
    
    @api.depends('name', 'process_id.name', 'create_date')
    def _compute_display_name(self):
        for record in self:
            if record.process_id and record.name:
                record.display_name = f"{record.process_id.name} - {record.name}"
            else:
                record.display_name = record.name or 'New Process Instance'
    
    def _compute_res_name(self):
        for record in self:
            if record.res_model and record.res_id:
                try:
                    related_record = self.env[record.res_model].browse(record.res_id)
                    record.res_name = related_record.display_name if related_record.exists() else ''
                except Exception:
                    record.res_name = ''
            else:
                record.res_name = ''
    
    @api.depends('incident_ids', 'incident_ids.state')
    def _compute_incident_count(self):
        for record in self:
            active_incidents = record.incident_ids.filtered(lambda i: i.state == 'created')
            record.incident_count = len(active_incidents)
            record.has_incidents = record.incident_count > 0
    
    def action_start(self):
        """Start the process instance"""
        self.ensure_one()
        self.write({
            'state': 'running',
            'started_date': fields.Datetime.now()
        })
        # TODO: Create initial token and begin execution
        
    def action_suspend(self):
        """Suspend the process instance"""
        self.write({'state': 'suspended'})
        
    def action_resume(self):
        """Resume a suspended process instance"""
        self.write({'state': 'running'})
        
    def action_cancel(self):
        """Cancel the process instance"""
        self.write({'state': 'cancelled'})
    
    def action_view_incidents(self):
        """View incidents for this process instance"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Process Incidents',
            'res_model': 'camoonda.process.incident',
            'domain': [('instance_id', '=', self.id)],
            'view_mode': 'tree,form',
            'context': {'default_instance_id': self.id}
        }
    
    @api.model
    def find_by_business_key(self, business_key, process_key=None):
        """
        Find process instances by business key
        
        :param business_key: Business key to search for
        :param process_key: Optional process key to filter by
        :return: Recordset of matching process instances
        """
        domain = [('business_key', '=', business_key)]
        if process_key:
            domain.append(('process_key', '=', process_key))
        return self.search(domain)
