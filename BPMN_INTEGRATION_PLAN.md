# BPMN-Camoonda Integration Plan

## Overview
**Architecture:** BPMN module provides the visual designer and deployment interface. Camoonda is a standalone process execution engine that stores complete process topology and executes processes independently.

**Key Principle:** BPMN diagrams are "deployed" to Camoonda, which extracts and stores the full process structure (elements and flows) in its own database tables. This makes Camoonda self-sufficient - it can execute processes without parsing XML at runtime.

---

## Implemented: Process Topology Storage (Foundation)

**Status:** ✅ COMPLETE

### Architecture Changes:
Instead of storing execution config only in BPMN module, we now:
1. **BPMN module** = Visual designer + deployment tool
2. **Camoonda** = Complete process engine with topology storage + execution

### Models Created:

**In Camoonda:**
- `process.element` - Stores all BPMN elements (tasks, events, gateways)
  - Contains full execution configuration per element
  - Links to process definition
  - Knows incoming/outgoing flows
  
- `sequence.flow` - Stores all connections between elements
  - Source and target element references
  - Condition expressions for gateways
  - Sequence/priority for evaluation order

- `camoonda.process.definition` - Enhanced with:
  - `bpmn_process_id` - Optional link back to BPMN diagram
  - `element_ids` - One2many to process.element
  - `flow_ids` - One2many to sequence.flow
  - Stores BPMN XML as reference

**In BPMN:**
- `bpmn.process` - Visual diagram storage + deployment actions
  - `action_deploy_to_camoonda()` - Parses XML and creates Camoonda records
  - `is_executable` - Deployment status flag
  - `camoonda_definition_id` - Link to deployed definition
  - `last_deployed_date` - Deployment timestamp

### Deployment Flow:
```
1. User creates BPMN diagram in BPMN editor
   ↓
2. User clicks "Deploy to Camoonda" button
   ↓
3. BPMN module action_deploy_to_camoonda():
   - Parses BPMN XML completely
   - Extracts all elements (tasks, events, gateways, etc.)
   - Extracts all sequence flows (connections)
   - Creates camoonda.process.definition
   - Creates process.element for each BPMN element
   - Creates sequence.flow for each connection
   - Stores configuration in Camoonda models
   ↓
4. Camoonda now has complete topology
   - Can execute process independently
   - Can query elements and flows via database
   - No XML parsing needed at runtime
```

### Benefits of This Architecture:
✅ **Sustainable** - Process topology persists even if BPMN diagram deleted
✅ **Independent** - Camoonda executes without BPMN module at runtime  
✅ **Queryable** - Can search/filter elements and flows in database
✅ **Configurable** - Rich execution config per element
✅ **Versionable** - Each deployment creates new version
✅ **Traceable** - Can track which BPMN diagram created definition

---

## Phase 1: Element Execution Configuration (Next)

**Goal:** Configure how each element executes (Odoo methods, forms, scripts, etc.)

### Current State:
- `process.element` model has all execution config fields
- Fields include:
  - `execution_type` - service, user_task, script, stoodio, auto, none
  - `odoo_model` / `odoo_method` - For service tasks
  - `form_view_id` / `form_mode` - For user tasks
  - `python_code` - For script tasks
  - `stoodio_module_id` - For Stoodio integration
  - `input_mapping` / `output_mapping` - Variable transformations
  - `condition_expression` - For gateway decisions
  - `async_execution`, `retry_count`, `timeout_seconds` - Advanced options

### Tasks Remaining:
1. **Configuration UI in Camoonda**
   - Views already created (`process_topology_views.xml`)
   - Users can open process definition → Process Topology tab
   - Edit element execution configs directly
   
2. **OR: Configuration from BPMN Properties Panel** (Alternative)
   - Add "Execution" tab to BPMN properties panel (JavaScript)
   - When element selected, load its `process.element` config via RPC
   - Save changes back to Camoonda
   - This keeps configuration in BPMN editor (more intuitive)

**Decision Point:** Where should users configure execution?
- **Option A:** In Camoonda form views (already works)
- **Option B:** In BPMN properties panel (needs JavaScript work)
- **Recommendation:** Start with Option A (simpler), add Option B later

---

## Phase 2: Process Execution Engine (Core)

**Goal:** Execute process instances using configured elements and flows.

### Tasks:
1. **Execution Service** (`camoonda/services/execution_engine.py`)
   ```python
   class ExecutionEngine:
       def start_process(self, process_definition_id, variables=None, business_key=None):
           """
           Create process instance and token at start event
           Returns: process_instance record
           """
           
       def execute_token(self, token_id):
           """
           Execute current element for token, move to next element(s)
           Handles: service tasks, user tasks, scripts, gateways
           """
           
       def handle_gateway(self, token, gateway_element):
           """
           Evaluate gateway conditions, create/merge tokens
           - XOR: Single path (first matching condition)
           - AND: Split to all paths / merge from all paths
           - OR: Split to matching paths / merge when any arrives
           """
   ```

