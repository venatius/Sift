import os
from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from . import database
from .worker import ScanWorker

DB_PATH = str(Path(__file__).resolve().parent.parent / "sift.db")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sift")
        self.resize(700, 500)

        self.folder = None
        self.thread = None
        self.worker = None
        self.paused = False

        self.folder_label = QLabel("No folder selected")
        self.choose_btn = QPushButton("Choose Folder")
        self.start_btn = QPushButton("Start Scan")
        self.pause_btn = QPushButton("Pause")
        self.cancel_btn = QPushButton("Cancel")
        self.status_label = QLabel("Ready")
        self.count_label = QLabel("Files found: 0")
        self.saved_label = QLabel("")
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)

        buttons = QHBoxLayout()
        for b in (self.choose_btn, self.start_btn, self.pause_btn, self.cancel_btn):
            buttons.addWidget(b)

        layout = QVBoxLayout()
        for w in (self.folder_label, buttons, self.status_label,
                  self.count_label, self.saved_label, self.report):
            if isinstance(w, QHBoxLayout):
                layout.addLayout(w)
            else:
                layout.addWidget(w)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.choose_btn.clicked.connect(self.choose_folder)
        self.start_btn.clicked.connect(self.start_scan)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.cancel_btn.clicked.connect(self.cancel_scan)

        self.set_scanning(False)
        self.init_database()

    # ----- setup -----
    def init_database(self):
        conn = database.connect(DB_PATH)
        database.init_db(conn)
        interrupted = database.mark_interrupted(conn)
        conn.close()
        if interrupted:
            self.status_label.setText(
                "The previous scan was interrupted. Saved results are kept; "
                "choose a folder and scan again to refresh them."
            )
        self.refresh_saved_count()

    def refresh_saved_count(self):
        conn = database.connect(DB_PATH)
        n = database.count_files(conn)
        conn.close()
        self.saved_label.setText(f"Saved file records in database: {n}")

    def set_scanning(self, scanning):
        self.paused = False
        self.pause_btn.setText("Pause")
        self.choose_btn.setEnabled(not scanning)
        self.start_btn.setEnabled(not scanning and self.folder is not None)
        self.pause_btn.setEnabled(scanning)
        self.cancel_btn.setEnabled(scanning)

    # ----- user actions -----
    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder to scan")
        if folder:
            self.folder = os.path.normpath(folder)
            self.folder_label.setText(self.folder)
            self.start_btn.setEnabled(True)

    def start_scan(self):
        self.report.clear()
        self.count_label.setText("Files found: 0")
        self.status_label.setText("Scanning...")

        self.thread = QThread()
        self.worker = ScanWorker(self.folder, DB_PATH)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.scan_done.connect(self.on_scan_done)

        self.set_scanning(True)
        self.thread.start()

    def toggle_pause(self):
        if self.paused:
            self.worker.resume()
            self.paused = False
            self.pause_btn.setText("Pause")
            self.status_label.setText("Scanning...")
        else:
            self.worker.pause()
            self.paused = True
            self.pause_btn.setText("Resume")
            self.status_label.setText("Paused (stops between files)")

    def cancel_scan(self):
        self.status_label.setText("Cancelling...")
        self.worker.cancel()

    # ----- updates from the worker -----
    def on_progress(self, total, path):
        self.count_label.setText(f"Files found: {total}")
        if path and not self.paused:
            self.status_label.setText(f"Scanning... {path[-70:]}")

    def on_scan_done(self, s):
        self.thread.quit()
        self.thread.wait()
        self.thread = None
        self.worker = None
        self.set_scanning(False)

        self.status_label.setText("Scan cancelled" if s["cancelled"] else "Scan finished")
        lines = [
            f"Scanned: {s['scanned']}",
            f"Skipped: {s['skipped']}",
            f"Failed: {s['failed']}",
        ]
        if s["cancelled"]:
            lines.append("The scan was cancelled before it finished.")
        if s["errors"]:
            lines += ["", "Problems:"]
            for path, message in s["errors"]:
                lines.append(f"  {path}\n      {message}")
        self.report.setPlainText("\n".join(lines))
        self.refresh_saved_count()

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.cancel()
            self.thread.quit()
            self.thread.wait()
        event.accept()