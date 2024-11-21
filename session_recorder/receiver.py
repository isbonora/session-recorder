import socket
import struct
import threading
from loguru import logger
from datetime import datetime
import time


# Class to represent each TrackerObject as defined in your packet
class TrackerObject:
    def __init__(
        self,
        name: bytes,
        trans_x: float,
        trans_y: float,
        trans_z: float,
        rot_x: float,
        rot_y: float,
        rot_z: float,
    ):
        if type(name) is not bytes:
            raise ValueError("name must be of type bytes")

        # Decode the object name from bytes
        self.name = name.split(b"\x00", 1)[0].decode("utf-8")
        self.trans_x = trans_x
        self.trans_y = trans_y
        self.trans_z = trans_z
        self.rot_x = rot_x
        self.rot_y = rot_y
        self.rot_z = rot_z
        self.translation = [trans_x, trans_y, trans_z]
        self.rotation = [rot_x, rot_y, rot_z]

    def __str__(self):
        # String representation for easy printing of the object data
        return (
            f"TrackerObject(name='{self.name}', "
            f"trans_x={self.trans_x:.3f}, trans_y={self.trans_y:.3f}, trans_z={self.trans_z:.3f}, "
            f"rot_x={self.rot_x:.4f}, rot_y={self.rot_y:.4f}, rot_z={self.rot_z:.4f})"
        )


# Class to handle the UDP packet reception
class UDPPacketReceiver:
    def __init__(self, host="localhost", port=51005, database=None):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.running = True
        self.database = database
        self.count = 0
        self.last_count_reported = 0
        self.last_milestone_timestamp = None

    # Start the packet listener in its own thread
    def start(self):
        logger.info(f"Starting UDP listener on {self.host}:{self.port}")
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.thread.start()

        self.reporting_thread = threading.Thread(
            target=self.provide_user_feedback, daemon=True
        )
        self.reporting_thread.start()

    # Stop the listener
    def stop(self):
        logger.info("Stopping UDP listener...")
        self.running = False
        self.thread.join()
        self.reporting_thread.join()

    # Listen for incoming packets and process them
    def listen(self):
        logger.info(f"Listening for UDP packets on {self.host}:{self.port}")
        while self.running:
            data, addr = self.sock.recvfrom(1024)  # Buffer size
            frame_number, objects = self.process_packet(data)
            
            logger.trace(f"Received frame {frame_number} with {len(objects)} objects")

            if self.database:
                self.database.insert_frame_objects(frame_number, objects)

    def provide_user_feedback(self):
        """
        Prints a message every 10 seconds with the number of objects received so far
        Useful to see if the data is coming in as expected at an expected FPS.
        """
        INTERVAL = 0.5  # seconds

        while self.running:
            if self.last_milestone_timestamp is None:
                if self.count > 0:
                    logger.info("Received first object from Vicon Tracker!")
                    self.last_milestone_timestamp = datetime.now()
                # TODO: Add a timeout here to stop the program if no data is received for a certain time
            else:
                self.last_milestone_timestamp = datetime.now()
                # FIXME: This value may not be accurate? in testing 200fps was reported at ~160fps
                average_fps = (self.count - self.last_count_reported) / INTERVAL
                

                self.last_count_reported = self.count

                # This weird logic here stops printing a log with invalid data.
                # we want to wait for the system to settle after getting the first frame
                if INTERVAL == 10:
                    logger.trace(
                        f"Received {self.count} {self.last_count_reported} ({average_fps:.2f} fps avg) frames so far..."
                    )
                    
                    logger.info(
                        f"Received {self.count} ({average_fps} fps avg) frames so far..."
                    )
                    # If the FPS is low (less than 0.1), we can assume Vicon has stopped sending data.
                    if average_fps < 0.1:
                        logger.error(
                            "FPS is too low. Vicon may have stopped sending frames?"
                        )

                INTERVAL = 10

            # Wait for the next interval
            # This is a blocking call, so the thread will sleep for the specified time
            # Had an issue before where it was taking up too much CPU time
            #   and the vicon data was not coming in at the right speed.
            time.sleep(INTERVAL)

    # Process the raw packet data
    def process_packet(self, data):
        # Only captures non byte data
        if type(data) is not bytes:
            raise ValueError("Data must be a bytes object")

        if len(data) < 80:
            raise ValueError(
                f"Data length is not long enough for atleast 1 object: {len(data)} bytes"
            )

        offset = 0

        # Frame number: first 4 bytes (unsigned int)
        frame_number = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        # ItemsInBlock: next 1 byte (unsigned char)
        items_in_block = struct.unpack_from("<B", data, offset)[0]

        # Check if the first 5 bytes are integers
        if type(frame_number) is int and type(items_in_block) is int:
            self.count += 1
        else:
            raise ValueError(
                f"First 5 bytes are not integers. Invalid data may be received. data: {data}"
            )

        offset += 1
        objects = []
        # Loop through all items
        for i in range(items_in_block):
            # ItemHeader:ItemID: 1 byte (unsigned char)
            # item_id = struct.unpack_from("<B", data, offset)[0]
            offset += 1

            # ItemHeader:ItemDataSize: 2 bytes (unsigned short)
            # item_data_size = struct.unpack_from("<H", data, offset)[0]
            offset += 2

            # TrackerObject:ItemName: 24 bytes (char array)
            name_bytes = struct.unpack_from("<24s", data, offset)[0]
            offset += 24

            # TrackerObject:TransX: 8 bytes (double)
            trans_x = struct.unpack_from("<d", data, offset)[0]
            offset += 8

            # TrackerObject:TransY: 8 bytes (double)
            trans_y = struct.unpack_from("<d", data, offset)[0]
            offset += 8

            # TrackerObject:TransZ: 8 bytes (double)
            trans_z = struct.unpack_from("<d", data, offset)[0]
            offset += 8

            # TrackerObject:RotX: 8 bytes (double)
            rot_x = struct.unpack_from("<d", data, offset)[0]
            offset += 8

            # TrackerObject:RotY: 8 bytes (double)
            rot_y = struct.unpack_from("<d", data, offset)[0]
            offset += 8

            # TrackerObject:RotZ: 8 bytes (double)
            rot_z = struct.unpack_from("<d", data, offset)[0]
            offset += 8

            # Create and log TrackerObject
            obj = TrackerObject(
                name_bytes, trans_x, trans_y, trans_z, rot_x, rot_y, rot_z
            )

            objects.append(obj)

        return frame_number, objects


# Example usage
if __name__ == "__main__":
    # logger.add("udp_listener.log", rotation="10 MB", retention="10 days", level="DEBUG")

    udp_receiver = UDPPacketReceiver(host="127.0.0.1", port=51001)

    # Start the receiver in a separate thread
    udp_receiver.start()

    try:
        while True:
            pass  # Keep the main thread alive
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping UDP listener...")
        udp_receiver.stop()
