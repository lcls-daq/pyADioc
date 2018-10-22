import os
import socket
import fcntl
import struct
import select
import logging
import argparse
import multiprocessing as mp
import threading
import Queue
from collections import namedtuple

LOG = logging.getLogger('daqts')

MCAST_GRP_START = 16
MCAST_GRP = '239.255.16.%d'
MCAST_PORT = 10150
MIN_PLATFORM = 0
MAX_PLATFORM = 4

FMT_STR = '[ %(asctime)s | %(levelname)-8s] %(message)s'

ts_struct_pat = '=7L'
cmd_struct_pat = '=%dB'
TimeStamp = namedtuple('TimeStamp', 'nsecs secs low high group evr ncmds')

def get_ip_address(ifname):
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  return socket.inet_ntoa(fcntl.ioctl(
      s.fileno(),
      0x8915,  # SIOCGIFADDR
      struct.pack('256s', ifname[:15])
  )[20:24])

def parse_cli():
    default_log = 'INFO'

    parser = argparse.ArgumentParser(
        description='Script for receiving EVR multicasts'
    )

    parser.add_argument(
      '-p',
      '--platform',
      metavar='[%d-%d]'%(MIN_PLATFORM, MAX_PLATFORM),
      type=int,
      default=MIN_PLATFORM,
      choices=range(MIN_PLATFORM,MAX_PLATFORM+1),
      help='the DAQ platform (default: 0)'
    )

    parser.add_argument(
        '-r',
        '--readout',
        metavar='[0-7]',
        type=int,
        default=0,
        choices=range(0,8),
        help='the DAQ readout group (default: 0)'
    )

    parser.add_argument(
        '-i',
        '--interface',
        metavar='INTERFACE',
        default=None,
        help='the interface to bind the receiving socket to'
    )

    parser.add_argument(
        '--log-level',
        metavar='LOG_LEVEL',
        default=default_log,
        help='the logging level of the client (default %s)'%default_log
    )

    return parser.parse_args()

class TimeoutException(Exception):
    pass

class SocketReceive(object):
    def __init__(self,mcast_addr,mcast_port,readout_mask,dev):
        self.readout_grp_mask = readout_mask
        self.mcast_addr = mcast_addr
        self.mcast_port = mcast_port
        self.if_ip = None
        self.dev = dev
        if self.dev is not None:
            self.if_ip = get_ip_address(dev)
        self.sock = None
        self.pipe = mp.Pipe()
        self.enable = mp.Lock()
        self.ts_queue = mp.Queue()
        self.collecting = False

    def _recv(self, max):
        return self.sock.recv(max)

    def _recv_ts(self):
        data = self._recv(10240)
        ts_data = TimeStamp._make(struct.unpack(ts_struct_pat, data[:28]))
        cmd_data = struct.unpack(cmd_struct_pat%ts_data.ncmds, data[28:])
        return ts_data, cmd_data

    def listen(self):
        #create a UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        #allow other sockets to bind this port too
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #explicitly join the multicast group on the interface specified
        if self.if_ip is None:
            mreq = struct.pack("4sl", socket.inet_aton(self.mcast_addr), socket.INADDR_ANY)
        else:
            mreq = struct.pack("4s4s",socket.inet_aton(self.mcast_addr), socket.inet_aton(self.if_ip))
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        #finally bind the socket to start getting data into your socket
        self.sock.bind((self.mcast_addr, self.mcast_port))

        # setup the poller
        poller = select.poll()
        poller.register(self.sock, select.POLLIN)
        poller.register(self.pipe[0], select.POLLIN)

        # look for timestamps
        try:
            while self.collecting:
                events = poller.poll()
                for e in events:
                    if (e[0] == self.sock.fileno()) and (e[1] & select.POLLIN):
                        ts, cmd = self._recv_ts()
                        if ts.group & self.readout_grp_mask:
                            self.ts_queue.put((ts, cmd))
                    elif (e[0] == self.pipe[0].fileno()) and (e[1] & select.POLLIN):
                        msg = self.pipe[0].recv()
                        self.collecting = False
                    else:
                        pass
        except KeyboardInterrupt:
            pass
        finally:
            # close the socket
            self.sock.close()

    def get(self, timeout=None):
        try:
            return self.ts_queue.get(timeout=timeout)
        except Queue.Empty:
            raise TimeoutException("timeout after %.2f s"%timeout)

    def start(self):
        if not self.collecting:
            LOG.debug("Starting daq timestamp listener")
            with self.enable:
                self.collecting = True
                self.ts_proc = mp.Process(name="ts", target=self.listen)
                self.ts_proc.daemon = True
                self.ts_proc.start()

    def stop(self, wait=True):
        if self.collecting:
            LOG.debug("Stopping daq timestamp listener")
            with self.enable:
                self.collecting = False
                self.pipe[1].send("stop")
                self.ts_proc.join()

def make_timestamp_reader(platform, readout, interface=None):
    group = MCAST_GRP%(MCAST_GRP_START + platform)
    port = MCAST_PORT + platform #+ (readout * 16)
    return SocketReceive(group,port,1<<readout,interface)

def main(args):
    sock = make_timestamp_reader(args.platform, args.readout, args.interface)
    sock.start()
    LOG.info('Multicast receiver initialized - waiting for input...')

    while True:
        ts_data, cmd_data = sock.get()
        if ts_data.group & (1<<args.readout):
            LOG.info("%s Evr Commands %s", ts_data, cmd_data)

if __name__ == '__main__':
    args = parse_cli()
    # Setup up the logging client
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(format=FMT_STR, level=log_level)
    try:
        main(args)
    except KeyboardInterrupt:
        LOG.info('\nExitting client!')
