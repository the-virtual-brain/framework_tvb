import json
import numpy

from tvb.core.neotraits.h5 import H5File, Scalar, DataSet, Reference, Json
from tvb.datatypes.time_series import TimeSeries, TimeSeriesRegion, TimeSeriesSurface, TimeSeriesVolume, prepare_time_slice
from tvb.basic.arguments_serialisation import preprocess_time_parameters, preprocess_space_parameters, postprocess_voxel_ts


class TimeSeriesH5(H5File):
    def __init__(self, path):
        super(TimeSeriesH5, self).__init__(path)
        self.title = Scalar(TimeSeries.title, self)
        self.data = DataSet(TimeSeries.data, self, expand_dimension=0)
        self.nr_dimensions = Scalar(TimeSeries.nr_dimensions, self)

        # omitted length_nd , these are indexing props, to be removed from datatype too
        self.labels_ordering = Json(TimeSeries.labels_ordering, self)
        self.labels_dimensions = Json(TimeSeries.labels_dimensions, self)

        self.time = DataSet(TimeSeries.time, self, expand_dimension=0)
        self.start_time = Scalar(TimeSeries.start_time, self)
        self.sample_period = Scalar(TimeSeries.sample_period, self)
        self.sample_period_unit = Scalar(TimeSeries.sample_period_unit, self)
        self.sample_rate = Scalar(TimeSeries.sample_rate, self)

        # omitted has_surface_mapping, has_volume_mapping, indexing props, to be removed fro datatype too

        # experiment: load header data eagerly, see surface for a lazy approach
        # as we do not explicitly make a difference between opening for read or write
        # the file might not yet exist, so loading headers makes no sense

        if self.storage_manager.is_valid_hdf5_file():
            self._sample_period = self.sample_period.load()
            self._start_time = self.start_time.load()


    # experimental port of some of the data access apis from the datatype
    # NOTE: some methods can not be here as they load data from dependent data types
    #       or they assume that dependent data has been loaded
    #       Those belong to a higher level where dependent h5 files are handles and
    #       partially loaded datatypes are filled


    def read_data_shape(self):
        return self.data.shape

    def read_data_slice(self, data_slice):
        """
        Expose chunked-data access.
        """
        return self.data[data_slice]


    def read_time_page(self, current_page, page_size, max_size=None):
        """
        Compute time for current page.
        :param current_page: Starting from 0
        """
        # todo: why are we even storing the time array if we return a synthetized version?
        current_page = int(current_page)
        page_size = int(page_size)

        if max_size is None:
            max_size = page_size
        else:
            max_size = int(max_size)

        page_real_size = page_size * self._sample_period
        start_time = self._start_time + current_page * page_real_size
        end_time = start_time + min(page_real_size, max_size * self._sample_period)

        return numpy.arange(start_time, end_time, self._sample_period)


    def read_channels_page(self, from_idx, to_idx, step=None, specific_slices=None, channels_list=None):
        """
        Read and return only the data page for the specified channels list.

        :param from_idx: the starting time idx from which to read data
        :param to_idx: the end time idx up until to which you read data
        :param step: increments in which to read the data. Optional, default to 1.
        :param specific_slices: optional parameter. If speficied slices the data accordingly.
        :param channels_list: the list of channels for which we want data
        """
        if channels_list:
            channels_list = json.loads(channels_list)
            for i in range(len(channels_list)):
                channels_list[i] = int(channels_list[i])

        if channels_list:
            channel_slice = tuple(channels_list)
        else:
            channel_slice = slice(None)

        data_page = self.read_data_page(from_idx, to_idx, step, specific_slices)
        # This is just a 1D array like in the case of Global Average monitor.
        # No need for the channels list
        if len(data_page.shape) == 1:
            return data_page.reshape(data_page.shape[0], 1)
        else:
            return data_page[:, channel_slice]


    def read_data_page(self, from_idx, to_idx, step=None, specific_slices=None):
        """
        Retrieve one page of data (paging done based on time).
        """
        from_idx, to_idx = int(from_idx), int(to_idx)

        if isinstance(specific_slices, basestring):
            specific_slices = json.loads(specific_slices)
        if step is None:
            step = 1
        else:
            step = int(step)

        slices = []
        overall_shape = self.data.shape
        for i in range(len(overall_shape)):
            if i == 0:
                # Time slice
                slices.append(
                    slice(from_idx, min(to_idx, overall_shape[0]), step))
                continue
            if i == 2:
                # Read full of the main_dimension (space for the simulator)
                slices.append(slice(overall_shape[i]))
                continue
            if specific_slices is None:
                slices.append(slice(0, 1))
            else:
                slices.append(slice(specific_slices[i], min(specific_slices[i] + 1, overall_shape[i]), 1))

        data = self.data[tuple(slices)]
        if len(data) == 1:
            # Do not allow time dimension to get squeezed, a 2D result need to
            # come out of this method.
            data = data.squeeze()
            data = data.reshape((1, len(data)))
        else:
            data = data.squeeze()

        return data


    def write_time_slice(self, partial_result):
        """
        Append a new value to the ``time`` attribute.
        """
        self.time.append(partial_result)

    def write_data_slice(self, partial_result, grow_dimension=0):
        """
        Append a chunk of time-series data to the ``data`` attribute.
        """
        self.data.append(partial_result)

    def get_min_max_values(self):
        """
        Retrieve the minimum and maximum values from the metadata.
        :returns: (minimum_value, maximum_value)
        """
        metadata = self.data.get_cached_metadata()
        return metadata.min, metadata.max

    def read_data_page_split(self, from_idx, to_idx, step=None, specific_slices=None):
        """
        No Split needed in case of basic TS (sensors and region level)
        """
        return self.read_data_page(from_idx, to_idx, step, specific_slices)


