# Agent Ops - Agentic Onboarding System

An intelligent agentic system that automates user onboarding and access provisioning. The system uses a Planner Agent that orchestrates multiple specialized agents (AWS, GitHub, Confluence, Entra ID, Jenkins) to fulfill service requests through a Think → Act → Observe lifecycle.

## Overview

This system automates the entire user onboarding workflow, from email generation to access provisioning across multiple services. The Planner Agent coordinates specialized agents to complete tasks autonomously without human intervention.

## Architecture

### The Planner Agent Lifecycle: Think → Act → Observe

**THINK:**
The Planner LLM determines the next step to take based on the current task and context.

**ACT:**
Based on its decision, the Planner selects an appropriate tool (AWS, GitHub, Confluence, Entra ID agent, or Jenkins) and validates any required preconditions before execution.

**OBSERVE:**
The results returned by the selected tool are fed back into the LLM as updated context, enabling the Planner to make informed decisions for subsequent steps.

### Persistent Memory

The Planner learns from historical patterns, storing user progress and interaction data in a database. This enables the system to track onboarding status, access provisioning history, and user preferences over time.

### Long-Term Learning

Over time, long-term memory enables the system to recognize usage patterns and service-access behaviors based on user profiles. This learning capability allows the system to optimize access provisioning recommendations and predict common access requirements.

### Multi-Agent & Tool Ecosystem

Each agent operates autonomously, equipped with its own tools and specialized responsibilities:

- **EntraAgent**: Generates SSO-enabled company email addresses and creates users in Microsoft Entra ID
- **JenkinsAgent**: Triggers Jenkins pipelines for provisioning access to AWS, GitHub, Confluence, and Database services
- **GitHubAgent**: Performs read-only GitHub operations (PRs, commits, files)
- **AWSAgent**: Performs read-only AWS operations (S3, EC2)
- **JiraAgent**: Performs read-only JIRA operations (issues, search)

The Planner orchestrates these agents/tools to fulfill service requests. *(Future scope: individual agents may further evolve to evaluate or summarize service-permission requirements.)*

### No Human-in-the-Loop

The entire workflow is fully automated. The designated POC (Point of Contact) is only notified of the final user-access outcome via email notifications. The system handles:

1. User creation and email generation
2. Access provisioning across multiple services
3. Status tracking and updates
4. Automated notifications

## Features

- **Automated User Onboarding**: Creates users, generates company emails, and provisions access automatically
- **Agentic Flow**: Intelligent planning and execution of multi-step onboarding processes
- **Real-time Status Tracking**: Monitors access provisioning status and updates in real-time
- **Email Notifications**: Automated email notifications to stakeholders about onboarding progress
- **Persistent State**: All user data, access status, and agent reasoning are stored in a database
- **RESTful API**: Easy integration with existing systems via FastAPI endpoints

## Tech Stack

- Python 3.10+
- FastAPI + Uvicorn
- OpenAI API (or compatible LLM provider)
- SQLite (user management database)
- Microsoft Entra ID / Azure AD (SSO and email generation)
- Jenkins (access provisioning pipelines)
- SMTP/Email (notification system)

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Access to:
  - OpenAI API (or compatible LLM provider)
  - Microsoft Entra ID / Azure AD
  - Jenkins instance
  - SMTP server (for email notifications)

### Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd "Agent Ops"
```

2. **Create a virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root with the following variables:

```bash
# Required
APP_SECRET_KEY=your-random-secret-key-here

# LLM Provider (at least one required)
OPENAI_API_KEY=your-openai-api-key
# OR
CURSOR_API_KEY=your-cursor-api-key

# Microsoft Entra ID / Azure AD (for email generation)
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret

# Jenkins Configuration
AWS_REGION=us-east-2
JENKINS_SSM_PARAMETER=jenkins

# AWS (for SSM Parameter Store access)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_SESSION_TOKEN=your-aws-session-token  # Optional, for temporary credentials

# Email Notifications (for SMTP)
SMTP_PASSWORD=your-smtp-password  # Password for prakhar.srivastava@draup.com

# Optional - GitHub (read-only operations)
GITHUB_TOKEN=your-github-token

# Optional - JIRA (read-only operations)
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-jira-email
JIRA_API_TOKEN=your-jira-api-token

# Optional - Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

### Environment Variables Explained

