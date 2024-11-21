import pytest
import os
from session_recorder.receiver import TrackerObject
from session_recorder.store import DatabaseStorage, Project
from sqlalchemy import create_engine, inspect, text
from datetime import datetime


def test_new_project_succesfully():
    project = Project()
    project.create("test", is_temp=True)

    assert os.path.exists(project.session_folder)

def test_new_project_config_succesfully():
    project_name = "this_is_a_test"
    project = Project()
    project.create(project_name, is_temp=True)

    assert project.session_name == project_name

def test_auto_make_safe_project_name_spaces():
    project_name_not_safe = "this is a test"
    project_name_safe = "this_is_a_test"

    project = Project()
    project.create(project_name_not_safe, is_temp=True)

    assert project.session_name == project_name_safe

def test_auto_make_safe_project_name_slashes():
    project_name_not_safe = "this/is/a/test"
    project_name_safe = "this_is_a_test"

    project = Project()
    project.create(project_name_not_safe, is_temp=True)

    assert project.session_name == project_name_safe


# Database
def test_database_storage():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    # ensures sqlaclhemy engine is created
    assert db.engine
    assert inspect(db.engine).has_table("frames")
    assert inspect(db.engine).has_table("objects")
    assert inspect(db.engine).has_table("events")
    assert inspect(db.engine).has_table("logs")



def test_database_frames_table_has_correct_columns():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    assert db.engine

    cols = inspect(db.engine).get_columns("frames")

    assert type(cols) == list
    assert len(cols) == 2
    assert cols[0]["name"] == "frame_id"
    assert cols[0]["primary_key"] == 1
    assert cols[1]["name"] == "timestamp"



def test_database_objects_table_has_correct_columns():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    assert db.engine

    cols = inspect(db.engine).get_columns("objects")

    assert type(cols) == list
    assert len(cols) == 9

    assert cols[0]["name"] == "object_id"
    assert cols[0]["primary_key"] == 1
    assert cols[1]["name"] == "frame_id"
    assert cols[2]["name"] == "name"
    assert cols[3]["name"] == "translation_x"
    assert cols[4]["name"] == "translation_y"
    assert cols[5]["name"] == "translation_z"
    assert cols[6]["name"] == "rotation_x"
    assert cols[7]["name"] == "rotation_y"
    assert cols[8]["name"] == "rotation_z"

def test_database_events_table_has_correct_columns():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    assert db.engine

    cols = inspect(db.engine).get_columns("events")

    assert type(cols) == list
    assert len(cols) == 4

    assert cols[0]["name"] == "event_id"
    assert cols[0]["primary_key"] == 1
    assert cols[1]["name"] == "frame_id"
    assert cols[2]["name"] == "event_type"
    assert cols[3]["name"] == "event_description"

def test_database_logs_table_has_correct_columns():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    assert db.engine

    cols = inspect(db.engine).get_columns("logs")

    assert type(cols) == list
    assert len(cols) == 6

    assert cols[0]["name"] == "log_id"
    assert cols[0]["primary_key"] == 1
    assert cols[1]["name"] == "frame_id"
    assert cols[2]["name"] == "timestamp"
    assert cols[3]["name"] == "host_timestamp"
    assert cols[4]["name"] == "level"
    assert cols[5]["name"] == "message"


def test_insert_frame():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    timestamp = datetime.now()
    timestamp_string = timestamp.isoformat(sep=" ")

    db.insert_frame(timestamp, 1)

    session = db.Session()
    query = text("SELECT * FROM frames")
    assert session.execute(query).fetchone() == (1, timestamp_string)


def test_insert_object():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    timestamp = datetime.now()

    f_id = db.insert_frame(timestamp, 1)
    db.insert_object(f_id, "test_object_name", [1, 2, 3], [4, 5, 6])

    session = db.Session()
    query = text("SELECT * FROM objects")
    assert session.execute(query).fetchone() == (f_id, 1, "test_object_name", 1, 2, 3, 4, 5, 6)

def test_insert_event():
    project = Project()
    project.create("insert_event_test", is_temp=True)
    db = DatabaseStorage(project)

    timestamp = datetime.now()

    f_id = db.insert_frame(timestamp, 1)

    db.insert_event(f_id, "test_event_type", "test_event_description")

    session = db.Session()
    query = text("SELECT * FROM events")
    assert session.execute(query).fetchone() == (1, f_id, "test_event_type", "test_event_description")


def test_insert_log():
    project = Project()
    project.create("insert_log_test", is_temp=True)
    db = DatabaseStorage(project)

    timestamp = datetime.now()
    timestamp_string = timestamp.isoformat(sep=" ")

    f_id = db.insert_frame(timestamp, 1)
    db.insert_log(f_id, timestamp, timestamp, "INFO", "test_message")

    session = db.Session()
    query = text("SELECT * FROM logs")
    assert session.execute(query).fetchone() == (1, f_id, timestamp_string, timestamp_string, "INFO", "test_message")


def test_insert_multiple_objects(how_many_objects=100):
    project = Project()
    project.create("insert_multi_objects_test", is_temp=True)
    db = DatabaseStorage(project)

    # how many objects per frame to test
    # Realistically, this number should only just a few objects 2-4

    frame_id = 1

    objects = [TrackerObject(f"test_object_name_{i}".encode(),1.0,2.0,3.0,4.0,5.0,6.0) for i in range(how_many_objects)]

    db.insert_frame_objects(frame_id, objects)

    session = db.Session()
    query = text("SELECT * FROM objects")
    assert session.execute(query).fetchall() == [(i+1, frame_id, f"test_object_name_{i}", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0) for i in range(how_many_objects)]


def test_get_latest_log():
    project = Project()
    project.create("get_latest_log_test", is_temp=True)
    db = DatabaseStorage(project)

    timestamp = datetime.now()

    f_id = db.insert_frame(timestamp, 4123453)

    db.insert_log(f_id, timestamp, timestamp, "INFO", "test_message")

    log = db.get_latest_log()

    assert log.frame_id == f_id
    assert log.timestamp == timestamp


def test_get_latest_frame():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    timestamp = datetime.now()

    f_id = db.insert_frame(timestamp, 123124)

    frame = db.get_latest_frame_number()
    assert frame == f_id


def test_get_latest_frame_where_frames_empty():
    project = Project()
    project.create("test", is_temp=True)
    db = DatabaseStorage(project)

    frame = db.get_latest_frame_number()
    assert frame == None


def test_parse_full_target_ssh_string():
    
    project = Project()
    project.create("test", target="username@endpoint:1234", is_temp=True)
    
    assert project.target_user == "username"
    assert project.target_host == "endpoint"
    assert project.target_port == 1234

def test_parse_full_target_ssh_string_without_port():
    
    project = Project()
    project.create("test", target="username@endpoint", is_temp=True)
    
    assert project.target_user == "username"
    assert project.target_host == "endpoint"
    assert project.target_port == 22

def test_parse_full_target_ssh_string_without_port_and_user():
        
    project = Project()
    project.create("test", target="endpoint", is_temp=True)
    
    assert project.target_user == "iw"
    assert project.target_host == "endpoint"
    assert project.target_port == 22
    
def test_parse_ssh_without_input_target_string():
            
    project = Project()
    project.create("test", is_temp=True)
    
    # should be default values
    assert project.target_user == "iw"
    assert project.target_host == "localhost"
    assert project.target_port == 22