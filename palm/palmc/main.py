import sys
import os
import traceback

from palm.palmc.codegen import CodeGenerator, convert_proto_name
from palm.palmc.parse import make_parser


def run():
    assert len(sys.argv) == 3, "exactly two arguments required: path to directory with .proto files and path to destination package"
    d = sys.argv[1]
    od = sys.argv[2]
    exit_status = 0

    protos = [f for f in os.listdir(d) if f.endswith(".proto")]
    codegen = CodeGenerator()

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
            s = codegen.gen_module([m for m in res if type(m) is tuple],
                    [m for m in res if type(m) is str],
                    [m for m in res if type(m) is list],
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
