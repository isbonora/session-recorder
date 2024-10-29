
import pytest
from session_recorder.receiver import UDPPacketReceiver, TrackerObject


def test_process_packet():
    receiver = UDPPacketReceiver()
    # this is a packet from the Vicon system
    # represtents 3 objects in the scene
    packet = b"6\xb7\x00\x00\x03\x00H\x00iwhub\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\xfb|\xa6\xabK\xda\xbft}\xb5n\x87C\xb6\xbf\x00\x00\x00\x00\x00\x00\xf0?\xb0 \xac\xe1\xa6\xb1\xc7?V\xe8E\x04\xd7\x19\x08@BD\xc5\x07\xc6\xce\xd5?\x00H\x00shape\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc1\xefU\xc9\x01\xe2\xea\xbf\xbf\x98\x1e\xb1\x9bD\xc3\xbf\x00\x00\x00\x00\x00\x00\xf0?\x80\xbc\x0b\xcb\xd9%\xce?8\x8b\xcfo\x8b'\x15@\xa56Tv\x94\x95\xd6?\x00H\x00dolly\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00E*y\x12_*\xde\xbfl\x0b\xb0I\x17\xa6\x83\xbf\x00\x00\x00\x00\x00\x00\xf0?A\x92\xab>\xed\xad\xc6?p\xeaD\x95\x00\xf9\xfc?\x93\x12:r\xd1>\n@"

    frame_number, objects = receiver.process_packet(packet)

    assert frame_number == 46902
    assert len(objects) == 3
    assert objects[0].name == "iwhub"
    assert objects[1].name == "shape"
    assert objects[2].name == "dolly"
    assert type(objects[0]) == TrackerObject

def test_bad_type_process_packet():
    with pytest.raises(ValueError):
        receiver = UDPPacketReceiver()
        # this is a packet from the Vicon system
        # represtents 3 objects in the scene
        packet = 12345678

        frame_number, objects = receiver.process_packet(packet)

def test_bad_bytes_process_packet():
    with pytest.raises(ValueError):
        receiver = UDPPacketReceiver()
        # this is a packet from the Vicon system
        # represtents 3 objects in the scene
        packet = b"asdfasd fkasjdhf alksdjf laksjdf laksjdf lkaj"

        frame_number, objects = receiver.process_packet(packet)


def test_tracker_object_create():
    obj = TrackerObject(b"test", 1, 2, 3, 4, 5, 6)

    assert obj.name == "test"
    assert obj.trans_x == 1
    assert obj.trans_y == 2
    assert obj.trans_z == 3
    assert obj.rot_x == 4
    assert obj.rot_y == 5
    assert obj.rot_z == 6

    assert obj.translation == [1, 2, 3]
    assert obj.rotation == [4, 5, 6]

def test_tracker_object_bad_type_create():
    with pytest.raises(ValueError):
        obj = TrackerObject("test", 2, 3, 4, 5, 6, 7)
