#!/bin/bash
# Test curl command for execute_task endpoint

curl -X POST "http://localhost:8000/api/execute_task" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Onboard john.doe@example.com with AWS and GitHub access"
  }' | jq .
