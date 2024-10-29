import click
from loguru import logger
import time

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
    project = Project(session_name)

    db = DatabaseStorage(project)

    logger.add(project.logfile_path, rotation="100 MB", retention="10 days", level="DEBUG")

    host = "localhost"
    user = "root"
    port = 22
    log_path = logpath
    docker_container = docker_container
    log_tailer = None

    if target:
        host = target.split('@')[1].split(':')[0]
        user = target.split('@')[0]
        port = target.split(':')[1]


        # Create the RemoteLogTailer instance
        log_tailer = RemoteLogTailer(
            host=host,
            user=user,
            port=port,
            password="inno2018",
            log_file=log_path,
            docker_container=docker_container,
            db=db
        )

    # UDP Receiver Thread setup
    udp_receiver = UDPPacketReceiver(host='127.0.0.1', port=51001, database = db)

    # Start the receiver in a separate thread
    udp_receiver.start()

    if log_tailer:
        # Start the log tailing in a separate threads
        log_tailer.start_threads()
    else:
        logger.warning("No target device found (--target). Recording without logs...")

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
