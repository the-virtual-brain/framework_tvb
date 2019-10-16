import pytest
import os

from sqlalchemy.orm import sessionmaker, relationship
from tvb.core.neotraits.db import Base, NArrayIndex
from sqlalchemy import create_engine, String, ForeignKey, Column, Integer
from tvb.tests.framework.core.neotraits.data import FooDatatype


class FooIndexManual(Base):
    __tablename__ = 'testdatatype_manual'
    id = Column(Integer, primary_key=True)

    array_float_id = Column(Integer, ForeignKey('narrays.id'), nullable=False)
    array_float = relationship(NArrayIndex, foreign_keys=array_float_id)

    array_int_id = Column(Integer, ForeignKey('narrays.id'), nullable=False)
    array_int = relationship(NArrayIndex, foreign_keys=array_int_id)

    scalar_str = Column(String, nullable=False)
    scalar_int = Column(Integer, nullable=False)

    def from_datatype(self, datatype):
        self.array_float = NArrayIndex(dtype=str(datatype.array_float.dtype),
                                          ndim=datatype.array_float.ndim,
                                          shape=str(datatype.array_float.shape))
        self.array_int = NArrayIndex(dtype=str(datatype.array_int.dtype),
                                        ndim=datatype.array_int.ndim,
                                        shape=str(datatype.array_int.shape))
        self.scalar_str = datatype.scalar_str
        self.scalar_int = datatype.scalar_int


class FooIndex(Base):
    trait = FooDatatype
    fields = [
        FooDatatype.array_float,
        FooDatatype.array_int,
        FooDatatype.scalar_int,
        FooDatatype.scalar_str
    ]


@pytest.fixture(scope='session')
def engine(tmpdir_factory):
    tmpdir = tmpdir_factory.mktemp('tmp')
    path = os.path.join(str(tmpdir), 'tmp.sqlite')
    return create_engine(r'sqlite:///' + path)


@pytest.fixture
def session(engine):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_schema(session):
    session.query(FooIndexManual)


def test_store_load(session, datatypeinstance):
    datatype_index = FooIndexManual()
    datatype_index.from_datatype(datatypeinstance)

    datatype_index2 = FooIndex()
    datatype_index2.from_datatype(datatypeinstance)

    session.add_all([datatype_index, datatype_index2])
    session.commit()

    res = session.query(FooIndexManual)
    assert res.count() == 1
    assert res[0].array_float.dtype == 'float64'
