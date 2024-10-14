"""
Công cụ gửi và nhận hồng ngoại cho Raspberry Pi, công cụ phân tích dữ liệu
Indoor Corgi, https://www.indoorcorgielec.com
GitHub: https://github.com/IndoorCorgi/cgir
Phiên bản 1.2

Yêu cầu môi trường:
1) Raspberry Pi OS, Python3
2) Dịch vụ pigpio
  sudo systemctl start pigpiod
  sudo systemctl enable pigpiod
3) Các bo mở rộng hỗ trợ gửi và nhận hồng ngoại
  RPZ-PIRS https://www.indoorcorgielec.com/products/rpz-pirs/
  RPZ-IR-Sensor https://www.indoorcorgielec.com/products/rpz-ir-sensor/
  RPi TPH Monitor https://www.indoorcorgielec.com/products/rpi-tph-monitor-rev2/

Usage:
  cgir rec  [-c <path>] [-g <gpio>] <code_name>...
  cgir send [-c <path>] [-g <gpio>] [-w <wait>] <code_name>...
  cgir list [-c <path>] 
  cgir del  [-c <path>] <code_name>...
  cgir dec  [-c <path>] -f <file> <code_name>
  cgir enc  [-c <path>] -f <file> <code_name>
  cgir -h --help

Options:
  rec          Nhận tín hiệu hồng ngoại và lưu với tên <code_name>.
  send         Gửi tín hiệu hồng ngoại đã lưu với tên <code_name>.
  list         Hiển thị danh sách các tín hiệu hồng ngoại đã lưu.
  del          Xóa tín hiệu hồng ngoại với tên <code_name>.
  dec          Giải mã tín hiệu hồng ngoại đã lưu, chuyển đổi định dạng và lưu vào file <file> (định dạng JSON).
  enc          Tạo tín hiệu hồng ngoại từ file <file> (định dạng JSON) và lưu với tên <code_name>.
  <code_name>  Tên của mã hồng ngoại. Có thể chỉ định nhiều tên với các lệnh rec, send, del.
  -c <path>    Tên hoặc đường dẫn của file lưu trữ mã hồng ngoại. Mặc định là codes.json.
  -g <gpio>    Số GPIO dùng để gửi/nhận. Mặc định gửi là GPIO 13, nhận là GPIO 4.
  -w <wait>    Khoảng thời gian (giây) giữa các mã khi gửi. Mặc định là 1.
  -f <file>    Tên file.
  -h --help    Hiển thị trợ giúp.
"""

from docopt import docopt
import time
import json
from infrared import *

