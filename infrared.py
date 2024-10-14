import pigpio
import time
import json

# Định nghĩa các định dạng IR
FORMAT_UNKNOWN = 0  # Định dạng không xác định
FORMAT_AEHA = 1     # Định dạng AEHA
FORMAT_NEC = 2      # Định dạng NEC
FORMAT_SONY = 3     # Định dạng SONY

# Trạng thái khi ghi nhận tín hiệu IR
REC_SUCCESS = 0    # Ghi nhận thành công
REC_NO_DATA = 1    # Không có dữ liệu
REC_SHORT = 2      # Tín hiệu quá ngắn
REC_ERR_PIGPIO = 3 # Lỗi kết nối với pigpio

# Các khoảng thời gian (micro giây) cho từng định dạng
_T_MAX_GAP = 10000         # Khoảng cách tối đa giữa các xung
_T_AEHA = 425              # Thời gian cho 1 xung AEHA
_T_NEC = 562               # Thời gian cho 1 xung NEC
_T_NEC_REPEAT = 2250       # Thời gian xung lặp lại NEC
_T_SONY = 600              # Thời gian cho 1 xung SONY
_T_TOLERANCE = 0.35        # Dung sai thời gian (± 35%)

class Infrared:
    def __init__(self, gpio_send=13, gpio_rec=4, codes_path='codes.json'):
        """
        Khởi tạo đối tượng IR với chân GPIO gửi và nhận.
        gpio_send: GPIO để gửi tín hiệu hồng ngoại (mặc định là 13)
        gpio_rec: GPIO để nhận tín hiệu hồng ngoại (mặc định là 4)
        codes_path: Đường dẫn đến tệp JSON chứa mã IR đã lưu
        """
        self.gpio_send = gpio_send
        self.gpio_rec = gpio_rec
        self.codes_path = codes_path
        self.codes = {}

        try:
            with open(self.codes_path, 'r') as f:
                self.codes = json.load(f)  # Tải mã IR từ file JSON
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Nếu không có file hoặc lỗi định dạng, bỏ qua

        # Kết nối với pigpio daemon
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise OSError("Không thể kết nối pigpio")
        
        self.pi.set_mode(self.gpio_send, pigpio.OUTPUT)  # Đặt GPIO gửi là đầu ra
        self.pi.set_mode(self.gpio_rec, pigpio.INPUT)    # Đặt GPIO nhận là đầu vào
        self.wave = []  # Mảng chứa dữ liệu sóng

    def send(self, frames, fmt=FORMAT_AEHA):
        """
        Gửi tín hiệu hồng ngoại (IR).
        frames: Dữ liệu khung cần gửi.
        fmt: Định dạng của khung (AEHA, NEC, SONY).
        """
        # Mã hóa khung dữ liệu thành tín hiệu sóng
        self.wave = self.encode(frames, fmt)
        self.pi.wave_clear()  # Xóa các sóng đã lưu trước đó
        self.pi.wave_add_generic(self.wave)  # Thêm sóng mới
        wave_id = self.pi.wave_create()  # Tạo sóng mới
        if wave_id >= 0:
            self.pi.wave_send_once(wave_id)  # Gửi sóng một lần
            while self.pi.wave_tx_busy():  # Chờ cho đến khi quá trình gửi hoàn thành
                time.sleep(0.001)
            self.pi.wave_delete(wave_id)  # Xóa sóng sau khi gửi xong

    def record(self, timeout=5000):
        """
        Ghi nhận tín hiệu hồng ngoại (IR) trong một khoảng thời gian xác định.
        timeout: Thời gian chờ tối đa (mili giây).
        """
        self.pi.set_watchdog(self.gpio_rec, timeout // 1000)  # Thiết lập watchdog cho GPIO nhận
        self.data = []  # Mảng chứa dữ liệu nhận được

        # Bắt đầu ghi nhận tín hiệu
        cb = self.pi.callback(self.gpio_rec, pigpio.EITHER_EDGE, self._call_back)
        start = time.time()  # Lưu thời gian bắt đầu

        while (time.time() - start) * 1000 < timeout:
            if len(self.data) > 1 and (self.data[-1][0] > _T_MAX_GAP):
                break  # Ngừng nếu không còn tín hiệu mới

            time.sleep(0.1)

        self.pi.set_watchdog(self.gpio_rec, 0)  # Hủy watchdog

        cb.cancel()  # Hủy bỏ callback

        if len(self.data) < 2:
            return REC_NO_DATA, []  # Không có dữ liệu được nhận

        if (self.data[-1][0] <= _T_MAX_GAP) or (self.data[-1][1] == pigpio.TIMEOUT):
            return REC_SHORT, []  # Dữ liệu quá ngắn

        return REC_SUCCESS, self.data  # Ghi nhận thành công

    def encode(self, frames, fmt):
        """
        Mã hóa khung dữ liệu thành tín hiệu sóng (Mark/Space) dựa trên định dạng.
        frames: Dữ liệu khung cần mã hóa.
        fmt: Định dạng của khung (AEHA, NEC, SONY).
        """
        wave = []  # Mảng chứa dữ liệu sóng
        if fmt == FORMAT_AEHA:
            # Mã hóa cho định dạng AEHA
            for i in frames:
                mark = _T_AEHA if i == 1 else _T_AEHA // 3
                wave.append(pigpio.pulse(1 << self.gpio_send, 0, mark))
                wave.append(pigpio.pulse(0, 1 << self.gpio_send, _T_AEHA))
        elif fmt == FORMAT_NEC:
            # Mã hóa cho định dạng NEC
            for i in frames:
                mark = _T_NEC if i == 1 else _T_NEC // 2
                wave.append(pigpio.pulse(1 << self.gpio_send, 0, mark))
                wave.append(pigpio.pulse(0, 1 << self.gpio_send, _T_NEC))
        elif fmt == FORMAT_SONY:
            # Mã hóa cho định dạng SONY
            for i in frames:
                mark = _T_SONY if i == 1 else _T_SONY // 2
                wave.append(pigpio.pulse(1 << self.gpio_send, 0, mark))
                wave.append(pigpio.pulse(0, 1 << self.gpio_send, _T_SONY))
        return wave  # Trả về sóng đã mã hóa
