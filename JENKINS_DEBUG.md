# Jenkins Debugging - Direct API vs Agent Call

## Issue
- **Direct API call** (`/api/jenkins/trigger`) ✅ **WORKS**
- **Agent call** (`/api/execute_task`) ❌ **FAILS** with 500 error

## Root Cause Analysis

Both paths use the same `JenkinsService.trigger_jenkins_job()` method, so they should behave identically.

### Key Findings:
1. **Direct API route** creates a NEW `JenkinsService` instance each time via dependency injection
2. **Agent path** uses a CACHED `JenkinsService` instance (created once and cached with the agent)
3. The CSRF token fetch happens on each call (not at initialization), so caching shouldn't matter
4. Both paths call the exact same method with the same parameters

### The Problem:
The Jenkins 500 error with HTML login page suggests:
- **Missing CSRF token** in the request headers
- OR **Invalid/malformed CSRF token**
- OR **Authentication issue**

### Why Direct Call Works But Agent Call Fails:
The most likely explanation is that **the server hasn't reloaded the CSRF fix code** when the agent was cached. The direct API route creates a fresh service instance, so it uses the new code, but the cached agent still has the old service instance.

## Solution

**Restart the FastAPI server** to clear the cached agents and ensure all code paths use the latest CSRF token handling.

## Verification

After restart, check logs for:
- `fetching_csrf_token` - confirms CSRF fetch is attempted
- `csrf_fetch_complete` - confirms CSRF fetch completed
- `csrf_crumb_fetched` - confirms CSRF token was obtained
- `jenkins_request_details` with `has_csrf_header: true` - confirms CSRF header is included
- `jenkins_response_check` - shows the response status

If these logs appear and `has_csrf_header` is `true`, but the request still fails, then the issue is elsewhere (e.g., parameter formatting, authentication, etc.).
