# -*- coding: utf-8 -*-
import logging
from odoo import _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Core process execution engine for Camoonda.
    Handles process instance creation, token execution, and navigation through process elements.
    """
    
    def __init__(self, env):
        """
        Initialize the execution engine with Odoo environment.
        
        Args:
            env: Odoo environment for database operations
        """
        self.env = env
        self.element_handlers = None  # Lazy loaded
    
    def _get_element_handlers(self):
        """Lazy load element handlers to avoid circular imports"""
        if not self.element_handlers:
            from .element_handlers import ElementHandlers
            self.element_handlers = ElementHandlers(self.env)
        return self.element_handlers
    
    def start_process(self, process_definition_id, variables=None, business_key=None, simulation_mode=False):
        """
        Start a new process instance from a process definition.
        
        Args:
            process_definition_id: ID of the process definition to instantiate
            variables: Dict of initial process variables (optional)
            business_key: Business identifier for this instance (optional)
            simulation_mode: If True, don't execute real operations (optional)
            
        Returns:
            process.instance record
        """
        _logger.info(f"Starting process instance for definition {process_definition_id}")
        
        # Get process definition
        process_def = self.env['camoonda.process.definition'].browse(process_definition_id)
        if not process_def.exists():
            raise ValidationError(_("Process definition not found"))
        
        # Create process instance
        instance_values = {
            'process_definition_id': process_definition_id,
            'business_key': business_key,
            'state': 'active',
            'simulation_mode': simulation_mode,
            'variables': variables or {},
        }
        instance = self.env['camoonda.process.instance'].create(instance_values)
        
        _logger.info(f"Created process instance {instance.id}")
        
        # Note: The create() method of process.instance automatically calls action_start()
        # which creates the initial token and starts execution.
        # We don't need to do it here to avoid double execution.
        
        return instance
    
    def execute_token(self, token_id):
        """
        Execute the current element for a token and move to next element(s).
        
        This is the main execution loop. It:
        1. Gets the current element for the token
        2. Executes the element (service task, user task, script, etc)
        3. Navigates to next element(s) based on sequence flows
        4. Handles gateways (splitting/merging tokens)
        
        Args:
            token_id: ID of the token to execute
            
        Returns:
            dict: Result information (next actions, forms to display, etc)
        """
        token = self.env['camoonda.process.token'].browse(token_id)
        if not token.exists():
            raise ValidationError(_("Token not found"))
        
        if token.state != 'active':
            _logger.warning(f"Token {token_id} is not active (state: {token.state})")
            return {'status': 'skipped', 'reason': f'Token state is {token.state}'}
        
        element = token.current_element_id
        instance = token.instance_id
        
        _logger.info(f"Executing token {token_id} at element {element.element_id} ({element.element_type})")
        
        try:
            # Log element started
            self.env['camoonda.execution.history'].create({
                'instance_id': instance.id,
                'token_id': token.id,
                'element_id': element.id,
                'event_type': 'element_started',
                'details': f"Started executing {element.element_name or element.element_id}",
            })
            
            # Execute based on element type
            result = self._execute_element(token, element)
            
            # Sync token variables to instance
            if token.variables:
                current_vars = instance.variables or {}
                # Only update if there are changes
                if token.variables != current_vars:
                    # Merge token variables into instance variables
                    new_vars = current_vars.copy()
                    new_vars.update(token.variables)
                    instance.write({'variables': new_vars})
            
            # Handle different result types
            if result.get('status') == 'waiting':
                # User task or external task - token waits
                token.write({'state': 'waiting'})
                _logger.info(f"Token {token_id} is now waiting at {element.element_id}")
                return result
            
            # Log element completed
            self.env['camoonda.execution.history'].create({
                'instance_id': instance.id,
                'token_id': token.id,
                'element_id': element.id,
                'event_type': 'element_completed',
                'details': f"Completed executing {element.element_name or element.element_id}",
            })
            
            # Navigate to next element(s)
            self._navigate_to_next(token, element)
            
            return result
            
        except Exception as e:
            _logger.exception(f"Error executing token {token_id} at element {element.element_id}")
            
            # Use savepoint to ensure we can log the incident even if transaction is aborted
            with self.env.cr.savepoint():
                # Create incident
                self.env['camoonda.process.incident'].create({
                    'instance_id': instance.id,
                    'token_id': token.id,
                    'element_id': element.id,
                    'incident_type': 'unhandled_error',
                    'message': str(e),
                    'state': 'created',
                })
                
                # Update token state
                token.write({'state': 'failed'})
                
                # Log error
                self.env['camoonda.execution.history'].create({
                    'instance_id': instance.id,
                    'token_id': token.id,
                    'element_id': element.id,
                    'event_type': 'element_failed',
                    'details': f"Error: {str(e)}",
                })
            
            return {'status': 'failed', 'error': str(e)}
    
    def _execute_element(self, token, element):
        """
        Execute a single element based on its type and configuration.
        
        Args:
            token: The token at this element
            element: The process element to execute
            
        Returns:
            dict: Execution result
        """
        element_type = element.element_type
        execution_type = element.execution_type
        
        # Handle flow elements (events, gateways) directly
        if element_type in ('startEvent', 'endEvent'):
            return self._handle_event(token, element)
        elif element_type in ('exclusiveGateway', 'parallelGateway', 'inclusiveGateway'):
            return self._handle_gateway(token, element)
        
        # Handle tasks with execution configuration
        if execution_type == 'none':
            _logger.info(f"Element {element.element_id} has no execution config, passing through")
            return {'status': 'completed'}
        
        # Delegate to element handlers
        handlers = self._get_element_handlers()
        
        if execution_type == 'service':
            return handlers.execute_service_task(token, element)
        elif execution_type == 'user_task':
            return handlers.execute_user_task(token, element)
        elif execution_type == 'script':
            return handlers.execute_script_task(token, element)
        elif execution_type == 'stoodio':
            return handlers.execute_stoodio_task(token, element)
        elif execution_type == 'auto':
            # Try to auto-detect and execute
            return handlers.execute_auto_task(token, element)
        else:
            _logger.warning(f"Unknown execution type: {execution_type}")
            return {'status': 'completed'}
    
    def _handle_event(self, token, element):
        """Handle start and end events"""
        if element.element_type == 'startEvent':
            _logger.info(f"Start event {element.element_id} - passing through")
            return {'status': 'completed'}
        
        elif element.element_type == 'endEvent':
            _logger.info(f"End event {element.element_id} - completing token")
            token.write({'state': 'completed'})
            
            # Check if all tokens are completed
            active_tokens = self.env['camoonda.process.token'].search_count([
                ('instance_id', '=', token.instance_id.id),
                ('state', 'in', ['active', 'waiting'])
            ])
            
            if active_tokens == 0:
                # All tokens completed - complete the instance
                token.instance_id.write({'state': 'completed'})
                _logger.info(f"Process instance {token.instance_id.id} completed")
            
            return {'status': 'completed', 'end_reached': True}
        
        return {'status': 'completed'}
    
    def _handle_gateway(self, token, gateway):
        """
        Handle gateway logic (exclusive, parallel, inclusive).
        This is called during execution. The actual split/merge happens in _navigate_to_next.
        """
        gateway_type = gateway.element_type
        
        if gateway_type == 'exclusiveGateway':
            # XOR gateway - will select one path in _navigate_to_next
            _logger.info(f"Exclusive gateway {gateway.element_id} - will select one path")
            return {'status': 'completed', 'gateway_type': 'exclusive'}
        
        elif gateway_type == 'parallelGateway':
            # AND gateway - check if this is a split or merge
            incoming_count = len(gateway.incoming_flow_ids)
            outgoing_count = len(gateway.outgoing_flow_ids)
            
            if outgoing_count > 1:
                # Split - will create multiple tokens in _navigate_to_next
                _logger.info(f"Parallel gateway {gateway.element_id} - split to {outgoing_count} paths")
                return {'status': 'completed', 'gateway_type': 'parallel_split'}
            else:
                # Merge - need to wait for all incoming tokens
                return self._handle_parallel_merge(token, gateway)
        
        elif gateway_type == 'inclusiveGateway':
            # OR gateway - select matching paths
            _logger.info(f"Inclusive gateway {gateway.element_id} - will select matching paths")
            return {'status': 'completed', 'gateway_type': 'inclusive'}
        
        return {'status': 'completed'}
    
    def _handle_parallel_merge(self, token, gateway):
        """
        Handle parallel gateway merge - wait for all incoming tokens.
        """
        incoming_flows = gateway.incoming_flow_ids
        
        # Mark this token as waiting at merge
        token.write({'state': 'waiting_merge'})
        
        # Check how many tokens are at this gateway
        tokens_at_gateway = self.env['camoonda.process.token'].search([
            ('instance_id', '=', token.instance_id.id),
            ('current_element_id', '=', gateway.id),
            ('state', '=', 'waiting_merge')
        ])
        
        _logger.info(f"Parallel merge: {len(tokens_at_gateway)} of {len(incoming_flows)} tokens arrived")
        
        if len(tokens_at_gateway) >= len(incoming_flows):
            # All tokens arrived - merge them
            _logger.info(f"All tokens arrived at parallel merge {gateway.element_id}")
            
            # Keep one token active, complete the others
            tokens_to_complete = tokens_at_gateway[1:]
            for t in tokens_to_complete:
                t.write({'state': 'completed'})
            
            # Reactivate the first token
            tokens_at_gateway[0].write({'state': 'active'})
            
            return {'status': 'completed', 'merged': True}
        else:
            # Still waiting for more tokens
            return {'status': 'waiting', 'reason': 'waiting_for_parallel_merge'}
    
    def _navigate_to_next(self, token, current_element):
        """
        Navigate to the next element(s) based on outgoing sequence flows.
        Handles splitting tokens for parallel gateways.
        """
        outgoing_flows = current_element.outgoing_flow_ids
        
        if not outgoing_flows:
            # No outgoing flows - must be an end event
            _logger.info(f"No outgoing flows from {current_element.element_id}")
            return
        
        gateway_type = current_element.element_type
        
        if gateway_type == 'exclusiveGateway':
            # XOR - take first matching condition or default
            next_flow = self._evaluate_exclusive_gateway(token, outgoing_flows)
            if next_flow:
                self._move_token(token, next_flow.target_element_id)
        
        elif gateway_type == 'parallelGateway':
            # AND - create token for each outgoing flow
            if len(outgoing_flows) > 1:
                self._split_token_parallel(token, outgoing_flows)
            else:
                # Single outgoing flow (merge already handled)
                self._move_token(token, outgoing_flows[0].target_element_id)
        
        elif gateway_type == 'inclusiveGateway':
            # OR - take all matching conditions
            matching_flows = self._evaluate_inclusive_gateway(token, outgoing_flows)
            if len(matching_flows) > 1:
                self._split_token_parallel(token, matching_flows)
            elif matching_flows:
                self._move_token(token, matching_flows[0].target_element_id)
        
        else:
            # Regular flow node - should have one outgoing flow
            if len(outgoing_flows) == 1:
                self._move_token(token, outgoing_flows[0].target_element_id)
            else:
                _logger.warning(f"Element {current_element.element_id} has {len(outgoing_flows)} outgoing flows but is not a gateway")
                # Take the first one
                self._move_token(token, outgoing_flows[0].target_element_id)
    
    def _evaluate_exclusive_gateway(self, token, flows):
        """Evaluate XOR gateway - return first matching flow or default"""
        default_flow = None
        
        for flow in flows.sorted('sequence'):
            if flow.is_default:
                default_flow = flow
                continue
            
            if flow.condition_type == 'none':
                return flow
            
            if self._evaluate_condition(token, flow.condition_expression):
                return flow
        
        # Return default flow if no condition matched
        return default_flow
    
    def _evaluate_inclusive_gateway(self, token, flows):
        """Evaluate OR gateway - return all matching flows"""
        matching_flows = []
        default_flow = None
        
        for flow in flows.sorted('sequence'):
            if flow.is_default:
                default_flow = flow
                continue
            
            if flow.condition_type == 'none':
                matching_flows.append(flow)
            elif self._evaluate_condition(token, flow.condition_expression):
                matching_flows.append(flow)
        
        # If no flows matched, use default
        if not matching_flows and default_flow:
            matching_flows = [default_flow]
        
        return matching_flows
    
    def _evaluate_condition(self, token, condition_expression):
        """Evaluate a condition expression using process variables"""
        if not condition_expression:
            return True
        
        try:
            # Create evaluation context with variables
            context = {
                'variables': token.variables,
                'env': self.env,
                'token': token,
                'instance': token.instance_id,
            }
            
            # Add variables directly to context for easier access
            if token.variables:
                context.update(token.variables)
            
            # Evaluate expression
            result = eval(condition_expression, {"__builtins__": {}}, context)
            return bool(result)
            
        except Exception as e:
            _logger.error(f"Error evaluating condition '{condition_expression}': {e}")
            return False
    
    def _move_token(self, token, next_element):
        """Move token to next element and continue execution"""
        _logger.info(f"Moving token {token.id} to {next_element.element_id}")
        
        token.write({'current_element_id': next_element.id})
        
        # Continue execution at new element
        self.execute_token(token.id)
    
    def _split_token_parallel(self, token, flows):
        """Split token into multiple tokens for parallel execution"""
        _logger.info(f"Splitting token {token.id} into {len(flows)} tokens")
        
        # Use the existing token for the first flow
        first_flow = flows[0]
        token.write({'current_element_id': first_flow.target_element_id.id})
        
        # Create new tokens for remaining flows
        for flow in flows[1:]:
            new_token = self.env['camoonda.process.token'].create({
                'instance_id': token.instance_id.id,
                'current_element_id': flow.target_element_id.id,
                'state': 'active',
                'variables': token.variables.copy() if token.variables else {},
                'parent_token_id': token.id,
            })
            _logger.info(f"Created new token {new_token.id} at {flow.target_element_id.element_id}")
            
            # Execute the new token
            self.execute_token(new_token.id)
        
        # Execute the original token
        self.execute_token(token.id)
