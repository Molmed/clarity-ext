import requests_cache
import clarity_ext
import xml.etree.ElementTree as ET
import logging
import re


class ProcessService(object):
    """Provides access to information about processes and process types"""
    def __init__(self, logger=None, use_cache=False):
        self.logger = logger or logging.getLogger(__name__)
        if use_cache:
            cache_name = "process-types"
            requests_cache.configure(cache_name)

    def list_process_types(self, filter_contains_pattern):
        session = clarity_ext.ClaritySession.create(None)
        for process_type in session.api.get_process_types():
            process_type.get()
            if filter_contains_pattern is not None:
                xml_string = ET.tostring(process_type.root)
                if re.search(filter_contains_pattern, xml_string):
                    yield process_type
            else:
                yield process_type

    def list_processes_by_process_type(self, process_type):
        session = clarity_ext.ClaritySession.create(None)
        return session.api.get_processes(type=process_type.name)

    def ui_link_process(self, process):
        """
        Returns the UI link to the process rather than the API uri. The link will only be available if the
        process step is active
        """
        if not process.date_run:
            return "{}/clarity/work-details/{}".format(process.uri.split("/api")[0], process.id.split("-")[1])
        else:
            return None
