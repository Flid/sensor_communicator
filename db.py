from prod_config import DATABASE_DSN
from psycopg2.pool import ThreadedConnectionPool

conn_pool = ThreadedConnectionPool(
    0,
    100,
    dsn=DATABASE_DSN,
)