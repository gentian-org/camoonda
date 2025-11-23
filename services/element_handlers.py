# -*- coding: utf-8 -*-
import logging
import json
from odoo import _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ElementHandlers:
    """
    Handlers for executing different types of process elements.
    Responsible for the actual execution logic of service tasks, user tasks, scripts, etc.
    """
    
    def __init__(self, env):
        """
        Initialize element handlers with Odoo environment.
        
        Args:
            env: Odoo environment for database operations
        """
        self.env = env
    
    def execute_service_task(self, token, element):
        """
        Execute a service task by calling an Odoo model method.
        
        Args:
            token: The token at this element
            element: The process element with service task configuration
            
        Returns:
            dict: Execution result
        """
        if not element.odoo_model or not element.odoo_method:
            raise ValidationError(_(
                f"Service task {element.element_id} is missing odoo_model or odoo_method configuration"
            ))
        
        _logger.info(f"Executing service task: {element.odoo_model}.{element.odoo_method}")
        
        # Check if in simulation mode
        if token.instance_id.simulation_mode:
            _logger.info("Simulation mode - skipping actual execution")
            return {'status': 'completed', 'simulated': True}
        
        try:
            # Get the model
            model = self.env[element.odoo_model]
            
            # Apply input mapping
            method_params = self._apply_input_mapping(token.variables, element.input_mapping)
            
            # Get the method
            method = getattr(model, element.odoo_method)
            
            # Execute the method
            # Handle Odoo create/write methods which expect a dictionary
            if element.odoo_method in ('create', 'write') and method_params:
                result = method(method_params)
            else:
                result = method(**method_params) if method_params else method()
            
            _logger.info(f"Service task completed, result type: {type(result)}")
            
            # Apply output mapping
            self._apply_output_mapping(token, result, element.output_mapping)
            
            return {
                'status': 'completed',
                'result': result,
            }
            
        except AttributeError as e:
            raise ValidationError(_(
                f"Method {element.odoo_method} not found on model {element.odoo_model}: {str(e)}"
            ))
        except Exception as e:
            _logger.exception(f"Error executing service task {element.element_id}")
            raise
    
    def execute_user_task(self, token, element):
        """
        Execute a user task by creating a work item and returning a form action.
        The token will wait until a user completes the task.
        
        Args:
            token: The token at this element
            element: The process element with user task configuration
            
        Returns:
            dict: Action to open the form for user interaction
        """
        _logger.info(f"Creating user task for element {element.element_id}")
        
        # Check if in simulation mode
        if token.instance_id.simulation_mode:
            _logger.info("Simulation mode - auto-completing user task")
            return {'status': 'completed', 'simulated': True}
        
        # Determine target model and view
        target_model = element.odoo_model or 'camoonda.process.token'
        form_view_id = element.form_view_id.id if element.form_view_id else False
        
        # Apply input mapping to prepare context
        context = self._apply_input_mapping(token.variables, element.input_mapping)
        context['token_id'] = token.id
        context['element_id'] = element.id
        context['default_instance_id'] = token.instance_id.id
        
        # Create or update target record if model is specified
        record_id = None
        if target_model != 'camoonda.process.token':
            try:
                # Create a new record with input variables
                record = self.env[target_model].create(context)
                record_id = record.id
                _logger.info(f"Created {target_model} record {record_id} for user task")
            except Exception as e:
                _logger.error(f"Could not create {target_model} record: {e}")
                record_id = False
        else:
            # Use the token itself as the record
            record_id = token.id
        
        # Return action to open form
        action = {
            'type': 'ir.actions.act_window',
            'name': element.element_name or 'User Task',
            'res_model': target_model,
            'res_id': record_id,
            'view_mode': element.form_mode or 'form',
            'view_id': form_view_id,
            'target': 'current',
            'context': context,
        }
        
        return {
            'status': 'waiting',
            'action': action,
            'reason': 'user_task',
        }
    
    def execute_script_task(self, token, element):
        """
        Execute a script task by running Python code.
        
        Args:
            token: The token at this element
            element: The process element with script configuration
            
        Returns:
            dict: Execution result
        """
        if not element.python_code:
            raise ValidationError(_(
                f"Script task {element.element_id} is missing python_code configuration"
            ))
        
        _logger.info(f"Executing script task: {element.element_id}")
        
        # Check if in simulation mode
        if token.instance_id.simulation_mode:
            _logger.info("Simulation mode - skipping script execution")
            return {'status': 'completed', 'simulated': True}
        
        try:
            # Create execution context
            variables = token.variables.copy() if token.variables else {}
            
            exec_context = {
                'env': self.env,
                'variables': variables,
                'token': token,
                'instance': token.instance_id,
                'element': element,
                'logger': _logger,
            }
            
            # Execute the script
            exec(element.python_code, {"__builtins__": __builtins__}, exec_context)
            
            # Update token variables from modified context
            if 'variables' in exec_context:
                token.write({'variables': exec_context['variables']})
            
            _logger.info(f"Script task completed successfully")
            
            return {
                'status': 'completed',
                'variables': exec_context.get('variables'),
            }
            
        except Exception as e:
            _logger.exception(f"Error executing script task {element.element_id}")
            raise
    
    def execute_stoodio_task(self, token, element):
        """
        Execute a Stoodio task by calling a Stoodio module.
        
        Args:
            token: The token at this element
            element: The process element with Stoodio configuration
            
        Returns:
            dict: Execution result
        """
        if not element.stoodio_module_id:
            raise ValidationError(_(
                f"Stoodio task {element.element_id} is missing stoodio_module_id configuration"
            ))
        
        _logger.info(f"Executing Stoodio task with module: {element.stoodio_module_id.name}")
        
        # Check if in simulation mode
        if token.instance_id.simulation_mode:
            _logger.info("Simulation mode - skipping Stoodio execution")
            return {'status': 'completed', 'simulated': True}
        
        # Check if stoodio.module model exists
        if 'stoodio.module' not in self.env:
            _logger.warning("Stoodio module not installed, skipping execution")
            return {'status': 'completed', 'stoodio_not_available': True}
        
        try:
            stoodio_module = element.stoodio_module_id
            
            # Apply input mapping
            input_data = self._apply_input_mapping(token.variables, element.input_mapping)
            
            # Call the Stoodio module (this is a placeholder - actual integration depends on Stoodio API)
            # TODO: Implement actual Stoodio module execution
            _logger.info(f"Stoodio module execution: {stoodio_module.name}")
            
            # For now, just pass through
            result = {
                'stoodio_module': stoodio_module.name,
                'input_data': input_data,
            }
            
            # Apply output mapping
            self._apply_output_mapping(token, result, element.output_mapping)
            
            return {
                'status': 'completed',
                'result': result,
            }
            
        except Exception as e:
            _logger.exception(f"Error executing Stoodio task {element.element_id}")
            raise
    
    def execute_auto_task(self, token, element):
        """
        Auto-detect and execute task based on available configuration.
        
        Args:
            token: The token at this element
            element: The process element
            
        Returns:
            dict: Execution result
        """
        _logger.info(f"Auto-detecting execution type for element {element.element_id}")
        
        # Try to detect based on configuration
        if element.odoo_model and element.odoo_method:
            _logger.info("Auto-detected as service task")
            return self.execute_service_task(token, element)
        
        elif element.python_code:
            _logger.info("Auto-detected as script task")
            return self.execute_script_task(token, element)
        
        elif element.stoodio_module_id:
            _logger.info("Auto-detected as Stoodio task")
            return self.execute_stoodio_task(token, element)
        
        elif element.form_view_id or element.odoo_model:
            _logger.info("Auto-detected as user task")
            return self.execute_user_task(token, element)
        
        else:
            _logger.warning(f"Could not auto-detect execution type for {element.element_id}, passing through")
            return {'status': 'completed', 'auto_detected': False}
    
    def _apply_input_mapping(self, variables, mapping_json):
        """
        Apply input mapping to transform process variables into method parameters.
        
        Args:
            variables: Dict of process variables
            mapping_json: JSON string defining the mapping
            
        Returns:
            dict: Mapped parameters
        """
        if not mapping_json:
            return variables or {}
        
        try:
            mapping = json.loads(mapping_json) if isinstance(mapping_json, str) else mapping_json
            result = {}
            
            for key, value in mapping.items():
                if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                    # Variable reference: ${variable_name}
                    var_name = value[2:-1]
                    result[key] = variables.get(var_name) if variables else None
                else:
                    # Literal value
                    result[key] = value
            
            return result
            
        except Exception as e:
            _logger.error(f"Error applying input mapping: {e}")
            return variables or {}
    
    def _apply_output_mapping(self, token, result, mapping_json):
        """
        Apply output mapping to transform method result into process variables.
        
        Args:
            token: The token to update
            result: The result from method execution
            mapping_json: JSON string defining the mapping
        """
        if not mapping_json:
            # No mapping - store entire result
            if result is not None:
                variables = token.variables.copy() if token.variables else {}
                variables['result'] = result
                token.write({'variables': variables})
            return
        
        try:
            mapping = json.loads(mapping_json) if isinstance(mapping_json, str) else mapping_json
            variables = token.variables.copy() if token.variables else {}
            
            for var_name, source_path in mapping.items():
                if isinstance(source_path, str) and source_path.startswith('${') and source_path.endswith('}'):
                    # Result reference: ${result.field} or ${result}
                    path = source_path[2:-1]
                    
                    if path == 'result':
                        variables[var_name] = result
                    elif path.startswith('result.'):
                        # Navigate result object
                        field = path[7:]  # Remove 'result.'
                        if hasattr(result, field):
                            variables[var_name] = getattr(result, field)
                        elif isinstance(result, dict):
                            variables[var_name] = result.get(field)
                        else:
                            _logger.warning(f"Could not find field {field} in result")
                    else:
                        variables[var_name] = variables.get(path)
                else:
                    # Literal value
                    variables[var_name] = source_path
            
            token.write({'variables': variables})
            
        except Exception as e:
            _logger.error(f"Error applying output mapping: {e}")
