# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProcessToken(models.Model):
    _name = 'camoonda.process.token'
    _description = 'Process Token (Execution Position)'
    _order = 'arrived_date desc'

    instance_id = fields.Many2one('camoonda.process.instance', string='Process Instance', required=True, ondelete='cascade')
    
    # Updated to use process.element instead of string element_id
    current_element_id = fields.Many2one(
        'process.element',
        string='Current Element',
        required=True,
        ondelete='cascade',
        help="The process element where this token is currently located"
    )
    
    # Legacy fields for backward compatibility
    element_id = fields.Char(
        string='Element ID (Legacy)',
        compute='_compute_element_id',
        store=True,
        help="BPMN element ID from current_element_id"
    )
    element_type = fields.Char(
        string='Element Type',
        compute='_compute_element_type',
        store=True,
        help="Type of BPMN element (task, gateway, event)"
    )
    
    state = fields.Selection([
        ('active', 'Active'),
        ('waiting', 'Waiting'),
        ('waiting_merge', 'Waiting for Merge'),
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
    
    @api.depends('current_element_id')
    def _compute_element_id(self):
        """Compute legacy element_id from current_element_id"""
        for token in self:
            token.element_id = token.current_element_id.element_id if token.current_element_id else False
    
    @api.depends('current_element_id')
    def _compute_element_type(self):
        """Compute element_type from current_element_id"""
        for token in self:
            token.element_type = token.current_element_id.element_type if token.current_element_id else False
    
    def execute(self):
        """
        Execute this token at its current position.
        Uses the execution engine to process the current element.
        
        Returns:
            dict: Execution result
        """
        from ..services.execution_engine import ExecutionEngine
        
        self.ensure_one()
        engine = ExecutionEngine(self.env)
        return engine.execute_token(self.id)
    
    def action_complete(self):
        """Mark token as completed and move to next element"""
        self.ensure_one()
        self.write({
            'state': 'completed',
            'completed_date': fields.Datetime.now()
        })
    
    def action_retry(self):
        """Retry a failed token"""
        self.ensure_one()
        if self.state == 'failed':
            self.write({'state': 'active'})
            return self.execute()
        return {'status': 'skipped', 'reason': 'Token is not in failed state'}
