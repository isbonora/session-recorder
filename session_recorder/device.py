import threading
import time
from fabric import Connection
from loguru import logger
from invoke.exceptions import UnexpectedExit, CommandTimedOut
from paramiko.ssh_exception import SSHException
from datetime import datetime, timezone
import hashlib
import re


class RemoteLogTailer:
    """
    This class handles connecting to a remote server via SSH, tailing a log file, 
    and saving the logs to an SQLite database. It includes retry logic for robust
    connections and runs the tailing operation in a separate thread.
    """
    
    def __init__(self, host, user, password, log_file, db, max_retries=5, keepalive_interval=30):
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
        self.db = db
        self.max_retries = max_retries
        self.heartbeat_interval = 2
        self.backoff_time = 5  # Initial backoff time for retries
        self.log_thread = None
        self.heartbeat_thread = None
        self.heartbeat_active = False
        self.conn = None  # Holds the connection object
        self.tail_active = False

    def establish_connection(self):
        """
        Establishes the SSH connection to the remote host.
        """
        retries = 0
        while retries < self.max_retries:
            try:
                logger.info(f"Attempting connection to {self.host}. Attempt {retries + 1}/{self.max_retries}")
                self.conn = Connection(
                    host=self.host,
                    port=22,
                    user=self.user,
                    connect_kwargs={"password": self.password},
                    connect_timeout=3,
                )
                logger.info(f"Successfully connected to {self.host}.")
                return True
            except (SSHException, TimeoutError, ConnectionError, UnexpectedExit) as e:
                retries += 1
                logger.error(f"Connection failed: {e}. Retrying in {self.backoff_time} seconds...")
                time.sleep(self.backoff_time)
                self.backoff_time *= 2
        return False

    def run_tail_f_logs(self):
        """
        Runs the tail -f command on the remote host.
        """
        self.tail_active = True
        while self.tail_active:
            try:
                if self.conn:
                    logger.info(f"Running tail -f on {self.log_file}")
                    with self.conn as c:
                        cfo = LogHandler(self.db)
                        c.run(f"tail -f {self.log_file}", hide=False, pty=True, warn=True, out_stream=cfo)
                else:
                    raise ConnectionError("SSH connection is not established.")
            except (SSHException, TimeoutError, ConnectionError, UnexpectedExit) as e:
                logger.error(f"Command execution failed: {e}. Re-establishing connection and restarting command...")
                time.sleep(self.backoff_time)
                self.establish_connection()

    def heartbeat(self):
        
        def run_command_with_timeout(conn, command, timeout):
            result = [None]
            def target():
                try:
                    result[0] = conn.run(command, hide=True, warn=True, timeout=timeout)
                except Exception as e:
                    result[0] = e

            thread = threading.Thread(target=target)
            thread.start()
            thread.join(timeout)
            if thread.is_alive():
                return ConnectionError("Command timed out")
            return result[0]
        
        """
        Periodically checks the connection by running a lightweight command like 'echo'.
        If the command fails, it triggers a reconnection and resets the log tailing.
        """
        # FIXME: doesn't restart after it runs once
        while self.heartbeat_active:
            try:
                if self.conn:
                    logger.info("Sending heartbeat...")
                    result = run_command_with_timeout(self.conn, "echo heartbeat", 3)
                    if isinstance(result, Exception):
                        raise result
                    if result.failed:
                        raise ConnectionError("Heartbeat command failed.")
                else:
                    logger.warning("Connection is not established.")
                    self.establish_connection()

                logger.info("Heartbeat successful. Connection is alive.")
            except (SSHException, TimeoutError, ConnectionError, UnexpectedExit, OSError, CommandTimedOut, EOFError) as e:
                logger.error(f"Heartbeat failed: {e}. Reconnecting and restarting tail...")

                # Handle specific socket error for unreachable hosts
                if isinstance(e, OSError) and e.errno == 65:
                    logger.error("No route to host detected. Will retry with exponential backoff.")
                
                # Stop the tailing command and reconnect
                self.tail_active = False  
                time.sleep(self.backoff_time)
                self.establish_connection()
                self.restart_tail()  # Restart the tail
            finally:

                time.sleep(self.heartbeat_interval)
        logger.error("Heartbeat thread stopped.")

    def restart_tail(self):
        """
        Restarts the tail -f log command after a connection failure.
        """
        if not self.tail_active:
            self.log_thread = None
            self.log_thread = threading.Thread(target=self.run_tail_f_logs, daemon=True)
            self.log_thread.start()

    def start_threads(self):
        """
        Starts the log tailing operation and heartbeat checks in separate threads.
        """
        # Establish connection before starting the threads
        if not self.establish_connection():
            logger.error("Failed to establish initial connection.")
            return

        # Start the log tailing thread
        self.log_thread = threading.Thread(target=self.run_tail_f_logs, daemon=True)
        self.log_thread.start()

        # Start the heartbeat thread
        self.heartbeat_active = True
        self.heartbeat_thread = threading.Thread(target=self.heartbeat, daemon=True)
        self.heartbeat_thread.start()

        logger.info("Started log tailing and heartbeat threads.")

    def stop(self):
        """
        Stops the log tailing and heartbeat operations.
        """
        self.heartbeat_active = False
        self.tail_active = False
        if self.log_thread:
            self.log_thread.join()
        if self.heartbeat_thread:
            self.heartbeat_thread.join()
        if self.conn:
            self.conn.close()
        logger.info("Log tailing and heartbeat threads stopped.")

    
class LogHandler:
    """
    Custom file-like object that handles Logs from the SSH connection run command.
    """
    # TODO: Tests for the LogHandler class

    def __init__(self, db):
        self.buffer = []
        self.is_open = True
        self.partial_line = ""
        self.db = db
        self.inserted_hashes = []
        
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
            
            # Create a hash from the parsed line

            if parsed_line:
                line_hash = hashlib.md5(line.encode()).hexdigest()
                if line_hash in self.inserted_hashes:
                    logger.error(f"Duplicate line: {parsed_line["timestamp"]} {parsed_line["message"]}")
                    break
                self.inserted_hashes.append(line_hash)
                # Once we have a valid line, it'll be here ready to send
                # TODO: Save to DB. Matching with timestamp of frame.
                host_timestamp = datetime.now(timezone.utc)
                timestamp = datetime.strptime(parsed_line["timestamp"], "%Y-%m-%d %H:%M:%S.%f")
                
                self.db.insert_log(0, timestamp, host_timestamp, parsed_line["level"], parsed_line["message"])
                
                logger.info(f"Parsed line: {parsed_line["timestamp"]} {parsed_line["message"]}")
        
        self.buffer = []

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