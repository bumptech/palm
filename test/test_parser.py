from palm.palmc.parse import make_parser, Package
import pdb

class ParserFixture(object):
    src = ''

    def setup(self):
        parser = make_parser()
        self.result = parser.parse(self.src)[1]

class TestProperEnumOrder(ParserFixture):
    src = '''\
package com.foo.bar;

message Foo {
    optional string bar = 1;
}

enum Baz {
    ACK = 1;
    NACK = 2;
}
'''
    def test_package_found(self):
        package = self.result[0]
        assert isinstance(package, Package)
        assert package.name == "com.foo.bar"

    def test_enums_dont_nest_in_prior_objects(self):
        msgname, (subs, fields, enums) = self.result[1]
        assert 'Baz' not in enums

    def test_top_level_enum_is_in_top_level_result(self):
        ename, efields = self.result[2]
        assert ename == 'Baz'
        assert efields['ACK'] == 1
        assert efields['NACK'] == 2

class TestBooleanDefaults(ParserFixture):
    src = '''\
message Bar {
    optional bool lies = 1 [default = false];
    optional bool damn_lies = 2 [default = true];
}
'''
    
    def test_parses_default_false_as_False(self):
        msgname, (fields, subs, enums) = self.result[0]
        req, type, name, default = fields[1]
        assert default is False

    def test_parses_default_true_as_True(self):
        msgname, (fields, subs, enums) = self.result[0]
        req, type, name, default = fields[2]
        assert default is True
    
