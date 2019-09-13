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
.. moduleauthor:: Mihai Andrei <mihai.andrei@codemart.ro>
"""

import pytest
import tvb_data
from os import path
from tvb.tests.framework.core.base_testcase import TransactionalTestCase, BaseTestCase
from tvb.adapters.uploaders.csv_connectivity_importer import CSVConnectivityParser
from tvb.core.entities.filters.chain import FilterChain
from tvb.core.entities.file.files_helper import FilesHelper
from tvb.core.services.exceptions import OperationException
from tvb.core.services.flow_service import FlowService
from tvb.datatypes.connectivity import Connectivity
from tvb.tests.framework.adapters.uploaders.connectivity_zip_importer_test import TestConnectivityZip
from tvb.tests.framework.core.factory import TestFactory

TEST_SUBJECT_A = "TEST_SUBJECT_A"
TEST_SUBJECT_B = "TEST_SUBJECT_B"
BASE_PTH = path.join(path.dirname(tvb_data.__file__), 'dti_pipeline_toronto')


class TestCSVConnectivityParser(BaseTestCase):

    def test_parse_happy(self):
        cap_pth = path.join(BASE_PTH, 'output_ConnectionDistanceMatrix.csv')

        with open(cap_pth) as f:
            result_conn = CSVConnectivityParser(f).result_conn
            assert [0, 61.7082, 50.7576, 76.4214] == result_conn[0][:4]
            for i in range(len(result_conn)):
                assert 0 == result_conn[i][i]


class TestCSVConnectivityImporter(TransactionalTestCase):
    """
    Unit-tests for csv connectivity importer.
    """

    def transactional_setup_method(self):
        self.test_user = TestFactory.create_user()
        self.test_project = TestFactory.create_project(self.test_user)
        self.helper = FilesHelper()

    def transactional_teardown_method(self):
        """
        Clean-up tests data
        """
        FilesHelper().remove_project_structure(self.test_project.name)

    def _import_csv_test_connectivity(self, reference_connectivity_gid, subject):
        ### First prepare input data:
        weights = path.join(BASE_PTH, 'output_ConnectionCapacityMatrix.csv')
        tracts = path.join(BASE_PTH, 'output_ConnectionDistanceMatrix.csv')
        weights_tmp = weights + '.tmp'
        tracts_tmp = tracts + '.tmp'
        self.helper.copy_file(weights, weights_tmp)
        self.helper.copy_file(tracts, tracts_tmp)

        ### Find importer and Launch Operation
        importer = TestFactory.create_adapter('tvb.adapters.uploaders.csv_connectivity_importer',
                                              'CSVConnectivityImporter')
        FlowService().fire_operation(importer, self.test_user, self.test_project.id,
                                     weights=weights_tmp, tracts=tracts_tmp, Data_Subject=subject,
                                     input_data=reference_connectivity_gid)

    def test_happy_flow_import(self):
        """
        Test that importing a CFF generates at least one DataType in DB.
        """
        TestConnectivityZip.import_test_connectivity96(self.test_user,
                                                       self.test_project,
                                                       subject=TEST_SUBJECT_A)

        field = FilterChain.datatype + '.subject'
        filters = FilterChain('', [field], [TEST_SUBJECT_A], ['=='])
        reference_connectivity = TestFactory.get_entity(self.test_project, Connectivity(), filters)

        dt_count_before = TestFactory.get_entity_count(self.test_project, Connectivity())

        self._import_csv_test_connectivity(reference_connectivity.gid, TEST_SUBJECT_B)

        dt_count_after = TestFactory.get_entity_count(self.test_project, Connectivity())
        assert dt_count_before + 1 == dt_count_after

        filters = FilterChain('', [field], [TEST_SUBJECT_B], ['like'])
        imported_connectivity = TestFactory.get_entity(self.test_project, Connectivity(), filters)

        # check relationship between the imported connectivity and the reference
        assert (reference_connectivity.centres == imported_connectivity.centres).all()
        assert (reference_connectivity.orientations == imported_connectivity.orientations).all()

        assert reference_connectivity.number_of_regions == imported_connectivity.number_of_regions
        assert (reference_connectivity.region_labels == imported_connectivity.region_labels).all()

        assert not (reference_connectivity.weights == imported_connectivity.weights).all()
        assert not (reference_connectivity.tract_lengths == imported_connectivity.tract_lengths).all()

    def test_bad_reference(self):
        TestFactory.import_cff(test_user=self.test_user, test_project=self.test_project)
        field = FilterChain.datatype + '.subject'
        filters = FilterChain('', [field], [TEST_SUBJECT_A], ['!='])
        bad_reference_connectivity = TestFactory.get_entity(self.test_project, Connectivity(), filters)

        with pytest.raises(OperationException):
            self._import_csv_test_connectivity(bad_reference_connectivity.gid, TEST_SUBJECT_A)
