# Quick Start: Testing Phase 2 Execution Engine

## Fastest Way to Test

### 1. Deploy a Simple Process

In BPMN module, create or open a diagram with:
- **Start Event**
- **Service Task** (name it "Create Partner")
- **End Event**

Click **"Deploy to Camoonda"**

---

### 2. Configure the Service Task

In Camoonda:
1. Open the deployed **Process Definition**
2. Go to **"Process Topology"** tab
3. Click on **"Create Partner"** task
4. Go to **"Execution"** tab
5. Configure:
   - **Execution Type**: Select **"Call Odoo Method"** (this is the service task)
   - **Odoo Model**: `res.partner`
   - **Method Name**: `create`
6. Go to **"Variables"** tab
7. Configure:
   - **Input Mapping**:
     ```json
     {
       "name": "Test from Process",
       "email": "process@test.com"
     }
     ```
   - **Output Mapping**:
     ```json
     {
       "partner_id": "${result.id}"
     }
     ```
8. **Save**

---

### 3. Start the Process

Still in Process Definition form:
1. Click **"Start Instance"** button (in header)
2. Optionally add business key: `TEST-001`
3. Process executes **automatically**

---

### 4. Verify Results

**Check the Partner:**
- Go to Contacts
- Look for "Test from Process"
- Should exist!

**Check the Instance:**
- Go back to Process Definition
- Click on "Instances" stat button
- Open your instance
- **State** should be "Completed"
- **Variables** should show `partner_id`

**Check Execution History:**
- In instance form, go to "Execution History" tab
- Should show:
  - element_started: Start Event
  - element_completed: Start Event
  - element_started: Create Partner
  - element_completed: Create Partner
  - element_started: End Event
  - element_completed: End Event

---

## Test 2: Script Task (5 minutes)

### Configure

Replace service task with script task:
1. Click on the task element
2. Go to **"Execution"** tab
3. **Execution Type**: Select **"Python Code"**
4. **Python Code**:
  ```python
  # Calculate something
  order_amount = 1000
  discount = 0.10
  final_amount = order_amount * (1 - discount)
  
  variables['order_amount'] = order_amount
  variables['discount'] = discount
  variables['final_amount'] = final_amount
  variables['message'] = f"Order: ${final_amount}"
  
  logger.info(f"Calculated: {variables['message']}")
  ```
5. **Save**

### Run

Click **"Start Instance"**

### Verify

Check instance variables:
- `order_amount`: 1000
- `discount`: 0.10
- `final_amount`: 900.0
- `message`: "Order: $900.0"

---

## Test 3: Gateway (10 minutes)

### Create BPMN

```
Start → XOR Gateway → [High] → Task A → End
                    → [Normal] → Task B → End
```

### Configure Gateway Flows

**High Priority Flow:**
- Condition Type: `Expression`
- Condition: `variables.get('priority') == 'high'`

**Normal Priority Flow:**
- Is Default: ✅ (checked)

### Start with Variable

Use Python shell:
```python
process_def = env['camoonda.process.definition'].search([('key', '=', 'your_key')], limit=1)

# Test high priority
instance1 = process_def.start_instance(
    variables={'priority': 'high'},
    business_key='TEST-HIGH'
)

# Test normal priority  
instance2 = process_def.start_instance(
    variables={'priority': 'normal'},
    business_key='TEST-NORMAL'
)
```

### Verify

- Instance 1: Should go through Task A
- Instance 2: Should go through Task B
- Check execution history to confirm path

---

## Programmatic Testing (Python Shell)

### Start Process
```python
# Get definition
pd = env['camoonda.process.definition'].search([('key', '=', 'test_process')], limit=1)

# Start instance
instance = pd.start_instance(
    variables={'customer': 'John', 'amount': 1500},
    business_key='ORDER-123'
)

# Check state
print(instance.state)  # 'completed' or 'active'
print(instance.variables)
```

### Monitor Execution
```python
# Get tokens
for token in instance.token_ids:
    print(f"{token.state} at {token.current_element_id.element_name}")

# Get history
for h in instance.execution_history_ids:
    print(f"{h.timestamp}: {h.event_type} - {h.details}")

# Check incidents
for inc in instance.incident_ids:
    print(f"Error: {inc.message}")
```

### Retry Failed Token
```python
failed_token = instance.token_ids.filtered(lambda t: t.state == 'failed')[0]
failed_token.action_retry()
```

---

## Common Issues

### "No start event found"
- Make sure your BPMN has a start event
- Re-deploy if you just added it

### "Method not found on model"
- Check model name is correct: `res.partner`, not `res_partner`
- Check method exists: `create`, not `Create`
- Check spelling
- Make sure you selected "Call Odoo Method" not just any execution type

### Token stuck at "waiting"
- This is normal for "Open Form" (user tasks)
- "Call Odoo Method" and "Python Code" tasks should complete automatically
- Check execution history for errors

### No partner created
- Check simulation_mode is False
- Check input mapping syntax (must be valid JSON)
- Look at incidents for errors
- Verify you selected "Call Odoo Method" execution type

---

## Debug Commands

### View Process Definition
```python
pd = env['camoonda.process.definition'].browse(DEFINITION_ID)
print(f"Elements: {len(pd.element_ids)}")
print(f"Flows: {len(pd.flow_ids)}")
```

### View Elements
```python
for elem in pd.element_ids:
    print(f"{elem.element_id}: {elem.element_type} - {elem.execution_type}")
```

### View Instance Details
```python
instance = env['camoonda.process.instance'].browse(INSTANCE_ID)
print(f"State: {instance.state}")
print(f"Variables: {instance.variables}")
print(f"Tokens: {instance.token_ids.mapped('state')}")
print(f"Incidents: {instance.incident_count}")
```

### Check Logs
```bash
kubectl -n odoo logs deployment/odoo --tail=100 | grep camoonda
```

---

## Success Checklist

- [ ] BPMN diagram deployed to Camoonda
- [ ] Service task configured with "Call Odoo Method" execution type
- [ ] Odoo Model and Method Name filled in
- [ ] Input/Output mapping configured in Variables tab
- [ ] Process started from UI button
- [ ] Instance reached "completed" state
- [ ] Expected side effect occurred (partner created, etc.)
- [ ] Execution history shows all steps
- [ ] Variables contain expected values
- [ ] No incidents created

---

## Next Steps

Once basic execution works:
1. ✅ Test with your real business processes
2. ✅ Configure multiple service tasks in sequence
3. ✅ Add script tasks for calculations
4. ✅ Test gateway conditions with variables
5. ✅ Test parallel execution (AND gateway)
6. ✅ Add error handling (try invalid config)
7. ✅ Test simulation mode

---

## Support

- **Full Testing Guide**: See `PHASE2_TESTING_GUIDE.md`
- **Implementation Details**: See `PHASE2_SUMMARY.md`
- **Architecture**: See `BPMN_INTEGRATION_PLAN.md`

Questions? Check:
1. Execution history in instance
2. Incidents for error messages
3. Odoo logs for detailed errors
4. Element configuration (execution type, model, method)
