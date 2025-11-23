# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StartInstanceWizard(models.TransientModel):
    _name = 'camoonda.start.instance.wizard'
    _description = 'Start Process Instance Wizard'

    process_definition_id = fields.Many2one(
        'camoonda.process.definition',
        string='Process Definition',
        required=True,
        readonly=True
    )
    
    business_key = fields.Char(
        string='Business Key',
        help="Optional unique identifier for this instance (e.g. Order-123)"
    )
    
    variables_json = fields.Text(
        string='Initial Variables (JSON)',
        default='{\n  \n}',
        help="JSON object containing initial process variables"
    )
    
    def action_start(self):
        self.ensure_one()
        
        # Parse variables
        variables = {}
        if self.variables_json:
            try:
                variables = json.loads(self.variables_json)
                if not isinstance(variables, dict):
                    raise UserError("Variables must be a JSON object (dictionary)")
            except json.JSONDecodeError as e:
                raise UserError(f"Invalid JSON format: {str(e)}")
        
        # Start instance
        instance = self.process_definition_id.start_instance(
            variables=variables,
            business_key=self.business_key
        )
        
        # Open the created instance
        return {
            'type': 'ir.actions.act_window',
            'name': 'Process Instance',
            'res_model': 'camoonda.process.instance',
            'res_id': instance.id,
            'view_mode': 'form',
            'target': 'current',
        }
