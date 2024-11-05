from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    TIMESTAMP,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from typing import List
from loguru import logger
from datetime import datetime, timezone
import json
import yaml
import os
import tempfile
import re
import sys

from session_recorder.receiver import TrackerObject


# Base declarative class for SQLAlchemy models
Base = declarative_base()


# SQLAlchemy ORM mapping for the 'frames' table
class Frame(Base):
    __tablename__ = "frames"
    frame_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP, nullable=False)


# SQLAlchemy ORM mapping for the 'objects' table
class Object(Base):
    __tablename__ = "objects"
    object_id = Column(Integer, primary_key=True, autoincrement=True)
    frame_id = Column(Integer, ForeignKey("frames.frame_id"))
    name = Column(String(255), nullable=False)
    translation_x = Column(Float, nullable=False)
    translation_y = Column(Float, nullable=False)
    translation_z = Column(Float, nullable=False)
    rotation_x = Column(Float, nullable=False)
    rotation_y = Column(Float, nullable=False)
    rotation_z = Column(Float, nullable=False)


# SQLAlchemy ORM mapping for the 'events' table
class Event(Base):
    __tablename__ = "events"
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    frame_id = Column(Integer, ForeignKey("frames.frame_id"))
    event_type = Column(String(255), nullable=False)
    event_description = Column(Text, nullable=True)


# SQLAlchemy ORM mapping for the 'logs' table
class Log(Base):
    __tablename__ = "logs"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    frame_id = Column(Integer, ForeignKey("frames.frame_id"))
    timestamp = Column(TIMESTAMP, nullable=False)
    host_timestamp = Column(TIMESTAMP, nullable=False)
    level = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)


class DatabaseStorage:
    """
    Class that provides thread-safe access to the SQLite database using connection pooling.
    Supports writing frames, objects, events, and logs concurrently, with batch write features.
    """

    def __init__(self, project=None):
        """
        Initialize the connection to the SQLite database using SQLAlchemy connection pooling.
        """
        logger.info("Initializing database engine with connection pooling...")
        self.db_path = project.database_path

        db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},  # Thread-safe SQLite
            pool_size=5,  # Connection pool size
            max_overflow=10,
        )  # Allow additional connections beyond pool size

        # Create tables if they do not already exist
        Base.metadata.create_all(self.engine)

        # Set up a scoped session for thread-safe sessions
        self.Session = scoped_session(sessionmaker(bind=self.engine))

    def insert_frame(self, timestamp, frame_id=None):
        """
        Insert a single frame into the database with an optional custom frame_id.

        :param timestamp: The timestamp of the frame.
        :param frame_id: Optional custom frame_id. If None, the database will auto-generate.
        :return: The frame_id of the inserted frame.
        """
        session = self.Session()
        try:
            frame = Frame(timestamp=timestamp)

            # If custom frame_id is provided, set it manually
            if frame_id is not None:
                frame.frame_id = frame_id

            session.add(frame)
            session.commit()

            return frame.frame_id
        except Exception as e:
            logger.error(f"Error inserting frame: {e}")
            session.rollback()
        finally:
            session.close()

    def insert_object(self, frame_id, name, translation, rotation):
        """
        Insert a single object into the database.
        """
        session = self.Session()
        try:
            obj = Object(
                frame_id=frame_id,
                name=name,
                translation_x=translation[0],
                translation_y=translation[1],
                translation_z=translation[2],
                rotation_x=rotation[0],
                rotation_y=rotation[1],
                rotation_z=rotation[2],
            )
            session.add(obj)
            session.commit()
        except Exception as e:
            logger.error(f"Error inserting object: {e}")
            session.rollback()
        finally:
            session.close()

    def insert_frame_objects(self, frame_number, objects: List[TrackerObject]):
        """
        Insert multiple objects for a single frame into the database.
        """
        session = self.Session()
        try:
            frame_id = self.insert_frame(datetime.now(timezone.utc), frame_number)
            for obj in objects:
                self.insert_object(frame_id, obj.name, obj.translation, obj.rotation)
            session.commit()
        except Exception as e:
            logger.error(f"Error inserting objects: {e}")
            session.rollback()
        finally:
            session.close()

    def insert_event(self, frame_id, event_type, event_description):
        """
        Insert a single event into the database.
        """
        session = self.Session()
        try:
            event = Event(
                frame_id=frame_id,
                event_type=event_type,
                event_description=event_description,
            )
            session.add(event)
            session.commit()
            logger.info(f"Inserted Event '{event_type}' for Frame ID {frame_id}.")
        except Exception as e:
            logger.error(f"Error inserting event: {e}")
            session.rollback()
        finally:
            session.close()

    def insert_log(self, frame_id, timestamp, host_timestamp, level, message):
        """
        Insert a single log into the database.
        """
        session = self.Session()
        try:
            log = Log(
                frame_id=frame_id,
                timestamp=timestamp,
                host_timestamp=host_timestamp,
                level=level,
                message=message,
            )
            session.add(log)
            session.commit()
            logger.info(f"Inserted Log at {timestamp} for Frame ID {frame_id}.")
        except Exception as e:
            logger.error(f"Error inserting log: {e}")
            session.rollback()
        finally:
            session.close()

    def get_latest_log(self):
        """
        Get the latest log entry from the database.
        """
        session = self.Session()
        try:
            log = session.query(Log).order_by(Log.log_id.desc()).first()
            if log:
                logger.info(f"Latest Log: {log.message}")
            return log
        except Exception as e:
            logger.error(f"Error getting latest log: {e}")
        finally:
            session.close()

    def get_latest_frame_number(self):
        """
        Get the latest frame number from the database.
        """
        session = self.Session()
        try:
            frame = session.query(Frame).order_by(Frame.frame_id.desc()).first()
            if frame:
                logger.info(f"Latest Frame ID: {frame.frame_id}")
            return frame.frame_id
        except Exception as e:
            logger.error(f"Error getting latest frame number: {e}")
        finally:
            session.close()


