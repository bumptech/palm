import sys
import os
import traceback
from optparse import OptionParser

from palm.palmc.codegen import gen_module, convert_proto_name
from palm.palmc.parse import make_parser, ProtoParseError, Package

class Namespace(object):
    def __init__(self, package, file):
        self.file = file
        self.package = package

    def __str__(self):
        return "(Namespace) " + str(self.package) + " - " + str(file)

    def __repr__(self):
        return str(self)

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
    namespaces = {}
    parsed = []
    protos = [f for f in os.listdir(d) if f.endswith(".proto")]

    try:
        for p in protos:
            sys.stdout.write(("%s..." % p).ljust(70))
            sys.stdout.flush()
            
            source = open(os.path.join(d, p)).read()

            parser = make_parser()
            r = parser.parse(source)

            _, res, l = r
            if l != len(source):
                raise SyntaxError("Syntax error on line %s near %r" % (
                    source[:l].count('\n') + 1,
                    source[l:l+10]))
            package = [m for m in res if type(m) is Package]
            if len(package) == 1:
                namespaces[package[0].name] = Namespace(package[0].name, p)
                package = package[0].name
                # print "added namespace"
            elif len(package) > 1:
                raise SyntaxError("Proto file %s declares more than 1 package." % p)
            else:
                package = None

            parsed.append((res, package, p))

        for (res, package, p) in parsed:
            sys.stdout.write(("%s..." % p).ljust(70))
            sys.stdout.flush()
            s = gen_module([m for m in res if type(m) is tuple],
                    [m for m in res if type(m) is str],
                    [m for m in res if type(m) is list],
                    options.with_slots,
                    namespaces,
                    package
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

    print "namespaces: " + namespaces.__str__()
    return exit_status
