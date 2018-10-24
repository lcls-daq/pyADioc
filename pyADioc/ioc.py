import os
import db
import sys
import time
import daqts
import logging
import argparse
import threading
import numpy as np

from admin import IocAdmin
from pcaspy import SimpleServer, Driver, Severity, Alarm


LOG = logging.getLogger('pyAD_ioc')
## LOGGING SETTINGS ##
MAX_BYTES = 104857600
BACKUP_COUNT = 5
FMT_STR = '[ %(asctime)s | %(levelname)-8s] %(message)s'
# IOC Settings
IOC_DATA = os.getcwd()


class CameraDriver(Driver):
    def __init__(self, pvdb, dtype, platform, readout_grp, interface, prefix, ioc_prefix, ioc_name, config_op=None):
        super(CameraDriver, self).__init__()
        self.run = True
        self.acq_count = 0
        self.prefix = prefix
        self.pvdb = pvdb
        self.dtype = dtype
        self.config_op = config_op
        self.need_conf = threading.Event()
        self.setParam('READOUT', readout_grp)
        self.setParam('PLATFORM', platform)
        self.ioc = IocAdmin(ioc_name, ioc_prefix, self, ioc_data=IOC_DATA)
        self.confpv = self.get_tagged_pvs('config')
        self.readonly = self.get_tagged_pvs('readonly')
        self.cmds = self.get_tagged_pvs('command')
        for pv in self.pvdb.keys():
            # remove the invalid state
            self.setParamStatus(pv, Alarm.NO_ALARM, Severity.NO_ALARM)

        self.configure(self.config)

        self.ts = daqts.make_timestamp_reader(platform, readout_grp, interface)
        self.cam_thread = threading.Thread(name="camera", target=self.acquire)
        self.cam_thread.setDaemon(True)
        self.cam_thread.start()

    def get_tagged_pvs(self, tag):
        tagged = []
        # main db
        for key, value in self.pvdb.iteritems():
            if value.get(tag, False):
                tagged.append(key)
        # iocAdmin db
        for key, value in self.ioc.pvdb.iteritems():
            if value.get(tag, False):
                tagged.append(key)
        return tagged

    def patch_ts(self, reason, fid):
        self.pvDB[reason].time.nsec = (self.pvDB[reason].time.nsec & ~0x1ffff) | (fid&0x1ffff)

    @property
    def config(self):
        return { name : self.getParam(name) for name in self.confpv }

    def configure(self, config):
        if self.config_op is not None:
            self.config_op(config)

    def acquire(self):
        LOG.info("Acquiring data")

        last_ts = None
        self.ts.start()

        try:
            while self.run:
                if self.need_conf.is_set():
                    LOG.info("Reconfiguring camera")
                    self.configure(self.config)
                    self.need_conf.clear()
                    LOG.info("Reconfigure complete")
                rows = self.getParam('IMAGE1:ArraySize1_RBV')
                cols = self.getParam('IMAGE1:ArraySize0_RBV')
                timeout = self.getParam('TIMEOUT')
                offset = self.getParam('OFFSET')
                scale = self.getParam('SCALE')
                try:
                    ts_data, cmd_data = self.ts.get(timeout=timeout)
                except daqts.TimeoutException:
                    LOG.debug("Waiting for daq ts timed out after %.1f s"%timeout)
                    continue
                evt_ts = ts_data.secs + ts_data.nsecs/1.e9
                LOG.debug(ts_data, cmd_data)

                frame = np.random.normal(offset, scale, (rows, cols)).astype(self.dtype)
                self.acq_count+=1

                # Update PV data
                self.setParam('FIDUCIAL', ts_data.high&0x1ffff)
                self.setParam('IMAGE1:ArrayData', frame)
                self.patch_ts('IMAGE1:ArrayData', ts_data.high)
                self.setParam('IMAGE1:ArrayData.NORD', frame.size)
                self.updatePVs()
        finally:
            self.ts.stop()

    def write(self, reason, value):
        status = True
        # take proper actions
        if reason in self.readonly:
            LOG.warn("The %s PV is read-only!", reason)
            status = False
        elif reason == 'SYSRESET':
            # the IOC should exit now
            self.run = False
        elif reason in self.cmds:
            status = getattr(self, reason.lower())(value)
        elif reason in self.confpv:
            # signal if a configuration PV has changed
            if value != self.getParam(reason):
                self.need_conf.set()

        # store the values
        if status:
            self.setParam(reason, value)
        return status

    def read(self, reason):
        if hasattr(self.ioc, reason.lower()):
            return getattr(self.ioc, reason.lower())()
        else:
            return self.getParam(reason)

    def shutdown(self):
        LOG.info("Waiting for camera to exit acquistion")
        self.cam_thread.join()
        LOG.info("Camera exitted acquistion")


