import threading
import time
from fabric import Connection
from loguru import logger
from invoke.exceptions import UnexpectedExit, CommandTimedOut
from paramiko.ssh_exception import SSHException
from datetime import datetime, timezone
import re
import paramiko


class RemoteLogTailer:
    """
    This class handles connecting to a remote server via SSH, tailing a log file,
    and saving the logs to an SQLite database. It includes retry logic for robust
    connections and runs the tailing operation in a separate thread.
    """

    def __init__(
        self,
        host,
        user,
        password,
        log_file,
        docker_container,
        db,
        port=22,
        max_retries=5,
        keepalive_interval=30,
    ):
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
        self.port = port
        self.password = password
        self.log_file = log_file
        self.docker_container = docker_container
        self.max_retries = max_retries
        self.keepalive_interval = keepalive_interval
        # Initial backoff time for retries
        self.backoff_time = 5
        self.log_thread = None
        self.db = db
        self.max_retries = max_retries
        self.heartbeat_interval = 2
        # Initial backoff time for retries
        self.backoff_time = 5
        self.log_thread = None
        self.heartbeat_thread = None
        self.heartbeat_active = False
        # Holds the connection object
        self.conn = None
        self.tail_active = False

    def establish_connection(self):
        paramiko.util.log_to_file("paramiko_debug.log", level="DEBUG")
        """
        Establishes the SSH connection to the remote host.
        """
        retries = 0
        while retries < self.max_retries:
            try:
                logger.info(
                    f"Attempting connection to {self.host}. Attempt {retries + 1}/{self.max_retries}"
                )
                self.conn = Connection(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    connect_kwargs={"password": self.password, "look_for_keys": False},
                    connect_timeout=3,
                )
                logger.info(f"Successfully connected to {self.host}.")
                return True
            except (SSHException, TimeoutError, ConnectionError, UnexpectedExit) as e:
                retries += 1
                logger.error(
                    f"Connection failed: {e}. Retrying in {self.backoff_time} seconds..."
                )
                time.sleep(self.backoff_time)
                self.backoff_time *= 2
        return False

    def run_tail_f_logs(self):
        """
        Runs the tail -f command on the remote host.
        TODO: Setup to handle tail -f & docker logs -f commands.
        TODO: Let me adjust how many it returns on first load. Default is 10, i want 50 if we have to restart the conneciton.
        TODO: Fix "Oops, unhandled type 3 ('unimplemented')" error. Happens on startup only occasionally.
        """

        if self.log_file:
            logger.info(f"Running tail -f on {self.log_file}")
            command = f"tail -f {self.log_file}"
        else:
            logger.info(f"Running docker logs on {self.docker_container}")
            command = f"docker logs {self.docker_container} -f -t -n 100"

        self.tail_active = True
        while self.tail_active:
            try:
                if self.conn:
                    logger.info(f"Running '{command}'...")
                    with self.conn as c:
                        # if not c.is_connected:
                        #     raise ConnectionError("SSH connection was lost and is not established.")
                        # TODO: Handle Docker logs -f command
                        cfo = LogHandler(self.db)
                        c.run(command, hide=False, pty=True, warn=True, out_stream=cfo)
                        logger.error("Tail command finished. Do something here.")
                else:
                    raise ConnectionError("SSH connection is not established.")
            except (SSHException, TimeoutError, ConnectionError, UnexpectedExit) as e:
                logger.error(
                    f"Command execution failed: {e}. Re-establishing connection and restarting command..."
                )
                time.sleep(self.backoff_time)
                self.establish_connection()

    def heartbeat(self):
        """
        Runs a lightweight command periodically to check the SSH connection.
        The timeout on .run doesn't work in my usecase so I had to implement a custom timeout function.
        FIXME: Fails sometimes on startup and restarts the main thread.
        """

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
            except (
                SSHException,
                TimeoutError,
                ConnectionError,
                UnexpectedExit,
                OSError,
                CommandTimedOut,
                EOFError,
            ) as e:
                logger.error(
                    f"Heartbeat failed: {e}. Reconnecting and restarting tail..."
                )

                # Stop the tailing command and reconnect
                self.tail_active = False
                time.sleep(self.backoff_time)
                self.establish_connection()
                self.restart_tail()  # Restart the tail

            finally:
                time.sleep(self.heartbeat_interval)
        # It should never reach here.
        logger.error("Heartbeat thread stopped.")

    def restart_tail(self):
        """
        Restarts the tail -f log command thread after a connection failure.
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


class Log:
    def __init__(self, timestamp, level: str, message: str, component: str = None):
        if type(timestamp) is str:
            self.timestamp = self.convert_to_datetime(timestamp)
        else:
            self.timestamp = timestamp

        self.level = level
        self.message = message
        self.component = component

    def __eq__(self, other):
        if isinstance(other, Log):
            return (
                self.timestamp == other.timestamp
                and self.level == other.level
                and self.message == other.message
                and self.component == other.component
            )
        return False

    def __repr__(self):
        return (
            f"Log(timestamp={self.timestamp!r}, level={self.level!r}, "
            f"message={self.message!r}, component={self.component!r})"
        )

    def convert_to_datetime(self, timestamp):
        """
        Convert a timestamp string to a datetime object.
        """
        try:
            # Truncate nanoseconds to microseconds
            if "." in timestamp:
                timestamp, nanoseconds = timestamp.split(".")
                nanoseconds = nanoseconds[
                    :6
                ]  # Keep only the first 6 digits for microseconds
                timestamp = f"{timestamp}.{nanoseconds}"
            return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        except:
            return None


class LogHandler:
    """
    Custom file-like object that handles Logs from the SSH connection run command.
    TODO: Handle duplicates. Rolling last imported timestamp and if get one that's the same or older, skip it.
    TODO: Tests for the LogHandler class
    TODO: Handle docker results. Make it agnostic to the log format.
    TODO: New class of our log.
    """

    def __init__(self, db):
        self.buffer = []
        self.is_open = True
        self.partial_line = ""
        self.db = db

    def write(self, string):
        """
        The `write()` method receives the data to be written to the file-like object.
        This simulates the process of writing to a file or logging system.
        """

        # print string length in bytes
        logger.debug(f"Received {len(string)} bytes of data")

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
                # Once we have a valid line, it'll be here ready to send
                # TODO: Save to DB. Matching with timestamp of frame.
                host_timestamp = datetime.now(timezone.utc)
                timestamp = parsed_line.timestamp

                latest_log = self.db.get_latest_log()
                latest_frame_number = self.db.get_latest_frame_number()

                if latest_log:
                    # Only insert the log if it's newer than the latest log in the database
                    if timestamp > latest_log.timestamp:
                        self.db.insert_log(
                            latest_frame_number,
                            timestamp,
                            host_timestamp,
                            parsed_line.level,
                            parsed_line.message,
                        )
                else:
                    self.db.insert_log(
                        latest_frame_number,
                        timestamp,
                        host_timestamp,
                        parsed_line.level,
                        parsed_line.message,
                    )
                logger.info(
                    f"Parsed line: {parsed_line.timestamp} {parsed_line.message}"
                )

        self.buffer = []

    def parse_line(self, line):
        """
        Parse a line of log data and extract relevant information.
        """

        # Applying regex to the log string
        clean_line = self.remove_ansi_colors(line).strip()

        log_features = self.extract_log_features(clean_line)

        if not log_features:
            logger.warning(f"Could not parse log line: {clean_line}")
            return None

        # Fixes a scenario where the level is not set
        # for some ros2 logs in foundries. Defaulting to DEBUG
        if log_features.get("level", None) is None:
            log_features["level"] = "DEBUG"

        log = Log(
            log_features["timestamp"],
            log_features.get("level", None),
            log_features["message"],
            log_features.get("component", None),
        )

        return log

    def extract_log_features(self, log_line):
        # TODO: Ensrue with foundires we get component as well (the bit between the brackets)
        patterns = [
            # Standard Isaac log pattern
            r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) (?P<level>\w+) (?P<message>.+)",
            # Foundries ROS log pattern
            r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s\[\w+-\d+\]\s\d+\.\d+\s(?P<level>INFO|DEBUG|ERROR|WARNING)\s(?P<message>.*)",
            # Foundries Isaac
            r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{9}Z)\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+(?P<level>\w+)\s+(?P<message>.+)$",
            # support for partial foundries ros log line
            r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s\[\w+-\d+\]\s(?P<message>.*)",
        ]

        for pattern in patterns:
            match = re.match(pattern, log_line)
            if match:
                return match.groupdict()
        return None

    def convert_to_datetime(self, timestamp):
        """
        Convert a timestamp string to a datetime object.
        """
        try:
            # Truncate nanoseconds to microseconds
            if "." in timestamp:
                timestamp, nanoseconds = timestamp.split(".")
                nanoseconds = nanoseconds[
                    :6
                ]  # Keep only the first 6 digits for microseconds
                timestamp = f"{timestamp}.{nanoseconds}"
            return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        except:
            return None

    def remove_ansi_colors(self, string):
        """
        Remove ANSI color codes from a string.
        """
        ansi_escape = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
        return ansi_escape.sub("", string)
