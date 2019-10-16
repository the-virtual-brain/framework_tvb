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
.. moduleauthor:: Marmaduke Woodman <marmaduke.woodman@univ-amu.fr>
.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
"""

from tvb.adapters.uploaders.abcuploader import ABCUploader
from tvb.basic.logger.builder import get_logger
from tvb.core.adapters.exceptions import LaunchException
from tvb.datatypes.surfaces import CorticalSurface
from tvb.datatypes.sensors import Sensors, SensorsEEG, SensorsMEG
from tvb.datatypes.projections import ProjectionSurfaceEEG, ProjectionSurfaceMEG, ProjectionSurfaceSEEG


DEFAULT_DATASET_NAME = "ProjectionMatrix"



def build_projection_instance(sensors, storage_path):
    if isinstance(sensors, SensorsEEG):
        projection_matrix = ProjectionSurfaceEEG(storage_path=storage_path)
    elif isinstance(sensors, SensorsMEG):
        projection_matrix = ProjectionSurfaceMEG(storage_path=storage_path)
    else:
        projection_matrix = ProjectionSurfaceSEEG(storage_path=storage_path)

    return projection_matrix


class ProjectionMatrixSurfaceEEGImporter(ABCUploader):
    """
    Upload ProjectionMatrix Cortical Surface -> EEG/MEG/SEEG Sensors from a MAT or NPY file.
    """

    _ui_name = "Gain Matrix for Sensors"
    _ui_description = "Upload a Projection Matrix between a Brain Cortical Surface and EEG/MEG Sensors."
    logger = get_logger(__name__)


    def get_upload_input_tree(self):
        """
        Define input parameters for this importer.
        """
        return [{'name': 'projection_file', 'type': 'upload', 'required_type': '.mat, .npy',
                 'label': 'Projection matrix file (.mat or .npy format)', 'required': True,
                 'description': 'Expected a file containing projection matrix (one vector of length '
                                'number of surface vertices nd values in the sensors range).'},

                {'name': 'dataset_name', 'type': 'str', 'required': False,
                 'label': 'Matlab dataset name', 'default': DEFAULT_DATASET_NAME,
                 'description': 'Name of the MATLAB dataset where data is stored. Required only for .mat files'},

                {'name': 'surface', 'label': 'Brain Cortical Surface',
                 'type': CorticalSurface, 'required': True, 'datatype': True,
                 'description': 'The Brain Surface used by the uploaded projection matrix.'},

                {'name': 'sensors', 'label': 'Sensors',
                 'type': Sensors, 'required': True, 'datatype': True,
                 'description': 'The Sensors used in for current projection.'}
                ]


    def get_output(self):
        return [ProjectionSurfaceEEG, ProjectionSurfaceMEG, ProjectionSurfaceSEEG]


    def launch(self, projection_file, surface, sensors, dataset_name=DEFAULT_DATASET_NAME):
        """
        Creates ProjectionMatrix entity from uploaded data.

        :raises LaunchException: when
                    * no projection_file or sensors are specified
                    * the dataset is invalid
                    * number of sensors is different from the one in dataset
        """
        if projection_file is None:
            raise LaunchException("Please select MATLAB file which contains data to import")

        if sensors is None:
            raise LaunchException("No sensors selected. Please initiate upload again and select one.")

        if surface is None:
            raise LaunchException("No source selected. Please initiate upload again and select a source.")
        expected_shape = surface.number_of_vertices

        self.logger.debug("Reading projection matrix from uploaded file...")
        if projection_file.endswith(".mat"):
            eeg_projection_data = self.read_matlab_data(projection_file, dataset_name)
        else:
            eeg_projection_data = self.read_list_data(projection_file)

        if eeg_projection_data is None or len(eeg_projection_data) == 0:
            raise LaunchException("Invalid (empty) dataset...")

        if eeg_projection_data.shape[0] != sensors.number_of_sensors:
            raise LaunchException("Invalid Projection Matrix shape[0]: %d Expected: %d" % (eeg_projection_data.shape[0],
                                                                                           sensors.number_of_sensors))

        if eeg_projection_data.shape[1] != expected_shape:
            raise LaunchException("Invalid Projection Matrix shape[1]: %d Expected: %d" % (eeg_projection_data.shape[1],
                                                                                           expected_shape))

        self.logger.debug("Creating Projection Matrix instance")
        projection_matrix = build_projection_instance(sensors, self.storage_path)
        projection_matrix.sources = surface
        projection_matrix.sensors = sensors
        if eeg_projection_data is not None:
            projection_matrix.projection_data = eeg_projection_data
        return [projection_matrix]
