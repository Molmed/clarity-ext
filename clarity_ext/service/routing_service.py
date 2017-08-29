import logging


class RoutingService(object):
    def __init__(self, session, commit=True):
        self.logger = logging.getLogger(__name__)
        self.session = session
        self.commit = commit

    @staticmethod
    def build_reroute_message(reroute_infos):
        request = list()
        request.append('<rt:routing xmlns:rt="http://genologics.com/ri/routing">')

        def uri_attribute(uri):
            return "stage-uri" if "/stages/" in uri else "workflow-uri"

        for reroute_info in reroute_infos:
            # let's build a routing message for the root artifact for
            # this sample:
            for assign in reroute_info.assign:
                request.append('<assign {}="{}">'.format(uri_attribute(assign.uri), assign.uri))
                request.append('  <artifact uri="' + reroute_info.artifact.uri + '"/>')
                request.append('</assign>')

            # TODO: clarity-ext should have stages as first class members of the artifact class
            for unassign in reroute_info.unassign:
                request.append('<unassign {}="{}">'.format(uri_attribute(unassign.uri), unassign.uri))
                request.append('  <artifact uri="' + reroute_info.artifact.uri + '"/>')
                request.append('</unassign>')

        request.append('</rt:routing>')
        return "\n".join(request)

    def route(self, reroute_infos):
        route_uri = self.session.api.get_uri("route", "artifacts")
        self.logger.info("Posting reroute message to {}".format(route_uri))
        reroute_request = self.build_reroute_message(reroute_infos)
        self.logger.info(reroute_request)
        if not self.commit:
            self.logger.info("Running with commit off. The message was not posted.")
        else:
            #response = self.session.api.post(route_uri, reroute_request)
            self.logger.info(response)


class RerouteInfo(object):
    """Defines a workflow stage to route to and from"""
    def __init__(self, artifact, unassign, assign):
        """
        :param artifact: The artifact to change
        :param unassign: Any number of workflows or stages to unassign, iterable or a single instance
        :param assign: Any number of workflows or stages to assign, iterable or a single instance
        """
        self.artifact = artifact
        self.assign = assign
        self.unassign = unassign

    def __repr__(self):
        return "{}: {} => {}".format(self.artifact.id, self.unassign, self.assign)

