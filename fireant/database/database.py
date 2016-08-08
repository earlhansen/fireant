# coding: utf-8
import logging
from abc import ABC

import pandas as pd

logger = logging.getLogger(__name__)


class Database(ABC):
    def connect(self):
        raise NotImplementedError

    def round_date(self, field, interval):
        raise NotImplementedError

    def fetch(self, query):
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def fetch_dataframe(self, query, columns=None, index=None):
        with self.connect() as connection:
            return pd.read_sql(query, connection, columns=columns, index_col=index)
