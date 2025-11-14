
db-sqllite DB

user table

| Column              | Type                     | Notes                                     |
| ------------------- | ------------------------ | ----------------------------------------- |
| id                  | INTEGER PK AUTOINCREMENT | Unique row ID                             |
| name                | TEXT                     |                                           |
| emailid             | TEXT                     | Unique constraint recommended             |
| contact_no          | TEXT                     |                                           |
| location            | TEXT                     |                                           |
| date_of_joining     | TEXT                     | ISO date string                           |
| level               | TEXT                     |                                           |
| team                | TEXT                     |                                           |
| manager             | TEXT                     |                                           |
| status              | TEXT                     | Values: `new`, `in_progress`, `completed` |
| access_items_status | TEXT (JSON)              | Stored as JSON array of objects           |

access_items_status table sample - 
[
  {"item": "aws", "status": "pending", "timestamp": null},
  {"item": "github", "status": "completed", "timestamp": 1731569228000}
]


poc_config table

| Column       | Type                         | Notes                         |
| ------------ | ---------------------------- | ----------------------------- |
| id           | INTEGER PK AUTOINCREMENT     |                               |
| role         | TEXT                         |                               |
| team         | TEXT                         |                               |
| access_item  | TEXT                         |                               |
| poc_id       | TEXT                         | Email or unique POC reference |

sample data - 
sde	backend	aws	abc@d.com
sde	backend github	xyz@d.com

POST /onboard_user/

Payload-
{
  "name": "",
  "emailid": "",
  "contact_no": "",
  "location": "",
  "date_of_joining": "",
  "level": "",
  "team": "",
  "manager": ""
}

Backend logic

Fetch all entries from poc_config where team = payload.team.
Extract all access_items.

Build access_items_status with default values:
[
  {"item": "<item_name>", "status": "pending", "timestamp": null}
]
Insert new row in users with:

status = new
access_items_status = JSON array


GET /status_all/
Return all users and their current status.

response:
[
  {
    "id": 1,
    "name": "",
    "emailid": "",
    "contact_no": "",
    "location": "",
    "date_of_joining": "",
    "level": "",
    "team": "",
    "manager": "",
    "status": "new",
    "access_items_status": [
      {"item": "aws", "status": "pending", "timestamp": null},
      {"item": "github", "status": "completed", "timestamp": 1731570000000}
    ]
  }
]


POST /add_poc_config/
 payload - 
[
  {
    "role": "sde",
    "team": "backend",
    "access_items": ["aws"],
    "poc_id": "abc@d.com"
  },
  {
    "role": "sde",
    "team": "backend",
    "access_items": ["github"],
    "poc_id": "xyz@d.com"
  }
]

logic-
Insert all received entries into poc_config.



notes- 
dont add strict validation. 
i want this only for demo purpose
