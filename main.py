import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor
import threading
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
                            QFileDialog, QMessageBox, QStyleFactory)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor

class GrabberThread(QThread):
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, url, output_dir):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.visited_urls = set()
        self.lock = threading.Lock()
        self.max_depth = 3
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
        self.is_running = True

    def run(self):
        try:
            self.grab_webserver(self.url, self.url)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

    def grab_webserver(self, url, base_url=None, depth=0):
        if not self.is_running or depth > self.max_depth:
            return
        if url in self.visited_urls:
            return
        with self.lock:
            self.visited_urls.add(url)

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            parsed_url = urlparse(url)
            path = parsed_url.path
            if not path:
                path = 'index.html'
            extension = os.path.splitext(path)[1]
            if not extension:
                extension = '.html'

            if base_url:
                base_parsed = urlparse(base_url)
                website_name = base_parsed.netloc
                if website_name.startswith('www.'):
                    website_name = website_name[4:]
            else:
                website_name = None

            self.save_file(url, response.content, extension, website_name)
            self.update_signal.emit(f"Grabbed: {url}")

            if extension == '.html':
                soup = BeautifulSoup(response.content, 'html.parser')

                with ThreadPoolExecutor(max_workers=10) as executor:
                    for link in soup.find_all(['a', 'link', 'script', 'img']):
                        if link.name == 'a':
                            href = link.get('href')
                            if href:
                                absolute_url = urljoin(url, href)
                                if absolute_url not in self.visited_urls:
                                    executor.submit(self.grab_webserver, absolute_url, base_url, depth+1)
                        elif link.name == 'link':
                            href = link.get('href')
                            if href and 'stylesheet' in link.get('rel', []):
                                absolute_url = urljoin(url, href)
                                if absolute_url not in self.visited_urls:
                                    executor.submit(self.grab_webserver, absolute_url, base_url, depth+1)
                        elif link.name == 'script':
                            src = link.get('src')
                            if src:
                                absolute_url = urljoin(url, src)
                                if absolute_url not in self.visited_urls:
                                    executor.submit(self.grab_webserver, absolute_url, base_url, depth+1)
                        elif link.name == 'img':
                            src = link.get('src')
                            if src:
                                absolute_url = urljoin(url, src)
                                if absolute_url not in self.visited_urls:
                                    executor.submit(self.grab_webserver, absolute_url, base_url, depth+1)

        except requests.exceptions.RequestException as e:
            self.update_signal.emit(f"Failed to grab {url}: {e}")

    def save_file(self, url, content, extension=None, website_name=None):
        parsed_url = urlparse(url)
        path = parsed_url.path
        if not path:
            path = 'index.html'
        filename = os.path.basename(path)
        if extension and not filename.endswith(extension):
            filename += extension
        if website_name:
            website_dir = os.path.join(self.output_dir, website_name)
            if not os.path.exists(website_dir):
                os.makedirs(website_dir)
            filepath = os.path.join(website_dir, filename)
        else:
            filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(content)

    def stop(self):
        self.is_running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WebServer Grabber")
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon("icon.png"))

        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555;
            }
            QTextEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }
            QProgressBar {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 5px;
            }
        """)

        self.thread = None
        self.output_dir = "output"

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignTop)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)


        title_label = QLabel("WebServer Grabber")
        title_label.setFont(QFont("Arial", 24, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)


        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setFont(QFont("Arial", 12))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter the URL of the webserver to grab")
        self.url_input.setFont(QFont("Arial", 12))
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addStretch()
        main_layout.addLayout(url_layout)


        output_layout = QHBoxLayout()
        output_label = QLabel("Output Directory:")
        output_label.setFont(QFont("Arial", 12))
        self.output_dir_label = QLabel(self.output_dir)
        self.output_dir_label.setFont(QFont("Arial", 12))
        self.output_dir_label.setStyleSheet("color: #4CAF50;")
        browse_button = QPushButton("Browse...")
        browse_button.setFont(QFont("Arial", 12))
        browse_button.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_dir_label)
        output_layout.addWidget(browse_button)
        output_layout.addStretch()
        main_layout.addLayout(output_layout)


        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Grab")
        self.start_button.setFont(QFont("Arial", 12))
        self.start_button.clicked.connect(self.start_grab)
        self.stop_button = QPushButton("Stop Grab")
        self.stop_button.setFont(QFont("Arial", 12))
        self.stop_button.clicked.connect(self.stop_grab)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)


        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.progress_bar)


        log_label = QLabel("Log Output:")
        log_label.setFont(QFont("Arial", 12, QFont.Bold))
        main_layout.addWidget(log_label)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Arial", 10))
        main_layout.addWidget(self.log_output)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_dir)
        if directory:
            self.output_dir = directory
            self.output_dir_label.setText(self.output_dir)

    def start_grab(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a valid URL")
            return

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setRange(0, 0)
        self.log_output.clear()

        self.thread = GrabberThread(url, self.output_dir)
        self.thread.update_signal.connect(self.update_log)
        self.thread.finished_signal.connect(self.grab_finished)
        self.thread.error_signal.connect(self.grab_error)
        self.thread.start()

    def stop_grab(self):
        if self.thread:
            self.thread.stop()
            self.thread.wait()
            self.thread = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setRange(0, 1)
        self.update_log("Grab process stopped by user")

    def update_log(self, message):
        self.log_output.append(message)
        self.log_output.ensureCursorVisible()

    def grab_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setRange(0, 1)
        self.update_log("Webserver grabbing completed. Files saved in the directory.")

    def grab_error(self, error):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setRange(0, 1)
        self.update_log(f"Error: {error}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
