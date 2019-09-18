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
Backend-side for Visualizers that display measures on regions in the brain volume.

.. moduleauthor:: Andrei Mihai <mihai.andrei@codemart.ro>
"""

import json
from tvb.core.entities.filters.chain import FilterChain
from tvb.basic.arguments_serialisation import slice_str, preprocess_space_parameters, parse_slice
from tvb.core.adapters.abcadapter import ABCAdapterForm
from tvb.core.adapters.abcdisplayer import ABCDisplayer
from tvb.core.adapters.exceptions import LaunchException
from tvb.core.entities.model.datatypes.graph import ConnectivityMeasureIndex
from tvb.core.entities.model.datatypes.region_mapping import RegionVolumeMappingIndex
from tvb.core.entities.model.datatypes.structural import StructuralMRIIndex
from tvb.core.entities.model.model_datatype import DataTypeMatrix
from tvb.core.entities.storage import dao
from tvb.core.neotraits._forms import DataTypeSelectField, SimpleStrField


class _MappedArrayVolumeBase(ABCDisplayer):
    """
    Base functionality for all non-temporal volume views.
    It prepares for display a slice of a mapped array.
    """
    _ui_subsection = "volume"

    def get_required_memory_size(self, **kwargs):
        return -1

    @staticmethod
    def get_default_slice(measure_shape, nregions):
        default = [0 for _ in range(len(measure_shape))]
        for i in range(len(measure_shape)):
            if measure_shape[i] == nregions:
                default[i] = slice(None)
                return tuple(default)
        raise LaunchException("The mapped array of shape %s is incompatible with the region mapping "
                              "(expected values for %d connectivity regions)." % (measure_shape, nregions))

    def _ensure_region_mapping_index(self, region_mapping_volume):
        if region_mapping_volume is None:
            region_mapping_volume = dao.try_load_last_entity_of_type(self.current_project_id, RegionVolumeMappingIndex)
        if region_mapping_volume is None:
            raise LaunchException('You should have a volume mapping to launch this viewer')
        return region_mapping_volume

    def _compute_region_volume_map_params(self, region_mapping_volume):
        # prepare the url that will display the region volume map
        conn_index = dao.get_datatype_by_gid(region_mapping_volume.connectivity.load().hex)
        min_value, max_value = [0, conn_index.number_of_regions]
        url_volume_data = self.build_url('get_volume_view', region_mapping_volume.gid.load().hex, '')
        return dict(minValue=min_value, maxValue=max_value, urlVolumeData=url_volume_data)

    def _compute_measure_params(self, region_mapping_volume, measure, data_slice):
        # prepare the url that will project the measure onto the region volume map
        measure_h5_class, measure_h5_path = self._load_h5_of_gid(measure.gid)
        measure_h5 = measure_h5_class(measure_h5_path)
        min_value, max_value = measure_h5.get_min_max_values()
        measure_shape = measure_h5.array_data.shape
        if not data_slice:
            conn_index = dao.get_datatype_by_gid(region_mapping_volume.connectivity.load().hex)
            data_slice = self.get_default_slice(measure_shape, conn_index.number_of_regions)
            data_slice = slice_str(data_slice)
        url_volume_data = self.build_url('get_mapped_array_volume_view', region_mapping_volume.gid.load().hex,
                                         parameter='')
        url_volume_data += 'mapped_array_gid=' + measure.gid + ';mapped_array_slice=' + data_slice + ';'

        return dict(minValue=min_value, maxValue=max_value,
                    urlVolumeData=url_volume_data,
                    measureShape=slice_str(measure_shape),
                    measureSlice=data_slice)

    def get_mapped_array_volume_view(self, entity_gid, mapped_array_gid, x_plane, y_plane, z_plane,
                                     mapped_array_slice=None, **kwargs):
        entity_h5_class, entity_h5_path = self._load_h5_of_gid(entity_gid)
        with entity_h5_class(entity_h5_path) as entity_h5:
            data_shape = entity_h5.array_data.shape
            x_plane, y_plane, z_plane = preprocess_space_parameters(x_plane, y_plane, z_plane, data_shape[0],
                                                                    data_shape[1], data_shape[2])
            slice_x, slice_y, slice_z = entity_h5.get_volume_slice(x_plane, y_plane, z_plane)
            connectivity_gid = entity_h5.connectivity.load().hex

        mapped_array_h5_class, mapped_array_h5_path = self._load_h5_of_gid(mapped_array_gid)
        with mapped_array_h5_class(mapped_array_h5_path) as mapped_array_h5:
            if mapped_array_slice:
                matrix_slice = parse_slice(mapped_array_slice)
                measure = mapped_array_h5.array_data[matrix_slice]
            else:
                measure = mapped_array_h5.array_data[:]

        connectivity_index = self.load_entity_by_gid(connectivity_gid)
        if measure.shape != (connectivity_index.number_of_regions,):
            raise ValueError('cannot project measure on the space')

        result_x = measure[slice_x]
        result_y = measure[slice_y]
        result_z = measure[slice_z]
        # Voxels outside the brain are -1. The indexing above is incorrect for those voxels as it
        # associates the values of the last region measure[-1] to them.
        # Here we replace those values with an out of scale value.
        result_x[slice_x == -1] = measure.min() - 1
        result_y[slice_y == -1] = measure.min() - 1
        result_z[slice_z == -1] = measure.min() - 1

        return [[result_x.tolist()],
                [result_y.tolist()],
                [result_z.tolist()]]

    @staticmethod
    def compute_background_params(min_value=0, max_value=0, url=None):
        return dict(minBackgroundValue=min_value, maxBackgroundValue=max_value, urlBackgroundVolumeData=url)

    def _compute_background(self, background):
        if background is None:
            return self.compute_background_params()

        background_class, background_path = self._load_h5_of_gid(background.gid)
        background_h5 = background_class(background_path)
        min_value, max_value = background_h5.get_min_max_values()
        background_h5.close()

        url_volume_data = self.build_url('get_volume_view', background.gid, '')
        return self.compute_background_params(min_value, max_value, url_volume_data)

    def compute_params(self, region_mapping_volume=None, measure=None, data_slice='', background=None):

        region_mapping_volume = self._ensure_region_mapping_index(region_mapping_volume)
        rmv_h5_class, rmv_h5_path = self._load_h5_of_gid(region_mapping_volume.gid)
        rmv_h5 = rmv_h5_class(rmv_h5_path)

        volume_shape = rmv_h5.array_data.shape
        volume_shape = (1,) + volume_shape

        if measure is None:
            params = self._compute_region_volume_map_params(rmv_h5)
        else:
            params = self._compute_measure_params(rmv_h5, measure, data_slice)

        url_voxel_region = self.build_h5_url(region_mapping_volume.gid, 'get_voxel_region', '')

        volume_gid = rmv_h5.volume.load()
        volume_h5_class, volume_g5_path = self._load_h5_of_gid(volume_gid.hex)
        volume_h5 = volume_h5_class(volume_g5_path)

        params.update(volumeShape=json.dumps(volume_shape),
                      volumeOrigin=json.dumps(volume_h5.origin.load().tolist()),
                      voxelUnit=volume_h5.voxel_unit.load(),
                      voxelSize=json.dumps(volume_h5.voxel_size.load().tolist()),
                      urlVoxelRegion=url_voxel_region)

        rmv_h5.close()
        volume_h5.close()

        if background is None:
            background = dao.try_load_last_entity_of_type(self.current_project_id, StructuralMRIIndex)

        params.update(self._compute_background(background))
        return params


class BaseVolumeVisualizerForm(ABCAdapterForm):

    def __init__(self, prefix='', project_id=None):
        super(BaseVolumeVisualizerForm, self).__init__(prefix, project_id)
        self.background = DataTypeSelectField(StructuralMRIIndex, self, name='background', required=False,
                                              label='Background T1')


class VolumeVisualizerForm(BaseVolumeVisualizerForm):

    def __init__(self, prefix='', project_id=None):
        super(VolumeVisualizerForm, self).__init__(prefix, project_id)
        self.measure = DataTypeSelectField(self.get_required_datatype(), self, name='measure', required=True,
                                           label='Measure', doc='A measure to view on anatomy',
                                           conditions=self.get_filters())
        self.region_mapping_volume = DataTypeSelectField(RegionVolumeMappingIndex, self, name='region_mapping_volume',
                                                         label='Region mapping')
        self.data_slice = SimpleStrField(self, name='data_slice', label='slice indices in numpy syntax')

    @staticmethod
    def get_filters():
        return FilterChain(fields=[FilterChain.datatype + '.ndim'], operations=[">="], values=[2])

    @staticmethod
    def get_input_name():
        return '_measure'

    @staticmethod
    def get_required_datatype():
        return DataTypeMatrix


class MappedArrayVolumeVisualizer(_MappedArrayVolumeBase):
    """
    This is a generic mapped array visualizer on a region volume.
    To view a multidimensional array one has to give this viewer a slice.
    """
    _ui_name = "Array Volume Visualizer"

    def get_form_class(self):
        return VolumeVisualizerForm

    def launch(self, measure, region_mapping_volume=None, data_slice='', background=None):
        params = self.compute_params(region_mapping_volume, measure, data_slice, background=background)
        params['title'] = "Mapped array on region volume Visualizer",
        return self.build_display_result("time_series_volume/staticView", params,
                                         pages=dict(controlPage="time_series_volume/controls"))


class ConnectivityMeasureVolumeVisualizerForm(BaseVolumeVisualizerForm):

    def __init__(self, prefix='', project_id=None):
        super(ConnectivityMeasureVolumeVisualizerForm, self).__init__(prefix, project_id)
        self.connectivity_measure = DataTypeSelectField(self.get_required_datatype(), self, name='connectivity_measure',
                                                        required=True, label='Connectivity measure',
                                                        doc='A connectivity measure', conditions=self.get_filters())
        self.region_mapping_volume = DataTypeSelectField(RegionVolumeMappingIndex, self, name='region_mapping_volume',
                                                         label='Region mapping')

    @staticmethod
    def get_required_datatype():
        return ConnectivityMeasureIndex

    @staticmethod
    def get_input_name():
        return '_connectivity_measure'

    @staticmethod
    def get_filters():
        return FilterChain(fields=[FilterChain.datatype + '.ndim'], operations=["=="], values=[1])


class ConnectivityMeasureVolumeVisualizer(_MappedArrayVolumeBase):
    _ui_name = "Connectivity Measure Volume Visualizer"

    def get_form_class(self):
        return ConnectivityMeasureVolumeVisualizerForm

    def launch(self, connectivity_measure, region_mapping_volume=None, background=None):
        params = self.compute_params(region_mapping_volume, connectivity_measure, background=background)
        params['title'] = "Connectivity Measure in Volume Visualizer"
        # the view will display slicing information if this key is present.
        # compute_params works with generic mapped arrays and it will return slicing info
        del params['measureSlice']
        return self.build_display_result("time_series_volume/staticView", params,
                                         pages=dict(controlPage="time_series_volume/controls"))


class RegionVolumeMappingVisualiserForm(BaseVolumeVisualizerForm):

    def __init__(self, prefix='', project_id=None):
        super(RegionVolumeMappingVisualiserForm, self).__init__(prefix, project_id)
        self.region_mapping_volume = DataTypeSelectField(self.get_required_datatype(), self,
                                                         name='region_mapping_volume', required=True,
                                                         label='Region mapping', conditions=self.get_filters())

        cm_conditions = FilterChain(fields=[FilterChain.datatype + '.ndim'], operations=["=="], values=[1])
        self.connectivity_measure = DataTypeSelectField(ConnectivityMeasureIndex, self, name='connectivity_measure',
                                                        label='Connectivity measure', doc='A connectivity measure',
                                                        conditions=cm_conditions)

    @staticmethod
    def get_filters():
        return None

    @staticmethod
    def get_input_name():
        return '_region_mapping_volume'

    @staticmethod
    def get_required_datatype():
        return RegionVolumeMappingIndex


class RegionVolumeMappingVisualiser(_MappedArrayVolumeBase):
    _ui_name = "Region Volume Mapping Visualizer"

    def get_form_class(self):
        return RegionVolumeMappingVisualiserForm

    def launch(self, region_mapping_volume, connectivity_measure=None, background=None):
        params = self.compute_params(region_mapping_volume, connectivity_measure, background=background)
        params['title'] = "Volume to Regions Visualizer"
        return self.build_display_result("time_series_volume/staticView", params,
                                         pages=dict(controlPage="time_series_volume/controls"))


class MriVolumeVisualizerForm(BaseVolumeVisualizerForm):

    def __init__(self, prefix='', project_id=None):
        super(MriVolumeVisualizerForm, self).__init__(prefix, project_id)
        self.background.required = True

    @staticmethod
    def get_required_datatype():
        return StructuralMRIIndex

    @staticmethod
    def get_input_name():
        return '_background'

    @staticmethod
    def get_filters():
        return None


class MriVolumeVisualizer(ABCDisplayer):
    _ui_name = "MRI Volume Visualizer"
    _ui_subsection = "volume"

    def get_form_class(self):
        return MriVolumeVisualizerForm

    def get_required_memory_size(self, **kwargs):
        return -1

    def launch(self, background=None):
        background_class, background_path = self._load_h5_of_gid(background.gid)
        background_h5 = background_class(background_path)
        volume_shape = background_h5.array_data.shape
        volume_shape = (1,) + volume_shape

        min_value, max_value = background_h5.get_min_max_values()
        url_volume_data = self.build_url('/get_volume_view/', background.gid, '')

        volume_gid = background_h5.volume.load()
        volume_class, volume_path = self._load_h5_of_gid(volume_gid.hex)
        volume_h5 = volume_class(volume_path)
        params = dict(title="MRI Volume visualizer",
                      minValue=min_value, maxValue=max_value,
                      urlVolumeData=url_volume_data,
                      volumeShape=json.dumps(volume_shape),
                      volumeOrigin=json.dumps(volume_h5.origin.load().tolist()),
                      voxelUnit=volume_h5.voxel_unit.load(),
                      voxelSize=json.dumps(volume_h5.voxel_size.load().tolist()),
                      urlVoxelRegion='',
                      minBackgroundValue=min_value, maxBackgroundValue=max_value,
                      urlBackgroundVolumeData='')

        background_h5.close()
        volume_h5.close()
        return self.build_display_result("time_series_volume/staticView", params,
                                         pages=dict(controlPage="time_series_volume/controls"))
