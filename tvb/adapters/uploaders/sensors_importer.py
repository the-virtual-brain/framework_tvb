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
.. moduleauthor:: Bogdan Neacsa <bogdan.neacsa@codemart.ro>
"""

import numpy
from tvb.adapters.uploaders.abcuploader import ABCUploader
from tvb.basic.logger.builder import get_logger
from tvb.core.adapters.exceptions import LaunchException
from tvb.datatypes.sensors import SensorsEEG, SensorsMEG, SensorsInternal
from tvb.core.entities.file.datatypes.sensors_h5 import SensorsH5
from tvb.core.entities.model.datatypes.sensors import SensorsIndex
from tvb.interfaces.neocom._h5loader import DirLoader


class Sensors_Importer(ABCUploader):
    """
    Upload Sensors from a TXT file.
    """ 
    _ui_name = "Sensors"
    _ui_subsection = "sensors_importer"
    _ui_description = "Import Sensor locations from TXT or BZ2"

    EEG_SENSORS = "EEG Sensors"
    MEG_SENSORS = "MEG sensors"
    INTERNAL_SENSORS = "Internal Sensors"
    logger = get_logger(__name__)


    def get_upload_input_tree(self):
        """
        Define input parameters for this importer.
        """
        return [{'name': 'sensors_file', 'type': 'upload', 'required_type': 'text/plain, .bz2',
                 'label': 'Please upload sensors file (txt or bz2 format)', 'required': True,
                 'description': 'Expected a text/bz2 file containing sensor measurements.'},
                
                {'name': 'sensors_type', 'type': 'select', 
                 'label': 'Sensors type: ', 'required': True,
                 'options': [{'name': self.EEG_SENSORS, 'value': self.EEG_SENSORS},
                             {'name': self.MEG_SENSORS, 'value': self.MEG_SENSORS},
                             {'name': self.INTERNAL_SENSORS, 'value': self.INTERNAL_SENSORS}]
                 }]

    def get_output(self):
        return [SensorsIndex]


    def launch(self, sensors_file, sensors_type):
        """
        Creates required sensors from the uploaded file.

        :param sensors_file: the file containing sensor data
        :param sensors_type: a string from "EEG Sensors", "MEG sensors", "Internal Sensors"

        :returns: a list of sensors instances of the specified type

        :raises LaunchException: when
                    * no sensors_file specified
                    * sensors_type is invalid (not one of the mentioned options)
                    * sensors_type is "MEG sensors" and no orientation is specified
        """
        if sensors_file is None:
            raise LaunchException("Please select sensors file which contains data to import")

        self.logger.debug("Create sensors instance")
        if sensors_type == self.EEG_SENSORS:
            sensors_inst = SensorsEEG()
        elif sensors_type == self.MEG_SENSORS:
            sensors_inst = SensorsMEG()
        elif sensors_type == self.INTERNAL_SENSORS:
            sensors_inst = SensorsInternal()
        else:
            exception_str = "Could not determine sensors type (selected option %s)" % sensors_type
            raise LaunchException(exception_str)
            
        locations = self.read_list_data(sensors_file, usecols=[1, 2, 3])

        # NOTE: TVB has the nose pointing -y and left ear pointing +x
        # If the sensors are in CTF coordinates : nose pointing +x left ear +y
        # to rotate the sensors by -90 along z uncomment below
        # locations = numpy.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]]).dot(locations.T).T
        sensors_inst.locations = locations
        sensors_inst.labels = self.read_list_data(sensors_file, dtype=numpy.str, usecols=[0])
        sensors_inst.number_of_sensors = sensors_inst.labels.size

        if isinstance(sensors_inst, SensorsMEG):
            try:
                sensors_inst.orientations = self.read_list_data(sensors_file, usecols=[4, 5, 6])
                sensors_inst.has_orientation = True
            except IndexError:
                raise LaunchException("Uploaded file does not contains sensors orientation.")
         
        self.logger.debug("Sensors instance ready to be stored")

        sensors_idx = SensorsIndex()
        sensors_idx.gid = sensors_inst.gid.hex  # TODO: keep GID on HasTraitsIndex
        sensors_idx.number_of_sensors = sensors_inst.number_of_sensors
        sensors_idx.sensors_type = sensors_inst.sensors_type

        loader = DirLoader(self.storage_path)
        sensors_path = loader.path_for(SensorsH5, sensors_idx.gid)
        sensors_h5 = SensorsH5(sensors_path)

        sensors_h5.sensors_type.store(sensors_inst.sensors_type)
        sensors_h5.labels.store(sensors_inst.labels)
        sensors_h5.locations.store(sensors_inst.locations)
        sensors_h5.has_orientation.store(sensors_inst.has_orientation)
        sensors_h5.orientations.store(sensors_inst.orientations)
        sensors_h5.number_of_sensors.store(sensors_inst.number_of_sensors)
        sensors_h5.usable.store(sensors_inst.usable)

        return sensors_idx
