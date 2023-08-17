##########################################################
# Neo Indicator
#
# Urs Utzinger, Spring 2023
###########################################################
import zmq
import msgpack
import logging

###########################################################
# Constants
###########################################################

ZMQPORT  = 5556
ZMQTIMEOUT = 1000 # ms

from neoindicator import neoData, neoshow

##############################################################################################
# MAIN
##############################################################################################

if __name__ == '__main__':
    
    # Setup logging
    logger = logging.getLogger(__name__)

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

    logger.log(logging.INFO, 'Turning on light')

    context = zmq.asyncio.Context()      
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{}".format(self.args.zmqport))

    data_neo  = neoData(show=neoshow["on"] 
                        speed_left=0.0, 
                        speed_right=0.0, 
                        battery_left=0.0, 
                        battery_right=0.0)

    neo_msgpack = msgpack.packb(obj2dict(vars(data_neo)))
    socket.send_multipart([b"light", neo_msgpack])               

    logger.log(logging.INFO, 'Done')
