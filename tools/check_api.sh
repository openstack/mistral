#!/bin/bash

# How many seconds to wait for the API to be responding before giving up
API_RESPONDING_TIMEOUT=20

if ! timeout ${API_RESPONDING_TIMEOUT} sh -c "while ! curl -s http://127.0.0.1:8989/v1/ 2>/dev/null | grep -q 'Authentication required' ; do sleep 1; done"; then
     echo "Mistral API failed to respond within ${API_RESPONDING_TIMEOUT} seconds"
     exit 1
fi
