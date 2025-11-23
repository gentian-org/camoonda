# -*- coding: utf-8 -*-

from odoo import models, fields


class ExecutionHistory(models.Model):
    _name = 'camoonda.execution.history'
    _description = 'BPMN Execution History'
    _order = 'execution_date desc'

    instance_id = fields.Many2one('camoonda.process.instance', string='Process Instance', required=True, ondelete='cascade')
    token_id = fields.Many2one('camoonda.process.token', string='Token', ondelete='set null')
    element_id = fields.Char(string='Element ID', required=True)
    element_type = fields.Char(string='Element Type')
    element_name = fields.Char(string='Element Name')
    
    execution_date = fields.Datetime(string='Execution Date', default=fields.Datetime.now, required=True)
    executed_by = fields.Many2one('res.users', string='Executed By', default=lambda self: self.env.user)
    
    event_type = fields.Char(string='Event Type', required=True)
    details = fields.Text(string='Details')
    
    result = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped')
    ], string='Result')
    
    error_message = fields.Text(string='Error Message')
    execution_data = fields.Json(string='Execution Data', help="Input/output data for this execution")
    
    duration_ms = fields.Integer(string='Duration (ms)', help="Execution duration in milliseconds")