def cli():
  """
  Chạy công cụ dòng lệnh
  """
  args = docopt(__doc__)
  ir = Infrared()

  # Đọc mã hồng ngoại đã lưu
  if args['-c'] != None:
    ir.codes_path = args['-c']
  ir.load_codes()

  # Nhận tín hiệu hồng ngoại
  if args['rec']:
    # Cài đặt GPIO
    if args['-g'] != None:
      i = check_gpio(args['-g'])
      if i == -1:
        print('Số GPIO được chỉ định bằng -g không hợp lệ hoặc ngoài phạm vi.')
        return
      else:
        ir.gpio_rec = i

    for cname in args['<code_name>']:
      print('------------------------------------')
      print('Đang nhận tín hiệu hồng ngoại "{}"... Hãy hướng điều khiển từ xa về phía máy thu.'.format(cname))
      result, code = ir.record()  # Bắt đầu nhận tín hiệu
      if result == REC_SUCCESS:
        print('\nMã nhận được')
        print(code)  # Hiển thị mã đã nhận

        ir_format, frames = ir.decode(code)
        print()
        print(ir.frames2str(ir_format, frames))  # Hiển thị kết quả đã giải mã

        ir.codes[cname] = code
        if ir.save_codes():
          print('\nMã hồng ngoại "{}" đã được lưu.\n'.format(cname))
        else:
          print('\nKhông thể lưu mã hồng ngoại. Hãy kiểm tra quyền truy cập của file {}.'.format(ir.codes_path))
      elif result == REC_NO_DATA:
        print('Nhận thất bại. Không có dữ liệu.\n')
      elif result == REC_SHORT:
        print('Nhận thất bại. Dữ liệu không hợp lệ.\n')
      elif result == REC_ERR_PIGPIO:
        print('Nhận thất bại. Không thể kết nối với pigpio.\n')
        return

  # Gửi tín hiệu hồng ngoại
  if args['send']:
    # Cài đặt GPIO
    if args['-g'] != None:
      i = check_gpio(args['-g'])
      if i == -1:
        print('Số GPIO được chỉ định bằng -g không hợp lệ hoặc ngoài phạm vi.')
        return
      else:
        ir.gpio_send = i

    # Thời gian chờ giữa các mã
    wait = 1
    if args['-w'] != None:
      if args['-w'].isdecimal():
        wait = int(args['-w'])
        if wait < 0 or wait > 1000:
          print('Thời gian chờ được chỉ định bằng -w không hợp lệ.')
          return
      else:
        print('Thời gian chờ được chỉ định bằng -w không hợp lệ.')
        return

    first_time = True
    for cname in args['<code_name>']:
      if not first_time:
        time.sleep(wait)
      if cname in ir.codes:
        print('Đang gửi mã hồng ngoại "{}"...'.format(cname))
        if not ir.send(ir.codes[cname]):
          print('Gửi thất bại. Không thể kết nối với pigpio.\n')
          return
      else:
        print('Không tìm thấy mã hồng ngoại "{}".'.format(cname))
      first_time = False

  # Hiển thị danh sách mã đã lưu
  if args['list']:
    if len(ir.codes) == 0:
      print('Không có mã hồng ngoại nào được lưu.')
    else:
      print('Danh sách mã hồng ngoại đã lưu')
      for key in ir.codes:
        print(key)

  # Xóa mã đã lưu
  if args['del']:
    for cname in args['<code_name>']:
      if cname in ir.codes:
        print('Đã xóa mã hồng ngoại "{}".'.format(cname))
        ir.codes.pop(cname)
        ir.save_codes()
      else:
        print('Không tìm thấy mã hồng ngoại "{}".'.format(cname))

  # Giải mã mã hồng ngoại
  if args['dec']:
    cname = args['<code_name>'][0]
    if cname not in ir.codes:
      print('Không tìm thấy mã hồng ngoại "{}".'.format(cname))
      return

    print('Đang giải mã mã hồng ngoại "{}"\n'.format(cname))
    code = ir.codes[cname]

    print('Mã')
    print(code)
    print()
    ir_format, frames = ir.decode(code)
    print(ir.frames2str(ir_format, frames))  # Hiển thị kết quả đã giải mã

    if ir_format == FORMAT_UNKNOWN:
      print('Định dạng không hỗ trợ hoặc không xác định. Dừng mà không lưu vào file.')
      return

    # Chuẩn bị lưu vào file
    obj = {}
    obj['format'] = ir_format
    obj['data'] = frames

    try:
      with open(args['-f'], 'w') as f:
        f.write(json.dumps(obj, indent=2, ensure_ascii=False))
        print('\nĐã lưu vào file "{}".'.format(args['-f']))
    except:
      print('\nLưu vào file thất bại.')

  # Mã hóa mã hồng ngoại
  if args['enc']:
    try:
      with open(args['-f'], 'r') as f:
        obj = json.load(f)
    except:
      print('\nĐọc file "{}" thất bại.'.format(args['-f']))
      return

    # Kiểm tra xem định dạng và dữ liệu có tồn tại không
    if not ('format' in obj and 'data' in obj):
      print('\nKhông tìm thấy định dạng và dữ liệu trong file "{}".'.format(args['-f']))
      return

    if obj['format'] != FORMAT_AEHA and obj['format'] != FORMAT_NEC and obj['format'] != FORMAT_SONY:
      print('Định dạng không hỗ trợ hoặc không xác định.')
      return

    code = ir.encode(obj['format'], obj['data'])
    if len(code) == 0:
      print('Mã hóa thất bại.')
      return

    print('Đã mã hóa file "{}"\n'.format(args['-f']))
    print(code)
    cname = args['<code_name>'][0]

    ir.codes[cname] = code
    if ir.save_codes():
      print('\nĐã lưu mã hồng ngoại "{}".\n'.format(cname))
    else:
      print('\nKhông thể lưu mã hồng ngoại. Hãy kiểm tra quyền truy cập của file {}.'.format(ir.codes_path))
      
    def check_gpio(gpio_str):
        if gpio_str.isdecimal():
            gpio = int(gpio_str)
        if gpio >= 0 and gpio <= 27:
            return gpio
        return -1
