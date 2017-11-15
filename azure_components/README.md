# Azure_webapp Integration

## Overview

Get metrics from azure_components service in real time to:

* Visualize and monitor azure_components states
* Be notified about azure_components failovers and events.

## Installation

Install the `dd-check-azure_components` package manually or with your favorite configuration manager

## Configuration

Edit the `azure_components.yaml` file to point to your server and port, set the masters to monitor

## Validation

When you run `datadog-agent info` you should see something like the following:

    Checks
    ======

        azure_components
        -----------
          - instance #0 [OK]
          - Collected 39 metrics, 0 events & 7 service checks

## Compatibility

The azure_components check is compatible with all major platforms
