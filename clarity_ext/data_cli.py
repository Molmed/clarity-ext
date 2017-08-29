from __future__ import print_function
import click
import logging
from clarity_ext.service import ProcessService
from clarity_ext import ClaritySession
from clarity_ext import utils
from clarity_ext.service.workflow_service import WorkflowService
import subprocess


@click.group()
@click.option("--level", default="INFO")
@click.option("--to-file/--no-to-file", default=True)
def main(level, to_file):
    """
    :param level: ["DEBUG", "INFO", "WARN", "ERROR"]
    :return:
    """
    log_level = level

    if not to_file:
        logging.basicConfig(level=log_level)
    else:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                            filename='adhoc.log',
                            filemode='a')

    # NOTE: The executed command is added to the log. Ensure sensitive data is filtered out if added
    # to any of the commands
    import sys
    logging.info("Executing: {}".format(sys.argv))
    results = subprocess.check_output(["pip", "freeze"])
    for result in results.splitlines():
        if "git+" in result:
            logging.info(result)

@main.command("list-process-types")
@click.option("--contains", help="Filter to process type containing this regex pattern anywhere in the XML")
@click.option("--list-procs", help="Lists procs: all|active")
@click.option("--ui-links", is_flag=True, help="Report ui links rather than api links")
def list_process_types(contains, list_procs, ui_links):
    """Lists all process types in the lims. Uses a cache file (process-type.sqlite)."""
    process_svc = ProcessService(use_cache=True)
    for process_type in process_svc.list_process_types(contains):
        click.echo("{name}: {uri}".format(name=process_type.name, uri=process_type.uri))

        if list_procs is not None:
            if list_procs not in ["all", "active"]:
                raise ValueError("Proc status not supported: {}".format(list_procs))
            for process in process_svc.list_processes_by_process_type(process_type):
                if list_procs == "active" and process.date_run is not None:
                    continue
                uri = process.uri if not ui_links else process_svc.ui_link_process(process)
                click.echo(u" - {}: date_run={}, technician={}".format(uri,
                           process.date_run, process.technician.name))


@main.command("workflow-info")
@click.argument("protocol")
@click.argument("status")
def workflow_info(protocol, status):
    """Finds workflows from protocol and step"""
    session = ClaritySession.create(None)
    workflow_service = WorkflowService(session)
    workflows = [workflow for workflow in workflow_service.get_workflows() if workflow.status == status]
    for workflow in workflows:
        for current_protocol in workflow.api_resource.protocols:
            if current_protocol.name == protocol:
                print(workflow.name, current_protocol.name)


@main.command("move-artifacts")
@click.argument("artifact-name")
@click.argument("unassign-stage-name")
@click.argument("assign-workflow-name")
@click.argument("assign-stage-name")
@click.option("--commit/--no-commit", default=False)
def move_artifacts(artifact_name, unassign_stage_name, assign_workflow_name, assign_stage_name, commit):
    """Moves all samples that are in a particular workflow from one workflow to another."""
    # TODO: Currently removes it from all stages it's currently in and assigns it to only one
    # TODO: This is a quick fix, so all the logic is currently in the CLI
    from clarity_ext.service.routing_service import RerouteInfo, RoutingService

    session = ClaritySession.create(None)
    logging.info("Searching for analytes of type '{}'".format(artifact_name))
    artifacts = session.api.get_artifacts(name=artifact_name, type="Analyte")

    # If there is only one artifact, that's the one we should unqueue, but we're always checking if it's staged
    # before:
    if len(artifacts) > 1:
        logging.info("Found more than one artifact")

    def get_artifacts_queued_for_stage():
        for artifact in artifacts:
            queued_stages = [stage for stage, status, name in artifact.workflow_stages_and_statuses
                             if status == "QUEUED" and name == unassign_stage_name]
            if len(queued_stages) > 0:
                yield artifact, queued_stages

    try:
        artifact, queued_stages = utils.single(get_artifacts_queued_for_stage())
    except ValueError:
        logging.error("Can't find a single artifact with name '{}' that's queued for stage with name '{}'".format(
            artifact_name, unassign_stage_name))

    if len(queued_stages) > 1:
        # The artifact is queued in several stages because of a bug that has been reported to Illumina
        logging.info("The artifact is queued in more than one stage. It will be unassigned from all of them.")

    assign_workflow = utils.single(session.api.get_workflows(name=assign_workflow_name))
    assign_stage = utils.single([stage for stage in assign_workflow.stages if stage.name == assign_stage_name])

    # Report for which artifacts to remove. This should be reviewed by an RE and then pushed back into this tool.
    reroute_info = RerouteInfo(artifact, queued_stages, [assign_stage])

    routing_service = RoutingService(session, commit=commit)

    # Log the details of the reroute info:
    # NOTE: This loads a lot of resources, but can be good to have.
    logging.info("About to reroute artifact {}, '{}'".format(artifact.id, artifact.name))

    def log_action(action, artifact, stage):
        logging.info("{} {} (workflow '{}', protocol '{}', step '{}')".format(
            action, artifact.id, stage.workflow.name, stage.protocol.name, stage.step.name))

    for assign in reroute_info.assign:
        log_action("Assign:", reroute_info.artifact, assign)

    for unassign in reroute_info.unassign:
        log_action("Unassign:", reroute_info.artifact, unassign)

    routing_service.route([reroute_info])


def reroute_info_to_csv(reroute_info):
    from clarity_ext.service.file_service import Csv
    csv = Csv()
    csv.set_header(["action", "artifact", "context", "info"])
    for context in reroute_info.unassign:
        info_msg = "Unassign artifact '{}' from {} '{}'".format(
            reroute_info.artifact.name, context.__class__.__name__, context.name)
        csv.append(["unassign", reroute_info.artifact.uri, context.uri, info_msg])
    return csv


if __name__ == "__main__":
    main()
