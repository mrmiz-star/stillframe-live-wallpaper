from __future__ import annotations

import ctypes
import random
import sys
from pathlib import Path
from ctypes import wintypes

from PySide6.QtCore import QSettings, Qt, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

APP_NAME = "Stillframe"
VIDEO_FILTER = "Video files (*.mp4 *.mkv *.mov *.webm *.avi *.wmv *.m4v);;All files (*.*)"


def windows_workerw() -> int | None:
    """Return the Explorer WorkerW window behind desktop icons, when available."""
    if sys.platform != "win32":
        return None
    user32 = ctypes.windll.user32
    progman = user32.FindWindowW("Progman", None)
    if progman:
        result = ctypes.c_ulong()
        for value in (0, 1):
            user32.SendMessageTimeoutW(progman, 0x052C, 0xD, value, 0, 1000, ctypes.byref(result))
    worker = None
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit(hwnd: int, _param: int) -> bool:
        nonlocal worker
        if user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None):
            worker = user32.FindWindowExW(0, hwnd, "WorkerW", None)
            return False
        return True

    callback = callback_type(visit)
    user32.EnumWindows(callback, 0)
    return int(worker) if worker else None


class WallpaperWindow(QWidget):
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setStyleSheet("background:#090d15")
        self.video = QVideoWidget(self)
        self.video.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video)
        self.player = QMediaPlayer(self)
        self.player.setLoops(QMediaPlayer.Loops.Infinite)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.errorOccurred.connect(lambda *_: self.failed.emit(self.player.errorString()))

    def attach_to_desktop(self) -> bool:
        try:
            host = windows_workerw()
            if not host:
                return False
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            user32.SetParent(hwnd, host)
            rect = QApplication.primaryScreen().geometry()
            return bool(user32.SetWindowPos(hwnd, 0, rect.x(), rect.y(), rect.width(), rect.height(), 0x0040))
        except Exception:
            return False

    def set_video(self, path: str, volume: float) -> None:
        self.audio.setVolume(volume)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.video.setGeometry(self.rect())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("Stillframe", "Stillframe")
        self.wallpaper = WallpaperWindow()
        self.wallpaper.failed.connect(self.show_media_error)
        self.desktop_attached = False
        self.shuffle_order: list[int] = []
        self.shuffle_position = 0
        self._building = True
        self.setWindowTitle("Stillframe — Live Wallpaper")
        self.setMinimumSize(600, 600)
        self.resize(660, 710)
        self.setStyleSheet("""
            QMainWindow,QWidget#root{background:#10141d;color:#e8edf6} QLabel{color:#e8edf6}
            QLabel#muted{color:#8994a6} QFrame#card{background:#181e2a;border:1px solid #2a3342;border-radius:16px}
            QPushButton{background:#273244;color:#eaf0fa;border:1px solid #344257;border-radius:10px;padding:9px 12px;font-weight:600}
            QPushButton:hover{background:#33415a} QPushButton#primary{background:#9fe870;color:#15200e;border:0}
            QPushButton#primary:hover{background:#b4f58b} QListWidget{background:#0e131b;border:1px solid #2a3342;border-radius:10px;padding:5px}
            QListWidget::item{padding:8px;border-radius:6px} QListWidget::item:selected{background:#33415a;color:#fff}
            QSlider::groove:horizontal{height:5px;background:#30394a;border-radius:3px}
            QSlider::sub-page:horizontal{background:#9fe870;border-radius:3px}
            QSlider::handle:horizontal{background:#d8f5c7;width:13px;margin:-5px 0;border-radius:7px}
            QCheckBox{color:#cbd4e1;spacing:8px}
        """)

        root = QWidget(objectName="root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(26, 22, 26, 24)
        outer.setSpacing(13)
        header = QHBoxLayout()
        brand = QLabel("stillframe")
        brand.setFont(QFont("Segoe UI", 21, QFont.Weight.Bold))
        brand.setStyleSheet("color:#9fe870;letter-spacing:1px")
        header.addWidget(brand)
        header.addStretch()
        badge = QLabel("LIVE WALLPAPER STUDIO")
        badge.setStyleSheet("color:#9aa7b8;font-size:10px;letter-spacing:1.2px")
        header.addWidget(badge)
        outer.addLayout(header)
        title = QLabel("Your desktop, in motion.")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.DemiBold))
        outer.addWidget(title)
        subtitle = QLabel("Build a video playlist, then send it behind your desktop icons.")
        subtitle.setObjectName("muted")
        outer.addWidget(subtitle)

        card = QFrame(objectName="card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        row = QHBoxLayout()
        self.current_label = QLabel("No wallpaper selected")
        self.current_label.setObjectName("muted")
        self.current_label.setWordWrap(True)
        row.addWidget(self.current_label, 1)
        self.apply_button = QPushButton("Set as wallpaper")
        self.apply_button.setObjectName("primary")
        self.apply_button.clicked.connect(self.apply_wallpaper)
        self.apply_button.setEnabled(False)
        row.addWidget(self.apply_button)
        layout.addLayout(row)
        self.playlist = QListWidget()
        self.playlist.setMinimumHeight(185)
        self.playlist.currentRowChanged.connect(self.select_track)
        layout.addWidget(self.playlist)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("＋ Add videos")
        self.add_button.clicked.connect(self.add_videos)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_track)
        self.up_button = QPushButton("↑")
        self.up_button.setToolTip("Move track up")
        self.up_button.clicked.connect(lambda: self.move_track(-1))
        self.down_button = QPushButton("↓")
        self.down_button.setToolTip("Move track down")
        self.down_button.clicked.connect(lambda: self.move_track(1))
        for button in (self.add_button, self.remove_button, self.up_button, self.down_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        outer.addWidget(card)

        controls = QHBoxLayout()
        self.previous_button = QPushButton("◀ Previous")
        self.previous_button.clicked.connect(lambda: self.change_track(-1))
        self.play_button = QPushButton("▶ Play")
        self.play_button.clicked.connect(self.toggle_playback)
        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(lambda: self.change_track(1))
        self.shuffle_box = QCheckBox("Shuffle")
        self.shuffle_box.toggled.connect(self.rebuild_shuffle)
        for button in (self.previous_button, self.play_button, self.next_button):
            controls.addWidget(button)
        controls.addStretch()
        controls.addWidget(self.shuffle_box)
        outer.addLayout(controls)

        audio_row = QHBoxLayout()
        audio_row.addWidget(QLabel("Wallpaper audio"))
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(float(self.settings.value("volume", 0.0)) * 100))
        self.volume.valueChanged.connect(self.set_volume)
        audio_row.addWidget(self.volume, 1)
        self.volume_text = QLabel(f"{self.volume.value()}%")
        self.volume_text.setObjectName("muted")
        audio_row.addWidget(self.volume_text)
        outer.addLayout(audio_row)
        self.startup_box = QCheckBox("Launch Stillframe when I sign in")
        self.startup_box.setChecked(self.startup_enabled())
        self.startup_box.toggled.connect(self.set_startup)
        outer.addWidget(self.startup_box)
        self.status = QLabel("Ready — add videos to create your wallpaper playlist.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        note = QLabel("Tip: MP4/H.264 is the most compatible format. Desktop embedding uses an Explorer integration and may be affected by shell customizations.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        note.setStyleSheet("font-size:11px")
        outer.addWidget(note)
        self.setCentralWidget(root)
        self.wallpaper.player.playbackStateChanged.connect(self.sync_play_button)
        self._load_playlist()
        self._building = False
        if self.playlist.count():
            saved = int(self.settings.value("currentIndex", 0))
            self.playlist.setCurrentRow(min(max(saved, 0), self.playlist.count() - 1))

    def _load_playlist(self) -> None:
        for path in self.settings.value("playlist", [], list):
            if Path(path).is_file():
                self.playlist.addItem(QListWidgetItem(path))

    def _save_playlist(self) -> None:
        paths = [self.playlist.item(i).text() for i in range(self.playlist.count())]
        self.settings.setValue("playlist", paths)
        if not self._building:
            self.settings.setValue("currentIndex", self.playlist.currentRow())

    def add_videos(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add videos to playlist", str(Path.home() / "Videos"), VIDEO_FILTER)
        existing = {self.playlist.item(i).text().lower() for i in range(self.playlist.count())}
        first = self.playlist.count()
        for path in paths:
            if path.lower() not in existing:
                self.playlist.addItem(QListWidgetItem(path))
                existing.add(path.lower())
        if self.playlist.count() and self.playlist.currentRow() < 0:
            self.playlist.setCurrentRow(first if first < self.playlist.count() else 0)
        self._save_playlist()
        self.rebuild_shuffle()

    def remove_track(self) -> None:
        row = self.playlist.currentRow()
        if row < 0:
            return
        self.playlist.takeItem(row)
        if self.playlist.count():
            self.playlist.setCurrentRow(min(row, self.playlist.count() - 1))
        else:
            self.wallpaper.player.stop()
            self.current_label.setText("No wallpaper selected")
            self.apply_button.setEnabled(False)
        self._save_playlist()
        self.rebuild_shuffle()

    def move_track(self, delta: int) -> None:
        row = self.playlist.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.playlist.count():
            return
        item = self.playlist.takeItem(row)
        self.playlist.insertItem(target, item)
        self.playlist.setCurrentRow(target)
        self._save_playlist()
        self.rebuild_shuffle()

    def select_track(self, row: int) -> None:
        if self._building or row < 0 or row >= self.playlist.count():
            return
        path = self.playlist.item(row).text()
        if not Path(path).is_file():
            self.status.setText("This playlist file is missing. Remove it or choose another video.")
            return
        self.current_label.setText(Path(path).name)
        self.apply_button.setEnabled(True)
        self.wallpaper.set_video(path, self.volume.value() / 100)
        self.status.setText("Now playing — each video loops continuously. Use Next or Shuffle to change scenes.")
        self._save_playlist()

    def change_track(self, direction: int) -> None:
        count = self.playlist.count()
        if not count:
            return
        row = self.playlist.currentRow()
        if self.shuffle_box.isChecked() and count > 1:
            if direction > 0 and self.shuffle_position + 1 < len(self.shuffle_order):
                self.shuffle_position += 1
                target = self.shuffle_order[self.shuffle_position]
            else:
                current = row
                options = [i for i in range(count) if i != current]
                target = random.choice(options)
                if direction > 0:
                    self.shuffle_order = [row, target] + [i for i in options if i != target]
                    self.shuffle_position = 1
        else:
            target = (row + direction) % count
        self.playlist.setCurrentRow(target)

    def rebuild_shuffle(self, *_args) -> None:
        count = self.playlist.count()
        self.shuffle_order = list(range(count))
        random.shuffle(self.shuffle_order)
        current = self.playlist.currentRow()
        if current in self.shuffle_order:
            self.shuffle_order.remove(current)
            self.shuffle_order.insert(0, current)
        self.shuffle_position = 0

    def apply_wallpaper(self) -> None:
        if not self.playlist.count():
            return
        if not self.wallpaper.isVisible():
            screen = QApplication.primaryScreen()
            if screen:
                self.wallpaper.setGeometry(screen.geometry())
            self.wallpaper.show()
        self.desktop_attached = self.wallpaper.attach_to_desktop()
        self.status.setText(
            "Live wallpaper active behind your desktop icons. This starter currently targets the primary display."
            if self.desktop_attached else
            "Explorer desktop attachment failed; video playback continues. Try reopening the app or restarting Windows Explorer."
        )

    def toggle_playback(self) -> None:
        if self.wallpaper.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.wallpaper.player.pause()
        else:
            self.wallpaper.player.play()

    def sync_play_button(self, state) -> None:
        self.play_button.setText("Ⅱ Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "▶ Play")

    def set_volume(self, value: int) -> None:
        self.wallpaper.audio.setVolume(value / 100)
        self.volume_text.setText(f"{value}%")
        self.settings.setValue("volume", value / 100)

    def startup_enabled(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                value, _ = winreg.QueryValueEx(key, "Stillframe")
                return bool(value)
        except OSError:
            return False

    def set_startup(self, enabled: bool) -> None:
        if sys.platform != "win32":
            return
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    exe = sys.executable
                    if getattr(sys, "frozen", False):
                        exe = sys.executable
                    winreg.SetValueEx(key, "Stillframe", 0, winreg.REG_SZ, f'"{exe}"')
                else:
                    try:
                        winreg.DeleteValue(key, "Stillframe")
                    except FileNotFoundError:
                        pass
            self.status.setText("Startup preference saved.")
        except OSError as exc:
            QMessageBox.warning(self, "Startup setting", f"Could not update Windows startup settings: {exc}")
            self.startup_box.blockSignals(True)
            self.startup_box.setChecked(not enabled)
            self.startup_box.blockSignals(False)

    def show_media_error(self, message: str) -> None:
        self.status.setText(f"Playback error: {message or 'unsupported video or codec'}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._save_playlist()
        self.wallpaper.player.stop()
        self.wallpaper.close()
        super().closeEvent(event)


def main() -> int:
    if sys.platform != "win32":
        print("Stillframe is a Windows desktop app. Build and run it on Windows.", file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
