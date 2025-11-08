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

## Phase 1: Element Execution Configuration ✅ COMPLETE

**Goal:** Configure how each element executes (Odoo methods, forms, scripts, etc.)

### Implementation Complete:
✅ **Models Created:**
- `process.element` model with all execution config fields:
  - `execution_type` - service, user_task, script, stoodio, auto, none
  - `odoo_model` / `odoo_method` - For service tasks
  - `form_view_id` / `form_mode` - For user tasks
  - `python_code` - For script tasks
  - `stoodio_module_id` - For Stoodio integration
  - `input_mapping` / `output_mapping` - Variable transformations
  - `condition_expression` - For gateway decisions
  - `async_execution`, `retry_count`, `timeout_seconds` - Advanced options

✅ **Configuration UI:**
- Views created in `process_topology_views.xml`:
  - Form view with notebook tabs: Execution, Variables, Flows, Advanced
  - List view showing configuration status
  - Inline editing for quick config changes
- Integrated into Process Definition form:
  - "Process Topology" tab shows elements and flows
  - Click any element to open full configuration form
  - Visual indicators for configured vs unconfigured elements

✅ **Deployment Integration:**
- Elements automatically created during BPMN deployment
- Default execution types assigned based on BPMN element type
- Ready for manual configuration after deployment

### How to Use:
1. Deploy BPMN diagram to Camoonda (button in BPMN form header)
2. Open created Process Definition in Camoonda
3. Navigate to "Process Topology" tab
4. Click on any element to configure execution:
   - **Service Task:** Set odoo_model='res.partner', odoo_method='create'
   - **User Task:** Choose form view, assign users/groups
   - **Script Task:** Write Python code with access to variables
   - **Stoodio:** Link to Stoodio module for visual workflow
5. Configure input/output mapping for variable flow
6. Save and proceed to execution

### Future Enhancement (Optional):
- Add configuration panel to BPMN properties panel (JavaScript)
- Allow inline config editing while designing diagram
- Currently: Configure after deployment in Camoonda UI

---

## Phase 2: Process Execution Engine ✅ COMPLETE

**Goal:** Execute process instances using configured elements and flows.

### Implementation Complete:

✅ **Execution Service** (`camoonda/services/execution_engine.py` - 570 lines)
- `start_process()` - Creates instance, finds start event, creates initial token, begins execution
- `execute_token()` - Main execution loop with element handling and navigation
- `_navigate_to_next()` - Moves tokens through sequence flows
- Gateway logic for XOR, AND, OR (split and merge)
- Condition evaluation with variable context
- Error handling with automatic incident creation
- Execution history logging

✅ **Element Handlers** (`camoonda/services/element_handlers.py` - 370 lines)
- **Service Task Handler**: Calls Odoo model methods
  - Applies input mapping (variables → parameters)
  - Executes method with error handling
  - Applies output mapping (result → variables)
- **User Task Handler**: Creates work items and returns form actions
  - Opens form for user interaction
  - Token enters "waiting" state
- **Script Task Handler**: Executes Python code
  - Full context: env, variables, token, instance, logger
  - Updates variables from executed code
- **Stoodio Handler**: Integrates with Stoodio modules
- **Auto Handler**: Auto-detects execution type from configuration
- Simulation mode support (skips real operations)

✅ **Model Integration**
- `process.definition.start_instance()` - Programmatic process start
- `process.definition.action_start_instance()` - UI action with button
- `process.token.execute()` - Execute token at current position
- `process.token.action_retry()` - Retry failed tokens
- Updated token model with `current_element_id` (Many2one to process.element)
- Added `simulation_mode` to process instances

✅ **Gateway Support**
- **Exclusive Gateway (XOR)**:
  - Evaluates conditions in sequence order
  - Takes first matching path or default path
  - Single token continues
- **Parallel Gateway (AND)**:
  - Split: Creates token for each outgoing flow
  - Merge: Waits for all incoming tokens, continues with one
- **Inclusive Gateway (OR)**:
  - Evaluates all conditions
  - Takes all matching paths
  - Creates tokens for each matching flow

✅ **Variable System**
- Process variables (instance.variables)
- Token variables (token.variables)
- Input mapping: `${variable_name}` → method parameters
- Output mapping: `${result.field}` → process variables
- Variables available in conditions and scripts

✅ **Error Management**
- Try/catch around all execution
- Automatic incident creation on failures
- Token state changes to 'failed'
- Execution history records errors
- Retry mechanism for failed tokens

### How to Use:

**UI Method:**
1. Open Process Definition in Camoonda
2. Click "Start Instance" button in header
3. Process executes automatically from start to end

**Programmatic Method:**
```python
process_def = env['camoonda.process.definition'].search([
    ('key', '=', 'order_process')
], limit=1)

instance = process_def.start_instance(
    variables={
        'customer_name': 'John Doe',
        'order_amount': 1500
    },
    business_key='ORDER-12345',
    simulation_mode=False
)
```

### Testing:

