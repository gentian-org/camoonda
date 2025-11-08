# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SequenceFlow(models.Model):
    _name = 'sequence.flow'
    _description = 'Process Sequence Flow (Connection)'
    _order = 'sequence, flow_id'

    process_definition_id = fields.Many2one(
        'camoonda.process.definition',
        string='Process Definition',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    flow_id = fields.Char(
        string='Flow ID',
        required=True,
        help="Flow ID from BPMN XML (e.g., Flow_1, SequenceFlow_2)"
    )
    
    flow_name = fields.Char(
        string='Flow Name',
        help="Display name of the flow"
    )
    
    source_element_id = fields.Many2one(
        'process.element',
        string='Source Element',
        required=True,
        ondelete='cascade',
        index=True,
        help="Element where this flow starts"
    )
    
    target_element_id = fields.Many2one(
        'process.element',
        string='Target Element',
        required=True,
        ondelete='cascade',
        index=True,
        help="Element where this flow ends"
    )
    
    # Display fields showing XML element IDs
    source_ref = fields.Char(
        string='From',
        compute='_compute_element_refs',
        store=True,
        help="Source element ID from BPMN XML"
    )
    
    target_ref = fields.Char(
        string='To',
        compute='_compute_element_refs',
        store=True,
        help="Target element ID from BPMN XML"
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Evaluation order for flows from same source (lower = higher priority)"
    )
    
    # Conditional flow
    condition_type = fields.Selection([
        ('none', 'Unconditional'),
        ('expression', 'Condition Expression'),
        ('default', 'Default Flow'),
    ], string='Condition Type', default='none', required=True)
    
    condition_expression = fields.Text(
        string='Condition Expression',
        help="Python expression evaluated to determine if flow should be taken. "
             "Available: variables dict. Should return True/False."
    )
    
    is_default = fields.Boolean(
        string='Is Default Flow',
        default=False,
        help="Default flow taken when no other conditions match (for gateways)"
    )
    
    # Status
    active = fields.Boolean(string='Active', default=True)
    
    notes = fields.Text(string='Notes')
    
    _sql_constraints = [
        ('unique_flow_per_definition', 
         'unique(process_definition_id, flow_id)',
         'Flow ID must be unique within a process definition!'),
        ('check_different_elements',
         'check(source_element_id != target_element_id)',
         'Source and target elements must be different!')
    ]
    
    @api.depends('source_element_id', 'source_element_id.element_id', 
                 'target_element_id', 'target_element_id.element_id')
    def _compute_element_refs(self):
        """Compute readable source and target references from BPMN XML IDs"""
        for record in self:
            record.source_ref = record.source_element_id.element_id if record.source_element_id else ''
            record.target_ref = record.target_element_id.element_id if record.target_element_id else ''
    
    def name_get(self):
        """Display flow with source and target"""
        result = []
        for record in self:
            source = record.source_element_id.element_id if record.source_element_id else '?'
            target = record.target_element_id.element_id if record.target_element_id else '?'
            name = f"{source} → {target}"
            if record.flow_name:
                name = f"{record.flow_name} ({name})"
            result.append((record.id, name))
        return result
    
    @api.constrains('condition_type', 'condition_expression', 'is_default')
    def _check_condition_consistency(self):
        """Ensure condition configuration is consistent"""
        for record in self:
            if record.condition_type == 'expression' and not record.condition_expression:
                raise models.ValidationError(
                    "Condition expression is required when condition type is 'expression'"
                )
            if record.condition_type == 'default' and not record.is_default:
                record.is_default = True
            if record.is_default and record.condition_type not in ['none', 'default']:
                raise models.ValidationError(
                    "Default flow cannot have a condition expression"
                )
