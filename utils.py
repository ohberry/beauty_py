import re
import time
from datetime import datetime
from pathlib import Path

import Everything


def exist(path):
    with Everything.Query(path,
                          matchingOptions=Everything.QueryStringOptions.WholeWord) as q:
        for p in q:
            if p.Path:
                return True
        return False


def local(uid, path):
    with Everything.Query(f"{path}\\{uid}*\\*.mp4 |folder:{path}\\{uid}*\\*",
                          matchingOptions=Everything.QueryStringOptions.WholeWord) as q:
        time_list = [datetime.strptime(Path(p.Path).stem.split('@')[0], '%Y%m%d%H%M%S') for p in q if
                     p.Path is not None]
        if not time_list:
            return 0.0
        return max(time_list).timestamp()


def query(path):
    with Everything.Query(path, maxResults=1, reverseOrder=True,
                          matchingOptions=Everything.QueryStringOptions.WholeWord) as q:
        for p in q:
            return p.Filename


def get_local_time(uid, path):
    t1 = 0
    t2 = 0
    file_name = query(f'file:{path}\\{uid}* depth:4')
    if file_name:
        match = re.search(r'^\d{14}', file_name)
        if match:
            t = time.strptime(match.group(), '%Y%m%d%H%M%S')
            t1 = time.mktime(t)
    folder_name = query(f'folder:{path}\\{uid}* depth:4')
    if folder_name:
        match = re.search(r'^\d{14}', folder_name)
        if match:
            t = time.strptime(match.group(), '%Y%m%d%H%M%S')
            t2 = time.mktime(t)
    return max([t1, t2])


if __name__ == "__main__":
    # note_id = '64c8f5e70000000010032141'
    # print(exist('E:\迅雷云盘\douyin'))
    # print(os.path.join('E:\迅雷云盘\douyin', f'*{note_id}*'))
    # print(datetime.timestamp(datetime.now()))
    # print(local('74953502089', 'E:\\迅雷云盘\\douyin'))
    # query('file:E:\\迅雷云盘\\douyin\\60625700486* depth:4')
    # query('folder:E:\\迅雷云盘\\douyin\\60625700486* depth:4')
    print(get_local_time('2071959634709648', 'E:\\迅雷云盘\\douyin'))
