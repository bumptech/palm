from palm.palmc.parse import make_parser


class ParserFixture(object):
    src = ''

    def setup(self):
        parser = make_parser()
        self.result = parser.parse(self.src)[1]

class TestProperEnumOrder(ParserFixture):
    src = '''\
message Foo {
    optional string bar = 1;
}

enum Baz {
    ACK = 1;
    NACK = 2;
}
'''
    def test_enums_dont_nest_in_prior_objects(self):
        msgname, (subs, fields, enums) = self.result[0]
        assert 'Baz' not in enums

    def test_top_level_enum_is_in_top_level_result(self):
        ename, efields = self.result[1]
        assert ename == 'Baz'
        assert efields['ACK'] == 1
        assert efields['NACK'] == 2

