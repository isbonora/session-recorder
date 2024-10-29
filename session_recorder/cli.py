import click
from loguru import logger
import time
import os

from session_recorder.device import RemoteLogTailer
from session_recorder.store import DatabaseStorage, Project
from session_recorder.receiver import UDPPacketReceiver

@click.group()
@click.version_option()
def cli():
    """Record Vicon and Logs from a QA session"""

@cli.command(name="record")
@click.argument(
    "session_name"
)
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
def record(target, logpath=None, docker_container=None, session_name=None):
    """Begin recording a session"""

    # TODO: Finish linking up config file throughout
    project = Project(session_name, target, logpath, docker_container, is_temp=False)
    print(project)
    db = DatabaseStorage(project)


    logger.add(project.logfile_path, rotation="100 MB", retention="10 days", level="DEBUG")

    log_tailer = None

    # UDP Receiver Thread setup
    udp_receiver = UDPPacketReceiver(host='127.0.0.1', port=51001, database = db)

    # Start the receiver in a separate thread
    udp_receiver.start()

    if project.tail_type:

        # Create the RemoteLogTailer instance
        log_tailer = RemoteLogTailer(
            host=project.host,
            user=project.user,
            port=project.port,
            password=project.password,
            log_file=project.log_path,
            docker_container=project.docker_container,
            db=db
        )
        # Start the log tailing in a separate threads
        log_tailer.start_threads()

    # Simulating main program loop
    try:
        while True:
            # Print the status of log thread if it's running
            if log_tailer:
                logger.debug(f"Log Thread {log_tailer.log_thread.is_alive()}, Heartbeat Thread: {log_tailer.heartbeat_thread.is_alive()}")

            # Main program continues with other tasks
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Main thread interrupted. Exiting...")


@cli.command(name="ls")
def list():
    """List all recorded sessions"""

    data_path = "data"

    print(os.listdir(data_path))
