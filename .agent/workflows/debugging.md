# Debugging Workflow - Pro-CMT

## Before Making Changes

1. **Test Current State First**
   - Run `./start.sh` and wait for both servers
   - Open http://localhost:5173 and verify it loads
   - Test the specific flow that's being modified

2. **Identify Scope**
   - Is it Frontend or Backend?
   - Which component/file?
   - What's the exact error message?

## When Fixing Bugs

1. **One Fix at a Time**
   - Make ONE change
   - Test immediately
   - Commit before next change

2. **Check Dependent Components**
   - If editing StepData.jsx → check StepProtocol.jsx and StepResults.jsx
   - If editing api.ts → check all components using that function
   - If editing backend endpoint → check frontend API call

3. **Null Check Checklist**
   - Always use optional chaining (`?.`) for nested objects
   - Always provide fallback values (`|| []`, `|| {}`)
   - Never assume API returns expected structure

## Test Sequence (Run After Every Change)

```bash
# 1. Backend health
curl http://localhost:8000/health

# 2. Datasets API
curl http://localhost:8000/api/v1/datasets | head -c 200

# 3. Frontend loads
# Open browser, check console for errors

# 4. Full flow test
# Dashboard → Upload → Wizard → Results
```

## Known Problem Patterns

| Symptom | Cause | Fix |
|---------|-------|-----|
| Blank page | Missing import or syntax error | Check browser console |
| `Cannot read property X of undefined` | API returns different structure | Add null checks |
| 500 error | Backend function missing or wrong params | Check uvicorn logs |
| Page loads but buttons don't work | Event handler error | Check browser console |

## Current Feature Status (Update After Testing)

- [ ] Dashboard loads
- [ ] Dataset list shows
- [ ] Upload works
- [ ] Wizard Step 1 (Goal selection)
- [ ] Wizard Step 2 (Data/Variables)
- [ ] Wizard Step 3 (Protocol)
- [ ] Wizard Step 4 (Results)
- [ ] Word export
- [ ] Batch mode
