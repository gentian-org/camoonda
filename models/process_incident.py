# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProcessIncident(models.Model):
    _name = 'camoonda.process.incident'
    _description = 'Process Incident'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    instance_id = fields.Many2one(
        'camoonda.process.instance',
        string='Process Instance',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    process_id = fields.Many2one(
        related='instance_id.process_id',
        string='Process Definition',
        store=True,
        readonly=True
    )
    
    incident_type = fields.Selection([
        ('job_no_retries', 'Job - No Retries Left'),
        ('unhandled_error', 'Unhandled Error'),
        ('extract_value_error', 'Extract Value Error'),
        ('io_mapping_error', 'I/O Mapping Error'),
        ('condition_error', 'Condition Evaluation Error'),
        ('called_element_error', 'Called Element Error'),
        ('called_decision_error', 'Called Decision Error'),
        ('job_timeout', 'Job Timeout'),
        ('unknown', 'Unknown Error')
    ], string='Incident Type', required=True, default='unhandled_error')
    
    element_id = fields.Char(
        string='Element ID',
        help="BPMN element ID where the incident occurred"
    )
    
    element_name = fields.Char(string='Element Name')
    element_type = fields.Char(string='Element Type')
    
    message = fields.Text(string='Message', required=True)
    error_message = fields.Text(related='message', string='Error Message', readonly=False)
    error_type = fields.Char(string='Error Type', help="Python exception class or error code")
    stack_trace = fields.Text(string='Stack Trace')
    
    state = fields.Selection([
        ('created', 'Created'),
        ('resolved', 'Resolved')
    ], string='State', default='created', required=True, tracking=True)
    
    created_date = fields.Datetime(
        string='Created Date',
        default=fields.Datetime.now,
        required=True,
        readonly=True
    )
    
    resolved_date = fields.Datetime(string='Resolved Date', readonly=True)
    resolved_by = fields.Many2one('res.users', string='Resolved By', readonly=True)
    resolution_notes = fields.Text(string='Resolution Notes')
    
    # Job-related fields
    job_key = fields.Char(string='Job Key', help="Related job identifier")
    job_retries = fields.Integer(string='Job Retries Left', default=0)
    
    # Token reference
    token_id = fields.Many2one(
        'camoonda.process.token',
        string='Related Token',
        ondelete='set null'
    )
    
    # Severity
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Severity', default='medium', required=True)
    
    @api.depends('incident_type', 'element_id', 'instance_id.name')
    def _compute_display_name(self):
        for record in self:
            type_label = dict(self._fields['incident_type'].selection).get(record.incident_type, 'Incident')
            element = record.element_id or 'Unknown'
            instance = record.instance_id.name if record.instance_id else 'N/A'
            record.display_name = f"{type_label} at {element} ({instance})"
    
    def action_resolve(self):
        """Mark incident as resolved"""
        self.ensure_one()
        
        if self.state == 'resolved':
            raise UserError(_("This incident is already resolved."))
        
        self.write({
            'state': 'resolved',
            'resolved_date': fields.Datetime.now(),
            'resolved_by': self.env.user.id
        })
        
        # Update instance incident count
        if self.instance_id:
            self.instance_id._compute_incident_count()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Incident Resolved'),
                'message': _('The incident has been marked as resolved.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_retry_job(self):
        """Retry the failed job (placeholder for future implementation)"""
        self.ensure_one()
        
        if self.incident_type not in ('job_no_retries', 'job_timeout'):
            raise UserError(_("This incident type does not support job retry."))
        
        if self.state == 'resolved':
            raise UserError(_("Cannot retry a resolved incident."))
        
        # TODO: Implement job retry logic
        raise UserError(_("Job retry functionality is not yet implemented."))
    
    def action_view_process_instance(self):
        """Navigate to the related process instance"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Process Instance'),
            'res_model': 'camoonda.process.instance',
            'res_id': self.instance_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def create_incident(self, instance_id, incident_type, message, **kwargs):
        """
        Helper method to create incidents programmatically
        
        :param instance_id: ID of the process instance
        :param incident_type: Type of incident
        :param message: Error message
        :param kwargs: Additional fields (element_id, error_type, stack_trace, etc.)
        :return: Created incident record
        """
        vals = {
            'instance_id': instance_id,
            'incident_type': incident_type,
            'message': message,
        }
        vals.update(kwargs)
        
        incident = self.create(vals)
        
        # Update instance incident count
        instance = self.env['camoonda.process.instance'].browse(instance_id)
        if instance.exists():
            instance._compute_incident_count()
        
        return incident