- **APP_SECRET_KEY**: Random string for application security (required)
- **OPENAI_API_KEY** or **CURSOR_API_KEY**: API key for the LLM provider (at least one required)
- **TENANT_ID, CLIENT_ID, CLIENT_SECRET**: Microsoft Entra ID credentials for email generation (required)
- **AWS_REGION, JENKINS_SSM_PARAMETER**: AWS and Jenkins configuration (required)
- **AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY**: AWS credentials for accessing Jenkins credentials from SSM (required)
- **SMTP_PASSWORD**: Password for sending email notifications (required)
- **GITHUB_TOKEN**: Optional, for GitHub read-only operations
- **JIRA credentials**: Optional, for JIRA read-only operations

### Running the Project

1. **Activate the virtual environment** (if not already activated):
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Start the FastAPI server**:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **API Documentation (Swagger)**: http://localhost:8000/docs
- **Alternative Documentation (ReDoc)**: http://localhost:8000/redoc

### Running in Production

For production deployment, use a production ASGI server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use gunicorn with uvicorn workers:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API Endpoints

### POST /api/execute_task

Execute a task using the Planner Agent. The agent will plan, execute, and synthesize results.

**Request Body**:
```json
{
  "task": "Generate and save email for user with name John Doe",
  "context": {
    "name": "John Doe"
  }
}
```

### POST /api/users/onboard_user

Onboard a new user. This triggers the automated onboarding flow:

1. Creates user in database
2. After 5 seconds: Generates company email via Entra ID
3. After another 5 seconds: Provisions access via Jenkins (if access items are pending)

**Request Body**:
```json
{
  "name": "John Doe",
  "emailid": "",
  "contact_no": "+1234567890",
  "location": "Remote",
  "date_of_joining": "2024-01-15",
  "level": "L1",
  "team": "Engineering",
  "manager": "Jane Smith"
}
```

**Response**: Returns immediately (fire-and-forget). The onboarding flow runs asynchronously in the background.

### GET /api/users/status_all

Get all users and their current onboarding/access status.

### POST /api/users/update_status

Update user status and access items status.

### DELETE /api/users/delete_email_by_name

Delete a user's email by name (sets email to empty string).

### GET /api/agents

List all available agents and their capabilities.

## Agentic Onboarding Flow

When a user is onboarded via `/api/users/onboard_user`, the following automated flow is triggered:

1. **User Creation**: User record is created in the database
2. **Wait 5 seconds**: Allows time for database commit
3. **Email Generation**: EntraAgent generates a company email address and creates the user in Microsoft Entra ID
4. **Wait 5 seconds**: Allows time for email to be saved
5. **Access Provisioning**: JenkinsAgent provisions access for services that are:
   - Present in the user's `access_items_status` as "pending"
   - Among the supported services: AWS, GitHub, Confluence, Database
6. **Status Updates**: Access items status is updated to "completed" after successful provisioning
7. **Notifications**: Email notifications are sent to:
   - `suchanya.p@draup.com` when email is generated
   - `salman.b@draup.com` when Jenkins access is provisioned

## Database Schema

The system uses SQLite to store:
- User information (name, email, contact details, etc.)
- Access items status (tracking pending/completed access provisioning)
- AI live reasoning (one-liner updates about what agents are doing with timestamps)

## Logging

The application uses structured logging (structlog) that outputs JSON logs. Logs include:
- Request IDs for tracing
- Agent actions and responses
- Execution durations
- Errors and warnings
- User onboarding progress

Logs are written to `logs/app.log` by default.

## Error Handling

- Email generation failures are logged but don't stop the onboarding flow
- Jenkins trigger failures are logged and reported in the response
- Database errors are caught and logged with detailed error messages
- All errors are stored in structured logs for debugging

## Security Considerations

- All agent actions are validated against a whitelist
- User input is sanitized to prevent injection attacks
- Database connections are managed securely
- SMTP credentials are stored as environment variables
- Jenkins credentials are retrieved securely from AWS SSM Parameter Store

## Limitations

- Sequential execution: Plan steps are executed one at a time
- Single LLM: Uses a single planning LLM for both planning and synthesis
- Email notifications require SMTP password to be configured
- Access provisioning depends on Jenkins pipeline availability

## Future Enhancements

- Parallel execution of independent agent actions
- Agent self-evaluation and summarization capabilities
- Advanced pattern recognition for access requirements
- Support for additional service providers
- Webhook integrations for real-time updates

## License

This is a prototype/minimal implementation for learning agentic flows and automated onboarding systems.
