import uuid

import typing
import os.path
import abc
import numpy
from tvb.core.entities.file.exceptions import MissingDataSetException

from tvb.core.entities.file.hdf5_storage_manager import HDF5StorageManager
from tvb.basic.neotraits.api import HasTraits, Attr, NArray


def is_scalar_type(t):
    return (
        t in [bool, ] or
        issubclass(t, basestring) or
        numpy.issubdtype(t, numpy.number)
    )


class Accessor(object):
    def __init__(self, trait_attribute, h5file, name=None):
        # type: (Attr, H5File, str) -> None
        """
        :param trait_attribute: A traited attribute
        :param h5file: The parent H5file that contains this Accessor
        :param name: The name of the dataset or attribute in the h5 file.
                     It defaults to the name of the associated traited attribute.
                     If the traited attribute is not a member of a HasTraits then
                     it has no name and you have to provide this parameter
        """
        self.owner = h5file
        self.trait_attribute = trait_attribute

        if name is None:
            name = trait_attribute.field_name

        self.field_name = name

        if self.field_name is None:
            raise ValueError('Accessor {} needs a name'.format(self))

    @abc.abstractmethod
    def load(self):
        pass

    @abc.abstractmethod
    def store(self, val):
        pass

    def __repr__(self):
        cls = type(self)
        return '<{}.{}({}, name="{}")>'.format(
            cls.__module__, cls.__name__, self.trait_attribute, self.field_name
        )


class Scalar(Accessor):
    """
    A scalar in a h5 file that corresponds to a traited attribute.
    Serialized as a global h5 attribute
    """

    def store(self, val):
        # type: (typing.Union[str, int, float]) -> None
        # noinspection PyProtectedMember
        val = self.trait_attribute._validate_set(None, val)
        self.owner.storage_manager.set_metadata({self.field_name: val})

    def load(self):
        # type: () -> typing.Union[str, int, float]
        # assuming here that the h5 will return the type we stored.
        # if paranoid do self.trait_attribute.field_type(value)
        return self.owner.storage_manager.get_metadata()[self.field_name]



class DataSetMetaData(object):
    """
    simple container for dataset metadata
    Useful as a cache of global min max values.
    Viewers rely on these for colorbars.
    """

    # noinspection PyShadowingBuiltins
    def __init__(self, min, max):
        self.min, self.max = min, max

    @classmethod
    def from_array(cls, array):
        try:
            return cls(min=array.min(), max=array.max())
        except (TypeError, ValueError):
            # likely a string array
            return cls(min=None, max=None)

    @classmethod
    def from_dict(cls, dikt):
        return cls(min=dikt['Minimum'], max=dikt['Maximum'])

    def to_dict(self):
        return {'Minimum': self.min, 'Maximum': self.max}



class DataSet(Accessor):
    """
    A dataset in a h5 file that corresponds to a traited NArray.
    """
    def __init__(self, trait_attribute, h5file, name=None, expand_dimension=None):
        # type: (NArray, H5File, str, int) -> None
        """
        :param trait_attribute: A traited attribute
        :param h5file: The parent H5file that contains this Accessor
        :param name: The name of the dataset in the h5 file.
                     It defaults to the name of the associated traited attribute.
                     If the traited attribute is not a member of a HasTraits then
                     it has no name and you have to provide this parameter
        :param expand_dimension: An int designating a dimension of the array that may grow.
        """
        super(DataSet, self).__init__(trait_attribute, h5file, name)
        self.expand_dimension = expand_dimension

    def append(self, data, close_file=True):
        # type: (numpy.ndarray, bool) -> None
        self.owner.storage_manager.append_data(
            self.field_name,
            data,
            grow_dimension=self.expand_dimension,
            close_file=close_file
        )
        # todo update the cached array min max metadata values

    # noinspection PyProtectedMember
    def store(self, data):
        # type: (numpy.ndarray) -> None
        data = self.trait_attribute._validate_set(None, data)
        if data is None:
            return

        self.owner.storage_manager.store_data(self.field_name, data)
        # cache some array information
        self.owner.storage_manager.set_metadata(
            DataSetMetaData.from_array(data).to_dict(),
            self.field_name
        )

    def load(self):
        # type: () -> numpy.ndarray
        return self.owner.storage_manager.get_data(self.field_name)

    def __getitem__(self, data_slice):
        # type: (typing.Tuple[slice, ...]) -> numpy.ndarray
        return self.owner.storage_manager.get_data(self.field_name, data_slice)

    @property
    def shape(self):
        # type: () -> typing.Tuple[int]
        return self.owner.storage_manager.get_data_shape(self.field_name)

    def get_cached_metadata(self):
        """
        Returns cached properties of this dataset, like min max mean etc.
        This cache is useful for large, expanding datasets,
        when we want to avoid loading the whole dataset just to compute a max.
        """
        meta = self.owner.storage_manager.get_metadata(self.field_name)
        return DataSetMetaData.from_dict(meta)



