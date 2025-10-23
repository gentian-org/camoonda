# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProcessToken(models.Model):
    _name = 'camoonda.process.token'
    _description = 'Process Token (Execution Position)'
    _order = 'arrived_date desc'

    instance_id = fields.Many2one('camoonda.process.instance', string='Process Instance', required=True, ondelete='cascade')
    element_id = fields.Char(string='Current Element ID', required=True, help="BPMN element ID from XML")
    element_type = fields.Char(string='Element Type', help="Type of BPMN element (task, gateway, event)")
    
    state = fields.Selection([
        ('active', 'Active'),
        ('waiting', 'Waiting'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], string='State', default='active', required=True)
    
    arrived_date = fields.Datetime(string='Arrived Date', default=fields.Datetime.now, required=True)
    completed_date = fields.Datetime(string='Completed Date')
    
    # For parallel gateways: tokens can split
    parent_token_id = fields.Many2one('camoonda.process.token', string='Parent Token', ondelete='set null')
    child_token_ids = fields.One2many('camoonda.process.token', 'parent_token_id', string='Child Tokens')
    
    # Token data (local scope)
    variables = fields.Json(string='Token Variables', default={})
    
    def action_complete(self):
        """Mark token as completed and move to next element"""
        self.ensure_one()
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now()
        })
        # TODO: Create new token(s) for next element(s)
