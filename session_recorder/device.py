import threading
import time
from fabric import Connection
from loguru import logger
from invoke.exceptions import UnexpectedExit
from paramiko.ssh_exception import SSHException

import re

class RemoteLogTailer:
    """
    This class handles connecting to a remote server via SSH, tailing a log file, 
    and saving the logs to an SQLite database. It includes retry logic for robust
    connections and runs the tailing operation in a separate thread.
    """
    
    def __init__(self, host, user, password, log_file, max_retries=5, keepalive_interval=30):
        """
        Initializes the RemoteLogTailer class.
        
        Args:
            host (str): The remote server hostname or IP.
            user (str): The SSH user.
            password (str): Path to the SSH private key.
            log_file (str): Path to the log file on the remote server.
            db_name (str): SQLite database file name.
            max_retries (int): Number of retry attempts for SSH connection.
            keepalive_interval (int): Interval in seconds for SSH keepalive messages.
        """
        self.host = host
        self.user = user
        self.password = password
        self.log_file = log_file
        self.max_retries = max_retries
        self.keepalive_interval = keepalive_interval
        self.backoff_time = 5  # Initial backoff time for retries
        self.log_thread = None


    def run_tail_f_logs(self):
        """
        Connects to the remote server and starts tailing the specified log file.
        If the connection fails, it retries using exponential backoff.
        """
        retries = 0

        while retries < self.max_retries:
            try:
                logger.info(f"Attempting connection to {self.host}. Attempt {retries + 1}/{self.max_retries}")

                # Establish the SSH connection using Fabric
                # TODO: Handle input details from CLI
                conn = Connection(
                    host=self.host,
                    port=22,
                    user=self.user,
                    connect_kwargs={"password": self.password},
                    connect_timeout=10,  # Timeout for connection
                )

                logger.info(f"Connected to {self.host}. Running tail -f on {self.log_file}")

                # Running the 'tail -f' command to stream logs
                with conn as c:
                    logger.info("running it now")
                    
                    # LogHandler will take in logs from this command.
                    cfo = LogHandler()
                    
                    # TODO: Run either tail or docker logs command.
                    result = c.run(f"tail -f {self.log_file}", hide=False, pty=True, warn=True, out_stream=cfo)
                    logger.warning("Result: %s", result)

                break  # Exit loop after a successful connection

            except (SSHException, UnexpectedExit) as e:
                retries += 1
                logger.error(f"Connection failed: {e}. Retrying in {self.backoff_time} seconds...")
                time.sleep(self.backoff_time)
                self.backoff_time *= 2  # Exponential backoff

        if retries == self.max_retries:
            logger.error(f"Failed to connect to {self.host} after {self.max_retries} attempts.")

    def start_log_thread(self):
        """
        Starts the log tailing operation in a separate daemon thread.
        This allows the main program to continue while logs are being collected.
        """
        if self.log_thread and self.log_thread.is_alive():
            logger.warning("Log thread is already running.")
            return

        self.log_thread = threading.Thread(
            target=self.run_tail_f_logs,
            daemon=True  # Ensures the thread exits when the main program exits
        )
        self.log_thread.start()
        logger.info("Started log tailing thread.")

    def join_log_thread(self):
        """
        Joins the log tailing thread, blocking until the thread terminates.
        Use this for clean shutdown or waiting for thread completion.
        """
        if self.log_thread:
            self.log_thread.join()
            logger.info("Log tailing thread has been joined and completed.")
    
class LogHandler:
    """
    Custom file-like object that handles Logs from the SSH connection run command.
    """
    # TODO: Tests for the LogHandler class

    def __init__(self):
        self.buffer = []
        self.is_open = True
        self.partial_line = ""
        
    def write(self, string):
        """
        The `write()` method receives the data to be written to the file-like object.
        This simulates the process of writing to a file or logging system.
        """
        
        # print string length in bytes
        logger.info(f"Received {len(string)} bytes of data")
        
        # Combine the partial line with the new string
        string = self.partial_line + string
        self.partial_line = ""
        
        # Here we're simulating writing to a log system or file.
        # In this example, we're appending data to an in-memory list.
        string_split = string.split("\n")
        
        # If the last line is incomplete, store it in partial_line
        if not string.endswith("\n"):
            self.partial_line = string_split.pop()
        
        if len(string_split) > 0:
            self.buffer.extend(string_split)

    def flush(self): 
        """
        Flush any buffered data. Called after the command this time runs or the buffered result is full (1000 charecters).
        """
        for line in self.buffer:
            parsed_line = self.parse_line(line)
            if parsed_line:
                # Once we have a valid line, it'll be here ready to send
                # TODO: Save to DB. Matching with timestamp of frame.
                logger.info(f"Parsed line: {parsed_line["timestamp"]} {parsed_line["message"]}")

    def parse_line(self, line):
        """
        Parse a line of log data and extract relevant information.
        """
        
        # Applying regex to the log string
        clean_line = self.remove_ansi_colors(line).strip()
        
        
        # TODO: Support different log formats and patterns
        #     docker logs
        #     docker ros
        #     docker isaac
        
        pattern = r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) (?P<level>\w+) (?P<message>.+)'
        
        match = re.match(pattern, clean_line)
        if match:
            return match.groupdict()
        return None

    def remove_ansi_colors(self, string):
        """
        Remove ANSI color codes from a string.
        """
        ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
        return ansi_escape.sub('', string)
    
    
    


# Example usage from another file
if __name__ == "__main__":
    # Configure Loguru logging (you can adjust the log file size, retention, etc.)
    logger.add("ssh_logs_{time}.log", rotation="500 MB", retention="10 days")

    # Example SSH connection parameters
    host = "example.com"
    user = "your_username"
    password = "password"
    log_file = "/var/log/syslog"  # Adjust to the log file on your server
    db_name = "logs.db"

    # Create the RemoteLogTailer instance
    log_tailer = RemoteLogTailer(
        host=host,
        user=user,
        password=password,
        log_file=log_file,
        db_name=db_name
    )

    # Start the log tailing in a separate thread
    log_tailer.start_log_thread()

    # Simulating main program loop
    try:
        while True:
            time.sleep(10)  # Main program continues with other tasks
    except KeyboardInterrupt:
        logger.info("Main thread interrupted. Exiting...")

    # Optionally, wait for the log tailing thread to finish (not necessary for daemon threads)
    # log_tailer.join_log_thread()