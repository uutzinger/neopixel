##########################################################
# Neo Indicator
#
# Urs Utzinger, Spring 2023
###########################################################

import math
import board
import neopixel
import asyncio
import logging
import zmq
import argparse
import os

###########################################################
# Configs for NEOPIXEL strip(s)
###########################################################

PIXEL_PIN   = board.D18      # pin that the NeoPixel is connected to
ORDER       = neopixel.RGBW  # pixel color channel order

NUMPIXELS   = 60             # total number of pixels in serially attached strips
BRIGHTNESS  = 0.75           # brightness of the pixels between 0.0 and 1.0 (should match your power supply)
INTERVAL    = 0.02           # update interval in seconds for animated displays

# I have one strip that runs along two sides of a board
# They are connected so half of the strip runs up on the left 
# and the other down the board on the other side.
START_LEFT  =  0             # first pixel I want to use on left strip
END_LEFT    = 29             # last pixel  on left strip
START_RIGHT = 30             # first pixel on right strip
END_RIGHT   = 59             # last pixel  on right strip

DISTANCE_PIXEL = 0.025      # distance between the individual pixels on the strip in meter
                            # If you want to indicate speed that simulates actual speed of board
                            # on ground you should enter the distance between the pixels here
BLOBWIDTH      = 6          # number of pixels for a running light blob 
MAXSPEED       = 15         # m/s 15*3600/1000 km/h, when you reach this speed, color will be 
                            # on max side of the rainbow spectrum

###########################################################
# Constants
###########################################################

TWOPI   = 2.0 * math.pi
PIHALF  = math.pi / 2.0
DEG2RAD = math.pi / 180.0
RAD2DEG = 180.0 / math.pi
EPSILON = 2.0*math.ldexp(1.0, -53)

# COLORS
WHT = (255, 255, 255,   0)  # color to  turn on to
RED = (255,   0,   0,   0)  # RED
GRN = (  0, 255,   0,   0)  # GREEN
BLU = (  0,   0, 255,   0)  # BLUE
BLK = (  0,   0,   0,   0)  # CLEAR

ZMQTIMEOUT = 1000 # ms

def colorwheel(pos):
    # RED, GREEN, BLUE, ?
    if pos < 0 or pos > 255: return (0, 0, 0, 0)                                     # out of range: off
    if pos < 85:             return (255 - pos * 3,       pos * 3,             0, 0) # min    red to green
    if pos < 170: pos -= 85; return (            0, 255 - pos * 3,       pos * 3, 0) # medium green to blue
    pos -= 170;              return (      pos * 3,             0, 255 - pos * 3, 0) # max    blue to white

# We have following static and dynamic pixel displays
# Speed: a blob of light runs along the strip at the indicated speed, color changes with speed
# Battery: a battery gage is displayed with green indicating remaining chanrge
# Rainbow: a rainbow runs along the strip
# Off: all pixels are off
# On: all pixels are on
# Hum: white light intensity on all pixels fluctuates
# Stop: exit program
neoshow = {"speed": 1, "battery": 2, "rainbow": 3, "stop": 4, "off": 5 , "on": 6, 'hum':7}

class neoData(object):
    '''
    Neopixel data
    Sent/Received via ZMQ to control light display
    '''
    def __init__(self,
                 show: int = neoshow["off"],
                 speed_left: float = 0.0,
                 speed_right: float = 0.0,
                 battery_left: float = 0.0,
                 battery_right: float = 0.0) -> None:
        self.show          = show                   # Show indicator
        self.speed_left    = speed_left             # Speed on left wheel
        self.speed_right   = speed_right            # Speed on right wheel
        self.battery_left  = battery_left           # Battery indicator for main battery
        self.battery_right = battery_right          # Battery indicator for remote battery

