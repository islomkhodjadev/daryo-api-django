#!/bin/bash

# Define the list of services
services=(
    "gunicorn-daryo-api-1.service"
    "gunicorn-daryo-api-2.service"
    "gunicorn-daryo-api-3.service"
)

# Check if at least one argument is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 {start|stop|restart}"
    exit 1
fi

# Store the action (start, stop, restart)
action=$1

# Loop through each service and apply the action
for service in "${services[@]}"; do
    echo "Executing $action on $service..."
    systemctl $action "$service"
done

echo "All specified services have been processed."
