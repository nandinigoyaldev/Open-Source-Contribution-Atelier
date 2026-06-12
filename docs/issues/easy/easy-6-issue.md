# Add API Unit Test for Accounts MeView Endpoint

- **Difficulty**: Easy
- **Category**: Testing
- **Beginner Friendliness**: Yes, great introduction to Django rest testing.

---

### Description
The current account information endpoint (/api/auth/me/) does not have dedicated unit tests verifying token authorization responses.

### Expected Outcome
A unit test confirming the endpoint returns 200 for validated users and 401 for anonymous hits.

### Acceptance Criteria
- [ ] Create a test case in backend/tests/test_auth_and_sandbox.py called test_me_endpoint.
- [ ] Assert correct JSON payload fields: id, username, email, is_staff.

### Files Likely Affected
- [backend/tests/test_auth_and_sandbox.py](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/backend/tests/test_auth_and_sandbox.py)
