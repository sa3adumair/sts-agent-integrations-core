# Azure_alerts Integration

## Overview

Get metrics from azure_alerts service in real time to:

* Visualize and monitor azure_alerts states
* Be notified about azure_alerts failovers and events.

## Installation

Install the `dd-check-azure_alerts` package manually or with your favorite configuration manager

## Configuration

Edit the `azure_alerts.yaml` file to point to your server and port, set the masters to monitor

## Validation

When you run `datadog-agent info` you should see something like the following:

    Checks
    ======

        azure_alerts
        -----------
          - instance #0 [OK]
          - Collected 39 metrics, 0 events & 7 service checks

## Compatibility

The azure_alerts check is compatible with all major platforms