class NeoIndicator():
    '''
    Neo Indicator
    Provides simple routines to handle neopixel display
    We have two strips connected serially, one on the left side and one on the right side, the directions are opposite
    - On to turn on all pixels to white
    - Off to turn off all pixels
    - Rainbow to create rainbow animation
    - Speed to create speed indicator
    - Battery to create battery indicator
    '''
    def __init__(self):
        self.brightness = BRIGHTNESS
        self.pixels = neopixel.NeoPixel(PIXEL_PIN, NUMPIXELS, brightness=BRIGHTNESS, auto_write=False, pixel_order=ORDER)

    def brightness(self, brightness):
        self.brightness = brightness
        self.pixels = neopixel.NeoPixel(PIXEL_PIN, NUMPIXELS, brightness=self.brightness, auto_write=False, pixel_order=ORDER)

    def clear(self):
        self.pixels.fill(BLK)
        self.pixels.show()

    def white(self):
        self.pixels.fill(WHT)
        self.pixels.show()

    def battery(self, level_left:float, level_right:float):
        END_GREEN_LEFT  = START_LEFT +int((END_LEFT-START_LEFT+1)*level_left)
        END_GREEN_RIGHT = START_RIGHT+int((END_RIGHT-START_RIGHT+1)*(1.-level_right))
        for pixel in range(0,                 START_LEFT):        self.pixels[pixel] = BLK
        for pixel in range(END_LEFT+1,        START_RIGHT):       self.pixels[pixel] = BLK
        for pixel in range(END_RIGHT+1,       NUMPIXELS):         self.pixels[pixel] = BLK
        for pixel in range(START_LEFT,        END_GREEN_LEFT+1):  self.pixels[pixel] = GRN
        for pixel in range(END_GREEN_LEFT+1,  END_LEFT+1):        self.pixels[pixel] = RED
        for pixel in range(END_GREEN_RIGHT+1, END_RIGHT+1):       self.pixels[pixel] = GRN
        for pixel in range(START_RIGHT,       END_GREEN_RIGHT+1): self.pixels[pixel] = RED
        self.pixels.show()

    async def rainbow_start(self, stop_event: asyncio.Event, pause_event: asyncio.Event):
        LEFT_LENGTH  = END_LEFT  - START_LEFT  +1
        RIGHT_LENGTH = END_RIGHT - START_RIGHT +1
        left_list  = list(range(START_LEFT, END_LEFT + 1, 1))
        right_list = list(range(END_RIGHT, START_RIGHT - 1, -1))
        color = 0
        
        while not stop_event.is_set():
            if not pause_event.is_set():
                color += 1
                if color > 255: color = 0
                for pixel in left_list:
                    color_index = ((pixel-START_LEFT) * 256 // LEFT_LENGTH) + color * 5
                    self.pixels[pixel] = colorwheel(color_index & 255)
                for pixel in right_list:
                    color_index = ((END_RIGHT-pixel) * 256 // RIGHT_LENGTH) + color * 5
                    self.pixels[pixel] = colorwheel(color_index & 255)
                self.pixels.show()
                await asyncio.sleep(INTERVAL)
            else:
                await asyncio.sleep(0.2)

    async def hum_start(self, stop_event: asyncio.Event, pause_event: asyncio.Event):
        left_list  = list(range(START_LEFT, END_LEFT + 1, 1))
        right_list = list(range(END_RIGHT, START_RIGHT - 1, -1))
        intensity = 50
        while not stop_event.is_set():
            if not pause_event.is_set():
                intensity += 1
                if intensity > 255: intensity = 50
                for pixel in left_list:
                    self.pixels[pixel] = ( intensity, intensity, intensity, 0 )
                for pixel in right_list:
                    self.pixels[pixel] = ( intensity, intensity, intensity, 0 )
                self.pixels.show()
                await asyncio.sleep(INTERVAL)
            else:
                await asyncio.sleep(0.2)
    
    def speed_update(self, speed_left:float, speed_right:float):
        self.speed_left  = speed_left
        self.speed_right = speed_right
        self.blob_location_left_inc  =  speed_left  *INTERVAL/DISTANCE_PIXEL
        self.blob_location_right_inc = -speed_right *INTERVAL/DISTANCE_PIXEL 
        self.color_left  = colorwheel(int(abs(speed_left)/MAXSPEED*255))
        self.color_right = colorwheel(int(abs(speed_right)/MAXSPEED*255)) 
        
    async def speed_start(self, speed_left:float, speed_right:float, stop_event: asyncio.Event, pause_event: asyncio.Event):
        self.blob_location_left  = START_LEFT
        self.blob_location_right = END_RIGHT
        self.blob_location_left_inc  =  speed_left  *INTERVAL/DISTANCE_PIXEL
        self.blob_location_right_inc = -speed_right *INTERVAL/DISTANCE_PIXEL 
        LEFT_LENGTH  = END_LEFT  - START_LEFT +1
        RIGHT_LENGTH = END_RIGHT - START_RIGHT +1
        self.color_left  = colorwheel(int(abs(speed_left)/MAXSPEED*255))
        self.color_right = colorwheel(int(abs(speed_right)/MAXSPEED*255)) 

        while not stop_event.is_set():
            if not pause_event.is_set():
                self.pixels.fill(BLK) # clear pixel buffer
                self.blob_location_left  += self.blob_location_left_inc          # light loc left
                self.blob_location_right += self.blob_location_right_inc         # light loc right
                bl = int(self.blob_location_left  % LEFT_LENGTH)  + START_LEFT   # make sure we stay in range
                br = int(self.blob_location_right % RIGHT_LENGTH) + START_RIGHT  # make sure we stay in range
                
                # create light blob on left side
                if speed_left > 0:
                    inten_inc = 1./(BLOBWIDTH)
                    inten = 0.0
                    for pixel in range(bl-BLOBWIDTH+1,bl+1):
                        if (pixel < START_LEFT): pixel = END_LEFT - (START_LEFT - pixel) +1
                        ic = inten**3
                        self.pixels[pixel] = ( int(self.color_left[0]*ic), 
                                               int(self.color_left[1]*ic), 
                                               int(self.color_left[2]*ic), 
                                               int(self.color_left[3]*ic) )
                        inten += inten_inc 
                else:
                    inten = 1.0
                    inten_inc =  -1./(BLOBWIDTH)
                    for pixel in range(bl,bl+BLOBWIDTH):
                        if (pixel > END_LEFT):  pixel = START_LEFT + (pixel - END_LEFT) -1
                        ic = inten**3
                        self.pixels[pixel] = ( int(self.color_left[0]*ic), 
                                               int(self.color_left[1]*ic), 
                                               int(self.color_left[2]*ic), 
                                               int(self.color_left[3]*ic) )
                        print(bl, pixel, ic)
                        inten += inten_inc

                # create light block or right side, runs backwards
                if speed_right > 0:
                    inten_inc = 1./(BLOBWIDTH)
                    inten = 0.0
                    for pixel in range(br-BLOBWIDTH+1,br+1):
                        if (pixel < START_RIGHT): pixel = END_RIGHT - (START_RIGHT - pixel) +1
                        ic = inten**3
                        self.pixels[pixel] = ( int(self.color_right[0]*ic), 
                                               int(self.color_right[1]*ic), 
                                               int(self.color_right[2]*ic), 
                                               int(self.color_right[3]*ic) )
                        inten += inten_inc 
                else:
                    inten = 1.0
                    inten_inc =  -1./(BLOBWIDTH)
                    for pixel in range(br,br+BLOBWIDTH):
                        if (pixel > END_RIGHT):  pixel = START_RIGHT + (pixel - END_RIGHT) -1
                        ic = inten**3
                        self.pixels[pixel] = ( int(self.color_right[0]*ic), 
                                               int(self.color_right[1]*ic), 
                                               int(self.color_right[2]*ic), 
                                               int(self.color_right[3]*ic) )
                        print(br, pixel, ic)
                        inten += inten_inc

                self.pixels.show()
                await asyncio.sleep(INTERVAL)
            else:
                await asyncio.sleep(0.2)

#########################################################################################################
# ZMQ Data Receiver for Neo Pixels
#########################################################################################################

class zmqWorkerNeo():

    def __init__(self, logger, zmqPort='tcp://localhost:5556', parent=None):
        super(zmqWorkerNeo, self).__init__(parent)

        self.dataReady =  asyncio.Event()
        self.finished  =  asyncio.Event()
        self.dataReady.clear()
        self.finished.clear()

        self.logger     = logger
        self.finish_up  = False
        self.paused     = False
        self.zmqPort    = zmqPort

        self.new_neo    = False
        self.timeout    = False

        self.zmqTimeout = ZMQTIMEOUT
        
        self.data_neo = neoData()

        self.logger.log(logging.INFO, 'IC20x zmqWorker initialized')

    async def start(self, stop_event: asyncio.Event):

        self.new_neo = False

        context = zmq.Context()
        poller  = zmq.Poller()
        
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"light")
        socket.connect(self.zmqPort)
        poller.register(socket, zmq.POLLIN)

        self.logger.log(logging.INFO, 'Neopixel  zmqWorker started on {}'.format(self.zmqPort))

        while not stop_event.is_set():
            try:
                events = dict(poller.poll(timeout=self.zmqTimeout))
                if socket in events and events[socket] == zmq.POLLIN:
                    response = socket.recv_multipart()
                    if len(response) == 2:
                        [topic, msg_packed] = response
                        if topic == b"light":
                            msg_dict = msgpack.unpackb(msg_packed)
                            self.data_neo = dict2obj(msg_dict)
                            self.new_neo = True
                        else:
                            pass  # not a topic we need
                    else:
                        self.logger.log(
                            logging.ERROR, 'Neopixels zmqWorker malformed message')
                else:  # ZMQ TIMEOUT
                    self.logger.log(logging.ERROR, 'Neopixels zmqWorker timed out')
                    poller.unregister(socket)
                    socket.close()
                    socket = context.socket(zmq.SUB)
                    socket.setsockopt(zmq.SUBSCRIBE, b"light")
                    socket.connect(self.zmqPort)
                    poller.register(socket, zmq.POLLIN)
                    self.new_neo = False

                if (self.new_neo):
                    self.dataReady.set()
                    self.new_neo  = False
                else:
                    pass

            except:
                self.logger.log(logging.ERROR, 'Neopixels zmqWorker error')
                poller.unregister(socket)
                socket.close()
                socket = context.socket(zmq.SUB)
                socket.setsockopt(zmq.SUBSCRIBE, b"light")
                socket.connect(self.zmqPort)
                poller.register(socket, zmq.POLLIN)
                self.new_neo = False

        self.logger.log(logging.DEBUG, 'Neopixels zmqWorker finished')
        socket.close()
        context.term()
        self.finished.set()

    def set_zmqPort(self, port):
        self.zmqPort = port

    async def handle_termination(self, tasks:None):
        '''
        Cancel slow tasks based on provided list (speed up closing of program)
        '''
        self.logger.log(logging.INFO, 'Controller ESC, Control-C or Kill signal detected')
        if tasks is not None: # This will terminate tasks faster
            self.logger.log(logging.INFO, 'Cancelling all Tasks...')
            await asyncio.sleep(1) # give some time for tasks to finish up
            for task in tasks:
                if task is not None:
                    task.cancel()

##############################################################################################
# MAIN
##############################################################################################

async def main(args: argparse.Namespace):

    speed_stop_event  = asyncio.Event()    
    speed_pause_event = asyncio.Event()
    speed_stop_event.clear()
    speed_pause_event.set()

    rainbow_stop_event = asyncio.Event()    
    rainbow_pause_event = asyncio.Event()
    rainbow_stop_event.clear()
    rainbow_pause_event.set()

    hum_stop_event = asyncio.Event()    
    hum_pause_event = asyncio.Event()
    hum_stop_event.clear()
    hum_pause_event.set()
        
    # Setup logging
    logger = logging.getLogger(__name__)
    logger.log(logging.INFO, 'Starting Neopixel...')

    # ICM IMU
    neo = NeoIndicator(logger=logger, args=args)
    zmq = zmqWorkerNeo(logger=logger, zmqPort=args.zmqPort)

    # Create all the async tasks
    # They will run until stop signal is created

    speed_task   = asyncio.create_task(neo.speed_start(speed_left=0.0, speed_right=0.0, stop_event=speed_stop_event, pause_event=speed_pause_event))
    rainbow_task = asyncio.create_task(neo.rainbow_start(stop_event=rainbow_stop_event, pause_event=rainbow_pause_event))
    hum_task      = asyncio.create_task(neo.hum_start(stop_event=hum_stop_event, pause_event=hum_pause_event))
        
    tasks = [speed_task, rainbow_task, hum_task] # frequently updated tasks

    # Set up a Control-C handler to gracefully stop the program
    # This mechanism is only available in Unix
    if os.name == 'posix':
        # Get the main event loop
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT,  lambda: asyncio.create_task(neo.handle_termination(tasks=tasks)) ) # control-c
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(neo.handle_termination(tasks=tasks)) ) # kill

    # Main Loop for ZMQ messages, 
    # Set lights according to ZMQ message we received

    while not zmq.finished.is_set():
        if zmq.dataReady.is_set():
            zmq.dataReady.clear()
        
            if zmq.data_neo.show == neoshow["rainbow"]:
                # pause all animations
                speed_pause_event.set()
                rainbow_pause_event.set()
                hum_pause_event.set()
                # clear all pixes
                neo.clear()
                # start rainbow
                rainbow_pause_event.clear()
            elif zmq.data_neo.show == neoshow["battery"]:
                # pause all animations
                rainbow_pause_event.set()
                speed_pause_event.set()
                hum_pause_event.set()
                # set static battery display
                neo.battery(level_left=zmq.data_neo.battery_left, level_right=zmq.data_neo.battery_right)                
            elif zmq.data_neo.show == neoshow["speed"]:
                # pause all animations
                rainbow_pause_event.set()
                speed_pause_event.set()
                hum_pause_event.set()
                # clear all pixes
                neo.clear()
                # start speed indicator
                neo.speed_update(speed_left=zmq.data_neo.speed_left, speed_right=zmq.data_neo.speed_right)
            elif zmq.data_neo.show == neoshow["stop"]:
                # exit program
                # stop all animations
                rainbow_stop_event.set()
                speed_stop_event.set()
                hum_stop_event.set()
                # unpause all animations so they can terminate
                rainbow_pause_event.clear()
                speed_pause_event.clear()
                hum_stop_event.clear()
                # Make sure lights are off
                neo.clear()
            elif zmq.data_neo.show == neoshow["off"]:
                # pause all animations
                rainbow_pause_event.set()
                speed_pause_event.set()
                hum_pause_event.set()
                # All lights off
                neo.clear()
            elif zmq.data_neo.show == neoshow["on"]:
                # pause all animations
                rainbow_pause_event.set()
                speed_pause_event.set()
                hum_pause_event.set()
                # all lights on
                neo.white()
            elif zmq.data_neo.show == neoshow["hum"]:
                # paus all animations
                speed_pause_event.set()
                rainbow_pause_event.set()
                hum_pause_event.set()
                # clear all pixes
                neo.clear()
                # start hum indicator
                hum_pause_event.clear()
                
        await asyncio.sleep(0.02)

    # Wait until all tasks are completed, which is when user wants to terminate the program
    await asyncio.wait(tasks, timeout=float('inf'))

    logger.log(logging.INFO,'Neopixel exit')

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help='sets the log level from info to debug',
        default = False
    )

    parser.add_argument(
        '-z',
        '--zmq',
        dest = 'zmqport',
        type = int,
        metavar='<zmqport>',
        help='port used by ZMQ, e.g. \'tcp://10.0.0.2:5556\'',
        default = 'tcp://localhost:5556'
    )

    args = parser.parse_args()
        
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        # format='%(asctime)-15s %(name)-8s %(levelname)s: %(message)s'
        format='%(asctime)-15s %(levelname)s: %(message)s'
    )   
    
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
