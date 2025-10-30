# BPMN-Camoonda Integration Plan

## Overview
**BPMN module is the primary interface.** Users design processes in BPMN, configure execution from there, and launch simulations/executions. Camoonda is the backend execution engine that processes call.

---

## Phase 1: BPMN-Driven Element Configuration (Foundation)

**Goal:** Add Camoonda execution configuration directly in BPMN properties panel.

### Tasks:
1. **Extend BPMN Process Model** (`bpmn/models/bpmn_process.py`)
   - Add fields:
     - `is_executable = fields.Boolean('Executable', default=False)`
     - `camoonda_process_id` (Many2one → camoonda.process.definition)
     - `execution_element_ids` (One2many → new bridge model)
   
2. **Create Bridge Model** (`bpmn/models/bpmn_element_execution.py`)
   ```python
   class BpmnElementExecution(models.Model):
       _name = 'bpmn.element.execution'
       
       bpmn_process_id = fields.Many2one('bpmn.process')
       element_id = fields.Char('BPMN Element ID')  # from XML
       element_name = fields.Char('Element Name')
       element_type = fields.Selection([...])  # task, gateway, event
       
       # Execution configuration
       execution_type = fields.Selection([
           ('none', 'No Action'),
           ('service', 'Call Odoo Method'),
           ('user_task', 'Open Form'),
           ('script', 'Python Code'),
           ('stoodio', 'Stoodio Module')
       ])
       
       # Odoo/Stoodio linking
       odoo_model = fields.Char('Model')
       odoo_method = fields.Char('Method')
       stoodio_module_id = fields.Many2one('stoodio.module')
       form_view_id = fields.Many2one('ir.ui.view')
       python_code = fields.Text('Python Code')
   ```

3. **BPMN Properties Panel Enhancement** (JavaScript)
   - Add "Execution" tab in properties panel
   - For selected element, show form to configure:
     - Execution Type dropdown
     - Dynamic fields based on type (model/method/form/etc)
   - Save to `bpmn.element.execution` via RPC
   - Visual indicator on diagram (e.g., badge) showing element is configured

4. **Auto-Parse BPMN on Save**
   - When BPMN XML changes, automatically:
     - Extract all elements (tasks, gateways, events)
     - Create/update `bpmn.element.execution` records
     - Keep existing configurations, add new elements

**Deliverables:**
- Properties panel with "Execution" tab in BPMN editor
- Bridge model linking BPMN elements to execution config
- Auto-sync of elements when diagram changes

---

## Phase 2: BPMN-Driven Simulation Mode (Debug)

**Goal:** Launch simulation from BPMN editor with visual token overlay.

### Tasks:
1. **Simulation Controls in BPMN Editor**
   - Add toolbar buttons:
     - "▶ Start Simulation" → Create Camoonda instance in simulation mode
     - "⏭ Step Forward" → Advance active tokens
     - "⏸ Pause" / "⏹ Stop"
     - "🔄 Reset" → Clear simulation
   - Show simulation status bar (instance ID, tokens count, current variables)

2. **Camoonda Execution Backend** (`camoonda/services/execution_engine.py`)
   - `start_simulation(bpmn_process_id, initial_variables)`:
     - Parse BPMN XML from bpmn.process
     - Create process.instance with `simulation_mode=True`
     - Create token at start event
     - Return instance_id + token positions
   
   - `step_forward(instance_id, token_id)`:
     - Move token to next element(s)
     - For simulation: skip actual execution, just move token
     - Handle gateways (XOR picks random path, AND splits/joins)
     - Return new token positions + updated variables
   
   - `get_token_positions(instance_id)`:
     - Return list of {element_id, token_id, state} for overlay

3. **Visual Token Overlay** (JavaScript)
   - Use bpmn-js overlays API
   - Show animated token markers on active elements
   - Highlight next possible paths
   - Display process variables panel (editable in simulation)
   - Show execution history timeline

4. **RPC Integration**
   - BPMN module calls Camoonda methods via RPC:
     ```javascript
     await this.orm.call('camoonda.process.instance', 
                         'start_simulation', 
                         [bpmn_process_id], 
                         {initial_variables: {...}});
     ```

**Deliverables:**
- Simulation controls integrated in BPMN editor toolbar
- Visual token overlay showing execution flow
- Camoonda backend that handles simulation logic
- No actual Odoo operations executed (safe debugging)

---

## Phase 3: BPMN-Driven Real Execution (Production)

**Goal:** Execute real Odoo/Stoodio operations from BPMN editor using configured elements.

### Tasks:
1. **Execution Launch from BPMN**
   - Add button: "▶ Execute Process" (separate from simulation)
   - Show dialog:
     - Initial variables input
     - Business key
     - "Run as current user" checkbox
   - Creates real Camoonda instance (`simulation_mode=False`)
   - Opens monitoring view (see below)

2. **Camoonda Execution Handlers** (`camoonda/services/element_handlers.py`)
   - Read configuration from `bpmn.element.execution` model
   - Execute based on `execution_type`:
   
   **Service Task:**
   ```python
   def execute_service_task(self, token, element_config):
       model = self.env[element_config.odoo_model]
       method = getattr(model, element_config.odoo_method)
       result = method(**self._map_variables(token))
       self._update_variables(token, result)
   ```
   
   **User Task:**
   ```python
   def execute_user_task(self, token, element_config):
       # Create action to open form
       action = {
           'type': 'ir.actions.act_window',
           'res_model': element_config.odoo_model,
           'view_id': element_config.form_view_id.id,
           'context': {
               'process_instance_id': token.instance_id.id,
               'token_id': token.id,
           }
       }
       # Token stays in 'waiting' state until form submitted
       return action
   ```
   
   **Stoodio Module:**
   ```python
   def execute_stoodio_module(self, token, element_config):
       # Launch Stoodio module with context
       stoodio_module = element_config.stoodio_module_id
       # Execute module logic...
   ```

