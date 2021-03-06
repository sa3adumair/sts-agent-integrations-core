from checks import AgentCheck, CheckException
from utils.ucmdb.ucmdb_file_dump import UcmdbDumpStructure, UcmdbFileDump
from utils.ucmdb.ucmdb_component_groups import UcmdbComponentGroups
from utils.ucmdb.ucmdb_component_trees import UcmdbComponentTrees
from utils.persistable_store import PersistableStore
from utils.timer import StsTimer


class UcmdbTopologyFileInstance(object):
    INSTANCE_TYPE = "ucmdb"
    PERSISTENCE_CHECK_NAME = "ucmdb_file"
    CONFIG_DEFAULTS = {
        "tag_attributes": [],
        "file_polling_interval": 0,
        "component_type_field": "name",
        "relation_type_field": "name",
        "excluded_types": [],
        "grouping_connected_components": False,
        "grouping_component_trees": False,
        "component_group": {},
        "label_min_group_size": 1,
        "tags": []}

    def __init__(self, instance):
        if 'location' not in instance:
            raise CheckException('topology instance missing "location" value.')

        self.location = instance["location"]
        self.attribute_tag_config = self._get_or_default(instance, "tag_attributes", self.CONFIG_DEFAULTS)
        self.polling_interval = self._get_or_default(instance, "file_polling_interval", self.CONFIG_DEFAULTS)
        self.component_type_field = self._get_or_default(instance, "component_type_field", self.CONFIG_DEFAULTS)
        self.relation_type_field = self._get_or_default(instance, "relation_type_field", self.CONFIG_DEFAULTS)
        self.excluded_types = set(self._get_or_default(instance, "excluded_types", self.CONFIG_DEFAULTS))
        self.grouping_connected_components = self._get_or_default(instance, "grouping_connected_components", self.CONFIG_DEFAULTS)
        self.grouping_component_trees = self._get_or_default(instance, "grouping_component_trees", self.CONFIG_DEFAULTS)
        self.component_group = self._get_or_default(instance, "component_group", self.CONFIG_DEFAULTS)
        self.label_min_group_size = self._get_or_default(instance, "label_min_group_size", self.CONFIG_DEFAULTS)
        self.tags = self._get_or_default(instance, 'tags', self.CONFIG_DEFAULTS)
        self.instance_key = {"type": self.INSTANCE_TYPE, "url":  self.location}

        self._persistable_store = PersistableStore(self.PERSISTENCE_CHECK_NAME, self.location)
        self.timer = StsTimer("last_poll_time", self.polling_interval)
        self.timer.load(self._persistable_store)
        self.dump_structure = UcmdbDumpStructure.load(self.location)
        self.previous_structure = self._persistable_store['ucmdb_dump_structure']

    def should_execute_check(self):
        return self.timer.expired() or (self.previous_structure is None or self.dump_structure.has_changes(self.previous_structure))

    def _get_or_default(self, instance, field_name, defaults):
        if field_name in instance:
            return instance.get(field_name)
        else:
            return defaults.get(field_name)

    def persist(self):
        self.timer.reset()
        self.timer.persist(self._persistable_store)
        self._persistable_store['ucmdb_dump_structure'] = self.dump_structure
        self._persistable_store.commit_status()


class UcmdbTopologyFile(AgentCheck):
    SERVICE_CHECK_NAME = "ucmdb_file"

    def check(self, instance):
        ucmdb_instance = UcmdbTopologyFileInstance(instance)

        if not ucmdb_instance.should_execute_check():
            self.log.debug("Skipping ucmdb file instance %s, waiting for changes and polling interval completion." % ucmdb_instance.location)
            return

        self.execute_check(ucmdb_instance)

        ucmdb_instance.persist()

    def execute_check(self, ucmdb_instance):
        self.start_snapshot(ucmdb_instance.instance_key)
        try:
            components, relations = self.load_and_label_groups(ucmdb_instance)
            self.add_components(ucmdb_instance, components)
            self.add_relations(ucmdb_instance, relations)
            self.stop_snapshot(ucmdb_instance.instance_key)
        except Exception as e:
            self._clear_topology(ucmdb_instance.instance_key, clear_in_snapshot=True)
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e))
            self.log.exception("Ucmdb Topology exception: %s" % str(e))
            raise CheckException("Cannot get topology from %s, please check your configuration. Message: %s" % (ucmdb_instance.location, str(e)))
        else:
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK)

    def load_and_label_groups(self, ucmdb_instance):
        dump = UcmdbFileDump(ucmdb_instance.dump_structure)
        dump.load(ucmdb_instance.excluded_types)
        components = dump.get_components()
        relations = dump.get_relations()

        if ucmdb_instance.grouping_connected_components:
            components, relations = self._label_connected_groups(components, relations, ucmdb_instance)

        if ucmdb_instance.grouping_component_trees:
            components, relations = self._label_trees(components, relations, ucmdb_instance)

        return (components.values(), relations.values())

    def _label_connected_groups(self, components, relations, ucmdb_instance):
        grouping = UcmdbComponentGroups(components, relations, ucmdb_instance.component_group, ucmdb_instance.label_min_group_size)
        grouping.label_groups()
        return (grouping.get_components(), grouping.get_relations())

    def _label_trees(self, components, relations, ucmdb_instance):
        trees = UcmdbComponentTrees(components, relations, ucmdb_instance.component_group)
        trees.label_trees()
        return (trees.get_components(), trees.get_relations())

    def add_components(self, ucmdb_instance, ucmdb_components):
        for ucmdb_component in ucmdb_components:
            if ucmdb_component['operation'] == 'add' or ucmdb_component['operation'] == 'update':
                data = ucmdb_component['data']
                tags_from_attributes = self.get_attribute_values(data, ucmdb_instance.attribute_tag_config)
                self.append_tags(data, tags_from_attributes)
                self.append_tags(data, ucmdb_instance.tags)
                component_type = self.get_type(ucmdb_instance.component_type_field, ucmdb_component)
                self.component(ucmdb_instance.instance_key, ucmdb_component['ucmdb_id'], {"name": component_type}, data)

    def add_relations(self, ucmdb_instance, ucmdb_relations):
        for ucmdb_relation in ucmdb_relations:
            if ucmdb_relation['operation'] == 'add' or ucmdb_relation['operation'] == 'update':
                data = ucmdb_relation['data']
                tags_from_attributes = self.get_attribute_values(data, ucmdb_instance.attribute_tag_config)
                self.append_tags(data, tags_from_attributes)
                self.append_tags(data, ucmdb_instance.tags)
                relation_type = self.get_type(ucmdb_instance.relation_type_field, ucmdb_relation)
                self.relation(ucmdb_instance.instance_key, ucmdb_relation['source_id'], ucmdb_relation['target_id'], {"name": relation_type}, data)

    def get_attribute_values(self, data, attribute_list):
        """ Retrieves the list of attribute values """
        attribute_values = []
        for attribute_name in attribute_list:
            if attribute_name in data:
                attribute_values.append(data[attribute_name])
        return attribute_values

    def get_type(self, type_field, ucmdb_element):
        if type_field in ucmdb_element:
            return ucmdb_element[type_field]
        elif type_field in ucmdb_element['data']:
            return ucmdb_element['data'][type_field]
        else:
            raise CheckException("Unable to resolve element type from ucmdb data %s" % (str(ucmdb_element)))

    def append_tags(self, data, tag_list):
        if 'tags' in data and tag_list:
            data['tags'] += tag_list
        elif tag_list:
            data['tags'] = tag_list
