from test_pb2 import Test


t = Test(sha1="thesha",
        a=911111,
        b=-911111,
        c=-911111,

        d=911111111111111,
        e=-911111111111111,
        f=-911111111111111,
        )
t.bars.append(8)
t.bars.append(5)
t.bars.append(0)
print t
open("gen", "wb").write(t.SerializeToString())