2. **Element Handlers** (`camoonda/services/element_handlers.py`)
   - Read `process.element` configuration
   - Execute based on `execution_type`:
   
   **Service Task:**
   ```python
   def execute_service_task(self, token, element):
       model = self.env[element.odoo_model]
       method = getattr(model, element.odoo_method)
       # Map process variables to method params
       params = self._apply_input_mapping(token.variables, element.input_mapping)
       result = method(**params)
       # Map result back to process variables
       self._apply_output_mapping(token.variables, result, element.output_mapping)
   ```
   
   **User Task:**
   ```python
   def execute_user_task(self, token, element):
       # Token goes to 'waiting' state
       # Create work item for assigned users/groups
       # Return action to open form
       return {
           'type': 'ir.actions.act_window',
           'res_model': element.odoo_model,
           'view_id': element.form_view_id.id,
           'context': {'token_id': token.id}
       }
   ```
   
   **Script Task:**
   ```python
   def execute_script_task(self, token, element):
       # Execute python code with context
       context = {
           'env': self.env,
           'variables': token.variables,
           'token': token,
           'instance': token.instance_id
       }
       exec(element.python_code, context)
       # Update variables from context
   ```

3. **Token Navigation**
   - Use `sequence.flow` records to find next elements
   - Evaluate `condition_expression` on flows
   - Handle multiple outgoing flows (gateways)
   - Create/merge tokens based on gateway type

4. **Incident Management**
   - Wrap execution in try/catch
   - Create `process.incident` on failures
   - Token goes to 'failed' state
   - Provide retry mechanism

**Deliverables:**
- Working execution engine
- Element handlers for all execution types
- Gateway logic (XOR, AND, OR)
- Error handling with incidents

---

## Phase 3: Simulation Mode (Testing & Debug)

**Goal:** Test processes without executing real operations.

### Tasks:
1. **Simulation Flag**
   - Add `simulation_mode` field to `camoonda.process.instance`
   - When true: skip actual execution, just move tokens
   - Gateways: can choose path manually or pick randomly

2. **BPMN Simulation Controls** (JavaScript)
   - Add toolbar in BPMN editor:
     - "▶ Start Simulation"
     - "⏭ Step Forward" 
     - "⏹ Stop"
   - Visual overlay showing token positions
   - Variables panel (editable during simulation)

3. **Token Position API**
   ```python
   @api.model
   def get_active_tokens(self, process_instance_id):
       tokens = self.env['camoonda.process.token'].search([
           ('instance_id', '=', process_instance_id),
           ('state', 'in', ['active', 'waiting'])
       ])
       return [{
           'element_id': t.current_element_id,
           'token_id': t.id,
           'state': t.state
       } for t in tokens]
   ```

4. **Visual Overlay** (BPMN JavaScript)
   - Use bpmn-js overlays API
   - Show animated token markers
   - Highlight active elements
   - Display execution history timeline

**Deliverables:**
- Simulation mode that doesn't execute real operations
- Visual token overlay in BPMN editor
- Step-through debugging capability

---

## Phase 4: Live Monitoring & Management

**Goal:** Monitor active process instances and manage execution.

### Tasks:
1. **Instance Management Views**
   - Enhanced `process_instance_views.xml`:
     - List view with filters (active, completed, failed)
     - Form view showing:
       - Current token positions
       - Process variables
       - Execution history
       - Incidents/errors
     - Actions: Suspend, Resume, Cancel, Retry

2. **BPMN Live Monitoring** (Optional)
   - Button in BPMN editor: "📊 Monitor Instances"
   - Side panel showing active instances for this process
   - Click instance → overlay its token positions on diagram
   - Real-time updates via long-polling or websocket

3. **Process Analytics**
   - Execution statistics per element
   - Average duration, success rate
   - Bottleneck detection
   - Heatmap overlay on BPMN diagram

**Deliverables:**
- Instance management interface
- Real-time monitoring (optional)
- Process analytics (optional)

---

## Revised Architecture: Camoonda-Centric Topology Storage

### Data Flow:
```
┌─────────────────────────────────────────────────┐
│  BPMN Module (Visual Designer)                 │
│  - Diagram editor (bpmn.js)                    │
│  - Stores BPMN XML                             │
│  - Deploy button                               │
│  - Links to Camoonda definition                │
└─────────────────┬───────────────────────────────┘
                  │ 
                  │ action_deploy_to_camoonda()
                  │ - Parse XML
                  │ - Extract elements & flows
                  │ - Create Camoonda records
                  │
                  ↓
┌─────────────────────────────────────────────────┐
│  Camoonda (Process Engine + Topology Storage)  │
│                                                 │
│  DESIGN-TIME:                                   │
│  - camoonda.process.definition                 │
│  - process.element (all tasks, events, etc)    │
│  - sequence.flow (all connections)             │
│                                                 │
│  RUNTIME:                                       │
│  - camoonda.process.instance                   │
│  - camoonda.process.token                      │
│  - camoonda.process.incident                   │
│  - camoonda.execution.history                  │
│                                                 │
│  EXECUTION:                                     │
│  - Read element config from process.element    │
│  - Navigate using sequence.flow                │
│  - Execute Odoo/Stoodio operations             │
│  - Track state in tokens & history             │
└─────────────────────────────────────────────────┘
```

