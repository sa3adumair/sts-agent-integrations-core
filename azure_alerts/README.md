# Azure_alerts Integration

## Overview

Convert Azure incidents, triggered by alert rules, to StackState events.

## Configuration

Edit the `azure_alerts.yaml` file to point to your server and port, set the masters to monitor

## Validation

When you run `stackstate-agent info` you should see something like the following:

    Checks
    ======

        azure_alerts
        -----------
          - instance #0 [OK]
          - Collected 39 metrics, 0 events & 7 service checks
