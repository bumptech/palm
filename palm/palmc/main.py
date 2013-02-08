import sys
import os
import traceback
from optparse import OptionParser

from palm.palmc.codegen import gen_module, convert_proto_name
from palm.palmc.parse import make_parser, ProtoParseError

def run():
    usage = "usage: %prog source dest [options]"

    parser = OptionParser()
    parser.add_option("-s", "--with-slots",
                      dest="with_slots",
                      action="store_true",
                      help="generate code using __slots__")
    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.error("exactly two arguments required: path to directory with .proto files and path to destination package")

    d = args[0]
    od = args[1]
    exit_status = 0

    protos = [f for f in os.listdir(d) if f.endswith(".proto")]

    for p in protos:
        sys.stdout.write(("%s..." % p).ljust(70))
        sys.stdout.flush()

        source = open(os.path.join(d, p)).read()

        try:
            parser = make_parser()
            r = parser.parse(source)

            _, res, l = r
            if l != len(source):
                raise SyntaxError("Syntax error on line %s near %r" % (
                    source[:l].count('\n') + 1,
                    source[l:l+10]))
            s = gen_module([m for m in res if type(m) is tuple],
                    [m for m in res if type(m) is str],
                    [m for m in res if type(m) is list],
                    options.with_slots,
                    )
            open(os.path.join(od, convert_proto_name(p) + ".py"), 'wb').write(s)
        except:
            sys.stdout.write("[FAIL]\n")
            sys.stdout.flush()
            traceback.print_exc()
            exit_status = 1
        else:
            sys.stdout.write("[OKAY]\n")
            sys.stdout.flush()

    return exit_status