class Reference(Scalar):
    """
    A reference to another h5 file
    Corresponds to a contained datatype
    """
    def store(self, val):
        # type: (HasTraits) -> None
        """
        The reference is stored as a gid in the metadata.
        :param val: a datatype or a uuid.UUID gid
        """
        if val is None and not self.trait_attribute.required:
            # this is an optional reference and it is missing
            return
        if isinstance(val, HasTraits):
            val = val.gid
        if not isinstance(val, uuid.UUID):
            raise TypeError("expected uuid.UUId or HasTraits, got {}".format(type(val)))
        # urn is a standard encoding, that is obvious an uuid
        # str(gid) is more ambiguous
        self.owner.storage_manager.set_metadata({self.field_name: val.urn})

    def load(self):
        urngid = super(Reference, self).load()
        return uuid.UUID(urngid)



class H5File(object):
    """
    A H5 based file format.
    This class implements reading and writing to a *specific* h5 based file format.
    A subclass of this defines a new file format.
    """

    def __init__(self, path):
        # type: (str) -> None
        self.path = path
        storage_path, file_name = os.path.split(path)
        self.storage_manager = HDF5StorageManager(storage_path, file_name)
        # would be nice to have an opened state for the chunked api instead of the close_file=False

    def iter_accessors(self):
        # type: () -> typing.Generator[Accessor]
        for accessor in self.__dict__.itervalues():
            if isinstance(accessor, Accessor):
                yield accessor


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        # write_metadata  creation time, serializer class name, etc
        self.storage_manager.set_metadata({
            'written_by': self.__class__.__module__ + '.' + self.__class__.__name__,
        })
        self.storage_manager.close_file()


    def store(self, datatype, scalars_only=False):
        # type: (HasTraits, bool) -> None
        for accessor in self.iter_accessors():
            f_name = accessor.trait_attribute.field_name
            if f_name is None:
                # skipp attribute that does not seem to belong to a traited type
                continue
            if not hasattr(datatype, f_name):
                raise AttributeError(
                    '{} has not attribute "{}". You tried to store a {!r}. '
                    'Is that datatype compatible with the field declarations in {}?'.format(
                        accessor.trait_attribute, f_name, datatype, self.__class__
                    )
                )
            if scalars_only and not isinstance(accessor, Scalar):
                continue
            accessor.store(getattr(datatype, f_name))


    def load_into(self, datatype):
        # type: (HasTraits) -> None
        for accessor in self.iter_accessors():
            if isinstance(accessor, Reference):
                # we do not load references recursively
                continue
            f_name = accessor.trait_attribute.field_name
            if f_name is None:
                # skipp attribute that does not seem to belong to a traited type
                continue

            # handle optional data, that will be missing from the h5 files
            try:
                value = accessor.load()
            except MissingDataSetException:
                if accessor.trait_attribute.required:
                    raise
                else:
                    value = None

            setattr(datatype, f_name, value)


    def gather_references(self):
        ret = []
        for accessor in self.iter_accessors():
            if isinstance(accessor, Reference):
                ret.append((accessor.trait_attribute.field_name, accessor.load()))
        return ret

    def __repr__(self):
        return '<{}("{}")>'.format(type(self).__name__, self.path)

