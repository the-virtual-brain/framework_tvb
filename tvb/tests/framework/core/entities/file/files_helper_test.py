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
.. moduleauthor:: Bogdan Neacsa <bogdan.neacsa@codemart.ro>
"""

import os
import pytest
from tvb.tests.framework.core.base_testcase import TransactionalTestCase
from tvb.basic.profile import TvbProfile
from tvb.core.entities.file.xml_metadata_handlers import XMLReader
from tvb.core.entities import model
from tvb.core.entities.storage import dao
from tvb.core.entities.file.exceptions import FileStructureException
from tvb.core.entities.file.files_helper import FilesHelper
from tvb.tests.framework.core.factory import TestFactory


root_storage = TvbProfile.current.TVB_STORAGE


class TestFilesHelper(TransactionalTestCase):
    """
    This class contains tests for the tvb.core.entities.file.files_helper module.
    """ 
    PROJECT_NAME = "test_proj"
           
           
    def transactional_setup_method(self):
        """
        Set up the context needed by the tests.
        """
        self.files_helper = FilesHelper()
        self.test_user = TestFactory.create_user()
        self.test_project = TestFactory.create_project(self.test_user, self.PROJECT_NAME)
    
    
    def transactional_teardown_method(self):
        """ Remove generated project during tests. """
        self.delete_project_folders()
    
    
    def test_check_created(self):
        """ Test standard flows for check created. """
        self.files_helper.check_created()
        assert os.path.exists(root_storage), "Storage not created!"
        
        self.files_helper.check_created(os.path.join(root_storage, "test"))
        assert os.path.exists(root_storage), "Storage not created!"
        assert os.path.exists(os.path.join(root_storage, "test")), "Test directory not created!"
            
    
    def test_get_project_folder(self):
        """
        Test the get_project_folder method which should create a folder in case
        it doesn't already exist.
        """
        project_path = self.files_helper.get_project_folder(self.test_project)
        assert os.path.exists(project_path), "Folder doesn't exist"
        
        folder_path = self.files_helper.get_project_folder(self.test_project, "43")
        assert os.path.exists(project_path), "Folder doesn't exist"
        assert os.path.exists(folder_path), "Folder doesn't exist"
        
   
    def test_rename_project_structure(self):
        """ Try to rename the folder structure of a project. Standard flow. """
        self.files_helper.get_project_folder(self.test_project)
        path, name = self.files_helper.rename_project_structure(self.test_project.name, "new_name")
        assert path != name, "Rename didn't take effect."


    def test_rename_structure_same_name(self):
        """ Try to rename the folder structure of a project. Same name. """
        self.files_helper.get_project_folder(self.test_project)
        
        with pytest.raises(FileStructureException):
            self.files_helper.rename_project_structure(self.test_project.name, self.PROJECT_NAME)


    def test_remove_project_structure(self):
        """ Check that remove project structure deletes the corresponding folder. Standard flow. """
        full_path = self.files_helper.get_project_folder(self.test_project)
        assert os.path.exists(full_path), "Folder was not created."
        
        self.files_helper.remove_project_structure(self.test_project.name)
        assert not os.path.exists(full_path), "Project folder not deleted."
        
    
    def test_write_project_metadata(self):
        """  Write XML for test-project. """
        self.files_helper.write_project_metadata(self.test_project)
        expected_file = self.files_helper.get_project_meta_file_path(self.PROJECT_NAME)
        assert os.path.exists(expected_file)
        project_meta = XMLReader(expected_file).read_metadata()
        loaded_project = model.Project(None, None)
        loaded_project.from_dict(project_meta, self.test_user.id)
        assert self.test_project.name == loaded_project.name
        assert self.test_project.description == loaded_project.description
        assert self.test_project.gid == loaded_project.gid
        expected_dict = self.test_project.to_dict()[1]
        del expected_dict['last_updated']
        found_dict = loaded_project.to_dict()[1]
        del found_dict['last_updated']
        self._dictContainsSubset(expected_dict, found_dict)
        self._dictContainsSubset(found_dict, expected_dict)
    
    
    def test_write_operation_metadata(self):
        """
        Test that a correct XML is created for an operation.
        """
        operation = TestFactory.create_operation(test_user=self.test_user, test_project=self.test_project)
        expected_file = self.files_helper.get_operation_meta_file_path(self.PROJECT_NAME, operation.id)
        assert not os.path.exists(expected_file)
        self.files_helper.write_operation_metadata(operation)
        assert os.path.exists(expected_file)
        operation_meta = XMLReader(expected_file).read_metadata()
        loaded_operation = model.Operation(None, None, None, None)
        loaded_operation.from_dict(operation_meta, dao, user_id=self.test_user.id)
        expected_dict = operation.to_dict()[1]
        found_dict = loaded_operation.to_dict()[1]
        for key, value in expected_dict.items():
            assert str(value) == str(found_dict[key])
        # Now validate that operation metaData can be also updated
        assert "new_group_name" != found_dict['user_group']
        self.files_helper.update_operation_metadata(self.PROJECT_NAME, "new_group_name", operation.id) 
        found_dict = XMLReader(expected_file).read_metadata()  
        assert "new_group_name" == found_dict['user_group']
        
    
    def test_remove_dt_happy_flow(self):
        """
        Happy flow for removing a file related to a DataType.
        """
        folder_path = self.files_helper.get_project_folder(self.test_project, "42")
        datatype = MappedType()
        datatype.storage_path = folder_path
        open(datatype.get_storage_file_path(), 'w') 
        assert os.path.exists(datatype.get_storage_file_path()), "Test file was not created!"
        self.files_helper.remove_datatype(datatype) 
        assert not os.path.exists(datatype.get_storage_file_path()), "Test file was not deleted!"
        
        
    def test_remove_dt_non_existent(self):
        """
        Try to call remove on a dataType with no H5 file.
        Should work.
        """
        folder_path = self.files_helper.get_project_folder(self.test_project, "42")
        datatype = MappedType()
        datatype.storage_path = folder_path
        assert not os.path.exists(datatype.get_storage_file_path())
        self.files_helper.remove_datatype(datatype)
        

    def test_move_datatype(self):
        """
        Make sure associated H5 file is moved to a correct new location.
        """
        folder_path = self.files_helper.get_project_folder(self.test_project, "42")
        datatype = MappedType()
        datatype.storage_path = folder_path
        open(datatype.get_storage_file_path(), 'w') 
        assert os.path.exists(datatype.get_storage_file_path()), "Test file was not created!"
        self.files_helper.move_datatype(datatype, self.PROJECT_NAME + '11', "43") 
        
        assert not os.path.exists(datatype.get_storage_file_path()), "Test file was not moved!"
        datatype.storage_path = self.files_helper.get_project_folder(self.PROJECT_NAME + '11', "43")
        assert os.path.exists(datatype.get_storage_file_path()), "Test file was not created!"
        
        
    def test_find_relative_path(self):
        """
        Tests that relative path is computed properly.
        """
        rel_path = self.files_helper.find_relative_path("/root/up/to/here/test/it/now", "/root/up/to/here")
        assert rel_path == os.sep.join(["test", "it", "now"]), "Did not extract relative path as expected."
        
        
    def test_remove_files_valid(self):
        """
        Pass a valid list of files and check they are all removed.
        """
        file_list = ["test1", "test2", "test3"]
        for file_n in file_list:
            fp = open(file_n, 'w')
            fp.write('test')
            fp.close()
        for file_n in file_list:
            assert os.path.isfile(file_n)
        self.files_helper.remove_files(file_list)
        for file_n in file_list:
            assert not os.path.isfile(file_n)


    def test_remove_folder(self):
        """
        Pass an open file pointer, but ignore exceptions.
        """
        folder_name = "test_folder"
        os.mkdir(folder_name)
        assert os.path.isdir(folder_name), "Folder should be created."
        self.files_helper.remove_folder(folder_name)
        assert not os.path.isdir(folder_name), "Folder should be deleted."
        
    def test_remove_folder_non_existing_ignore_exc(self):
        """
        Pass an open file pointer, but ignore exceptions.
        """
        folder_name = "test_folder"
        assert not os.path.isdir(folder_name), "Folder should not exist before call."
        self.files_helper.remove_folder(folder_name, ignore_errors=True)
        
        
    def test_remove_folder_non_existing(self):
        """
        Pass an open file pointer, but ignore exceptions.
        """
        folder_name = "test_folder"
        assert not os.path.isdir(folder_name), "Folder should not exist before call."
        with pytest.raises(FileStructureException):
            self.files_helper.remove_folder(folder_name, False)

    def _dictContainsSubset(self, expected, actual, msg=None):
        """Checks whether actual is a superset of expected."""
        missing = []
        mismatched = []
        for key, value in expected.items():
            if key not in actual:
                return False
            elif value != actual[key]:
                return False
        return True
