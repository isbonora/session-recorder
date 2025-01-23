import click
from loguru import logger
import time
import os
import sys

from session_recorder.device import RemoteLogTailer
from session_recorder.store import DatabaseStorage, Project
from session_recorder.receiver import UDPPacketReceiver
import json
import tabulate

logger.remove()

@click.group()
@click.version_option()
def cli():
    """Record Vicon and Logs from a QA session"""


@cli.command(name="record")
@click.argument("session_name")
@click.option(
    "-t",
    "--target",
    help="target ssh device. Should be full user@host:port",
)
@click.option(
    "-l",
    "--logpath",
    help="Which file on the host device to tail (exclusive with --docker-container)",
)
@click.option(
    "-c",
    "--docker-container",
    help="Which docker container to tail (exclusive with --logpath)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose logging (Debug level)",
)
def record(target, logpath=None, docker_container=None, session_name=None, verbose=False):
    """Begin recording a session"""
    
    project = Project()
    project.create(session_name, target, logpath, docker_container, is_temp=False)
    db = DatabaseStorage(project)

    # TODO: Move to a seperate function to setup logging
    log_level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stdout, colorize=True, format="<green>{time}</green> <level>{level} - {message}</level>", level=log_level)
    logger.add(
        project.session_cli_logs_path, rotation="100 MB", retention="10 days", level="DEBUG"
    )
    
    log_tailer = None

    # UDP Receiver Thread setup
    udp_receiver = UDPPacketReceiver(host="127.0.0.1", port=51001, database=db)

    # Start the receiver in a separate thread
    udp_receiver.start()

    if project.target_tail_type:
        # Create the RemoteLogTailer instance
        log_tailer = RemoteLogTailer(
            host=project.target_host,
            user=project.target_user,
            port=project.target_port,
            password=project.target_password,
            log_file=project.target_log_path,
            docker_container=project.target_docker_container,
            db=db,
        )
        # Start the log tailing in a separate threads
        log_tailer.start_threads()

    # Simulating main program loop
    # TODO: Put more information here. Maybe a status of the threads
    try:
        while True:
            time.sleep(1)
            continue
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt Received! Exiting...")
        db.close()
            
        sys.exit(0)
        


@cli.command(name="ls")
def list():
    """List all recorded sessions"""

    data_path = "data"

    try:
        sessions = os.listdir(data_path)
    except FileNotFoundError:
        logger.error("Data directory at '{data_path}' not found. Exiting...")
        sys.exit(0)

    if sessions:
        table = []
        for session in sessions:
            if session.startswith("."):
                continue
            try:
                with open(os.path.join(data_path, session, "project_data.json")) as f:
                    project_data = json.loads(f.read())

                    table.append(
                        [session, project_data["host"], project_data["tail_type"]]
                    )

            except NotADirectoryError:
                continue
            except FileNotFoundError:
                logger.debug(
                    f"Session '{session}' is missing project_data.json file. Skipping..."
                )
                continue
            except json.JSONDecodeError:
                logger.debug(
                    f"Session '{session}' project_data.json file is corrupted. Skipping..."
                )
                continue

        print(
            tabulate.tabulate(
                table, headers=["Session", "Target Host", "Tail Type"]
            )
        )
        print(f"Total Sessions: {len(table)}")

    else:
        print("No sessions recordings found in data directory.")


@cli.command(name="export")
@click.argument("session_name")
@click.option(
    "-o",
    "--output",
    help="Output file path. If not provided, will default to session_name.csv",
)
@click.option(
    "-e",
    "--events-only",
    is_flag=True,
)
def export(session_name, output=None, events_only=False):
	"""Export a session to a CSV file (DOESNT WORK YET)"""
 
	if not output:
		output = f"output_{session_name}.csv"

	if events_only:
		logger.info(f"Exporting events only for session '{session_name}' to '{output}'")

	session_path = os.path.join("data", session_name)
 
	if not os.path.exists(session_path):
		logger.error(f"Session '{session_name}' folder does not exist.")
		return

	# Load the SQL database
	
	db = DatabaseStorage(Project(session_name, None, None, None, is_temp=False))
    
	print(db.get_latest_frame_number())
    
	return None