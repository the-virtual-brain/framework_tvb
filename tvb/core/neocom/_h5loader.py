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

import os
import uuid
import typing
from tvb.basic.neotraits.api import HasTraits
from tvb.core.neotraits.h5 import H5File
from tvb.core.entities.generic_attributes import GenericAttributes
from tvb.core.entities.model.model_datatype import DataType
from tvb.core.entities.storage import dao
from tvb.core.entities.file.files_helper import FilesHelper
from tvb.core.neocom._registry import Registry


class Loader(object):
    """
    A default simple loader. Does not do recursive loads. Loads stores just to paths.
    """

    def __init__(self, registry):
        self.registry = registry

    def load(self, source):
        # type: (str) -> HasTraits

        with H5File.from_file(source) as f:
            datatype_cls = self.registry.get_datatype_for_h5file(type(f))
            datatype = datatype_cls()
            f.load_into(datatype)
            return datatype

    def store(self, datatype, destination):
        # type: (HasTraits, str) -> None
        h5file_cls = self.registry.get_h5file_for_datatype(type(datatype))

        with h5file_cls(destination) as f:
            f.store(datatype)



class DirLoader(object):
    """
    A simple recursive loader. Stores all files in a directory.
    You refer to files by their gid
    """

    def __init__(self, base_dir, registry, recursive=False):
        # type: (str, Registry, bool) -> None
        if not os.path.isdir(base_dir):
            raise IOError('not a directory {}'.format(base_dir))

        self.base_dir = base_dir
        self.recursive = recursive
        self.registry = registry

    def _locate(self, gid):
        # type: (uuid.UUID) -> str
        for fname in os.listdir(self.base_dir):
            if fname.endswith(gid.hex + '.h5'):
                return fname
        raise IOError('could not locate h5 with gid {}'.format(gid))

    def find_file_name(self, gid):
        # type: (typing.Union[uuid.UUID, str]) -> str
        if isinstance(gid, str):
            gid = uuid.UUID(gid)

        fname = self._locate(gid)
        return fname

    def load(self, gid):
        # type: (typing.Union[uuid.UUID, str]) -> HasTraits
        fname = self.find_file_name(gid)

        sub_dt_refs = []

        with H5File.from_file(os.path.join(self.base_dir, fname)) as f:
            datatype_cls = self.registry.get_datatype_for_h5file(type(f))
            datatype = datatype_cls()
            f.load_into(datatype)

            if self.recursive:
                sub_dt_refs = f.gather_references()

        for fname, sub_gid in sub_dt_refs:
            subdt = self.load(sub_gid)
            setattr(datatype, fname, subdt)

        return datatype

    def store(self, datatype):
        # type: (HasTraits) -> None
        h5file_cls = self.registry.get_h5file_for_datatype(type(datatype))
        path = self.path_for(h5file_cls, datatype.gid)

        sub_dt_refs = []

        with h5file_cls(path) as f:
            f.store(datatype)

            if self.recursive:
                sub_dt_refs = f.gather_references()

        for fname, sub_gid in sub_dt_refs:
            subdt = getattr(datatype, fname)
            self.store(subdt)

    def path_for(self, h5_file_class, gid):
        """
        where will this Loader expect to find a file of this format and with this gid
        """
        datatype_cls = self.registry.get_datatype_for_h5file(h5_file_class)
        return self.path_for_has_traits(datatype_cls, gid)

    def path_for_has_traits(self, has_traits_class, gid):

        if isinstance(gid, str):
            gid = uuid.UUID(gid)
        fname = '{}_{}.h5'.format(has_traits_class.__name__, gid.hex)
        return os.path.join(self.base_dir, fname)


class TVBLoader(object):

    def __init__(self, registry):
        self.file_handler = FilesHelper()
        self.registry = registry

    def path_for_stored_index(self, dt_index_instance):
        # type: (DataType) -> str
        """ Given a Datatype(HasTraitsIndex) instance, build where the corresponding H5 should be or is stored"""
        operation = dao.get_operation_by_id(dt_index_instance.fk_from_operation)
        operation_folder = self.file_handler.get_project_folder(operation.project, str(operation.id))

        gid = uuid.UUID(dt_index_instance.gid)
        h5_file_class = self.registry.get_h5file_for_index(dt_index_instance.__class__)
        fname = '{}_{}.h5'.format(h5_file_class.file_name_base(), gid.hex)

        return os.path.join(operation_folder, fname)

    def path_for(self, operation_dir, h5_file_class, gid):
        if isinstance(gid, str):
            gid = uuid.UUID(gid)
        fname = '{}_{}.h5'.format(h5_file_class.file_name_base(), gid.hex)
        return os.path.join(operation_dir, fname)

    def load_from_index(self, dt_index, dt_class=None):
        # type: (DataType, typing.Type[HasTraits]) -> HasTraits
        h5_path = self.path_for_stored_index(dt_index)
        h5_file_class = self.registry.get_h5file_for_index(dt_index.__class__)
        traits_class = dt_class or self.registry.get_datatype_for_index(dt_index.__class__)
        with h5_file_class(h5_path) as f:
            result_dt = traits_class()
            f.load_into(result_dt)
        return result_dt

    def load_with_references(self, file_path):
        # type: (str) -> (HasTraits, GenericAttributes)
        with H5File.from_file(file_path) as f:
            datatype_cls = self.registry.get_datatype_for_h5file(type(f))
            datatype = datatype_cls()
            f.load_into(datatype)
            ga = f.load_generic_attributes()
            sub_dt_refs = f.gather_references()

        for fname, sub_gid in sub_dt_refs:
            ref_idx = dao.get_datatype_by_gid(sub_gid.hex, load_lazy=False)
            ref_ht = self.load_from_index(ref_idx)
            setattr(datatype, fname, ref_ht)

        return datatype, ga
