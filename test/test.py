from os import system
from os.path import dirname, abspath

root = dirname(abspath(__file__))
system('protoc --python_out=%s -I%s %s/test.proto' % (root, root, root))
system('cat %s/test.proto | python %s/../palm/palmc/parse.py > %s/test_pb.py' % (root, root, root))


import py.test

import test_pb
import test_pb2


class TestProto(object):
    def get_proto(self):
        return test_pb2.Test(
            sha1="thesha",

            a=911111,
            b=-911111,
            c=-911111,

            d=911111111111111,
            e=-911111111111111,
            f=-911111111111111,

            g=2**64-1,
            h=2**63-1,
            i=-2**63,

            k=float(10**200),

            l=2**32-1,
            m=2**31-1,
            n=-2**31,

            o=float(253),
            )

    def test_fields(self):
        pb = self.get_proto()
        raw = pb.SerializeToString()
        new = test_pb.Test(raw)

        assert sorted(new.fields()) == sorted(pb.DESCRIPTOR.fields_by_name.keys())

    def fields_test(self, *fields):
        pb = self.get_proto()
        new = test_pb.Test(pb.SerializeToString())

        for f in fields:
            assert getattr(pb, f) == getattr(new, f)
            getattr(new, '_mod_%s' % f)()

        renew = test_pb.Test(new.dumps())

        for f in fields:
            assert getattr(pb, f) == getattr(renew, f)

    def test_string(self):
        self.fields_test('sha1')

    def test_int32(self):
        self.fields_test('a', 'b', 'c')

    def test_int64(self):
        self.fields_test('d', 'e', 'f')

    def test_fixed64(self):
        self.fields_test('g', 'h', 'i')

    def test_double(self):
        self.fields_test('k')

    def test_fixed32(self):
        self.fields_test('l', 'm', 'n')

    def test_float(self):
        self.fields_test('o')

    def test_default(self):
        pb = self.get_proto()
        new = test_pb.Test(pb.SerializeToString())

        assert new.p == 13
        assert new.q == 23.4
        assert new.r == "cats"

        assert new.dumps() == pb.SerializeToString()

        new.p = 29
        renew = test_pb.Test(new.dumps())

        assert renew.p == 29
