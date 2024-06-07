import os
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


if __name__ == "__main__":
    note_id = '64c8f5e70000000010032141'
    # print(exist('E:\迅雷云盘\douyin'))
    # print(os.path.join('E:\迅雷云盘\douyin', f'*{note_id}*'))
    # print(datetime.timestamp(datetime.now()))
    print(local('74953502089', 'E:\\迅雷云盘\\douyin'))
