# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and 
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2017, Baycrest Centre for Geriatric Care ("Baycrest") and others
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#

"""
.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
"""

import os
import csv
import sys
import json
import datetime
import uuid
import urllib.request, urllib.parse, urllib.error
import numpy
import six
from tvb.basic.profile import TvbProfile
from tvb.basic.logger.builder import get_logger
from tvb.core.decorators import user_environment_execution

MATLAB = "matlab"
OCTAVE = "octave"

CHAR_SEPARATOR = "__"
CHAR_SPACE = "--"
CHAR_DRIVE = "-DriVe-"
DRIVE_SEP = ":"
COMPLEX_TIME_FORMAT = '%Y-%m-%d,%H-%M-%S.%f'
# LESS_COMPLEX_TIME_FORMAT is also compatible with data exported from TVB 1.0. 
# This is only used as a fallback in the string to date conversion.
LESS_COMPLEX_TIME_FORMAT = '%Y-%m-%d,%H-%M-%S'
SIMPLE_TIME_FORMAT = "%m-%d-%Y"


################## PATH related methods start here ###############

def path2url_part(file_path):
    """
    Prepare a File System Path for passing into an URL.
    """
    if not os.path.isabs(file_path):
        file_path = os.path.join(TvbProfile.current.TVB_STORAGE, file_path)
    result = file_path.replace(os.sep, CHAR_SEPARATOR).replace(" ", CHAR_SPACE).replace(DRIVE_SEP, CHAR_DRIVE)
    return urllib.parse.quote(result)


def url2path(encoded_path):
    """
    Retrieve File System Path from encoded URL (inverse of path2url_part).
    """
    return encoded_path.replace(CHAR_SEPARATOR, os.sep).replace(CHAR_SPACE, " ").replace(CHAR_DRIVE, DRIVE_SEP)


def get_unique_file_name(storage_folder, file_name, try_number=0):
    """
    Compute non-existent file name, in storage_folder.
    Try file_name, and if already exists, try adding a number.
    """
    # TODO this method should be re-tought
    name, ext = os.path.splitext(file_name)
    date = str(datetime.datetime.now())
    date = date.replace(' ', '').replace(':', '').replace('.', '').replace('-', '')
    if try_number > 0:
        file_ = '%s-%s%s' % (name, date, ext)
    else:
        file_ = file_name
    full_path = os.path.join(storage_folder, file_)
    if os.path.exists(full_path):
        # Try another name, by appending the consecutive try_number
        return get_unique_file_name(storage_folder, file_name, try_number + 1)
    return full_path, file_


################## PATH related methods end here ###############    


################## FILE related methods start here ###############

def store_list_data(data_list, file_name, storage_folder, overwrite=False):
    """
    Write a list into a file using CSV writer.
    CSV writer, better than numpy, write also Strings
    """
    if not isinstance(data_list, (list, numpy.ndarray)):
        raise Exception("Invalid given type!! " + str(type(data_list)))
    if overwrite:
        full_path = os.path.join(storage_folder, file_name)
        file_name = os.path.split(full_path)[1]
    else:
        full_path, file_name = get_unique_file_name(storage_folder, file_name)

    # generic writer, capable to write strings also
    with open(full_path, 'wb') as destination:
        csv_writer = csv.writer(destination, delimiter=' ')
        if isinstance(data_list[0], (list, numpy.ndarray)):
            for row in data_list:
                csv_writer.writerow(row)
        else:
            csv_writer.writerow(data_list)

    return file_name


################## FILE related methods end here ###############  


################## CONVERT related methods start here ###############

def parse_json_parameters(parameters):
    """
    From JSON with Unicodes, return a dictionary having strings as keys.
    Loading from DB a JSON will return instead of string keys, unicodes.
    """
    params = json.loads(parameters)
    new_params = {}
    for key, value in six.iteritems(params):
        new_params[str(key)] = value
    return new_params


def string2date(string_input, complex_format=True, date_format=None):
    """Read date from string, after internal format"""
    if date_format is not None:
        return datetime.datetime.strptime(string_input, date_format)
    if complex_format:
        try:
            return datetime.datetime.strptime(string_input, COMPLEX_TIME_FORMAT)
        except ValueError:
            # For backwards compatibility with TVB 1.0
            return datetime.datetime.strptime(string_input, LESS_COMPLEX_TIME_FORMAT)
    return datetime.datetime.strptime(string_input, SIMPLE_TIME_FORMAT)


def date2string(date_input, complex_format=True, date_format=None):
    """Convert date into string, after internal format"""
    if date_input is None:
        return "None"

    if date_format is not None:
        return date_input.strftime(date_format)

    if complex_format:
        return date_input.strftime(COMPLEX_TIME_FORMAT)
    return date_input.strftime(SIMPLE_TIME_FORMAT)


