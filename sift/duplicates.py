import sqlite3

from PySide6.QtCore import QThread, Signal

from . import database


class DuplicateWorker(QThread):
    """Load exact duplicate groups without blocking the interface thread."""

    groups_ready = Signal(list, int)
    query_failed = Signal(str)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        conn = None
        try:
            conn = database.connect_readonly(self.db_path)
            groups, empty_file_count = database.get_exact_duplicate_groups(conn)
        except sqlite3.Error as error:
            self.query_failed.emit(str(error))
        else:
            self.groups_ready.emit(groups, empty_file_count)
        finally:
            if conn is not None:
                conn.close()
