# coding: utf-8


from fireant.slicer.transformers import HighchartsTransformer, TransformationException, HighchartsColumnTransformer
from fireant.tests.slicer.transformers.base import BaseTransformerTests


class HighChartsLineTransformerTests(BaseTransformerTests):
    """
    Line charts work with the following requests:

    1-cont-dim, *-metric
    1-cont-dim, *-dim, *-metric
    """
    hc_tx = HighchartsTransformer()
    type = HighchartsTransformer.line

    def evaluate_result(self, df, result):
        result_data = [series['data'] for series in result['series']]

        for data, (_, row) in zip(result_data, df.iteritems()):
            self.assertListEqual(list(row.items()), data)

    def evaluate_chart_options(self, result, n_results=1, xaxis_type='linear'):
        self.assertSetEqual({'title', 'series', 'chart', 'tooltip', 'xAxis', 'yAxis'}, set(result.keys()))
        self.assertEqual(n_results, len(result['series']))

        self.assertSetEqual({'text'}, set(result['title'].keys()))
        self.assertIsNone(result['title']['text'])

        self.assertEqual(self.type, result['chart']['type'])

        self.assertSetEqual({'type'}, set(result['xAxis'].keys()))
        self.assertEqual(xaxis_type, result['xAxis']['type'])

        for series in result['series']:
            self.assertSetEqual({'name', 'data', 'yAxis'}, set(series.keys()))

    def test_series_single_metric(self):
        # Tests transformation of a single-metric, single-dimension result
        df = self.cont_dim_single_metric_df

        result = self.hc_tx.transform(df, self.cont_dim_single_metric_schema)

        self.evaluate_chart_options(result)

        self.assertSetEqual(
            {'One'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df, result)

    def test_series_multi_metric(self):
        # Tests transformation of a multi-metric, single-dimension result
        df = self.cont_dim_multi_metric_df

        result = self.hc_tx.transform(df, self.cont_dim_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=2)

        self.assertSetEqual(
            {'One', 'Two'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df, result)

    def test_time_series_date_to_millis(self):
        # Tests transformation of a single-metric, single-dimension result
        df = self.time_dim_single_metric_df

        result = self.hc_tx.transform(df, self.time_dim_single_metric_schema)

        self.evaluate_chart_options(result, xaxis_type='datetime')

        self.assertSetEqual(
            {'One'},
            {series['name'] for series in result['series']}
        )

        df2 = df
        df2.index = df2.index.astype(int) // 1e6
        self.evaluate_result(df2, result)

    def test_cont_uni_dim_single_metric(self):
        # Tests transformation of a metric with a unique dimension with one key and label
        df = self.cont_uni_dims_single_metric_df

        result = self.hc_tx.transform(df, self.cont_uni_dims_single_metric_schema)

        self.evaluate_chart_options(result, n_results=4)

        self.assertSetEqual(
            {'One (Uni2_1)', 'One (Uni2_2)', 'One (Uni2_3)', 'One (Uni2_4)'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df.unstack(level=[1, 2, 3]), result)

    def test_cont_uni_dim_multi_metric(self):
        # Tests transformation of two metrics with a unique dimension with two keys and label
        df = self.cont_uni_dims_multi_metric_df

        result = self.hc_tx.transform(df, self.cont_uni_dims_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=8)

        self.assertSetEqual(
            {'One (Uni2_1)', 'One (Uni2_2)', 'One (Uni2_3)', 'One (Uni2_4)',
             'Two (Uni2_1)', 'Two (Uni2_2)', 'Two (Uni2_3)', 'Two (Uni2_4)'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df.unstack(level=[1, 2, 3]), result)

    def test_double_dimension_single_metric(self):
        # Tests transformation of a single-metric, double-dimension result
        df = self.cont_cat_dims_single_metric_df

        result = self.hc_tx.transform(df, self.cont_cat_dims_single_metric_schema)

        self.evaluate_chart_options(result, n_results=2)

        self.assertSetEqual(
            {'One (A)', 'One (B)'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df.unstack(level=1), result)

    def test_double_dimension_multi_metric(self):
        # Tests transformation of a multi-metric, double-dimension result
        df = self.cont_cat_dims_multi_metric_df

        result = self.hc_tx.transform(df, self.cont_cat_dims_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=4)

        self.assertSetEqual(
            {'One (A)', 'One (B)', 'Two (A)', 'Two (B)'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df.unstack(level=1), result)

    def test_triple_dimension_multi_metric(self):
        # Tests transformation of a multi-metric, double-dimension result
        df = self.cont_cat_cat_dims_multi_metric_df

        result = self.hc_tx.transform(df, self.cont_cat_cat_dims_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=8)

        self.assertSetEqual(
            {'One (A, Y)', 'One (A, Z)', 'One (B, Y)', 'One (B, Z)',
             'Two (A, Y)', 'Two (A, Z)', 'Two (B, Y)', 'Two (B, Z)'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df.unstack(level=[1, 2]), result)

    def test_mixed_order_dimensions(self):
        # Tests transformation of a multi-metric, double-dimension result
        df = self.cont_cat_uni_dims_multi_metric_df.reorder_levels([1, 2, 4, 0, 3])

        result = self.hc_tx.transform(df, self.cont_cat_uni_dims_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=16)

        self.assertSetEqual(
            {'One (A, Uni2_1)', 'One (A, Uni2_2)', 'One (A, Uni2_3)', 'One (A, Uni2_4)',
             'One (B, Uni2_1)', 'One (B, Uni2_2)', 'One (B, Uni2_3)', 'One (B, Uni2_4)',
             'Two (A, Uni2_1)', 'Two (A, Uni2_2)', 'Two (A, Uni2_3)', 'Two (A, Uni2_4)',
             'Two (B, Uni2_1)', 'Two (B, Uni2_2)', 'Two (B, Uni2_3)', 'Two (B, Uni2_4)'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df.unstack([0, 1, 2, 4]), result)

    def test_rollup_triple_dimension_multi_metric(self):
        # Tests transformation of a multi-metric, double-dimension result
        df = self.rollup_cont_cat_cat_dims_multi_metric_df

        result = self.hc_tx.transform(df, self.rollup_cont_cat_cat_dims_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=14)

        self.assertSetEqual(
            {'One', 'One (A)', 'One (A, Y)', 'One (A, Z)', 'One (B)', 'One (B, Y)', 'One (B, Z)',
             'Two', 'Two (A)', 'Two (A, Y)', 'Two (A, Z)', 'Two (B)', 'Two (B, Y)', 'Two (B, Z)'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df.unstack(level=[1, 2]), result)

    def test_require_at_least_one_dimension(self):
        df = self.no_dims_multi_metric_df

        with self.assertRaises(TransformationException):
            self.hc_tx.transform(df, self.no_dims_multi_metric_schema)


class HighChartsColumnTransformerTests(BaseTransformerTests):
    """
    Bar and Column charts work with the following requests:

    1-dim, *-metric
    2-dim, 1-metric
    """
    type = HighchartsColumnTransformer.column

    def evaluate_chart_options(self, result, n_results=1, categories=None):
        self.assertSetEqual({'title', 'series', 'chart', 'tooltip', 'xAxis', 'yAxis'}, set(result.keys()))
        self.assertEqual(n_results, len(result['series']))

        self.assertSetEqual({'text'}, set(result['title'].keys()))
        self.assertIsNone(result['title']['text'])

        self.assertEqual(self.type, result['chart']['type'])
        self.assertEqual('categorical', result['xAxis']['type'])
        if categories:
            self.assertSetEqual({'type', 'categories'}, set(result['xAxis'].keys()))

        else:
            self.assertSetEqual({'type'}, set(result['xAxis'].keys()))

        for series in result['series']:
            self.assertSetEqual({'name', 'data', 'yAxis'}, set(series.keys()))

    @classmethod
    def setUpClass(cls):
        cls.hc_tx = HighchartsColumnTransformer(cls.type)

    def evaluate_result(self, df, result):
        result_data = [series['data'] for series in result['series']]

        for data, (_, item) in zip(result_data, df.iteritems()):
            self.assertListEqual(list(item), data)

    def test_no_dims_multi_metric(self):
        df = self.no_dims_multi_metric_df

        result = self.hc_tx.transform(df, self.no_dims_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=8)

        self.assertSetEqual(
            {'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df, result)

    def test_cat_dim_single_metric(self):
        # Tests transformation of a single-metric, single-dimension result
        df = self.cat_dim_single_metric_df

        result = self.hc_tx.transform(df, self.cat_dim_single_metric_schema)

        self.evaluate_chart_options(result, categories=['A', 'B'])

        self.assertSetEqual(
            {'One'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df, result)

    def test_cat_dim_multi_metric(self):
        # Tests transformation of a single-metric, single-dimension result
        df = self.cat_dim_multi_metric_df

        result = self.hc_tx.transform(df, self.cat_dim_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=2, categories=['A', 'B'])

        self.assertSetEqual(
            {'One', 'Two'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df, result)

    def test_cat_cat_dim_single_metric(self):
        # Tests transformation of a multi-metric, single-dimension result
        df = self.cat_cat_dims_single_metric_df

        result = self.hc_tx.transform(df, self.cat_cat_dims_single_metric_schema)

        self.evaluate_chart_options(result, n_results=2, categories=['A', 'B'])

        self.assertSetEqual(
            {'One (Y)', 'One (Z)'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df.unstack(), result)

    def test_uni_dim_single_metric(self):
        # Tests transformation of a metric with a unique dimension with one key and label
        df = self.uni_dim_single_metric_df

        result = self.hc_tx.transform(df, self.uni_dim_single_metric_schema)

        self.evaluate_chart_options(result, categories=['Uni1_1', 'Uni1_2', 'Uni1_3'])

        self.assertSetEqual(
            {'One'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df, result)

    def test_uni_dim_multi_metric(self):
        # Tests transformation of two metrics with a unique dimension with two keys and label
        df = self.uni_dim_multi_metric_df

        result = self.hc_tx.transform(df, self.uni_dim_multi_metric_schema)

        self.evaluate_chart_options(result, n_results=2, categories=['Uni2_1', 'Uni2_2', 'Uni2_3', 'Uni2_4'])

        self.assertSetEqual(
            {'One', 'Two'},
            {series['name'] for series in result['series']}
        )

        self.evaluate_result(df, result)

    def test_require_no_more_than_one_dimension_with_multi_metrics(self):
        df = self.cat_cat_dims_multi_metric_df

        with self.assertRaises(TransformationException):
            self.hc_tx.transform(df, self.cat_cat_dims_multi_metric_schema)


class HighChartsBarTransformerTests(HighChartsColumnTransformerTests):
    type = HighchartsColumnTransformer.bar