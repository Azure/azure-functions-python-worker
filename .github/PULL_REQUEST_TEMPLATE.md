<!-- DO NOT DELETE THIS TEMPLATE -->

## Description

<!-- please list issues, if any -->
Fixes #

---
<!--
Please add an informative description that covers the changes made by the pull request. 
This checklist is used to make sure that common issues in a pull request are addressed.
This will expedite the process of getting your pull request merged and avoid extra work on your part to fix issues discovered during the review process.
-->

## Pull Request Checklist
<!--
Please fill out the following checklist to ensure compatibility across Python versions and programming models.
You can mark the following checkboxes as [x] to mark them during the PR creation itself.
-->
### Host-Worker Contract
- [ ] Does this PR impact the host-worker contract (e.g., gRPC messages, shared interfaces)?
   - If yes, have the changes been applied to:
      - [ ] azure_functions_worker (Python <= 3.12)
      - [ ] proxy_worker (Python >= 3.13)
   - If no, please explain why:   

### Worker Execution Logic
- [ ] Does this PR affect worker execution logic (e.g., function invocation, bindings, lifecycle)?
If yes, please answer the following:

**Python Version Coverage**
   - [ ] Does this change apply to both Python <=3.12 and 3.13+?
   - If yes, have the changes been made to:
      - [ ] azure_functions_worker (Python <= 3.12)
      - [ ] azure_functions_worker_v1 / azure_functions_worker_v2 (Python >= 3.13)
   - If no, please explain why:

**Programming Model Compatibility (for Python 3.13+)**
- Does this change apply to both:
   - [ ] V1 programming model (azure_functions_worker_v1)?
   - [ ] V2 programming model (azure_functions_worker_v2)?
- Explanation (if limited to one model):

<!-- Thanks for using the checklist -->
