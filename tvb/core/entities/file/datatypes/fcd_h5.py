from tvb.datatypes.fcd import Fcd

from tvb.core.entities.file.datatypes.spectral_h5 import DataTypeMatrixH5
from tvb.core.neotraits.h5 import DataSet, Reference, Scalar, Json


class FcdH5(DataTypeMatrixH5):

    def __init__(self, path):
        super(FcdH5, self).__init__(path)
        self.array_data = DataSet(Fcd.array_data)
        self.source = Reference(Fcd.source)
        self.sw = Scalar(Fcd.sw)
        self.sp = Scalar(Fcd.sp)
        self.labels_ordering = Json(Fcd.labels_ordering)
        self._end_accessor_declarations()
