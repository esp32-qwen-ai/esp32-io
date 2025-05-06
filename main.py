from machine import I2S
from machine import Pin
from lib import happy
import time
import socket
import struct

AUDIO_SAMPLE_RATE = 24000
MIC_SAMPLE_RATE = 16000
FORMAT = I2S.MONO
BITS = 16
RECORD_TIME_IN_SECONDS = 5
RECORD_BUF_SIZE = RECORD_TIME_IN_SECONDS * MIC_SAMPLE_RATE * BITS // 8

SOCKET_BUF_SIZE = 1024

class AudioPlayer:
    def __init__(self, sck_pin, ws_pin, sd_pin):
        self.sck_pin = sck_pin
        self.ws_pin = ws_pin
        self.sd_pin = sd_pin
        # self.audio = I2S(0, sck=self.sck_pin, ws=self.ws_pin, sd=self.sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO, rate=44100, ibuf=20000)
        self.audio = I2S(0, sck=self.sck_pin, ws=self.ws_pin, sd=self.sd_pin, mode=I2S.TX, bits=BITS, format=FORMAT, rate=AUDIO_SAMPLE_RATE, ibuf=32768)

    def __del__(self):
        del self.audio

    def write(self, data):
        return self.audio.write(data)

class MIC:
    def __init__(self, sck_pin, ws_pin, sd_pin):
        self.sck_pin = sck_pin
        self.ws_pin = ws_pin
        self.sd_pin = sd_pin
        self.mic = I2S(0, sck=self.sck_pin, ws=self.ws_pin, sd=self.sd_pin, mode=I2S.RX, bits=BITS, format=FORMAT, rate=MIC_SAMPLE_RATE, ibuf=32768)

    def __del__(self):
        del self.mic

    def read(self, data):
        return self.mic.readinto(data)

class Request:
    HEADER_SIZE = 8
    MAGIC = b'bee'  # 3字节魔数

    WAV_FORMAT = 1
    PCM_FORMAT = 2

    def __init__(self):
        self.magic = Request.MAGIC  # 3字节魔数
        self.type = 0               # 1字节类型
        self.eof = 0                # 1字节标识结束
        self.dummy = 0              # 1字节保留字段
        self.length = 0             # 2字节长度

        self.data = b''

    @classmethod
    def from_bytes(cls, data: bytes):
        req = cls()

        # 使用 struct.unpack_from 解析前 8 字节
        # 格式字符串：3s B B B H -> 3字节字符串、1字节无符号char、1字节、1字节、2字节短整型
        unpacked = struct.unpack_from('<3sBBBH', data)
        req.magic = unpacked[0]
        req.type = unpacked[1]
        req.eof = unpacked[2]
        req.dummy = unpacked[3]
        req.length = unpacked[4]

        return req

    def to_bytes(self):
        # 使用 struct.pack 打包数据
        # 格式字符串：3s B B B H -> 3字节字符串、1字节无符号char、1字节、1字节、2字节短整型
        packed = struct.pack('<3sBBBH', self.magic, self.type, self.eof, self.dummy, self.length)
        return packed + self.data

class Response:
    HEADER_SIZE = 8
    MAGIC = b'bee'  # 3字节魔数

    PCM_DATA = 1
    EXIT_CHAT = 2
    TOKEN = 3

    def __init__(self):
        self.magic = Request.MAGIC  # 3字节魔数
        self.type = 0               # 1字节类型
        self.eof = 0                # 1字节标识结束
        self.dummy1 = 0             # 1字节保留字段
        self.length = 0             # 2字节长度

        self.data = b''

    @classmethod
    def from_bytes(cls, data: bytes):
        resp = cls()

        # 使用 struct.unpack_from 解析前 8 字节
        # 格式字符串：3s B B B H -> 3字节字符串、1字节无符号char、1字节、1字节、2字节短整型
        unpacked = struct.unpack_from('<3sBBBH', data)
        resp.magic = unpacked[0]
        resp.type = unpacked[1]
        resp.eof = unpacked[2]
        resp.dummy1 = unpacked[3]
        resp.length = unpacked[4]

        return resp

    def to_bytes(self):
        # 使用 struct.pack 打包数据
        # 格式字符串：3s B B B H -> 3字节字符串、1字节无符号char、1字节、1字节、2字节短整型
        packed = struct.pack('<3sBBBH', self.magic, self.type, self.eof, self.dummy1, self.length)
        return packed + self.data

