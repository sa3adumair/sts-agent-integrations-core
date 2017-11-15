# stdlib
import logging

# 3rd party
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient

# project
from azure.mgmt.servicebus import ServiceBusManagementClient
from azure.mgmt.web import WebSiteManagementClient
from checks import AgentCheck

EVENT_TYPE = SOURCE_TYPE_NAME = 'azure'


##
# /run.sh install && python embedded/dd-agent/agent.py check azure_components
##

class AzureWebApp(AgentCheck):
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
    network_client = NetworkManagementClient(credentials, subscription_id)
    website_client = WebSiteManagementClient(credentials, subscription_id)
    service_bus_client = ServiceBusManagementClient(credentials, subscription_id)


    def check(self, instance):
        for resource_group in self.resource_client.resource_groups.list():
            self.log.info("Processing resource group: {}".format(resource_group.name))

            resource_group_name = resource_group.name

            # web app / app services (resource type Microsoft.Web/sites)
            for web_app in self.list_web_apps(resource_group_name):
                self.process_web_app(web_app, resource_group_name)

            # application gateway (resource type Microsoft.Network/applicationGateways)
            for application_gateway in self.list_application_gateways(resource_group_name):
                self.process_application_gateway(application_gateway, resource_group_name)

            # service bus (resource type Microsoft.ServiceBus/namespaces)
            for service_bus in self.list_service_buses(resource_group_name):
                self.process_service_bus(service_bus, resource_group_name)

            # other components, generic handling
            accepted_resource_types = """
            resourceType eq 'microsoft.insights/components'
            or resourceType eq 'Microsoft.Relay/namespaces'
            or resourceType eq 'Microsoft.Storage/storageAccounts'
            """
            for resource in self.resource_client.resources.list_by_resource_group(resource_group_name, filter=accepted_resource_types):
                self.process_generic_component(resource, resource_group.name)

    @staticmethod
    def map_component_type(resource_type):
        """
        map resource type from resource to stackstate component type
        :param resource_type: str resource type
        :return: str component_type or None when resource type was not matched
        """
        return {
            "microsoft.relay/namespaces": "relay",
            "microsoft.insights/components": "insights",
            "microsoft.storage/storageaccounts": "storage"
        }.get(resource_type.lower(), None)

    def process_generic_component(self, resource, resource_group_name):
        """
        process generic component
        :param component_type: str
        :param resource: models.generic_resource.GenericResource
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing generic component {} with type {}".format(resource.name, resource.type))
        self.log.debug("Generic component information: {}".format(resource))

        component_type = self.map_component_type(resource.type)
        if component_type is None:
            self.log.info("Skipping unhandled resource type, got: {}".format(resource.type))
            return

        id = resource.name

        data = {
            'type': resource.type,
            'location': resource.location,
            'id': resource.id,
            'resource_group': resource_group_name
        }
        component_type_obj = {
            "name": component_type
        }

        self.component(self.instance_key, id, component_type_obj, data)

    def list_web_apps(self, resource_group_name):
        """
        get list of web apps / app services for the given resource group
        :param resource_group_name: str
        :return: list of azure.mgmt.web.models.site.Site
        """
        return self.website_client.web_apps.list_by_resource_group(resource_group_name)

    def list_application_gateways(self, resource_group_name):
        """
        get list of application gateways for the given resource group
        :param resource_group_name: str
        :return: list of azure.mgmt.network.v2017_03_01.models.application_gateway.ApplicationGateway
        """
        return self.network_client.application_gateways.list(resource_group_name)

    def list_service_buses(self, resource_group_name):
        """
        get list of service buses for the given resource group
        :param resource_group_name: str
        :return: list of azure.mgmt.servicebus.models.sb_namespace.SBNamespace
        """
        return self.service_bus_client.namespaces.list_by_resource_group(resource_group_name)

    def process_web_app(self, web_app, resource_group_name):
        """
        process web app / app service
        :param web_app: azure.mgmt.web.models.site.Site
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing web app {}".format(web_app.name))
        self.log.debug("Web app information: {}".format(web_app))

        id = web_app.name

        data = {
            'type': web_app.type,
            'location': web_app.location,
            'id': web_app.id,
            'resource_group': resource_group_name,
            'host_names': web_app.host_names
        }
        component_type_obj = {
            "name": "app"
        }

        self.component(self.instance_key, id, component_type_obj, data)

    def process_application_gateway(self, application_gateway, resource_group_name):
        """
        process application gateway
        :param application_gateway: azure.mgmt.network.v2017_03_01.models.application_gateway.ApplicationGateway
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing application gateway {}".format(application_gateway.name))
        self.log.debug("Application gateway information: {}".format(application_gateway))

        id = application_gateway.name
        data = {
            'type': application_gateway.type,
            'location': application_gateway.location,
            'id': application_gateway.id,
            'resource_group': resource_group_name
        }
        component_type_obj = {
            "name": "appgateway"
        }

        # front end public ip
        public_ip = self.network_client.public_ip_addresses.get(resource_group_name, application_gateway.name)
        # azure.mgmt.network.v2017_03_01.models.public_ip_address.PublicIPAddress
        data.update({"front_end_ip": public_ip.ip_address})

        # back end address(es)
        data.update({'backend_pool': []})
        for backend_pool in application_gateway.backend_address_pools:
            # azure.mgmt.network.v2017_03_01.models.application_gateway_backend_address_pool.ApplicationGatewayBackendAddressPool
            for backend_address in backend_pool.backend_addresses:
                # azure.mgmt.network.v2017_03_01.models.application_gateway_backend_address.ApplicationGatewayBackendAddress'
                if backend_address.ip_address is not None:
                    data['backend_pool'].append({'ip_address': backend_address.ip_address})
                if backend_address.fqdn is not None:
                    data['backend_pool'].append({'fqdn': backend_address.fqdn})

        self.component(self.instance_key, id, component_type_obj, data)

    def process_service_bus(self, service_bus, resource_group_name):
        """
        process service bus
        :param service_bus: azure.mgmt.servicebus.models.sb_namespace.SBNamespace
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing service bus {}".format(service_bus.name))
        self.log.debug("Service bus information: {}".format(service_bus))

        external_id = service_bus.name
        data = {
            'type': service_bus.type,
            'location': service_bus.location,
            'id': service_bus.id,
            'resource_group': resource_group_name,
            'service_bus_endpoint': service_bus.service_bus_endpoint,
            'metric_id': service_bus.metric_id
        }
        component_type_obj = {
            "name": "servicebus"
        }

        self.component(self.instance_key, external_id, component_type_obj, data)