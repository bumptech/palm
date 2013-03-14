from subprocess import Popen, PIPE
from os.path import dirname, abspath, join
import operator as op

from palm.palm import ProtoRequiredFieldMissing, ProtoValueError


def run(cmd):
    child = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    assert child.wait() == 0, "Command failed:\n%s" % child.stderr.read()

root = dirname(abspath(__file__))
run('protoc --python_out=%s -I%s %s/*.proto' % (root, root, root))
run('palmc %s %s' % (root, root))

import py.test

import test_palm
import test_pb2
import test_nesting_palm
import test_nesting_pb2

class TestPalmc(object):
    def test_duplicate(self):
        duplicate_root = join(root, 'duplicate')
        assert Popen('palmc %s %s' % (duplicate_root, duplicate_root), shell=True, stdout=PIPE, stderr=PIPE).wait() == 1, \
               'Duplicate field numbers not caught'

def approx_list_match(l1, l2):
    for i1, i2 in zip(l1, l2):
        if abs(i1 - i2) > 0.02:
            return False
    return True

def foo_match(f1, f2):
    return f1.baz == f2.baz

def secret_match(f1, f2):
    return f1.code == f2.code and f1.message == f2.message

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

            req_a=911111,
            req_b=-911111,
            req_c=-911111,
            )

        pb.r_sha1.extend(["three", "blind", "mice"])

        pb.r_a.extend(range(500)) # 500 length meaningful for repeat alloc resize!
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

        pb.secret.code = 42
        pb.secret.message = "ssshhh!"

        return pb

    def test_fields(self):
        pb = self.get_proto()
        raw = pb.SerializeToString()
        new = test_palm.Test(raw)

        assert sorted(new.fields()) == sorted(pb.DESCRIPTOR.fields_by_name.keys())

    def fields_test(self, *fields, **kw):
        cmp = kw.pop('cmp', op.eq)
        pb = self.get_proto()
        new = test_palm.Test(pb.SerializeToString())

        for f in fields:
            assert cmp(getattr(pb, f), getattr(new, f))
            getattr(new, '_mod_%s' % f)()

        renew = test_palm.Test(new.dumps(update=True))

        for f in fields:
            assert cmp(getattr(pb, f), getattr(renew, f))

        pbrenew = test_pb2.Test()
        pbrenew.ParseFromString(new.dumps())

        for f in fields:
            assert cmp(getattr(pb, f), getattr(pbrenew, f))


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

    def test_getting_internal_message_value(self):
        # the Foo message defined inside of Test
        self.fields_test('msg', cmp=foo_match)

    def test_getting_external_message_value(self):
        # the Secret message defined outside of Test
        self.fields_test('secret', cmp=secret_match)

    def test_setting_external_message_value(self):
        original = test_palm.Test(req_a=1, req_b=1, req_c=1)
        original.secret = test_palm.Secret(code=1234, message="boo!")
        dumped = original.dumps()
        loaded = test_palm.Test(dumped)
        assert original.secret.code == loaded.secret.code
        assert original.secret.message == loaded.secret.message

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
        o = test_palm.Test(m.SerializeToString())
        o.cls = test_palm.Test.BUSINESS
        n = test_palm.Test(o.dumps())
        assert n.cls == o.cls

    def test_enum_repeated(self):
        m = self.get_proto()
        o = test_palm.Test(m.SerializeToString())
        o.r_cls.extend([o.FIRST, o.BUSINESS])
        n = test_palm.Test(o.dumps())
        assert n.r_cls == o.r_cls

    def test_enum_name(self):
        m = self.get_proto()
        o = test_palm.Test(m.SerializeToString())
        assert o.get_AirplaneClass_name(o.FIRST) == 'FIRST'
        assert o.get_AirplaneClass_name(o.ECONOMY) == 'ECONOMY'
        assert o.get_AirplaneClass_name(o.ECONOMY) != 'BUSINESS'

    def test_default(self):
        pb = self.get_proto()
        new = test_palm.Test(pb.SerializeToString())

        assert new.p == 13
        assert new.q == 23.4
        assert new.r == "cats"

        assert new.dumps() == pb.SerializeToString()

        new.p = 29
        renew = test_palm.Test(new.dumps())

        assert renew.p == 29

    def test_required(self):
        pb = self.get_proto()
        new = test_palm.Test(pb.SerializeToString())
        del new.req_a
        pb.ClearField('req_a')
        try:
            new.dumps()
        except ProtoRequiredFieldMissing:
            pass
        else:
            assert False, "Missing required field not caught"

        assert new.dumps(partial=True) == pb.SerializePartialToString()

    def test_contains_support_works(self):
        pb = test_palm.Test(a=1, b=2, r="test")
        for field in ['a', 'b', 'r']:
            assert field in pb
        for field in ['c', 'p', 'asdggouasdfs']:
            assert field not in pb

    def test_deeply_nested_messages(self):
        pb = test_palm.Test()
        pb.msg = pb.Foo()
        pb.msg.flop = pb.msg.Flop(desc='hhhhaaa')
        # if we don't have an exception here, i'm feeling good
        assert pb.msg.flop.desc == 'hhhhaaa'
        pb.msg.flop.desc = 'rrrraaa'
        assert pb.msg.flop.desc == 'rrrraaa'
        del pb.msg.flop.desc
        assert 'desc' not in pb.msg.flop

    def test_assigning_list_to_repeated_field_raises_ProtoValueError(self):
        pb = test_palm.Test()
        try:
            pb.r_sha1 = ['abc', '123']
        except ProtoValueError:
            pass
        except Exception, e:
            assert 0, "UNEXPECTED EXCEPTION: %s" % e
        else:
            assert 0, "DID NOT RAISE"

    def test_instantiating_a_repeated_with_a_list_raises_ProtoValueError(self):
        try:
            pb = test_palm.Test(r_sha1=['this', 'n', 'that'])
        except ProtoValueError:
            pass
        except Exception, e:
            assert 0, "UNEXPECTED EXCEPTION: %s" % e
        else:
            assert 0, "DID NOT RAISE"

    def test_can_copy_repeated_fields(self):
        pb1 = test_palm.Test(req_a=1, req_b=2, req_c=3)
        pb2 = pb1.copy()

        pb1.r_sha1.extend(['a', 'b', 'c'])

        pb2.r_sha1 = pb1.r_sha1.copy()

        assert pb1.r_sha1 == pb2.r_sha1

    def test_default_true_is_True(self):
        pb = test_palm.Test()
        assert pb.answer1 is True

    def test_default_false_is_False(self):
        pb = test_palm.Test()
        assert pb.answer2 is False

    def test_get(self):
        pb = test_palm.Test()
        assert pb.get('sha1', 'Test') == 'Test'

    def test_field_number_and_name_in_exceptions(self):
        pb = test_palm.Test()
        try:
            pb.dumps()
        except ProtoRequiredFieldMissing, e:
            assert e.args[0] == 50, e.args
            assert e.args[1] == 'req_a', e.args
        else:
            assert 0, "DID NOT RAISE"

    def test_can_get_a_field_number_from_a_field_name(self):
        pb = test_palm.Test()
        assert pb.get_field_number('req_a') == 50

    def test_equal_fresh_protobufs_compare_equally(self):
        pb1 = test_palm.Test(req_a=1, req_b=2, req_c=3)
        pb2 = test_palm.Test(req_a=1, req_b=2, req_c=3)
        assert pb1 == pb2

    def test_unequal_fresh_protobufs_compare_unequally(self):
        pb1 = test_palm.Test(req_a=1, req_b=2, req_c=3)
        pb2 = test_palm.Test(req_a=4, req_b=5, req_c=6)
        assert pb1 != pb2

    def test_equal_loaded_protobufs_compare_equally(self):
        data = test_palm.Test(req_a=1, req_b=2, req_c=3).dumps()
        pb1 = test_palm.Test(data)
        pb2 = test_palm.Test(data)
        assert pb1 == pb2

    def test_unequal_loaded_protobufs_compare_unequally(self):
        data1 = test_palm.Test(req_a=1, req_b=2, req_c=3).dumps()
        data2 = test_palm.Test(req_a=4, req_b=5, req_c=6).dumps()
        pb1 = test_palm.Test(data1)
        pb2 = test_palm.Test(data2)
        assert pb1 != pb2

    def test_equal_fresh_and_loaded_protobufs_compare_equally(self):
        pb1 = test_palm.Test(req_a=1, req_b=2, req_c=3)
        pb2 = test_palm.Test(pb1.dumps())
        assert pb1 == pb2

    def test_equal_complex_protobufs_compare_equally(self):
        pb1 = test_palm.Test()
        pb1.msg = pb1.Foo()
        pb1.msg.flop = pb1.msg.Flop(desc='hhhhaaa')
        pb1.r_msg.append(pb1.Foo(flop=pb1.Foo.Flop(desc="yaar!")))

        pb2 = test_palm.Test()
        pb2.msg = pb2.Foo()
        pb2.msg.flop = pb2.msg.Flop(desc='hhhhaaa')
        pb2.r_msg.append(pb2.Foo(flop=pb2.Foo.Flop(desc="yaar!")))

        assert pb1 == pb2

    def test_unequal_complex_protobufs_compare_unequally(self):
        pb1 = test_palm.Test()
        pb1.msg = pb1.Foo()
        pb1.msg.flop = pb1.msg.Flop(desc='hhhhaaa')
        pb1.r_msg.append(pb1.Foo(flop=pb1.Foo.Flop(desc="yaar!")))

        pb2 = test_palm.Test()
        pb2.msg = pb2.Foo()
        pb2.msg.flop = pb2.msg.Flop(desc='hhhhaaa')
        pb2.r_msg.append(pb2.Foo(flop=pb2.Foo.Flop(desc="yaar!")))
        pb2.r_msg.append(pb2.Foo(flop=pb2.Foo.Flop(desc="yaar?")))

        assert pb1 != pb2

    def test_can_test_for_membership_in_repeated(self):
        pb1 = test_palm.Test()
        pb1.r_msg.append(pb1.Foo(flop=pb1.Foo.Flop(desc="yaar!")))
        assert pb1.Foo(flop=pb1.Foo.Flop(desc="yaar!")) in pb1.r_msg
        assert pb1.Foo(flop=pb1.Foo.Flop(desc="yaar?")) not in pb1.r_msg

    def test_non_pb_objects_compare_unqually_with_pbs(self):
        assert "a" != test_palm.Test()


    def test_stream_equivalence(self):
        pb1 = test_palm.Test()
        pb1.r_secret.append(test_palm.Secret(code=3, message="yup"))
        pb1.r_secret.append(test_palm.Secret(code=9, message="nope"))
        pb2 = pb1.copy()

        for (i1, i2) in zip(pb1.r_secret, pb2.r_secret__stream):
            assert i1 == i2()

        assert list(pb1.r_secret) == map(apply, pb2.r_secret__stream)

    def test_accessing_a_repeated_doesnt_mark_parent_as_modified(self):
        pb1 = test_palm.Test()
        assert not pb1.modified()
        pb1.r_secret
        assert not pb1.modified()

    def test_accessing_a_repeated_doesnt_override_previous_evermod_state(self):
        pb1 = test_palm.Test()
        assert not pb1.modified()
        pb1.req_a = 1
        assert pb1.modified()
        pb1.r_secret
        assert pb1.modified()

    def test_setting_a_repeated_field_to_empty_sets_evermod_to_True(self):
        pb1 = test_palm.Test(req_a=1, req_b=2, req_c=3)
        pb1.r_sha1.extend(['a', 'b', 'c'])
        pb2 = test_palm.Test(pb1.dumps())
        assert not pb2.modified()
        assert pb2.r_sha1
        pb2.r_sha1.set([])
        assert not pb2.r_sha1
        assert pb2.modified()

    def test_can_append_to_empty_repeated_and_stream(self):
        pb1 = test_palm.Test(req_a=1, req_b=2, req_c=3)
        secrets = []
        for i,c in zip(range(5), 'abcde'):
            secrets.append(test_palm.Secret(code=i, message=c))
        pb1.r_secret.extend(secrets)
        expected = secrets
        actual = [c() for c in pb1.r_secret__stream]
        assert actual == expected, [str(a) for a in actual]

    def test_can_append_and_then_stream_and_dumps_works_right(self):
        pb1 = test_palm.Test(req_a=1, req_b=2, req_c=3)
        pb1.r_secret.append(test_palm.Secret(code=100, message="woo!"))
        pb2 = test_palm.Test(pb1.dumps())
        pb2.r_secret.append(test_palm.Secret(code=200, message="hoo!"))
        st = pb2.r_secret__stream
        assert st[0]() == test_palm.Secret(code=100, message="woo!")
        assert st[1]() == test_palm.Secret(code=200, message="hoo!")
        pb3 = test_palm.Test(pb2.dumps())
        assert pb3 == pb2

    def make_foo(self):
        return test_palm.Test.Foo(baz="baz",
                                  flop=test_palm.Test.Foo.Flop(desc="flop"))

    def test_update(self):
        pb1 = test_palm.Test(req_a=1, req_b=2, req_c=3,
                             msg=self.make_foo())
        pb2 = test_palm.Test()
        pb2.update(pb1)
        assert pb1 == pb2

        pb2 = test_palm.Test(a=23)
        pb2.update(pb1)
        assert pb2.a == 23

        pb2 = test_palm.Test()
        pb2.r_sha1.set(['a', 'b', 'c'])
        pb2.update(pb1)
        assert pb2.r_sha1 == ['a', 'b', 'c']

        pb1.r_sha1.set(['d', 'e', 'f'])
        pb2.update(pb1)
        assert pb2.r_sha1 == ['d', 'e', 'f']

    def test_optional_default_enum_value(self):
        pb1 = test_palm.Test()
        assert pb1.chosen_class == test_palm.Test.ECONOMY


class TestNesting(object):
    def test_nested_messages(self):
        """See https://github.com/bumptech/palm/issues/24"""
        p = test_nesting_palm.A()
        p.b = test_nesting_palm.A.B()
        p.b.x = test_nesting_palm.A.B.X(wat=False)

        g = test_nesting_pb2.A()
        g.b.x.wat = False

        assert p.dumps() == g.SerializeToString()

        g2 = test_nesting_pb2.A()
        g2.ParseFromString(p.dumps())
        assert g == g2
