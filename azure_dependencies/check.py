# stdlib
import logging
import requests
import json

# 3rd party

# project
from checks import AgentCheck

EVENT_TYPE = SOURCE_TYPE_NAME = 'azure_dependencies'

##
# /run.sh install && python embedded/dd-agent/agent.py check azure_dependencies
##

class AzureDependencies(AgentCheck):

    # Your Service Principal App ID
    CLIENT = '7042b714-72e0-4cf7-a0d3-c9d4c68dec05'

    log = logging.getLogger('%s.%s' % (__name__, "Azure-Components"))

    INSTANCE_TYPE = "Azure"
    instance_key = {
        'type': INSTANCE_TYPE,
        "url": CLIENT
    }

    def check(self, instance):

        application_id = '013c1735-8542-42fe-89a1-5095bc9f8a7e'
        api_key = 'w2k6g0i7vx8gvyd3filzrkc5ubmkjn1gdcbbd8t4'

        # storage queue
        for dependency in self.fetch_storage_queue_dependencies(application_id, api_key):
            self.process_storage_queue_dependency(dependency)

    def fetch_storage_queue_dependencies(self, application_id, api_key):
        """
        :param application_id: str application insights identifier
        :param api_key: str api key with read access to application insights' app_id
        :return: json
        """
        self.log.info("Fetching storage queue dependencies for application id {}.".format(application_id))

        # query timespan is one hour
        url = "https://api.applicationinsights.io/v1/apps/{}/events/dependencies?timespan=PT1H&$apply=filter(dependency%2Ftype%20eq%20'Azure%20queue')%2FgroupBy(cloud%2FroleName%2Ccloud%2FroleInstance%2Cdependency%2Fname)".format(application_id)
        headers = {'x-api-key': '{}'.format(api_key)}

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return json.loads(response.content)['value']

    def process_storage_queue_dependency(self, dependency):
        """
        process storage queue dependency json to stackstate relation, assuming the components exist.
        has; dependency/type eq 'Azure queue'
        :param dependency: json containing raw data from Azure
        :return: nothing
        """
        dependency_name = dependency['dependency']['name'] # dependency name has format <storage account>/<queue name> prefrixed with HTTP method
        if dependency_name.startswith('POST '):
            (storage_account, queue_name) = dependency_name[5:].split('/')  # strip off 'POST ' and extract storage account and queue name
            # cloud_rolename = dependency['cloud']['roleName']  # app service name
            cloud_roleinstance = dependency['cloud']['roleInstance']  # app service url
            self.relation(self.instance_key, cloud_roleinstance, 'storage.{}.queue.{}'.format(storage_account, queue_name), {'name': 'uses'})
        else:
            self.log.warning("Storage queue dependency processing failed on dependency.name with contents {}.".format(dependency_name))





