from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QBrush, QColor, QIcon, QPen
from PyQt5.QtWidgets import QMessageBox

from urh import constants
from urh.controller.SendRecvDialogController import SendRecvDialogController
from urh.dev.VirtualDevice import VirtualDevice, Mode
from urh.signalprocessing.Signal import Signal
from urh.ui.painting.SignalSceneManager import SignalSceneManager
from urh.util import FileOperator


class SendDialogController(SendRecvDialogController):
    def __init__(self, project_manager, modulated_data, modulation_msg_indices=None, parent=None, testing_mode=False):
        super().__init__(project_manager, is_tx=True, parent=parent, testing_mode=testing_mode)

        self.graphics_view = self.ui.graphicsViewSend
        self.ui.stackedWidget.setCurrentWidget(self.ui.page_send)
        self.hide_receive_ui_items()

        self.ui.btnStart.setIcon(QIcon.fromTheme("media-playback-start"))
        self.setWindowTitle("Send Signal")
        self.setWindowIcon(QIcon.fromTheme("media-playback-start"))
        self.ui.btnStart.setToolTip("Send data")
        self.ui.btnStop.setToolTip("Stop sending")
        self.device_is_sending = False
        self.modulation_msg_indices = modulation_msg_indices

        if self.modulation_msg_indices is not None:
            self.ui.progressBarMessage.setMaximum(len(self.modulation_msg_indices))

        if modulated_data is not None:
            # modulated_data is none in continuous send mode
            self.ui.progressBarSample.setMaximum(len(modulated_data))
            samp_rate = self.ui.spinBoxSampleRate.value()
            signal = Signal.from_samples(modulated_data, "Modulated Preview", samp_rate)
            self.scene_manager = SignalSceneManager(signal, parent=self)
            self.send_indicator = self.scene_manager.scene.addRect(0, -2, 0, 4,
                                                                   QPen(QColor(Qt.transparent), Qt.FlatCap),
                                                                   QBrush(constants.SEND_INDICATOR_COLOR))
            self.send_indicator.stackBefore(self.scene_manager.scene.selection_area)
            self.scene_manager.init_scene()
            self.graphics_view.set_signal(signal)
            self.graphics_view.sample_rate = samp_rate

            self.init_device()

            self.graphics_view.setScene(self.scene_manager.scene)
            self.graphics_view.scene_manager = self.scene_manager

            self.create_connects()

    def create_connects(self):
        super().create_connects()

        self.graphics_view.save_as_clicked.connect(self.on_graphics_view_save_as_clicked)
        self.scene_manager.signal.data_edited.connect(self.on_signal_data_edited)

    def _update_send_indicator(self, width: int):
        y, h = self.ui.graphicsViewSend.view_rect().y(), self.ui.graphicsViewSend.view_rect().height()
        self.send_indicator.setRect(0, y - h, width, 2 * h + abs(y))

    def set_current_message_progress_bar_value(self, current_sample: int):
        if self.modulation_msg_indices is not None:
            msg_index = next((i for i, sample in enumerate(self.modulation_msg_indices) if sample >= current_sample),
                             len(self.modulation_msg_indices))
            self.ui.progressBarMessage.setValue(msg_index + 1)

    def update_view(self):
        if super().update_view():
            self._update_send_indicator(self.device.current_index)
            self.ui.progressBarSample.setValue(self.device.current_index)
            self.set_current_message_progress_bar_value(self.device.current_index)

            if not self.device.sending_finished:
                self.ui.lblCurrentRepeatValue.setText(str(self.device.current_iteration + 1))
            else:
                self.ui.lblCurrentRepeatValue.setText("Done")

    def init_device(self):
        device_name = self.ui.cbDevice.currentText()
        num_repeats = self.ui.spinBoxNRepeat.value()
        sts = self.scene_manager.signal._fulldata

        self.device = VirtualDevice(self.backend_handler, device_name, Mode.send, samples_to_send=sts,
                                    device_ip="192.168.10.2", sending_repeats=num_repeats, parent=self)
        self._create_device_connects()

    @pyqtSlot()
    def on_graphics_view_save_as_clicked(self):
        filename = FileOperator.get_save_file_name("signal.complex")
        if filename:
            try:
                self.scene_manager.signal.save_as(filename)
            except Exception as e:
                QMessageBox.critical(self, self.tr("Error saving signal"), e.args[0])

    @pyqtSlot()
    def on_signal_data_edited(self):
        signal = self.scene_manager.signal
        self.ui.progressBarSample.setMaximum(signal.num_samples)
        self.device.samples_to_send = signal.data
        self.scene_manager.init_scene()
        self.ui.graphicsViewSend.redraw_view()

    @pyqtSlot()
    def on_start_clicked(self):
        super().on_start_clicked()
        if self.ui.progressBarSample.value() >= self.ui.progressBarSample.maximum() - 1:
            self.on_clear_clicked()

        if self.device_is_sending:
            self.device.stop("Sending paused by user")
        else:
            self.device.start()

    @pyqtSlot()
    def on_stop_clicked(self):
        self.device.stop("Stopped receiving: Stop button clicked")
        super().on_stop_clicked()
        self.on_clear_clicked()

    @pyqtSlot()
    def on_device_stopped(self):
        super().on_device_stopped()
        self.ui.btnStart.setIcon(QIcon.fromTheme("media-playback-start"))
        self.ui.btnStart.setToolTip("Start sending")
        self.device_is_sending = False

    @pyqtSlot()
    def on_device_started(self):
        super().on_device_started()
        self.device_is_sending = True
        self.ui.btnStart.setEnabled(True)
        self.ui.btnStart.setIcon(QIcon.fromTheme("media-playback-pause"))
        self.set_device_ui_items_enabled(False)

    @pyqtSlot()
    def on_clear_clicked(self):
        self._update_send_indicator(0)
        self.reset()
