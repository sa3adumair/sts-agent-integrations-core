# (C) Datadog, Inc. 2010-2016
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)

# stdlib
import logging
import datetime

# 3rd party
from azure.monitor import MonitorClient
from azure.common.credentials import ServicePrincipalCredentials

# project
from checks import AgentCheck

EVENT_TYPE = SOURCE_TYPE_NAME = 'azure_metrics'

##
# /run.sh install && python embedded/dd-agent/agent.py check azure_metrics
##

class Azure_metricsCheck(AgentCheck):
    # Tenant ID for your Azure Subscription
    TENANT_ID = '3d4d17ea-1ae4-4705-947e-51369c5a5f79'

    # Your Service Principal App ID
    CLIENT = '7042b714-72e0-4cf7-a0d3-c9d4c68dec05'

    # Your Service Principal Password
    KEY = '2euZsHeg8tTyN9F2'

    log = logging.getLogger('%s.%s' % (__name__, "Azure-Components"))

    credentials = ServicePrincipalCredentials(
        client_id = CLIENT,
        secret = KEY,
        tenant = TENANT_ID
    )

    subscription_id = "adf99e3c-e0d1-44f6-87c4-decfc27f87ad"
    resource_group_name = "StackStateDemoWebApi"

    def check(self, instance):
        client = MonitorClient(
            self.credentials,
            self.subscription_id
        )

        webapp = "NuonCoreWebDemo20171109110132"
        webapp_provider = "Microsoft.Web/sites/{}".format(webapp)

        service_bus = "nuonpocsb"
        servicebus_provider = "Microsoft.ServiceBus/namespaces/{}".format(service_bus)

        resource_id = (
            "/subscriptions/{}"
            "/resourceGroups/{}"
            "/providers/{}"
        # ).format(self.subscription_id, self.resource_group_name, webapp_provider)
        ).format(self.subscription_id, self.resource_group_name, servicebus_provider)

        self.log.debug("Resource id: {}.".format(resource_id))

        # get the available metrics of this specific resource
        for metric in client.metric_definitions.list(resource_id):
            # # azure.monitor.models.MetricDefinition

            metric_name = metric.name.value
            end_time = datetime.datetime.utcnow()
            start_time = end_time - datetime.timedelta(hours=1)
            time_grain = "PT1H"  # 1 minute is minimal, PT1M

            # poor man's filter to limit intake
            if metric_name != "ConnectionsOpened":
                continue

            filter = " and ".join([
                "name.value eq '{}'".format(metric_name),
                "startTime eq {}".format(start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")),
                "endTime eq {}".format(end_time.strftime("%Y-%m-%dT%H:%M:%S.%f")),
                "timeGrain eq duration'{}'".format(time_grain)
            ])

            metrics_data = client.metrics.list(
                resource_id,
                filter=filter
            )

            for item in metrics_data:
                # azure.monitor.models.Metric
                for data in item.data:
                    metric = None
                    if data.count is not None:
                        metric = data.count
                    elif data.average is not None:
                        metric = data.average
                    elif data.minimum is not None:
                        metric = data.minimum
                    else:
                        metric = data.total

                    if metric is not None:
                        # TODO can't use the data's timestamp because it is pruned by the agent, more than a hour old?
                        # self.gauge(metric_name, data.total, hostname=webapp_provider, timestamp=data.time_stamp.strftime("%s"))
                        self.gauge(metric_name, metric, hostname=resource_id)
