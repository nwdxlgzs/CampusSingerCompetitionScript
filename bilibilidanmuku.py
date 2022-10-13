import json
import random
from struct import pack, unpack
import aiohttp
import zlib
import asyncio
'''
bilibilidanmuku用法
async def printer(q):
    while True:
        m = await q.get()
        if m['msg_type'] == 'danmuku':
            print(m)
            #print(f'{m["name"]}：{m["content"]}')
async def main(url):
    q = asyncio.Queue()
    dmc = bilibilidanmuku.Bilibili(url, q)
    asyncio.create_task(printer(q))
    await dmc.start()

a = input('请输入直播间地址：')
asyncio.run(main(a))
'''
class Bilibili:
    wss_url = 'wss://broadcastlv.chat.bilibili.com/sub'
    heartbeat = b'\x00\x00\x00\x1f\x00\x10\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x5b\x6f\x62\x6a\x65\x63\x74\x20' \
                b'\x4f\x62\x6a\x65\x63\x74\x5d '
    heartbeatInterval = 60

    @staticmethod
    async def get_ws_info(url):
        url = 'https://api.live.bilibili.com/room/v1/Room/room_init?id=' + url.split('/')[-1]
        reg_datas = []
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                room_json = json.loads(await resp.text())
                room_id = room_json['data']['room_id']
                data = json.dumps({
                    'roomid': room_id,
                    'uid': int(1e14 + 2e14 * random.random()),
                    'protover': 1
                }, separators=(',', ':')).encode('ascii')
                data = (pack('>i', len(data) + 16) + b'\x00\x10\x00\x01' +
                        pack('>i', 7) + pack('>i', 1) + data)
                reg_datas.append(data)

        return Bilibili.wss_url, reg_datas

    @staticmethod
    def decode_msg(data):
        dm_list_compressed = []
        dm_list = []
        ops = []
        msgs = []
        while True:
            try:
                packetLen, headerLen, ver, op, seq = unpack('!IHHII', data[0:16])
            except Exception as e:
                break
            if len(data) < packetLen:
                break
            if ver == 1 or ver == 0:
                ops.append(op)
                dm_list.append(data[16:packetLen])
            elif ver == 2:
                dm_list_compressed.append(data[16:packetLen])
            if len(data) == packetLen:
                data = b''
                break
            else:
                data = data[packetLen:]

        for dm in dm_list_compressed:
            d = zlib.decompress(dm)
            while True:
                try:
                    packetLen, headerLen, ver, op, seq = unpack('!IHHII', d[0:16])
                except Exception as e:
                    break
                if len(d) < packetLen:
                    break
                ops.append(op)
                dm_list.append(d[16:packetLen])
                if len(d) == packetLen:
                    d = b''
                    break
                else:
                    d = d[packetLen:]

        for i, d in enumerate(dm_list):
            try:
                msg = {}
                if ops[i] == 5:
                    j = json.loads(d)
                    msg['msg_type'] = {
                        'SEND_GIFT': 'gift',
                        'DANMU_MSG': 'danmuku',
                        'WELCOME': 'enter',
                        'NOTICE_MSG': 'broadcast',
                        'LIVE_INTERACTIVE_GAME': 'interactive_danmuku'  # 新增互动弹幕，经测试与弹幕内容一致
                    }.get(j.get('cmd'), 'other')

                    # 2021-06-03 bilibili 字段更新, 形如 DANMU_MSG:4:0:2:2:2:0
                    if msg.get('msg_type', 'UNKNOWN').startswith('DANMU_MSG'):
                        msg['msg_type'] = 'danmuku'

                    if msg['msg_type'] == 'danmuku':
                        msg['name'] = (j.get('info', ['', '', ['', '']])[2][1]
                                       or j.get('data', {}).get('uname', ''))
                        msg['content'] = j.get('info', ['', ''])[1]
                    elif msg['msg_type'] == 'interactive_danmuku':
                        msg['name'] = j.get('data', {}).get('uname', '')
                        msg['content'] = j.get('data', {}).get('msg', '')
                    elif msg['msg_type'] == 'broadcast':
                        msg['type'] = j.get('msg_type', 0)
                        msg['roomid'] = j.get('real_roomid', 0)
                        msg['content'] = j.get('msg_common', 'none')
                        msg['raw'] = j
                    else:
                        msg['content'] = j
                else:
                    msg = {'name': '', 'content': d, 'msg_type': 'other'}
                msgs.append(msg)
            except Exception as e:
                pass

        return msgs

    #__init__.py
    def __init__(self, url, q):
        self.__url = ''
        self.__hs = None
        self.__ws = None
        self.__stop = False
        self.__dm_queue = q
        if 'http://' == url[:7] or 'https://' == url[:8]:
            self.__url = url
        else:
            self.__url = 'http://' + url
        self.__hs = aiohttp.ClientSession()

    async def init_ws(self):
        ws_url, reg_datas = await self.get_ws_info(self.__url)
        self.__ws = await self.__hs.ws_connect(ws_url)
        if reg_datas:
            for reg_data in reg_datas:
                await self.__ws.send_bytes(reg_data)

    async def heartbeats(self):
        while not self.__stop and self.heartbeat:
            await asyncio.sleep(self.heartbeatInterval)
            try:
                await self.__ws.send_bytes(self.heartbeat)
            except:
                pass

    async def fetch_danmuku(self):
        while not self.__stop:
            async for msg in self.__ws:
                ms = self.decode_msg(msg.data)
                for m in ms:
                    await self.__dm_queue.put(m)
            await asyncio.sleep(1)
            await self.init_ws()
            await asyncio.sleep(1)

    async def start(self):
        await self.init_ws()
        await asyncio.gather(
            self.heartbeats(),
            self.fetch_danmuku(),
        )

    async def stop(self):
        self.__stop = True
        await self.__hs.close()