class Project:
    """
    Project class holds all the necessary information for a single project.
    session_name: The name of the session.
    target: The target device to connect to. following the format of user@host:port.
    device_logpath: The path to the device log file.
    docker_container: The docker container id to connect to.
    is_temp: Whether the project is temporary or not. Creates a temp dir (used primarily for testing purposes)
    """

    def __init__(
        self,
        session_name=None,
        target=None,
        device_logpath=None,
        docker_container=None,
        is_temp=False,
    ):
        self.config = self.init_config()
        self.config["data"]["session_name"] = self.ensure_safe_name(session_name)
        self.data = self.config["data"]
        self.is_temp = is_temp
        self.project_folder = self.setup_project_files(
            self.data["session_name"], self.data["data_dir"]
        )
        self.database_path = os.path.join(self.project_folder, "session_data.db")
        self.logfile_path = os.path.join(self.project_folder, "debug_session.logs")

        # Get ssh details
        self.host, self.user, self.port, self.password = self.get_ssh_config(target)
        self.log_path = device_logpath
        self.docker_container = docker_container

        # Determine tail type
        # If logpath is provided, use file tailing
        # If docker_container is provided, use docker tailing
        # If neither is provided, use no tailing
        #    This will disable the tailing feature.
        if self.log_path:
            self.tail_type = "file"
        elif self.docker_container:
            self.tail_type = "docker"
        else:
            logger.warning(
                "No log path or docker container provided. Disabling tailing feature."
            )
            self.tail_type = None

        # This will save the project data to the project folder
        self.save_project_data()

    def __str__(self):
        return f"""
        Project Name: {self.data['session_name']}
        Project Folder: {self.project_folder}
        Database Path: {self.database_path}
        Logfile Path: {self.logfile_path}
        Is Temp?: {self.is_temp}
        SSH Host: {self.host}
        SSH User: {self.user}
        SSH Port: {self.port}
        SSH Password: {self.password}
        Log Path: {self.log_path}
        Docker Container: {self.docker_container}
        Tail Type: {self.tail_type}
        """

    def init_config(self, config="config.yml"):
        with open("config.yml", "r") as file:
            config = yaml.safe_load(file)
            if not config:
                # TODO: Maybe create a default config file if none is found?
                logger.error("No config file found at 'config.yml'. Please create one.")
                sys.exit(1)
        return config

    def setup_project_files(self, session_name="session", data_folder="data"):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

        project_folder = f"{timestamp}_{session_name}"

        if data_folder:
            project_folder = os.path.join(data_folder, project_folder)

        if self.is_temp:
            logger.warning(
                "Running in testing mode. Data will be stored in a temporary directory."
            )
            temp_dir = "tests/temp"
            os.makedirs(temp_dir, exist_ok=True)  # Ensure the temp directory exists
            project_folder = tempfile.mkdtemp(
                prefix=f"{timestamp}_{session_name}", dir=temp_dir
            )
        else:
            os.makedirs(project_folder, exist_ok=True)

        return project_folder

    def get_ssh_config(self, target: String = None):
        host = self.config["device"].get("host", None)
        user = self.config["device"].get("user", None)
        port = self.config["device"].get("port", None)
        # TODO: If this is missing? Should we prompt for it?
        password = self.config["device"].get("password", None)

        # TODO: Test for valid target format
        if self.is_valid_target_host(target):
            host = target.split("@")[1].split(":")[0]
            user = target.split("@")[0]
            port = target.split(":")[1]

        if host is None or user is None or port is None or password is None:
            raise ValueError(
                "Missing SSH configuration. Please check your config file."
            )
            sys.exit(1)

        return host, user, port, password

    def ensure_safe_name(self, name):
        return re.sub(r"[^a-zA-Z0-9_]", "_", name)

    def is_valid_target_host(self, target):
        # Ensures the target is valid string format (user@host:port)
        # Will raise error if not valid.
        if target is None:
            return False

        regex_pattern = r"^[a-zA-Z0-9_]+@[a-zA-Z0-9_]+:[0-9]+$"
        if not re.match(regex_pattern, target):
            raise ValueError(
                "Invalid target format. Please use the format 'user@host:port'."
            )
            sys.exit(1)

        return target

    def get_project_data_as_dict(self):
        return {
            "session_name": self.data["session_name"],
            "project_folder": self.project_folder,
            "database_path": self.database_path,
            "logfile_path": self.logfile_path,
            "is_temp": self.is_temp,
            "host": self.host,
            "user": self.user,
            "port": self.port,
            "password": self.password,
            "log_path": self.log_path,
            "docker_container": self.docker_container,
            "tail_type": self.tail_type,
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

    # TODO: Save this project data to a table within the SQLite database.
    def save_project_data(self):
        with open(os.path.join(self.project_folder, "project_data.json"), "w") as file:
            json.dump(self.get_project_data_as_dict(), file, indent=4)

    # TODO: Save this session details to a file for later review.
    def save_session(self):
        pass
