import click
from loguru import logger
import sys
import time

from session_recorder.device import RemoteLogTailer

@click.group()
@click.version_option()
def cli():
    "Record Vicon and Logs from a QA session"

@cli.command(name="record")
@click.argument(
    "session_name"
)
@click.option(
    "-t",
    "--target",
    help="target ssh device. Should be full user@host:port",
)
def record(session_name, target):
    "Begin recording a session"
    
    
    # Create the RemoteLogTailer instance
    log_tailer = RemoteLogTailer(
        host="localhost",
        user="root",
        password="password",
        log_file="output.log",
    )

    # Start the log tailing in a separate thread
    log_tailer.start_log_thread()

    # Simulating main program loop
    try:
        while True:
            logger.info("Recording session...")
            time.sleep(10)  # Main program continues with other tasks
    except KeyboardInterrupt:
        logger.info("Main thread interrupted. Exiting...")