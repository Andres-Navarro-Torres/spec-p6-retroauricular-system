import sys, time, os, csv
from datetime import datetime
from typing import Dict, Optional, List, Tuple, Set
from collections import deque

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QMessageBox, QFormLayout,
    QComboBox, QSizePolicy, QGridLayout, QDialog, QLineEdit,
    QDialogButtonBox, QProgressBar, QFileDialog, QSpacerItem,
    QTextEdit, QScrollArea, QFrame, QTabWidget, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, Qt, pyqtSlot, QPropertyAnimation, QEasingCurve, QRectF
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QPalette
from PyQt6.QtSerialPort import QSerialPort, QSerialPortInfo
import pyqtgraph as pg
import numpy as np

try:
    from scipy.signal import butter, lfilter, filtfilt, lfilter_zi, welch
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# =============================================================================
#  PARÁMETROS DEL SISTEMA SPEC-P6
# =============================================================================
BAUD_RATE = 921600
DATA_WINDOW_SECONDS = 5
DATA_WINDOW_US = DATA_WINDOW_SECONDS * 1_000_000
GUI_FPS = 30 
GUI_INTERVAL_MS = int(1000/GUI_FPS)
RING_CAPACITY = 2000 
IMU_SPARKLINE_LEN = 200
FILTER_PADDING_S = 1.0 
FILTER_PADDING_US = int(FILTER_PADDING_S * 1_000_000)

JOIN_GRACE_SECONDS = 8.0
TARGET_FS_HZ = 50 
MAX_WAIT_EXTRA_S = 30.0
START_DROP_SAMPLES = 10
CALIBRATION_TIMEOUT_MS = 30_000

SLAVE_LOCATIONS = {
    "1": "Retroauricular", "Slave1": "Retroauricular",
    "2": "Muñeca", "Slave2": "Muñeca",
    "3": "Dedo Índice", "Slave3": "Dedo índice"
}

LOCATION_ACCENT = {
    "Retroauricular": "#8B5CF6", 
    "Muñeca": "#3B82F6",         
    "Dedo Índice": "#10B981",    
    "Dedo índice": "#10B981",
}
DEFAULT_ACCENT = "#6B7280"

_LIPO_CURVE = [
    (4.20, 100), (4.15, 95), (4.11, 90), (4.08, 85), (4.02, 80),
    (3.98, 75),  (3.95, 70), (3.91, 65), (3.87, 60), (3.85, 55),
    (3.84, 50),  (3.82, 45), (3.80, 40), (3.79, 35), (3.77, 30),
    (3.75, 25),  (3.73, 20), (3.71, 15), (3.69, 10), (3.61, 5),
    (3.27, 0),
]

def lipo_voltage_to_percent(v: float) -> int:
    if v >= _LIPO_CURVE[0][0]: return 100
    if v <= _LIPO_CURVE[-1][0]: return 0
    for (v_hi, p_hi), (v_lo, p_lo) in zip(_LIPO_CURVE, _LIPO_CURVE[1:]):
        if v_lo <= v <= v_hi:
            frac = (v - v_lo) / (v_hi - v_lo)
            return int(round(p_lo + frac * (p_hi - p_lo)))
    return 0

pg.setConfigOption('useOpenGL', False) 
pg.setConfigOption('background', '#FFFFFF')
pg.setConfigOption('foreground', '#000000') 
pg.setConfigOptions(antialias=True) 

class OneDecimalAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing): return [f"{v:.1f}" for v in values]

# =================================================================
# --- WIDGET DE BATERÍA ---
# =================================================================
class BatteryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(54, 24)
        self.pct = 0; self.is_valid = False
        self.setToolTip("Sin datos de batería")

    def set_value(self, voltage_mv):
        if voltage_mv <= 0:
            self.is_valid = False; self.setToolTip("Sin datos"); self.update(); return
        self.is_valid = True
        v = voltage_mv / 1000.0
        self.pct = lipo_voltage_to_percent(v)
        self.setToolTip(f"Voltaje: {v:.2f} V ({self.pct}%)"); self.update()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width() - 5, self.height() - 2
        body_rect = QRectF(1, 1, w - 3, h)
        
        painter.setPen(QPen(QColor("#9CA3AF"), 1.5))
        painter.drawRoundedRect(body_rect, 4, 4)
        term_rect = QRectF(w - 2, h / 2 - 4, 3, 8)
        painter.setBrush(QBrush(QColor("#9CA3AF"))); painter.drawRoundedRect(term_rect, 1, 1)

        if self.is_valid:
            color = QColor("#10B981") if self.pct >= 50 else QColor("#F59E0B") if self.pct >= 20 else QColor("#EF4444")
            fill_width = max(0, ((w - 5) * self.pct) / 100.0)
            if fill_width > 0:
                painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(color))
                painter.drawRoundedRect(QRectF(2.5, 2.5, fill_width, h - 3), 2, 2)
                
            painter.setPen(QPen(QColor("#000000")))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(body_rect, Qt.AlignmentFlag.AlignCenter, f"{self.pct}%")
        else:
            painter.setPen(QPen(QColor("#9CA3AF"), 1))
            painter.drawLine(int(body_rect.left() + 4), int(body_rect.top() + 4), int(body_rect.right() - 4), int(body_rect.bottom() - 4))

# =================================================================
# --- DSP: Filtrado & Estimación HR ---
# =================================================================
def create_filter(fs, lowcut=0.5, highcut=5.0, order=2):
    if not SCIPY_AVAILABLE: return None, None
    nyq = 0.5 * fs; low = lowcut / nyq; high = highcut / nyq
    if low >= 1.0 or high >= 1.0 or low <= 0 or high <= 0: return None, None
    return butter(order, [low, high], btype='band')

BPM_MIN, BPM_MAX = 40, 180
HR_RECOMPUTE_INTERVAL_S = 1.0
WELCH_RECOMPUTE_INTERVAL_S = 0.1 

def estimate_bpm(y_raw: np.ndarray, fs: float, b, a):
    if not SCIPY_AVAILABLE or b is None or fs < 10 or len(y_raw) < int(fs * 3): return None, 0.0
    try:
        y = y_raw.astype(np.float64) - np.mean(y_raw)
        y_f = filtfilt(b, a, y); n = len(y_f)
        if n < int(fs * 3) or np.std(y_f) < 1e-6: return None, 0.0

        y_win = (y_f - np.mean(y_f)) * np.hanning(n)
        nfft = 1
        while nfft < n * 4: nfft *= 2
        mag = np.abs(np.fft.rfft(y_win, n=nfft)); freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)

        band = (freqs >= BPM_MIN / 60.0) & (freqs <= BPM_MAX / 60.0)
        if not np.any(band): return None, 0.0
        
        band_mag = mag[band]; band_freqs = freqs[band]
        f_peak = band_freqs[np.argmax(band_mag)]

        lobe_mask = np.abs(band_freqs - f_peak) <= 0.15
        sqi = float(np.sum(band_mag[lobe_mask] ** 2)) / (float(np.sum(band_mag ** 2)) + 1e-9)

        if sqi < 0.65: return None, 0.0
        return float(f_peak * 60.0), sqi
    except Exception: return None, 0.0

# =================================================================
# --- Manejo de Buffers ---
# =================================================================
class RingBuffer:
    __slots__ = ("t","ir","red","cap","head","count")
    def __init__(self, capacity:int):
        self.cap = capacity
        self.t, self.ir, self.red = np.empty(self.cap, dtype=np.int64), np.empty(self.cap, dtype=np.int32), np.empty(self.cap, dtype=np.int32)
        self.head = self.count = 0
    def append(self, ts:int, ir:int, red:int):
        self.t[self.head], self.ir[self.head], self.red[self.head] = ts, ir, red
        self.head = (self.head + 1) % self.cap; self.count = min(self.count + 1, self.cap)
    def window_view(self, t_now:int, span_us:int):
        if self.count == 0: return None
        idx, seen = (self.head - 1) % self.cap, 0
        while seen < self.count and self.t[idx] >= t_now - span_us:
            idx = (idx - 1) % self.cap; seen += 1
        start, length = (idx + 1) % self.cap, min(seen, self.count)
        if length == 0: return None
        if start + length <= self.cap: return (self.t[start:start+length], self.ir[start:start+length], self.red[start:start+length])
        first_len = self.cap - start
        return (np.concatenate((self.t[start:], self.t[:length-first_len])), np.concatenate((self.ir[start:], self.ir[:length-first_len])), np.concatenate((self.red[start:], self.red[:length-first_len])))

