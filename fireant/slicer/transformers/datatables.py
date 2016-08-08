# coding: utf-8
import numpy as np
import pandas as pd

from .base import Transformer


class TableIndex(object):
    column_index = 'col'
    row_index = 'row'


class DataTablesTransformer(Transformer):
    def __init__(self, table_type=TableIndex.row_index):
        self.table_type = table_type

    def transform(self, data_frame, display_schema):
        dim_ordinal = {name: ordinal
                       for ordinal, name in enumerate(data_frame.index.names)}

        data_frame = self._prepare_data_frame(data_frame, display_schema['dimensions'])
        records = len(data_frame)

        data = []
        for row_id, (idx, row) in enumerate(data_frame.iterrows()):
            record = {'DT_RowId': 'row_%d' % row_id}

            for key, value in self._render_index_levels(idx, dim_ordinal, display_schema):
                record[key] = value

            for key, value in self._render_column_levels(row, dim_ordinal, display_schema):
                record[key] = value

            data.append(record)

        return {
            'draw': 1,
            'recordsTotal': records,
            'recordsFiltered': records,
            'data': data,
        }

    def _prepare_data_frame(self, data_frame, dimensions):
        # Replaces invalid values and unstacks the data frame for column_index tables.
        data_frame = data_frame.replace([np.inf, -np.inf], np.nan)

        if 1 < len(dimensions) and self.table_type == TableIndex.column_index:
            unstack_levels = list(range(
                len(dimensions[0]['id_fields']),
                len(data_frame.index.levels))
            )
            return data_frame.unstack(level=unstack_levels)

        return data_frame

    def _render_index_levels(self, idx, dim_ordinal, display_schema):
        row_dimensions = display_schema['dimensions'][:None if self.table_type == TableIndex.row_index else 1]
        for dimension in row_dimensions:
            key = dimension['label']

            if not isinstance(idx, tuple):
                value = idx

            elif 1 < len(dimension['id_fields']) or 'label_field' in dimension:
                fields = dimension['id_fields'] + [dimension.get('label_field')]

                value = {id_field: idx[dim_ordinal[id_field]]
                         for id_field in filter(None, fields)}

            else:
                id_field = dimension['id_fields'][0]
                value = idx[dim_ordinal[id_field]]

                if value is np.nan:
                    value = 'Total'

                if 'label_options' in dimension:
                    value = dimension['label_options'].get(value, value)

            yield key, value

    def _render_column_levels(self, row, dim_ordinal, display_schema):
        if isinstance(row.index, pd.MultiIndex):
            # Multi level columns
            for idx, value in row.iteritems():
                label = self._format_series_labels(idx, dim_ordinal, display_schema)
                yield label, value

        else:
            # Single level columns
            for col in row.index:
                yield display_schema['metrics'][col], row[col]

    def _format_series_labels(self, idx, dim_ordinal, display_schema):
        metric, *dimensions = idx

        if not [d for d in dimensions if d is not np.nan]:
            # If all the dimensions are NaN the data frame, then do not display them.
            return display_schema['metrics'][metric]

        metric_label = display_schema['metrics'].get(idx[0], idx[0])
        dimension_labels = [self._format_dimension_label(idx, dim_ordinal, dimension)
                            for dimension in display_schema['dimensions'][1:]]
        dimension_labels = [dim_label  # filter out the NaNs
                            for dim_label in dimension_labels
                            if dim_label is not np.nan]

        return (
            '{metric} ({dimensions})'.format(metric=metric_label, dimensions=', '.join(dimension_labels))
            if dimension_labels else
            metric_label
        )

    @staticmethod
    def _format_dimension_label(idx, dim_ordinal, dimension):
        if 'label_field' in dimension:
            label_field = dimension['label_field']
            return idx[dim_ordinal[label_field]]

        if isinstance(idx, tuple):
            id_field = dimension['id_fields'][0]
            dimension_label = idx[dim_ordinal[id_field]]

        else:
            dimension_label = idx

        if 'label_options' in dimension:
            dimension_label = dimension['label_options'].get(dimension_label, dimension_label)

        return dimension_label


class CSVTransformer(DataTablesTransformer):
    def __init__(self, table_type=TableIndex.row_index):
        self.table_type = table_type

    def transform(self, data_frame, display_schema):
        dim_ordinal = {name: ordinal
                       for ordinal, name in enumerate(data_frame.index.names)}

        csv_df = self._format_columns(data_frame, dim_ordinal, display_schema)

        if isinstance(data_frame.index, pd.RangeIndex):
            # If there are no dimensions, just serialize to csv without the index
            return csv_df.to_csv(index=False)

        csv_df = self._format_index(csv_df, dim_ordinal, display_schema)

        row_dimensions = display_schema['dimensions'][:None if self.table_type == TableIndex.row_index else 1]
        return csv_df.to_csv(index_label=[dimension['label']
                                          for dimension in row_dimensions])

    def _format_index(self, csv_df, dim_ordinal, display_schema):
        if isinstance(csv_df.index, pd.MultiIndex):
            csv_df.index = pd.MultiIndex.from_tuples(
                [[self._format_dimension_label(idx, dim_ordinal, dimension)
                  for dimension in display_schema['dimensions']]
                 for idx in list(csv_df.index)]
            )

        else:
            csv_df.reindex(
                self._format_dimension_label(idx, dim_ordinal, display_schema['dimensions'][0])
                for idx in list(csv_df.index)
            )

        return csv_df

    def _format_columns(self, data_frame, dim_ordinal, display_schema):
        if 1 < len(display_schema['dimensions']) and self.table_type == TableIndex.column_index:
            csv_df = self._prepare_data_frame(data_frame, display_schema['dimensions'])

            csv_df.columns = pd.Index([self._format_series_labels(column, dim_ordinal, display_schema)
                                       for column in csv_df.columns])
            return csv_df

        return data_frame.rename(
            columns=lambda metric: display_schema['metrics'].get(metric, metric)
        )