See **`PHASE2_TESTING_GUIDE.md`** for comprehensive testing instructions including:
- Linear process with service task
- Script task with variables
- XOR gateway with conditions
- AND gateway with parallel execution
- User task (waiting state)
- Error handling and incidents
- Simulation mode

### Supported BPMN Elements:

**Events:**
- ✅ Start Event (pass through)
- ✅ End Event (complete token and instance)

**Tasks:**
- ✅ Service Task (call Odoo methods)
- ✅ User Task (create work items)
- ✅ Script Task (execute Python)
- ✅ Manual Task (pass through)

**Gateways:**
- ✅ Exclusive Gateway (XOR - one path)
- ✅ Parallel Gateway (AND - all paths)
- ✅ Inclusive Gateway (OR - matching paths)

**Flows:**
- ✅ Sequence Flow (with conditions)
- ✅ Conditional expressions (Python)
- ✅ Default flows

### Architecture:

```
start_process()
    ↓
create instance + initial token
    ↓
execute_token() [recursive loop]
    ↓
├─ get current element
├─ execute element (call handler)
├─ update variables
├─ log history
├─ evaluate conditions on flows
├─ handle gateway (split/merge)
└─ navigate to next element(s)
    ↓
    [repeat until end event]
    ↓
complete instance
```

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

**Foundation: Topology Storage Architecture**
- `process.element` model with full execution config
- `sequence.flow` model for connections
- Enhanced `camoonda.process.definition`
- Deployment method in BPMN module
- All views and security rules

**Phase 0: BPMN Deployment** ✅
- `action_deploy_to_camoonda()` working
- XML parsing and element extraction
- Flow extraction with conditions
- Versioning support
- UI integration (Deploy button in header)
- Successfully tested with real BPMN diagrams

**Phase 1: Element Execution Configuration** ✅
- Configuration UI in Camoonda (form views with tabs)
- Process Topology tab in Process Definition
- All execution types supported (service, user_task, script, stoodio)
- Input/output mapping for variables
- Advanced options (async, retry, timeout)
- Ready for production use

**Phase 2: Process Execution Engine** ✅
- Execution service with start_process() and execute_token()
- Element handlers for all task types
- Gateway logic (XOR, AND, OR) with splitting/merging
- Token navigation through sequence flows
- Condition evaluation with variables
- Error handling with incidents
- Execution history logging
- Simulation mode
- Variable input/output mapping
- **See PHASE2_SUMMARY.md and PHASE2_TESTING_GUIDE.md for details**

### 📋 Next Priorities:

**🎮 Phase 3: Simulation Mode & Debugging (NEXT)**
Priority: MEDIUM - Helpful for testing

1. **Visual Token Overlay** (BPMN JavaScript)
   - Add toolbar in BPMN editor: ▶ Start Simulation, ⏭ Step, ⏹ Stop
   - Overlay showing current token positions on diagram
   - Highlight active elements
   - Variables panel showing current state

2. **Step-through Debugging**
   - Execute one element at a time
   - Inspect variables at each step
   - Manual gateway path selection
   - Reset to start

3. **Simulation Controls API**
   ```python
   @api.model
   def get_active_tokens(self, instance_id):
       # Return token positions for visual overlay
   
   @api.model
   def step_token(self, token_id):
       # Execute one step and pause
   ```

**📊 Phase 4: Live Monitoring & Management**
Priority: LOW - Nice to have

1. **Instance Management**
   - Enhanced instance views with token visualization
   - Actions: Suspend, Resume, Cancel, Retry
   - Bulk operations on instances

2. **Process Analytics** (Optional)
   - Execution statistics per element
   - Average duration, success rate
   - Bottleneck detection
   - Heatmap overlay on BPMN

3. **Real-time Monitoring** (Optional)
   - Live token position updates
   - WebSocket or long-polling
   - Multiple instance monitoring

**🚀 Additional Features** (Future)
- Message events (send/receive, correlation)
- Timer events (duration, date)
- Subprocess support (call activities, embedded)
- Error boundary events
- Compensation handlers
- Multi-instance tasks (parallel/sequential)
- User task claiming and assignment
- Task list view for users

---

## Current Status

**✅ Phase 2 Complete - Fully Functional Execution Engine**

You can now:
1. ✅ Deploy BPMN diagrams to Camoonda
2. ✅ Configure element execution (service, user, script tasks)
3. ✅ Start process instances (UI or programmatic)
4. ✅ Execute processes automatically through completion
5. ✅ Handle gateways (XOR, AND, OR)
6. ✅ Use variables with input/output mapping
7. ✅ Handle errors with incidents
8. ✅ View execution history
9. ✅ Retry failed tokens
10. ✅ Run in simulation mode

**Next Recommended Step:**

**Option A: Test Current Implementation**
- Deploy and configure real processes
- Test different execution scenarios
- Validate with business use cases
- Gather feedback on functionality

**Option B: Add Visual Simulation (Phase 3)**
- Build BPMN editor controls
- Add token visualization overlay
- Implement step-through debugging
- Makes testing easier and more intuitive

**Option C: Production Hardening**
- Add user task completion mechanism
- Enhance error messages
- Add performance optimizations
- Build monitoring dashboard

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
