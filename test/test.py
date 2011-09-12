from os import system
from os.path import dirname, abspath
import operator as op

root = dirname(abspath(__file__))
system('protoc --python_out=%s -I%s %s/test.proto' % (root, root, root))
system('cat %s/test.proto | python %s/../palm/palmc/parse.py > %s/test_pb.py' % (root, root, root))


import py.test

import test_pb
import test_pb2

def approx_list_match(l1, l2):
    for i1, i2 in zip(l1, l2):
        if abs(i1 - i2) > 0.02:
            return False
    return True

def foo_match(f1, f2):
    return f1.baz == f2.baz

def list_foo_match(l1, l2):
    for i1, i2 in zip(l1, l2):
        if not foo_match(i1, i2):
            return False
    return True

class TestProto(object):
    def get_proto(self):
        pb = test_pb2.Test(
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
            yn = True,
            msg = test_pb2.Test.Foo(baz="blah"),
            )

        pb.r_sha1.extend(["three", "blind", "mice"])

        pb.r_a.extend([8, 5, 0])
        pb.r_b.extend([-8, 5, 0])
        pb.r_c.extend([-8, 5, 0])

        pb.r_d.extend([39293923923, 39239, 1])
        pb.r_e.extend([-39293923923, 39239, -1])
        pb.r_f.extend([-39293923923, 39239, -1])

        pb.r_g.extend([39293923923, 39239, 1])
        pb.r_h.extend([-39293923923, 39239, -1])

        pb.r_k.extend([-39293923923.11119, 39239.3, -2.0])

        pb.r_l.extend([33923, 39, 1])
        pb.r_m.extend([-33923, 39, -1])

        pb.r_o.extend([-33923.3911, 39.3, -2.0])

        f1 = pb.r_msg.add()
        f2 = pb.r_msg.add()
        f1.baz = "woot"
        f2.baz = "yelp"

        pb.r_yn.extend([True, False, True])

        return pb

    def test_fields(self):
        pb = self.get_proto()
        raw = pb.SerializeToString()
        new = test_pb.Test(raw)

        assert sorted(new.fields()) == sorted(pb.DESCRIPTOR.fields_by_name.keys())

    def fields_test(self, *fields, **kw):
        cmp = kw.pop('cmp', op.eq)
        pb = self.get_proto()
        new = test_pb.Test(pb.SerializeToString())

        for f in fields:
            assert cmp(getattr(pb, f), getattr(new, f))
            getattr(new, '_mod_%s' % f)()

        renew = test_pb.Test(new.dumps())

        for f in fields:
            assert cmp(getattr(pb, f), getattr(renew, f))

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

    def test_message(self):
        self.fields_test('msg', cmp=foo_match)

    def test_bool(self):
        self.fields_test('yn')

    def test_repeated_string(self):
        self.fields_test("r_sha1")

    def test_repeated_uint32(self):
        self.fields_test("r_a")

    def test_repeated_int32(self):
        self.fields_test("r_b")

    def test_repeated_sint32(self):
        self.fields_test("r_c")

    def test_repeated_uint64(self):
        self.fields_test("r_d")

    def test_repeated_int64(self):
        self.fields_test("r_e")

    def test_repeated_sint64(self):
        self.fields_test("r_f")

    def test_repeated_fixed64(self):
        self.fields_test("r_g")

    def test_repeated_sfixed64(self):
        self.fields_test("r_h")

    def test_repeated_double(self):
        self.fields_test("r_k")

    def test_repeated_fixed32(self):
        self.fields_test("r_l")

    def test_repeated_sfixed32(self):
        self.fields_test("r_m")

    def test_repeated_float(self):
        self.fields_test("r_o", cmp=approx_list_match)

    def test_repeated_msg(self):
        self.fields_test("r_msg", cmp=list_foo_match)

    def test_repeated_bool(self):
        self.fields_test("r_yn")

    def test_enum(self):
        m = self.get_proto()
        o = test_pb.Test(m.SerializeToString())
        o.cls = test_pb.Test.AirplaneClass.BUSINESS
        n = test_pb.Test(o.dumps())
        assert n.cls == o.cls

    def test_enum_repeated(self):
        m = self.get_proto()
        o = test_pb.Test(m.SerializeToString())
        o.r_cls.extend([o.AirplaneClass.FIRST, o.AirplaneClass.BUSINESS])
        n = test_pb.Test(o.dumps())
        assert n.r_cls == o.r_cls

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
