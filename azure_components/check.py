# stdlib
import logging

# 3rd party
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient

# project
from azure.mgmt.servicebus import ServiceBusManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.storage import CloudStorageAccount
from azure_mgmt import RelayManagementClient
from azure_mgmt.models import Relaytype
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
    storage_client = StorageManagementClient(credentials, subscription_id)
    relay_client = RelayManagementClient(credentials, subscription_id)

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

            # service bus namespaces (resource type Microsoft.ServiceBus/namespaces)
            for service_bus_namespace in self.list_service_bus_namespaces(resource_group_name):
                self.process_service_bus_namespace(service_bus_namespace, resource_group_name)

                service_bus_namespace_name = service_bus_namespace.name

                # service bus queues
                for queue in self.list_service_bus_queues(resource_group_name, service_bus_namespace_name):
                    self.process_service_bus_queue(queue, resource_group_name, service_bus_namespace)

                # service bus topics
                for topic in self.list_service_bus_topics(resource_group_name, service_bus_namespace_name):
                    self.process_service_bus_topic(topic, resource_group_name, service_bus_namespace)

            # storage accounts (resource type Microsoft.Storage/storageAccounts)
            for storage_account in self.list_storage_accounts(resource_group_name):
                self.process_storage_account(storage_account, resource_group_name)

            # relay namespaces (resource type Microsoft.Relay/namespaces)
            for relay_namespace in self.list_relay_namespaces(resource_group_name):
                self.process_relay_namespace(relay_namespace, resource_group_name)

            # application insights information from resource management client
            for resource in self.resource_client.resources.list_by_resource_group(resource_group_name, filter="""resourceType eq 'microsoft.insights/components'"""):
                self.process_application_insights(resource, resource_group.name)

    def process_application_insights(self, resource, resource_group_name):
        """
        process generic component
        :param component_type: str
        :param resource: models.generic_resource.GenericResource
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing application insights {}".format(resource.name))
        self.log.debug("Application insights information: {}".format(resource))

        external_id = resource.id
        data = {
            'name': resource.name,
            'type': resource.type,
            'location': resource.location,
            'resource_group': resource_group_name,
            'tags': dict(filter(lambda (k, v): not k.startswith('hidden-link'), resource.tags.iteritems())) # hidden-link -> referenced azure resource
        }

        # component
        self.component(self.instance_key, external_id, {"name": 'application_insights'}, data)

        # relation: resource -> application insights
        tags = resource.tags
        tags_hidden_link_list = filter(lambda (k, v): k.startswith('hidden-link:') and v == "Resource", tags.iteritems())  # fetch tags where key matched 'hidden-link:' and value is 'Resource'
        referenced_azure_ids = map(lambda (k, v): k.lstrip("hidden-link:"), tags_hidden_link_list)  # strip off 'hidden-link' from tag key to get referenced azure resource id
        map(lambda referenced_azure_id: self.relation(self.instance_key, referenced_azure_id, external_id, {'name': 'uses_application_insights'}), referenced_azure_ids)


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

    def list_service_bus_namespaces(self, resource_group_name):
        """
        get list of service buses for the given resource group
        :param resource_group_name: str
        :return: list of azure.mgmt.servicebus.models.sb_namespace.SBNamespace
        """
        return self.service_bus_client.namespaces.list_by_resource_group(resource_group_name)

    def list_service_bus_queues(self, resource_group_name, namespace_name):
        """
        get list of queues in the service bus namespace of the resource group
        :param namespace_name: str
        :param resource_group_name: str
        :return: list of azure.mgmt.servicebus.models.sb_queue.SBQueue
        """
        return self.service_bus_client.queues.list_by_namespace(resource_group_name, namespace_name)

    def list_service_bus_topics(self, resource_group_name, namespace_name):
        """
        get list of topics in the service bus namespace of the resource group
        :param resource_group_name: str
        :param namespace_name: str
        :return: list of azure.mgmt.servicebus.models.sb_topic.SBTopic
        """
        return self.service_bus_client.topics.list_by_namespace(resource_group_name, namespace_name)

    def list_storage_accounts(self, resource_group_name):
        """
        get list of storage accounts in the resource group
        :param resource_group_name: str
        :return: list of azure.mgmt.storage.v2016_12_01.models.storage_account.StorageAccount'
        """
        return self.storage_client.storage_accounts.list_by_resource_group(resource_group_name)

    def list_relay_namespaces(self, resource_group_name):
        """
        get list of relays in the resource group
        :param resource_group_name:
        :return: list of azure_mgmt.models.relay_namespace.RelayNamespace
        """
        return self.relay_client.namespaces.list_by_resource_group(resource_group_name)

    def list_wcf_relays(self, relay_namespace_name, resource_group_name):
        """
        get list of wcf relays in the relay namespace in the resource group
        :param relay_namespace_name: str
        :param resource_group_name: str
        :return: list of azure_mgmt.models.wcf_relay.WcfRelay
        """
        return self.relay_client.wcf_relays.list_by_namespace(resource_group_name, relay_namespace_name)

    def list_hybrid_connections_relays(self, relay_namespace_name, resource_group_name):
        """
        get list of hybrid connection relays in the relay namespace in the resource group
        :param relay_namespace_name: str
        :param resource_group_name: str
        :return: list of azure.mgmt.relay.models.HybridConnection
        """
        return self.relay_client.hybrid_connections.list_by_namespace(resource_group_name, relay_namespace_name)

    def process_web_app(self, web_app, resource_group_name):
        """
        process web app / app service
        :param web_app: azure.mgmt.web.models.site.Site
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing web app {}".format(web_app.name))
        self.log.debug("Web app information: {}".format(web_app))

        external_id = web_app.id
        data = {
            'name': web_app.name,
            'type': web_app.type,
            'location': web_app.location,
            'resource_group': resource_group_name,
            'host_names': web_app.host_names,
            'tags': dict(filter(lambda (k, v): not k.startswith('hidden-related'), web_app.tags.iteritems())) # hidden-related -> serviceplan/farm
        }
        self.component(self.instance_key, external_id, {"name": "app"}, data)

    def process_application_gateway(self, application_gateway, resource_group_name):
        """
        process application gateway
        :param application_gateway: azure.mgmt.network.v2017_03_01.models.application_gateway.ApplicationGateway
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing application gateway {}".format(application_gateway.name))
        self.log.debug("Application gateway information: {}".format(application_gateway))

        external_id = application_gateway.id
        data = {
            'name': application_gateway.name,
            'type': application_gateway.type,
            'location': application_gateway.location,
            'resource_group': resource_group_name
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
                    # self.relation(self.instance_key, external_id, backend_address.ip_address, {"name": "appgateway_backend"})
                if backend_address.fqdn is not None:
                    data['backend_pool'].append({'fqdn': backend_address.fqdn})
                    # self.relation(self.instance_key, external_id, backend_address.fqdn, {"name": "appgateway_backend"})

        self.component(self.instance_key, external_id, {"name": "appgateway"}, data)

    def process_service_bus_namespace(self, service_bus_namespace, resource_group_name):
        """
        process service bus
        :param service_bus_namespace: azure.mgmt.servicebus.models.sb_namespace.SBNamespace
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing service bus namespace {}".format(service_bus_namespace.name))
        self.log.debug("Service bus namespace information: {}".format(service_bus_namespace))

        external_id = service_bus_namespace.id
        data = {
            'name': service_bus_namespace.name,
            'type': service_bus_namespace.type,
            'location': service_bus_namespace.location,
            'resource_group': resource_group_name,
            'service_bus_endpoint': service_bus_namespace.service_bus_endpoint,
            'metric_id': service_bus_namespace.metric_id
        }
        self.component(self.instance_key, external_id, {"name": "servicebus_namespace"}, data)

    def process_service_bus_queue(self, service_bus_queue, resource_group_name, service_bus_namespace):
        """
        process service bus queue
        :param service_bus_queue: azure.mgmt.servicebus.models.sb_queue.SBQueue
        :param resource_group_name: str
        :param service_bus_namespace: azure.mgmt.servicebus.models.sb_namespace.SBNamespace
        :return: nothing
        """
        self.log.info("Processing service bus queue {}".format(service_bus_queue.name))
        self.log.debug("Service bus queue information: {}".format(service_bus_queue))

        external_id = service_bus_queue.id
        data = {
            'name': service_bus_queue.name,
            'type': service_bus_queue.type,
            'service_bus_namespace': service_bus_namespace.name,
            'resource_group': resource_group_name,
            'message_count': service_bus_queue.message_count,
            'requires_duplicate_detection': service_bus_queue.requires_duplicate_detection,
            'enable_partitioning': service_bus_queue.enable_partitioning,
            'default_message_time_to_live': str(service_bus_queue.default_message_time_to_live),
            'max_size_in_megabytes': service_bus_queue.max_size_in_megabytes
        }
        # TODO maybe put contents of service_bus_queue.count_details to a metric stream
        self.component(self.instance_key, external_id, {"name": "servicebus_queue"}, data)
        self.relation(self.instance_key, service_bus_namespace.id, external_id, {'name': 'has_servicebus_queue'})

    def process_service_bus_topic(self, service_bus_topic, resource_group_name, service_bus_namespace):
        """
        process service bus topic
        :param service_bus_topic: azure.mgmt.servicebus.models.sb_topic.SBTopic
        :param resource_group_name:  str
        :param service_bus_namespace: azure.mgmt.servicebus.models.sb_namespace.SBNamespace
        :return: nothing
        """
        self.log.info("Processing service bus topic {}".format(service_bus_topic.name))
        self.log.debug("Service bus topic information: {}".format(service_bus_topic))

        external_id = service_bus_topic.id
        data = {
            'name': service_bus_topic.name,
            'type': service_bus_topic.type,
            'service_bus_namespace': service_bus_namespace.name,
            'resource_group': resource_group_name,
            'subscription_count': service_bus_topic.subscription_count,
            'max_size_in_megabytes': service_bus_topic.max_size_in_megabytes,
            'duplicate_detection_history_time_window': str(service_bus_topic.duplicate_detection_history_time_window),
            'requires_duplicate_detection': service_bus_topic.requires_duplicate_detection,
            'enable_batched_operations': service_bus_topic.enable_batched_operations,
            'default_message_time_to_live': str(service_bus_topic.default_message_time_to_live),
            'enable_partitioning': service_bus_topic.enable_partitioning,
            'auto_delete_on_idle': str(service_bus_topic.auto_delete_on_idle),
            'support_ordering': service_bus_topic.support_ordering,
        }
        # TODO maybe put contents of service_bus_topic.count_details to a metric stream
        self.component(self.instance_key, external_id, {"name": "servicebus_topic"}, data)
        # relation from topic to namespace
        self.relation(self.instance_key, service_bus_namespace.id, external_id, {'name': 'has_servicebus_topic'})

    def process_storage_account(self, storage_account, resource_group_name):
        """
        process storage account
        :param storage_account: azure.mgmt.storage.v2016_12_01.models.storage_account.StorageAccount
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing storage account {}".format(storage_account.name))
        self.log.debug("Storage account information: {}".format(storage_account))

        def process_storage_services(storage_account_resource_id, storage_account_name, primary_endpoints, secondary_endpoints):
            """
            process storage service specific information about table and queue service
            :param storage_account_resource_id: str
            :param primary_endpoints: azure.mgmt.storage.v2017_06_01.models.endpoints.Endpoints
            :param secondary_endpoints: azure.mgmt.storage.v2017_06_01.models.endpoints.Endpoints
            :param storage_account_name: str
            :return: nothing
            """
            # fetch keys that are known in the storage account
            storage_account_keys = self.storage_client.storage_accounts.list_keys(resource_group_name, storage_account_name).keys
            # list of azure.mgmt.storage.v2017_06_01.models.storage_account_key.StorageAccountKey

            # use first key, if any, to fetch information about specific storage services
            if not storage_account_keys:
                self.log.info("No storage account keys found to fetch list of storage services.")
            else:
                storage_account_key = storage_account_keys[0].value
                cloud_storage_account = CloudStorageAccount(storage_account_name, account_key=storage_account_key)

                # TODO add blob and table storage services

                # queues
                for queue in cloud_storage_account.create_queue_service().list_queues():
                    # azure.storage.queue.models.Queue
                    self.log.info("Processing queue storage service {}".format(queue.name))

                    external_id = queue.name
                    data = {
                        'name': queue.name,
                        'primary_endpoint': "{}{}".format(primary_endpoints.queue, queue.name),
                        'secondary_endpoint': "{}{}".format(secondary_endpoints.queue, queue.name),
                        'service_id': '{}/services/queue'.format(storage_account.id)
                    }
                    self.component(self.instance_key, external_id, {'name': 'storage_queue'}, data)
                    self.relation(self.instance_key, storage_account_resource_id, external_id, {'name': 'has_storage_queue'})

                # tables
                for table in cloud_storage_account.create_table_service().list_tables():
                    # azure.storage.table.models.Table
                    self.log.info("Processing table storage service {}".format(table.name))
                    external_id = table.name
                    data = {
                        'name': table.name,
                        'primary_endpoint': "{}{}".format(primary_endpoints.table, table.name),
                        'secondary_endpoint': "{}{}".format(secondary_endpoints.table, table.name),
                        'service_id': '{}/services/table'.format(storage_account.id)
                    }
                    self.component(self.instance_key, external_id, {'name': 'storage_table'}, data)
                    self.relation(self.instance_key, storage_account_resource_id, external_id, {'name': 'has_storage_table'})

        external_id = storage_account.id
        data = {
            'name': storage_account.name,
            'type': storage_account.type,
            'resource_group': resource_group_name,
            'primary_location': storage_account.primary_location,
            'secondary_location': storage_account.secondary_location,
            'primary_endpoints': {
                'queue': storage_account.primary_endpoints.queue,
                'table': storage_account.primary_endpoints.table,
                'blob': storage_account.primary_endpoints.blob,
                'file': storage_account.primary_endpoints.file
            },
            'secondary_endpoints': {
                'queue': storage_account.secondary_endpoints.queue,
                'table': storage_account.secondary_endpoints.table,
                'blob': storage_account.secondary_endpoints.blob,
                'file': storage_account.secondary_endpoints.file
            }
        }
        self.component(self.instance_key, external_id, {"name": "storage_account"}, data)

        # additional storage table and storage queue components
        process_storage_services(storage_account.id, storage_account.name, storage_account.primary_endpoints, storage_account.secondary_endpoints)

    def process_relay_namespace(self, relay_namespace, resource_group_name):
        """
        process relays in the namespace of the resource group
        :param relay_namespace: azure_mgmt.models.relay_namespace.RelayNamespace
        :param resource_group_name: str
        :return: nothing
        """
        self.log.info("Processing relay namespace {}".format(relay_namespace.name))
        self.log.debug("Relay namespace information: {}".format(relay_namespace))

        relay_namespace_name = relay_namespace.name
        relay_namespace_resource_id = relay_namespace.id

        for wcf_relay in self.list_wcf_relays(relay_namespace_name, resource_group_name):
            # azure_mgmt.models.wcf_relay.WcfRelay
            self.log.info("Processing WCF relay {}".format(wcf_relay.name))
            self.log.debug("WCF relay information: {}".format(wcf_relay))

            external_id = wcf_relay.id
            data = {
                'name': wcf_relay.name,
                'resource_group': resource_group_name,
                'namespace': relay_namespace_name,
                'relay_type': 'Http' if wcf_relay.relay_type == wcf_relay.relay_type == Relaytype.http else "NetTcp",
                'requires_client_authorization': wcf_relay.requires_client_authorization,
                'is_dynamic': wcf_relay.is_dynamic,
                'listener_count': wcf_relay.listener_count,
                'user_metadata': wcf_relay.user_metadata
            }
            self.component(self.instance_key, external_id, {"name": "relay_wcf"}, data)
            self.relation(self.instance_key, relay_namespace_resource_id, external_id, {"name": "has_relay"})

        for hybrid_connection_relay in self.list_hybrid_connections_relays(relay_namespace_name, resource_group_name):
            # azure_mgmt.models.hybrid_connection.HybridConnection
            self.log.info("Processing hybrid connection relay {}".format(hybrid_connection_relay.name))
            self.log.debug("hybrid connection relay information: {}".format(hybrid_connection_relay))

            external_id = hybrid_connection_relay.id
            data = {
                'name': hybrid_connection_relay.name,
                'resource_group': resource_group_name,
                'namespace': relay_namespace_name,
                'listener_count': hybrid_connection_relay.listener_count,
                'requires_client_authorization': hybrid_connection_relay.requires_client_authorization,
                'user_metadata': hybrid_connection_relay.user_metadata
            }
            self.component(self.instance_key, external_id, {"name": "relay_hybrid_connection"}, data)
            self.relation(self.instance_key, relay_namespace_resource_id, external_id, {"name": "has_relay"})

        external_id = relay_namespace_resource_id
        data = {
            'name': relay_namespace_name,
            'resource_group': resource_group_name,
            'tags': dict(filter(lambda (k, v): not k.startswith('hidden-related'), relay_namespace.tags.iteritems()))
        }
        self.component(self.instance_key, external_id, {'name': 'relay_namespace'}, data)
