# worked-contrast.md — decomposition worked example (bad cut vs good cut)

Task: "add a CSV export option to an existing XLSX export feature."

**Bad cut** (by file): agent1 "edit the exporter module", agent2 "edit the
routes", agent3 "edit the frontend download button" — in parallel. No one
owns the CSV format decision; the three guess differently; integration fails.
**Good cut** (by outcome, sequential where dependent; each step names its executor):
1. ranger-pathfinder: "map the existing XLSX export path end-to-end (backend
   format layer → route → frontend trigger), return file:line chain"
2. gondor-builder: "add CSV alongside XLSX at these points: {file:line chain};
   acceptance: the app starts + a request to the convert endpoint with
   `format=csv` returns a valid CSV; existing XLSX tests still pass"
3. eagle-sentinel (model: sonnet): run the acceptance commands, per dispatch.md §5.
The frontend button, if needed, is step 2b AFTER the API shape from step 2
is fixed — it depends on the response contract.
