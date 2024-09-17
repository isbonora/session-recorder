import socket
import struct
import threading
from loguru import logger

# Class to represent each TrackerObject as defined in your packet
class TrackerObject:
    def __init__(self, name_bytes, trans_x, trans_y, trans_z, rot_x, rot_y, rot_z):
        # Decode the object name from bytes
        self.name = name_bytes.split(b'\x00', 1)[0].decode('utf-8')
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
        return (f"TrackerObject(name='{self.name}', "
                f"trans_x={self.trans_x:.3f}, trans_y={self.trans_y:.3f}, trans_z={self.trans_z:.3f}, "
                f"rot_x={self.rot_x:.4f}, rot_y={self.rot_y:.4f}, rot_z={self.rot_z:.4f})")


# Class to handle the UDP packet reception
class UDPPacketReceiver:
    def __init__(self, host='localhost', port=5005, database=None):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.running = True
        self.database = database

    # Start the packet listener in its own thread
    def start(self):
        logger.info(f"Starting UDP listener on {self.host}:{self.port}")
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.thread.start()

    # Stop the listener
    def stop(self):
        logger.info("Stopping UDP listener...")
        self.running = False
        self.thread.join()

    # Listen for incoming packets and process them
    def listen(self):
        logger.info(f"Listening for UDP packets on {self.host}:{self.port}")
        while self.running:
            data, addr = self.sock.recvfrom(1024)  # Buffer size
            self.process_packet(data)

    # Process the raw packet data
    def process_packet(self, data):
        offset = 0

        # Frame number: first 4 bytes (unsigned int)
        frame_number = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        # ItemsInBlock: next 1 byte (unsigned char)
        items_in_block = struct.unpack_from('<B', data, offset)[0]
        offset += 1
        objects = []
        # Loop through all items
        for i in range(items_in_block):
            # ItemHeader:ItemID: 1 byte (unsigned char)
            item_id = struct.unpack_from('<B', data, offset)[0]
            offset += 1

            # ItemHeader:ItemDataSize: 2 bytes (unsigned short)
            item_data_size = struct.unpack_from('<H', data, offset)[0]
            offset += 2

            # TrackerObject:ItemName: 24 bytes (char array)
            name_bytes = struct.unpack_from('<24s', data, offset)[0]
            offset += 24

            # TrackerObject:TransX: 8 bytes (double)
            trans_x = struct.unpack_from('<d', data, offset)[0]
            offset += 8

            # TrackerObject:TransY: 8 bytes (double)
            trans_y = struct.unpack_from('<d', data, offset)[0]
            offset += 8

            # TrackerObject:TransZ: 8 bytes (double)
            trans_z = struct.unpack_from('<d', data, offset)[0]
            offset += 8

            # TrackerObject:RotX: 8 bytes (double)
            rot_x = struct.unpack_from('<d', data, offset)[0]
            offset += 8

            # TrackerObject:RotY: 8 bytes (double)
            rot_y = struct.unpack_from('<d', data, offset)[0]
            offset += 8

            # TrackerObject:RotZ: 8 bytes (double)
            rot_z = struct.unpack_from('<d', data, offset)[0]
            offset += 8

            # Create and log TrackerObject
            obj = TrackerObject(name_bytes, trans_x, trans_y, trans_z, rot_x, rot_y, rot_z)
            
            objects.append(obj)
        
        # Log the objects to the database
        if self.database:
            self.database.insert_frame_objects(frame_number, objects)
            


# Example usage
if __name__ == "__main__":
    # logger.add("udp_listener.log", rotation="10 MB", retention="10 days", level="DEBUG")

    udp_receiver = UDPPacketReceiver(host='127.0.0.1', port=51001)
    
    # Start the receiver in a separate thread
    udp_receiver.start()
    
    try:
        while True:
            pass  # Keep the main thread alive
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping UDP listener...")
        udp_receiver.stop()