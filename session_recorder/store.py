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
        self.db_path = project.session_database_path

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
    def __init__(self):
        # Project information
        self.data_directory: String = "data" # Default data directory where each session is stored
        
        # Session information
        self.is_temp: bool = False
        self.existing_session: bool = False
        self.session_name: String = "session"
        self.session_folder: String = None
        self.session_database_path: String = None
        self.session_cli_logs_path: String = None
        self.session_timestamp: datetime = datetime.now(timezone.utc)
        
        # Target device information
        self.target_tail_log_path: String = None
        self.target_tail_docker_container: String = None
        self.target_tail_type: String = None
        self.target_host: String = "localhost"
        self.target_user: String = "iw"
        self.target_port: Integer = 22
        self.target_password: String = "inno2018"
        
        # Vicon Data
        self.vicon_host: String = "127.0.0.1"
        self.vicon_port: Integer = 51001
        
        
        
    def serialize(self):
        return {
            "vicon": {
                "host": self.vicon_host,
                "port": self.vicon_port
            },
            "target": {
                "log_path": self.target_log_path,
                "docker_container": self.target_docker_container,
                "host": self.target_host,
                "user": self.target_user,
                "port": self.target_port,
                "password": self.target_password,
                "tail_type": self.target_tail_type
            },
            "session": {
                "name": self.session_name,
                "folder": self.session_folder,
                "database_path": self.session_database_path,
                "cli_logs_path": self.session_cli_logs_path,
                "timestamp": self.session_timestamp,
                "is_temp": self.is_temp
            },
            "data_directory": self.data_directory
        }
    
    def deserialize(self, data):
        self.vicon_host = data["vicon"]["host"]
        self.vicon_port = data["vicon"]["port"]
        self.target_log_path = data["target"]["log_path"]
        self.target_docker_container = data["target"]["docker_container"]
        self.target_host = data["target"]["host"]
        self.target_user = data["target"]["user"]
        self.target_port = data["target"]["port"]
        self.target_password = data["target"]["password"]
        self.target_tail_type = data["target"]["tail_type"]
        self.session_name = data["session"]["name"]
        self.session_folder = data["session"]["folder"]
        self.session_database_path = data["session"]["database_path"]
        self.session_cli_logs_path = data["session"]["cli_logs_path"]
        self.session_timestamp = data["session"]["timestamp"]
        self.is_temp = data["session"]["is_temp"]
        self.data_directory = data["data_directory"]
        
    def load_session(self, session_name):
        """Load an existing session from disk."""
        session_path = os.path.join(self.data_directory, session_name)
        if not os.path.exists(session_path):
            logger.error(f"session '{session_name}' does not exist.")
            return False
        
        session_file = os.path.join(session_path, "session.yml")
        if not os.path.exists(session_file):
            logger.error(f"session file '{session_file}' does not exist.")
            return False
        
        with open(session_file, "r") as f:
            session_data = yaml.safe_load(f)
            self.deserialize(session_data)
        
        self.existing_session = True
        return True
    
    def save_session(self, session_folder):
        """Save the session to disk."""
        
        session_file = os.path.join(session_folder, "session.yml")
        with open(session_file, "w") as f:
            yaml.dump(self.serialize(), f)
        
        return session_file
        
        
    def create(self, session_name, target=None, target_log_path=None, target_docker_container=None, is_temp=False):
        """Create a new project, including all it's folders and files."""
        
        self.is_temp = is_temp
        self.session_name = self.__clean_session_name__(session_name)
        
        # Set the target SSH information
        if target:
            self.__setup_target_ssh__(target)
        
        # Setup the project folders
        self.__setup_session_folder__()
        
        # Setup logger targets
        self.__setup_tail_details__(target_log_path, target_docker_container)
        
        self.session_database_path = os.path.join(self.session_folder, "session.db")
        self.session_cli_logs_path = os.path.join(self.session_folder, "debug.logs")
        
    def __clean_session_name__(self, session_name):
        """
        # Clean the session name.
        
        Replaces spaces and slashes with underscores.
        """
        return re.sub(r"[ /]", "_", session_name)
        
    def __setup_target_ssh__(self, target):
        """
        # Setup the target SSH information.
        
        The target is in the format of user@host:port.
        
        will take any combination 
        """
        regex_pattern = r"^(?:(?P<user>\w+)@)?(?P<host>[\w\.\-]+)(?::(?P<port>\d+))?$"
        match = re.search(regex_pattern, target)
        
        if match:
            match_dict = match.groupdict()
            print(match_dict)
        else:
            raise ValueError(f"Invalid target format: {target}")
        
        if match_dict.get("user") is not None:
            self.target_user = match_dict.get("user", self.target_user)
            
        if match_dict.get("host") is not None:
            self.target_host = match_dict.get("host", self.target_host)
        
        if match_dict.get("port") is not None:
            self.target_port = int(match_dict.get("port", self.target_port))
        
        logger.debug(f"Target SSH: {self.target_user} @ {self.target_host} : {self.target_port}")
        
        
        
    def __setup_session_folder__(self):
        """
        # Setup a new session folder.
        
        If the project is temporary, create a temporary directory. This is used primarily for testing purposes.
        """
        timestamp_string = self.session_timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        session_folder = f"{timestamp_string}_{self.session_name}"
        session_path = os.path.join(self.data_directory, session_folder)
        
        # If the project is temporary, create a temporary directory
        if self.is_temp:
            session_path = tempfile.mkdtemp(timestamp_string)
        
        if not os.path.exists(session_path):
            os.makedirs(session_path)
            
        self.session_folder = session_path
        return session_path
    
    def __setup_tail_details__(self, target_log_path, target_docker_container):
        """
        # Setup the tail details for the target device.
        
        The target device log path and docker container id are set here.
        """
        self.target_log_path = target_log_path
        self.target_docker_container = target_docker_container
        
        if self.target_log_path:
            self.target_tail_type = "log"
        elif self.target_docker_container:
            self.target_tail_type = "docker"
        else:
            logger.error("No target log path or docker container provided. Continuing without tailing.")
            return False
        
        return self.target_log_path, self.target_docker_container