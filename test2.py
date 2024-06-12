class MyException(Exception):
    def __init__(self, msg):
        super().__init__()
        self.msg = msg

    def __str__(self):
        return self.msg


if __name__ == '__main__':
    try:
        raise Exception('this is a test')
        # raise MyException('this is a test')
    except Exception as e:
        print(e)