### Database Structure:

**camoonda.process.definition**
- Stores: name, key, version, BPMN XML, description
- Links: bpmn_process_id (optional back-reference)
- Relations: element_ids, flow_ids, instance_ids

**process.element** (one per BPMN element)
- Stores: element_id, element_name, element_type
- Config: execution_type, odoo_model, odoo_method, python_code, etc.
- Relations: process_definition_id, incoming_flow_ids, outgoing_flow_ids

**sequence.flow** (one per BPMN connection)
- Stores: flow_id, flow_name, condition_expression
- Links: source_element_id, target_element_id
- Relations: process_definition_id

### Key Benefits:
1. **Complete Topology in Database** - No XML parsing at runtime
2. **Queryable Structure** - Can search elements by type, find paths, etc.
3. **Independent Execution** - Camoonda doesn't need BPMN module at runtime
4. **Version Control** - Each deployment creates new version
5. **Configuration Persistence** - Element configs survive diagram changes

### Deployment Process:
```python
def action_deploy_to_camoonda(self):
    # 1. Parse BPMN XML
    root = ET.fromstring(self.bpmn_xml)
    process_elem = root.find('.//bpmn:process', ns)
    
    # 2. Create process definition
    process_def = self.env['camoonda.process.definition'].create({
        'name': process_name,
        'key': process_key,
        'version': new_version,
        'bpmn_xml': self.bpmn_xml,
        'bpmn_process_id': self.id,
    })
    
    # 3. Extract and create elements
    for element_type, bpmn_tag in element_types:
        elements = process_elem.findall(f'.//bpmn:{bpmn_tag}', ns)
        for element in elements:
            self.env['process.element'].create({
                'process_definition_id': process_def.id,
                'element_id': element.get('id'),
                'element_name': element.get('name'),
                'element_type': element_type,
                'execution_type': default_exec_type,
            })
    
    # 4. Extract and create flows
    flows = process_elem.findall('.//bpmn:sequenceFlow', ns)
    for flow in flows:
        self.env['sequence.flow'].create({
            'process_definition_id': process_def.id,
            'flow_id': flow.get('id'),
            'source_element_id': element_map[flow.get('sourceRef')].id,
            'target_element_id': element_map[flow.get('targetRef')].id,
            'condition_expression': ...,
        })
```

---

## Implementation Status & Next Steps

### ✅ Completed:
1. **Topology Storage Architecture**
   - `process.element` model with full execution config
   - `sequence.flow` model for connections
   - Enhanced `camoonda.process.definition`
   - Deployment method in BPMN module
   - All views and security rules

2. **BPMN Deployment**
   - `action_deploy_to_camoonda()` working
   - XML parsing and element extraction
   - Flow extraction with conditions
   - Versioning support
   - UI integration (Deploy button in header)

### 🔨 In Progress:
- Module dependencies resolved
- Testing deployment with real BPMN diagrams

### 📋 Next Priorities:

**Immediate (Phase 1 completion):**
1. Configure element execution in Camoonda UI
   - Open process definition → Process Topology tab
   - Edit element execution types and parameters
   - Test different execution types
   
**Short Term (Phase 2):**
1. Build execution engine service
2. Implement element handlers
3. Token navigation using flows
4. Start/execute process instances

**Medium Term (Phase 3):**
1. Add simulation mode flag
2. Build BPMN editor simulation controls
3. Visual token overlay

**Long Term (Phase 4):**
1. Live monitoring
2. Process analytics
3. Advanced features

---

## Current Recommendation

**Start using the system:**
1. Deploy a simple BPMN diagram to Camoonda
2. Open the created process definition in Camoonda
3. Go to "Process Topology" tab
4. Configure element execution for each task:
   - Service tasks → set model/method
   - User tasks → set form view
   - Script tasks → add Python code
5. Test manual instance creation and execution

This will validate the architecture and identify any gaps before building the full execution engine.

---

## Technical Notes

### Dependencies:
- `camoonda` depends on: `base`, `mail`
- `bpmn` depends on: `base`, `web`, `stoodio`, `camoonda`
- Optional: `stoodio` for Stoodio module integration

### Model Naming Convention:
- Camoonda models use `camoonda.` prefix for main entities
- Topology models use short names: `process.element`, `sequence.flow`
- This makes them easier to reference while clearly separating concerns

### Avoiding Circular Dependencies:
- `bpmn_process_id` in process.definition is optional
- Field works if BPMN installed, but doesn't break if it's not
- Hidden from views to avoid reference errors
