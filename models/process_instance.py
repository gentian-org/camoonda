# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class ProcessInstance(models.Model):
    _name = 'camoonda.process.instance'
    _description = 'Process Instance (Execution)'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    name = fields.Char(string='Instance Name', compute='_compute_name', store=True)
    business_key = fields.Char(
        string='Business Key',
        index=True,
        help="User-defined identifier for this process instance. Used for correlating process instances with business entities."
    )
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    process_definition_id = fields.Many2one(
        'camoonda.process.definition',
        string='Process Definition',
        required=True,
        ondelete='restrict'
    )
    
    # Backward compatibility alias
    process_id = fields.Many2one(
        'camoonda.process.definition',
        related='process_definition_id',
        string='Process Definition (Alias)',
        store=False
    )
    
    process_key = fields.Char(related='process_definition_id.key', string='Process Key', store=True)
    
    state = fields.Selection([
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string='State', default='active', required=True, tracking=True)
    
    # Simulation mode - skip real execution
    simulation_mode = fields.Boolean(
        string='Simulation Mode',
        default=False,
        help="If true, process runs in simulation mode without executing real operations"
    )
    
    # Process variables (stored as JSON)
    variables = fields.Json(string='Process Variables', default={})
    
    # Link to business object
    res_model = fields.Char(string='Related Model')
    res_id = fields.Integer(string='Related Record ID')
    res_name = fields.Char(string='Related Record Name', compute='_compute_res_name')
    
    # Execution tracking
    started_by = fields.Many2one('res.users', string='Started By', default=lambda self: self.env.user)
    started_date = fields.Datetime(string='Started Date', default=fields.Datetime.now)
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
    
    @api.depends('process_definition_id', 'business_key')
    def _compute_name(self):
        """Auto-generate name if not set"""
        for record in self:
            if record.process_definition_id:
                if record.business_key:
                    record.name = f"{record.process_definition_id.name} - {record.business_key}"
                elif record.id:
                    record.name = f"{record.process_definition_id.name} #{record.id}"
                else:
                    record.name = f"{record.process_definition_id.name} #New"
            elif record.id:
                record.name = f"Process Instance #{record.id}"
            else:
                record.name = "New Process Instance"
    
    @api.depends('name', 'process_definition_id.name', 'create_date')
    def _compute_display_name(self):
        for record in self:
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
        
        # Use execution engine to start
        from ..services.execution_engine import ExecutionEngine
        engine = ExecutionEngine(self.env)
        
        # Find start event and create initial token
        start_element = self.env['process.element'].search([
            ('process_definition_id', '=', self.process_definition_id.id),
            ('element_type', '=', 'startEvent')
        ], limit=1)
        
        if not start_element:
            raise UserError("No start event found in process definition")
        
        # Create token and execute
        token = self.env['camoonda.process.token'].create({
            'instance_id': self.id,
            'current_element_id': start_element.id,
            'state': 'active',
            'variables': self.variables or {},
        })
        
        self.write({'started_date': fields.Datetime.now()})
        
        # Execute from start
        return engine.execute_token(token.id)
        
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