class SlaveBuffer:
    __slots__ = ("ring", "fs_dev", "fs_host", "fs_est", "last_ts", "last_rx", "last_rx_prev", "alpha", "beta", "dirty", "t0_us", "ts_hist", "ax_hist", "ay_hist", "az_hist", "gx_hist", "gy_hist", "gz_hist", "battery_mv")
    def __init__(self):
        self.ring = RingBuffer(RING_CAPACITY)
        self.fs_dev = self.fs_host = self.fs_est = 0.0
        self.last_ts = self.last_rx_prev = self.t0_us = None
        self.last_rx = time.monotonic()
        self.alpha, self.beta, self.dirty, self.battery_mv = 0.25, 0.20, False, 0
        self.ts_hist = deque(maxlen=128)
        self.ax_hist, self.ay_hist, self.az_hist = deque(maxlen=RING_CAPACITY), deque(maxlen=RING_CAPACITY), deque(maxlen=RING_CAPACITY)
        self.gx_hist, self.gy_hist, self.gz_hist = deque(maxlen=RING_CAPACITY), deque(maxlen=RING_CAPACITY), deque(maxlen=RING_CAPACITY)

    def append(self, ts, red, ir, ax, ay, az, gx, gy, gz, fs_csv, battery_mv=0):
        if self.t0_us is None: self.t0_us = ts
        self.ring.append(ts, ir, red); self.battery_mv = battery_mv
        self.ax_hist.append(ax); self.ay_hist.append(ay); self.az_hist.append(az)
        self.gx_hist.append(gx); self.gy_hist.append(gy); self.gz_hist.append(gz)

        if self.last_ts is not None and (dt_us := ts - self.last_ts) > 0:
            inst_fs_dev = 1_000_000.0 / dt_us; self.fs_dev = inst_fs_dev if self.fs_dev == 0.0 else (self.alpha*inst_fs_dev + (1-self.alpha)*self.fs_dev)
        self.last_ts = ts; self.ts_hist.append(ts)
        
        if len(self.ts_hist) >= 5 and (dt_win := self.ts_hist[-1] - self.ts_hist[0]) > 0:
            fs_now = ((len(self.ts_hist) - 1) * 1_000_000.0) / dt_win; self.fs_est = fs_now if self.fs_est == 0.0 else (self.beta*fs_now + (1-self.beta)*self.fs_est)
        rx_now = time.monotonic()
        if self.last_rx_prev is not None and (dt_host := rx_now - self.last_rx_prev) > 0:
            inst_fs_host = 1.0 / dt_host; self.fs_host = inst_fs_host if self.fs_host == 0.0 else (self.alpha*inst_fs_host + (1-self.alpha)*self.fs_host)
        self.last_rx_prev = self.last_rx = rx_now; self.dirty = True

    def snapshot(self):
        if self.ring.count == 0 or self.t0_us is None: self.dirty = False; return None
        t_now_us = int(self.ring.t[(self.ring.head-1) % self.ring.cap])
        view = self.ring.window_view(t_now_us, DATA_WINDOW_US + FILTER_PADDING_US)
        if view is None: self.dirty = False; return None
        t_us, y_ir, y_red = view
        self.dirty = False
        return (t_us - self.t0_us) / 1e6, y_ir, y_red, (t_now_us, self.fs_est, self.fs_dev, self.fs_host, self.last_rx, (t_now_us - self.t0_us) / 1e6, self.t0_us)

class SerialIO(QObject):
    lineParsed, systemMessage = pyqtSignal(str), pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.port = QSerialPort(self); self.port.setBaudRate(BAUD_RATE); self.port.readyRead.connect(self._on_ready_read)
    def open(self, port_name: str) -> bool:
        if self.port.isOpen(): self.port.close()
        self.port.setPortName(port_name); self.port.setReadBufferSize(128000) 
        return self.port.open(QSerialPort.OpenModeFlag.ReadWrite)
    def close(self):
        if self.port.isOpen(): self.port.close()
    def write_cmd(self, cmd: str):
        if self.port.isOpen(): self.port.write(cmd.encode('utf-8'))
    def _on_ready_read(self):
        while self.port.canReadLine():
            try:
                line = self.port.readLine().data().decode('utf-8', 'ignore').strip()
                if not line: continue
                if line.startswith('Slave') or line.startswith('Unknown'): self.lineParsed.emit(line)
                else: self.systemMessage.emit(line)
            except Exception: pass

