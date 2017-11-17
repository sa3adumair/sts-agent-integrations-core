# stdlib
import logging
import time

# 3rd party

# project
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.resource import ResourceManagementClient
from checks import AgentCheck
from msrestazure.azure_active_directory import ServicePrincipalCredentials

EVENT_TYPE = SOURCE_TYPE_NAME = 'azure_alerts'

##
# /run.sh install && python embedded/dd-agent/agent.py check azure_alerts
##

class AzureAlerts(AgentCheck):
    # Tenant ID for your Azure Subscription
    TENANT_ID = '3d4d17ea-1ae4-4705-947e-51369c5a5f79'

    # Your Service Principal App ID
    CLIENT = '7042b714-72e0-4cf7-a0d3-c9d4c68dec05'

    # Your Service Principal Password
    KEY = '2euZsHeg8tTyN9F2'

    log = logging.getLogger('%s.%s' % (__name__, "Azure-Components"))

    INSTANCE_TYPE = "Azure"
    instance_key = {
        'type': INSTANCE_TYPE,
        "url": CLIENT
    }

    subscription_id = "adf99e3c-e0d1-44f6-87c4-decfc27f87ad"
    credentials = ServicePrincipalCredentials(
        client_id=CLIENT,
        secret=KEY,
        tenant=TENANT_ID
    )

    resource_client = ResourceManagementClient(credentials, subscription_id)
    monitor_client = MonitorManagementClient(credentials, subscription_id)

    def check(self, instance):
        for resource_group_name in self.list_resource_groups():
            self.log.info("Processing resource group: {}".format(resource_group_name))

            seen_resource_ids = set()  # keep track of resource ids that contain an alert rule
            incident_sent_on_resource_ids = set()  # keep track of resource ids that have a triggered alert rule / incident

            for alert_rule_resource in self.list_alert_rules(resource_group_name):
                self.log.info("Processing alert rule: {}".format(alert_rule_resource.name))

                alert_id = alert_rule_resource.id
                is_enabled = alert_rule_resource.is_enabled
                alert_rule_name = alert_rule_resource.name

                tags = alert_rule_resource.tags
                tags_hidden_link_list = filter(lambda (k, v): k.startswith('hidden-link:') and v == "Resource", tags.iteritems())  # fetch tags where key matched 'hidden-link:'
                referenced_azure_ids = map(lambda (k, v): k.lstrip("hidden-link:"), tags_hidden_link_list)  # strip off 'hidden-link' from tag key to get referenced azure resource id
                if len(referenced_azure_ids) != 1:  # expecting only one referenced azure resource id
                    self.log.warning("Found {} references to an Azure resource id for alert with id {}.".format(len(referenced_azure_ids), alert_id))
                    continue
                affected_resource_id = referenced_azure_ids[0]

                # mark affected resource id as seen
                seen_resource_ids.add(affected_resource_id)

                if not is_enabled:
                    # no need to process incidents for alerts that are not enabled.
                    continue

                for incident in self.list_alert_rule_incidents(resource_group_name, alert_rule_name):
                    if not incident.resolved_time:
                        # we are only interested in unresolved incidents at this point (clear state will be reported later on)
                        continue

                    incident_sent_on_resource_ids.add(affected_resource_id)
                    self.event({
                        # "timestamp": time.mktime(incident.activated_time.timetuple()),
                        "timestamp": time.time(),
                        "event_type": 'Azure Incident',
                        "msg_title": 'Alert rule {} triggered.'.format(alert_rule_name),
                        "msg_text": 'Incident reported on rule name {} affecting resource id {}. Activated: {}'.format(incident.rule_name, affected_resource_id, str(incident.activated_time)),
                        "alert_type": 'error',
                        "tags": ['rule_name:{}'.format(incident.rule_name), 'affected_resource_id:{}'.format(affected_resource_id), 'state:critical']
                    })

            # send clear state to seen resources excluding sources that have triggered alert rules / incidents
            for non_affected_resource_id in seen_resource_ids.difference(incident_sent_on_resource_ids):
                self.event({
                    "timestamp": time.time(),
                    "event_type": 'Azure Incident',
                    "msg_title": 'Alert rule {} not triggered.'.format(alert_rule_name),
                    "msg_text": 'No alerts triggered on {}.'.format(alert_id),
                    "alert_type": 'success',
                    "tags": ['affected_resource_id:{}'.format(non_affected_resource_id), 'state:clear']
                })

    def list_resource_groups(self):
        """
        get list of available resource groups
        :return: list of str, resource group names
        """
        resource_groups = self.resource_client.resource_groups.list()
        return map(lambda rg: rg.name, resource_groups)

    def list_alert_rules(self, resource_group_name):
        """
        get list of alert rules within the resource group
        :param resource_group_name: str
        :return: list of azure.mgmt.monitor.models.alert_rule_resource.AlertRuleResource
        """
        return self.monitor_client.alert_rules.list_by_resource_group(resource_group_name)

    def list_alert_rule_incidents(self, resource_group_name, alert_rule_name):
        """
        get list of incidents of the alert rule in the resource group
        :param resource_group_name: str
        :param alert_rule_name: str
        :return: list of azure.mgmt.monitor.models.incident.Incident
        """
        return self.monitor_client.alert_rule_incidents.list_by_alert_rule(resource_group_name, alert_rule_name)
