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
import os
import tvb_data
from tvb.adapters.datatypes.db.connectivity import ConnectivityIndex
from tvb.tests.framework.core.base_testcase import TransactionalTestCase
from tvb.core.entities.file.files_helper import FilesHelper
from tvb.adapters.visualizers.cross_coherence import CrossCoherenceVisualizer
from tvb.tests.framework.core.factory import TestFactory

class TestCrossCoherenceViewer(TransactionalTestCase):
    """
    Unit-tests for Cross Coherence Viewer.
    """

    def transactional_setup_method(self):
        """
        Sets up the environment for running the tests;
        creates a test user, a test project, a connectivity and a surface;
        imports a CFF data-set
        """
        self.test_user = TestFactory.create_user('CrossCoherence_User')
        self.test_project = TestFactory.create_project(self.test_user, "CrossCoherence_Project")

        zip_path = os.path.join(os.path.dirname(tvb_data.__file__), 'connectivity', 'connectivity_66.zip')
        TestFactory.import_zip_connectivity(self.test_user, self.test_project, zip_path);
        self.connectivity = TestFactory.get_entity(self.test_project, ConnectivityIndex())
        assert self.connectivity is not None


    def transactional_teardown_method(self):
        """
        Clean-up tests data
        """
        FilesHelper().remove_project_structure(self.test_project.name)


    def test_launch(self):
        """
        Check that all required keys are present in output from BrainViewer launch.
        """
        time_series = self.datatypeFactory.create_timeseries(self.connectivity)
        cross_coherence = self.datatypeFactory.create_crosscoherence(time_series)
        viewer = CrossCoherenceVisualizer()
        result = viewer.launch(cross_coherence)
        expected_keys = ['matrix_data', 'matrix_shape', 'frequency']
        for key in expected_keys:
            assert key in result