3. **Live Monitoring in BPMN**
   - Button: "📊 Monitor Active Instances"
   - Opens side panel showing:
     - List of running instances for this process
     - Token positions overlayed on diagram (live)
     - Current variables for selected instance
     - Incidents/errors highlighted in red
   - Click instance → see its execution history

4. **Process Instance Management**
   - From BPMN editor, access instance actions:
     - Suspend/Resume
     - Cancel
     - View execution history
     - Resolve incidents (retry failed elements)

**Deliverables:**
- Execute button launches real processes from BPMN
- Camoonda executes configured Odoo/Stoodio operations
- Live monitoring overlay showing active instances
- User task forms integrated with process flow

---

## Phase 4: Polish & Production Features

### Tasks:
1. **BPMN XML Extension Elements**
   - Store execution config in BPMN XML `extensionElements`:
     ```xml
     <bpmn:serviceTask id="Task_1">
       <bpmn:extensionElements>
         <odoo:execution>
           <odoo:type>service</odoo:type>
           <odoo:model>sale.order</odoo:model>
           <odoo:method>action_confirm</odoo:method>
         </odoo:execution>
       </bpmn:extensionElements>
     </bpmn:serviceTask>
     ```
   - Import/export: sync `bpmn.element.execution` ↔ XML extensions
   - Makes BPMN portable with execution config embedded

2. **Process Template Library** (in BPMN module)
   - Gallery of pre-configured executable processes
   - "Sales Order Approval", "Invoice Processing", etc.
   - Clone template → customize → execute

3. **Advanced Monitoring**
   - Heatmap overlay: show element execution frequency/duration
   - Performance analytics per element
   - Bottleneck detection

4. **Camoonda Admin Interface** (minimal)
   - View for process admins (not typical users)
   - Bulk incident management
   - System health dashboard
   - Most users never see Camoonda directly

**Deliverables:**
- Portable BPMN with embedded execution config
- Template library for quick starts
- Advanced process analytics

---

## Revised Architecture: BPMN-Centric Design

### Data Flow:
```
┌─────────────────────────────────────────────────┐
│  BPMN Module (PRIMARY INTERFACE)               │
│  - Visual diagram editor                       │
│  - Properties panel (execution config)         │
│  - Simulation controls (▶⏭⏸⏹)                 │
│  - Execution launcher                          │
│  - Live monitoring overlay                     │
└─────────────────┬───────────────────────────────┘
                  │ RPC Calls
                  ↓
┌─────────────────────────────────────────────────┐
│  Camoonda (BACKEND ENGINE - Hidden from users) │
│  - Parse BPMN XML                              │
│  - Execute tokens (simulation or real)         │
│  - Call Odoo/Stoodio operations                │
│  - Track instance state                        │
│  - Store execution history                     │
└─────────────────────────────────────────────────┘
```

### Models:
**BPMN Module:**
- `bpmn.process` - Main model users interact with
- `bpmn.element.execution` - Execution config per element (bridge model)

**Camoonda Module:**
- `camoonda.process.instance` - Runtime instances
- `camoonda.process.token` - Token positions
- `camoonda.process.incident` - Errors
- `camoonda.execution.history` - Audit trail
- (No `process.definition` - uses bpmn.process directly)

### Key Services (in Camoonda):
- `execution_engine.py` - Token movement, graph navigation
- `element_handlers.py` - Execute service/user/script tasks
- `bpmn_parser.py` - Parse XML to extract structure

### User Experience:
1. **User opens BPMN process** → Sees diagram editor
2. **Clicks element** → Properties panel shows "Execution" tab
3. **Configures execution** → Select Odoo model/method/form
4. **Clicks "Simulate"** → Tokens move visually, no real operations
5. **Clicks "Execute"** → Creates real instance, executes operations
6. **Monitors live** → See active instances overlayed on diagram

**Users never open Camoonda forms directly** - everything done from BPMN editor.

---

## Implementation Priority

### Phase 1 (Foundation):
1. Create `bpmn.element.execution` bridge model
2. Auto-parse BPMN XML on save to populate bridge records
3. Add "Execution" tab to BPMN properties panel
4. Allow selecting execution type + configuring Odoo/Stoodio links

### Phase 2 (Simulation):
1. Add simulation toolbar to BPMN editor
2. Implement Camoonda `start_simulation()` / `step_forward()` methods
3. Visual token overlay using bpmn-js overlays API
4. Process variables panel in BPMN editor

### Phase 3 (Real Execution):
1. Implement element handlers (service/user/script tasks)
2. Add "Execute" button to BPMN editor
3. Live monitoring overlay for active instances
4. User task form integration

### Phase 4 (Polish):
1. Store config in BPMN XML extensionElements
2. Process template library
3. Advanced analytics

---

## Key Principle

**Everything is driven from BPMN module.** Camoonda is just the execution backend - a service layer that BPMN calls via RPC. Users design, configure, simulate, execute, and monitor all from the BPMN editor.

---

## Next Steps

Ready to start Phase 1? We'll begin with:
1. Create `bpmn.element.execution` model
2. Add "Execution" tab to BPMN properties panel
3. Auto-sync elements when BPMN XML changes

This gives you the foundation to configure elements directly in the BPMN editor.
