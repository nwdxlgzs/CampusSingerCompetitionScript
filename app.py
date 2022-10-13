import asyncio
import bilibilidanmuku  # B站弹幕获取
import time
import difflib
songlist = [
    # "爱乐之城", "cityofstars",
    # "oldmoney",
    # "rise", "lol18年主题曲",
    # "菊次郎的夏天","summer",
    # "娱乐天空",
    # "he'sthepirate", "he‘sthepirate", "他是海盗",
    # "105度的你",
    # "当年情",
    # "海阔天空",
    # "孤勇者",
    # "lethergo",
    # "红莲之弓矢","红莲の弓矢",
    # "roundabout",
    # "模特",
    # "最佳损友",
    "再见",
    "eldenring"
]


def verifyOK(text):
    if(text == "" or text == None):
        return False
    text = text.replace(" ", "").lower()
    for i in songlist:
        if difflib.SequenceMatcher(None, text, i).quick_ratio() >= 0.5:
            return True,i
    return False,None


def log_danmuku(name, content):
    try:
        ok,matchT = verifyOK(content)
        if(ok):
            oklogfile = open('log-ok.txt', 'a')
            oklogfile.write(
                f'time:{time.time()},  name:{name},  content:{content},  match:{matchT}\n')
            oklogfile.close()
            print(f"发现歌曲：{content}")
        logfile = open('log.txt', 'a')
        logfile.write(
            f'time:{time.time()},  name:{name},  content:{content},  verifyOK:{ok}\n')
        logfile.close()
    except Exception as e:
        print("log_danmuku出错：", e)


def log_everything(m):
    try:
        strm = str(m)
        if(strm.find("STOP_LIVE_ROOM_LIST") != -1):  # STOP_LIVE_ROOM_LIST忽略
            print("发现：STOP_LIVE_ROOM_LIST，屏蔽本次记录")
            return
        if(strm.find("HOT_RANK_CHANGED_V2") != -1):  # HOT_RANK_CHANGED_V2忽略
            print("发现：HOT_RANK_CHANGED_V2，屏蔽本次记录")
            return
        if(strm.find("HOT_RANK_CHANGED") != -1):  # HOT_RANK_CHANGED忽略
            print("发现：HOT_RANK_CHANGED，屏蔽本次记录")
            return
        logfile = open('log-all.txt', 'a')
        logfile.write(f'time:{time.time()},  json:{m}\n')
        logfile.close()
    except Exception as e:
        print("log_everything出错：", e)


async def printer(q):
    while True:
        m = await q.get()
        log_everything(m)
        if m['msg_type'] == 'danmuku':
            log_danmuku(m['name'], m['content'])
            print("获取到弹幕信息：", m)
        else:
            print("获取到其他信息：", m)


async def main(url):
    q = asyncio.Queue()
    dmc = bilibilidanmuku.Bilibili(url, q)
    asyncio.create_task(printer(q))
    await dmc.start()

# 测试直播间
# a = "https://live.bilibili.com/24014907"
# 校园歌手大赛直播间
a = "https://live.bilibili.com/26164677"
#a= input('请输入直播间地址：')
asyncio.run(main(a))