# =================================================================
# --- SLAVE CARD ---
# =================================================================
class SlaveCard(QWidget):
    def __init__(self, slave_id: str):
        super().__init__() 
        self.slave_id = slave_id; self.t0_us = None; self.filter_enabled = False 
        self.cached_b = self.cached_a = None; self.last_filter_fs = 0.0
        self.filt_zi_ir = self.filt_zi_red = self.filt_offset_ir = self.filt_offset_red = self.filt_last_x_sec = None
        self.filt_hist_t, self.filt_hist_ir, self.filt_hist_red = deque(maxlen=RING_CAPACITY), deque(maxlen=RING_CAPACITY), deque(maxlen=RING_CAPACITY)
        
        self.cached_hr_b = self.cached_hr_a = None; self.last_hr_filter_fs = 0.0
        self.hr_ema = None; self.hr_miss_count = 0 
        
        self.last_hr_calc_time = 0.0 
        self.last_welch_calc_time = 0.0 
        
        self._build()

    def _build(self):
        loc_name = SLAVE_LOCATIONS.get(str(self.slave_id), "Sensor Genérico")
        accent = LOCATION_ACCENT.get(loc_name, DEFAULT_ACCENT)
        self.accent_color = accent

        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 12px; }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15); shadow.setXOffset(0); shadow.setYOffset(4); shadow.setColor(QColor(0, 0, 0, 15))
        self.container.setGraphicsEffect(shadow)

        main_lay = QVBoxLayout(self); main_lay.setContentsMargins(5, 5, 5, 5)
        main_lay.addWidget(self.container)

        card_layout = QVBoxLayout(self.container); card_layout.setContentsMargins(20,20,20,20); card_layout.setSpacing(15)
        
        accent_bar = QFrame(); accent_bar.setFixedHeight(4)
        accent_bar.setStyleSheet(f"background-color: {accent}; border: none; border-radius: 2px;")
        card_layout.addWidget(accent_bar)

        title_layout = QHBoxLayout()
        self.heartbeat_label = QLabel("●"); self.heartbeat_label.setFont(QFont("Segoe UI", 16)); self.heartbeat_label.setStyleSheet("border: none; background: transparent;")
        title_label = QLabel(f"{loc_name} ({self.slave_id})"); title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold)); title_label.setStyleSheet("color: #000000; border: none; background: transparent;")
        title_layout.addWidget(self.heartbeat_label); title_layout.addWidget(title_label); title_layout.addStretch()
          
        self.l_fs = QLabel("Fs: -- Hz"); self.l_fs.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold)); self.l_fs.setStyleSheet("color: #000000; background: #F1F5F9; padding: 4px 10px; border-radius: 6px; border: 1px solid #CBD5E1;")
        title_layout.addWidget(self.l_fs)
        self.battery_ui = BatteryWidget(); title_layout.addWidget(self.battery_ui)
        card_layout.addLayout(title_layout)

        hr_row = QHBoxLayout()
        self.l_hr_icon = QLabel("♥"); self.l_hr_icon.setFont(QFont("Segoe UI", 24)); self.l_hr_icon.setStyleSheet("color: #EF4444; border: none; background: transparent;")
        self.l_hr_value = QLabel("--"); self.l_hr_value.setFont(QFont("Segoe UI", 36, QFont.Weight.Black)); self.l_hr_value.setStyleSheet("color: #0EA5E9; border: none; background: transparent;")
        self.l_hr_unit = QLabel("BPM"); self.l_hr_unit.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold)); self.l_hr_unit.setStyleSheet("color: #000000; border: none; background: transparent;"); self.l_hr_unit.setAlignment(Qt.AlignmentFlag.AlignBottom)
        hr_row.addWidget(self.l_hr_icon); hr_row.addWidget(self.l_hr_value); hr_row.addWidget(self.l_hr_unit); hr_row.addStretch()

        hr_status_col = QVBoxLayout()
        self.l_hr_status = QLabel("Buscando señal…"); self.l_hr_status.setFont(QFont("Segoe UI", 10)); self.l_hr_status.setStyleSheet("color: #000000; font-weight: 800; border: none; background: transparent;"); self.l_hr_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.hr_quality_bar = QProgressBar(); self.hr_quality_bar.setFixedSize(80, 8); self.hr_quality_bar.setTextVisible(False)
        self.hr_quality_bar.setStyleSheet("QProgressBar { border: 1px solid #CBD5E1; background: #F1F5F9; border-radius: 4px; } QProgressBar::chunk { background-color: #6B7280; border-radius: 3px; }")
        hr_status_col.addWidget(self.l_hr_status); hr_status_col.addWidget(self.hr_quality_bar)
        hr_row.addLayout(hr_status_col); card_layout.addLayout(hr_row)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #CBD5E1; border-radius: 8px; background: #FFFFFF; }
            QTabBar::tab { background: #F1F5F9; color: #000000; padding: 8px 16px; border: 1px solid #CBD5E1; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: 800; margin-right: 2px; }
            QTabBar::tab:selected { background: #FFFFFF; color: #0EA5E9; border-bottom: 2px solid #0EA5E9; }
            QTabBar::tab:hover:!selected { background: #E2E8F0; }
        """)

        tab_time = QWidget(); lay_time = QVBoxLayout(tab_time); lay_time.setContentsMargins(8,8,8,8)
        ax_ir, ax_red = OneDecimalAxis(orientation='bottom'), OneDecimalAxis(orientation='bottom')
        self.plot_ir, self.plot_red = pg.PlotWidget(axisItems={'bottom': ax_ir}), pg.PlotWidget(axisItems={'bottom': ax_red})
          
        C_IR, C_RED, C_IMU = '#0284C7', '#DC2626', '#D97706' 

        for p in (self.plot_ir, self.plot_red):
            p.setMinimumHeight(130); p.showGrid(x=True, y=True, alpha=0.2); p.setMenuEnabled(False); p.enableAutoRange(axis='y', enable=True); p.getPlotItem().getViewBox().setMouseEnabled(x=False, y=False); p.getPlotItem().invertY(True)
            p.getAxis('bottom').setPen(pg.mkPen('#CBD5E1')); p.getAxis('left').setPen(pg.mkPen('#CBD5E1'))
            p.getAxis('bottom').setTextPen('#000000'); p.getAxis('left').setTextPen('#000000')

        self.plot_ir.setLabel('left', 'IR', color=C_IR); self.plot_red.setLabel('left', 'RED', color=C_RED); self.plot_red.setXLink(self.plot_ir)
        self.c_ir = self.plot_ir.plot(pen=pg.mkPen(C_IR, width=2)); self.c_red = self.plot_red.plot(pen=pg.mkPen(C_RED, width=2))
        
        pen_pulse = pg.mkPen('#10B981', style=Qt.PenStyle.DashLine, width=1.5)
        self.pulse_line_ir, self.pulse_line_red = pg.InfiniteLine(pos=0, angle=90, movable=False, pen=pen_pulse), pg.InfiniteLine(pos=0, angle=90, movable=False, pen=pen_pulse)
        self.pulse_line_ir.setVisible(False); self.pulse_line_red.setVisible(False)
        self.plot_ir.addItem(self.pulse_line_ir); self.plot_red.addItem(self.pulse_line_red)

        lay_time.addWidget(self.plot_ir); lay_time.addWidget(self.plot_red)
        self.tabs.addTab(tab_time, "Dominio del Tiempo (PPG)")

        tab_welch = QWidget(); lay_welch = QVBoxLayout(tab_welch); lay_welch.setContentsMargins(8,8,8,8)
        self.plot_welch = pg.PlotWidget(); self.plot_welch.setMinimumHeight(260); self.plot_welch.showGrid(x=True, y=True, alpha=0.3)
        self.plot_welch.getAxis('bottom').setPen(pg.mkPen('#CBD5E1')); self.plot_welch.getAxis('left').setPen(pg.mkPen('#CBD5E1'))
        self.plot_welch.getAxis('bottom').setTextPen('#000000'); self.plot_welch.getAxis('left').setTextPen('#000000')
        self.plot_welch.setLabel('bottom', 'Frecuencia (Hz)', color='#000000')
        self.plot_welch.setLabel('left', 'Potencia Espectral (PSD Lineal)', color='#000000')
        self.plot_welch.setXRange(0.1, 8.0) 
        
        self.c_welch_imu = self.plot_welch.plot(pen=pg.mkPen(C_IMU, width=1.5), fillLevel=0, fillBrush=(217, 119, 6, 40), name='PSD IMU (Ref)')
        self.c_welch_ir = self.plot_welch.plot(pen=pg.mkPen(C_IR, width=2.5), name='PSD IR')
        self.c_welch_red = self.plot_welch.plot(pen=pg.mkPen(C_RED, width=1.5, style=Qt.PenStyle.DashLine), name='PSD RED')
        
        self.hr_freq_line = pg.InfiniteLine(pos=1.0, angle=90, movable=False, pen=pg.mkPen('#10B981', width=2.0))
        self.plot_welch.addItem(self.hr_freq_line); self.hr_freq_line.setVisible(False)

        lay_welch.addWidget(self.plot_welch); self.tabs.addTab(tab_welch, "Espectro Welch (Mitigación Artefactos)")
        card_layout.addWidget(self.tabs, 1)

        imu_frame = QFrame(); imu_frame.setStyleSheet("background-color: #F8FAFC; border-radius: 8px; border: 1px solid #CBD5E1;")
        imu_layout = QHBoxLayout(imu_frame); imu_layout.setContentsMargins(15,12,15,12)
        def _imu_block(caption):
            block = QVBoxLayout(); block.setSpacing(2)
            cap = QLabel(caption); cap.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold)); cap.setStyleSheet(f"color: {self.accent_color}; border: none; background: transparent;")
            val = QLabel("X: ---   Y: ---   Z: ---"); val.setFont(QFont("Consolas", 11, QFont.Weight.Bold)); val.setStyleSheet("color: #000000; border: none; background: transparent;")
            block.addWidget(cap); block.addWidget(val); return block, val
        acc_block, self.lbl_acc = _imu_block("ACELERÓMETRO")
        gyro_block, self.lbl_gyro = _imu_block("GIROSCOPIO")
        imu_layout.addLayout(acc_block); imu_layout.addLayout(gyro_block)
        card_layout.addWidget(imu_frame)

    def set_filter_mode(self, enabled: bool):
        self.filter_enabled = enabled
        if enabled:
            self.filt_zi_ir = self.filt_zi_red = self.filt_offset_ir = self.filt_offset_red = self.filt_last_x_sec = None
            self.filt_hist_t.clear(); self.filt_hist_ir.clear(); self.filt_hist_red.clear()
        suffix = " (Filt)" if enabled else ""
        self.plot_ir.setLabel('left', f'IR{suffix}', color='#0284C7'); self.plot_red.setLabel('left', f'RED{suffix}', color='#DC2626')

    def update_heartbeat(self, last_rx_time: float):
        dt = time.monotonic() - last_rx_time
        if dt < 1.0: self.heartbeat_label.setStyleSheet("color: #10B981; border: none; background: transparent;")
        elif dt < 3.0: self.heartbeat_label.setStyleSheet("color: #F59E0B; border: none; background: transparent;")
        else: self.heartbeat_label.setStyleSheet("color: #EF4444; border: none; background: transparent;")

    def update_battery(self, battery_mv: int): self.battery_ui.set_value(battery_mv)

    def _update_hr_display(self, bpm: Optional[float], sqi: float):
        self.hr_quality_bar.setValue(max(0, min(100, int((sqi - 0.65) / 0.35 * 100))))
        if bpm is None:
            self.hr_miss_count += 1
            self.hr_quality_bar.setStyleSheet("QProgressBar::chunk { background-color: #9CA3AF; }")
            if self.hr_ema is not None and self.hr_miss_count <= 4:
                self.l_hr_value.setText(f"{self.hr_ema:.0f}"); self.l_hr_status.setText("Señal débil"); self.l_hr_status.setStyleSheet("color: #F59E0B; font-weight: bold; border: none; background: transparent;")
            else:
                self.hr_ema = None; self.l_hr_value.setText("--"); self.l_hr_status.setText("Buscando señal…"); self.l_hr_status.setStyleSheet("color: #000000; font-weight: bold; border: none; background: transparent;")
                self.hr_freq_line.setVisible(False)
            return

        self.hr_miss_count = 0; self.hr_ema = bpm if self.hr_ema is None else (0.3 * bpm + 0.7 * self.hr_ema)
        self.l_hr_value.setText(f"{self.hr_ema:.0f}")
        self.hr_freq_line.setPos(self.hr_ema / 60.0); self.hr_freq_line.setVisible(True)

        color = "#10B981" if sqi >= 0.85 else "#F59E0B"
        self.l_hr_status.setText("Señal fuerte" if sqi >= 0.85 else "Señal aceptable")
        self.l_hr_status.setStyleSheet(f"color: {color}; font-weight: bold; border: none; background: transparent;")
        self.hr_quality_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")

    def update_from_snapshot(self, snap, pulse_time_us: Optional[int], imu_acc_norm: Optional[np.ndarray] = None):
        if snap is None: return
        x_sec, y_ir, y_red, meta = snap
        t_now_us, fs_est, fs_dev, fs_host, last_rx, last_sec, self.t0_us = meta

        now_mono = time.monotonic()
        
        # --- CÁLCULO HR (1 Hz) ---
        if now_mono - self.last_hr_calc_time >= HR_RECOMPUTE_INTERVAL_S:
            self.last_hr_calc_time = now_mono
            fs_for_hr = fs_est if fs_est > 10 else TARGET_FS_HZ
            if SCIPY_AVAILABLE and len(y_ir) > 20:
                if abs(fs_for_hr - self.last_hr_filter_fs) > 1.0 or self.cached_hr_b is None:
                    self.cached_hr_b, self.cached_hr_a = create_filter(fs_for_hr, 0.5, 5.0, order=2); self.last_hr_filter_fs = fs_for_hr
                bpm, sqi = estimate_bpm(y_ir, fs_for_hr, self.cached_hr_b, self.cached_hr_a)
            else: bpm, sqi = None, 0.0
            self._update_hr_display(bpm, sqi)

        # --- CÁLCULO WELCH FLUIDO (10 FPS) ---
        if now_mono - self.last_welch_calc_time >= WELCH_RECOMPUTE_INTERVAL_S:
            self.last_welch_calc_time = now_mono
            if SCIPY_AVAILABLE and self.tabs.currentIndex() == 1 and len(y_ir) >= 100:
                try:
                    fs_for_hr = fs_est if fs_est > 10 else TARGET_FS_HZ
                    if self.filter_enabled and self.cached_b is not None:
                        y_ir_w = filtfilt(self.cached_b, self.cached_a, y_ir.astype(np.float64) - np.mean(y_ir))
                        y_red_w = filtfilt(self.cached_b, self.cached_a, y_red.astype(np.float64) - np.mean(y_red))
                    else:
                        y_ir_w = y_ir.astype(np.float64) - np.mean(y_ir)
                        y_red_w = y_red.astype(np.float64) - np.mean(y_red)

                    ir_n = y_ir_w / (np.std(y_ir_w) + 1e-6)
                    red_n = y_red_w / (np.std(y_red_w) + 1e-6)
                    
                    nperseg = min(len(ir_n), int(fs_for_hr * 2))
                    nfft = max(512, nperseg) 

                    f_ir, psd_ir = welch(ir_n, fs=fs_for_hr, nperseg=nperseg, nfft=nfft)
                    f_red, psd_red = welch(red_n, fs=fs_for_hr, nperseg=nperseg, nfft=nfft)
                    
                    self.c_welch_ir.setData(f_ir, psd_ir)
                    self.c_welch_red.setData(f_red, psd_red)

                    if imu_acc_norm is not None and len(imu_acc_norm) >= 100:
                        imu_n = (imu_acc_norm - np.mean(imu_acc_norm)) / (np.std(imu_acc_norm) + 1e-6)
                        f_imu, psd_imu = welch(imu_n, fs=fs_for_hr, nperseg=min(len(imu_n), int(fs_for_hr*2)), nfft=nfft)
                        self.c_welch_imu.setData(f_imu, psd_imu)
                except Exception: pass

        # --- Filtro visual streaming (Dominio Tiempo) ---
        if self.filter_enabled and SCIPY_AVAILABLE and len(y_ir) > 30:
            fs_calc = fs_est if fs_est > 10 else TARGET_FS_HZ
            if abs(fs_calc - self.last_filter_fs) > 1.0 or self.cached_b is None:
                self.cached_b, self.cached_a = create_filter(fs_calc, 0.5, 5.0, order=2); self.last_filter_fs = fs_calc
                self.filt_zi_ir = self.filt_zi_red = self.filt_offset_ir = self.filt_offset_red = self.filt_last_x_sec = None
                self.filt_hist_t.clear(); self.filt_hist_ir.clear(); self.filt_hist_red.clear()

            if self.cached_b is not None:
                try:
                    new_mask = np.ones(len(x_sec), dtype=bool) if self.filt_last_x_sec is None else x_sec > self.filt_last_x_sec
                    if np.any(new_mask):
                        new_ir, new_red, new_x = y_ir[new_mask].astype(np.float64), y_red[new_mask].astype(np.float64), x_sec[new_mask]
                        if self.filt_offset_ir is None: self.filt_offset_ir, self.filt_offset_red = float(new_ir[0]), float(new_red[0])
                        if self.filt_zi_ir is None:
                            zi0 = lfilter_zi(self.cached_b, self.cached_a)
                            self.filt_zi_ir, self.filt_zi_red = zi0 * (new_ir[0] - self.filt_offset_ir), zi0 * (new_red[0] - self.filt_offset_red)
                        f_ir, self.filt_zi_ir = lfilter(self.cached_b, self.cached_a, new_ir - self.filt_offset_ir, zi=self.filt_zi_ir)
                        f_red, self.filt_zi_red = lfilter(self.cached_b, self.cached_a, new_red - self.filt_offset_red, zi=self.filt_zi_red)
                        self.filt_hist_t.extend(new_x.tolist()); self.filt_hist_ir.extend((f_ir + self.filt_offset_ir).tolist()); self.filt_hist_red.extend((f_red + self.filt_offset_red).tolist())
                        self.filt_last_x_sec = float(new_x[-1])
                    if len(self.filt_hist_t) > 0: x_sec, y_ir, y_red = np.array(self.filt_hist_t), np.array(self.filt_hist_ir), np.array(self.filt_hist_red)
                except Exception: pass

        visible_start = last_sec - DATA_WINDOW_SECONDS
        mask = x_sec >= visible_start
        x_plot, y_ir_plot, y_red_plot = (x_sec[mask], y_ir[mask], y_red[mask]) if np.any(mask) else (x_sec, y_ir, y_red)
        self.c_ir.setData(x=x_plot, y=y_ir_plot); self.c_red.setData(x=x_plot, y=y_red_plot)
        self.plot_ir.setXRange(visible_start, last_sec, padding=0.01)
        self.l_fs.setText(f"Fs: {fs_est:.1f} Hz")

        if pulse_time_us is not None and self.t0_us is not None:
            pos = (pulse_time_us - self.t0_us) / 1e6
            self.pulse_line_ir.setPos(pos); self.pulse_line_red.setPos(pos)
            self.pulse_line_ir.setVisible(True); self.pulse_line_red.setVisible(True)
        else: self.pulse_line_ir.setVisible(False); self.pulse_line_red.setVisible(False)

    def update_imu_text(self, ax, ay, az, gx, gy, gz):
        self.lbl_acc.setText(f"X:{ax[-1] if ax else 0:>6}   Y:{ay[-1] if ay else 0:>6}   Z:{az[-1] if az else 0:>6}")
        self.lbl_gyro.setText(f"X:{gx[-1] if gx else 0:>6}   Y:{gy[-1] if gy else 0:>6}   Z:{gz[-1] if gz else 0:>6}")

# =================================================================
# --- DIÁLOGOS DE REGISTRO (CON FORZADO DE ESTILO ABSOLUTO) ---
# =================================================================
class RecordConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Registro")
        self.setModal(True); self._build()
    def _build(self):
        self.setStyleSheet("""
            QDialog { background-color: #F8FAFC; }
            QLabel { color: #000000; font-size: 14px; font-weight: 800; font-family: 'Segoe UI'; }
            QLineEdit, QComboBox { 
                background-color: #FFFFFF; color: #000000; border: 1px solid #CBD5E1; 
                border-radius: 6px; padding: 8px; font-size: 14px; font-family: 'Segoe UI';
                font-weight: 800;
            }
            QComboBox QAbstractItemView { 
                background-color: #FFFFFF; color: #000000; 
                selection-background-color: #BAE6FD; selection-color: #000000; 
            }
            QPushButton { 
                background-color: #7DD3FC; color: #000000; border: 1px solid #38BDF8; 
                border-radius: 6px; padding: 10px 20px; font-weight: 800; font-family: 'Segoe UI';
            }
            QPushButton:hover { background-color: #38BDF8; }
        """)
        lay = QVBoxLayout(self); form = QFormLayout(); form.setSpacing(15)
        self.e_num, self.e_name = QLineEdit(), QLineEdit()
        self.cb_stage = QComboBox(); self.cb_stage.addItems(["Sentado", "Parado", "2 km", "4 km", "8 km"])
        self.cb_time = QComboBox(); self.cb_time.addItems(["30 s", "1 min", "2 min"])
        form.addRow("Número de sujeto:", self.e_num); form.addRow("Nombre:", self.e_name)
        form.addRow("Etapa deportiva:", self.cb_stage); form.addRow("Tiempo:", self.cb_time)
        lay.addLayout(form); lay.addItem(QSpacerItem(10, 20))
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
    def values(self):
        tsel = self.cb_time.currentText()
        return self.e_num.text().strip(), self.e_name.text().strip(), self.cb_stage.currentText(), 30 if tsel == "30 s" else (60 if tsel == "1 min" else 120)

class RecordPreviewDialog(QDialog):
    def __init__(self, parent, recorded: Dict[str, Dict[str, np.ndarray]], duration_s: float):
        super().__init__(parent)
        self.setWindowTitle("Revisión de Señal Grabada")
        self.resize(1000, 600); self.setModal(True); self.duration_s = float(duration_s); self._build(recorded)
    def _build(self, recorded):
        self.setStyleSheet("QDialog { background-color: #F8FAFC; color: #000000; font-family: 'Segoe UI'; }")
        lay = QVBoxLayout(self)
        title = QLabel("Vista Previa de Datos Sincronizados")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold)); title.setStyleSheet("color: #000000; margin-bottom: 15px;")
        lay.addWidget(title)
        scroll_area = QWidget(); scroll_area.setStyleSheet("background-color: transparent;")
        scroll_lay = QVBoxLayout(scroll_area)
        for sid, seg in recorded.items():
            box = QGroupBox(f"Dispositivo: {sid}")
            box.setStyleSheet("QGroupBox { border: 2px solid #CBD5E1; border-radius: 8px; margin-top: 20px; background-color: #FFFFFF; color: #000000; font-weight: 800; }")
            v = QVBoxLayout(box)
            pw = pg.PlotWidget(axisItems={'bottom': OneDecimalAxis(orientation='bottom')}); pw.setMinimumHeight(160)
            pw.showGrid(x=False, y=False); pw.getPlotItem().invertY(True)
            pw.setBackground('#FFFFFF')
            pw.getAxis('bottom').setPen(pg.mkPen('#CBD5E1')); pw.getAxis('left').setPen(pg.mkPen('#CBD5E1'))
            pw.getAxis('bottom').setTextPen('#000000'); pw.getAxis('left').setTextPen('#000000')
            t_sec, ir, red, ylims = seg.get("t_sec", np.array([])), seg.get("ir", np.array([])), seg.get("red", np.array([])), seg.get("ylims", None)
            pw.plot(t_sec, ir, pen=pg.mkPen('#0284C7', width=1.5)); pw.plot(t_sec, red, pen=pg.mkPen('#DC2626', width=1.5))
            pw.setXRange(0.0, self.duration_s, padding=0.0)
            if ylims: pw.setYRange(ylims[0], ylims[1], padding=0.0)
            v.addWidget(pw); scroll_lay.addWidget(box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_area)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        lay.addWidget(scroll, 1)
        self.buttons = QDialogButtonBox()
        btn_cancel = self.buttons.addButton("Descartar", QDialogButtonBox.ButtonRole.RejectRole)
        btn_save = self.buttons.addButton("Guardar CSV", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_cancel.setStyleSheet("background-color: #FEE2E2; border: 1px solid #FCA5A5; border-radius: 6px; padding: 10px 20px; color: #000000; font-weight: 800;")
        btn_save.setStyleSheet("background-color: #D1FAE5; border: 1px solid #6EE7B7; border-radius: 6px; padding: 10px 20px; color: #000000; font-weight: 800;")
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)

# =================================================================
# --- MainWindow ---
# =================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPEC-P6 Acquisition Suite | M.Sc. Andrés Navarro")
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(int((screen.width()-1600)/2), int((screen.height()-950)/2), min(1600, int(screen.width()*0.9)), min(950, int(screen.height()*0.9)))

        self.slave_store, self.cards, self.order = {}, {}, []
        self.io = SerialIO(self); self.io.lineParsed.connect(self._on_line); self.io.systemMessage.connect(self._on_system_message)
        self.connected, self.biopac_pulse_fired, self.rec_active, self.is_calibrating = False, False, False, False
        self.rec_pulse_ts_us, self.align_us = None, None
        self.participants_to_calibrate, self.calibrated_slaves, self.participants = set(), set(), set()
        self.rec_meta, self.first_ts, self.count, self.saved, self.drop_left = {}, {}, {}, {}, {}
        self.rec_duration_s, self.rec_target_n, self.join_deadline, self.join_start_time = 0.0, 0, 0.0, 0.0
        self.participants_frozen = False

        self.timer = QTimer(self); self.timer.setInterval(GUI_INTERVAL_MS); self.timer.timeout.connect(self.refresh_gui)
        self.progress_timer = QTimer(self); self.progress_timer.setInterval(100); self.progress_timer.timeout.connect(self._on_progress_tick)
        self.countdown_timer = QTimer(self); self.countdown_timer.setInterval(1000); self.countdown_timer.timeout.connect(self._on_countdown_tick)
        self.calib_timeout_timer = QTimer(self); self.calib_timeout_timer.setSingleShot(True); self.calib_timeout_timer.timeout.connect(self._on_calib_timeout)
        self.countdown_value, self.frame_counter = 0, 0

        self._style(); self._build()
        self.log_message("Sistema de Laboratorio Iniciado.")

    def _style(self):
        self.setStyleSheet("""
            * { outline: none; }
            QMainWindow, QWidget#central { background-color: #F1F5F9; } 
            QWidget { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; color: #000000; }
            QStatusBar { background-color: #FFFFFF; color: #000000; border-top: 1px solid #CBD5E1; }
            
            QComboBox { 
                background-color: #FFFFFF; color: #000000; 
                border: 1px solid #9CA3AF; padding: 8px 12px; border-radius: 6px; 
                font-weight: 800;
            }
            QComboBox QAbstractItemView { 
                background-color: #FFFFFF; color: #000000; 
                selection-background-color: #BAE6FD; selection-color: #000000; 
            }
            
            QPushButton { 
                background-color: #F8FAFC; color: #000000; border: 1px solid #9CA3AF; 
                padding: 10px 18px; border-radius: 6px; font-weight: 800; 
            }
            QPushButton:hover { background-color: #E2E8F0; border-color: #64748B; }
            QPushButton:disabled { background-color: #E5E7EB; color: #9CA3AF; border-color: transparent; }
            
            /* Colores vivos tipo PASTEL garantizan que la letra NEGRA resalte siempre */
            QPushButton#btnPrimary { background-color: #BAE6FD; color: #000000; border: 1px solid #7DD3FC; } 
            QPushButton#btnPrimary:hover { background-color: #7DD3FC; }
            
            QPushButton#btnSuccess { background-color: #D1FAE5; color: #000000; border: 1px solid #6EE7B7; } 
            QPushButton#btnSuccess:hover { background-color: #6EE7B7; }
            
            QPushButton#btnDanger { background-color: #FEE2E2; color: #000000; border: 1px solid #FCA5A5; } 
            QPushButton#btnDanger:hover { background-color: #FCA5A5; }
            
            QPushButton#btnInfo { background-color: #EDE9FE; color: #000000; border: 1px solid #C4B5FD; } 
            QPushButton#btnInfo:hover { background-color: #C4B5FD; }
            
            QPushButton#btnFilter { background-color: #FFFFFF; color: #000000; border: 1px solid #9CA3AF; }
            QPushButton#btnFilter:checked { background-color: #BAE6FD; color: #000000; border: 1px solid #7DD3FC; }
            
            QGroupBox#panel { 
                border: 2px solid #CBD5E1; border-radius: 10px; margin-top: 12px; 
                background-color: #FFFFFF; font-weight: 900; color: #000000; 
            }
            QGroupBox#panel::title { 
                subcontrol-origin: margin; left: 12px; bottom: -8px; 
                background-color: #F1F5F9; color: #000000; padding: 4px 10px; 
                border-radius: 4px; border: 1px solid #CBD5E1; 
            }
            
            QTextEdit { 
                background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; 
                color: #000000; font-family: 'Consolas', monospace; padding: 8px; font-weight: 600;
            }
            
            QProgressBar { 
                border: 1px solid #CBD5E1; background-color: #F8FAFC; 
                height: 12px; border-radius: 6px; text-align: center; color: transparent; 
            }
            QProgressBar::chunk { background-color: #10B981; border-radius: 5px; }
            
            QScrollArea { background-color: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background-color: transparent; }
        """)

    def _build(self):
        central = QWidget(); central.setObjectName("central")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)

        self.sidebar_widget = QWidget(); self.sidebar_widget.setFixedWidth(350)
        self.sidebar_widget.setStyleSheet("background-color: #FFFFFF; border-right: 2px solid #CBD5E1;")
        sidebar_layout = QVBoxLayout(self.sidebar_widget); sidebar_layout.setContentsMargins(20,30,20,30); sidebar_layout.setSpacing(20)

        title_row = QHBoxLayout()
        title = QLabel("SPEC-P6 STUDIO"); title.setFont(QFont("Segoe UI", 16, QFont.Weight.Black)); title.setStyleSheet("color: #000000; border: none;")
        version_pill = QLabel("PRO"); version_pill.setStyleSheet("color: #000000; background-color: #6EE7B7; border-radius: 4px; padding: 2px 6px; font-weight: 900; border: none;")
        title_row.addWidget(title); title_row.addWidget(version_pill); title_row.addStretch()
        sidebar_layout.addLayout(title_row)

        com_box = QGroupBox("CONEXIÓN"); com_box.setObjectName("panel")
        comL = QGridLayout(com_box); comL.setSpacing(12); comL.setContentsMargins(15,25,15,20)
        self.cb_port = QComboBox()
        self.btn_refresh = QPushButton("Refrescar"); self.btn_refresh.clicked.connect(self.refresh_ports)
        self.btn_conn = QPushButton("Conectar"); self.btn_conn.setObjectName("btnPrimary"); self.btn_conn.clicked.connect(self.toggle_conn)
        comL.addWidget(self.cb_port, 0, 0, 1, 2); comL.addWidget(self.btn_refresh, 1, 0); comL.addWidget(self.btn_conn, 1, 1)
        self.lbl_status = QLabel("<span style='color:#64748B;'>●</span> Desconectado"); self.lbl_status.setStyleSheet("font-weight: 800;")
        comL.addWidget(self.lbl_status, 2, 0, 1, 2)
        sidebar_layout.addWidget(com_box)
          
        cmd_box = QGroupBox("CONTROL MAESTRO"); cmd_box.setObjectName("panel")
        cmdL = QGridLayout(cmd_box); cmdL.setSpacing(12); cmdL.setContentsMargins(15,25,15,20)
        self.btn_start = QPushButton("MONITOREAR"); self.btn_start.setObjectName("btnSuccess"); self.btn_start.clicked.connect(lambda: self.send_cmd('1'))
        self.btn_stop  = QPushButton("STOP"); self.btn_stop.setObjectName("btnDanger"); self.btn_stop.clicked.connect(lambda: self.send_cmd('0'))
        self.btn_calib = QPushButton("Calibrar Sensores"); self.btn_calib.setObjectName("btnInfo"); self.btn_calib.clicked.connect(lambda: self.send_cmd('3'))
        self.btn_filter = QPushButton("Filtro y PSD (Activar)"); self.btn_filter.setObjectName("btnFilter"); self.btn_filter.setCheckable(True); self.btn_filter.clicked.connect(self.toggle_filter)
        self.btn_record = QPushButton("NUEVO REGISTRO"); self.btn_record.setObjectName("btnPrimary"); self.btn_record.setMinimumHeight(55); self.btn_record.clicked.connect(self.open_record_dialog)
        cmdL.addWidget(self.btn_start, 0, 0); cmdL.addWidget(self.btn_stop, 0, 1)
        cmdL.addWidget(self.btn_calib, 1, 0, 1, 2); cmdL.addWidget(self.btn_filter, 2, 0, 1, 2); cmdL.addWidget(self.btn_record, 3, 0, 1, 2)
        sidebar_layout.addWidget(cmd_box)

        log_box = QGroupBox("TERMINAL"); log_box.setObjectName("panel")
        logL = QVBoxLayout(log_box); logL.setContentsMargins(15,20,15,15)
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True); logL.addWidget(self.log_area)
        sidebar_layout.addWidget(log_box, 1)
        main_layout.addWidget(self.sidebar_widget)

        # ÁREA CENTRAL
        main_area_widget = QWidget(); main_area_layout = QVBoxLayout(main_area_widget)
        main_area_layout.setContentsMargins(0,0,0,0); main_area_layout.setSpacing(0)

        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #FFFFFF; border-bottom: 2px solid #CBD5E1;")
        
        shadow_tb = QGraphicsDropShadowEffect()
        shadow_tb.setBlurRadius(10); shadow_tb.setXOffset(0); shadow_tb.setYOffset(2); shadow_tb.setColor(QColor(0,0,0, 10))
        top_bar.setGraphicsEffect(shadow_tb)

        top_bar_layout = QHBoxLayout(top_bar); top_bar_layout.setContentsMargins(20, 10, 20, 10)
        self.btn_toggle_sidebar = QPushButton("☰ Menú Principal")
        self.btn_toggle_sidebar.setStyleSheet("QPushButton { background: transparent; color: #000000; border: none; font-size: 14px; font-weight: 800; } QPushButton:hover { color: #0EA5E9; }")
        self.btn_toggle_sidebar.clicked.connect(self.toggle_sidebar)
        top_bar_layout.addWidget(self.btn_toggle_sidebar); top_bar_layout.addStretch()
        main_area_layout.addWidget(top_bar)

        content_area = QWidget(); content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(30, 25, 30, 30); content_layout.setSpacing(20)

        self.rec_panel = QGroupBox()
        self.rec_panel.setStyleSheet("QGroupBox { background-color: #FFFFFF; border: 2px solid #EF4444; border-radius: 10px; }")
        recL = QHBoxLayout(self.rec_panel); recL.setContentsMargins(20, 20, 20, 20)
        self.lbl_rec_meta = QLabel("Preparando protocolo..."); self.lbl_rec_meta.setStyleSheet("font-size: 16px; font-weight: 900; color: #000000;")
        self.lbl_countdown = QLabel(""); self.lbl_countdown.setStyleSheet("font-size: 18px; font-weight: 900; color: #EF4444;")
        self.lbl_biopac_status = QLabel("TRIG: LOW"); self.lbl_biopac_status.setStyleSheet("color: #000000; font-family: Consolas; font-weight: 900; padding: 6px 12px; border: 2px solid #CBD5E1; border-radius: 6px;")
        self.pbar = QProgressBar(); self.lbl_pct = QLabel("0%"); self.lbl_pct.setStyleSheet("font-family: Consolas; font-weight: 900; color: #000000;")
        self.btn_cancel_rec = QPushButton("✕"); self.btn_cancel_rec.setObjectName("btnDanger"); self.btn_cancel_rec.setFixedSize(40, 40); self.btn_cancel_rec.clicked.connect(self.cancel_recording)
        
        rec_dot = QLabel("⚫ REC"); rec_dot.setStyleSheet("color:#EF4444; font-weight:900; font-size:18px;")
        recL.addWidget(rec_dot); recL.addWidget(self.lbl_rec_meta, 1); recL.addWidget(self.lbl_countdown)
        recL.addWidget(self.lbl_biopac_status); recL.addWidget(self.pbar); recL.addWidget(self.lbl_pct); recL.addWidget(self.btn_cancel_rec)
        self.rec_panel.setVisible(False); content_layout.addWidget(self.rec_panel)

        self.grid_container = QWidget(); self.grid = QGridLayout(self.grid_container)
        self.grid.setContentsMargins(0,0,0,0); self.grid.setSpacing(25)
        
        empty_widget = QWidget(); empty_lay = QVBoxLayout(empty_widget)
        empty_icon = QLabel("📡"); empty_icon.setFont(QFont("Segoe UI", 48)); empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter); empty_icon.setStyleSheet("color: #94A3B8;")
        self.empty_state = QLabel("Esperando telemetría de sensores...\nConecte un puerto y presione 'MONITOREAR'")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter); self.empty_state.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold)); self.empty_state.setStyleSheet("color: #475569;")
        empty_lay.addStretch(); empty_lay.addWidget(empty_icon); empty_lay.addWidget(self.empty_state); empty_lay.addStretch()
        self.grid.addWidget(empty_widget, 0, 0)

        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True); self.scroll_area.setWidget(self.grid_container)
        content_layout.addWidget(self.scroll_area, 1)

        main_area_layout.addWidget(content_area, 1); main_layout.addWidget(main_area_widget, 1)
        self.update_button_states(); self.refresh_ports()

    def toggle_sidebar(self):
        width = self.sidebar_widget.width()
        target = 0 if width > 0 else 350
        self.animation1 = QPropertyAnimation(self.sidebar_widget, b"minimumWidth")
        self.animation1.setDuration(250); self.animation1.setStartValue(width); self.animation1.setEndValue(target)
        self.animation1.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.animation2 = QPropertyAnimation(self.sidebar_widget, b"maximumWidth")
        self.animation2.setDuration(250); self.animation2.setStartValue(width); self.animation2.setEndValue(target)
        self.animation2.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.animation1.start(); self.animation2.start()

    def log_message(self, message: str, level: str = "INFO"):
        color = {"INFO": "#000000", "WARN": "#B45309", "ERROR": "#B91C1C", "DEBUG": "#0369A1"}.get(level, "#000000")
        self.log_area.append(f'<span style="color:#64748B;">[{datetime.now().strftime("%H:%M:%S")}]</span> <strong style="color:{color};">[{level}]</strong> {message}')
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def toggle_filter(self, checked):
        if not SCIPY_AVAILABLE: self.log_message("Scipy no instalada.", "ERROR"); self.btn_filter.setChecked(False); return
        for card in self.cards.values(): card.set_filter_mode(checked)

    def update_button_states(self):
        b = self.rec_active or self.is_calibrating; s = self.timer.isActive()
        self.btn_conn.setEnabled(not b); self.btn_refresh.setEnabled(not self.connected and not b)
        self.btn_start.setEnabled(self.connected and not b and not s); self.btn_stop.setEnabled(self.connected and not b and s)
        self.btn_calib.setEnabled(self.connected and not b); self.btn_record.setEnabled(self.connected and not b)

    def refresh_ports(self):
        self.cb_port.clear()
        for p in QSerialPortInfo.availablePorts(): self.cb_port.addItem(f"{p.portName()} — {p.description()}", p.portName())

    def toggle_conn(self):
        if not self.connected:
            p = self.cb_port.currentData()
            if not p: return
            self._clear_grid(); self.slave_store.clear()
            if self.io.open(p):
                self.connected = True
                self.btn_conn.setText("Desconectar"); self.btn_conn.setObjectName("btnDanger")
                self.btn_conn.style().unpolish(self.btn_conn); self.btn_conn.style().polish(self.btn_conn)
                self.lbl_status.setText(f"<span style='color:#10B981;'>●</span> ONLINE: {p}")
        else:
            if self.rec_active or self.is_calibrating: return
            self.io.write_cmd('b'); self.send_cmd('0'); self.io.close()
            self.connected = False; self._clear_grid(); self.slave_store.clear()
            self.btn_conn.setText("Conectar"); self.btn_conn.setObjectName("btnPrimary")
            self.btn_conn.style().unpolish(self.btn_conn); self.btn_conn.style().polish(self.btn_conn)
            self.lbl_status.setText("<span style='color:#9CA3AF;'>●</span> Desconectado")
        self.update_button_states()

    def send_cmd(self, cmd: str):
        if not self.connected: return
        self.io.write_cmd(cmd)
        if cmd == '1': self._clear_grid(); self.slave_store.clear(); self.timer.start()
        elif cmd == '0': self.timer.stop()
        self.update_button_states()

    @pyqtSlot(str)
    def _on_line(self, line: str):
        if self.is_calibrating: return
        try:
            parts = line.split(',')
            if len(parts) != 12: return
            sid, ts = parts[0], int(parts[1])
            red, ir = int(parts[2]), int(parts[3])
            ax, ay, az = int(parts[4]), int(parts[5]), int(parts[6])
            gx, gy, gz = int(parts[7]), int(parts[8]), int(parts[9])
            fs, battery_mv = float(parts[10]), int(parts[11])
        except Exception: return

        buf = self.slave_store.get(sid)
        if buf is None:
            buf = SlaveBuffer(); self.slave_store[sid] = buf
            card = SlaveCard(sid); card.set_filter_mode(self.btn_filter.isChecked())
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.cards[sid] = card; self.order.append(sid); self._reflow()
              
        buf.append(ts, red, ir, ax, ay, az, gx, gy, gz, fs, battery_mv)

        if self.rec_active:
            if sid not in self.first_ts: self.first_ts[sid] = ts
            if not self.participants_frozen: self.participants.add(sid)
            if self.participants_frozen and sid in self.participants and self.align_us is not None and ts >= self.align_us:
                self.drop_left.setdefault(sid, START_DROP_SAMPLES); self.count.setdefault(sid, 0); self.saved.setdefault(sid, [])
                if self.drop_left[sid] > 0: self.drop_left[sid] -= 1
                else:
                    if not self.biopac_pulse_fired:
                        self.io.write_cmd('B'); self.biopac_pulse_fired = True; self.rec_pulse_ts_us = ts 
                        self.lbl_biopac_status.setText("TRIG: HIGH")
                        self.lbl_biopac_status.setStyleSheet("color: #000000; background-color: #10B981; border: 2px solid #059669; padding: 6px 12px; border-radius: 6px; font-weight: 900;")
                    if self.count[sid] < self.rec_target_n:
                        self.saved[sid].append((ts, red, ir, ax, ay, az, gx, gy, gz, fs, ts, battery_mv))
                        self.count[sid] += 1

    def _reflow(self):
        if not self.order: self.grid.addWidget(self.empty_state.parentWidget(), 0, 0); return
        self.empty_state.parentWidget().setVisible(False)
        cols = 1 if len(self.order) <= 2 else 2
        for sid, w in self.cards.items():
            try: self.grid.removeWidget(w)
            except RuntimeError: pass
        row = col = max_r = 0
        for sid in self.order:
            if sid in self.cards:
                self.grid.addWidget(self.cards[sid], row, col)
                max_r = row; col += 1
                if col >= cols: col = 0; row += 1
        for c in range(cols): self.grid.setColumnStretch(c, 1)
        for r in range(max_r + 1): self.grid.setRowStretch(r, 1)

    def _clear_grid(self):
        for sid, w in list(self.cards.items()): self.grid.removeWidget(w); w.deleteLater()
        self.cards.clear(); self.order.clear(); self.empty_state.parentWidget().setVisible(True)

    def refresh_gui(self):
        pulse_time_us = self.rec_pulse_ts_us if (self.rec_active and self.biopac_pulse_fired) else None
        self.frame_counter += 1
        for sid, buf in self.slave_store.items():
            if not (card := self.cards.get(sid)): continue
            card.update_heartbeat(buf.last_rx); card.update_battery(buf.battery_mv)
            if buf.dirty and (snap := buf.snapshot()):
                if len(buf.ax_hist) > 0:
                    ax_f, ay_f, az_f = np.array(buf.ax_hist, dtype=np.float64), np.array(buf.ay_hist, dtype=np.float64), np.array(buf.az_hist, dtype=np.float64)
                    imu_norm = np.sqrt(ax_f**2 + ay_f**2 + az_f**2)
                else: imu_norm = None

                card.update_from_snapshot(snap, pulse_time_us, imu_acc_norm=imu_norm)
                if self.frame_counter % 5 == 0:
                    card.update_imu_text(buf.ax_hist, buf.ay_hist, buf.az_hist, buf.gx_hist, buf.gy_hist, buf.gz_hist)

    def open_record_dialog(self):
        if not self.connected or self.rec_active or self.is_calibrating: return
        if not self.slave_store: return QMessageBox.warning(self, "Atención", "No hay dispositivos conectados para grabar.")
        dlg = RecordConfigDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            su, na, st, du = dlg.values()
            if su and na: self.start_recording(su, na, st, du)

    def start_recording(self, subj:str, name:str, stage:str, dur_s:int):
        self.is_calibrating = self.rec_active = True
        self.participants_to_calibrate = set(self.slave_store.keys()); self.calibrated_slaves.clear()
        if not self.participants_to_calibrate: self.is_calibrating = self.rec_active = False; return
        self.update_button_states()
        self.rec_meta = {"subject": subj, "name": name, "stage": stage}
        self.rec_duration_s = float(dur_s); self.rec_target_n = int(dur_s * TARGET_FS_HZ)
        self.biopac_pulse_fired = False; self.rec_pulse_ts_us = None
        self.participants.clear(); self.participants_frozen = False
        self.first_ts.clear(); self.align_us = None; self.count.clear(); self.saved.clear(); self.drop_left.clear()
        self.lbl_rec_meta.setText(f"Sujeto {subj}: {name} | {stage} | {dur_s}s"); self.rec_panel.setVisible(True)
        self.send_cmd('0'); self.send_cmd('3')
        self.calib_timeout_timer.start(CALIBRATION_TIMEOUT_MS)

    @pyqtSlot(str)
    def _on_system_message(self, msg: str):
        if not self.is_calibrating: return
        p = msg.split(',')
        if len(p) == 2 and p[0] == "CAL_OK" and p[1].strip() in self.participants_to_calibrate:
            sid = p[1].strip(); self.participants_to_calibrate.remove(sid); self.calibrated_slaves.add(sid)
            if not self.participants_to_calibrate:
                self.calib_timeout_timer.stop(); self.is_calibrating = False
                self.countdown_value = 3; self.countdown_timer.start()

    @pyqtSlot()
    def _on_calib_timeout(self):
        if self.is_calibrating: self.cancel_recording()

    def _on_countdown_tick(self):
        self.countdown_value -= 1
        if self.countdown_value <= 0:
            self.countdown_timer.stop()
            self._clear_grid(); self.slave_store.clear()
            self.io.write_cmd('1'); self.timer.start(); self.update_button_states()
            self.join_start_time = time.monotonic(); self.join_deadline = self.join_start_time + JOIN_GRACE_SECONDS
            self.progress_timer.start()

    def _on_progress_tick(self):
        if not self.rec_active or self.is_calibrating: return
        now = time.monotonic()
        if not self.participants_frozen:
            if now > self.join_deadline:
                self.participants_frozen = True
                if self.participants: self.align_us = max(self.first_ts.get(s, 0) for s in self.participants)
                else: self.finish_recording(); return
        if self.participants_frozen and self.biopac_pulse_fired:
            min_count = min(self.count.get(s, 0) for s in self.participants)
            pct = int(min(100, (min_count / max(1, self.rec_target_n)) * 100))
            self.pbar.setValue(pct); self.lbl_pct.setText(f"{pct}%")
            if all(self.count.get(s, 0) >= self.rec_target_n for s in self.participants): self.finish_recording(); return
            elif now - self.join_deadline > self.rec_duration_s + MAX_WAIT_EXTRA_S: self.finish_recording(True)

    def cancel_recording(self):
        if not self.rec_active and not self.is_calibrating: return
        self.calib_timeout_timer.stop(); self.io.write_cmd('b')
        self.lbl_biopac_status.setText("TRIG: LOW")
        self.lbl_biopac_status.setStyleSheet("color: #000000; font-family: Consolas; font-weight: 900; padding: 6px 12px; border: 2px solid #CBD5E1; border-radius: 6px;")
        self.rec_active = self.is_calibrating = False
        self.progress_timer.stop(); self.countdown_timer.stop()
        self.rec_panel.setVisible(False)
        if self.connected: self.send_cmd('0')
        self.update_button_states(); self._clear_grid(); self.slave_store.clear()

    def finish_recording(self, force=False):
        self.io.write_cmd('b')
        self.lbl_biopac_status.setText("TRIG: LOW")
        self.lbl_biopac_status.setStyleSheet("color: #000000; font-family: Consolas; font-weight: 900; padding: 6px 12px; border: 2px solid #CBD5E1; border-radius: 6px;")
        self.rec_active = self.is_calibrating = False
        self.progress_timer.stop(); self.calib_timeout_timer.stop()
        if not self.participants: return self.cancel_recording()
          
        t_sec_uniform = np.arange(self.rec_target_n, dtype=np.float64) / TARGET_FS_HZ
        recorded_segments = {}

        for sid in self.participants:
            rows = self.saved.get(sid, [])
            if len(rows) == 0: continue
            if len(rows) < self.rec_target_n: rows = rows + [rows[-1]] * (self.rec_target_n - len(rows))
            ir  = np.fromiter((r[2] for r in rows[:self.rec_target_n]), dtype=np.int32, count=self.rec_target_n)
            red = np.fromiter((r[1] for r in rows[:self.rec_target_n]), dtype=np.int32, count=self.rec_target_n)
            ylims = None
            if ir.size and red.size:
                y_all = np.concatenate((ir.astype(np.float64), red.astype(np.float64)))
                p1, p99 = np.percentile(y_all, [1, 99])
                if p99 > p1: ylims = (p1 - 0.1*(p99-p1), p99 + 0.1*(p99-p1))
            recorded_segments[sid] = {"t_sec": t_sec_uniform, "ir": ir, "red": red, "ylims": ylims}

        dlg = RecordPreviewDialog(self, recorded_segments, duration_s=self.rec_duration_s)
        if dlg.exec() == QDialog.DialogCode.Accepted: self._export_csvs()

        self.rec_panel.setVisible(False)
        if self.connected: self.send_cmd('0')
        self.update_button_states(); self._clear_grid(); self.slave_store.clear()

    def _export_csvs(self):
        folder = QFileDialog.getExistingDirectory(self, "Guardar CSV Unificado")
        if not folder: return
        ts_label = datetime.now().strftime("%Y%m%d_%H%M%S")
        subj = self.rec_meta.get("subject","NA")
        name = self.rec_meta.get("name","NA").replace(" ", "_")
        stage = self.rec_meta.get("stage","NA").replace(" ", "")
        fname = f"{ts_label}_Subj{subj}_{name}_{stage}_MERGED.csv"
        path = os.path.join(folder, fname)
        step_us = int(round(1_000_000 / TARGET_FS_HZ))
        sorted_sids = sorted(list(self.participants))
        base_cols = ["SlaveID", "Timestamp_us", "Red", "IR", "Ax", "Ay", "Az", "Gx", "Gy", "Gz", "Instant_Fs_Hz", "DeviceTimestamp_us", "Battery_mV", "Battery_pct"]
        
        final_headers = []
        for sid in sorted_sids:
            raw_loc = SLAVE_LOCATIONS.get(str(sid), SLAVE_LOCATIONS.get(f"Slave{sid}", "General"))
            clean_loc = raw_loc.replace(" ", "").replace("í", "i").replace("ñ", "n")
            final_headers.extend([f"{col}_{sid}_{clean_loc}" for col in base_cols])
        
        try:
            with open(path, "w", newline="") as f:
                w = csv.writer(f); w.writerow(final_headers)
                for i in range(self.rec_target_n):
                    full_row = []
                    for sid in sorted_sids:
                        rows = self.saved.get(sid, [])
                        if i < len(rows):
                            ts_dev, red, ir, ax, ay, az, gx, gy, gz, fs, ts_original, battery_mv = rows[i]
                            full_row.extend([sid, i * step_us, red, ir, ax, ay, az, gx, gy, gz, f"{fs:.6f}", ts_original, battery_mv, lipo_voltage_to_percent(battery_mv / 1000.0) if battery_mv > 0 else "NA"])
                        else: full_row.extend(["NA"] * len(base_cols))
                    w.writerow(full_row)
            QMessageBox.information(self, "Éxito", f"Datos unificados guardados en:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{e}")

    def closeEvent(self, e):
        self.timer.stop(); self.progress_timer.stop(); self.countdown_timer.stop(); self.calib_timeout_timer.stop()
        if self.connected:
            try: self.io.write_cmd('b'); self.io.write_cmd('0')
            except Exception: pass
            self.io.close()
        e.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())