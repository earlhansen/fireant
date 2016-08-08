# coding: utf-8
import copy
import logging

from fireant import settings
from pypika import Query, Interval

logger = logging.getLogger(__name__)

reference_criterion = {
    'yoy': lambda key, join_key: key == join_key - Interval(weeks=52),
    'qoq': lambda key, join_key: key == join_key - Interval(quarters=1),
    'mom': lambda key, join_key: key == join_key - Interval(weeks=4),
    'wow': lambda key, join_key: key == join_key - Interval(weeks=1),
}
reference_field = {
    'd': lambda field, join_field: field - join_field,
    'p': lambda field, join_field: (field - join_field) / join_field,
}


class QueryManager(object):
    def _query_data(self, table=None, joins=None,
                    metrics=None, dimensions=None,
                    mfilters=None, dfilters=None,
                    references=None, rollup=None):
        """
        Loads a pandas data frame given a table and a description of the request.

       :param table:
            Type: pypika.Table
            (Required) The primary table to select data from.  In SQL, this is the table in the FROM clause.

        :param joins:
            Type: list[tuple[pypika.Table, pypika.Criterion, pypika.JoinType]]
            (Optional) A list of tables to join in the query.  If a metric should be selected from a table besides the
            table parameter, the additional table *must* be joined.

            The tuple includes in the following order: Join table, Join criterion, Join type

        :param metrics:
            Type: dict[str: pypika.Field]]
            A dict containing metrics fields to query.  This value is required to contain at least one entry.  The key used
            will match the corresponding column in the returned pd.DataFrame.

        :param dimensions:
            Type: OrderedDict[str: pypika.Field]]
            (Optional) An OrderedDict containing indices to query.  If empty, a pd.Series will be returned containing one
            value per metric.  If given one entry, a pd.DataFrame with a single index will be returned.  If more than one
            value is given, then a pd.DataFrame with a multi-index will be returned.  The key used will match the
            corresponding index level in the returned DataFrame.

            If a dict is used instead of an OrderedDict, then the index levels cannot be guarenteed, so in most cases an
            OrderedDict should be used.

        :param mfilters:
            Type: list[pypika.Criterion]
            (Optional) A list containing criterions to use in the HAVING clause of the query.  This will reduce the data
            to instances where metrics meet the criteria.

        :param dfilters:
            Type: list[pypika.Criterion]
            (Optional) A list containing criterions to use in the WHERE clause of the query.  This will reduce the data
            to instances where dimensions meet the criteria.

        :param references:
            Type: dict[str: str]]
            (Optional) A dict containing comparison operations.  The key must match a valid reference.  The value must
            match the key of a provided dimension.  The value must match a dimensions of the appropriate type, usually a
            Time Series dimension.

            For each value passed, the query will be duplicated containing values for a comparison.

            References can also modify the comparison field to show values such as change.  The format is as follows:

            {key}_{modifier}

            The modifier type is optional and the underscore must be omitted when one is not used.

            Valid references are as follows:

            - *wow*: Week over Week - duplicates the query for values one week prior.
            - *mom*: Month over Month - duplicates the query for values 4 weeks prior.
            - *qoq*: Quarter over Quarter - duplicates the query for values one quarter prior.
            - *yoy*: Year over Year - duplicates the query for values 52 weeks prior.

            Valid modifier types are as follows:

            - *d*: Delta - difference between previous value and current
            - *p*: Delta Percentage - difference between previous value and current as a percentage of the previous value.

            Examples:

            "wow":   Week over Week
            "wow_d": delta Week over Week

        :param rollup:
            Type: list[str]
            (Optional) Lists the dimensions to include for ROLLUP which calculates the totals across groups.  This list
            must be a subset of the keys of the dimensions parameter dict.

            .. note::

                When using rollup for less than all of the dimensions, the dimensions included in the ROLLUP will be
                moved after the non-ROLLUP dimensions.

        :return:
            A pd.DataFrame indexed by the provided dimensions paramaters containing columns for each metrics parameter.
        """
        query = self._build_query(table, joins or dict(), metrics or dict(),
                                  dimensions or dict(), mfilters or dict(), dfilters or dict(),
                                  references or dict(),
                                  rollup or dict())

        df_idx = query.groupby_aliases()
        df_cols = query.select_aliases()

        query_str = str(query)
        if getattr(settings, 'debug', False):
            print("Executing query:\n----START----\n{query}\n-----END-----".format(query=query_str))

        return settings.database.fetch_dataframe(query_str, columns=df_cols, index=df_idx).sort_index()

    def _build_query(self, table, joins, metrics, dimensions, mfilters, dfilters, references, rollup):
        # Initialize query
        query = Query.from_(table)

        # Add join tables
        for join_table, criterion, join_type in joins:
            query = query.join(join_table, how=join_type).on(criterion)

        # Select dimensions
        dx = [dimension.as_(key)
              for key, dimension in dimensions.items()
              if key not in rollup]
        rx = [dimension.as_(key)
              for key, dimension in dimensions.items()
              if key in rollup]

        if dx:
            query = query.select(*dx).groupby(*dx)
        if rx:
            query = query.select(*rx).rollup(*rx)

        # Select metrics
        mx = [metric.as_(key) for key, metric in metrics.items()]
        query = query.select(*mx)

        # Add comparisons
        for reference_key, dimension_key in references.items():
            criterion_f, field_f = self._get_reference_mappers(reference_key)

            reference_query = copy.deepcopy(query)
            cx = self._build_reference_join_criterion(reference_query, dimensions, criterion_f, dimension_key)

            query = query.join(reference_query).on(cx)

            # Select all of the comparison dimensions
            # TODO maybe just select the dimensions that is different
            if dimensions:
                query = query.select(*[reference_query.field(key).as_('%s_%s' % (key, reference_key))
                                       for key, dimension in dimensions.items()])

            # Select all of the comparison metrics
            query = query.select(*[field_f(metric, reference_query.field(key)).as_('%s_%s' % (key, reference_key))
                                   for key, metric in metrics.items()])

        # Add ordering
        if dx:
            query = query.orderby(*dx)
        if rx:
            query = query.orderby(*rx)

        # Add filters
        if dfilters:
            for dfx in dfilters:
                query = query.where(dfx)

        if mfilters:
            for mfx in mfilters:
                query = query.having(mfx)

        return query

    @staticmethod
    def _get_reference_mappers(reference_key):
        """
        Selects the mapper functions for a reference operation.

        :param reference_key:
            A string identifier that maps to the reference operations.  This contains one to two parts separated by an
            underscore '_' character.  The first part is required and maps to a reference criteria from the dict
            reference_criterion.  The second part is optional and maps to a reference field from the dict
            reference_field.

            The reference criteria is the criteria used to link the values from the original query to the comparison
            values.  For example, in wow (Week over Week), the criteria maps a date field to the same date field minus one
            week.

            The reference field is an optional part that modifies the selected field in the final results.  For example,
            in wow-p (Week over Week change as a Percentage), the final field is the query field minus the comparison
            field as a ratio of the join field.  This gives the change in value over the last week as a percentage of
            the current value.  If the reference key does not contain two parts (no '_' character), then a function will
            still be returned for field_f, however it will not modify the final field.

            Concretely, if the field is clicks and current value is 105 and the wow value is 100, then the change is
            (105 - 100) = 5 clicks, then the wow-p value is (105 - 100) / 100 = 0.05.
        :return:
            Type: Tuple
            (criterion_f, function_f)
        """
        reference_key, *optional_parts = reference_key.split('_')

        # Maps function
        criterion_f = reference_criterion[reference_key]
        field_f = reference_field[optional_parts[0]] if optional_parts else lambda field, join_field: join_field
        return criterion_f, field_f

    @staticmethod
    def _build_reference_join_criterion(query, dimensions, criterion_f, dimension_key):
        """
        Returns join criterion for joining a reference query.

        :param query:

        :param dimensions:

        :param criterion_f:

        :param dimension_key:

        :return:
            join criterion for joining a reference query.
        """
        compared_dimension = dimensions[dimension_key]
        cx = criterion_f(compared_dimension, query.field(dimension_key))
        for dimension in dimensions.values():
            if dimension is not compared_dimension:
                cx &= dimension == dimension.for_(query)
        return cx