def parse_cli():
    default_log = 'INFO'
    MIN_PLATFORM = 0
    MAX_PLATFORM = 4

    parser = argparse.ArgumentParser(
        description='Simulated camera IOC application'
    )

    parser.add_argument(
        'camera_type',
        metavar='CAMTYPE',
        help='The camera type to simulate'
    )

    parser.add_argument(
        'prefix',
        metavar='PV_PREFIX',
        help='The PV prefix to use for the IOC'
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
        '-n',
        '--name',
        metavar='IOC_NAME',
        default=None,
        help='The name of the IOC instance - this is needed for autosave (default: None)'
    )

    parser.add_argument(
        '--log-level',
        metavar='LOG_LEVEL',
        default=default_log,
        help='the logging level of the client (default %s)'%default_log
    )

    parser.add_argument(
        '--log-file',
        metavar='LOG_FILE',
        help='an optional file to write the log output to'
    )

    return parser.parse_args()


def check_prefix(prefix):
    if prefix is None:
        return prefix
    else:
        if prefix.endswith(':'):
            return prefix
        else:
            return prefix + ':'


def run_ioc(camera_type, ioc_name, prefix, platform, readout_grp, interface):
    LOG.info('%s camera server, abort with Ctrl-C', camera_type)
    ioc_prefix = "IOC:%s"%prefix
    pvdb = db.init(camera_type)
    if pvdb is None:
        LOG.error('Unsupported camera type: %s', camera_type)
        return 2

    dtype = db.get_dtype(camera_type)

    os.environ['EPICS_CA_MAX_ARRAY_BYTES'] = str(db.get_max_array_size(camera_type))

    server = SimpleServer()
    server.createPV(prefix, pvdb)
    server.createPV(ioc_prefix, IocAdmin.ioc_pvdb)
    driver = CameraDriver(pvdb, dtype, platform, readout_grp, interface, prefix, ioc_prefix, ioc_name)
    LOG.debug('%s camera server is now started', camera_type)
    try:
        while driver.run:
            try:
                # process CA transactions
                server.process(0.1)
            except KeyboardInterrupt:
                LOG.info('%s camera server stopped by console interrupt!', camera_type)
                driver.run = False
    finally:
        # process CA transactions
        server.process(0.1)
        server.process(0.1)
        # why 2? only psi knows...
        driver.shutdown()
        # do a final autosave
        driver.ioc.shutdown()

    # If we get here the server died in an unexpected way
    if driver.run:
        LOG.error('%s camera server exited unexpectedly!', camera_type)
        return 1
    else:
        LOG.info('%s camera server exited normally', camera_type)
        return 0


def main():
    args = parse_cli()
    prefix = check_prefix(args.prefix)

    # Setup up the logging client
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(format=FMT_STR, level=log_level)
    if args.log_file is not None:
        log_fmt = logging.Formatter(FMT_STR)
        file_handler = RotatingFileHandler(args.log_file, MAX_BYTES, BACKUP_COUNT)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(log_fmt)
        LOG.addHandler(file_handler)

    return run_ioc(args.camera_type, args.name, prefix, args.platform, args.readout, args.interface)


if __name__ == '__main__':
    sys.exit(main())
