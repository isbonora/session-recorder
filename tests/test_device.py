from session_recorder.device import LogHandler, Log
from session_recorder.store import DatabaseStorage, Project
import datetime



# everything loghandler
def test_parse_standard_isaac_log_line():
    project = Project("standard_isaac", is_temp=True)

    db = DatabaseStorage(project)
    lh = LogHandler(db)

    input_string = "[0m2024-04-09 13:38:32.723 INFO  components/cloud/AWS/components/MissionAdapterHelper.cpp@919: Updating all order actions from RUNNING to FAILED[0m"

    expected_value = Log(
        timestamp=datetime.datetime(2024, 4, 9, 13, 38, 32, 723000),
        level="INFO",
        message=" components/cloud/AWS/components/MissionAdapterHelper.cpp@919: Updating all order actions from RUNNING to FAILED"
    )

    assert lh.parse_line(input_string) == expected_value

def test_parse_foundries_isaac_log_line():
    project = Project("foundries_isaac", is_temp=True)

    db = DatabaseStorage(project)
    lh = LogHandler(db)

    input_string = "2024-07-25T13:59:50.007869000Z 2024-06-25 13:00:35.152 WARN  components/behaviors/behavior_tree/MemorySequenceBehavior.cpp@24: str Memory Sequence Behavior ticked, child status:succeess"

    expected_value = Log(
        timestamp=datetime.datetime(2024, 7, 25, 13, 59, 50, 7869),
        level="WARN",
        message="components/behaviors/behavior_tree/MemorySequenceBehavior.cpp@24: str Memory Sequence Behavior ticked, child status:succeess"
    )

    assert lh.parse_line(input_string) == expected_value


def test_parse_foundries_ros_log_line():
    project = Project("foundries_ros", is_temp=True)

    db = DatabaseStorage(project)
    lh = LogHandler(db)

    input_string = "2024-07-25T14:20:09.675714000Z [iw_brain_exe-23] [0m1721917209.672508050 INFO brain.brain: Executing mission 'a605b7c6-0fe4-41d3-ae9c-7d8a911d25cd' with step number '4' of type 'DROP'[0m"

    expected_value = Log(datetime.datetime(2024, 7, 25, 14, 20, 9, 675714), "INFO", "brain.brain: Executing mission 'a605b7c6-0fe4-41d3-ae9c-7d8a911d25cd' with step number '4' of type 'DROP'")

    assert lh.parse_line(input_string) == expected_value

def test_handle_parital_foundries_ros_log_line():
    project = Project("foundries_ros", is_temp=True)

    db = DatabaseStorage(project)
    lh = LogHandler(db)

    input_string = "2024-07-25T14:16:38.182418000Z [iw_brain_exe-23] is_retry: false"
    expected_value = Log(datetime.datetime(2024, 7, 25, 14, 16, 38, 182418), "DEBUG", "is_retry: false")


    assert lh.parse_line(input_string) == expected_value

def test_convert_any_possible_timestamp_to_datetime():
    project = Project("standard_isaac", is_temp=True)
    db = DatabaseStorage(project)
    lh = LogHandler(db)

    timestamps = [
        "2024-04-09 13:38:32.723",
        "2024-07-25T14:20:09.675714000Z",
        "2024-07-25T14:18:36.349745000Z",
        "2024-07-25T14:16:38.183269000Z",
        "2024-10-28T13:36:00.655659681Z"
    ]

    for t in timestamps:
        assert type(lh.convert_to_datetime(t)) == datetime.datetime


# TODO: Load in log files from the robot and run the tests on them. Test if it parses everything. and misses is a fail.


def test_remove_ansi_colors():
    project = Project("standard_isaac", is_temp=True)
    db = DatabaseStorage(project)
    lh = LogHandler(db)

    input_string = "[0m2024-04-09 13:38:32.723 INFO  components/cloud/AWS/components/MissionAdapterHelper.cpp@919: Updating all order actions from RUNNING to FAILED[0m"

    expected_value = "2024-04-09 13:38:32.723 INFO  components/cloud/AWS/components/MissionAdapterHelper.cpp@919: Updating all order actions from RUNNING to FAILED"

    assert lh.remove_ansi_colors(input_string) == expected_value