class TimeSeriesRegionH5(TimeSeriesH5):
    def __init__(self, path):
        super(TimeSeriesRegionH5, self).__init__(path)
        self.connectivity = Reference(TimeSeriesRegion.connectivity, self)
        self.region_mapping_volume = Reference(TimeSeriesRegion.region_mapping_volume, self)
        self.region_mapping = Reference(TimeSeriesRegion.region_mapping, self)
        self.labels_ordering = Json(TimeSeriesRegion.labels_ordering, self)

    # fixme: move to higher level where dependent files like self.connectivity can be provided
    #        or give up on the concept of one H5File has single responsibility of dealing with one file
    #        and let Reference know about a locator strategy and let it load files
    def get_volume_view(self, from_idx, to_idx, x_plane, y_plane, z_plane, var=0, mode=0):
        """
        Retrieve 3 slices through the Volume TS, at the given X, y and Z coordinates, and in time [from_idx .. to_idx].

        :param from_idx: int This will be the limit on the first dimension (time)
        :param to_idx: int Also limit on the first Dimension (time)
        :param x_plane: int coordinate
        :param y_plane: int coordinate
        :param z_plane: int coordinate

        :return: An array of 3 Matrices 2D, each containing the values to display in planes xy, yz and xy.
        """

        if self.region_mapping_volume is None:
            raise Exception("Invalid method called for TS without Volume Mapping!")

        volume_rm = self.region_mapping_volume

        # Work with space inside Volume:
        x_plane, y_plane, z_plane = preprocess_space_parameters(x_plane, y_plane, z_plane, volume_rm.length_1d,
                                                                volume_rm.length_2d, volume_rm.length_3d)
        var, mode = int(var), int(mode)
        slice_x, slice_y, slice_z = self.region_mapping_volume.get_volume_slice(x_plane, y_plane, z_plane)

        # Read from the current TS:
        from_idx, to_idx, current_time_length = preprocess_time_parameters(from_idx, to_idx, self.read_data_shape()[0])
        no_of_regions = self.read_data_shape()[2]
        time_slices = slice(from_idx, to_idx), slice(var, var + 1), slice(no_of_regions), slice(mode, mode + 1)

        min_signal = self.get_min_max_values()[0]
        regions_ts = self.read_data_slice(time_slices)[:, 0, :, 0]
        regions_ts = numpy.hstack((regions_ts, numpy.ones((current_time_length, 1)) * self.out_of_range(min_signal)))

        # Index from TS with the space mapping:
        result_x, result_y, result_z = [], [], []

        for i in range(0, current_time_length):
            result_x.append(regions_ts[i][slice_x].tolist())
            result_y.append(regions_ts[i][slice_y].tolist())
            result_z.append(regions_ts[i][slice_z].tolist())

        return [result_x, result_y, result_z]

    # TODO: move to higher level
    def get_voxel_time_series(self, x, y, z, var=0, mode=0):
        """
        Retrieve for a given voxel (x,y,z) the entire timeline.

        :param x: int coordinate
        :param y: int coordinate
        :param z: int coordinate

        :return: A complex dictionary with information about current voxel.
                The main part will be a vector with all the values over time from the x,y,z coordinates.
        """

        if self.region_mapping_volume is None:
            raise Exception("Invalid method called for TS without Volume Mapping!")

        volume_rm = self.region_mapping_volume
        x, y, z = preprocess_space_parameters(x, y, z, volume_rm.length_1d, volume_rm.length_2d, volume_rm.length_3d)
        idx_slices = slice(x, x + 1), slice(y, y + 1), slice(z, z + 1)

        idx = int(volume_rm.get_data('array_data', idx_slices))

        time_length = self.read_data_shape()[0]
        var, mode = int(var), int(mode)
        voxel_slices = prepare_time_slice(time_length), slice(var, var + 1), slice(idx, idx + 1), slice(mode, mode + 1)
        label = volume_rm.connectivity.region_labels[idx]

        background, back_min, back_max = None, None, None
        if idx < 0:
            back_min, back_max = self.get_min_max_values()
            background = numpy.ones((time_length, 1)) * self.out_of_range(back_min)
            label = 'background'

        result = postprocess_voxel_ts(self, voxel_slices, background, back_min, back_max, label)
        return result



