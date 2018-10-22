import os
import time
import json
import logging
import datetime
import threading

from pcaspy import Severity, Alarm

LOG = logging.getLogger(__name__)

# Default IOC Settings
IOC_DATA = '/reg/d/iocData'


class IocAdmin(object):
    ioc_pvdb = {
        'HEARTBEAT' : {
            'type' : 'int',
            'scan' : 1,
            'readonly' : True,
        },
        'TOD' : {
            'type' : 'string',
            'scan' : 1,
            'readonly' : True,
        },
        'STARTTOD' : {
            'type' : 'string',
            'readonly' : True,
        },
        'SYSRESET' : {
            'type' : 'int',
        },
    }

    def __init__(self, name, prefix, driver, ioc_data=None):
        self.run = True
        self.name = name
        self.prefix = prefix
        self.pvdb = IocAdmin.ioc_pvdb
        self.driver = driver
        if ioc_data is None:
            self.ioc_data = IOC_DATA
        else:
            self.ioc_data = ioc_data
        self.autosave = (name is not None)
        self.refresh = 5.0
        self.nSaved = 8
        self.type_map = {
            int    : "int",
            long   : "int",
            str    : "string",
            unicode: "char",
            float  : "float"
        }
        if self.autosave:
            LOG.info('Initializng autosave and restoring values')
            self.savereq = self.make_autosave_reqs()
            self.make_autosave_dir()
            if not self.load_values():
                LOG.error('Problem loading autosave file!')
            self.set_autosave_file()
            self.remove_oldest_file()
            self.make_pv_list()
        else:
            LOG.debug('Autosave not active - using passed parameters for host and platform')
        for pv in self.pvdb.keys():
            # remove the invalid state
            self.driver.setParamStatus(pv, Alarm.NO_ALARM, Severity.NO_ALARM)
        # Set up the IOC pvs
        self.start_int = int(time.time())
        self.start_str = self.tod()
        # start autosave thread if autosave is enabled
        if self.autosave:
            LOG.debug('Starting autosave thread')
            self.ioc_id = threading.Thread(target = self.runAuto)
            self.ioc_id.setDaemon(True)
            self.ioc_id.start()

    def date_str(self, dt):
        """Return a string representing a date from a datetime object."""
        return "{0:02}/{1:02}/{2:04} {3:02}:{4:02}:{5:02}".format(
                dt.month, dt.day, dt.year, dt.hour, dt.minute, dt.second)

    def tod(self):
        """Return the current time of day on this machine."""
        dt = datetime.datetime.now()
        return self.date_str(dt)

    def heartbeat(self):
        """Return the number of seconds this IOC has been running."""
        return int(time.time()) - self.start_int

    def starttod(self):
        """Return the time of day this IOC was last rebooted."""
        return self.start_str

    def pv_list_lines(self, prefix, d):
        """Helper function to get the lines for the IOC.pvlist file in make_pv_list."""
        lines = []
        for key, value in d.items():
            tp = value["type"]
            if tp == "int":
                epics_type = "longout"
            elif tp == "float":
                epics_type = "ao"
            else:
                epics_type = "stringout"
            PV = prefix + key
            lines.append("{0}, {1}".format(PV, epics_type))
        return lines

    def make_pv_list(self):
        """Writes the IOC.pvlist file in the iocInfo directory."""
        if self.name:
            file = "{0}/{1}/iocInfo/IOC.pvlist".format(self.ioc_data, self.name)
            lines = self.pv_list_lines(self.driver.prefix, self.driver.pvdb)
            ioc_lines = self.pv_list_lines(self.prefix, self.pvdb)
            try:
                all_lines = lines + ioc_lines
                with open(file, "w") as f:
                    for line in all_lines:
                        f.write(line + "\n")
            except StandardError as e:
                print "Error writing pv list. {0}".format(e)

    def make_autosave_reqs(self):
        LOG.debug('Deteriming autosave request list')
        reqs = []
        for key, value in self.driver.pvdb.iteritems():
            if value.get('autosave', False):
                LOG.debug('Found autosave request for %s%s', self.driver.prefix, key)
                reqs.append(key)
        LOG.debug('Found autosave requests for %d PVs', len(reqs))
        return reqs

    def make_autosave_dir(self):
        """Makes the autsave directory if it does not exist."""
        if self.name:
           self.my_dir = self.ioc_data + "/{0}/autosave".format(self.name)
        else:
            self.my_dir = "autosave_" + self.prefix.replace(":", "_").lower()
            if not os.path.exists(self.my_dir):
                os.mkdir(self.my_dir)
            elif not os.path.isdir(self.my_dir):
                raise IOError("Filename conflict for autosave directory")
        LOG.debug('Autosave directory: %s', self.my_dir)

    def set_autosave_file(self):
        """Picks a name for the autosave file."""
        date_string = str(datetime.datetime.now())
        valid_filename = date_string.replace(" ", "_").replace(":", "")
        truncated = valid_filename.split(".")[0]
        self.autosave_filename = "{0}/{1}.txt".format(self.my_dir, truncated)
        LOG.debug('Current autosave file: %s', self.autosave_filename)

    def save_values(self):
        """Serializes all values into a JSON object."""
        try:
            LOG.debug('Starting autosave update')
            value_dict = {}
            for reason in self.savereq:
                value_dict[reason] = self.driver.getParam(reason)
            with open(self.autosave_filename, "w") as f:
                f.write(json.dumps(value_dict, sort_keys = True, indent = 4) + "\n")
            LOG.debug('Autosave update completed')
        except StandardError as e:
            LOG.error('Autosave error: %s', e)

    def load_values(self, i=-1):
        """Loads all values from the most recent JSON serialization."""
        save_files = self.list_autosaves()
        if len(save_files) == 0:
            return False
        most_recent = save_files[i]
        try:
            LOG.debug("Opening autosave file: %s/%s", self.my_dir, most_recent)
            with open("{0}/{1}".format(self.my_dir, most_recent), "r") as f:
                value_dict = json.load(f)
            loaded_something = False
            loaded_count = 0
            for reason, value in value_dict.items():
                try:
                    expected_type = self.driver.pvdb[reason]["type"]
                    value_type = self.type_map[type(value)]
                    if value_type == expected_type or (expected_type == 'enum' and value_type == 'int'):
                        self.driver.setParam(reason, value)
                        loaded_count += 1
                        loaded_something = True
                        LOG.debug('Autosave restored %s to a value of %s', reason, value)
                    else:
                        error = "Saved value for {} is type ".format(reason)
                        error += "{} instead of expected ".format(value_type)
                        error += "type {}. Skipping...".format(expected_type)
                        raise TypeError(error)
                except Exception as exc:
                    LOG.error('Could not load value for %s. %s', reason, exc)
            LOG.info('Autosave restored %d of %d values', loaded_count, len(self.savereq))
            did_work = loaded_something
            if not did_work:
                raise IOError('All values in autosave were invalid.')
        except Exception as exc:
            LOG.error('Could not load values. %s', exc)
            if abs(i) >= len(save_files):
                LOG.warning('No more valid files to load.')
                did_work = False
            else:
                LOG.warning('Trying older autosave...')
                did_work = self.load_values(i-1)
        return did_work

    def list_autosaves(self):
        """Returns a list of files in the autosave folder."""
        flist = [f for f in os.listdir(self.my_dir)
                if os.path.isfile("{0}/{1}".format(self.my_dir, f))]
        flist.sort()
        return flist

    def remove_oldest_file(self):
        """Removes old autosaves until we have the max number of files."""
        save_files = self.list_autosaves()
        while len(save_files) > self.nSaved:
            oldest = save_files[0]
            LOG.debug("Removing old autosave file: %s/%s", self.my_dir, oldest)
            os.remove("{0}/{1}".format(self.my_dir, oldest))
            save_files = self.list_autosaves()

    def shutdown(self):
        if self.autosave:
            LOG.debug('Autosave shutdown requested')
            self.run = False
            self.ioc_id.join()

    def runAuto(self):
        while self.run:
            time.sleep(self.refresh)
            self.save_values()
        LOG.debug('Autosave thread exitting...')

