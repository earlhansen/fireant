# coding: utf-8
from pypika import functions as fn, Field
from pypika.terms import Mod

from fireant import settings
from fireant.slicer.managers import SlicerManager


class SlicerElement(object):
    """
    The `SlicerElement` class represents a vertica table column.
    params:
        key: a unique identifier of the column.
        label: a human representation of the column, if not provided it's capitalised version of the key.
    """

    def __init__(self, key, label=None, definition=None, joins=None):
        self.key = key
        self.label = label or ' '.join(key.capitalize().split('_'))
        self.definition = definition
        self.joins = joins

    def __unicode__(self):
        return self.key

    def __repr__(self):
        return self.key

    def schemas(self, *args):
        return [
            (self.key, self.definition)
        ]


class Metric(SlicerElement):
    """
    The `Metric` class represents a metric in the `Slicer` object.
    """

    def __init__(self, key, label=None, definition=None, joins=None):
        super(Metric, self).__init__(key, label, definition or fn.Sum(Field(key)), joins)


class Dimension(SlicerElement):
    """
    The `Dimension` class represents a dimension in the `Slicer` object.
    """

    def __init__(self, key, label=None, definition=None, joins=None):
        super(Dimension, self).__init__(key, label, definition or Field(key) or fn.Sum(Field(key)), joins)


class NumericInterval(object):
    def __init__(self, size=1, offset=0):
        self.size = size
        self.offset = offset

    def __eq__(self, other):
        return isinstance(other, NumericInterval) and self.size == other.size and self.offset == other.offset

    def __hash__(self):
        return hash('NumericInterval %d %d' % (self.size, self.offset))

    def __str__(self):
        return 'NumericInterval(size=%d,offset=%d)' % (self.size, self.offset)


class ContinuousDimension(Dimension):
    def __init__(self, key, label=None, definition=None, default_interval=NumericInterval(1, 0)):
        super(ContinuousDimension, self).__init__(key=key, label=label, definition=definition)
        self.default_interval = default_interval

    def schemas(self, *args):
        size, offset = args if args else (self.default_interval.size, self.default_interval.offset)
        return [(self.key, Mod(self.definition + offset, size))]


class DatetimeInterval(object):
    def __init__(self, size):
        self.size = size

    def __eq__(self, other):
        return isinstance(other, DatetimeInterval) and self.size == other.size

    def __hash__(self):
        return hash('DatetimeInterval %s' % self.size)

    def __str__(self):
        return 'DatetimeInterval(interval=%s)' % self.size


class DatetimeDimension(ContinuousDimension):
    hour = DatetimeInterval('HH')
    day = DatetimeInterval('DD')
    week = DatetimeInterval('WW')
    month = DatetimeInterval('MM')
    quarter = DatetimeInterval('Q')
    year = DatetimeInterval('IY')

    def __init__(self, key, label=None, definition=None, default_interval=day):
        super(DatetimeDimension, self).__init__(key=key, label=label, definition=definition,
                                                default_interval=default_interval)

    def schemas(self, *args):
        interval = args[0] if args else self.default_interval
        # TODO fix this to work for different databases
        return [(self.key, settings.database.round_date(self.definition, interval.size))]


class CategoricalDimension(Dimension):
    def __init__(self, key, label=None, definition=None, options=tuple()):
        super(CategoricalDimension, self).__init__(key=key, label=label, definition=definition)
        self.options = options


class UniqueDimension(Dimension):
    def __init__(self, key, label=None, label_field=None, id_fields=None):
        super(UniqueDimension, self).__init__(key=key, label=label, definition=label_field)
        # TODO label_field and definition here are redundant
        self.label_field = label_field
        self.id_fields = id_fields

    def schemas(self, *args):
        id_field_schemas = [('{key}_id{ordinal}'.format(key=self.key, ordinal=i), id_field)
                            for i, id_field in enumerate(self.id_fields)]
        return id_field_schemas + [('{key}_label'.format(key=self.key), self.definition)]


class BooleanDimension(Dimension):
    def __init__(self, key, label=None, definition=None):
        super(BooleanDimension, self).__init__(key=key, label=label, definition=definition)


class DimensionValue(object):
    """
    An option belongs to a categorical dimension which specifies a fixed set of values
    """

    def __init__(self, key, label=None):
        self.key = key
        self.label = label


class Slicer(object):
    def __init__(self, table, joins=tuple(), metrics=tuple(), dimensions=tuple()):
        self.table = table
        self.joins = joins

        self.metrics = {metric.key: metric for metric in metrics}
        self.dimensions = {dimension.key: dimension for dimension in dimensions}

        self.manager = SlicerManager(self)


class EqualityOperator(object):
    eq = 'eq'
    ne = 'ne'
    gt = 'gt'
    lt = 'lt'
    gte = 'gte'
    lte = 'lte'