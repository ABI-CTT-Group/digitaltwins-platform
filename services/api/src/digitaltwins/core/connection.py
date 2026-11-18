import psycopg2

from ..settings import load_settings


class Connection(object):
    """
    Class for connecting to the digitaltwins platform.
    """

    def __init__(self, host=None, port=None, database=None, user=None, password=None):

        self._cur = None
        self._conn = None

        pg = load_settings().postgres
        self._host = host or pg.host
        self._port = port or pg.port
        self._database = database or pg.db
        self._user = user or pg.user
        self._password = password or pg.password


    def get_cur(self):
        return self._cur

    def get_conn(self):
        return self._conn

    def connect(self):
        self._conn = psycopg2.connect(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._user,
            password=self._password)
        # create a cursor
        self._cur = self._conn.cursor()

        return self._conn, self._cur

    def disconnect(self):
        self._cur.close()
        self._conn.close()
