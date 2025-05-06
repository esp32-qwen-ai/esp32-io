import machine
import network
import binascii
import time
from machine import Pin, SoftI2C
from .ssd1306 import SSD1306_I2C
from .font import Font
import asyncio
import os

class Network:
    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.Connect()
        self.SyncTime()

    def Scan(self):
        security_str = ['open', 'WEP', 'WPA-PSK', 'WPA2-PSK', 'WPA/WPA2-PSK']
        hidden_str = ['visible', 'hidden']
        result = self.wlan.scan()
        for item in result:
            print(f"ssid:{item[0].decode('utf-8')}")
            print(f"\t----> bssid:{binascii.hexlify(item[1])}\tsecurity:{security_str[item[4]]}\thidden:{hidden_str[item[5]]}")

    def Connect(self):
        print('connecting to network...')
        if not self.wlan.isconnected():
            begin = time.ticks_ms()
            self.wlan.connect(self.ssid, self.password)
            while not self.wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), begin) > 6666:
                    self.wlan.disconnect()
                    raise Exception(f'connect network timeout, costtime:{time.ticks_diff(time.ticks_ms(), begin)}ms')
                time.sleep(0.5)
        print('network config:', self.wlan.ifconfig())
    
    def Ifconfig(self):
        return self.wlan.ifconfig()

    def Disconnect(self):
        print('disconnecting network...')
        self.wlan.disconnect()
        while self.wlan.isconnected():
            time.sleep(1)
        print('disconnected network...')

    def IsConnected(self):
        return self.wlan.isconnected()
    
    def SyncTime(self):
        ntp_source = ['ntp1.aliyun.com', 'ntp2.aliyun.com', 'ntp3.aliyun.com', 'ntp4.aliyun.com', 'ntp5.aliyun.com', 'ntp6.aliyun.com', 'ntp7.aliyun.com', 's1a.time.edu.cn', 's1b.time.edu.cn', 's1c.time.edu.cn', 's1d.time.edu.cn', 's1e.time.edu.cn', 's2a.time.edu.cn', 's2b.time.edu.cn', 's2c.time.edu.cn', 's2d.time.edu.cn', 's2e.time.edu.cn', 's2f.time.edu.cn', 's2g.time.edu.cn', 's2h.time.edu.cn', 's2j.time.edu.cn', 's2k.time.edu.cn', 's2m.time.edu.cn']
        import ntptime
        ntptime.NTP_DELTA = 3155644800
        for source in ntp_source:
            retry = 3
            while retry:
                retry -= 1
                try:
                    ntptime.host = source
                    ntptime.settime()
                    return
                except:
                    pass

class Oled:
    def __init__(self, scl = 22, sda = 21, width = 128, height = 64):
        i2c = SoftI2C(scl = Pin(scl), sda = Pin(sda))
        self.width = width
        self.height = height
        self.display = SSD1306_I2C(width, height, i2c)
        self.f_display = Font(self.display)
        self.head_y = 0
        self.body_y = 20
        self.tail_y = 48

    def Text(self, text, x, y, font_size = 16):
        self.f_display.text(text, x, y, font_size)

    def Show(self):
        self.display.show()

    def Clear(self):
        self.display.fill(0)

    def Buffer(self, fb, x, y):
        self.display.blit(fb, x, y)

    def fontWidth(self, font_size):
        if font_size == 8:
            return 8
        return font_size // 2

    def calcOffset(self, txt, font_size, split_size):
        size = len(txt)
        font_width = self.fontWidth(font_size)
        offset = (split_size - size * font_width) // 2
        if offset < 0 or offset >= split_size:
            offset = 0
        return offset

    def clearRow(self, y, height):
        self.display.rect(0, y, 128, height, 0, True)

    async def HeadText(self, txt, offset):
        if len(txt) * self.fontWidth(16) <= self.width:
            self.Text(txt, offset, self.head_y, 16)
        else:
            await self.ScrollPingPong(txt, self.head_y, 16)

    async def BodyText(self, txt, offset):
        self.display.hline(0, 18, self.width, 1)
        self.display.hline(0, 46, self.width, 1)
        if len(txt) * self.fontWidth(24) <= self.width:
            self.Text(txt, offset, self.body_y, 24)
        else:
            await self.ScrollPingPong(txt, self.body_y, 24)

    async def TailText(self, txt, offset):
        if len(txt) * self.fontWidth(16) <= self.width:
            self.Text(txt, offset, self.tail_y, 16)
        else:
            await self.ScrollPingPong(txt, self.tail_y, 16)

    async def gridTextWrapper(self, txt_list, func, font_size):
        font_width = self.fontWidth(font_size)
        txt_width = sum([len(txt) * font_width for txt in txt_list])
        if txt_width <= self.width:
            count = len(txt_list)
            split_size = self.width // count
            for i, txt in enumerate(txt_list):
                offset = self.calcOffset(txt, font_size, split_size)
                offset += i * split_size
                await func(txt, offset)
        else:
            txt = ' '.join(txt_list)
            await func(txt, 0)

    async def HeadCenterText(self, txt):
        await self.HeadGridText([txt])

    async def BodyCenterText(self, txt):
        await self.BodyGridText([txt])

    async def TailCenterText(self, txt):
        await self.TailGridText([txt])

    async def HeadGridText(self, txt_list):
        await self.gridTextWrapper(txt_list, self.HeadText, 16)

    async def BodyGridText(self, txt_list):
        await self.gridTextWrapper(txt_list, self.BodyText, 24)

    async def TailGridText(self, txt_list):
        await self.gridTextWrapper(txt_list, self.TailText, 16)

    async def ScrollRightToLeft(self, txt, y, font_size = 16, speed = 2):
        font_width = self.fontWidth(font_size)
        txt_len = len(txt) * font_width
        window_size = txt_len + self.width
        for i in range(0, window_size + 1, speed):
            x = -i
            if i >= txt_len:
                x = window_size - i
            self.clearRow(y, font_size)
            self.Text(txt, x, y, font_size)
            self.display.show()
            await asyncio.sleep(0.05)

    async def ScrollPingPong(self, txt, y, font_size = 16, speed = 2):
        font_width = self.fontWidth(font_size)
        if len(txt) * font_width > self.width:
            await self.overflowScrollPingPong(txt, y, font_size, speed)
        else:
            await self.innerScrollPingPong(txt, y, font_size, speed)

    async def innerScrollPingPong(self, txt, y, font_size = 16, speed = 2):
        font_width = self.fontWidth(font_size)
        txt_len = len(txt) * font_width
        hole_len = self.width - txt_len
        window_size = hole_len * 2
        for i in range(0, window_size + 1, speed):
            x = i
            if i >= hole_len:
                x = window_size - i
            self.clearRow(y, font_size)
            self.Text(txt, x, y, font_size)
            self.display.show()
            await asyncio.sleep(0.05)

    async def overflowScrollPingPong(self, txt, y, font_size = 16, speed = 2):
        font_width = self.fontWidth(font_size)
        txt_len = len(txt) * font_width
        overflow_len = txt_len - self.width
        window_size = overflow_len * 2
        for i in range(0, window_size + 1, speed):
            x = -i
            if i >= overflow_len:
                x = -(window_size - i)
            self.clearRow(y, font_size)
            self.Text(txt, x, y, font_size)
            self.display.show()
            await asyncio.sleep(0.05)