def format_timedelta(timedelta, most_significant2=True):
    """
    Format a datetime.timedelta.
    :param timedelta: object timedelta to format
    :param most_significant2: Will show only the 2 most significant units (ex: hours, minutes). Default True.
    """
    days = timedelta.days
    hours, remainder = divmod(timedelta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    fragments = [str(days) + 'd', str(hours) + 'h', str(minutes) + 'm', str(seconds) + 's']

    if days:
        fragments = fragments[0:]
    elif hours:
        fragments = fragments[1:]
    elif minutes:
        fragments = fragments[2:]
    else:
        fragments = fragments[3:]

    if most_significant2:
        fragments = fragments[:2]

    return ' '.join(fragments)


def string2bool(string_input):
    """ Convert given string into boolean value."""
    string_input = str(string_input).lower()
    return string_input in ("yes", "true", "t", "1")


ARRAY_BEGIN = -1
DATA_UNCONVERTED = 1
DATA_CONVERTED = 2


def string2array(input_data_str, split_char, dtype=None):
    """
    Given an input string first try to load it using JSON and if that fails,
     meaning some weird array is given by the user, fall-back to _custom_string2array.
    """
    prepared_input_data_str = input_data_str.replace(split_char, ',')
    if not prepared_input_data_str.strip().startswith('['):
        # In case of range for a model parameter for example, the input string here is just a float
        # which will be converted to a 0-d numpy array instead of a 1-d array if brackets are missing.
        prepared_input_data_str = '[' + prepared_input_data_str.strip() + ']'
    try:
        array = json.loads(prepared_input_data_str)
        return numpy.array(array)
    except ValueError:
        logger = get_logger(__name__)
        logger.debug("Received input array %s is poorly formatted and could not be evaluated by Python."
                     "Falling back to _custom_string2array." % prepared_input_data_str)
        return _custom_string2array(input_data_str, split_char, dtype)


def _custom_string2array(input_data_str, split_char, dtype=None):
    """
    From a long string, parse a NumPy array.
    """

    class HelperData:
        """Helper for parsing arrays"""

        def __init__(self, data, type_):
            self.data = data
            self.type = type_

    input_str = input_data_str.lstrip().rstrip()
    to_replace = split_char + split_char
    while to_replace in input_str:
        input_str = input_str.replace(to_replace, split_char)
    input_str = input_str.replace('[' + split_char, '[')
    input_str = input_str.replace(split_char + ']', ']')
    input_str = input_str.replace(' ' + split_char, split_char)
    input_str = input_str.replace(split_char + ' ', split_char)
    input_str = input_str.replace('[ ', '[').replace(' ]', ']')

    str_pos = 0
    data_stack = []
    while str_pos < len(input_str):
        if input_str[str_pos] == '[':
            data_stack.append(HelperData('[', -1))
        elif input_str[str_pos] == split_char:
            if data_stack[-1].type == DATA_UNCONVERTED:
                if dtype is not None:
                    elem_type = dtype + "('" + data_stack[-1].data + "')"
                    data_stack[-1].data = eval(elem_type)
                data_stack[-1].type = DATA_CONVERTED
        elif input_str[str_pos] == ']':
            new_array = []
            if data_stack[-1].type == DATA_UNCONVERTED:
                if dtype is not None:
                    elem_type = dtype + "('" + data_stack[-1].data + "')"
                    data_stack[-1].data = eval(elem_type)
                data_stack[-1].type = DATA_CONVERTED
            while data_stack[-1].type != ARRAY_BEGIN:
                last_data = data_stack.pop()
                new_array.insert(0, last_data.data)
            data_stack.pop()
            new_array = HelperData(new_array, 0)
            data_stack.append(new_array)

        elif len(data_stack) == 0 or data_stack[-1].type != DATA_UNCONVERTED:
            data_stack.append(HelperData(input_str[str_pos], DATA_UNCONVERTED))
        else:
            data_stack[-1].data = data_stack[-1].data + input_str[str_pos]
        str_pos += 1
    if len(data_stack) == 0:
        return None

    if type(data_stack[0].data) is str:
        if dtype is not None:
            if data_stack[-1].data == 'None':
                return None
            elem_type = dtype + "('" + data_stack[-1].data + "')"
            data_stack[-1].data = eval(elem_type)
        return data_stack[0].data
    return numpy.array(data_stack[0].data)


class TVBJSONEncoder(json.JSONEncoder):
    """
    Custom encoder class. Referring towards "to_json" method, when found, or default behaviour otherwise.
    """

    def default(self, obj):
        if hasattr(obj, "to_json"):
            return obj.to_json()

        return json.JSONEncoder.default(self, obj)


################## CONVERT related methods end here ###############


################## MATLAB related method start here ###############

def get_matlab_executable():
    """
    Check If MATLAB is installed on current system.
    Return True or False.
    Return True, when MATLAB executable is found in Path.
    """
    matlab_exe_path = None
    if sys.platform.startswith('win'):
        split_char = ";"
        octave_exec = OCTAVE + ".exe"
        matlab_exec = MATLAB + ".exe"
    else:
        split_char = ":"
        octave_exec = OCTAVE
        matlab_exec = MATLAB
    logger = get_logger(__name__)
    logger.debug("Searching Matlab in path: " + str(os.environ["PATH"]))
    for path in os.environ["PATH"].split(split_char):
        if os.path.isfile(os.path.join(path, matlab_exec)):
            matlab_exe_path = os.path.join(path, matlab_exec)
            logger.debug("MATLAB was found:" + path)
            return matlab_exe_path
    for path in os.environ["PATH"].split(split_char):
        if os.path.isfile(os.path.join(path, octave_exec)):
            logger.debug("OCTAVE was found:" + path)
            matlab_exe_path = os.path.join(path, octave_exec)
            return matlab_exe_path
    return matlab_exe_path


@user_environment_execution
def check_matlab_version(matlab_path):
    """
    Try to get the current version of matlab from a given path.
    """
    version = None
    logger = get_logger(__name__)
    matlab_test_file_name = os.path.join(TvbProfile.current.TVB_STORAGE, 'test_mat_version')
    matlab_test_file = matlab_test_file_name + '.m'
    matlab_log_file = os.path.join(TvbProfile.current.TVB_STORAGE, 'version_log.txt')

    try:
        matlab_version_txt = """tvb_checking_version = version
        quit()
        """
        with open(matlab_test_file, 'w') as file_p:
            file_p.write(matlab_version_txt)

        matlab_cmd(matlab_path, matlab_test_file_name, matlab_log_file)

        with open(matlab_log_file) as log_file:
            result_data = log_file.read()
        version = result_data.strip().split('tvb_checking_version')[1]
        version = version.replace('\n', '').strip()

        logger.debug("Response in TVB from: %s\n Version: %s \nOriginal %s" % (matlab_path, version, result_data))
        os.remove(matlab_test_file)
        os.remove(matlab_log_file)

    except Exception:
        logger.exception('Could not parse Matlab Version!')
        try:
            os.remove(matlab_test_file)
            os.remove(matlab_log_file)
        except Exception:
            logger.exception('Could not remove files in the second try...')

    return version


@user_environment_execution
def matlab_cmd(matlab_path, script_name, log_file):
    """
    Called in order to obtain the command for calling MATLAB
    """
    folder_path, exe_name = os.path.split(matlab_path)
    if folder_path not in os.environ['PATH']:
        os.environ['PATH'] = os.environ.get('PATH', '') + os.pathsep + folder_path
    if MATLAB in exe_name:
        base = exe_name + ' '
        opts = ' -nodesktop -nojvm -nosplash -logfile %s -r "run %s "' % (log_file, script_name)
        if os.name == 'nt':
            opts = '-minimize ' + opts
        command = base + opts
    else:  # if OCTAVE in exe_name:
        command = exe_name + ' %s.m >> %s' % (script_name, log_file)
    return os.system(command)


def extract_matlab_doc_string(file_n):
    """
    Extract the first doc entry from a matlab file.
    """
    try:
        with open(file_n) as m_file:
            m_data = m_file.read()
    except Exception:
        return "Description not available."

    doc_started_flag = False
    result = ""

    for row in m_data.split('\n'):
        if row.startswith('%'):
            doc_started_flag = True
            result += row.replace('%', '') + "<br/>"
        else:
            if len(row.strip()) == 0:
                result += "<br/>"
            else:
                if doc_started_flag:
                    break
    return str(result, errors="ignore")


################## MATLAB methods end here     ##############

################## GENERIC  methods start here ###############


def generate_guid():
    """ 
    Generate new Global Unique Identifier.
    This identifier should be unique per each station, 
    and unique for different machines.
    """
    return str(uuid.uuid1())


def format_bytes_human(size, si=False):
    """
    :param size: size in kilobytes
    :param si: if True use SI units (multiple of 1000 not 1024)
    :return: a String with [number] [memory unit measure]
    """
    if si:
        m = ['kB', 'MB', 'GB']
        base = 1000.0
    else:
        m = ['KiB', 'MiB', 'GiB']
        base = 1024.0

    exp = 0
    while size >= base and exp < len(m) - 1:
        size /= base
        exp += 1
    return "%.1f %s" % (size, m[exp])


def prepare_time_slice(total_time_length, max_length=10 ** 4):
    """
    Limit the time dimension when retrieving from TS.
    If total time length is greater than MAX, then retrieve only the last part of the TS

    :param total_time_length: TS time dimension
    :param max_length: limiting number of TS steps

    :return: python slice
    """

    if total_time_length < max_length:
        return slice(total_time_length)

    return slice(total_time_length - max_length, total_time_length)