class TimeSeriesSurfaceH5(TimeSeriesH5):
    def __init__(self, path):
        super(TimeSeriesSurfaceH5, self).__init__(path)
        self.surface = Reference(TimeSeriesSurface.surface, self)
        self.labels_ordering = Json(TimeSeriesSurface.labels_ordering, self)

    # fixme
    def read_data_page_split(self, from_idx, to_idx, step=None, specific_slices=None):

        basic_result = self.read_data_page(from_idx, to_idx, step, specific_slices)
        result = []
        if self.surface.number_of_split_slices <= 1:
            result.append(basic_result.tolist())
        else:
            for slice_number in range(self.surface.number_of_split_slices):
                start_idx, end_idx = self.surface._get_slice_vertex_boundaries(slice_number)
                result.append(basic_result[:,start_idx:end_idx].tolist())

        return result


class TimeSeriesVolumeH5(TimeSeriesH5):
    def __init__(self, path):
        super(TimeSeriesVolumeH5, self).__init__(path)
        self.volume = Reference(TimeSeriesVolume.volume, self)
        self.labels_ordering = Json(TimeSeriesVolume.labels_ordering, self)


    def get_volume_view(self, from_idx, to_idx, x_plane, y_plane, z_plane, **kwargs):
        """
        Retrieve 3 slices through the Volume TS, at the given X, y and Z coordinates, and in time [from_idx .. to_idx].

        :param from_idx: int This will be the limit on the first dimension (time)
        :param to_idx: int Also limit on the first Dimension (time)
        :param x_plane: int coordinate
        :param y_plane: int coordinate
        :param z_plane: int coordinate

        :return: An array of 3 Matrices 2D, each containing the values to display in planes xy, yz and xy.
        """

        overall_shape = self.data.shape
        from_idx, to_idx, time = preprocess_time_parameters(from_idx, to_idx, overall_shape[0])
        x_plane, y_plane, z_plane = preprocess_space_parameters(x_plane, y_plane, z_plane,
                                                                overall_shape[1], overall_shape[2], overall_shape[3])

        slices = slice(from_idx, to_idx), slice(overall_shape[1]), slice(overall_shape[2]), slice(z_plane, z_plane + 1)
        slicex = self.read_data_slice(slices)[:, :, :, 0].tolist()

        slices = slice(from_idx, to_idx), slice(x_plane, x_plane + 1), slice(overall_shape[2]), slice(overall_shape[3])
        slicey = self.read_data_slice(slices)[:, 0, :, :][..., ::-1].tolist()

        slices = slice(from_idx, to_idx), slice(overall_shape[1]), slice(y_plane, y_plane + 1), slice(overall_shape[3])
        slicez = self.read_data_slice(slices)[:, :, 0, :][..., ::-1].tolist()

        return [slicex, slicey, slicez]


    def get_voxel_time_series(self, x, y, z, **kwargs):
        """
        Retrieve for a given voxel (x,y,z) the entire timeline.

        :param x: int coordinate
        :param y: int coordinate
        :param z: int coordinate

        :return: A complex dictionary with information about current voxel.
                The main part will be a vector with all the values over time from the x,y,z coordinates.
        """

        overall_shape = self.data.shape
        x, y, z = preprocess_space_parameters(x, y, z, overall_shape[1], overall_shape[2], overall_shape[3])

        slices = prepare_time_slice(overall_shape[0]), slice(x, x + 1), slice(y, y + 1), slice(z, z + 1)

        result = postprocess_voxel_ts(self, slices)
        return result
