# GDPR Data Export API

In compliance with the General Data Protection Regulation (GDPR), the Open-Source Contribution Atelier allows users to request an export of all their personal data stored within the platform. 

## Export API Specification

The export API provides a single endpoint that aggregates personal data from multiple application modules (User Profile, Lesson Progress, Help Requests, Dashboard Issues, Notifications, Sandbox Logs, and Webhooks) into a standardized format.

**Endpoint:**  
`GET /api/users/me/export/?export_format=<format>`

**Authentication:**  
Requires a valid JWT access token. The API strictly filters data to ensure only information directly associated with the requesting user is exported.

### Supported Formats

1. **JSON (Default)**
   - **Parameter:** `?export_format=json`
   - **Response Type:** `application/json`
   - **Description:** Returns a structured JSON payload containing keys for each data entity (e.g., `user_profile`, `lesson_progress`, `assigned_issues`). Best for machine-readable integrations.

2. **CSV (Spreadsheet-friendly)**
   - **Parameter:** `?export_format=csv`
   - **Response Type:** `application/zip`
   - **Description:** Because a user's data spans multiple database tables, a CSV export returns a compressed `.zip` archive containing individual `.csv` files for each entity type (e.g., `user_profile.csv`, `lesson_progress.csv`).
   - **Streaming:** The archive is built and sent in chunks while rows are read in batches, so the response has no `Content-Length` and server memory does not grow with the number of rows. The JSON format is still built in memory.

### Example Request
```bash
curl -X GET "https://api.atelier.dev/api/users/me/export/?export_format=json" \
     -H "Authorization: Bearer <your_access_token>" \
     --output my_data.json
```

## GDPR & Privacy Considerations

- **Data Minimization:** Only fields defined on the models are included. Security credentials, such as hashed passwords, OTP tokens, and password reset tokens, are explicitly omitted from the export for security reasons.
- **Data Portability:** Providing both JSON and CSV options ensures the data is returned in a structured, commonly used, and machine-readable format.
- **Data Isolation:** The centralized export service uses strict Django ORM filtering (`user=self.user`) to guarantee that one user can never access or accidentally trigger an export containing another user's personal data.

## Guidelines for Extending

The export service uses a centralized architecture located in `apps/accounts/export.py` (`DataExportService`).

To incorporate additional data sources in the future:
1. Import the new model in `export.py`.
2. Add a new key to the dictionary returned by `_sources()` with the unevaluated QuerySet:
   ```python
   "new_module_data": NewModel.objects.filter(user=self.user)
   ```
3. The service will automatically handle the new model's fields, meaning JSON serialization and CSV `.zip` file generation will dynamically support the new dataset without further changes.
