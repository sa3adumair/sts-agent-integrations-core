# Azure_metrics Integration

## Overview

Get metrics from azure_metrics service in real time to:

* Visualize and monitor azure_metrics states
* Be notified about azure_metrics failovers and events.

## Installation

Install the `dd-check-azure_metrics` package manually or with your favorite configuration manager

## Configuration

Edit the `azure_metrics.yaml` file to point to your server and port, set the masters to monitor

## Validation

When you run `datadog-agent info` you should see something like the following:

    Checks
    ======

        azure_metrics
        -----------
          - instance #0 [OK]
          - Collected 39 metrics, 0 events & 7 service checks

## Compatibility

The azure_metrics check is compatible with all major platforms
