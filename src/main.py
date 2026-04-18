import sys
import os
from pathlib import Path

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QFileDialog,
                               QProgressBar, QMessageBox, QGroupBox, QCheckBox,
                               QListWidget, QListWidgetItem, QScrollArea, QSplitter,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFrame)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QAction, QDragEnterEvent, QDropEvent, QPixmap

sys.path.insert(0, str(Path(__file__).parent.parent))

from audio.scanner import AudioScanner, AudioMetadata
from core.finder import DuplicateFinder, DuplicateGroup


class ScanThread(QThread):
    progress = Signal(int, int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, folder_path: str):
        super().__init__()
        self.folder_path = folder_path

    def run(self):
        try:
            scanner = AudioScanner()
            self.progress.emit(0, 0, "正在扫描音频文件...")

            audio_files = scanner.scan_folder(self.folder_path)
            self.progress.emit(1, 100, "正在计算文件哈希...")

            for i, audio in enumerate(audio_files):
                audio.file_hash = scanner.calculate_hash(audio.file_path)
                progress_percent = int((i + 1) / len(audio_files) * 100)
                self.progress.emit(i + 1, progress_percent, f"已处理 {i+1}/{len(audio_files)} 个文件")

            self.finished.emit(audio_files)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.audio_files = []
        self.duplicate_groups = []
        self.scan_thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("音乐重复文件检测工具")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(900, 600)

        self.setup_menu()
        self.setup_central_widget()

        self.statusBar().showMessage("就绪")

    def setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")

        open_action = QAction("打开文件夹", self)
        open_action.triggered.connect(self.select_folder)
        file_menu.addAction(open_action)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def setup_central_widget(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        toolbar = self.create_toolbar()
        main_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([350, 750])

        main_layout.addWidget(splitter)

        bottom_bar = self.create_bottom_bar()
        main_layout.addLayout(bottom_bar)

    def create_toolbar(self):
        toolbar = QHBoxLayout()

        self.btn_scan = QPushButton("选择文件夹")
        self.btn_scan.clicked.connect(self.select_folder)
        toolbar.addWidget(self.btn_scan)

        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_scan)
        toolbar.addWidget(self.btn_stop)

        toolbar.addStretch()

        self.lbl_status = QLabel("就绪")
        toolbar.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.setVisible(False)
        toolbar.addWidget(self.progress_bar)

        return toolbar

    def create_left_panel(self):
        group = QGroupBox()
        layout = QVBoxLayout()

        all_files_label = QLabel("所有文件")
        layout.addWidget(all_files_label)

        self.all_files_list = QListWidget()
        self.all_files_list.setMaximumHeight(150)
        self.all_files_list.itemClicked.connect(self.on_all_file_clicked)
        layout.addWidget(self.all_files_list)

        layout.addWidget(QFrame())

        dup_label = QLabel("重复组")
        layout.addWidget(dup_label)

        self.duplicate_list = QListWidget()
        self.duplicate_list.itemClicked.connect(self.on_group_clicked)
        layout.addWidget(self.duplicate_list)

        group.setLayout(layout)
        return group

    def create_right_panel(self):
        group = QGroupBox()
        layout = QVBoxLayout()

        files_label = QLabel("文件详情")
        layout.addWidget(files_label)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(6)
        self.file_table.setHorizontalHeaderLabels(["保留", "文件名", "大小", "时长", "艺术家", "比特率"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.itemClicked.connect(self.on_file_selected)
        self.file_table.setMaximumHeight(180)

        layout.addWidget(self.file_table)

        detail_label = QLabel("歌曲详情")
        layout.addWidget(detail_label)

        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setMinimumHeight(200)

        detail_widget = QWidget()
        self.detail_layout = QVBoxLayout(detail_widget)

        self.cover_label = QLabel("封面")
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setMinimumSize(200, 200)
        self.cover_label.setMaximumSize(200, 200)
        self.detail_layout.addWidget(self.cover_label)

        self.info_label = QLabel()
        self.detail_layout.addWidget(self.info_label)

        self.lyrics_label = QLabel("歌词")
        self.detail_layout.addWidget(self.lyrics_label)

        self.lyrics_text = QLabel()
        self.lyrics_text.setWordWrap(True)
        self.detail_layout.addWidget(self.lyrics_text)

        detail_scroll.setWidget(detail_widget)
        layout.addWidget(detail_scroll)

        group.setLayout(layout)
        return group

    def create_bottom_bar(self):
        bar = QHBoxLayout()

        self.btn_select_all = QPushButton("全选保留 (每组第一个)")
        self.btn_select_all.clicked.connect(self.select_all_keepers)
        bar.addWidget(self.btn_select_all)

        bar.addStretch()

        self.lbl_result = QLabel("找到 0 组重复文件")
        bar.addWidget(self.lbl_result)

        self.btn_delete = QPushButton("删除选中")
        self.btn_delete.setStyleSheet("background-color: #FF5722; color: white;")
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_delete.setEnabled(False)
        bar.addWidget(self.btn_delete)

        return bar

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音乐文件夹")
        if folder:
            self.start_scan(folder)

    def start_scan(self, folder_path: str):
        self.btn_scan.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("正在扫描...")

        self.duplicate_list.clear()
        self.file_table.setRowCount(0)
        self.audio_files = []
        self.duplicate_groups = []

        self.scan_thread = ScanThread(folder_path)
        self.scan_thread.progress.connect(self.on_scan_progress)
        self.scan_thread.finished.connect(self.on_scan_finished)
        self.scan_thread.error.connect(self.on_scan_error)
        self.scan_thread.start()

    def stop_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.terminate()
            self.scan_thread.wait()

        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("扫描已停止")

    def on_scan_progress(self, current: int, percent: int, text: str):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(text)

    def on_scan_finished(self, audio_files: list):
        self.audio_files = audio_files
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)

        if not audio_files:
            self.lbl_status.setText("未找到音频文件")
            QMessageBox.information(self, "提示", "未在选定文件夹中找到音频文件")
            return

        self.lbl_status.setText(f"已扫描 {len(audio_files)} 个文件，正在查找重复...")

        self.display_all_files()

        finder = DuplicateFinder()
        self.duplicate_groups = finder.find_duplicates(audio_files)

        self.display_duplicate_groups()
        self.lbl_status.setText(f"找到 {len(self.duplicate_groups)} 组重复文件")

    def on_scan_error(self, error: str):
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.lbl_status.setText("扫描出错")
        QMessageBox.warning(self, "错误", f"扫描出错: {error}")

    def display_all_files(self):
        self.all_files_list.clear()
        for audio in self.audio_files:
            item = QListWidgetItem(audio.file_name)
            item.setData(Qt.UserRole, audio)
            self.all_files_list.addItem(item)

    def on_all_file_clicked(self, list_item: QListWidgetItem):
        audio: AudioMetadata = list_item.data(Qt.UserRole)
        if audio:
            self.display_song_details(audio)

    def display_duplicate_groups(self):
        self.duplicate_list.clear()

        for group in self.duplicate_groups:
            type_text = "哈希" if group.duplicate_type == "hash" else "元数据"
            text = f"重复组 {group.group_id} - {len(group.files)} 个文件 ({type_text})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, group)
            self.duplicate_list.addItem(item)

        self.lbl_result.setText(f"找到 {len(self.duplicate_groups)} 组重复文件")

        if self.duplicate_groups:
            self.duplicate_list.setCurrentRow(0)
            self.btn_delete.setEnabled(True)
        else:
            self.btn_delete.setEnabled(False)

    def on_group_clicked(self, item: QListWidgetItem):
        group: DuplicateGroup = item.data(Qt.UserRole)
        if group:
            self.display_group_files(group)

    def display_group_files(self, group: DuplicateGroup):
        self.file_table.setRowCount(0)

        for i, audio in enumerate(group.files):
            self.file_table.insertRow(i)

            checkbox = QCheckBox()
            checkbox.setChecked(i == 0)
            self.file_table.setCellWidget(i, 0, checkbox)

            self.file_table.setItem(i, 1, QTableWidgetItem(audio.file_name))
            self.file_table.setItem(i, 2, QTableWidgetItem(self.format_size(audio.file_size)))
            self.file_table.setItem(i, 3, QTableWidgetItem(self.format_duration(audio.duration)))
            self.file_table.setItem(i, 4, QTableWidgetItem(audio.artist or "未知"))
            self.file_table.setItem(i, 5, QTableWidgetItem(self.format_bitrate(audio.bitrate)))

            self.file_table.item(i, 1).setData(Qt.UserRole, audio)

    def display_song_details(self, audio: AudioMetadata):
        if audio.album_cover:
            pixmap = QPixmap()
            pixmap.loadFromData(audio.album_cover)
            scaled = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cover_label.setPixmap(scaled)
        else:
            self.cover_label.setText("无封面")

        info_text = f"标题: {audio.title or '未知'}\n艺术家: {audio.artist or '未知'}\n专辑: {audio.album or '未知'}\n时长: {self.format_duration(audio.duration)}\n比特率: {self.format_bitrate(audio.bitrate)}"
        self.info_label.setText(info_text)

        if audio.lyrics:
            self.lyrics_text.setText(audio.lyrics)
            self.lyrics_label.setVisible(True)
            self.lyrics_text.setVisible(True)
        else:
            self.lyrics_label.setVisible(False)
            self.lyrics_text.setVisible(False)

    def on_file_selected(self, item: QTableWidgetItem):
        audio: AudioMetadata = item.data(Qt.UserRole)
        if audio:
            self.display_song_details(audio)

    def select_all_keepers(self):
        for row in range(self.file_table.rowCount()):
            checkbox = self.file_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(row == 0)

    def delete_selected(self):
        rows_to_delete = []
        for row in range(self.file_table.rowCount()):
            checkbox = self.file_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                item = self.file_table.item(row, 1)
                if item:
                    audio: AudioMetadata = item.data(Qt.UserRole)
                    if audio:
                        rows_to_delete.append((row, audio))

        if not rows_to_delete:
            QMessageBox.information(self, "提示", "请选择要删除的文件")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(rows_to_delete)} 个文件吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            deleted_count = 0
            for row, audio in rows_to_delete:
                try:
                    if os.path.exists(audio.file_path):
                        os.remove(audio.file_path)
                        deleted_count += 1
                except Exception as e:
                    print(f"删除失败: {audio.file_path}, {e}")

            QMessageBox.information(self, "完成", f"已删除 {deleted_count} 个文件")

            for row, audio in rows_to_delete:
                for group in self.duplicate_groups:
                    group.files = [f for f in group.files if f.file_path != audio.file_path]

            self.duplicate_groups = [g for g in self.duplicate_groups if len(g.files) > 1]

            self.display_duplicate_groups()

            if self.duplicate_groups:
                self.btn_delete.setEnabled(True)

    def format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    def format_duration(self, duration: float) -> str:
        if not duration:
            return "未知"
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        return f"{minutes}:{seconds:02d}"

    def format_bitrate(self, bitrate: int) -> str:
        if not bitrate:
            return "未知"
        return f"{bitrate // 1000} kbps"


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()