class ExitChatException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Connection:
    HOST = 'dev.lan'
    PORT = 3000

    def __init__(self):
        self.socket = None

    def __del__(self):
        self.disconnect()

    def wait_ready(self):
        if self.socket:
            return
        self.connect()

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((Connection.HOST, Connection.PORT))

    def disconnect(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def send(self, filename):
        req = Request()
        req.type = Request.PCM_FORMAT
        with open(filename, 'rb') as f:
            f.seek(0, 2)
            total_size = f.tell() - 44
            # print(f"wav size: {total_size}")
            f.seek(44, 0) # Skip the WAV header
            sent = 0
            while True:
                data = f.read(SOCKET_BUF_SIZE)
                if not data:
                    break
                req.length = len(data)
                req.data = data
                sent += req.length
                req.eof = 1 if sent >= total_size else 0
                self.socket.sendall(req.to_bytes())
    
    def sendall(self, data, is_finish):
        req = Request()
        req.type = Request.PCM_FORMAT
        req.length = len(data)
        req.data = data
        req.eof = is_finish
        self.socket.sendall(req.to_bytes())

    def receive_stream(self):
        while True:
            resp_header = self.socket.recv(Response.HEADER_SIZE)
            assert len(resp_header) == Response.HEADER_SIZE
            resp = Response.from_bytes(resp_header)
            # print(f"resp: {resp.magic}, eof: {resp.eof}, length: {resp.length}")

            if resp.magic != Response.MAGIC:
                raise ValueError(f"Invalid magic: {resp.magic}")

            if resp.type == Response.EXIT_CHAT:
                raise ExitChatException("Received EXIT_CHAT")

            if resp.type != Response.PCM_DATA:
                continue

            read_done = 0
            while read_done < resp.length:
                chunk_size = min(SOCKET_BUF_SIZE, resp.length - read_done)
                data = self.socket.recv(chunk_size) if self.socket else None
                if not data:
                    break
                read_done += len(data)

                yield data

            if resp.eof == 1:
                break

def create_wav_header(sampleRate, bitsPerSample, num_channels, num_samples):
    datasize = int(num_samples * num_channels * bitsPerSample // 8)
    o = bytes("RIFF",'ascii')                                                   # (4byte) Marks file as RIFF
    o += (datasize + 36).to_bytes(4,'little')                                   # (4byte) File size in bytes excluding this and RIFF marker
    o += bytes("WAVE",'ascii')                                                  # (4byte) File type
    o += bytes("fmt ",'ascii')                                                  # (4byte) Format Chunk Marker
    o += (16).to_bytes(4,'little')                                              # (4byte) Length of above format data
    o += (1).to_bytes(2,'little')                                               # (2byte) Format type (1 - PCM)
    o += (num_channels).to_bytes(2,'little')                                    # (2byte)
    o += (sampleRate).to_bytes(4,'little')                                      # (4byte)
    o += (sampleRate * num_channels * bitsPerSample // 8).to_bytes(4,'little')  # (4byte)
    o += (num_channels * bitsPerSample // 8).to_bytes(2,'little')               # (2byte)
    o += (bitsPerSample).to_bytes(2,'little')                                   # (2byte)
    o += bytes("data",'ascii')                                                  # (4byte) Data Chunk Marker
    o += (datasize).to_bytes(4,'little')                                        # (4byte) Data size in bytes
    return o

class Oled:
    def __init__(self):
        self.oled = happy.Oled(scl=5, sda=4)

    def show(self, text):
        self.oled.Clear()
        self.oled.Text(text, 0, 0)
        self.oled.Show()

def main():
    wakeup = False
    oled = Oled()
    oled.show("INITING...")
    net = happy.Network("ft", "xiyangxiadebenpao")
    button = Pin(9, Pin.IN, Pin.PULL_UP)
    conn = Connection()
    def button_irq_handler(pin):
        nonlocal wakeup
        wakeup = not wakeup
        conn.disconnect()
        raise Exception("WAKEUP")
    button.irq(trigger=Pin.IRQ_RISING, handler=button_irq_handler)
    oled.show("BUTTON WAKEUP...")

    data = bytearray(SOCKET_BUF_SIZE)
    data_mv = memoryview(data)

    while True:
        if not wakeup:
            time.sleep(0.5)
            continue
        time.sleep(0.5)
        try:
            conn.wait_ready()
            mic = MIC(Pin(10), Pin(3), Pin(2))
            oled.show("RECORDING...")
            record_done = 0
            while record_done < RECORD_BUF_SIZE:
                size = min(RECORD_BUF_SIZE - record_done, SOCKET_BUF_SIZE)
                ret = mic.read(data_mv[:size])
                record_done += ret
                conn.sendall(data_mv[:ret], record_done == RECORD_BUF_SIZE)
            del mic

            oled.show("WAITING...")
            # conn.send('test.wav')

            audio = AudioPlayer(Pin(1), Pin(12), Pin(0))
            for chunk in conn.receive_stream():
                audio.write(chunk)
            del audio
        except ExitChatException:
            wakeup = False
            oled.show("EXIT CHAT...")
            conn.disconnect()
            time.sleep(1)
        except Exception as e:
            wakeup = False
            oled.show("ERROR...")
            #print(e)
            conn.disconnect()
            time.sleep(1)
        finally:
            oled.show("BUTTON WAKEUP...")

if __name__ == '__main__':
    main()
