import click
from loguru import logger
import sys
import time

from session_recorder.device import RemoteLogTailer
from session_recorder.store import DatabaseStorage
from session_recorder.receiver import UDPPacketReceiver

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
    
    db = DatabaseStorage()
    
    # Create the RemoteLogTailer instance
    log_tailer = RemoteLogTailer(
        host="localhost",
        user="root",
        password="password",
        log_file="output.log",
        db=db
    )
    
    
    udp_receiver = UDPPacketReceiver(host='127.0.0.1', port=51001, database = db)
    
    # Start the receiver in a separate thread
    udp_receiver.start()

    # Start the log tailing in a separ
    log_tailer.start_threads()

    # Simulating main program loop
    try:
        while True:
            logger.info("Recording session...")
            time.sleep(10)  # Main program continues with other tasks
    except KeyboardInterrupt:
        logger.info("Main thread interrupted. Exiting...")